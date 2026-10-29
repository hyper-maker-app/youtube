"""Deterministic Signal Quality Gate for Generated Keyframes and Video Clips.

Performs fast, algorithmic CV-based quality verification (ADR-066):
1. Sharpness & Blur: Laplacian variance to catch diffusion melting / motion blur.
2. Histogram Dynamic Range: Detects crushed blacks or blown-out highlights.
3. Geometry & Aspect Ratio: Validates target format dimensions (1080x1920 or 1920x1080).
4. Letterbox & Edge Invariants: Detects black borders / letterboxing.

By default, operates in ADVISORY mode (logs warnings without failing production runs),
protecting expensive AI generation compute unless VISION_QA_STRICT=true is set.

Strictly AST-clean: Uses only cv2 and numpy. Zero network or provider imports.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    """Detailed visual quality assessment report."""

    path: str
    asset_type: str  # "image" | "video_frame_sample"
    sharpness_score: float  # cv2.Laplacian variance (> 100 is typically sharp)
    dynamic_range_score: float  # 0.0 - 1.0 histogram spread
    geometry_valid: bool  # True if dimensions match target
    letterbox_detected: bool  # True if black border rows/cols exist
    aspect_ratio_correct: bool  # True if close to 16:9 or 9:16
    overall_quality_score: float  # Composite 0.0 - 1.0
    verdict: str  # "PASS" | "QUARANTINE_ADVISORY" | "REJECT"
    reasons: list[str] = field(default_factory=list)

    @property
    def is_passed(self) -> bool:
        return self.verdict == "PASS"


class VisionQualityGate:
    """Algorithmic visual quality gate with advisory-first safety."""

    def __init__(
        self,
        sharpness_min: float | None = None,
        dynamic_range_min: float | None = None,
        strict_mode: bool | None = None,
    ) -> None:
        self.sharpness_min = (
            sharpness_min
            if sharpness_min is not None
            else float(os.getenv("VISION_SHARPNESS_MIN", "80.0"))
        )
        self.dynamic_range_min = (
            dynamic_range_min
            if dynamic_range_min is not None
            else float(os.getenv("VISION_DYNRANGE_MIN", "0.30"))
        )
        self.strict_mode = (
            strict_mode
            if strict_mode is not None
            else (os.getenv("VISION_QA_STRICT", "false").lower() == "true")
        )

    def _compute_sharpness(self, gray: np.ndarray) -> float:
        """Compute Laplacian variance as focus / blur indicator."""
        if gray.size == 0:
            return 0.0
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    def _compute_dynamic_range(self, gray: np.ndarray) -> float:
        """Calculate dynamic range score based on luminance histogram spread."""
        if gray.size == 0:
            return 0.0
        p5, p95 = np.percentile(gray, [5, 95])
        # Normalized spread between 5th and 95th percentile
        spread = float(p95 - p5) / 255.0
        return max(0.0, min(1.0, spread))

    def _check_geometry(
        self, frame: np.ndarray, expected_format: str = "16:9"
    ) -> tuple[bool, bool]:
        """Verify image height, width, and aspect ratio match expectation."""
        h, w = frame.shape[:2]
        if h == 0 or w == 0:
            return False, False

        actual_ar = float(w) / float(h)
        fmt = str(expected_format).strip()

        if fmt == "9:16":
            expected_ar = 9.0 / 16.0
            # Target Shorts: 1080x1920 or 720x1280
            dims_match = (w, h) in ((1080, 1920), (720, 1280), (360, 640))
        else:
            expected_ar = 16.0 / 9.0
            # Target Longform: 1920x1080 or 1280x720
            dims_match = (w, h) in ((1920, 1080), (1280, 720), (640, 360))

        ar_match = abs(actual_ar - expected_ar) < 0.05
        return (dims_match or ar_match), ar_match

    def _detect_letterbox(self, gray: np.ndarray, margin_px: int = 12) -> bool:
        """Detect solid black letterbox/pillarbox borders along outer edges."""
        h, w = gray.shape[:2]
        if h <= margin_px * 2 or w <= margin_px * 2:
            return False

        # Sample top, bottom, left, and right border bands
        top = gray[:margin_px, :]
        bot = gray[-margin_px:, :]
        left = gray[:, :margin_px]
        right = gray[:, -margin_px:]

        black_threshold = 8.0  # Average luminance under 8 is near-pure black
        has_horizontal_bars = (np.mean(top) < black_threshold) and (np.mean(bot) < black_threshold)
        has_vertical_bars = (np.mean(left) < black_threshold) and (np.mean(right) < black_threshold)

        return bool(has_horizontal_bars or has_vertical_bars)

    def analyze_frame(
        self,
        frame: np.ndarray,
        expected_format: str = "16:9",
        asset_path: str = "memory_frame",
        asset_type: str = "image",
    ) -> QualityReport:
        """Evaluate a single BGR frame."""
        if frame is None or frame.size == 0:
            return QualityReport(
                path=asset_path,
                asset_type=asset_type,
                sharpness_score=0.0,
                dynamic_range_score=0.0,
                geometry_valid=False,
                letterbox_detected=False,
                aspect_ratio_correct=False,
                overall_quality_score=0.0,
                verdict="REJECT" if self.strict_mode else "QUARANTINE_ADVISORY",
                reasons=["Empty or corrupted image frame"],
            )

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        sharpness = self._compute_sharpness(gray)
        dynamic_range = self._compute_dynamic_range(gray)
        geo_valid, ar_correct = self._check_geometry(frame, expected_format)
        letterbox = self._detect_letterbox(gray)

        reasons: list[str] = []
        if sharpness < self.sharpness_min:
            reasons.append(f"Low sharpness score {sharpness:.1f} < threshold {self.sharpness_min}")
        if dynamic_range < self.dynamic_range_min:
            reasons.append(f"Compressed dynamic range {dynamic_range:.2f} < threshold {self.dynamic_range_min}")
        if not ar_correct:
            reasons.append(f"Aspect ratio incorrect for expected {expected_format}")
        if letterbox:
            reasons.append("Black letterbox/pillarbox borders detected")

        # Composite score calculation (0.0 - 1.0)
        norm_sharpness = min(1.0, sharpness / 200.0)
        composite = (
            0.40 * norm_sharpness
            + 0.30 * dynamic_range
            + 0.15 * (1.0 if ar_correct else 0.0)
            + 0.15 * (0.0 if letterbox else 1.0)
        )

        if not reasons:
            verdict = "PASS"
        else:
            verdict = "REJECT" if self.strict_mode else "QUARANTINE_ADVISORY"

        return QualityReport(
            path=asset_path,
            asset_type=asset_type,
            sharpness_score=sharpness,
            dynamic_range_score=dynamic_range,
            geometry_valid=geo_valid,
            letterbox_detected=letterbox,
            aspect_ratio_correct=ar_correct,
            overall_quality_score=composite,
            verdict=verdict,
            reasons=reasons,
        )

    def analyze_image(
        self, image_path: Path | str, expected_format: str = "16:9"
    ) -> QualityReport:
        """Analyze a static image file on disk."""
        path = Path(image_path)
        if not path.is_file():
            return QualityReport(
                path=str(path),
                asset_type="image",
                sharpness_score=0.0,
                dynamic_range_score=0.0,
                geometry_valid=False,
                letterbox_detected=False,
                aspect_ratio_correct=False,
                overall_quality_score=0.0,
                verdict="REJECT" if self.strict_mode else "QUARANTINE_ADVISORY",
                reasons=[f"File not found: {path}"],
            )

        frame = cv2.imread(str(path))
        return self.analyze_frame(
            frame,
            expected_format=expected_format,
            asset_path=str(path),
            asset_type="image",
        )

    def analyze_video_sample(
        self, video_path: Path | str, sample_count: int = 5, expected_format: str = "16:9"
    ) -> QualityReport:
        """Sample multiple evenly-spaced frames from a video file."""
        path = Path(video_path)
        if not path.is_file():
            return QualityReport(
                path=str(path),
                asset_type="video_frame_sample",
                sharpness_score=0.0,
                dynamic_range_score=0.0,
                geometry_valid=False,
                letterbox_detected=False,
                aspect_ratio_correct=False,
                overall_quality_score=0.0,
                verdict="REJECT" if self.strict_mode else "QUARANTINE_ADVISORY",
                reasons=[f"Video not found: {path}"],
            )

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return QualityReport(
                path=str(path),
                asset_type="video_frame_sample",
                sharpness_score=0.0,
                dynamic_range_score=0.0,
                geometry_valid=False,
                letterbox_detected=False,
                aspect_ratio_correct=False,
                overall_quality_score=0.0,
                verdict="REJECT" if self.strict_mode else "QUARANTINE_ADVISORY",
                reasons=["Unable to open video stream via OpenCV"],
            )

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            cap.release()
            return QualityReport(
                path=str(path),
                asset_type="video_frame_sample",
                sharpness_score=0.0,
                dynamic_range_score=0.0,
                geometry_valid=False,
                letterbox_detected=False,
                aspect_ratio_correct=False,
                overall_quality_score=0.0,
                verdict="REJECT" if self.strict_mode else "QUARANTINE_ADVISORY",
                reasons=["Video stream contains 0 frames"],
            )

        step = max(1, total_frames // (sample_count + 1))
        reports: list[QualityReport] = []

        try:
            for i in range(1, sample_count + 1):
                idx = min(total_frames - 1, i * step)
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if ret and frame is not None:
                    rep = self.analyze_frame(
                        frame,
                        expected_format=expected_format,
                        asset_path=str(path),
                        asset_type="video_frame_sample",
                    )
                    reports.append(rep)
        finally:
            cap.release()

        if not reports:
            return QualityReport(
                path=str(path),
                asset_type="video_frame_sample",
                sharpness_score=0.0,
                dynamic_range_score=0.0,
                geometry_valid=False,
                letterbox_detected=False,
                aspect_ratio_correct=False,
                overall_quality_score=0.0,
                verdict="REJECT" if self.strict_mode else "QUARANTINE_ADVISORY",
                reasons=["Failed to read any video frames"],
            )

        # Aggregate metrics across sampled frames
        avg_sharpness = float(np.mean([r.sharpness_score for r in reports]))
        avg_dyn = float(np.mean([r.dynamic_range_score for r in reports]))
        avg_composite = float(np.mean([r.overall_quality_score for r in reports]))
        any_letterbox = any(r.letterbox_detected for r in reports)
        all_geo = all(r.geometry_valid for r in reports)
        all_ar = all(r.aspect_ratio_correct for r in reports)

        all_reasons: list[str] = []
        for r in reports:
            for reason in r.reasons:
                if reason not in all_reasons:
                    all_reasons.append(reason)

        if not all_reasons:
            verdict = "PASS"
        else:
            verdict = "REJECT" if self.strict_mode else "QUARANTINE_ADVISORY"

        return QualityReport(
            path=str(path),
            asset_type="video_frame_sample",
            sharpness_score=avg_sharpness,
            dynamic_range_score=avg_dyn,
            geometry_valid=all_geo,
            letterbox_detected=any_letterbox,
            aspect_ratio_correct=all_ar,
            overall_quality_score=avg_composite,
            verdict=verdict,
            reasons=all_reasons,
        )

    def should_reject(self, report: QualityReport) -> bool:
        """Check if an asset must trigger immediate regeneration."""
        return report.verdict == "REJECT"

    def should_quarantine_advisory(self, report: QualityReport) -> bool:
        """Check if an asset has quality concerns requiring advisory notice."""
        return report.verdict == "QUARANTINE_ADVISORY"
