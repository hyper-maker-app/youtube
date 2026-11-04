"""Remotion Motion Graphics Bridge for Grok Cinematic Studio.

Executes broadcast-quality React / Remotion parametric motion graphics
compositions (Geospatial maps, radar overlays, HUD telemetry curves)
via headless Remotion CLI.

PURE ENGINE INVARIANT:
- SIFIR HARDCODE: No fixed scenarios, cities, events, or static text.
- 100% parametric: Drives templates strictly via JSON data payloads.
- Headless render: Generates 60 FPS 1920x1080 MP4 files for timeline assembly.
"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger("remotion_bridge")

# Root directory of the Remotion motion graphics project
_SERVICES_DIR = Path(__file__).resolve().parent
_ENGINE_DIR = _SERVICES_DIR.parent
MOTION_GRAPHICS_DIR = _ENGINE_DIR / "motion_graphics"

# Canonical template alias mapping
TEMPLATE_ALIASES: dict[str, str] = {
    "storm_map": "GeospatialStormMap",
    "storm-map": "GeospatialStormMap",
    "geospatial_storm_map": "GeospatialStormMap",
    "geospatial_map": "GeospatialStormMap",
    "radar": "GeospatialStormMap",
    "telemetry": "TelemetryCurve",
    "telemetry_curve": "TelemetryCurve",
    "telemetry-curve": "TelemetryCurve",
    "telemetry_hud": "TelemetryCurve",
    "temperature_curve": "TelemetryCurve",
    "volcano_map": "VolcanoSeismicMap",
    "volcano-map": "VolcanoSeismicMap",
    "volcano_seismic_map": "VolcanoSeismicMap",
    "seismic_map": "VolcanoSeismicMap",
}


def resolve_npx() -> str:
    """Resolve the path to the npx binary across platforms."""
    npx_bin = shutil.which("npx")
    if not npx_bin and os.name == "nt":
        npx_bin = shutil.which("npx.cmd")
    if not npx_bin:
        raise FileNotFoundError(
            "Node.js 'npx' executable could not be found. Please ensure Node.js is installed on PATH."
        )
    return npx_bin


def resolve_browser_executable() -> str | None:
    """Find installed Chrome or Edge executable to bypass downloading Chrome Headless Shell."""
    candidates = [
        os.getenv("REMOTION_BROWSER_EXECUTABLE"),
        os.getenv("PUPPETEER_EXECUTABLE_PATH"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        shutil.which("google-chrome"),
        shutil.which("chrome"),
        shutil.which("chromium"),
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return str(Path(c).resolve())
    return None


def resolve_template_name(template_name: str) -> str:
    """Resolve an incoming template name or alias to the registered Remotion Composition ID."""
    clean = template_name.strip()
    return TEMPLATE_ALIASES.get(clean.lower(), clean)


def validate_broll_payload(template_name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate production inputs using the same field contract as the TS renderer."""
    template = resolve_template_name(template_name)
    schemas = json.loads((MOTION_GRAPHICS_DIR / "payload_schema.json").read_text(encoding="utf-8"))
    if template not in schemas:
        raise ValueError(f"Unsupported motion graphics template: {template}")
    if not isinstance(payload, Mapping):
        raise ValueError("data_payload must be a JSON object")
    schema = schemas[template]
    data = dict(payload)
    finite = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    for key in schema['strings']:
        if not isinstance(data.get(key), str):
            raise ValueError(f"{template} data_payload requires string field '{key}'")
    for key in schema['numbers']:
        if not finite(data.get(key)):
            raise ValueError(f"{template} data_payload requires finite numeric field '{key}'")
    for key in schema['arrays']:
        if not isinstance(data.get(key), list):
            raise ValueError(f"{template} data_payload requires array field '{key}'")
    if schema.get('map'):
        if 'tileSource' in data and not isinstance(data['tileSource'], str):
            raise ValueError("tileSource must be a string")
        pan = data.get('cameraPan')
        if pan is not None and (not isinstance(pan, Mapping) or any(not finite(pan.get(key)) for key in ('deltaLat', 'deltaLon', 'zoomDelta'))):
            raise ValueError("cameraPan requires finite deltaLat, deltaLon and zoomDelta")
        center = data.get('center')
        if not isinstance(center, (list, tuple)) or len(center) != 2 or not all(finite(v) for v in center) or abs(center[0]) > 85.05112878 or abs(center[1]) > 180:
            raise ValueError("Map center must be valid [latitude, longitude]")
        if not finite(data.get('zoom')) or not 0 <= data['zoom'] <= 22:
            raise ValueError("Map zoom must be between 0 and 22")
    if template == 'TelemetryCurve':
        points = data['dataPoints']
        if len(points) < 2 or not all(finite(v) for v in points):
            raise ValueError("dataPoints requires at least two finite numbers")
        bounds = data.get('yRange')
        if bounds is not None and (not isinstance(bounds, (list, tuple)) or len(bounds) != 2 or not all(finite(v) for v in bounds) or bounds[1] <= bounds[0]):
            raise ValueError("yRange must be [min, max] with max > min")
    for key in ('metrics', 'summaryMetrics'):
        for item in data.get(key, []):
            if not isinstance(item, Mapping) or not isinstance(item.get('label'), str) or not isinstance(item.get('value'), (str, int, float)) or isinstance(item.get('value'), bool) or (isinstance(item.get('value'), (int, float)) and not finite(item['value'])):
                raise ValueError(f"{key} items require label and value")
    return data


