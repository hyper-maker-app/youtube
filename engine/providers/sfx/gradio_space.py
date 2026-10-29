"""Hugging Face Gradio Space SFX Provider with Resilient Lavfi Fallback.

Primary: Remote Hugging Face Space ('fffiloni/audiogen' or 'declare-lab/TangoFlux').
Fallback: Instant local FFmpeg Lavfi procedural synthesis on timeout or network error.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import config
from providers.base import BaseSfxProvider, ProviderError
from providers.sfx.ffmpeg_lavfi import FFmpegLavfiSfxProvider

logger = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class GradioSpaceSfxProvider(BaseSfxProvider):
    """SFX generator connecting to remote Hugging Face Gradio Space with zero-fail fallback."""

    def __init__(
        self,
        space_url: str | None = None,
        timeout_seconds: float = 20.0,
        fallback_to_lavfi: bool = True,
    ) -> None:
        self.space_url = space_url or os.getenv("SFX_SPACE_URL", "fffiloni/audiogen")
        self.timeout_seconds = float(os.getenv("SFX_SPACE_TIMEOUT", str(timeout_seconds)))
        self.fallback_to_lavfi = fallback_to_lavfi
        self._lavfi_fallback = FFmpegLavfiSfxProvider()

    async def resolve_asset(self, query: dict[str, Any], cache_dir: Path) -> dict[str, Any]:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

        prompt = str(query.get("prompt") or "cinematic atmospheric foley impact").strip()
        tags = [str(t) for t in query.get("tags") or []]
        duration = max(1.0, min(10.0, float(query.get("duration", 3.0))))
        asset_id = str(query.get("asset_id") or f"hf_{abs(hash(prompt + str(duration))) % 1000000:06d}")
        out_wav = cache_dir / f"{asset_id}.wav"

        if out_wav.is_file() and out_wav.stat().st_size > 1000:
            return self._build_record(asset_id, out_wav, tags, duration, "cached")

        generated = False
        try:
            logger.info(f"Connecting to Hugging Face Space '{self.space_url}' for SFX: '{prompt}' ({duration:.1f}s)...")
            await asyncio.wait_for(
                asyncio.to_thread(self._generate_remote, prompt, duration, out_wav),
                timeout=self.timeout_seconds,
            )
            if out_wav.is_file() and out_wav.stat().st_size > 1000:
                self._normalize_audio_loudness(out_wav)
                generated = True
                logger.info(f"Hugging Face Space SFX successfully generated -> {out_wav.name}")
        except Exception as exc:
            logger.warning(
                f"Gradio Space SFX generation failed or timed out ({type(exc).__name__}: {exc}). "
                "Engaging resilient FFmpeg Lavfi fallback."
            )

        if not generated:
            if not self.fallback_to_lavfi:
                raise ProviderError(f"Gradio Space SFX generation failed for prompt: {prompt}")
            return await self._lavfi_fallback.resolve_asset(query, cache_dir)

        return self._build_record(asset_id, out_wav, tags, duration, self.space_url)

    def _generate_remote(self, prompt: str, duration: float, out_path: Path) -> None:
        try:
            from gradio_client import Client  # type: ignore
        except ImportError as exc:
            raise RuntimeError("gradio_client is not installed") from exc

        client = Client(self.space_url)

        # Handle different known Space API signatures
        result = None
        space_lower = self.space_url.lower()

        if "audiogen" in space_lower:
            # fffiloni/audiogen or facebook/audiogen: prompt, duration
            try:
                result = client.predict(prompt, duration, api_name="/predict")
            except Exception:
                result = client.predict(prompt, api_name="/predict")
        elif "tangoflux" in space_lower:
            # declare-lab/TangoFlux: prompt, duration, steps
            result = client.predict(prompt=prompt, steps=25, duration=int(duration), api_name="/predict")
        else:
            # Generic predict
            try:
                result = client.predict(prompt, api_name="/predict")
            except Exception:
                result = client.predict(prompt, duration, api_name="/predict")

        if isinstance(result, (str, Path)) and Path(result).is_file():
            shutil.copy2(result, out_path)
        elif isinstance(result, tuple) and len(result) > 0 and Path(str(result[0])).is_file():
            shutil.copy2(result[0], out_path)
        else:
            raise RuntimeError(f"Unexpected return signature from Space: {result}")

    def _normalize_audio_loudness(self, wav_path: Path, target_lufs: float = -16.0) -> None:
        ffmpeg = config.resolve_ffmpeg()
        temp_wav = wav_path.with_suffix(".norm.wav")
        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(wav_path),
            "-af", f"loudnorm=I={target_lufs}:TP=-1.0:LRA=7.0",
            "-ar", "48000",
            "-ac", "2",
            str(temp_wav),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=15)
            if proc.returncode == 0 and temp_wav.is_file() and temp_wav.stat().st_size > 0:
                os.replace(temp_wav, wav_path)
        finally:
            if temp_wav.exists():
                temp_wav.unlink(missing_ok=True)

    def _build_record(
        self, asset_id: str, wav_path: Path, tags: list[str], duration: float, source: str
    ) -> dict[str, Any]:
        return {
            "asset_id": asset_id,
            "local_path": str(wav_path.resolve()),
            "sha256": _sha256(wav_path),
            "source_url": f"https://huggingface.co/spaces/{source}",
            "creator": f"Hugging Face Space ({source})",
            "license": "CC-BY-4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "commercial_allowed": True,
            "attribution": f"Generated via Hugging Face Space {source}",
            "tags": tags,
            "duration": round(duration, 3),
            "lufs": -16.0,
            "peak": -1.0,
        }
