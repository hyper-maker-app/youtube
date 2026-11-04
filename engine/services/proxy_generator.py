"""Build small, timecoded audit proxies without embedding creative direction."""

from __future__ import annotations

import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence



@dataclass(frozen=True)
class ProxyScene:
    """Timeline metadata used only to identify an audit block."""

    block_id: str
    start: float
    end: float
    index: int


def _ass_time(seconds: float) -> str:
    if seconds < 0:
        raise ValueError("Timeline time cannot be negative")
    centiseconds = int(round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, centis = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _scene_from_mapping(item: dict[str, Any], index: int, cursor: float) -> ProxyScene:
    block_id = item.get("block_id", item.get("scene_id", item.get("id")))
    if not isinstance(block_id, str) or not block_id.strip():
        raise ValueError("Every proxy scene requires a non-empty block_id")
    start = float(item.get("start", item.get("audio_t0", cursor)))
    end = float(item.get("end", item.get("audio_t1", start + item.get("duration", 0))))
    if start < 0 or end <= start:
        raise ValueError(f"Invalid time range for proxy block {block_id!r}")
    return ProxyScene(block_id.strip(), start, end, index)


def normalize_scenes(scenes: Sequence[ProxyScene | dict[str, Any]]) -> list[ProxyScene]:
    """Normalize a manifest while preserving its supplied block identity."""
    normalized: list[ProxyScene] = []
    cursor = 0.0
    seen: set[str] = set()
    for index, item in enumerate(scenes):
        scene = item if isinstance(item, ProxyScene) else _scene_from_mapping(item, index, cursor)
        if scene.block_id in seen:
            raise ValueError(f"Duplicate proxy block_id: {scene.block_id}")
        if scene.start < cursor - 0.001:
            raise ValueError("Proxy scene ranges must be ordered and non-overlapping")
        seen.add(scene.block_id)
        normalized.append(scene)
        cursor = scene.end
    return normalized


def generate_proxy_hud_ass(
    scenes: Sequence[ProxyScene | dict[str, Any]],
    output_ass: str | Path,
    *,
    aspect_ratio: str = "16:9",
) -> Path:
    """Write an identifier/timecode HUD; no narrative or style text is generated."""
    if aspect_ratio not in {"16:9", "9:16"}:
        raise ValueError("aspect_ratio must be 16:9 or 9:16")
    normalized = normalize_scenes(scenes)
    output = Path(output_ass)
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height = (854, 480) if aspect_ratio == "16:9" else (480, 854)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: AuditHUD,Arial,14,&H00FFFFFF,&H000000FF,&H00000000,&H90000000,0,0,0,0,100,100,0,0,3,1,0,7,12,12,10,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    total = len(normalized)
    for scene in normalized:
        label = f"BLOCK {scene.index + 1:02d}/{total:02d} [ID: {scene.block_id}]"
        label += f" | RANGE: {_ass_time(scene.start)}-{_ass_time(scene.end)}"
        lines.append(
            f"Dialogue: 0,{_ass_time(scene.start)},{_ass_time(scene.end)},AuditHUD,,0,0,0,,{label}"
        )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _resolve_ffmpeg() -> str:
    binary = shutil.which("ffmpeg")
    if binary:
        return binary
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError("ffmpeg is required for audit proxy generation") from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def build_audit_proxy(
    source_path: str | Path,
    output_path: str | Path,
    scenes: Sequence[ProxyScene | dict[str, Any]],
    *,
    ffmpeg: str | None = None,
    hud_path: str | Path | None = None,
    runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
    crf: int = 28,
    aspect_ratio: str = "16:9",
) -> Path:
    """Downscale a master into a constant-rate, HUD-labelled audit proxy."""
    if aspect_ratio not in {"16:9", "9:16"}:
        raise ValueError("aspect_ratio must be 16:9 or 9:16")
    source = Path(source_path)
    output = Path(output_path)
    if not source.is_file():
        raise FileNotFoundError(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    hud = Path(hud_path) if hud_path else output.with_suffix(".ass")
    generate_proxy_hud_ass(scenes, hud, aspect_ratio=aspect_ratio)
    ffmpeg_bin = ffmpeg or _resolve_ffmpeg()
    width, height = (854, 480) if aspect_ratio == "16:9" else (480, 854)
    hud_filter_path = hud.resolve().as_posix().replace("\\", "/").replace(":", "\\:")
    filter_graph = (
        f"[0:v]fps=24,scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,subtitles='{hud_filter_path}'[v]"
    )
    args = [
        ffmpeg_bin, "-y", "-hide_banner", "-i", str(source),
        "-filter_complex", filter_graph, "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
        "-g", "48", "-keyint_min", "24", "-bf", "2", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "64k", "-ac", "1", "-ar", "44100",
        "-movflags", "+faststart", str(output),
    ]
    result = (runner or _run)(args)
    if result.returncode != 0:
        raise RuntimeError("Audit proxy generation failed")
    if not output.is_file() or output.stat().st_size <= 0:
        raise RuntimeError("Audit proxy generation produced no media output")
    return output
