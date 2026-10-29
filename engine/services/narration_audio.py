"""Decode and verify provider audio before concatenating canonical PCM samples."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import wave

from providers.base import ProviderError


def command(args: list) -> str:
    result = subprocess.run(list(map(str, args)), capture_output=True)
    if result.returncode:
        raise ProviderError("Narration media decode/probe failed; repair audio dependency")
    return result.stdout.decode("utf-8", errors="replace")


def probe_audio(path: Path) -> dict:
    import config
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as source:
                rate, channels, frames = source.getframerate(), source.getnchannels(), source.getnframes()
                if not rate or not frames:
                    raise ValueError()
                sample_width = source.getsampwidth()
                codec = "pcm_s16le" if sample_width == 2 else f"pcm_s{sample_width * 8}"
                return {"duration": frames / rate, "codec": codec, "sample_rate": rate,
                        "channels": channels, "container": "wav"}
        except (wave.Error, OSError, ValueError):
            raise ProviderError("Narration audio probe missing or invalid") from None
    # Use the ffprobe sibling shipped with the selected ffmpeg when present.
    ffmpeg = Path(config.resolve_ffmpeg())
    sibling = ffmpeg.with_name("ffprobe.exe" if ffmpeg.suffix == ".exe" else "ffprobe")
    executable = str(sibling) if sibling.is_file() else "ffprobe"
    try:
        payload = json.loads(command([executable, "-v", "error", "-show_streams", "-show_format", "-of", "json", path]))
        streams = [s for s in payload["streams"] if s["codec_type"] == "audio"]
        if len(streams) != 1:
            raise ValueError()
        stream = streams[0]
        duration = float(payload["format"].get("duration", stream.get("duration", 0)))
        if not 0 < duration < float("inf"):
            raise ValueError()
        return {"duration": duration, "codec": stream["codec_name"],
                "sample_rate": int(stream["sample_rate"]), "channels": int(stream["channels"]),
                "container": payload["format"]["format_name"]}
    except (KeyError, TypeError, ValueError, OSError):
        raise ProviderError("Narration audio probe missing or invalid") from None


def assemble(parts: list[Path], target: Path, directory: Path) -> dict:
    import config
    pcm = directory / "canonical.wav"
    with wave.open(str(pcm), "wb") as output:
        output.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        for i, part in enumerate(parts):
            measured = probe_audio(part)
            if measured["codec"] not in {"pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_s8"}:
                raise ProviderError("Provider audio is not a supported decoded PCM stream")
            decoded = directory / f"decoded{i}.wav"
            command([config.resolve_ffmpeg(), "-v", "error", "-y", "-i", part, "-map", "0:a:0",
                     "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", decoded])
            with wave.open(str(decoded), "rb") as source:
                output.writeframes(source.readframes(source.getnframes()))
    if target.suffix.lower() == ".wav":
        codec = ["-c:a", "pcm_s16le"]
    elif target.suffix.lower() == ".mp3":
        codec = ["-c:a", "libmp3lame", "-b:a", "192k"]
    else:
        raise ProviderError("Narration destination must explicitly select WAV or MP3")
    command([config.resolve_ffmpeg(), "-v", "error", "-y", "-i", pcm, *codec, target])
    return probe_audio(target)
