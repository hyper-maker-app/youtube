"""Provider-neutral sampled-frame video audit via the configured Gemini sidecar.

Only the extracted still frames are submitted. A pass describes visible sampled
frames, not unsampled motion, audio, or full-frame temporal continuity.
"""
from __future__ import annotations

import json
import math
import re
import tempfile
from pathlib import Path
from typing import Any, Callable, Sequence

from services.multimodal_audit import parse_audit_response
from services.proxy_generator import normalize_scenes


def audit_sampled_frames(
    proxy_path: str | Path,
    scenes: Sequence[dict[str, Any]],
    *,
    model: str,
    invoke: Callable[..., str] | None = None,
    max_images_per_request: int = 12,
    max_requests: int = 100,
) -> dict[str, Any]:
    """Send three time-stamped frames per block to the vision provider.

    Missing frames, malformed JSON, incomplete block coverage, and uncertain
    responses are never substituted with passing results.
    """
    import cv2
    from providers.gemini_webapi import call_gemini_vision

    source = Path(proxy_path)
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError("Audit proxy is missing or empty")
    manifest = normalize_scenes(scenes)
    if not manifest:
        raise ValueError("At least one audit block is required")
    if (isinstance(max_images_per_request, bool) or not isinstance(max_images_per_request, int)
            or max_images_per_request < 3):
        raise ValueError("max_images_per_request must be an integer of at least 3")
    if isinstance(max_requests, bool) or not isinstance(max_requests, int) or max_requests < 1:
        raise ValueError("max_requests must be a positive integer")
    normalize_id = lambda value: re.sub(r"(\d+)", lambda m: str(int(m.group(1))), value)
    if len({normalize_id(scene.block_id) for scene in manifest}) != len(manifest):
        raise ValueError("Audit block IDs must be unique, including zero-padded aliases")
    blocks_per_request = max_images_per_request // 3
    if math.ceil(len(manifest) / blocks_per_request) > max_requests:
        raise ValueError("Audit requires more requests than max_requests permits")
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        capture.release()
        raise ValueError("Audit proxy could not be opened")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0 or frame_count <= 0:
        capture.release()
        raise ValueError("Audit proxy frame timing is unavailable")
    duration = frame_count / fps
    try:
        with tempfile.TemporaryDirectory(prefix="video_qa_frames_") as directory:
            paths: list[Path] = []
            frame_manifest = []
            for scene in manifest:
                if scene.end > duration + 1 / fps:
                    raise ValueError("Audit block extends beyond proxy duration")
                for fraction in (0.25, 0.5, 0.75):
                    position = scene.start + (scene.end - scene.start) * fraction
                    index = min(int(position * fps), frame_count - 1)
                    capture.set(cv2.CAP_PROP_POS_FRAMES, index)
                    ok, frame = capture.read()
                    if not ok or frame is None:
                        raise ValueError(f"Cannot extract audit frame for {scene.block_id}")
                    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if not ok:
                        raise ValueError("Cannot encode audit frame")
                    path = Path(directory) / f"frame_{len(paths):04d}.jpg"
                    path.write_bytes(encoded.tobytes())
                    paths.append(path)
                    frame_manifest.append({"image": len(paths), "block_id": scene.block_id,
                                           "time_seconds": round(index / fps, 3)})
            contract = {
                "schema_version": "1",
                "overall_verdict": "PASS | FLAGGED | NEEDS_REVIEW",
                "blocks": [{"block_id": "manifest ID", "verdict": "PASS | FLAGGED | NEEDS_REVIEW",
                            "confidence": "number 0..1", "review_required": "boolean",
                            "evidence": [{"timecode": "MM:SS.mmm - MM:SS.mmm", "description": "observed fact"}],
                            "defects": [{"defect_type": "string", "severity": "critical | moderate | advisory",
                                         "description": "observed defect", "action": "RE_RENDER_CLIP | RE_TIMING_ONLY | PASS",
                                         "evidence": [{"timecode": "MM:SS.mmm - MM:SS.mmm", "description": "observed fact"}]}]}],
            }
            prompt_template = (
                "Audit these numbered still images in the exact order supplied. "
                "They are sparse video frames, not a full video or audio. "
                "Do not infer unseen motion, audio, or events. For uncertainty use NEEDS_REVIEW. "
                "Include every manifest block exactly once. Evidence must refer to the sampled "
                "times for its block. Each evidence range must identify one sampled instant "
                "with matching start and end timestamps, not a span of unobserved video. "
                "Include defects only when actually visible; use "
                "RE_RENDER_CLIP for visible defects requiring replacement. Return only a JSON object "
                "with the following shape and concrete values (no alternatives or placeholders):\n"
                + json.dumps(contract, ensure_ascii=True)
            )
            reports = []
            rows = []
            batch_metadata = []
            for start_idx in range(0, len(manifest), blocks_per_request):
                batch_scenes = manifest[start_idx:start_idx + blocks_per_request]
                first_frame = start_idx * 3
                batch_paths = paths[first_frame:first_frame + len(batch_scenes) * 3]
                batch_manifest = [dict(item, image=i + 1, global_image=first_frame + i + 1)
                                  for i, item in enumerate(frame_manifest[first_frame:first_frame + len(batch_paths)])]
                prompt = prompt_template + "\nSampled image manifest: " + json.dumps(batch_manifest, ensure_ascii=True)
                response = (invoke or call_gemini_vision)(prompt, batch_paths, model=model, timeout=60.0)
                if not isinstance(response, str):
                    raise ValueError("Vision provider returned a non-text response")
                payload = json.loads(response.strip())
                report = parse_audit_response(payload, expected_block_ids=[scene.block_id for scene in batch_scenes])
                reports.append(report)
                batch_rows = [dict(block.raw) for block in report.blocks]
                # Preserve batch-level uncertainty even if the provider labels
                # all of that batch's individual blocks PASS. The downstream
                # parser gives flagged blocks priority unless a block itself
                # carries review_required.
                if report.overall_verdict == "NEEDS_REVIEW":
                    batch_rows[0]["review_required"] = True
                rows.extend(batch_rows)
                batch_metadata.append({"batch": len(reports), "block_ids": [s.block_id for s in batch_scenes],
                                       "image_count": len(batch_paths), "overall_verdict": report.overall_verdict})
            versions = {report.schema_version for report in reports}
            if len(versions) != 1:
                raise ValueError("Audit batches returned inconsistent schema versions")
            verdict = ("NEEDS_REVIEW" if any(r.overall_verdict == "NEEDS_REVIEW" for r in reports)
                       else "FLAGGED" if any(r.overall_verdict == "FLAGGED" for r in reports) else "PASS")
            payload = {"schema_version": reports[0].schema_version, "overall_verdict": verdict, "blocks": rows}
            report = parse_audit_response(payload, expected_block_ids=[scene.block_id for scene in manifest])
            by_id = {scene.block_id: scene for scene in manifest}
            for block in report.blocks:
                # Accept the parser's equivalent zero-padded identifiers while
                # retaining strict correspondence with the sampled manifest.
                scene = next(item for key, item in by_id.items() if normalize_id(key) == normalize_id(block.block_id))
                sampled = [item["time_seconds"] for item in frame_manifest if item["block_id"] == scene.block_id]
                evidence = list(block.evidence) + [item for defect in block.defects for item in defect.evidence]
                for item in evidence:
                    left, right = (part.strip() for part in re.split(r"\s*-\s*", item.timecode, maxsplit=1))
                    def seconds(value):
                        parts = value.split(":")
                        return sum(float(part) * (60 ** index) for index, part in enumerate(reversed(parts)))
                    start, end = seconds(left), seconds(right)
                    if (start > end or start < scene.start - 0.05 or end > scene.end + 0.05
                            or not any(abs(start - sample) <= 0.05 and abs(end - sample) <= 0.05
                                       for sample in sampled)):
                        raise ValueError(f"Audit evidence does not match sampled frames: {block.block_id}")
            # Preserve the actual frame indices and timestamps used in this
            # invocation. These are local observations, not provider claims.
            payload["sample_manifest"] = frame_manifest
            payload["audit_scope"] = "sampled_frames_only"
            payload["batches"] = batch_metadata
            payload["max_images_per_request"] = max_images_per_request
            return payload
    finally:
        capture.release()
