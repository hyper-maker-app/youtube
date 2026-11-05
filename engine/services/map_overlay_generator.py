"""Procedural Deterministic B-Roll & Tactical HUD Overlay Generator.

Provides dynamic, zero-cost, broadcast-standard graphical B-roll videos
using Pillow (PIL) and FFmpeg:
1. Tactical Map Video:
   Dark tactical map grid with coordinate axes, dynamic continental landmasses,
   tectonic boundaries, and pulsing nodes driven strictly by data_payload.
2. Data Curve Video:
   Strategic telemetry curve screen tracking dynamic values over time,
   parameterized entirely via data_payload.
3. Shockwave Grid Video:
   Isobar anomaly grid with expanding concentric rings and metric readouts,
   parameterized entirely via data_payload.
4. Unified Dispatcher (`generate_data_broll`):
   General entry point for automated sequence assembly.

PURE ENGINE INVARIANT:
Engines do not hardcode creative narrative text, coordinates, or disaster lore.
All telemetry text, metrics, coordinates, and labels are driven dynamically
by data_payload.
"""

from __future__ import annotations

import logging
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generator, List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_ENGINE_DIR = Path(__file__).resolve().parents[1]
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

try:
    from engine import config
except ImportError:
    import config

logger = logging.getLogger(__name__)

__all__ = [
    "generate_volcano_map_video",
    "generate_temperature_curve_video",
    "generate_pressure_grid_video",
    "generate_data_broll",
    "test_map_overlay_generator",
]

# ---------------------------------------------------------------------------
# Font Management & Typography Helper
# ---------------------------------------------------------------------------

_FONT_CACHE: dict[tuple[int, bool], Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]] = {}


def resolve_hud_font(
    size: int = 20,
    bold: bool = False,
) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    """Resolve a high-legibility monospace or tactical HUD font with cross-platform fallbacks."""
    cache_key = (size, bold)
    if cache_key in _FONT_CACHE:
        return _FONT_CACHE[cache_key]

    candidate_names: list[str] = []
    if bold:
        candidate_names.extend([
            "consolab.ttf",
            "consola.ttf",
            "arialbd.ttf",
            "segoeuib.ttf",
            "DejaVuSansMono-Bold.ttf",
            "LiberationMono-Bold.ttf",
            "Courier New Bold.ttf",
            "courbd.ttf",
        ])
    else:
        candidate_names.extend([
            "consola.ttf",
            "arial.ttf",
            "segoeui.ttf",
            "DejaVuSansMono.ttf",
            "LiberationMono-Regular.ttf",
            "Courier New.ttf",
            "cour.ttf",
        ])

    search_dirs: list[Path] = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
        Path(r"C:\Windows\Fonts"),
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path("~/.fonts").expanduser(),
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts"),
        _ENGINE_DIR.parent / "assets",
        Path("."),
    ]

    for name in candidate_names:
        for sdir in search_dirs:
            if not sdir.is_dir():
                continue
            target = sdir / name
            if target.is_file():
                try:
                    font = ImageFont.truetype(str(target), size=size)
                    _FONT_CACHE[cache_key] = font
                    return font
                except Exception:
                    pass

    default_font = ImageFont.load_default()
    _FONT_CACHE[cache_key] = default_font
    return default_font


# ---------------------------------------------------------------------------
# Projection Helper & Generic Geometric Structures (Zero-hardcode defaults)
# ---------------------------------------------------------------------------

def _ll2xy(lon: float, lat: float, width: int, height: int) -> Tuple[int, int]:
    """Project longitude (-180..180) and latitude (-90..90) to canvas pixel coordinates."""
    x = (lon + 180.0) / 360.0 * width
    y = (90.0 - lat) / 180.0 * height
    return int(round(x)), int(round(y))


CONTINENTAL_OUTLINES: dict[str, list[tuple[float, float]]] = {}
TECTONIC_BOUNDARIES: list[list[tuple[float, float]]] = []
MAJOR_CALDERAS: list[tuple[float, float, str]] = []


@dataclass
class VolcanoNode:
    """Generic telemetry map node."""
    lon: float
    lat: float
    radius: float
    freq: float
    phase: float
    core_rgb: tuple[int, int, int]
    halo_rgb: tuple[int, int, int]


