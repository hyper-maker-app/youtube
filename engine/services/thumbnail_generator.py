"""Autonomous YouTube Thumbnail Generator for Grok Imagine Cinematic Studio.

Phase 4 (R4) — Thumbnail Automation Standard:
Produces YouTube-ready 1280×720 JPEG thumbnails composed of 4 strict PIL layers:
1. Layer 1: Base climax frame (1280×720, aspect-ratio preserved center-crop, or
   procedural catastrophe climax synthesis fallback).
2. Layer 2: Red-to-orange gradient overlay (#FF0000 -> #FF6B00, 40% opacity, left-to-right).
3. Layer 3: Bold White text (Impact or Montserrat Black bold, upper 1/3: y in [0, 240]).
4. Layer 4: Bottom strip (60% black opacity #000000 + small channel logo placeholder badge).

Callable via Python API or standalone CLI (`python -m engine.services.thumbnail_generator`).
"""

from __future__ import annotations

import argparse
import io
import logging
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Module constants
THUMBNAIL_WIDTH: int = 1280
THUMBNAIL_HEIGHT: int = 720
UPPER_THIRD_MAX_Y: int = 240  # 720 // 3

GRADIENT_START_HEX: str = "#FF0000"
GRADIENT_END_HEX: str = "#FF6B00"
GRADIENT_OPACITY: float = 0.40  # 40%

BOTTOM_STRIP_HEIGHT: int = 70
BOTTOM_STRIP_OPACITY: float = 0.60  # 60%

logger = logging.getLogger("thumbnail_generator")

__all__ = [
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
]


def hex_to_rgb(hex_code: str) -> tuple[int, int, int]:
    """Convert hex string (e.g. '#FF0000' or 'FF6B00') to RGB integer tuple."""
    clean = hex_code.lstrip("#")
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    if len(clean) != 6:
        raise ValueError(f"Invalid hex color: {hex_code}")
    return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)


