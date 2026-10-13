"""Unit tests for services/vision_quality_gate.py (Vision Quality Gate Engine)."""

from __future__ import annotations

import ast
from pathlib import Path

import cv2
import numpy as np
import pytest
from services.vision_quality_gate import QualityReport, VisionQualityGate


def test_sharp_frame_passes():
    gate = VisionQualityGate(sharpness_min=50.0, dynamic_range_min=0.25, strict_mode=False)
    # Generate high-contrast textured/checkerboard 16:9 frame (1920x1080)
    img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    # Add random high-frequency texture across the whole image
    np.random.seed(42)
    noise = np.random.randint(0, 256, (1080, 1920, 3), dtype=np.uint8)
    img = cv2.addWeighted(img, 0.2, noise, 0.8, 0)

    report = gate.analyze_frame(img, expected_format="16:9")
    assert report.sharpness_score > 50.0
    assert report.dynamic_range_score > 0.30
    assert report.geometry_valid is True
    assert report.aspect_ratio_correct is True
    assert report.letterbox_detected is False
    assert report.verdict == "PASS"
    assert report.is_passed is True


def test_blurry_frame_advisory():
    # Blurry / solid frame: Laplacian variance is close to 0
    gate = VisionQualityGate(sharpness_min=80.0, strict_mode=False)
    solid_gray = np.full((1080, 1920, 3), 128, dtype=np.uint8)

    report = gate.analyze_frame(solid_gray, expected_format="16:9")
    assert report.sharpness_score < 10.0
    assert report.verdict == "QUARANTINE_ADVISORY"
    assert any("sharpness" in r.lower() for r in report.reasons)
    assert gate.should_reject(report) is False
    assert gate.should_quarantine_advisory(report) is True


def test_strict_mode_rejects_on_defect():
    gate = VisionQualityGate(sharpness_min=80.0, strict_mode=True)
    solid_gray = np.full((1080, 1920, 3), 128, dtype=np.uint8)

    report = gate.analyze_frame(solid_gray, expected_format="16:9")
    assert report.verdict == "REJECT"
    assert gate.should_reject(report) is True


def test_letterbox_detection():
    gate = VisionQualityGate()
    # Create 1920x1080 frame with black horizontal bars top and bottom
    img = np.full((1080, 1920, 3), 200, dtype=np.uint8)
    img[:50, :] = 0  # top bar
    img[-50:, :] = 0  # bottom bar

    report = gate.analyze_frame(img, expected_format="16:9")
    assert report.letterbox_detected is True
    assert any("letterbox" in r.lower() for r in report.reasons)


def test_aspect_ratio_mismatch():
    gate = VisionQualityGate()
    # Pass 9:16 vertical frame (1080x1920) but declare expected format "16:9"
    img = np.full((1920, 1080, 3), 150, dtype=np.uint8)

    report = gate.analyze_frame(img, expected_format="16:9")
    assert report.aspect_ratio_correct is False
    assert any("aspect ratio" in r.lower() for r in report.reasons)


def test_shorts_9_16_geometry_validation():
    gate = VisionQualityGate()
    # High frequency textured 9:16 frame (1080x1920)
    np.random.seed(99)
    img = np.random.randint(0, 256, (1920, 1080, 3), dtype=np.uint8)

    report = gate.analyze_frame(img, expected_format="9:16")
    assert report.geometry_valid is True
    assert report.aspect_ratio_correct is True
    assert report.letterbox_detected is False


def test_empty_corrupted_frame():
    gate = VisionQualityGate()
    empty = np.array([])
    report = gate.analyze_frame(empty)
    assert report.geometry_valid is False
    assert report.verdict in ("QUARANTINE_ADVISORY", "REJECT")


def test_missing_image_file_handled_gracefully():
    gate = VisionQualityGate()
    report = gate.analyze_image("non_existent_image_12345.png")
    assert report.geometry_valid is False
    assert any("not found" in r.lower() for r in report.reasons)


def test_ast_cleanliness_no_network_imports():
    """Verify services/vision_quality_gate.py contains zero network or provider imports."""
    source_path = Path(__file__).resolve().parent.parent / "services" / "vision_quality_gate.py"
    tree = ast.parse(source_path.read_text("utf-8"), filename=str(source_path))

    forbidden_modules = {"httpx", "requests", "urllib", "aiohttp", "websockets", "google"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                assert mod not in forbidden_modules, f"Forbidden import: {mod}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module.split(".")[0]
                assert mod not in forbidden_modules, f"Forbidden from-import: {mod}"
