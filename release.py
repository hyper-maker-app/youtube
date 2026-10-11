"""Deterministic publishing-readiness report.  It never uploads or publishes media."""

from __future__ import annotations

import json
from pathlib import Path

import config
import editor
from timeline import TimelinePlan


def write_release_report(
    out_dir: Path,
    final: Path,
    captions_path: Path | None,
    research: dict | None,
    quality: dict | None,
    timeline: TimelinePlan,
) -> dict:
    info = editor.probe(final)
    checks: list[dict] = []
    def check(name: str, ok: bool, severity: str, detail: str) -> None:
        checks.append({"name": name, "status": "pass" if ok else severity, "detail": detail})
    check("video_geometry", info.width == config.WIDTH and info.height == config.HEIGHT, "fail", f"{info.width}x{info.height}; expected {config.WIDTH}x{config.HEIGHT}")
    check("fps", info.fps is not None and abs(info.fps - config.FPS) < 0.1, "fail", f"{info.fps}; expected {config.FPS}")
    # ``target_duration`` is the persisted final render budget and already
    # includes the cloned tail.  Adding TAIL_HOLD again rejects valid renders.
    expected_duration = (
        float(timeline.target_duration)
        if timeline.target_duration is not None
        else float(timeline.total_duration)
    )
    check("duration", info.duration is not None and abs(info.duration - expected_duration) <= 0.35, "fail", f"{info.duration}; expected {expected_duration}")
    check("audio", info.has_audio, "fail", "audio stream present" if info.has_audio else "missing audio stream")
    check("captions", captions_path is not None and captions_path.exists(), "review", "caption artifact present" if captions_path else "captions disabled or missing")
    all_blocks = (quality or {}).get("blocks", [])
    bad_blocks = [b for b in all_blocks if not b.get("accepted")]
    blocks_ok = (len(bad_blocks) == 0) and (len(all_blocks) > 0 if quality else True)
    check("block_quality", blocks_ok, "fail", f"{len(bad_blocks)} rejected block(s)" if bad_blocks else ("no blocks evaluated in quality report" if (quality and not all_blocks) else "all evaluated blocks accepted"))
    visual_blockers = [b for b in (quality or {}).get("blocks", []) if b.get("visual_quality_blocker")]
    check("visual_quality", not visual_blockers, "fail", f"{len(visual_blockers)} blocking visual-quality rejection(s)")
    subjective_reviews = [b for b in (quality or {}).get("blocks", []) if b.get("visual_quality") and not b.get("visual_quality_blocker") and not b.get("visual_quality", {}).get("accepted", True)]
    check("visual_review", not subjective_reviews, "review", f"{len(subjective_reviews)} non-blocking visual review note(s)")
    semantic_blockers = [b for b in (quality or {}).get("blocks", []) if b.get("semantic_quality_blocker")]
    check("semantic_continuity", not semantic_blockers, "fail", f"{len(semantic_blockers)} blocking state/event continuity rejection(s)")
    semantic_reviews = [
        b for b in (quality or {}).get("blocks", [])
        if b.get("semantic_quality") and not b.get("semantic_quality_blocker")
        and not b.get("semantic_quality", {}).get("accepted", True)
    ]
    check("semantic_review", not semantic_reviews, "review", f"{len(semantic_reviews)} non-blocking semantic review note(s)")
    factual = (research or {}).get("content_type") == "factual"
    check("claim_evidence", not factual or (research or {}).get("status") == "pass", "review", (research or {}).get("status", "missing"))
    status = "fail" if any(c["status"] == "fail" for c in checks) else "review" if any(c["status"] == "review" for c in checks) else "pass"
    payload = {
        "schema_version": 3,
        "status": status,
        "publishable": status == "pass",
        "checks": checks,
        "timeline": timeline.to_dict(),
        "review": {"visual_notes": subjective_reviews, "semantic_notes": semantic_reviews},
        "final": str(final),
        "contact_sheet": (quality or {}).get("contact_sheet"),
    }
    path = Path(out_dir) / "release_report.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload
