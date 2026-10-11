"""MCP server for inspecting video, audio, loudness (LUFS), freeze frames, and captions."""
from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path
from mcp.server.mcpserver import MCPServer
import config

mcp = MCPServer("youtube-media-inspector")
PROJECT_ROOT = Path(__file__).resolve().parent

def _resolve_path(target: str | Path) -> Path:
    p = Path(target)
    return p.resolve() if p.is_absolute() else (PROJECT_ROOT / p).resolve()

def _check_file(path: Path, target_str: str) -> dict | None:
    if not path.is_file():
        return {"error": f"File not found: {target_str}"}
    try:
        if path.stat().st_size == 0:
            return {"error": f"File is empty (0 bytes): {target_str}"}
    except (OSError, FileNotFoundError) as exc:
        return {"error": f"Could not access file {target_str}: {exc}"}
    return None

@mcp.tool()
def inspect_media(media_path: str = "", video_path: str = "") -> dict:
    """Probe a media file for resolution, aspect ratio (verifies 9:16 vertical), duration, fps, and codecs."""
    target_str = media_path or video_path
    if not target_str:
        return {"error": "Missing media_path or video_path parameter"}
    path = _resolve_path(target_str)
    err = _check_file(path, target_str)
    if err:
        return err

    ffmpeg = config.resolve_ffmpeg()
    # Run ffprobe if available or ffmpeg -i probe
    probe_cmd = [
        ffmpeg, "-hide_banner", "-i", str(path), "-f", "null", "-"
    ]
    proc = subprocess.run(probe_cmd, capture_output=True, text=True, check=False)
    stderr = proc.stderr

    duration_m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", stderr)
    video_m = re.search(r"Stream #\d+:\d+.*Video:.*,\s*(\d+)x(\d+)", stderr)
    fps_m = re.search(r"([\d.]+)\s*fps", stderr)
    audio_m = re.search(r"Stream #\d+:\d+.*Audio:\s*(\w+)", stderr)

    if proc.returncode != 0 and not video_m and not audio_m:
        last_err = stderr.strip().splitlines()[-1] if stderr.strip() else "unreadable media"
        return {"error": f"Media probing failed: {last_err}"}

    duration_sec = 0.0
    if duration_m:
        h, m, s = duration_m.groups()
        duration_sec = int(h) * 3600 + int(m) * 60 + float(s)

    width, height = (int(video_m.group(1)), int(video_m.group(2))) if video_m else (0, 0)
    is_vertical_9_16 = (width > 0 and height > 0) and abs((height / width) - (16.0 / 9.0)) < 0.05

    return {
        "file": str(path),
        "exists": True,
        "duration_sec": duration_sec,
        "width": width,
        "height": height,
        "aspect_ratio_9_16": is_vertical_9_16,
        "fps": float(fps_m.group(1)) if fps_m else None,
        "has_audio": bool(audio_m),
        "audio_codec": audio_m.group(1) if audio_m else None,
    }

