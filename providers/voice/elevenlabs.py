"""ElevenLabs narration adapter using the time-stamped synthesis response."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

import httpx

from providers.base import BaseVoiceProvider, ConfigurationError, ProviderError
from ._utils import narration_text, write_words


class ElevenLabsProvider(BaseVoiceProvider):
    """Create one MP3 and its word timestamps from ElevenLabs alignment data."""

    def __init__(
        self, *, api_key: str | None = None, base_url: str | None = None,
        voice_id: str | None = None, model: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.base_url = (base_url or os.getenv("ELEVENLABS_BASE_URL") or "").rstrip("/")
        self.voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID")
        self.model = model or os.getenv("ELEVENLABS_MODEL")
        missing = [
            name for name, value in (
                ("ELEVENLABS_API_KEY", self.api_key),
                ("ELEVENLABS_BASE_URL", self.base_url),
                ("ELEVENLABS_VOICE_ID", self.voice_id),
                ("ELEVENLABS_MODEL", self.model),
            ) if not value
        ]
        if missing:
            raise ConfigurationError(
                "elevenlabs provider requires: " + ", ".join(missing) + ". Configure them in .env."
            )

    async def generate_narration(self, beats: list, out_path: Path, lang: str) -> dict[str, Any]:
        text = narration_text(beats)
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        settings = {"stability": 0.55, "similarity_boost": 0.80, "style": 0.15, "use_speaker_boost": True}
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
            response = await client.post(
                f"{self.base_url}/text-to-speech/{self.voice_id}/with-timestamps",
                headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
                json={"text": text, "model_id": self.model, "voice_settings": settings},
            )
        if response.status_code >= 400:
            raise ProviderError(f"elevenlabs synthesis failed with HTTP {response.status_code}")
        payload = response.json()
        encoded_audio = payload.get("audio_base64")
        if not encoded_audio:
            raise ProviderError("elevenlabs time-stamped response contained no audio_base64")
        try:
            out_path.write_bytes(base64.b64decode(encoded_audio))
        except (ValueError, TypeError) as exc:
            raise ProviderError("elevenlabs returned invalid base64 audio") from exc
        words = self._words_from_alignment(payload)
        duration = max((word["end"] for word in words), default=0.0)
        write_words(
            out_path, words, provider="elevenlabs", voice_id=self.voice_id,
            lang=lang, duration=duration, source="elevenlabs_with_timestamps",
        )
        return {"vo_path": out_path, "duration": duration, "words": words}

    @staticmethod
    def _words_from_alignment(payload: dict[str, Any]) -> list[dict[str, Any]]:
        alignment = payload.get("normalized_alignment") or payload.get("alignment")
        if not isinstance(alignment, dict):
            raise ProviderError("elevenlabs response contained no character alignment")
        try:
            chars = alignment["characters"]
            starts = alignment["character_start_times_seconds"]
            ends = alignment["character_end_times_seconds"]
        except KeyError as exc:
            raise ProviderError("elevenlabs alignment was incomplete") from exc
        words: list[dict[str, Any]] = []
        token: list[str] = []
        start: float | None = None
        end: float | None = None

        def flush() -> None:
            nonlocal token, start, end
            text = "".join(token).strip()
            if text and start is not None and end is not None:
                words.append({"text": text, "start": round(start, 3), "end": round(end, 3), "loss": None})
            token, start, end = [], None, None

        for character, char_start, char_end in zip(chars, starts, ends):
            if str(character).isspace():
                flush()
                continue
            if start is None:
                start = float(char_start)
            end = float(char_end)
            token.append(str(character))
        flush()
        if not words:
            raise ProviderError("elevenlabs alignment produced no words")
        return words
