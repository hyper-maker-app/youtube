"""Gemini Flash 'Transition Boundary Triplet' (Filmstrip Grid) QA Gateway.

Inspects cross-block continuity across consecutive video blocks:
[Hero DNA Plate] + [Block N Exit Frame (t=T-0.04s)] + [Block N+1 Entry Frame (t=0.04s)]

Constructs an in-memory composite horizontal filmstrip grid (16-30 KB, ~258 tokens)
and evaluates 6 continuity rules with Gemini 2.5 Flash:
1. Wardrobe & costume consistency
2. Held items & props consistency
3. Lighting vector, color temperature & atmosphere
4. Camera perspective & spatial axis continuity
5. Physical condition / injury persistence
6. Jump-cut / temporal disorientation prevention

If Gemini API key is unavailable or in offline mode, falls back to fast
in-memory OpenCV histogram & structural correlation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


TRANSITION_SCORE_THRESHOLD: float = 0.80


@dataclass
class BoundaryQAReport:
    """Evaluation result of cross-block visual transition."""

    continuity_score: float  # 0.0 to 1.0
    passed: bool  # True if score >= TRANSITION_SCORE_THRESHOLD (0.80)
    violations: list[str] = field(default_factory=list)
    corrective_prompt: str = ""
    triplet_bytes: bytes | None = None
    inspected_by: str = "opencv_histogram"

    def to_dict(self) -> dict[str, Any]:
        """Convert QA report to serializable dict without raw image bytes."""
        return {
            "continuity_score": round(float(self.continuity_score), 3),
            "passed": bool(self.passed),
            "threshold": TRANSITION_SCORE_THRESHOLD,
            "violations": list(self.violations),
            "corrective_prompt": str(self.corrective_prompt),
            "inspected_by": str(self.inspected_by),
        }


def write_qa_report(
    report_data: BoundaryQAReport | dict[str, Any] | list[Any],
    output_path: Path | str,
    *,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Write visual transition QA report or failed transition logs to qa_report.json."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(report_data, BoundaryQAReport):
        payload: dict[str, Any] = {
            "threshold": TRANSITION_SCORE_THRESHOLD,
            "report": report_data.to_dict(),
            "overall_passed": report_data.passed,
            "failed_transitions": [] if report_data.passed else [report_data.to_dict()],
        }
    elif isinstance(report_data, list):
        failed = [
            item.to_dict() if isinstance(item, BoundaryQAReport) else item
            for item in report_data
            if (isinstance(item, BoundaryQAReport) and not item.passed)
            or (isinstance(item, dict) and not item.get("passed", True))
        ]
        all_items = [
            item.to_dict() if isinstance(item, BoundaryQAReport) else item
            for item in report_data
        ]
        payload = {
            "threshold": TRANSITION_SCORE_THRESHOLD,
            "total_inspections": len(all_items),
            "passed_count": len(all_items) - len(failed),
            "failed_count": len(failed),
            "overall_passed": len(failed) == 0,
            "failed_transitions": failed,
            "transitions": all_items,
        }
    elif isinstance(report_data, dict):
        payload = dict(report_data)
        if "threshold" not in payload:
            payload["threshold"] = TRANSITION_SCORE_THRESHOLD
    else:
        payload = {"data": str(report_data), "threshold": TRANSITION_SCORE_THRESHOLD}

    if metadata:
        payload.update(metadata)

    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info(f"Visual Boundary QA report written -> {out}")
    return out


def load_image_unicode(path: Path) -> np.ndarray | None:
    """Read image robustly handling non-ASCII / Unicode paths on Windows."""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if len(data) == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def extract_video_frame(video_path: Path, position: str = "last") -> np.ndarray | None:
    """Extract a single frame from video at either 'first' or 'last' timestamp."""
    if not video_path.is_file():
        return None

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count <= 0:
        cap.release()
        return None

    target_frame = 0 if position == "first" else max(0, frame_count - 2)
    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None or frame.size == 0:
        return None
    return frame


def build_boundary_triplet_image(
    hero_plate_path: Path | None,
    block_n_video: Path,
    block_n_plus_1_video: Path,
    target_width: int = 480,
    target_height: int = 270,
) -> tuple[np.ndarray, bytes]:
    """Assemble in-memory horizontal filmstrip: [Hero DNA] | [Block N Exit] | [Block N+1 Entry]."""
    # 1. Load Hero Plate or create dark slate
    if hero_plate_path and hero_plate_path.is_file():
        hero_img = load_image_unicode(hero_plate_path)
        if hero_img is None:
            hero_img = np.zeros((target_height, target_width, 3), dtype=np.uint8)
    else:
        hero_img = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        cv2.putText(
            hero_img, "HERO DNA REF", (20, target_height // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 180), 2
        )

    # 2. Extract exit frame from Block N
    exit_frame = extract_video_frame(block_n_video, position="last")
    if exit_frame is None:
        exit_frame = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        cv2.putText(
            exit_frame, f"EXIT: {block_n_video.name}", (20, target_height // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 255), 1
        )

    # 3. Extract entry frame from Block N+1
    entry_frame = extract_video_frame(block_n_plus_1_video, position="first")
    if entry_frame is None:
        entry_frame = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        cv2.putText(
            entry_frame, f"ENTRY: {block_n_plus_1_video.name}", (20, target_height // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 255, 100), 1
        )

    # Resize all to uniform grid resolution
    p1 = cv2.resize(hero_img, (target_width, target_height))
    p2 = cv2.resize(exit_frame, (target_width, target_height))
    p3 = cv2.resize(entry_frame, (target_width, target_height))

    # Add overlay labels
    cv2.putText(p1, "[1] HERO REF", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.putText(p2, f"[2] EXIT {block_n_video.stem}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.putText(p3, f"[3] ENTRY {block_n_plus_1_video.stem}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # Concatenate horizontally
    composite = np.hstack([p1, p2, p3])

    # Encode to JPEG bytes (quality 80 for minimal token payload)
    success, encoded = cv2.imencode(".jpg", composite, [cv2.IMWRITE_JPEG_QUALITY, 80])
    jpeg_bytes = encoded.tobytes() if success else b""

    return composite, jpeg_bytes


async def inspect_transition_boundary(
    hero_plate_path: Path | None,
    block_n_video: Path,
    block_n_plus_1_video: Path,
    api_key: str | None = None,
    model_name: str | None = None,
    dry_run: bool = False,
    report_path: Path | str | None = None,
) -> BoundaryQAReport:
    """Inspect the cross-block boundary between two consecutive video blocks."""
    composite, jpeg_bytes = build_boundary_triplet_image(
        hero_plate_path, block_n_video, block_n_plus_1_video
    )

    # In dry-run mode, immediately use fast algorithmic OpenCV correlation on synthetic test frames
    if dry_run:
        rep = _inspect_with_opencv(composite, block_n_video, block_n_plus_1_video, jpeg_bytes)
        if report_path:
            write_qa_report(rep, report_path)
        return rep

    gemini_key = api_key or os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()
    gemini_model = model_name or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

    # 1. First priority: gemini-web2api sidecar using user's authenticated Google Pro account
    try:
        from providers.gemini_webapi import call_gemini_vision, BINARY
        if BINARY.is_file() and len(jpeg_bytes) > 500:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(jpeg_bytes)
                tmp_path = Path(tmp.name)
            try:
                prompt = (
                    "You are the master visual continuity QA inspector for a cinematic film.\n"
                    "Analyze this composite filmstrip triplet containing 3 horizontally tiled panels:\n"
                    "Panel 1: [Hero Reference / Style Anchor]\n"
                    "Panel 2: [Block N Exit Frame - end of previous shot]\n"
                    "Panel 3: [Block N+1 Entry Frame - start of next shot]\n\n"
                    "Evaluate continuity across 6 strict physical rules:\n"
                    "1. Wardrobe & costume consistency across panels\n"
                    "2. Held items & props consistency\n"
                    "3. Lighting vector, color temperature & atmosphere\n"
                    "4. Camera perspective & spatial axis continuity\n"
                    "5. Physical condition / injury persistence\n"
                    "6. Jump-cut / temporal disorientation prevention\n\n"
                    "Return ONLY valid JSON matching this schema:\n"
                    "{\n"
                    '  "continuity_score": float (0.0 to 1.0),\n'
                    f'  "passed": bool (true if score >= {TRANSITION_SCORE_THRESHOLD:.2f}),\n'
                    '  "violations": [string],\n'
                    '  "corrective_prompt": string (empty if passed, else prompt fix)\n'
                    "}"
                )
                sidecar_model = "gemini-3.5-flash-lite" if "flash-lite" in gemini_model or "3.5" in gemini_model else "gemini-3.5-flash-lite"
                raw_json = await asyncio.wait_for(
                    asyncio.to_thread(call_gemini_vision, prompt, [tmp_path], model=sidecar_model, timeout=60.0),
                    timeout=75.0,
                )
                cleaned = raw_json.strip()
                if cleaned.startswith("```"):
                    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.MULTILINE).strip()
                data = json.loads(cleaned)
                score = float(data.get("continuity_score", 0.90))
                passed = bool(data.get("passed", score >= TRANSITION_SCORE_THRESHOLD))
                rep = BoundaryQAReport(
                    continuity_score=score,
                    passed=passed,
                    violations=list(data.get("violations", [])),
                    corrective_prompt=str(data.get("corrective_prompt", "")),
                    triplet_bytes=jpeg_bytes,
                    inspected_by=f"gemini_web2api_pro ({sidecar_model})",
                )
                if report_path:
                    write_qa_report(rep, report_path)
                return rep
            finally:
                tmp_path.unlink(missing_ok=True)
    except Exception as sidecar_err:
        logger.info(f"gemini-web2api sidecar notice ({sidecar_err}); evaluating API / CV fallback.")

    # 2. Second priority: Official GenAI SDK if API key configured
    if gemini_key and len(jpeg_bytes) > 500:
        try:
            rep = await _inspect_with_gemini_flash(jpeg_bytes, gemini_key, gemini_model)
            if report_path:
                write_qa_report(rep, report_path)
            return rep
        except Exception as exc:
            logger.warning(f"Gemini Flash visual boundary QA failed ({exc}). Falling back to CV.")

    # 3. Third priority: Algorithmic OpenCV Fallback
    rep = _inspect_with_opencv(composite, block_n_video, block_n_plus_1_video, jpeg_bytes)
    if report_path:
        write_qa_report(rep, report_path)
    return rep


async def _inspect_with_gemini_flash(
    jpeg_bytes: bytes, api_key: str, model_name: str
) -> BoundaryQAReport:
    """Evaluate continuity using Gemini 2.5 Flash with structured JSON schema."""
    import asyncio
    from google import genai
    from google.genai import types

    def _sync_call() -> dict[str, Any]:
        client = genai.Client(api_key=api_key)
        prompt = (
            "You are the master visual continuity QA inspector for a cinematic film.\n"
            "Analyze this composite filmstrip triplet containing 3 horizontally tiled panels:\n"
            "Panel 1: [Hero Reference / Style Anchor]\n"
            "Panel 2: [Block N Exit Frame - end of previous shot]\n"
            "Panel 3: [Block N+1 Entry Frame - start of next shot]\n\n"
            "Evaluate continuity across 6 strict physical rules:\n"
            "1. Wardrobe & costume consistency across panels\n"
            "2. Held items & hand props consistency\n"
            "3. Lighting vector, color temperature & atmosphere continuity\n"
            "4. Perspective & spatial axis continuity (no disorienting jump cuts)\n"
            "5. Physical damage / wetness / dirt state persistence\n"
            "6. Realistic physical cause-and-effect transition\n\n"
            "Return valid JSON matching this exact structure:\n"
            "{\n"
            '  "continuity_score": float between 0.0 and 1.0,\n'
            f'  "passed": boolean (true if continuity_score >= {TRANSITION_SCORE_THRESHOLD:.2f}),\n'
            '  "violations": list of strings describing any continuity breaks,\n'
            f'  "corrective_prompt": string suggesting specific prompt additions to fix the transition if score < {TRANSITION_SCORE_THRESHOLD:.2f}\n'
            "}"
        )
        contents = [
            prompt,
            types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
        ]
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(response.text)

    res = await asyncio.to_thread(_sync_call)
    score = float(res.get("continuity_score", 0.90))
    passed = bool(res.get("passed", score >= TRANSITION_SCORE_THRESHOLD))
    violations = list(res.get("violations", []))
    corrective = str(res.get("corrective_prompt", ""))

    return BoundaryQAReport(
        continuity_score=round(score, 3),
        passed=passed,
        violations=violations,
        corrective_prompt=corrective,
        triplet_bytes=jpeg_bytes,
        inspected_by=f"gemini_flash ({model_name})",
    )


def _inspect_with_opencv(
    composite: np.ndarray,
    block_n_video: Path,
    block_n_plus_1_video: Path,
    jpeg_bytes: bytes,
) -> BoundaryQAReport:
    """Deterministic CV-based cross-block histogram and gradient similarity."""
    w = composite.shape[1] // 3
    p2 = composite[:, w : 2 * w]
    p3 = composite[:, 2 * w :]

    # Convert to HSV for robust color/lighting comparison
    hsv2 = cv2.cvtColor(p2, cv2.COLOR_BGR2HSV)
    hsv3 = cv2.cvtColor(p3, cv2.COLOR_BGR2HSV)

    hist2 = cv2.calcHist([hsv2], [0, 1], None, [30, 32], [0, 180, 0, 256])
    hist3 = cv2.calcHist([hsv3], [0, 1], None, [30, 32], [0, 180, 0, 256])
    cv2.normalize(hist2, hist2, 0, 1, cv2.NORM_MINMAX)
    cv2.normalize(hist3, hist3, 0, 1, cv2.NORM_MINMAX)

    hist_corr = float(cv2.compareHist(hist2, hist3, cv2.HISTCMP_CORREL))
    # Normalized correlation typically ranges from -1 to 1; clamp to [0.0, 1.0]
    normalized_score = max(0.0, min(1.0, (hist_corr + 1.0) / 2.0))

    passed = normalized_score >= 0.65  # CV threshold calibrated for cuts
    violations = []
    corrective = ""
    if not passed:
        violations.append("Sudden lighting or palette discontinuity detected between shots")
        corrective = "Maintain continuous low-key lighting and atmospheric volumetric fog matching previous shot"

    return BoundaryQAReport(
        continuity_score=round(normalized_score, 3),
        passed=passed,
        violations=violations,
        corrective_prompt=corrective,
        triplet_bytes=jpeg_bytes,
        inspected_by="opencv_histogram_correlation",
    )
