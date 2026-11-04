"""Procedural Deterministic B-Roll & Tactical HUD Overlay Generator.

Provides dynamic, zero-cost, broadcast-standard graphical B-roll videos
for Procedural Catastrophe documentaries using Pillow (PIL) and FFmpeg:
1. Volcano Seismic Map Video:
   Dark tactical world map with continental landmasses, tectonic plate boundaries,
   and ~1,000 pulsing glowing red/orange LED eruption nodes along the Pacific
   Ring of Fire and global tectonic belts, complete with live HUD telemetry:
   "SEISMIC ACTIVITY: CRITICAL", "ACTIVE ERUPTIONS: 1000/1000", "MAGNITUDE: 9.8+".
2. Temperature Curve Video:
   Strategic climate collapse telemetry screen tracking global volcanic winter
   temperature drop from +22°C down to -15°C, complete with sub-zero freezing
   threshold, glowing dynamic neon trajectory, and HUD indicators:
   "STRATOSPHERIC AEROSOL OPTICAL DEPTH: >2.0", "GLOBAL THERMAL COLLAPSE: -15°C".
3. Pressure Grid Video:
   Atmospheric shockwave anomaly grid with expanding supersonic isobars and
   barometric drop readouts (1013.2 hPa -> 840.0 hPa).
4. Unified Dispatcher (`generate_data_broll`):
   General entry point for automated sequence assembly.
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
from typing import Generator, List, Optional, Tuple, Union

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

    # Resilient fallback
    default_font = ImageFont.load_default()
    _FONT_CACHE[cache_key] = default_font
    return default_font


# ---------------------------------------------------------------------------
# Continental Landmass Polygons & Tectonic Chains (Equirectangular Lat/Lon)
# ---------------------------------------------------------------------------

def _ll2xy(lon: float, lat: float, width: int, height: int) -> Tuple[int, int]:
    """Project longitude (-180..180) and latitude (-90..90) to canvas pixel coordinates."""
    x = (lon + 180.0) / 360.0 * width
    y = (90.0 - lat) / 180.0 * height
    return int(round(x)), int(round(y))


CONTINENTAL_OUTLINES: dict[str, list[tuple[float, float]]] = {
    "north_america": [
        (-168, 65), (-140, 70), (-120, 75), (-85, 70), (-60, 60), (-55, 50),
        (-65, 44), (-75, 35), (-80, 25), (-88, 30), (-97, 26), (-90, 20),
        (-83, 10), (-78, 8), (-85, 14), (-105, 20), (-110, 24), (-115, 32),
        (-124, 40), (-125, 50), (-135, 58), (-165, 60), (-168, 65)
    ],
    "greenland": [
        (-45, 83), (-20, 80), (-20, 70), (-40, 60), (-50, 65), (-55, 75), (-45, 83)
    ],
    "south_america": [
        (-78, 8), (-60, 10), (-50, 0), (-35, -5), (-38, -15), (-45, -23),
        (-55, -35), (-65, -45), (-70, -55), (-75, -50), (-72, -40), (-76, -20),
        (-81, -5), (-78, 8)
    ],
    "eurasia": [
        (-9, 36), (-9, 43), (0, 48), (5, 58), (15, 56), (25, 70), (45, 68),
        (70, 73), (105, 77), (140, 72), (170, 66), (160, 55), (140, 50),
        (130, 42), (122, 32), (118, 24), (108, 18), (105, 10), (100, 5),
        (95, 20), (88, 22), (80, 10), (75, 15), (68, 24), (60, 25),
        (55, 15), (45, 12), (35, 28), (28, 41), (20, 40), (15, 38),
        (-5, 36), (-9, 36)
    ],
    "africa": [
        (-5, 36), (10, 37), (25, 32), (32, 31), (34, 27), (43, 12), (51, 10),
        (40, -5), (35, -20), (28, -32), (18, -34), (12, -20), (10, -5),
        (0, 5), (-15, 12), (-17, 16), (-12, 28), (-5, 36)
    ],
    "australia": [
        (115, -22), (122, -15), (130, -12), (136, -12), (142, -11), (145, -15),
        (153, -28), (150, -37), (142, -38), (135, -34), (125, -33), (115, -34),
        (113, -26), (115, -22)
    ],
    "antarctica": [
        (-180, -72), (-120, -70), (-60, -64), (0, -68), (60, -66),
        (120, -65), (180, -72), (180, -90), (-180, -90), (-180, -72)
    ],
    "japan": [
        (130, 32), (132, 34), (138, 37), (141, 43), (145, 44), (141, 38), (135, 34), (130, 32)
    ],
    "uk": [
        (-5, 50), (-1, 51), (1, 53), (-2, 57), (-5, 58), (-6, 54), (-5, 50)
    ]
}

TECTONIC_BOUNDARIES: list[list[tuple[float, float]]] = [
    # Pacific Ring of Fire - East Arc (South America -> Alaska)
    [
        (-72, -54), (-72, -42), (-71, -30), (-75, -18), (-78, -8),
        (-78, 2), (-85, 10), (-92, 14), (-102, 18), (-115, 32),
        (-122, 40), (-124, 46), (-135, 56), (-152, 60), (-168, 54),
        (-178, 52), (175, 52), (160, 55)
    ],
    # Pacific Ring of Fire - West Arc (Kamchatka -> New Zealand)
    [
        (160, 55), (155, 50), (143, 44), (139, 36), (130, 30),
        (124, 16), (124, 8), (126, 0), (120, -6), (112, -8),
        (100, -2), (132, -4), (148, -6), (160, -10), (168, -16),
        (178, -22), (176, -38), (173, -45)
    ],
    # Mid-Atlantic Ridge (Iceland -> South Atlantic)
    [
        (-18, 66), (-24, 56), (-32, 45), (-42, 30), (-35, 14),
        (-30, 0), (-20, -16), (-15, -32), (-12, -48), (-10, -56)
    ],
    # Alpine-Himalayan Belt (Mediterranean -> Indonesia)
    [
        (-5, 36), (14, 40), (24, 38), (35, 39), (48, 36),
        (62, 32), (76, 32), (88, 28), (96, 22), (98, 12)
    ],
    # East African Rift System
    [
        (43, 12), (39, 7), (36, 0), (35, -6), (34, -13), (35, -20)
    ]
]

# Major Caldera Centers for Epicenter Shockwaves
MAJOR_CALDERAS: list[tuple[float, float, str]] = [
    (-110.5, 44.4, "YELLOWSTONE"),
    (105.4, -6.1, "KRAKATOA"),
    (98.8, 2.6, "TOBA"),
    (175.9, -38.8, "TAUPO"),
    (14.1, 40.8, "CAMPI FLEGREI"),
    (118.0, -8.2, "TAMBORA"),
    (120.3, 15.1, "PINATUBO"),
    (25.4, 36.4, "SANTORINI"),
]


@dataclass
class VolcanoNode:
    """Deterministic volcano eruption node."""
    lon: float
    lat: float
    radius: float
    freq: float
    phase: float
    core_rgb: tuple[int, int, int]
    halo_rgb: tuple[int, int, int]


def _build_volcano_nodes(target_count: int = 1000, seed: int = 42) -> list[VolcanoNode]:
    """Generate deterministically positioned volcano nodes concentrated on tectonic rifts."""
    rng = random.Random(seed)
    nodes: list[VolcanoNode] = []

    # Distribution budget across tectonic chains
    # Total = 350 + 350 + 100 + 100 + 60 + 40 = 1000
    chain_budgets = [
        (TECTONIC_BOUNDARIES[0], 350),  # Pacific East
        (TECTONIC_BOUNDARIES[1], 350),  # Pacific West
        (TECTONIC_BOUNDARIES[2], 100),  # Mid-Atlantic
        (TECTONIC_BOUNDARIES[3], 100),  # Alpine-Himalayan
        (TECTONIC_BOUNDARIES[4], 60),   # East Africa Rift
    ]

    color_palette = [
        ((255, 60, 0), (255, 30, 0)),     # Blazing Red
        ((255, 120, 0), (255, 80, 0)),    # Incandescent Orange
        ((255, 180, 20), (255, 110, 0)),  # Molten Amber
        ((255, 230, 80), (255, 150, 0)),  # White-Hot Gold
    ]

    for waypoints, budget in chain_budgets:
        for _ in range(budget):
            seg_idx = rng.randint(0, len(waypoints) - 2)
            p1 = waypoints[seg_idx]
            p2 = waypoints[seg_idx + 1]
            t = rng.random()
            lon = p1[0] + (p2[0] - p1[0]) * t + rng.gauss(0, 1.4)
            lat = p1[1] + (p2[1] - p1[1]) * t + rng.gauss(0, 1.4)
            # Clamp lat/lon
            lon = max(-179.0, min(179.0, lon))
            lat = max(-80.0, min(80.0, lat))

            core, halo = rng.choice(color_palette)
            nodes.append(
                VolcanoNode(
                    lon=lon,
                    lat=lat,
                    radius=rng.uniform(1.8, 3.8),
                    freq=rng.uniform(0.9, 3.6),
                    phase=rng.uniform(0.0, math.tau),
                    core_rgb=core,
                    halo_rgb=halo,
                )
            )

    # 40 Hotspots (Hawaii, Yellowstone, Galapagos, Iceland, Reunion, Azores, etc.)
    hotspot_anchors = [
        (-155.3, 19.4),   # Hawaii Kilauea
        (-110.5, 44.4),   # Yellowstone
        (-91.2, -0.4),    # Galapagos
        (-19.0, 64.9),    # Iceland Bardarbunga
        (55.7, -21.2),    # Reunion Piton de la Fournaise
        (-16.6, 28.3),    # Canary Islands Tenerife
        (-25.7, 37.7),    # Azores
        (168.3, -16.2),   # Vanuatu Ambrym
    ]

    for _ in range(40):
        anchor = rng.choice(hotspot_anchors)
        lon = anchor[0] + rng.gauss(0, 1.8)
        lat = anchor[1] + rng.gauss(0, 1.8)
        core, halo = rng.choice(color_palette)
        nodes.append(
            VolcanoNode(
                lon=max(-179.0, min(179.0, lon)),
                lat=max(-80.0, min(80.0, lat)),
                radius=rng.uniform(2.2, 4.5),
                freq=rng.uniform(1.2, 4.0),
                phase=rng.uniform(0.0, math.tau),
                core_rgb=core,
                halo_rgb=halo,
            )
        )

    return nodes[:target_count]


_GLOBAL_VOLCANO_NODES = _build_volcano_nodes(1000, seed=42)


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
    """Pipe raw RGB24 frames directly into FFmpeg stdin to produce an H.264 broadcast MP4."""
    ffmpeg_bin = ffmpeg or config.resolve_ffmpeg()
    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{width}x{height}",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-preset", "veryfast",
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
# Generator 1: 1,000 Volcanoes Seismic Activity Map Video
# ---------------------------------------------------------------------------

def generate_volcano_map_video(
    output_path: str | Path,
    duration: float = 5.0,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    ffmpeg: str | None = None,
) -> Path:
    """Generate deterministic tactical video of 1,000 synchronous erupting volcanoes.

    Renders styled continental landmasses, plate tectonics, pulsing LED volcano clusters,
    expanding caldera shockwaves, and critical HUD telemetry overlays.
    """
    total_frames = max(1, int(round(duration * fps)))
    font_hud_title = resolve_hud_font(size=max(14, int(height * 0.030)), bold=True)
    font_hud_body = resolve_hud_font(size=max(11, int(height * 0.018)), bold=False)
    font_hud_mono = resolve_hud_font(size=max(10, int(height * 0.015)), bold=True)

    # Pre-project continental polygons
    projected_continents: list[list[tuple[int, int]]] = [
        [_ll2xy(lon, lat, width, height) for lon, lat in coords]
        for coords in CONTINENTAL_OUTLINES.values()
    ]

    # Pre-project tectonic lines
    projected_faults: list[list[tuple[int, int]]] = [
        [_ll2xy(lon, lat, width, height) for lon, lat in line]
        for line in TECTONIC_BOUNDARIES
    ]

    # Pre-project caldera epicenters
    projected_calderas: list[tuple[int, int, str]] = [
        (*_ll2xy(lon, lat, width, height), name)
        for lon, lat, name in MAJOR_CALDERAS
    ]

    # Pre-project 1000 volcano node coordinates
    projected_nodes: list[tuple[int, int, float, float, float, tuple[int, int, int], tuple[int, int, int]]] = [
        (
            *_ll2xy(n.lon, n.lat, width, height),
            n.radius * (height / 1080.0),
            n.freq,
            n.phase,
            n.core_rgb,
            n.halo_rgb,
        )
        for n in _GLOBAL_VOLCANO_NODES
    ]

    def _frame_generator() -> Generator[Image.Image, None, None]:
        for frame_idx in range(total_frames):
            t = frame_idx / fps

            # 1. Base Slate Background
            base = Image.new("RGB", (width, height), (7, 10, 15))
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw_base = ImageDraw.Draw(base)
            draw_ov = ImageDraw.Draw(overlay)

            # 2. Coordinate Grid (Latitude & Longitude)
            for lon in range(-180, 181, 30):
                gx, _ = _ll2xy(lon, 0, width, height)
                draw_base.line([(gx, 0), (gx, height)], fill=(18, 25, 36), width=1)
            for lat in range(-60, 91, 30):
                _, gy = _ll2xy(0, lat, width, height)
                draw_base.line([(0, gy), (width, gy)], fill=(18, 25, 36), width=1)

            # 3. Continental Landmasses
            for poly in projected_continents:
                draw_base.polygon(poly, fill=(14, 20, 29), outline=(32, 45, 62))

            # 4. Tectonic Fault Lines (Subtle Amber-Cyan Glow)
            for fault in projected_faults:
                if len(fault) > 1:
                    draw_base.line(fault, fill=(45, 65, 88), width=2)

            # 5. Expanding Caldera Shockwaves
            for cx, cy, cname in projected_calderas:
                # Emitter cycles every 1.6s
                phase_t = (t + (cx % 100) * 0.01) % 1.6
                wave_r = int(phase_t * (height * 0.12))
                wave_alpha = int(max(0, 140 * (1.0 - phase_t / 1.6)))
                if wave_r > 3 and wave_alpha > 5:
                    draw_ov.ellipse(
                        [(cx - wave_r, cy - wave_r), (cx + wave_r, cy + wave_r)],
                        outline=(255, 70, 0, wave_alpha),
                        width=2,
                    )

            # 6. 1,000 Pulsing Glowing Volcano Nodes
            for x, y, r, freq, phase, core_rgb, halo_rgb in projected_nodes:
                pulse = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(math.tau * freq * t + phase))
                halo_r = r * 2.8 * pulse
                core_r = max(1.0, r * 0.9 * pulse)

                # Outer Translucent Halo
                draw_ov.ellipse(
                    [(x - halo_r, y - halo_r), (x + halo_r, y + halo_r)],
                    fill=(*halo_rgb, int(75 * pulse)),
                )
                # Inner Molten Core
                draw_ov.ellipse(
                    [(x - core_r, y - core_r), (x + core_r, y + core_r)],
                    fill=(*core_rgb, 255),
                )

            # Composite glowing overlay
            base.paste(overlay, (0, 0), overlay)
            draw = ImageDraw.Draw(base)

            # 7. Tactical HUD Overlays
            # Top Alert Bar (Strobe red pulse)
            alert_strobe = int(abs(math.sin(t * 4.0)) * 255)
            draw.rectangle([(0, 0), (width, int(height * 0.008))], fill=(255, 30, 0))

            # HUD Box 1: Top-Left Critical Status
            pad_x = int(width * 0.03)
            pad_y = int(height * 0.04)

            # Warning Badge
            draw.rectangle(
                [(pad_x, pad_y), (pad_x + int(width * 0.18), pad_y + int(height * 0.034))],
                fill=(180, 20, 10),
            )
            draw.text(
                (pad_x + 8, pad_y + 4),
                "CRITICAL ALERT // GLOBAL EVENT",
                font=font_hud_mono,
                fill=(255, 255, 255),
            )

            # High-Impact Mandatory HUD Directives
            draw.text(
                (pad_x, pad_y + int(height * 0.042)),
                "SEISMIC ACTIVITY: CRITICAL",
                font=font_hud_title,
                fill=(255, 60, 40),
            )
            draw.text(
                (pad_x, pad_y + int(height * 0.082)),
                "ACTIVE ERUPTIONS: 1000/1000",
                font=font_hud_title,
                fill=(255, 200, 50),
            )
            draw.text(
                (pad_x, pad_y + int(height * 0.122)),
                "MAGNITUDE: 9.8+",
                font=font_hud_title,
                fill=(255, 255, 255),
            )

            draw.text(
                (pad_x, pad_y + int(height * 0.165)),
                "TECTONIC CASCADE: GLOBAL SYNCHRONIZATION DETECTED",
                font=font_hud_body,
                fill=(180, 200, 220),
            )

            # HUD Box 2: Top-Right Geodetic Telemetry
            tr_x = width - int(width * 0.28)
            timecode = f"T+{int(t//60):02d}:{int(t%60):02d}:{int((t*100)%100):02d}"
            draw.text(
                (tr_x, pad_y),
                f"MISSION ELAPSED: {timecode}",
                font=font_hud_mono,
                fill=(56, 189, 248),
            )
            draw.text(
                (tr_x, pad_y + int(height * 0.025)),
                "PACIFIC RIM: 100% UNSTABLE",
                font=font_hud_body,
                fill=(248, 113, 113),
            )
            draw.text(
                (tr_x, pad_y + int(height * 0.048)),
                "STRATOSPHERIC INJECTION: 850 MT/S",
                font=font_hud_body,
                fill=(255, 200, 50),
            )
            draw.text(
                (tr_x, pad_y + int(height * 0.071)),
                "SATELLITE DOWNLINK: CASP-09 [GEO-SYNC]",
                font=font_hud_mono,
                fill=(148, 163, 184),
            )

            # Tactical Brackets & Targeting Crosshairs
            _draw_tactical_crosshairs(draw, width, height)

            # Bottom Status Bar
            bot_y = height - int(height * 0.04)
            draw.rectangle([(0, bot_y), (width, height)], fill=(11, 15, 22))
            draw.text(
                (pad_x, bot_y + int(height * 0.008)),
                "GLOBAL MONITORING NETWORK // TECTONIC VECTORING ENGINE v4.0 // ZERO RETRIEVAL LOSS",
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
# Generator 2: Volcanic Winter Temperature Collapse Curve Video
# ---------------------------------------------------------------------------

def generate_temperature_curve_video(
    output_path: str | Path,
    duration: float = 5.0,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    ffmpeg: str | None = None,
) -> Path:
    """Generate strategic telemetry video tracking volcanic winter global temperature collapse.

    Renders dynamic temperature graph starting at +22°C and plummeting to -15°C,
    sub-zero thermal freezing boundary, real-time digital readouts, and atmospheric
    optical depth alerts.
    """
    total_frames = max(1, int(round(duration * fps)))

    font_huge_temp = resolve_hud_font(size=max(24, int(height * 0.075)), bold=True)
    font_hud_title = resolve_hud_font(size=max(14, int(height * 0.028)), bold=True)
    font_hud_body = resolve_hud_font(size=max(11, int(height * 0.018)), bold=False)
    font_hud_mono = resolve_hud_font(size=max(10, int(height * 0.015)), bold=True)

    # Graph Geometry Boundaries
    gx1 = int(width * 0.12)
    gx2 = int(width * 0.88)
    gy1 = int(height * 0.22)
    gy2 = int(height * 0.84)
    graph_w = gx2 - gx1
    graph_h = gy2 - gy1

    # Temperature Range Mapping: +25°C (top) to -20°C (bottom)
    temp_max = 25.0
    temp_min = -20.0
    temp_range = temp_max - temp_min

    def _temp_to_y(temp: float) -> int:
        norm = (temp_max - temp) / temp_range
        return int(gy1 + norm * graph_h)

    def _progress_to_temp(p: float) -> float:
        # Sigmoidal rapid climate collapse curve: +22°C down to -15.0°C
        # Drops sharply after Month 2 (p > 0.25)
        sigmoid = 1.0 / (1.0 + math.exp(-8.0 * (p - 0.42)))
        return 22.0 - 37.0 * sigmoid

    freezing_y = _temp_to_y(0.0)

    def _frame_generator() -> Generator[Image.Image, None, None]:
        for frame_idx in range(total_frames):
            p = min(1.0, frame_idx / max(1, total_frames - 1))
            t = frame_idx / fps
            current_temp = _progress_to_temp(p)
            current_aod = 0.08 + 2.82 * min(1.0, p * 1.35)  # Climbs from 0.08 to >2.80

            # 1. Base Dark Navy Space Canvas
            base = Image.new("RGB", (width, height), (6, 9, 14))
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw_base = ImageDraw.Draw(base)
            draw_ov = ImageDraw.Draw(overlay)

            # 2. Sub-Zero Freezing Zone Shading (0°C to -20°C)
            draw_ov.rectangle(
                [(gx1, freezing_y), (gx2, gy2)],
                fill=(14, 38, 68, 85),  # Cold blue gradient wash
            )

            # 3. Tactical Coordinate Grid Lines
            # Horizontal Temperature Ticks (+20, +15, +10, +5, 0, -5, -10, -15)
            for temp_tick in range(-15, 25, 5):
                ty = _temp_to_y(temp_tick)
                is_zero = (temp_tick == 0)
                line_color = (56, 189, 248) if is_zero else (24, 36, 52)
                line_w = 2 if is_zero else 1
                draw_base.line([(gx1, ty), (gx2, ty)], fill=line_color, width=line_w)
                # Label
                tick_label = f"{temp_tick:+d}°C"
                draw_base.text(
                    (gx1 - int(width * 0.055), ty - 8),
                    tick_label,
                    font=font_hud_mono,
                    fill=(120, 150, 180) if not is_zero else (56, 189, 248),
                )

            # 0°C Freezing Threshold Warning Label
            draw_base.text(
                (gx2 - int(width * 0.22), freezing_y - 18),
                "[ 0°C FREEZING THRESHOLD ]",
                font=font_hud_mono,
                fill=(56, 189, 248),
            )

            # Vertical Time Ticks (Month 0 to Month 12)
            for month in range(0, 13, 2):
                mx = gx1 + int((month / 12.0) * graph_w)
                draw_base.line([(mx, gy1), (mx, gy2)], fill=(24, 36, 52), width=1)
                draw_base.text(
                    (mx - 15, gy2 + 10),
                    f"M{month:02d}",
                    font=font_hud_mono,
                    fill=(100, 130, 160),
                )

            # 4. Draw Falling Temperature Trajectory Curve
            steps = max(2, int(p * 200))
            curve_points: list[tuple[int, int]] = []
            for s in range(steps + 1):
                sp = (s / 200.0)
                cx = gx1 + int(sp * graph_w)
                cy = _temp_to_y(_progress_to_temp(sp))
                curve_points.append((cx, cy))

            if len(curve_points) >= 2:
                # Translucent Area Shading under the curve
                poly_pts = [(curve_points[0][0], gy2)] + curve_points + [(curve_points[-1][0], gy2)]
                draw_ov.polygon(poly_pts, fill=(6, 182, 212, 35))

                # Trajectory Line Segments with Dynamic Color Transition
                for i in range(len(curve_points) - 1):
                    p1 = curve_points[i]
                    p2 = curve_points[i + 1]
                    seg_temp = _progress_to_temp((i / 200.0))
                    if seg_temp > 10.0:
                        seg_color = (249, 115, 22)   # Molten Amber (+22 -> +10)
                    elif seg_temp > 0.0:
                        seg_color = (234, 179, 8)    # Warning Gold (+10 -> 0)
                    elif seg_temp > -10.0:
                        seg_color = (6, 182, 212)    # Electric Cyan (0 -> -10)
                    else:
                        seg_color = (99, 102, 241)   # Freezing Cobalt Deep (-10 -> -15)

                    draw_base.line([p1, p2], fill=seg_color, width=4)

                # 5. Glowing Cursor Head with Radar Pulse Ping
                tip_x, tip_y = curve_points[-1]
                pulse_r = int((t * 24.0) % 18) + 4
                pulse_alpha = int(max(0, 180 * (1.0 - (pulse_r / 22.0))))
                draw_ov.ellipse(
                    [(tip_x - pulse_r, tip_y - pulse_r), (tip_x + pulse_r, tip_y + pulse_r)],
                    outline=(56, 189, 248, pulse_alpha),
                    width=2,
                )
                draw_base.ellipse(
                    [(tip_x - 5, tip_y - 5), (tip_x + 5, tip_y + 5)],
                    fill=(255, 255, 255),
                    outline=(6, 182, 212),
                    width=2,
                )

            # Composite glowing overlays
            base.paste(overlay, (0, 0), overlay)
            draw = ImageDraw.Draw(base)

            # 6. High-Tech Telemetry HUD Elements
            pad_x = int(width * 0.04)
            pad_y = int(height * 0.04)

            # Dynamic Temperature Big Digital Readout
            temp_color = (249, 115, 22) if current_temp > 5 else (56, 189, 248)
            draw.text(
                (pad_x, pad_y),
                "MEAN PLANETARY SURFACE TEMPERATURE",
                font=font_hud_mono,
                fill=(148, 163, 184),
            )
            draw.text(
                (pad_x, pad_y + int(height * 0.025)),
                f"{current_temp:+.1f}°C",
                font=font_huge_temp,
                fill=temp_color,
            )

            # Mandatory Telemetry Indicators
            alert_box_x = int(width * 0.44)
            # AOD Telemetry Box
            draw.rectangle(
                [(alert_box_x, pad_y), (alert_box_x + int(width * 0.27), pad_y + int(height * 0.042))],
                fill=(15, 23, 42),
                outline=(56, 189, 248),
                width=1,
            )
            aod_text = "STRATOSPHERIC AEROSOL OPTICAL DEPTH: >2.0" if current_aod >= 2.0 else f"AEROSOL OPTICAL DEPTH: {current_aod:.2f}"
            draw.text(
                (alert_box_x + 10, pad_y + int(height * 0.010)),
                aod_text,
                font=font_hud_mono,
                fill=(255, 200, 50) if current_aod >= 2.0 else (56, 189, 248),
            )

            # Global Thermal Collapse Box
            if current_temp <= -5.0 or p > 0.6:
                strobe_red = (220, 38, 38) if int(t * 3) % 2 == 0 else (185, 28, 28)
                draw.rectangle(
                    [(alert_box_x, pad_y + int(height * 0.052)), (alert_box_x + int(width * 0.27), pad_y + int(height * 0.094))],
                    fill=strobe_red,
                )
                draw.text(
                    (alert_box_x + 10, pad_y + int(height * 0.062)),
                    "GLOBAL THERMAL COLLAPSE: -15°C",
                    font=font_hud_title,
                    fill=(255, 255, 255),
                )

            # Top-Right Telemetry
            tr_x = width - int(width * 0.25)
            draw.text(
                (tr_x, pad_y),
                f"SOLAR FLUX DEFICIT: -{min(85.0, p * 85.0):.1f}%",
                font=font_hud_mono,
                fill=(248, 113, 113),
            )
            draw.text(
                (tr_x, pad_y + int(height * 0.024)),
                f"PHOTOSYNTHESIS INDEX: {max(0.0, (1.0 - p) * 100):.1f}%",
                font=font_hud_mono,
                fill=(255, 200, 50),
            )
            draw.text(
                (tr_x, pad_y + int(height * 0.048)),
                "HEMISPHERIC GLACIATION: EXPANDING",
                font=font_hud_body,
                fill=(148, 163, 184),
            )

            # Tactical Framing
            _draw_tactical_crosshairs(draw, width, height)

            # X-Axis & Y-Axis Titles
            draw.text(
                (gx1 + int(graph_w * 0.35), gy2 + int(height * 0.045)),
                "ELAPSED TIME SINCE SYNCHRONOUS ERUPTION (MONTHS)",
                font=font_hud_mono,
                fill=(100, 130, 160),
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
# Generator 3: Atmospheric Pressure Shockwave Grid Video
# ---------------------------------------------------------------------------

def generate_pressure_grid_video(
    output_path: str | Path,
    duration: float = 5.0,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    ffmpeg: str | None = None,
) -> Path:
    """Generate atmospheric pressure shockwave anomaly telemetry video."""
    total_frames = max(1, int(round(duration * fps)))
    font_hud_title = resolve_hud_font(size=max(14, int(height * 0.028)), bold=True)
    font_hud_mono = resolve_hud_font(size=max(10, int(height * 0.015)), bold=True)

    def _frame_generator() -> Generator[Image.Image, None, None]:
        cx, cy = width // 2, height // 2
        for frame_idx in range(total_frames):
            p = frame_idx / max(1, total_frames - 1)
            t = frame_idx / fps
            current_hpa = 1013.2 - 173.2 * p  # 1013.2 -> 840.0 hPa

            base = Image.new("RGB", (width, height), (8, 10, 14))
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw_base = ImageDraw.Draw(base)
            draw_ov = ImageDraw.Draw(overlay)

            # Concentric Radar Isobar Rings
            for ring in range(1, 9):
                r = int(ring * (height * 0.07) + (t * 40.0) % (height * 0.07))
                alpha = int(max(0, 140 * (1.0 - (r / (height * 0.65)))))
                draw_ov.ellipse(
                    [(cx - r, cy - r), (cx + r, cy + r)],
                    outline=(239, 68, 68, alpha),
                    width=2,
                )

            # Radial coordinate cross
            draw_base.line([(0, cy), (width, cy)], fill=(24, 32, 44), width=1)
            draw_base.line([(cx, 0), (cx, height)], fill=(24, 32, 44), width=1)

            base.paste(overlay, (0, 0), overlay)
            draw = ImageDraw.Draw(base)

            # Telemetry Labels
            draw.text(
                (int(width * 0.04), int(height * 0.05)),
                "BAROMETRIC ANOMALY: CRITICAL",
                font=font_hud_title,
                fill=(239, 68, 68),
            )
            draw.text(
                (int(width * 0.04), int(height * 0.09)),
                f"SURFACE PRESSURE: {current_hpa:.1f} hPa // EYE DETECTED",
                font=font_hud_mono,
                fill=(255, 200, 50),
            )
            draw.text(
                (int(width * 0.04), int(height * 0.12)),
                "SHOCKWAVE VELOCITY: MACH 1.18 [ATMOSPHERIC COMPRESSION]",
                font=font_hud_mono,
                fill=(56, 189, 248),
            )

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

    # Top-Left Bracket
    draw.line([(margin, margin), (margin + bracket_len, margin)], fill=b_color, width=2)
    draw.line([(margin, margin), (margin, margin + bracket_len)], fill=b_color, width=2)

    # Top-Right Bracket
    draw.line([(width - margin, margin), (width - margin - bracket_len, margin)], fill=b_color, width=2)
    draw.line([(width - margin, margin), (width - margin, margin + bracket_len)], fill=b_color, width=2)

    # Bottom-Left Bracket
    draw.line([(margin, height - margin), (margin + bracket_len, height - margin)], fill=b_color, width=2)
    draw.line([(margin, height - margin), (margin, height - margin - bracket_len)], fill=b_color, width=2)

    # Bottom-Right Bracket
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
) -> Path:
    """Unified entry point for procedural catastrophe data B-roll video generation.

    Parameters
    ----------
    broll_type:
        Type of B-roll to generate:
        - "volcano_map", "volcano", "seismic_map" -> 1,000 Volcanoes Seismic Activity Map
        - "temperature_drop", "temperature_curve", "thermal_collapse" -> Volcanic Winter Temperature Curve
        - "pressure_grid", "pressure", "shockwave" -> Atmospheric Pressure Shockwave Grid
    output_path:
        Destination video file path (.mp4).
    duration:
        Video duration in seconds (default: 5.0).
    fps:
        Frames per second (default: 30).
    width:
        Frame width in pixels (default: 1920).
    height:
        Frame height in pixels (default: 1080).
    ffmpeg:
        Optional path to FFmpeg binary.
    """
    key = broll_type.lower().strip()

    if key in ("volcano_map", "volcano", "seismic_map", "seismic"):
        return generate_volcano_map_video(
            output_path=output_path,
            duration=duration,
            fps=fps,
            width=width,
            height=height,
            ffmpeg=ffmpeg,
        )
    elif key in ("temperature_drop", "temperature_curve", "thermal_collapse", "temperature", "winter"):
        return generate_temperature_curve_video(
            output_path=output_path,
            duration=duration,
            fps=fps,
            width=width,
            height=height,
            ffmpeg=ffmpeg,
        )
    elif key in ("pressure_grid", "pressure", "shockwave", "isobars"):
        return generate_pressure_grid_video(
            output_path=output_path,
            duration=duration,
            fps=fps,
            width=width,
            height=height,
            ffmpeg=ffmpeg,
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
        # Fast 1.0-second 640x360 test clips
        volcano_out = test_dir / "volcano_test.mp4"
        v_res = generate_volcano_map_video(
            output_path=volcano_out,
            duration=1.0,
            fps=24,
            width=640,
            height=360,
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
        )
        assert t_res.is_file(), f"Temperature curve video was not created: {t_res}"
        assert t_res.stat().st_size > 5000, "Temperature curve video is unexpectedly small"

        # Test generic entry point
        broll_out = test_dir / "broll_test.mp4"
        b_res = generate_data_broll(
            broll_type="pressure_grid",
            output_path=broll_out,
            duration=1.0,
            fps=24,
            width=640,
            height=360,
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
