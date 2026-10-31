"""Unit tests for Phase 4 (R4) — YouTube Thumbnail Automation.

Verifies:
1. thumbnail_generator.py module imports, exports, and constants:
   - 1280x720 YouTube-ready resolution
   - #FF0000 -> #FF6B00 gradient constants (40% opacity)
   - Upper 1/3 boundary (y <= 240)
   - 60% black opacity bottom strip
2. Layer 1: Base climax frame:
   - Accepts PIL Image, file path, video block, or None.
   - Preserves aspect ratio with cover center-crop to 1280x720.
   - Procedural catastrophe climax frame synthesis when base is None.
3. Layer 2: Red-to-orange gradient overlay:
   - Left-to-right horizontal interpolation (#FF0000 to #FF6B00).
   - Exact 40% alpha opacity (alpha = 102 / 255).
4. Layer 3: Bold White text:
   - Impact or Montserrat Black font resolution with robust fallbacks.
   - Text bounding box strictly confined within upper 1/3 (y <= 240).
   - Multi-line word wrapping and auto-font sizing for short and long titles.
5. Layer 4: Bottom strip:
   - 60% black opacity strip at bottom of canvas (y from 650 to 720).
   - Channel logo placeholder with icon badge and channel text.
   - Custom channel logo placement.
6. Standalone execution:
   - 'python -m engine.services.thumbnail_generator' runs standalone and produces test JPEG.
   - generate_test_thumbnail() helper.
7. CLI & Flow Bridge Pipeline Integration:
   - produce-film produces out/<project>/thumbnail.jpg.
   - Dry-run console panel references thumbnail path out/<project>/thumbnail.jpg.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw

from engine.services.thumbnail_generator import (
    BOTTOM_STRIP_HEIGHT,
    BOTTOM_STRIP_OPACITY,
    GRADIENT_END_HEX,
    GRADIENT_OPACITY,
    GRADIENT_START_HEX,
    THUMBNAIL_HEIGHT,
    THUMBNAIL_WIDTH,
    UPPER_THIRD_MAX_Y,
    __all__ as thumb_all,
    create_gradient_overlay,
    create_procedural_climax_frame,
    draw_bottom_strip_layer,
    draw_title_layer,
    extract_climax_frame,
    generate_test_thumbnail,
    generate_thumbnail,
    hex_to_rgb,
    load_or_create_base_frame,
    resolve_bold_font,
)


def test_thumbnail_constants_and_exports():
    """Verify standard constants and module exports for Phase 4."""
    assert THUMBNAIL_WIDTH == 1280
    assert THUMBNAIL_HEIGHT == 720
    assert UPPER_THIRD_MAX_Y == 240
    assert GRADIENT_START_HEX == "#FF0000"
    assert GRADIENT_END_HEX == "#FF6B00"
    assert GRADIENT_OPACITY == 0.40
    assert BOTTOM_STRIP_OPACITY == 0.60
    assert BOTTOM_STRIP_HEIGHT == 70

    expected_exports = {
        "THUMBNAIL_WIDTH",
        "THUMBNAIL_HEIGHT",
        "UPPER_THIRD_MAX_Y",
        "GRADIENT_START_HEX",
        "GRADIENT_END_HEX",
        "GRADIENT_OPACITY",
        "BOTTOM_STRIP_HEIGHT",
        "BOTTOM_STRIP_OPACITY",
        "hex_to_rgb",
        "resolve_bold_font",
        "create_procedural_climax_frame",
        "load_or_create_base_frame",
        "create_gradient_overlay",
        "draw_title_layer",
        "draw_bottom_strip_layer",
        "extract_climax_frame",
        "generate_thumbnail",
        "generate_test_thumbnail",
    }
    for symbol in expected_exports:
        assert symbol in thumb_all, f"Expected symbol '{symbol}' in __all__"


def test_hex_to_rgb_conversion():
    """Verify hex color parsing matches exact RGB triples."""
    assert hex_to_rgb("#FF0000") == (255, 0, 0)
    assert hex_to_rgb("#FF6B00") == (255, 107, 0)
    assert hex_to_rgb("000000") == (0, 0, 0)
    assert hex_to_rgb("#FFF") == (255, 255, 255)

    with pytest.raises(ValueError):
        hex_to_rgb("invalid")


def test_layer1_procedural_base_frame():
    """Verify procedural climax base frame produces exact 1280x720 RGBA image."""
    base = create_procedural_climax_frame(1280, 720)
    assert isinstance(base, Image.Image)
    assert base.size == (1280, 720)
    assert base.mode == "RGBA"

    # Verify image is not blank/uniform
    extrema = base.getextrema()
    # At least one color channel has dynamic range
    assert any(ex[1] - ex[0] > 50 for ex in extrema[:3])


def test_layer1_base_frame_resizing_and_crop(tmp_path: Path):
    """Verify Layer 1 normalizes different aspect ratio inputs to exact 1280x720."""
    # 1. 1920x1080 source image (16:9)
    src_16_9 = Image.new("RGB", (1920, 1080), (100, 150, 200))
    p1 = tmp_path / "src_16_9.png"
    src_16_9.save(p1)

    layer1_a = load_or_create_base_frame(p1, 1280, 720)
    assert layer1_a.size == (1280, 720)
    assert layer1_a.mode == "RGBA"

    # 2. 1080x1920 source image (9:16 vertical video) -> center crop
    src_9_16 = Image.new("RGB", (1080, 1920), (50, 80, 120))
    layer1_b = load_or_create_base_frame(src_9_16, 1280, 720)
    assert layer1_b.size == (1280, 720)

    # 3. Square image 800x800 -> center crop
    src_sq = Image.new("RGB", (800, 800), (30, 40, 50))
    layer1_c = load_or_create_base_frame(src_sq, 1280, 720)
    assert layer1_c.size == (1280, 720)

    # 4. None input -> fallback procedural
    layer1_d = load_or_create_base_frame(None, 1280, 720)
    assert layer1_d.size == (1280, 720)


def test_layer2_gradient_overlay_mathematics():
    """Verify Layer 2 red-to-orange gradient overlay mathematics and opacity."""
    grad = create_gradient_overlay(
        width=1280,
        height=720,
        start_hex="#FF0000",
        end_hex="#FF6B00",
        opacity=0.40,
    )
    assert grad.size == (1280, 720)
    assert grad.mode == "RGBA"

    # Leftmost column (x=0) must be pure #FF0000 with 40% alpha (102)
    left_pixel = grad.getpixel((0, 360))
    assert left_pixel == (255, 0, 0, 102), f"Left pixel was {left_pixel}"

    # Rightmost column (x=1279) must be pure #FF6B00 with 40% alpha (102)
    right_pixel = grad.getpixel((1279, 360))
    assert right_pixel == (255, 107, 0, 102), f"Right pixel was {right_pixel}"

    # Midpoint column (x=640) must have interpolated green value between 0 and 107
    mid_pixel = grad.getpixel((640, 360))
    assert mid_pixel[0] == 255
    assert 45 <= mid_pixel[1] <= 60
    assert mid_pixel[2] == 0
    assert mid_pixel[3] == 102


def test_layer3_title_text_within_upper_third():
    """Verify Layer 3 renders bold text strictly confined inside the upper 1/3 (y <= 240)."""
    base = Image.new("RGBA", (1280, 720), (20, 20, 20, 255))

    # Test standard catastrophe title
    title1 = "What if 1000 Volcanoes Erupted at Once"
    img1, bbox1 = draw_title_layer(base, title1, uppercase=True, max_height=240)
    assert isinstance(img1, Image.Image)
    assert bbox1[1] >= 0, f"Text y0 out of upper bounds: {bbox1[1]}"
    assert bbox1[3] <= UPPER_THIRD_MAX_Y, f"Text y1 exceeds upper 1/3 (240px): {bbox1[3]}"

    # Test long multi-line catastrophe title
    title2 = "WHAT IF A 500-MEGATON ASTEROID HIT THE PACIFIC OCEAN AT 40,000 KM/H?"
    img2, bbox2 = draw_title_layer(base, title2, uppercase=True, max_height=240)
    assert bbox2[1] >= 0
    assert bbox2[3] <= UPPER_THIRD_MAX_Y, f"Long title y1 exceeds upper 1/3: {bbox2[3]}"


def test_layer3_font_resolution():
    """Verify font resolution resolves Impact or bold TrueType fallback."""
    font = resolve_bold_font(size=64)
    assert font is not None


def test_layer4_bottom_strip_opacity_and_logo():
    """Verify Layer 4 renders 60% black opacity bottom strip with logo placeholder."""
    base = Image.new("RGBA", (1280, 720), (100, 100, 100, 255))
    out = draw_bottom_strip_layer(base, strip_height=70, opacity=0.60, channel_name="GROK STUDIO")
    assert out.size == (1280, 720)

    # Coordinates y in [650, 720] are within bottom strip
    # Baseline was 100, 60% black strip has alpha 153/255.
    # Composited pixel: 100 * (1 - 0.60) = 40.
    sample_pixel = out.getpixel((700, 680))
    assert sample_pixel[0] == 40
    assert sample_pixel[1] == 40
    assert sample_pixel[2] == 40
    assert sample_pixel[3] == 255

    # Coordinates y < 650 must remain untouched background (100, 100, 100)
    top_pixel = out.getpixel((700, 500))
    assert top_pixel == (100, 100, 100, 255)


def test_layer4_custom_logo_composite(tmp_path: Path):
    """Verify custom channel logo image can be passed and composited into bottom strip."""
    logo_img = Image.new("RGBA", (64, 64), (255, 200, 0, 255))
    logo_path = tmp_path / "custom_logo.png"
    logo_img.save(logo_path)

    base = Image.new("RGBA", (1280, 720), (0, 0, 0, 255))
    out = draw_bottom_strip_layer(base, channel_logo=logo_path)
    assert out.size == (1280, 720)


def test_generate_thumbnail_end_to_end(tmp_path: Path):
    """Verify end-to-end generate_thumbnail produces a valid 1280x720 JPEG file."""
    out_file = tmp_path / "test_thumb.jpg"
    result_path = generate_thumbnail(
        base_image=None,
        title_text="WHAT IF 1000 VOLCANOES ERUPTED AT ONCE?",
        output_path=out_file,
    )

    assert result_path.is_file()
    assert result_path == out_file

    with Image.open(result_path) as img:
        assert img.format == "JPEG"
        assert img.size == (1280, 720)
        assert img.mode == "RGB"

    # Verify file is not empty
    assert result_path.stat().st_size > 20000


def test_generate_test_thumbnail_helper(tmp_path: Path):
    """Verify generate_test_thumbnail helper function."""
    out_file = tmp_path / "helper_test.jpg"
    res = generate_test_thumbnail(output_path=out_file)
    assert res.is_file()
    with Image.open(res) as img:
        assert img.size == (1280, 720)
        assert img.format == "JPEG"


def test_standalone_cli_execution(tmp_path: Path):
    """Verify python -m engine.services.thumbnail_generator runs cleanly as a standalone module."""
    out_file = tmp_path / "cli_thumb.jpg"
    cmd = [
        sys.executable,
        "-m",
        "engine.services.thumbnail_generator",
        "--title",
        "WHAT IF 1000 VOLCANOES ERUPTED AT ONCE?",
        "--output",
        str(out_file),
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert proc.returncode == 0, f"CLI standalone failed with error: {proc.stderr}"
    assert "[THUMBNAIL] Generated 1280x720 YouTube thumbnail" in proc.stdout
    assert out_file.is_file()

    with Image.open(out_file) as img:
        assert img.size == (1280, 720)
        assert img.format == "JPEG"


def test_extract_climax_frame_from_video(tmp_path: Path):
    """Verify extract_climax_frame extracts frame from mp4 video fixture."""
    import config

    ffmpeg = config.resolve_ffmpeg()
    test_video = tmp_path / "test_climax.mp4"
    # Create 4-second lavfi test video
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=red:s=1280x720:r=30",
        "-t", "4.0",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        str(test_video),
    ]
    subprocess.run(cmd, check=True)
    assert test_video.is_file()

    extracted = extract_climax_frame(test_video, position_ratio=0.72)
    assert extracted is not None
    assert isinstance(extracted, Image.Image)
    assert extracted.size == (1280, 720)


def test_produce_film_dry_run_thumbnail_integration(tmp_path: Path):
    """Verify produce-film dry-run execution produces and references out/<project>/thumbnail.jpg."""
    cmd = [
        sys.executable,
        "tools/cinematic_studio_cli.py",
        "produce-film",
        "What if 1000 Volcanoes Erupted at Once",
        "--genre", "catastrophe",
        "--duration", "300",
        "--dry-run",
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert proc.returncode == 0, f"produce-film dry-run failed: {proc.stderr}"

    # Dry-run output must explicitly reference out/<project>/thumbnail.jpg
    expected_rel_path = os.path.join("what-if-1000-volcanoes-erupted-at-once", "thumbnail.jpg").replace("\\", "/")
    combined_output = (proc.stdout + "\n" + proc.stderr).replace("\\", "/")
    assert expected_rel_path in combined_output, (
        f"Dry run output did NOT reference thumbnail path '{expected_rel_path}':\n{combined_output}"
    )
    assert "[THUMBNAIL]" in proc.stdout, f"Expected '[THUMBNAIL]' section in stdout panel:\n{proc.stdout}"

    # Check thumbnail.jpg file exists on disk
    project_thumbnail = Path("out") / "what-if-1000-volcanoes-erupted-at-once" / "thumbnail.jpg"
    assert project_thumbnail.is_file(), f"Expected thumbnail file at {project_thumbnail} does not exist"

    with Image.open(project_thumbnail) as img:
        assert img.format == "JPEG"
        assert img.size == (1280, 720)
        assert img.mode == "RGB"
