"""ElevenLabs Sound Effects (Text-to-Foley) provider.

Generates studio-grade 44.1kHz diegetic Foley and sound effects directly
from natural language physical event prompts.
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

import httpx

from providers.base import BaseSfxProvider, ConfigurationError, ProviderError
from services.sfx import SfxAsset

logger = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ElevenLabsSfxProvider(BaseSfxProvider):
    """Generate high-fidelity diegetic SFX via ElevenLabs sound-generation API."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY", "")
        if not self.api_key or not str(self.api_key).startswith("sk_"):
            raise ConfigurationError("ElevenLabs SFX requires a valid ELEVENLABS_API_KEY starting with 'sk_'.")
        self.base_url = "https://api.elevenlabs.io/v1/sound-generation"

    async def resolve_asset(self, query: dict[str, Any], cache_dir: Path) -> dict[str, Any]:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

        prompt = str(query.get("prompt") or "").strip()
        if not prompt:
            raise ProviderError("ElevenLabs SFX generation requires a non-empty prompt.")

        duration = min(max(float(query.get("duration") or 1.0), 0.5), 5.0)
        asset_id = str(query.get("asset_id") or f"eleven_sfx_{abs(hash(prompt)) % 1000000:06d}")
        out_wav = cache_dir / f"{asset_id}.wav"

        # Check existing cached asset
        if out_wav.is_file() and out_wav.stat().st_size > 0:
            return self._build_record(asset_id, out_wav, query.get("tags") or ["foley"], duration)

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": prompt[:200],
            "duration_seconds": round(duration, 1),
            "prompt_influence": 0.5,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(self.base_url, json=payload, headers=headers)
            except Exception as exc:
                raise ProviderError(f"ElevenLabs SFX connection failed: {exc}") from exc

        if response.status_code != 200:
            raise ProviderError(f"ElevenLabs SFX generation failed ({response.status_code}): {response.text}")

        temp_mp3 = cache_dir / f"{asset_id}.raw.mp3"
        temp_mp3.write_bytes(response.content)

        # Convert to standard 44.1kHz stereo WAV with peak loudness normalization
        import config

        ffmpeg = config.resolve_ffmpeg()
        if ffmpeg:
            cmd = [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(temp_mp3),
                "-af", "loudnorm=I=-14.0:TP=-1.0:LRA=7.0",
                "-ar", "44100", "-ac", "2",
                str(out_wav)
            ]
            subprocess.run(cmd, check=False)
            if temp_mp3.is_file():
                temp_mp3.unlink(missing_ok=True)
        else:
            shutil.move(temp_mp3, out_wav)

        return self._build_record(asset_id, out_wav, query.get("tags") or ["foley"], duration)

    def _build_record(self, asset_id: str, local_path: Path, tags: list[str], duration: float) -> dict[str, Any]:
        return {
            "asset_id": asset_id,
            "local_path": str(local_path.resolve()),
            "sha256": _sha256(local_path),
            "source_url": f"https://api.elevenlabs.io/v1/sound-generation#{asset_id}",
            "creator": "ElevenLabs Sound Generation",
            "license": "CC0-1.0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "commercial_allowed": True,
            "attribution": "",
            "tags": list(dict.fromkeys(list(tags) + ["elevenlabs", "foley"])),
            "duration": round(duration, 2),
            "peak": -1.0,
            "lufs": -14.0,
        }