def cache_map_tiles(payload: dict[str, Any], frame_count: int, width: int, height: int) -> dict[str, Any]:
    """Persist raster tiles and embed cached images so rendering is network independent."""
    import base64
    import hashlib
    import io
    from concurrent.futures import ThreadPoolExecutor
    from urllib.request import urlopen
    from PIL import Image

    source = payload.get('tileSource', 'esri_world_imagery')
    if source.startswith('data:'):
        return payload
    providers = json.loads((MOTION_GRAPHICS_DIR / 'tile_providers.json').read_text(encoding='utf-8'))
    source = providers.get(source, source)
    if not source.startswith(('http://', 'https://')):
        raise ValueError('tileSource must be a known provider, HTTP tile template or data URI')
    urls: set[str] = set()
    pan = payload.get('cameraPan') or {}
    for frame in range(frame_count):
        progress = frame / frame_count
        lat = max(-85.05112878, min(85.05112878, payload['center'][0] + pan.get('deltaLat', 0) * progress))
        lon = payload['center'][1] + pan.get('deltaLon', 0) * progress
        zoom = payload['zoom'] + pan.get('zoomDelta', 0) * progress
        tile_zoom = math.floor(zoom)
        if tile_zoom < 0 or tile_zoom > 22:
            raise ValueError('Animated map zoom must remain between 0 and 22')
        count = 2 ** tile_zoom
        tile_size = 256 * 2 ** (zoom - tile_zoom)
        px = (lon + 180) / 360 * count * tile_size
        sin_lat = math.sin(math.radians(lat))
        py = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * count * tile_size
        for x in range(math.floor((px - width / 2) / tile_size), math.floor((px + width / 2) / tile_size) + 1):
            for y in range(max(0, math.floor((py - height / 2) / tile_size)), min(count - 1, math.floor((py + height / 2) / tile_size)) + 1):
                urls.add(source.replace('{z}', str(tile_zoom)).replace('{x}', str(x % count)).replace('{y}', str(y)))
    cache_dir = Path(os.getenv('REMOTION_TILE_CACHE_DIR', str(_ENGINE_DIR.parent / 'artifacts' / 'cache' / 'tiles')))
    cache_dir.mkdir(parents=True, exist_ok=True)
    def load(url: str) -> tuple[str, str]:
        path = cache_dir / (hashlib.sha256(url.encode()).hexdigest() + '.png')
        if not path.is_file():
            with urlopen(url, timeout=20) as response:
                raw = response.read()
            image = Image.open(io.BytesIO(raw)).convert('RGB')
            encoded = io.BytesIO()
            image.save(encoded, format='PNG')
            # Atomic replace avoids partially written files across simultaneous renders.
            with tempfile.NamedTemporaryFile(dir=cache_dir, suffix='.tmp', delete=False) as temp:
                temp.write(encoded.getvalue())
                temp_name = temp.name
            os.replace(temp_name, path)
        return url, 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
    with ThreadPoolExecutor(max_workers=8) as executor:
        tiles = dict(executor.map(load, sorted(urls)))
    return {**payload, 'tileCache': tiles}


