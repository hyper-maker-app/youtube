"""Grok Imagine Cinematic Studio CLI â€” Remotion Motion Graphics Commands.

Provides independent testing, previewing, and headless rendering of broadcast-standard
Remotion motion graphics B-Roll clips (1920x1080 @ 60 FPS):
- `motion-graphics storm-map`: Geospatial multi-spectral storm / radar HUD
- `motion-graphics telemetry`: Tactical telemetry HUD curve / threshold decay
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

_TOOLS = Path(__file__).resolve().parents[1]
_ROOT = _TOOLS.parent

# Ensure root and engine are on sys.path
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "engine") not in sys.path:
    sys.path.insert(0, str(_ROOT / "engine"))
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from engine.services.remotion_bridge import render_remotion_broll  # noqa: E402

console = Console()
logger = logging.getLogger("cli_motion_commands")


def _load_props(
    props_file: Optional[Path] = None,
    props_json: Optional[str] = None,
    base_props: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Helper to merge props from file, inline JSON, and overrides (Zero Hardcode)."""
    payload: dict[str, Any] = {}
    if props_file:
        file_path = Path(props_file)
        if not file_path.is_file():
            console.print(f"[bold red]Error:[/] Props file not found: {file_path}")
            raise typer.Exit(1)
        try:
            file_data = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(file_data, dict):
                raise ValueError("Props must be a JSON object")
            payload.update(file_data)
        except Exception as exc:
            console.print(f"[bold red]Error parsing props file:[/] {exc}")
            raise typer.Exit(1)

    if props_json:
        try:
            inline_data = json.loads(props_json)
            if not isinstance(inline_data, dict):
                raise ValueError("Props must be a JSON object")
            payload.update(inline_data)
        except Exception as exc:
            console.print(f"[bold red]Error parsing inline JSON props:[/] {exc}")
            raise typer.Exit(1)

    payload.update(base_props or {})
    return payload


def storm_map(
    output: Path = typer.Option(
        Path("artifacts/motion_graphics/storm_map.mp4"),
        "--output",
        "-o",
        help="Target MP4 file output path",
    ),
    duration: float = typer.Option(
        8.0,
        "--duration",
        "-d",
        help="Composition duration in seconds (default: 8.0s)",
    ),
    fps: int = typer.Option(
        60,
        "--fps",
        help="Frames per second (broadcast standard: 60)",
    ),
    width: int = typer.Option(
        1920,
        "--width",
        help="Render width in pixels (default: 1920)",
    ),
    height: int = typer.Option(
        1080,
        "--height",
        help="Render height in pixels (default: 1080)",
    ),
    title: Optional[str] = typer.Option(
        None,
        "--title",
        help="HUD title text (e.g. 'HURRICANE IONIC CELL RECON')",
    ),
    subtitle: Optional[str] = typer.Option(
        None,
        "--subtitle",
        help="HUD subtitle text (e.g. 'GOES-18 SATELLITE MULTI-SPECTRAL RADAR')",
    ),
    classification: Optional[str] = typer.Option(
        None,
        "--classification",
        help="Security/classification banner text",
    ),
    event_count: Optional[int] = typer.Option(
        None,
        "--event-count",
        "--events",
        help="Detected event discharge counter",
    ),
    props_file: Optional[Path] = typer.Option(
        None,
        "--props-file",
        "-p",
        help="Complete JSON payload matching engine/motion_graphics/payload_schema.json",
    ),
    props_json: Optional[str] = typer.Option(
        None,
        "--props",
        help="Complete JSON payload; no fictional default data is supplied",
    ),
) -> None:
    """Render a broadcast Geospatial Storm Map B-Roll video via Remotion (60 FPS)."""
    overrides: dict[str, Any] = {}
    if title:
        overrides["title"] = title
    if subtitle:
        overrides["subtitle"] = subtitle
    if classification:
        overrides["classification"] = classification
    if event_count is not None:
        overrides["eventCount"] = event_count

    data_payload = _load_props(props_file, props_json, overrides)

    console.print(
        Panel(
            f"[bold cyan]Rendering Remotion Motion Graphics:[/] GeospatialStormMap\n"
            f"[dim]Output:[/] [green]{output}[/]\n"
            f"[dim]Dimensions:[/] {width}x{height} @ {fps} FPS, {duration:.1f}s",
            title="[bold yellow]Remotion Engine[/]",
            border_style="cyan",
        )
    )

    try:
        out_path = render_remotion_broll(
            template_name="GeospatialStormMap",
            data_payload=data_payload,
            output_path=output,
            width=width,
            height=height,
            fps=fps,
            duration_seconds=duration,
        )

        size_kb = out_path.stat().st_size / 1024
        console.print(f"[bold green]âœ“ Remotion render successful:[/] {out_path} ({size_kb:.1f} KB)")
    except Exception as exc:
        console.print(f"[bold red]âœ— Remotion render failed:[/] {exc}")
        raise typer.Exit(1)


