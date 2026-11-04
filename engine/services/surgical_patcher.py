"""Bounded, non-destructive block replacement and media validation."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


class PatchError(RuntimeError):
    """Raised when a replacement cannot be safely assembled."""


@dataclass(frozen=True)
class MediaSignature:
    duration: float
    video_codec: str
    width: int
    height: int
    pixel_format: str
    frame_rate: str
    time_base: str
    has_audio: bool
    audio_codec: str | None


def _probe(path: Path, executable: str | None = None) -> dict[str, Any]:
    binary = executable or shutil.which("ffprobe")
    if not binary:
        raise PatchError("ffprobe is required for surgical media validation")
    result = subprocess.run(
        [binary, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    if result.returncode != 0:
        raise PatchError("ffprobe failed for surgical media validation")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PatchError("ffprobe returned malformed JSON") from exc


def media_signature(path: str | Path, *, probe: Callable[[Path], dict[str, Any]] | None = None) -> MediaSignature:
    source = Path(path)
    if not source.is_file() or source.stat().st_size <= 0:
        raise PatchError(f"Media file missing or empty: {source}")
    payload = (probe or _probe)(source)
    streams = payload.get("streams") or []
    videos = [s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")]
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    if len(videos) != 1:
        raise PatchError(f"Expected exactly one video stream: {source.name}")
    video = videos[0]
    duration = float(video.get("duration") or payload.get("format", {}).get("duration") or 0)
    if duration <= 0:
        raise PatchError(f"Media duration is unavailable: {source.name}")
    return MediaSignature(
        duration, str(video.get("codec_name", "")), int(video.get("width", 0)), int(video.get("height", 0)),
        str(video.get("pix_fmt", "")), str(video.get("avg_frame_rate", "")), str(video.get("time_base", "")),
        bool(audios), str(audios[0].get("codec_name")) if audios else None,
    )


def _compatible(expected: MediaSignature, replacement: MediaSignature, tolerance: float = 1 / 30) -> None:
    fields = ("video_codec", "width", "height", "pixel_format", "frame_rate", "time_base", "has_audio")
    mismatches = [field for field in fields if getattr(expected, field) != getattr(replacement, field)]
    if mismatches:
        raise PatchError("Replacement media is incompatible: " + ", ".join(mismatches))
    if abs(expected.duration - replacement.duration) > tolerance:
        raise PatchError("Replacement duration differs from target block")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _concat_line(path: Path) -> str:
    escaped = path.resolve().as_posix().replace("'", "'\\''")
    return f"file '{escaped}'"


def surgically_splice_timeline(
    master_video_path: str | Path,
    replacement_blocks: Mapping[int, str | Path],
    all_block_paths: Iterable[str | Path],
    output_path: str | Path,
    *,
    master_audio_path: str | Path | None = None,
    captions_path: str | Path | None = None,
    ffmpeg: str | None = None,
    probe: Callable[[Path], dict[str, Any]] | None = None,
    runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
) -> Path:
    """Replace selected blocks, reassemble, then validate the resulting media."""
    master = Path(master_video_path)
    blocks = [Path(item) for item in all_block_paths]
    output = Path(output_path)
    if not master.is_file() or not blocks:
        raise PatchError("Master video and block list are required")
    if any(not path.is_file() or path.stat().st_size <= 0 for path in blocks):
        raise PatchError("Every timeline block must exist and be non-empty")
    if captions_path is not None and not Path(captions_path).is_file():
        raise PatchError("Explicit captions file is missing")
    if any(index < 0 or index >= len(blocks) for index in replacement_blocks):
        raise PatchError("Replacement block index is outside the timeline")
    if not replacement_blocks:
        raise PatchError("At least one replacement block is required")
    original_hashes = {index: _hash(path) for index, path in enumerate(blocks) if index not in replacement_blocks}
    signatures = [media_signature(path, probe=probe) for path in blocks]
    updated = list(blocks)
    for index, replacement in replacement_blocks.items():
        replacement_path = Path(replacement)
        replacement_signature = media_signature(replacement_path, probe=probe)
        _compatible(signatures[index], replacement_signature)
        updated[index] = replacement_path
    for index, digest in original_hashes.items():
        if _hash(blocks[index]) != digest:
            raise PatchError("Untouched block changed during patch preparation")

    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = ffmpeg or shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise PatchError("ffmpeg is required for surgical splicing")
    audio = Path(master_audio_path) if master_audio_path else master
    if not audio.is_file():
        raise PatchError("Master audio or master video is missing")
    with tempfile.TemporaryDirectory(prefix="surgical_splice_", dir=output.parent) as temp_dir:
        concat_file = Path(temp_dir) / "blocks.txt"
        concat_file.write_text("\n".join(_concat_line(path) for path in updated) + "\n", encoding="utf-8")
        filters = ["[0:v]fps=30,format=yuv420p[v]"]
        current = "[v]"
        if captions_path and Path(captions_path).is_file():
            subtitle = Path(captions_path).resolve().as_posix().replace(":", "\\:").replace("'", "\\'")
            filters.append(f"{current}subtitles='{subtitle}'[vs]")
            current = "[vs]"
        args = [
            ffmpeg_bin, "-y", "-hide_banner", "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-i", str(audio), "-filter_complex", ";".join(filters), "-map", current, "-map", "1:a?",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(output),
        ]
        result = (runner or _run)(args)
    if result.returncode != 0 or not output.is_file() or output.stat().st_size <= 0:
        raise PatchError("FFmpeg surgical splice failed")
    output_sig = media_signature(output, probe=probe)
    master_sig = media_signature(master, probe=probe)
    if abs(output_sig.duration - master_sig.duration) > 0.05:
        raise PatchError("Spliced output duration differs from master")
    if master_sig.has_audio and not output_sig.has_audio:
        raise PatchError("Spliced output lost the master audio stream")
    if master_sig.has_audio and output_sig.audio_codec != master_sig.audio_codec:
        raise PatchError("Spliced output audio codec differs from master")
    return output


def execute_selective_patch(
    audit_report: Any,
    block_paths: Iterable[str | Path],
    render_block: Callable[[str, Any, int], str | Path],
    splice: Callable[[Mapping[int, str | Path]], Path],
    *,
    max_passes: int = 1,
    reaudit: Callable[[Path], Any] | None = None,
    block_id_for_path: Callable[[Path], str] | None = None,
) -> Path | None:
    """Run at most two patch passes and dispatch only flagged block IDs."""
    if max_passes < 0 or max_passes > 2:
        raise ValueError("max_passes must be between 0 and 2")
    paths = list(block_paths)
    current = None
    report = audit_report
    get_block_id = block_id_for_path or (lambda path: Path(path).stem)
    for pass_index in range(max_passes + 1):
        patch_ids = tuple(getattr(report, "patch_blocks", ()))
        if not patch_ids:
            return current
        if pass_index == max_passes:
            raise PatchError("Patch budget exhausted before audit passed")
        replacements: dict[int, str | Path] = {}
        by_id = {getattr(block, "block_id"): block for block in getattr(report, "blocks", ())}
        for index, path in enumerate(paths):
            block_id = get_block_id(path)
            if block_id in patch_ids:
                replacements[index] = render_block(block_id, by_id[block_id], pass_index)
        if set(replacements) != {index for index, path in enumerate(paths) if get_block_id(path) in patch_ids}:
            raise PatchError("Audit block IDs do not map to supplied block paths")
        current = splice(replacements)
        if reaudit is None:
            return current
        report = reaudit(current)
    return current


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