def resolve_bold_font(
    font_preference: Optional[str] = None,
    size: int = 70,
) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    """Resolve Impact, Montserrat Black, or bold TrueType font with resilient fallbacks."""
    candidate_names: list[str] = []
    if font_preference:
        candidate_names.append(font_preference)

    candidate_names.extend([
        # Montserrat Black variants
        "Montserrat-Black.ttf",
        "Montserrat-Black",
        "MontserratBlack.ttf",
        "Montserrat-ExtraBold.ttf",
        "Montserrat-Bold.ttf",
        # Impact variants (high-CTR YouTube standard)
        "impact.ttf",
        "Impact.ttf",
        "Impact",
        # Cross-platform bold fallbacks
        "arialbd.ttf",
        "Arial Bold.ttf",
        "segoeuib.ttf",
        "DejaVuSans-Bold.ttf",
        "LiberationSans-Bold.ttf",
        "HelveticaNeue-Bold.ttf",
    ])

    search_dirs: list[Path] = [
        Path(r"C:\Windows\Fonts"),
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path("~/.fonts").expanduser(),
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts"),
        Path(__file__).resolve().parent.parent / "assets",
        Path("."),
    ]

    # 1. Search candidate paths and directories
    for name in candidate_names:
        direct = Path(name)
        if direct.is_file():
            try:
                return ImageFont.truetype(str(direct), size=size)
            except Exception:
                pass
        for sdir in search_dirs:
            if not sdir.is_dir():
                continue
            target = sdir / name
            if target.is_file():
                try:
                    return ImageFont.truetype(str(target), size=size)
                except Exception:
                    pass
            # Glob search for case-insensitive match
            try:
                matches = list(sdir.glob(f"**/{name}"))
                for m in matches:
                    if m.is_file():
                        try:
                            return ImageFont.truetype(str(m), size=size)
                        except Exception:
                            pass
            except Exception:
                pass

    # 2. Try loading font directly by family name in FreeType
    for name in candidate_names:
        try:
            return ImageFont.truetype(name, size=size)
        except Exception:
            pass

    # 3. Pillow default font fallback (with size if supported)
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def create_procedural_climax_frame(
    width: int = THUMBNAIL_WIDTH,
    height: int = THUMBNAIL_HEIGHT,
) -> Image.Image:
    """Synthesize a dramatic 1280x720 catastrophe climax base frame with volcanic/cosmic tones."""
    base = Image.new("RGBA", (width, height), (15, 10, 12, 255))
    draw = ImageDraw.Draw(base)

    # 1. Vertical atmospheric background gradient: dark obsidian to deep molten ash
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(14 + 28 * t)
        g = int(8 + 14 * t)
        b = int(10 + 6 * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # 2. Dramatic fiery magma glow & radial blast in lower-center
    glow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    center_x = width // 2
    center_y = int(height * 0.65)
    max_radius = int(width * 0.48)

    # Layered concentric atmospheric glow
    steps = 18
    for step in range(steps, 0, -1):
        radius_x = int(max_radius * (step / steps))
        radius_y = int(max_radius * 0.55 * (step / steps))
        factor = 1.0 - (step / steps)
        # Volcanic fiery core (#FF3B00 to #FF9000)
        gr = int(220 + 35 * factor)
        gg = int(30 + 130 * factor)
        gb = int(5 + 15 * factor)
        alpha = int(45 * factor)
        glow_draw.ellipse(
            [
                (center_x - radius_x, center_y - radius_y),
                (center_x + radius_x, center_y + radius_y),
            ],
            fill=(gr, gg, gb, alpha),
        )

    # 3. Silhouette fissure / catastrophe horizon
    fissure_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(fissure_layer)
    horizon_y = int(height * 0.72)
    poly = [(0, height)]
    for seg in range(0, width + 40, 40):
        wave = int(18 * math.sin(seg * 0.02) + 12 * math.cos(seg * 0.05))
        poly.append((seg, horizon_y + wave))
    poly.append((width, height))
    fdraw.polygon(poly, fill=(8, 5, 6, 230))

    # Composite layers
    base = Image.alpha_composite(base, glow_layer)
    base = Image.alpha_composite(base, fissure_layer)
    return base


def extract_climax_frame(
    video_path: Union[str, Path],
    position_ratio: float = 0.72,
) -> Optional[Image.Image]:
    """Extract a single frame from video file at given position ratio (default ~72% for climax)."""
    vpath = Path(video_path)
    if not vpath.is_file():
        return None

    # Method A: OpenCV VideoCapture
    try:
        import cv2

        cap = cv2.VideoCapture(str(vpath))
        if cap.isOpened():
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames > 0:
                target_frame = max(0, min(total_frames - 1, int(total_frames * position_ratio)))
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None and frame.size > 0:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    return Image.fromarray(rgb).convert("RGBA")
            cap.release()
    except Exception as exc:
        logger.debug(f"OpenCV video frame extraction notice: {exc}")

    # Method B: FFmpeg CLI pipe fallback
    try:
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-ss", "2.0",
            "-i", str(vpath),
            "-vframes", "1",
            "-f", "image2pipe",
            "-vcodec", "png", "-",
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if res.stdout:
            return Image.open(io.BytesIO(res.stdout)).convert("RGBA")
    except Exception as exc:
        logger.debug(f"FFmpeg CLI video frame extraction notice: {exc}")

    return None


def load_or_create_base_frame(
    base_image: Union[str, Path, Image.Image, Any, None],
    width: int = THUMBNAIL_WIDTH,
    height: int = THUMBNAIL_HEIGHT,
) -> Image.Image:
    """Layer 1: Load, aspect-crop, and normalize base climax frame to exact (1280, 720)."""
    raw_img: Optional[Image.Image] = None

    if isinstance(base_image, Image.Image):
        raw_img = base_image.convert("RGBA")
    elif base_image is not None:
        bpath = Path(base_image)
        if bpath.is_file():
            ext = bpath.suffix.lower()
            if ext in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
                raw_img = extract_climax_frame(bpath)
            else:
                try:
                    raw_img = Image.open(bpath).convert("RGBA")
                except Exception as exc:
                    logger.warning(f"Could not open base image file '{bpath}': {exc}")
        elif hasattr(base_image, "shape"):  # NumPy ndarray
            try:
                import cv2
                import numpy as np

                arr = np.asarray(base_image)
                if len(arr.shape) == 3 and arr.shape[2] == 3:
                    # Check if BGR vs RGB (default assume RGB or convert)
                    raw_img = Image.fromarray(arr).convert("RGBA")
            except Exception as exc:
                logger.warning(f"Could not convert array to image: {exc}")

    # If no valid base image was loaded, synthesize a dramatic procedural climax frame
    if raw_img is None:
        return create_procedural_climax_frame(width=width, height=height)

    # Check for empty / flat black dummy frames (e.g. from dry-run lavfi color blocks)
    # If the frame has zero variation, blend it with the procedural backdrop
    try:
        extrema = raw_img.getextrema()
        is_flat_black = all(ex[1] < 5 for ex in extrema[:3])
        if is_flat_black:
            procedural = create_procedural_climax_frame(width=width, height=height)
            return procedural
    except Exception:
        pass

    # Aspect-ratio preserving cover-fit and center-crop to exact (width, height)
    orig_w, orig_h = raw_img.size
    if orig_w == width and orig_h == height:
        return raw_img

    scale = max(width / orig_w, height / orig_h)
    new_w = int(round(orig_w * scale))
    new_h = int(round(orig_h * scale))

    resized = raw_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    cropped = resized.crop((left, top, left + width, top + height))
    return cropped


def create_gradient_overlay(
    width: int = THUMBNAIL_WIDTH,
    height: int = THUMBNAIL_HEIGHT,
    start_hex: str = GRADIENT_START_HEX,
    end_hex: str = GRADIENT_END_HEX,
    opacity: float = GRADIENT_OPACITY,
) -> Image.Image:
    """Layer 2: Red-to-orange gradient overlay (#FF0000 -> #FF6B00, 40% opacity, left-to-right)."""
    start_rgb = hex_to_rgb(start_hex)
    end_rgb = hex_to_rgb(end_hex)
    alpha = max(0, min(255, int(round(255 * opacity))))

    # Construct 1-pixel high horizontal gradient row
    row = Image.new("RGBA", (width, 1))
    r0, g0, b0 = start_rgb
    r1, g1, b1 = end_rgb

    for x in range(width):
        t = x / max(1, width - 1)
        r = int(round(r0 + (r1 - r0) * t))
        g = int(round(g0 + (g1 - g0) * t))
        b = int(round(b0 + (b1 - b0) * t))
        row.putpixel((x, 0), (r, g, b, alpha))

    # Stretch vertically to full height
    gradient = row.resize((width, height), Image.Resampling.NEAREST)
    return gradient


def draw_title_layer(
    base: Image.Image,
    title_text: str,
    font_name: Optional[str] = None,
    uppercase: bool = True,
    max_height: int = UPPER_THIRD_MAX_Y,
    align: str = "center",
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Layer 3: Render bold White text (Impact/Montserrat Black) strictly within the upper 1/3 (y in [0, 240]).

    Returns:
        tuple[Image.Image, tuple[int, int, int, int]]: Composited image and actual text bounding box.
    """
    clean_text = title_text.strip()
    if uppercase:
        clean_text = clean_text.upper()

    tlayer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(tlayer)

    width, height = base.size
    max_content_width = width - 140  # 70px margin on each side
    safe_max_y = min(max_height, int(height / 3))

    # Iterative font sizing to ensure text cleanly fits in the upper 1/3
    chosen_size = 74
    chosen_lines: list[str] = []
    chosen_font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont] = resolve_bold_font(font_name, size=chosen_size)

    words = clean_text.split()
    for size_cand in range(74, 38, -4):
        test_font = resolve_bold_font(font_name, size=size_cand)
        # Wrap words into lines
        lines: list[str] = []
        cur: list[str] = []
        for w in words:
            candidate_line = " ".join(cur + [w])
            bbox = tdraw.textbbox((0, 0), candidate_line, font=test_font, stroke_width=3)
            if (bbox[2] - bbox[0]) <= max_content_width or not cur:
                cur.append(w)
            else:
                lines.append(" ".join(cur))
                cur = [w]
        if cur:
            lines.append(" ".join(cur))

        # Check total height with line spacing
        line_heights = []
        for l in lines:
            bb = tdraw.textbbox((0, 0), l, font=test_font, stroke_width=3)
            line_heights.append(bb[3] - bb[1])
        spacing = int(size_cand * 0.16)
        total_h = sum(line_heights) + max(0, len(lines) - 1) * spacing

        if total_h <= (safe_max_y - 45) and len(lines) <= 3:
            chosen_size = size_cand
            chosen_lines = lines
            chosen_font = test_font
            break
        chosen_lines = lines
        chosen_font = test_font

    # Calculate vertical position strictly inside upper 1/3
    line_bboxes = [tdraw.textbbox((0, 0), l, font=chosen_font, stroke_width=3) for l in chosen_lines]
    line_heights = [bb[3] - bb[1] for bb in line_bboxes]
    spacing = int(chosen_size * 0.16)
    total_text_h = sum(line_heights) + max(0, len(chosen_lines) - 1) * spacing

    # Vertical start: centered within [20, safe_max_y - 15]
    y_start = max(20, (safe_max_y - total_text_h) // 2)
    # Enforce upper third hard constraint
    if y_start + total_text_h > safe_max_y - 8:
        y_start = max(10, safe_max_y - total_text_h - 10)

    stroke_w = max(3, int(chosen_size * 0.055))
    curr_y = y_start
    overall_x0, overall_y0, overall_x1, overall_y1 = width, height, 0, 0

    for i, line in enumerate(chosen_lines):
        bb = tdraw.textbbox((0, 0), line, font=chosen_font, stroke_width=stroke_w)
        line_w = bb[2] - bb[0]
        if align == "center":
            x = (width - line_w) // 2
        else:
            x = 70

        # Draw subtle drop shadow for maximum depth & readability
        shadow_offset = (3, 4)
        tdraw.text(
            (x + shadow_offset[0], curr_y + shadow_offset[1]),
            line,
            font=chosen_font,
            fill=(0, 0, 0, 160),
            stroke_width=stroke_w,
            stroke_fill=(0, 0, 0, 160),
        )

        # Draw main White bold text (#FFFFFF) with black stroke
        tdraw.text(
            (x, curr_y),
            line,
            font=chosen_font,
            fill=(255, 255, 255, 255),
            stroke_width=stroke_w,
            stroke_fill=(0, 0, 0, 255),
        )

        line_box = (x, curr_y, x + line_w, curr_y + line_heights[i])
        overall_x0 = min(overall_x0, line_box[0])
        overall_y0 = min(overall_y0, line_box[1])
        overall_x1 = max(overall_x1, line_box[2])
        overall_y1 = max(overall_y1, line_box[3])

        curr_y += line_heights[i] + spacing

    composited = Image.alpha_composite(base, tlayer)
    return composited, (overall_x0, overall_y0, overall_x1, overall_y1)


def draw_bottom_strip_layer(
    base: Image.Image,
    strip_height: int = BOTTOM_STRIP_HEIGHT,
    opacity: float = BOTTOM_STRIP_OPACITY,
    channel_name: str = "GROK STUDIO",
    channel_logo: Union[str, Path, Image.Image, None] = None,
) -> Image.Image:
    """Layer 4: Bottom strip (60% black opacity + small channel logo placeholder badge)."""
    width, height = base.size
    alpha = max(0, min(255, int(round(255 * opacity))))

    strip_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(strip_layer)

    # 1. 60% Black Opacity Bottom Bar (#000000 with alpha=153)
    bar_top = height - strip_height
    sdraw.rectangle([(0, bar_top), (width, height)], fill=(0, 0, 0, alpha))

    # 2. Subtle accent separator line at top of strip
    sdraw.line([(0, bar_top), (width, bar_top)], fill=(255, 255, 255, 35), width=1)

    # 3. Channel Logo Placeholder Badge
    badge_x0 = 40
    badge_y0 = bar_top + 10
    badge_h = strip_height - 20
    badge_w = 210

    # Badge pill background
    sdraw.rounded_rectangle(
        [(badge_x0, badge_y0), (badge_x0 + badge_w, badge_y0 + badge_h)],
        radius=6,
        fill=(20, 20, 20, 220),
        outline=(255, 255, 255, 120),
        width=1,
    )

    logo_placed = False
    if channel_logo is not None:
        try:
            if isinstance(channel_logo, Image.Image):
                limg = channel_logo.convert("RGBA")
            else:
                lpath = Path(channel_logo)
                if lpath.is_file():
                    limg = Image.open(lpath).convert("RGBA")
                else:
                    limg = None

            if limg is not None:
                max_lh = badge_h - 10
                scale = max_lh / limg.size[1]
                target_lw = int(round(limg.size[0] * scale))
                resized_logo = limg.resize((target_lw, max_lh), Image.Resampling.LANCZOS)
                strip_layer.paste(
                    resized_logo,
                    (badge_x0 + 8, badge_y0 + (badge_h - max_lh) // 2),
                    resized_logo,
                )
                logo_placed = True
        except Exception as exc:
            logger.debug(f"Custom channel logo composite notice: {exc}")

    if not logo_placed:
        # High-aesthetic default channel logo badge: Red square + white play glyph
        icon_box_size = badge_h - 12
        icon_x = badge_x0 + 8
        icon_y = badge_y0 + 6
        sdraw.rounded_rectangle(
            [(icon_x, icon_y), (icon_x + icon_box_size, icon_y + icon_box_size)],
            radius=4,
            fill=(225, 30, 30, 255),
        )
        # White play triangle glyph
        tri_p1 = (icon_x + int(icon_box_size * 0.35), icon_y + int(icon_box_size * 0.25))
        tri_p2 = (icon_x + int(icon_box_size * 0.35), icon_y + int(icon_box_size * 0.75))
        tri_p3 = (icon_x + int(icon_box_size * 0.75), icon_y + int(icon_box_size * 0.50))
        sdraw.polygon([tri_p1, tri_p2, tri_p3], fill=(255, 255, 255, 255))

        # Channel name text
        cfont = resolve_bold_font(size=18)
        text_x = icon_x + icon_box_size + 10
        text_y = badge_y0 + (badge_h - 18) // 2
        sdraw.text((text_x, text_y), channel_name, font=cfont, fill=(255, 255, 255, 255))

    # 4. Right-side YouTube telemetry badge (e.g. "4K UHD • 60 FPS")
    tag_font = resolve_bold_font(size=14)
    tag_text = "4K UHD • 60 FPS"
    tag_bb = sdraw.textbbox((0, 0), tag_text, font=tag_font)
    tag_w = tag_bb[2] - tag_bb[0]
    tag_x = width - tag_w - 45
    tag_y = bar_top + (strip_height - 14) // 2
    sdraw.text((tag_x, tag_y), tag_text, font=tag_font, fill=(210, 210, 210, 200))

    composited = Image.alpha_composite(base, strip_layer)
    return composited


def generate_thumbnail(
    base_image: Union[str, Path, Image.Image, Any, None] = None,
    title_text: str = "WHAT IF 1000 VOLCANOES ERUPTED AT ONCE?",
    output_path: Union[str, Path, None] = None,
    channel_name: str = "GROK STUDIO",
    channel_logo: Union[str, Path, Image.Image, None] = None,
    font_name: Optional[str] = None,
    gradient_start: str = GRADIENT_START_HEX,
    gradient_end: str = GRADIENT_END_HEX,
    gradient_opacity: float = GRADIENT_OPACITY,
    bottom_strip_opacity: float = BOTTOM_STRIP_OPACITY,
    uppercase: bool = True,
    width: int = THUMBNAIL_WIDTH,
    height: int = THUMBNAIL_HEIGHT,
) -> Path:
    """Generate a YouTube-ready 1280×720 JPEG thumbnail composed of 4 strict PIL layers.

    Args:
        base_image: Video climax frame path, PIL Image, numpy array, or None for procedural synthesis.
        title_text: Video title text to render in bold White font in the upper 1/3.
        output_path: Destination path for the JPEG thumbnail. Defaults to 'out/thumbnail.jpg'.
        channel_name: Channel name rendered in the bottom strip placeholder.
        channel_logo: Optional path or PIL Image for channel logo.
        font_name: Preferred font family or file path (e.g. 'Impact' or 'Montserrat-Black').
        gradient_start: Hex color for gradient start (#FF0000).
        gradient_end: Hex color for gradient end (#FF6B00).
        gradient_opacity: Opacity for Layer 2 gradient (0.40).
        bottom_strip_opacity: Opacity for Layer 4 bottom bar (0.60).
        uppercase: If True, renders title text in uppercase for high CTR.
        width: Canvas width in pixels (1280).
        height: Canvas height in pixels (720).

    Returns:
        Path: Resolved absolute path to the generated 1280×720 JPEG file.
    """
    if output_path is None:
        output_path = Path("out") / "thumbnail.jpg"
    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Layer 1: Base climax frame (1280x720)
    # -------------------------------------------------------------------------
    layer1 = load_or_create_base_frame(base_image=base_image, width=width, height=height)

    # -------------------------------------------------------------------------
    # Layer 2: Red-to-orange gradient overlay (#FF0000 -> #FF6B00, 40% opacity, L-to-R)
    # -------------------------------------------------------------------------
    layer2 = create_gradient_overlay(
        width=width,
        height=height,
        start_hex=gradient_start,
        end_hex=gradient_end,
        opacity=gradient_opacity,
    )
    layer1_and_2 = Image.alpha_composite(layer1, layer2)

    # -------------------------------------------------------------------------
    # Layer 3: White Impact or Montserrat Black bold text (upper 1/3: y in [0, 240])
    # -------------------------------------------------------------------------
    layer1_to_3, text_bbox = draw_title_layer(
        base=layer1_and_2,
        title_text=title_text,
        font_name=font_name,
        uppercase=uppercase,
        max_height=UPPER_THIRD_MAX_Y,
    )

    # -------------------------------------------------------------------------
    # Layer 4: Bottom strip (60% black opacity + small channel logo placeholder)
    # -------------------------------------------------------------------------
    final_rgba = draw_bottom_strip_layer(
        base=layer1_to_3,
        strip_height=BOTTOM_STRIP_HEIGHT,
        opacity=bottom_strip_opacity,
        channel_name=channel_name,
        channel_logo=channel_logo,
    )

    # Convert to RGB and write YouTube-ready JPEG
    final_rgb = final_rgba.convert("RGB")
    final_rgb.save(out_file, format="JPEG", quality=95, optimize=True)

    logger.info(
        f"Thumbnail generated -> {out_file} "
        f"({final_rgb.width}x{final_rgb.height}, text bbox y: [{text_bbox[1]}, {text_bbox[3]}])"
    )
    return out_file


def generate_test_thumbnail(output_path: Union[str, Path] = "out/thumbnail_test.jpg") -> Path:
    """Generate a test thumbnail for verification purposes."""
    return generate_thumbnail(
        base_image=None,
        title_text="WHAT IF 1000 VOLCANOES ERUPTED AT ONCE?",
        output_path=output_path,
    )


def _cli_entrypoint() -> None:
    """CLI execution handler for standalone thumbnail generation."""
    parser = argparse.ArgumentParser(
        description="YouTube-Ready 1280x720 Thumbnail Generator (Phase 4 / R4)",
    )
    parser.add_argument(
        "--base", "-b",
        help="Path to base image or video climax block",
        default=None,
    )
    parser.add_argument(
        "--title", "-t",
        help="Thumbnail title text (upper 1/3)",
        default="WHAT IF 1000 VOLCANOES ERUPTED AT ONCE?",
    )
    parser.add_argument(
        "--output", "-o",
        help="Destination path for generated JPEG thumbnail",
        default="out/thumbnail_test.jpg",
    )
    parser.add_argument(
        "--channel", "-c",
        help="Channel name for logo placeholder badge",
        default="GROK STUDIO",
    )
    parser.add_argument(
        "--logo", "-l",
        help="Optional channel logo image path",
        default=None,
    )

    args = parser.parse_args()

    out_path = generate_thumbnail(
        base_image=args.base,
        title_text=args.title,
        output_path=args.output,
        channel_name=args.channel,
        channel_logo=args.logo,
    )
    print(f"[THUMBNAIL] Generated 1280x720 YouTube thumbnail at: {out_path}")


if __name__ == "__main__":
    _cli_entrypoint()