_GLOBAL_VOLCANO_NODES: list[VolcanoNode] = []


# ---------------------------------------------------------------------------
# FFmpeg Video Encoding Pipeline
# ---------------------------------------------------------------------------

def _encode_frames_to_mp4(
    frame_generator: Generator[Image.Image, None, None],
    output_path: str | Path,
    duration: float,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    ffmpeg: str | None = None,
) -> Path:
    """Encode an in-memory sequence of PIL Image frames directly into H.264 MP4."""
    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_bin = ffmpeg or getattr(config, "FFMPEG_BIN", None) or shutil.which("ffmpeg") or "ffmpeg"

    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{width}x{height}",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "-",
        "-an",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-t", f"{duration:.3f}",
        str(out),
    ]

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        assert proc.stdin is not None
        for frame in frame_generator:
            if frame.size != (width, height):
                frame = frame.resize((width, height), Image.Resampling.LANCZOS)
            if frame.mode != "RGB":
                frame = frame.convert("RGB")
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        stdout, stderr = proc.communicate(timeout=60.0)
    except Exception as exc:
        proc.kill()
        logger.error(f"[MAP OVERLAY] Direct pipe encode failed: {exc}. Trying fallback sequence.")
        return _fallback_encode_sequence(frame_generator, out, fps, ffmpeg_bin)

    if proc.returncode != 0 or not out.is_file() or out.stat().st_size < 1000:
        err_msg = stderr.decode("utf-8", errors="replace") if stderr else "Unknown error"
        raise RuntimeError(f"FFmpeg render failed (exit code {proc.returncode}): {err_msg}")

    return out


