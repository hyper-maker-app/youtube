"""Strict, provider-neutral parsing and block-level triage for video QA."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable


class AuditParseError(ValueError):
    """Raised when an audit response cannot be trusted as a QA result."""


_TIMECODE = re.compile(r"^(?:\d{2}:)?\d{2}:\d{2}\.\d{3}\s*-\s*(?:\d{2}:)?\d{2}:\d{2}\.\d{3}$|^\d{2}:\d{2}\.\d{3}\s*-\s*\d{2}:\d{2}\.\d{3}$")
_VERDICTS = {"PASS", "FLAGGED", "NEEDS_REVIEW"}
_SEVERITIES = {"critical", "moderate", "advisory"}


@dataclass(frozen=True)
class AuditEvidence:
    timecode: str
    description: str
    frame_index: int | None = None
    source_hash: str | None = None


@dataclass(frozen=True)
class BlockDefect:
    defect_type: str
    severity: str
    description: str
    action: str
    evidence: tuple[AuditEvidence, ...]


@dataclass(frozen=True)
class BlockAudit:
    block_id: str
    verdict: str
    confidence: float
    evidence: tuple[AuditEvidence, ...] = ()
    defects: tuple[BlockDefect, ...] = ()
    recommended_patch: str | None = None
    review_required: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class AuditReport:
    schema_version: str
    overall_verdict: str
    blocks: tuple[BlockAudit, ...]
    confidence: float
    review_required: bool
    source: str = "multimodal"

    @property
    def patch_blocks(self) -> tuple[str, ...]:
        return tuple(
            block.block_id for block in self.blocks
            if block.verdict == "FLAGGED" and any(d.action == "RE_RENDER_CLIP" for d in block.defects)
        )


def _strict_load(payload: str | bytes | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if not isinstance(payload, (str, bytes)):
        raise AuditParseError("Audit response must be a JSON object or JSON text")
    text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    if text != text.strip() or "```" in text:
        raise AuditParseError("Audit response contains non-JSON wrapper text")
    try:
        def reject_constant(value: str) -> None:
            raise ValueError(value)
        value = json.loads(text, parse_constant=reject_constant)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AuditParseError("Audit response is malformed JSON") from exc
    if not isinstance(value, dict):
        raise AuditParseError("Audit response root must be an object")
    return value


def _evidence(value: Any) -> AuditEvidence:
    if not isinstance(value, dict):
        raise AuditParseError("Evidence entries must be objects")
    timecode = value.get("timecode", value.get("timestamp_range"))
    description = value.get("description", value.get("observed", ""))
    if not isinstance(timecode, str) or not _TIMECODE.fullmatch(timecode):
        raise AuditParseError("Evidence requires a valid timecode range")
    if not isinstance(description, str) or not description.strip():
        raise AuditParseError("Evidence requires a description")
    frame = value.get("frame_index")
    if frame is not None and (not isinstance(frame, int) or frame < 0):
        raise AuditParseError("Evidence frame_index must be a non-negative integer")
    source_hash = value.get("source_hash")
    if source_hash is not None and (not isinstance(source_hash, str) or not source_hash.strip()):
        raise AuditParseError("Evidence source_hash must be a non-empty string")
    return AuditEvidence(timecode, description.strip(), frame, source_hash)


def _defect(value: Any) -> BlockDefect:
    if not isinstance(value, dict):
        raise AuditParseError("Defects must be objects")
    defect_type = value.get("defect_type")
    severity = value.get("severity")
    description = value.get("description", value.get("defect_description"))
    action = value.get("action", value.get("action_directive"))
    evidence = tuple(_evidence(item) for item in value.get("evidence", []))
    if not isinstance(defect_type, str) or not defect_type.strip():
        raise AuditParseError("Defects require defect_type")
    if severity not in _SEVERITIES or not isinstance(description, str) or not description.strip():
        raise AuditParseError("Defect severity or description is invalid")
    if action not in {"RE_RENDER_CLIP", "RE_TIMING_ONLY", "PASS"}:
        raise AuditParseError("Defect action is invalid")
    if not evidence:
        raise AuditParseError("Every defect requires evidence")
    return BlockDefect(defect_type, severity, description.strip(), action, evidence)


def parse_audit_response(
    payload: str | bytes | dict[str, Any],
    *,
    expected_block_ids: Iterable[str] | None = None,
    min_confidence: float = 0.80,
) -> AuditReport:
    """Parse and triage a strict block audit; malformed or uncertain input cannot pass."""
    if not 0 <= min_confidence <= 1:
        raise ValueError("min_confidence must be between 0 and 1")
    data = _strict_load(payload)
    if not isinstance(data.get("schema_version"), str) or not data["schema_version"].strip():
        raise AuditParseError("schema_version is required")
    rows = data.get("blocks")
    if not isinstance(rows, list) or not rows:
        raise AuditParseError("blocks must be a non-empty array")
    expected_raw = set(expected_block_ids or ())
    expected_norm = {re.sub(r"(\d+)", lambda m: str(int(m.group(1))), x): x for x in expected_raw}
    seen: set[str] = set()
    parsed: list[BlockAudit] = []
    for row in rows:
        if not isinstance(row, dict):
            raise AuditParseError("Each block audit must be an object")
        block_id = row.get("block_id")
        confidence = row.get("confidence")
        verdict = row.get("verdict")
        if not isinstance(block_id, str) or not block_id.strip():
            raise AuditParseError("Each block requires a unique block_id")
        matched_expected = block_id
        if expected_raw:
            if block_id in expected_raw:
                matched_expected = block_id
            else:
                norm = re.sub(r"(\d+)", lambda m: str(int(m.group(1))), block_id)
                if norm in expected_norm:
                    matched_expected = expected_norm[norm]
                else:
                    raise AuditParseError(f"Unexpected block_id: {block_id}")
        if matched_expected in seen:
            raise AuditParseError("Each block requires a unique block_id")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
            raise AuditParseError(f"Invalid confidence for block {block_id}")
        if verdict not in _VERDICTS:
            raise AuditParseError(f"Invalid verdict for block {block_id}")
        evidence = tuple(_evidence(item) for item in row.get("evidence", []))
        defects = tuple(_defect(item) for item in row.get("defects", []))
        if not evidence:
            raise AuditParseError(f"Block {block_id} requires timecoded evidence")
        uncertain = confidence < min_confidence
        needs_review = bool(row.get("review_required", False)) or uncertain or verdict == "NEEDS_REVIEW"
        if verdict == "PASS" and (needs_review or defects):
            verdict = "NEEDS_REVIEW"
        if verdict == "FLAGGED" and not defects:
            raise AuditParseError(f"Flagged block {block_id} has no defects")
        seen.add(matched_expected)
        parsed.append(BlockAudit(block_id, verdict, float(confidence), evidence, defects,
                                 row.get("recommended_patch"), needs_review, row))
    if expected_raw and seen != expected_raw:
        raise AuditParseError("Audit did not cover every expected block")
    overall = str(data.get("overall_verdict", ""))
    if overall not in _VERDICTS:
        overall = "NEEDS_REVIEW"
    if any(block.verdict == "FLAGGED" for block in parsed):
        overall = "FLAGGED"
    if any(block.review_required or block.verdict == "NEEDS_REVIEW" for block in parsed):
        overall = "NEEDS_REVIEW"
    confidence = min(block.confidence for block in parsed)
    return AuditReport(data["schema_version"], overall, tuple(parsed), confidence,
                       overall == "NEEDS_REVIEW", str(data.get("source", "multimodal")))


def audit_with_adapter(
    adapter: Callable[[Any], str | bytes | dict[str, Any]],
    proxy: Any,
    *,
    expected_block_ids: Iterable[str] | None = None,
    min_confidence: float = 0.80,
) -> AuditReport:
    """Call an injected adapter and apply the same strict parser used by CLI callers."""
    return parse_audit_response(adapter(proxy), expected_block_ids=expected_block_ids,
                                min_confidence=min_confidence)