@mcp.tool()
def measure_audio_loudness(media_path: str = "", audio_path: str = "") -> dict:
    """Measure integrated loudness (LUFS), true peak (dBTP), and loudness range (LRA) using EBU R128."""
    target_str = media_path or audio_path
    if not target_str:
        return {"error": "Missing media_path or audio_path parameter"}
    path = _resolve_path(target_str)
    err = _check_file(path, target_str)
    if err:
        return err

    ffmpeg = config.resolve_ffmpeg()
    cmd = [ffmpeg, "-hide_banner", "-i", str(path), "-af", "ebur128=framelog=verbose", "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    stderr = proc.stderr

    i_m = re.search(r"\s*I:\s*([-\d.]+)\s*LUFS", stderr)
    tp_m = re.search(r"\s*Peak:\s*([-\d.]+)\s*dBFS", stderr)
    lra_m = re.search(r"\s*LRA:\s*([-\d.]+)\s*LU", stderr)

    if proc.returncode != 0 or not i_m:
        last_err = stderr.strip().splitlines()[-1] if stderr.strip() else "no audio stream found"
        return {"error": f"Audio loudness measurement failed: {last_err}"}

    integrated = float(i_m.group(1)) if i_m else None
    return {
        "file": str(path),
        "integrated_lufs": integrated,
        "true_peak_db": float(tp_m.group(1)) if tp_m else None,
        "lra_lu": float(lra_m.group(1)) if lra_m else None,
        "optimal_for_shorts": bool(integrated and -16.0 <= integrated <= -13.0),
    }

@mcp.tool()
def detect_black_or_freeze(video_path: str = "", media_path: str = "") -> dict:
    """Detect accidental black frames or freeze frames in a rendered short."""
    target_str = video_path or media_path
    if not target_str:
        return {"error": "Missing video_path or media_path parameter"}
    path = _resolve_path(target_str)
    err = _check_file(path, target_str)
    if err:
        return err

    ffmpeg = config.resolve_ffmpeg()
    cmd = [
        ffmpeg, "-hide_banner", "-i", str(path),
        "-vf", "freezedetect=n=0.003:d=1.6,blackdetect=d=0.5:pix_th=0.10",
        "-f", "null", "-"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    stderr = proc.stderr

    if proc.returncode != 0:
        last_err = stderr.strip().splitlines()[-1] if stderr.strip() else "unknown error"
        return {"error": f"FFmpeg freeze/black detection failed: {last_err}"}

    freezes = re.findall(r"freeze_start:\s*([\d.]+).*?freeze_duration:\s*([\d.]+)", stderr)
    blacks = re.findall(r"black_start:\s*([\d.]+).*?black_duration:\s*([\d.]+)", stderr)

    return {
        "file": str(path),
        "freeze_events": [{"start": float(s), "duration": float(d)} for s, d in freezes],
        "black_events": [{"start": float(s), "duration": float(d)} for s, d in blacks],
        "has_defect": bool(freezes or blacks),
    }

@mcp.tool()
def analyze_audio_spectrum(media_path: str = "", audio_path: str = "") -> dict:
    """Analyze audio spectrum, dynamic range, RMS statistics, and clipping risk using FFmpeg astats."""
    target_str = media_path or audio_path
    if not target_str:
        return {"error": "Missing media_path or audio_path parameter"}
    path = _resolve_path(target_str)
    err = _check_file(path, target_str)
    if err:
        return err

    ffmpeg = config.resolve_ffmpeg()
    cmd = [
        ffmpeg, "-hide_banner", "-i", str(path),
        "-af", "astats=metadata=1:reset=0",
        "-f", "null", "-"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    stderr = proc.stderr

    def _extract_float(pattern: str, text: str) -> float | None:
        m = re.search(pattern, text)
        return float(m.group(1)) if m else None

    peak_db = _extract_float(r"Peak level dB:\s*([-\d.]+)", stderr)
    rms_db = _extract_float(r"RMS level dB:\s*([-\d.]+)", stderr)
    rms_peak_db = _extract_float(r"RMS peak dB:\s*([-\d.]+)", stderr)
    flat_factor = _extract_float(r"Flat factor:\s*([-\d.]+)", stderr)
    entropy = _extract_float(r"Entropy:\s*([-\d.]+)", stderr)

    if proc.returncode != 0 or (peak_db is None and rms_db is None):
        last_err = stderr.strip().splitlines()[-1] if stderr.strip() else "no audio stream found"
        return {"error": f"FFmpeg audio spectrum analysis failed: {last_err}"}

    has_clipping = bool(flat_factor is not None and flat_factor > 0.0001)
    is_broadcast_safe = bool(
        peak_db is not None and peak_db <= -0.5
        and not has_clipping
        and (rms_db is not None and -26.0 <= rms_db <= -14.0)
    )

    return {
        "file": str(path),
        "peak_level_db": peak_db,
        "rms_level_db": rms_db,
        "rms_peak_db": rms_peak_db,
        "flat_factor": flat_factor,
        "entropy": entropy,
        "clipping_detected": has_clipping,
        "broadcast_dynamics_safe": is_broadcast_safe,
    }

@mcp.tool()
def analyze_video_stability(video_path: str = "", media_path: str = "", sample_seconds: float = 12.0) -> dict:
    """Analyze video motion smoothness, temporal consistency, and detect micro-stutters or abrupt jitter."""
    target_str = video_path or media_path
    if not target_str:
        return {"error": "Missing video_path or media_path parameter"}
    path = _resolve_path(target_str)
    err = _check_file(path, target_str)
    if err:
        return err

    ffmpeg = config.resolve_ffmpeg()
    dur_arg = ["-t", f"{sample_seconds:.1f}"] if sample_seconds > 0 else []
    cmd = [
        ffmpeg, "-hide_banner", *dur_arg, "-i", str(path),
        "-vf", "scale=270:480,freezedetect=n=0.002:d=0.8,blackdetect=d=0.3:pix_th=0.10",
        "-f", "null", "-"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    stderr = proc.stderr

    if proc.returncode != 0:
        last_err = stderr.strip().splitlines()[-1] if stderr.strip() else "unknown error"
        return {"error": f"FFmpeg video analysis failed: {last_err}"}

    freezes = re.findall(r"freeze_start:\s*([\d.]+).*?freeze_duration:\s*([\d.]+)", stderr)
    blacks = re.findall(r"black_start:\s*([\d.]+).*?black_duration:\s*([\d.]+)", stderr)

    fps_m = re.search(r"([\d.]+)\s*fps", stderr)
    if fps_m is None and not freezes and not blacks:
        return {"error": "No video stream found or video analysis failed"}
    fps = float(fps_m.group(1)) if fps_m else 30.0

    penalty = len(freezes) * 20 + len(blacks) * 30
    stability_score = max(0, 100 - penalty)
    is_stable = stability_score >= 80 and not blacks

    return {
        "file": str(path),
        "analyzed_duration_sec": sample_seconds,
        "fps": fps,
        "freeze_count": len(freezes),
        "black_count": len(blacks),
        "stability_score": stability_score,
        "is_smooth_and_stable": is_stable,
    }

if __name__ == "__main__":
    mcp.run()