def render_remotion_broll(
    template_name: str,
    data_payload: Mapping[str, Any] | dict[str, Any],
    output_path: Path | str,
    width: int = 1920,
    height: int = 1080,
    fps: int = 60,
    duration_seconds: float = 8.0,
    entry_point: str = "src/index.ts",
    extra_args: list[str] | None = None,
) -> Path:
    """Render a Remotion motion graphics composition into a broadcast-standard MP4.

    Parameters
    ----------
    template_name:
        Composition ID (e.g. 'GeospatialStormMap', 'TelemetryCurve', 'VolcanoSeismicMap')
        or recognized alias ('storm_map', 'telemetry', 'volcano_map').
    data_payload:
        Parametric JSON data dictionary passed to the Remotion composition via `--props`.
    output_path:
        Target .mp4 file destination.
    width:
        Output frame width (default 1920).
    height:
        Output frame height (default 1080).
    fps:
        Output frame rate (default 60 FPS).
    duration_seconds:
        Video duration in seconds (default 8.0).
    entry_point:
        Relative path to Remotion entry point within motion_graphics directory (default: src/index.ts).
    extra_args:
        Optional additional CLI arguments forwarded to Remotion.

    Returns
    -------
    Path:
        Verified Path to the rendered MP4 file.

    Raises
    ------
    FileNotFoundError:
        If motion_graphics directory or npx cannot be resolved.
    RuntimeError:
        If Remotion CLI execution fails or produces an empty/invalid file.
    """
    if not MOTION_GRAPHICS_DIR.is_dir():
        raise FileNotFoundError(
            f"Remotion motion graphics directory not found at: {MOTION_GRAPHICS_DIR}"
        )

    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("duration_seconds must be finite and positive")
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in (width, height, fps)):
        raise ValueError("width, height and fps must be positive integers")
    data_payload = validate_broll_payload(template_name, data_payload)
    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    resolved_comp_id = resolve_template_name(template_name)
    duration_in_frames = max(1, int(round(duration_seconds * fps)))
    frame_range_arg = f"--frames=0-{duration_in_frames - 1}"
    if resolved_comp_id in ("GeospatialStormMap", "VolcanoSeismicMap"):
        data_payload = cache_map_tiles(data_payload, duration_in_frames, width, height)

    npx_bin = resolve_npx()

    # Write props to a temporary JSON file to avoid CLI argument escaping issues on Windows
    temp_props = tempfile.NamedTemporaryFile(
        mode="w",
        prefix=f"remotion_props_{resolved_comp_id}_",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    )
    try:
        json.dump(dict(data_payload), temp_props, ensure_ascii=False, indent=2)
        temp_props.flush()
        temp_props_path = Path(temp_props.name).resolve()
    finally:
        temp_props.close()

    cmd: list[str] = [
        npx_bin,
        "remotion",
        "render",
        entry_point,
        resolved_comp_id,
        str(out_file),
        f"--props={str(temp_props_path)}",
        frame_range_arg,
        f"--duration={duration_in_frames}",
        f"--width={width}",
        f"--height={height}",
        f"--fps={fps}",
        "--overwrite",
    ]

    browser_bin = resolve_browser_executable()
    if browser_bin:
        cmd.append(f"--browser-executable={browser_bin}")

    if extra_args:
        cmd.extend(extra_args)

    logger.info(
        f"Rendering Remotion B-Roll: {resolved_comp_id} -> {out_file.name} "
        f"({duration_seconds:.2f}s, {duration_in_frames} frames @ {fps}fps, {width}x{height})"
    )

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(MOTION_GRAPHICS_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if proc.returncode != 0:
            err_msg = (
                f"Remotion render failed with exit code {proc.returncode} for template '{resolved_comp_id}'.\n"
                f"Command: {' '.join(cmd)}\n"
                f"STDERR:\n{proc.stderr}\n"
                f"STDOUT:\n{proc.stdout}"
            )
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        if not out_file.is_file() or out_file.stat().st_size == 0:
            err_msg = (
                f"Remotion finished with code 0 but output file was not created or is empty: {out_file}\n"
                f"STDOUT:\n{proc.stdout}\n"
                f"STDERR:\n{proc.stderr}"
            )
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        logger.info(
            f"Successfully rendered Remotion B-Roll: {out_file} "
            f"({out_file.stat().st_size / 1024:.1f} KB)"
        )
        return out_file

    finally:
        # Clean up temporary props file
        try:
            if temp_props_path.is_file():
                temp_props_path.unlink(missing_ok=True)
        except Exception as cleanup_err:
            logger.debug(f"Failed to remove temp props file {temp_props_path}: {cleanup_err}")