def telemetry(
    output: Path = typer.Option(
        Path("artifacts/motion_graphics/telemetry.mp4"),
        "--output",
        "-o",
        help="Target MP4 file output path",
    ),
    duration: float = typer.Option(
        6.0,
        "--duration",
        "-d",
        help="Composition duration in seconds (default: 6.0s)",
    ),
    fps: int = typer.Option(
        60,
        "--fps",
        help="Frames per second (broadcast standard: 60)",
    ),
    width: int = typer.Option(
        1920,
        "--width",
        help="Render width in pixels (default: 1920)",
    ),
    height: int = typer.Option(
        1080,
        "--height",
        help="Render height in pixels (default: 1080)",
    ),
    metric_name: Optional[str] = typer.Option(
        None,
        "--metric-name",
        "-m",
        help="Telemetry metric name (e.g. 'ATMOSPHERIC TEMPERATURE CRITICAL DECAY')",
    ),
    unit: Optional[str] = typer.Option(
        None,
        "--unit",
        "-u",
        help="Telemetry measurement unit (e.g. 'Â°C', 'hPa', 'dB')",
    ),
    threshold: Optional[float] = typer.Option(
        None,
        "--threshold",
        "-t",
        help="Critical alarm threshold value",
    ),
    props_file: Optional[Path] = typer.Option(
        None,
        "--props-file",
        "-p",
        help="Complete JSON payload matching engine/motion_graphics/payload_schema.json",
    ),
    props_json: Optional[str] = typer.Option(
        None,
        "--props",
        help="Complete JSON payload; no fictional default data is supplied",
    ),
) -> None:
    """Render a tactical Telemetry Curve HUD B-Roll video via Remotion (60 FPS)."""
    overrides: dict[str, Any] = {}
    if metric_name:
        overrides["metricName"] = metric_name
    if unit:
        overrides["unit"] = unit
    if threshold is not None:
        overrides["thresholdValue"] = threshold

    data_payload = _load_props(props_file, props_json, overrides)

    console.print(
        Panel(
            f"[bold cyan]Rendering Remotion Motion Graphics:[/] TelemetryCurve\n"
            f"[dim]Output:[/] [green]{output}[/]\n"
            f"[dim]Dimensions:[/] {width}x{height} @ {fps} FPS, {duration:.1f}s",
            title="[bold yellow]Remotion Engine[/]",
            border_style="cyan",
        )
    )

    try:
        out_path = render_remotion_broll(
            template_name="TelemetryCurve",
            data_payload=data_payload,
            output_path=output,
            width=width,
            height=height,
            fps=fps,
            duration_seconds=duration,
        )

        size_kb = out_path.stat().st_size / 1024
        console.print(f"[bold green]âœ“ Remotion render successful:[/] {out_path} ({size_kb:.1f} KB)")
    except Exception as exc:
        console.print(f"[bold red]âœ— Remotion render failed:[/] {exc}")
        raise typer.Exit(1)


def render(
    template: str = typer.Argument(..., help="Composition ID or alias: storm_map, telemetry, volcano_map"),
    props_file: Optional[Path] = typer.Option(None, "--props-file", "-p", help="Complete payload matching engine/motion_graphics/payload_schema.json"),
    props_json: Optional[str] = typer.Option(None, "--props", help="Complete JSON payload; all scenario values must be supplied"),
    output: Path = typer.Option(..., "--output", "-o"),
    duration: float = typer.Option(8.0, "--duration", "-d", min=0.01),
) -> None:
    """Render any registered composition with explicit scenario data (1920x1080, 60 FPS)."""
    try:
        payload = _load_props(props_file, props_json)
        result = render_remotion_broll(template, payload, output, duration_seconds=duration)
        console.print(f"[green]Rendered:[/] {result}")
    except Exception as exc:
        console.print(f"[red]Render failed:[/] {exc}")
        raise typer.Exit(1)


def register(app: typer.Typer) -> None:
    """Register motion-graphics subcommands onto Typer."""
    app.command("render", help="Render any composition with a complete JSON payload")(render)
    app.command("storm-map", help="Render Remotion Geospatial Storm Map (60 FPS)")(storm_map)
    app.command("telemetry", help="Render Remotion Telemetry HUD Curve (60 FPS)")(telemetry)
