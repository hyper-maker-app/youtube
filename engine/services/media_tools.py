"""Discover locally installed FFmpeg companion tools without changing PATH."""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def find_ffprobe() -> str | None:
    override = os.getenv("FFPROBE_BINARY")
    if override:
        if not Path(override).is_file():
            raise ValueError("FFPROBE_BINARY does not point to a file")
        return override
    found = shutil.which("ffprobe")
    if found:
        return found
    ffmpeg = os.getenv("FFMPEG_BINARY") or shutil.which("ffmpeg")
    if ffmpeg:
        sibling = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
        if sibling.is_file():
            return str(sibling)
    local = os.getenv("LOCALAPPDATA")
    if os.name == "nt" and local:
        packages = Path(local) / "Microsoft" / "WinGet" / "Packages"
        candidates = sorted(packages.glob("Gyan.FFmpeg_*/ffmpeg-*/bin/ffprobe.exe"), reverse=True)
        if candidates:
            return str(candidates[0])
    return None