def _fallback_encode_sequence(
    frame_generator: Generator[Image.Image, None, None],
    output_path: Path,
    fps: int,
    ffmpeg_bin: str,
) -> Path:
    """Fallback renderer writing temporary PNG frames when stdin pipe is blocked."""
    temp_dir = Path(tempfile.mkdtemp(prefix="broll_frames_"))
    try:
        frame_idx = 0
        for frame in frame_generator:
            frame.save(temp_dir / f"f_{frame_idx:06d}.png")
            frame_idx += 1

        cmd = [
            ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
            "-r", str(fps),
            "-i", str(temp_dir / "f_%06d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Generator 1: Tactical Map Video
# ---------------------------------------------------------------------------

def generate_volcano_map_video(
    output_path: str | Path,
    duration: float = 5.0,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    ffmpeg: str | None = None,
    data_payload: dict[str, Any] | None = None,
) -> Path:
    """Generate dynamic tactical map video driven strictly by data_payload."""
    total_frames = max(1, int(round(duration * fps)))
    font_hud_title = resolve_hud_font(size=max(14, int(height * 0.030)), bold=True)
    font_hud_body = resolve_hud_font(size=max(11, int(height * 0.018)), bold=False)
    font_hud_mono = resolve_hud_font(size=max(10, int(height * 0.015)), bold=True)

    payload = data_payload or {}
    hud_alert = str(payload.get("alert_badge") or "")
    hud_metric_1 = str(payload.get("metric_1") or "")
    hud_metric_2 = str(payload.get("metric_2") or "")
    hud_metric_3 = str(payload.get("metric_3") or "")
    hud_sub_status = str(payload.get("sub_status") or "")
    hud_telemetry_1 = str(payload.get("telemetry_1") or "")
    hud_telemetry_2 = str(payload.get("telemetry_2") or "")
    hud_satellite = str(payload.get("satellite_name") or "")
    hud_footer = str(payload.get("footer_text") or "")

    outlines = payload.get("continental_outlines") or payload.get("outlines") or {}
    faults = payload.get("tectonic_boundaries") or payload.get("boundaries") or []
    calderas = payload.get("calderas") or payload.get("epicenters") or []
    node_data = payload.get("nodes") or payload.get("data_points") or []

    projected_continents: list[list[tuple[int, int]]] = [
        [_ll2xy(float(lon), float(lat), width, height) for lon, lat in coords]
        for coords in outlines.values()
    ]

    projected_faults: list[list[tuple[int, int]]] = [
        [_ll2xy(float(lon), float(lat), width, height) for lon, lat in line]
        for line in faults
    ]

    projected_calderas: list[tuple[int, int, str]] = [
        (*_ll2xy(float(lon), float(lat), width, height), str(name))
        for lon, lat, name in calderas
    ]

    projected_nodes: list[tuple[int, int, float, float, float, tuple[int, int, int], tuple[int, int, int]]] = []
    for n in node_data:
        if isinstance(n, (list, tuple)) and len(n) >= 2:
            nx, ny = _ll2xy(float(n[0]), float(n[1]), width, height)
            rad = float(n[2]) if len(n) > 2 else 2.5
            projected_nodes.append((nx, ny, rad * (height / 1080.0), 1.5, 0.0, (255, 120, 0), (255, 60, 0)))

    def _frame_generator() -> Generator[Image.Image, None, None]:
        for frame_idx in range(total_frames):
            t = frame_idx / fps

            base = Image.new("RGB", (width, height), (7, 10, 15))
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw_base = ImageDraw.Draw(base)
            draw_ov = ImageDraw.Draw(overlay)

            # Coordinate Grid (Latitude & Longitude)
            for lon in range(-180, 181, 30):
                gx, _ = _ll2xy(lon, 0, width, height)
                draw_base.line([(gx, 0), (gx, height)], fill=(18, 25, 36), width=1)
            for lat in range(-60, 91, 30):
                _, gy = _ll2xy(0, lat, width, height)
                draw_base.line([(0, gy), (width, gy)], fill=(18, 25, 36), width=1)

            for poly in projected_continents:
                draw_base.polygon(poly, fill=(14, 20, 29), outline=(32, 45, 62))

            for fault in projected_faults:
                if len(fault) > 1:
                    draw_base.line(fault, fill=(45, 65, 88), width=2)

            for cx, cy, cname in projected_calderas:
                phase_t = (t + (cx % 100) * 0.01) % 1.6
                wave_r = int(phase_t * (height * 0.12))
                wave_alpha = int(max(0, 140 * (1.0 - phase_t / 1.6)))
                if wave_r > 3 and wave_alpha > 5:
                    draw_ov.ellipse(
                        [(cx - wave_r, cy - wave_r), (cx + wave_r, cy + wave_r)],
                        outline=(255, 70, 0, wave_alpha),
                        width=2,
                    )

            for x, y, r, freq, phase, core_rgb, halo_rgb in projected_nodes:
                pulse = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(math.tau * freq * t + phase))
                halo_r = r * 2.8 * pulse
                core_r = max(1.0, r * 0.9 * pulse)

                draw_ov.ellipse(
                    [(x - halo_r, y - halo_r), (x + halo_r, y + halo_r)],
                    fill=(*halo_rgb, int(75 * pulse)),
                )
                draw_ov.ellipse(
                    [(x - core_r, y - core_r), (x + core_r, y + core_r)],
                    fill=(*core_rgb, 255),
                )

            base.paste(overlay, (0, 0), overlay)
            draw = ImageDraw.Draw(base)

            draw.rectangle([(0, 0), (width, int(height * 0.008))], fill=(255, 30, 0))

            pad_x = int(width * 0.03)
            pad_y = int(height * 0.04)

            if hud_alert:
                draw.rectangle(
                    [(pad_x, pad_y), (pad_x + int(width * 0.18), pad_y + int(height * 0.034))],
                    fill=(180, 20, 10),
                )
                draw.text(
                    (pad_x + 8, pad_y + 4),
                    hud_alert,
                    font=font_hud_mono,
                    fill=(255, 255, 255),
                )

            y_pos = pad_y + int(height * 0.042)
            if hud_metric_1:
                draw.text((pad_x, y_pos), hud_metric_1, font=font_hud_title, fill=(255, 60, 40))
                y_pos += int(height * 0.040)
            if hud_metric_2:
                draw.text((pad_x, y_pos), hud_metric_2, font=font_hud_title, fill=(255, 200, 50))
                y_pos += int(height * 0.040)
            if hud_metric_3:
                draw.text((pad_x, y_pos), hud_metric_3, font=font_hud_title, fill=(255, 255, 255))
                y_pos += int(height * 0.040)
            if hud_sub_status:
                draw.text((pad_x, y_pos), hud_sub_status, font=font_hud_body, fill=(180, 200, 220))

            tr_x = width - int(width * 0.28)
            timecode = f"T+{int(t//60):02d}:{int(t%60):02d}:{int((t*100)%100):02d}"
            draw.text((tr_x, pad_y), f"ELAPSED: {timecode}", font=font_hud_mono, fill=(56, 189, 248))

            tr_y = pad_y + int(height * 0.025)
            if hud_telemetry_1:
                draw.text((tr_x, tr_y), hud_telemetry_1, font=font_hud_body, fill=(248, 113, 113))
                tr_y += int(height * 0.023)
            if hud_telemetry_2:
                draw.text((tr_x, tr_y), hud_telemetry_2, font=font_hud_body, fill=(255, 200, 50))
                tr_y += int(height * 0.023)
            if hud_satellite:
                draw.text((tr_x, tr_y), hud_satellite, font=font_hud_mono, fill=(148, 163, 184))

            _draw_tactical_crosshairs(draw, width, height)

            if hud_footer:
                bot_y = height - int(height * 0.04)
                draw.rectangle([(0, bot_y), (width, height)], fill=(11, 15, 22))
                draw.text(
                    (pad_x, bot_y + int(height * 0.008)),
                    hud_footer,
                    font=font_hud_mono,
                    fill=(100, 120, 145),
                )

            yield base

    return _encode_frames_to_mp4(
        frame_generator=_frame_generator(),
        output_path=output_path,
        duration=duration,
        fps=fps,
        width=width,
        height=height,
        ffmpeg=ffmpeg,
    )


# ---------------------------------------------------------------------------
# Generator 2: Environmental / Telemetry Curve Video
# ---------------------------------------------------------------------------

def generate_temperature_curve_video(
    output_path: str | Path,
    duration: float = 5.0,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    ffmpeg: str | None = None,
    data_payload: dict[str, Any] | None = None,
) -> Path:
    """Generate dynamic telemetry curve video driven strictly by data_payload."""
    total_frames = max(1, int(round(duration * fps)))

    payload = data_payload or {}
    chart_title = str(payload.get("chart_title") or "")
    unit = str(payload.get("unit") or "")
    has_values = ("start_value" in payload or "end_value" in payload)
    start_val = float(payload.get("start_value", 0.0))
    end_val = float(payload.get("end_value", 0.0))
    threshold_val = float(payload["threshold_value"]) if "threshold_value" in payload else None
    threshold_label = str(payload.get("threshold_label") or "")
    metric_a_label = str(payload.get("metric_a_label") or payload.get("metric_a_prefix") or "")
    metric_b_text = str(payload.get("metric_b_text") or "")
    telemetry_top_1 = str(payload.get("telemetry_top_1") or "")
    telemetry_top_2 = str(payload.get("telemetry_top_2") or "")
    telemetry_top_3 = str(payload.get("telemetry_top_3") or "")
    x_axis_title = str(payload.get("x_axis_title") or "")

    font_huge_temp = resolve_hud_font(size=max(24, int(height * 0.075)), bold=True)
    font_hud_title = resolve_hud_font(size=max(14, int(height * 0.028)), bold=True)
    font_hud_body = resolve_hud_font(size=max(11, int(height * 0.018)), bold=False)
    font_hud_mono = resolve_hud_font(size=max(10, int(height * 0.015)), bold=True)

    gx1 = int(width * 0.12)
    gx2 = int(width * 0.88)
    gy1 = int(height * 0.22)
    gy2 = int(height * 0.84)
    graph_w = gx2 - gx1
    graph_h = gy2 - gy1

    val_max = max(start_val, end_val) + 5.0 if has_values else 10.0
    val_min = min(start_val, end_val) - 5.0 if has_values else -10.0
    val_range = max(1.0, val_max - val_min)
    val_drop = start_val - end_val

    def _val_to_y(val: float) -> int:
        norm = (val_max - val) / val_range
        return int(gy1 + norm * graph_h)

    def _progress_to_val(p: float) -> float:
        sigmoid = 1.0 / (1.0 + math.exp(-8.0 * (p - 0.42)))
        return start_val - val_drop * sigmoid

    def _frame_generator() -> Generator[Image.Image, None, None]:
        for frame_idx in range(total_frames):
            p = min(1.0, frame_idx / max(1, total_frames - 1))
            t = frame_idx / fps
            current_val = _progress_to_val(p) if has_values else 0.0

            base = Image.new("RGB", (width, height), (6, 9, 14))
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw_base = ImageDraw.Draw(base)
            draw_ov = ImageDraw.Draw(overlay)

            if threshold_val is not None:
                thresh_y = _val_to_y(threshold_val)
                draw_ov.rectangle([(gx1, thresh_y), (gx2, gy2)], fill=(14, 38, 68, 85))
                draw_base.line([(gx1, thresh_y), (gx2, thresh_y)], fill=(56, 189, 248), width=2)
                if threshold_label:
                    draw_base.text((gx2 - int(width * 0.22), thresh_y - 18), threshold_label, font=font_hud_mono, fill=(56, 189, 248))

            for month in range(0, 13, 2):
                mx = gx1 + int((month / 12.0) * graph_w)
                draw_base.line([(mx, gy1), (mx, gy2)], fill=(24, 36, 52), width=1)
                draw_base.text((mx - 15, gy2 + 10), f"M{month:02d}", font=font_hud_mono, fill=(100, 130, 160))

            if has_values:
                steps = max(2, int(p * 200))
                curve_points: list[tuple[int, int]] = []
                for s in range(steps + 1):
                    sp = (s / 200.0)
                    cx = gx1 + int(sp * graph_w)
                    cy = _val_to_y(_progress_to_val(sp))
                    curve_points.append((cx, cy))

                if len(curve_points) >= 2:
                    poly_pts = [(curve_points[0][0], gy2)] + curve_points + [(curve_points[-1][0], gy2)]
                    draw_ov.polygon(poly_pts, fill=(6, 182, 212, 35))

                    for i in range(len(curve_points) - 1):
                        p1 = curve_points[i]
                        p2 = curve_points[i + 1]
                        draw_base.line([p1, p2], fill=(6, 182, 212), width=4)

                    tip_x, tip_y = curve_points[-1]
                    draw_base.ellipse([(tip_x - 5, tip_y - 5), (tip_x + 5, tip_y + 5)], fill=(255, 255, 255), outline=(6, 182, 212), width=2)

            base.paste(overlay, (0, 0), overlay)
            draw = ImageDraw.Draw(base)

            pad_x = int(width * 0.04)
            pad_y = int(height * 0.04)

            if chart_title:
                draw.text((pad_x, pad_y), chart_title, font=font_hud_mono, fill=(148, 163, 184))
            if has_values:
                draw.text((pad_x, pad_y + int(height * 0.025)), f"{current_val:+.1f}{unit}", font=font_huge_temp, fill=(56, 189, 248))

            alert_box_x = int(width * 0.44)
            if metric_a_label:
                draw.rectangle([(alert_box_x, pad_y), (alert_box_x + int(width * 0.27), pad_y + int(height * 0.042))], fill=(15, 23, 42), outline=(56, 189, 248), width=1)
                draw.text((alert_box_x + 10, pad_y + int(height * 0.010)), metric_a_label, font=font_hud_mono, fill=(56, 189, 248))

            if metric_b_text and (threshold_val is None or current_val <= threshold_val or p > 0.6):
                strobe_red = (220, 38, 38) if int(t * 3) % 2 == 0 else (185, 28, 28)
                draw.rectangle([(alert_box_x, pad_y + int(height * 0.052)), (alert_box_x + int(width * 0.27), pad_y + int(height * 0.094))], fill=strobe_red)
                draw.text((alert_box_x + 10, pad_y + int(height * 0.062)), metric_b_text, font=font_hud_title, fill=(255, 255, 255))

            tr_x = width - int(width * 0.25)
            tr_y = pad_y
            if telemetry_top_1:
                draw.text((tr_x, tr_y), telemetry_top_1, font=font_hud_mono, fill=(248, 113, 113))
                tr_y += int(height * 0.024)
            if telemetry_top_2:
                draw.text((tr_x, tr_y), telemetry_top_2, font=font_hud_mono, fill=(255, 200, 50))
                tr_y += int(height * 0.024)
            if telemetry_top_3:
                draw.text((tr_x, tr_y), telemetry_top_3, font=font_hud_body, fill=(148, 163, 184))

            _draw_tactical_crosshairs(draw, width, height)

            if x_axis_title:
                draw.text((gx1 + int(graph_w * 0.35), gy2 + int(height * 0.045)), x_axis_title, font=font_hud_mono, fill=(100, 130, 160))

            yield base

    return _encode_frames_to_mp4(
        frame_generator=_frame_generator(),
        output_path=output_path,
        duration=duration,
        fps=fps,
        width=width,
        height=height,
        ffmpeg=ffmpeg,
    )


# ---------------------------------------------------------------------------
# Generator 3: Shockwave Grid Video
# ---------------------------------------------------------------------------

def generate_pressure_grid_video(
    output_path: str | Path,
    duration: float = 5.0,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    ffmpeg: str | None = None,
    data_payload: dict[str, Any] | None = None,
) -> Path:
    """Generate dynamic shockwave anomaly grid video driven strictly by data_payload."""
    total_frames = max(1, int(round(duration * fps)))
    font_hud_title = resolve_hud_font(size=max(14, int(height * 0.028)), bold=True)
    font_hud_mono = resolve_hud_font(size=max(10, int(height * 0.015)), bold=True)

    payload = data_payload or {}
    hud_title = str(payload.get("title") or "")
    start_val = float(payload.get("start_pressure", 1000.0))
    end_val = float(payload.get("end_pressure", 1000.0))
    val_delta = start_val - end_val
    metric_label = str(payload.get("metric_label") or "")
    velocity_label = str(payload.get("velocity_label") or "")

    def _frame_generator() -> Generator[Image.Image, None, None]:
        cx, cy = width // 2, height // 2
        for frame_idx in range(total_frames):
            p = frame_idx / max(1, total_frames - 1)
            t = frame_idx / fps
            current_val = start_val - val_delta * p

            base = Image.new("RGB", (width, height), (8, 10, 14))
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw_base = ImageDraw.Draw(base)
            draw_ov = ImageDraw.Draw(overlay)

            for ring in range(1, 9):
                r = int(ring * (height * 0.07) + (t * 40.0) % (height * 0.07))
                alpha = int(max(0, 140 * (1.0 - (r / (height * 0.65)))))
                draw_ov.ellipse(
                    [(cx - r, cy - r), (cx + r, cy + r)],
                    outline=(239, 68, 68, alpha),
                    width=2,
                )

            draw_base.line([(0, cy), (width, cy)], fill=(24, 32, 44), width=1)
            draw_base.line([(cx, 0), (cx, height)], fill=(24, 32, 44), width=1)

            base.paste(overlay, (0, 0), overlay)
            draw = ImageDraw.Draw(base)

            if hud_title:
                draw.text((int(width * 0.04), int(height * 0.05)), hud_title, font=font_hud_title, fill=(239, 68, 68))
            if metric_label:
                draw.text((int(width * 0.04), int(height * 0.09)), f"{metric_label}: {current_val:.1f}", font=font_hud_mono, fill=(255, 200, 50))
            if velocity_label:
                draw.text((int(width * 0.04), int(height * 0.12)), velocity_label, font=font_hud_mono, fill=(56, 189, 248))

            _draw_tactical_crosshairs(draw, width, height)
            yield base

    return _encode_frames_to_mp4(
        frame_generator=_frame_generator(),
        output_path=output_path,
        duration=duration,
        fps=fps,
        width=width,
        height=height,
        ffmpeg=ffmpeg,
    )


# ---------------------------------------------------------------------------
# Visual Polish: Tactical Crosshairs & Corner Brackets
# ---------------------------------------------------------------------------

def _draw_tactical_crosshairs(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    """Draw sci-fi tactical targeting brackets and border tick marks."""
    bracket_len = int(min(width, height) * 0.035)
    margin = int(min(width, height) * 0.02)
    b_color = (65, 85, 110)

    draw.line([(margin, margin), (margin + bracket_len, margin)], fill=b_color, width=2)
    draw.line([(margin, margin), (margin, margin + bracket_len)], fill=b_color, width=2)

    draw.line([(width - margin, margin), (width - margin - bracket_len, margin)], fill=b_color, width=2)
    draw.line([(width - margin, margin), (width - margin, margin + bracket_len)], fill=b_color, width=2)

    draw.line([(margin, height - margin), (margin + bracket_len, height - margin)], fill=b_color, width=2)
    draw.line([(margin, height - margin), (margin, height - margin - bracket_len)], fill=b_color, width=2)

    draw.line([(width - margin, height - margin), (width - margin - bracket_len, height - margin)], fill=b_color, width=2)
    draw.line([(width - margin, height - margin), (width - margin, height - margin - bracket_len)], fill=b_color, width=2)


# ---------------------------------------------------------------------------
# Unified Data B-Roll Entry Point
# ---------------------------------------------------------------------------

def generate_data_broll(
    broll_type: str,
    output_path: str | Path,
    duration: float = 5.0,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    ffmpeg: str | None = None,
    data_payload: dict[str, Any] | None = None,
) -> Path:
    """Unified entry point for dynamic data B-roll video generation."""
    key = broll_type.lower().strip()

    if key in ("volcano_map", "volcano", "seismic_map", "seismic"):
        return generate_volcano_map_video(
            output_path=output_path,
            duration=duration,
            fps=fps,
            width=width,
            height=height,
            ffmpeg=ffmpeg,
            data_payload=data_payload,
        )
    elif key in ("temperature_drop", "temperature_curve", "thermal_collapse", "temperature", "winter"):
        return generate_temperature_curve_video(
            output_path=output_path,
            duration=duration,
            fps=fps,
            width=width,
            height=height,
            ffmpeg=ffmpeg,
            data_payload=data_payload,
        )
    elif key in ("pressure_grid", "pressure", "shockwave", "isobars"):
        return generate_pressure_grid_video(
            output_path=output_path,
            duration=duration,
            fps=fps,
            width=width,
            height=height,
            ffmpeg=ffmpeg,
            data_payload=data_payload,
        )
    else:
        raise ValueError(
            f"Unsupported broll_type: '{broll_type}'. Supported types: "
            "['volcano_map', 'temperature_drop', 'pressure_grid']"
        )


# ---------------------------------------------------------------------------
# Self-Test Validation Function
# ---------------------------------------------------------------------------

def test_map_overlay_generator() -> bool:
    """Self-contained runnable validation for map_overlay_generator module."""
    test_dir = Path(tempfile.mkdtemp(prefix="test_map_overlay_"))
    try:
        volcano_out = test_dir / "volcano_test.mp4"
        v_res = generate_volcano_map_video(
            output_path=volcano_out,
            duration=1.0,
            fps=24,
            width=640,
            height=360,
            data_payload={"alert_badge": "TEST", "metric_1": "SYSTEM CHECK"},
        )
        assert v_res.is_file(), f"Volcano map video was not created: {v_res}"
        assert v_res.stat().st_size > 5000, "Volcano map video is unexpectedly small"

        temp_out = test_dir / "temp_test.mp4"
        t_res = generate_temperature_curve_video(
            output_path=temp_out,
            duration=1.0,
            fps=24,
            width=640,
            height=360,
            data_payload={"chart_title": "TEST CURVE", "start_value": 10.0, "end_value": 0.0},
        )
        assert t_res.is_file(), f"Temperature curve video was not created: {t_res}"
        assert t_res.stat().st_size > 5000, "Temperature curve video is unexpectedly small"

        broll_out = test_dir / "broll_test.mp4"
        b_res = generate_data_broll(
            broll_type="pressure_grid",
            output_path=broll_out,
            duration=1.0,
            fps=24,
            width=640,
            height=360,
            data_payload={"title": "PRESSURE TEST"},
        )
        assert b_res.is_file(), f"Data B-roll video was not created: {b_res}"
        assert b_res.stat().st_size > 5000, "Data B-roll video is unexpectedly small"

        logger.info("[MAP OVERLAY] All map overlay generator self-tests passed successfully.")
        return True
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = test_map_overlay_generator()
    print(f"map_overlay_generator self-test passed: {success}")
