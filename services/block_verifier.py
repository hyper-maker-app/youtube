"""Per-block verification and provenance.

Every block that enters the edit MUST have a `blockNN.provenance.json` sidecar written by the
pipeline at generation time. The sidecar records HOW the file came to exist (provider, prompt hash,
Flow job id) plus the measured motion verdict and the SHA-256 of the exact bytes verified.

Two independent defences against self-deception:
  1. provenance  - a Ken Burns / still-photo render has no generation record, so it cannot enter.
  2. measurement - even a generated clip is rejected if analysis shows frozen or rigid-2D motion.

No network or provider imports here (services/ must stay AST-clean).
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from services.motion_authenticity import ClipMotionReport, analyze_clip

PROVENANCE_SUFFIX = ".provenance.json"
FLOW_META_SUFFIX = ".flow.json"
KIND_FLOW_VIDEO = "flow_video"
KIND_LIPSYNC_HOST = "lipsync_host"
ALLOWED_KINDS = {KIND_FLOW_VIDEO, KIND_LIPSYNC_HOST}

RETRY_MOTION_SUFFIX = (
    "The camera must travel through space with clearly visible parallax between foreground, midground and "
    "background; dust, fabric, flames and vegetation move continuously. Not a still image, not a zoom."
)


class BlockMotionRejected(RuntimeError):
    """A generated block failed provenance or motion-authenticity verification."""


def provenance_path(block_path: Path) -> Path:
    block_path = Path(block_path)
    return block_path.with_name(block_path.stem + PROVENANCE_SUFFIX)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def prompt_sha(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def verify_new_block(path: Path, *, require_diffusion: bool = True) -> tuple[bool, str, ClipMotionReport]:
    """Measure a freshly generated block. Lip-sync hosts only need to be non-frozen (static set, moving face)."""
    rep = analyze_clip(path)
    if not rep.readable:
        return False, "; ".join(rep.reasons) or "unreadable", rep
    if rep.verdict == "frozen":
        return False, "; ".join(rep.reasons), rep
    if require_diffusion:
        if rep.verdict != "diffusion_motion":
            return False, "; ".join(rep.reasons) or f"verdict={rep.verdict}", rep
        if rep.freeze_tail_s >= 1.0:
            return False, f"frozen tail {rep.freeze_tail_s}s", rep
    return True, "ok", rep


def write_provenance(
    block_path: Path,
    *,
    kind: str,
    provider: str,
    prompt: str,
    attempt: int,
    report: ClipMotionReport,
    shot_duration: float,
    extra: dict[str, Any] | None = None,
) -> Path:
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"unknown block kind {kind!r}")
    block_path = Path(block_path)
    flow_meta: dict[str, Any] = {}
    meta_file = block_path.with_name(block_path.stem + FLOW_META_SUFFIX)
    if meta_file.is_file():
        try:
            flow_meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            flow_meta = {}
    payload = {
        "schema": 1,
        "kind": kind,
        "provider": provider,
        "attempt": attempt,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "block_file": block_path.name,
        "sha256": sha256_file(block_path),
        "prompt_sha256": prompt_sha(prompt),
        "shot_duration": shot_duration,
        "flow": flow_meta,
        "motion": report.to_dict(),
        "extra": extra or {},
    }
    out = provenance_path(block_path)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def read_provenance(block_path: Path) -> dict[str, Any] | None:
    p = provenance_path(block_path)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def cached_block_is_trustworthy(block_path: Path, *, min_duration: float = 0.0) -> tuple[bool, str]:
    """Cheap trust check for a block already on disk (no re-analysis): provenance + hash + duration."""
    block_path = Path(block_path)
    prov = read_provenance(block_path)
    if prov is None:
        return False, "no provenance sidecar (unknown origin - possibly an old Ken Burns/still render)"
    if prov.get("kind") not in ALLOWED_KINDS:
        return False, f"unrecognised block kind {prov.get('kind')!r}"
    try:
        if sha256_file(block_path) != prov.get("sha256"):
            return False, "file changed since verification (sha256 mismatch)"
    except OSError as exc:
        return False, f"unreadable: {exc}"
    verdict = (prov.get("motion") or {}).get("verdict")
    if prov.get("kind") == KIND_FLOW_VIDEO and verdict != "diffusion_motion":
        return False, f"recorded motion verdict {verdict!r}"
    dur = float((prov.get("motion") or {}).get("duration") or 0.0)
    if min_duration and dur and dur < min_duration:
        return False, f"clip {dur:.2f}s shorter than required {min_duration:.2f}s"
    return True, "ok"
