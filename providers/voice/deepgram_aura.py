"""Deepgram Aura synthesis adapter with Deepgram word-level transcription."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from providers.base import BaseVoiceProvider, ConfigurationError, ProviderError
from ._utils import narration_text, write_words


class DeepgramAuraProvider(BaseVoiceProvider):
    """Synthesize MP3 with Aura, then align that exact MP3 through Deepgram Listen."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        voice_model: str | None = None,
        transcribe_model: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        self.base_url = (base_url or os.getenv("DEEPGRAM_BASE_URL") or "").rstrip("/")
        is_longform = str(os.getenv("LONGFORM_MODE", "")).casefold() in {"1", "true", "yes"} or str(os.getenv("PRODUCTION_FORMAT", "")).casefold() in {"longform", "explorer"}
        env_voice = os.getenv("DEEPGRAM_VOICE_MODEL")
        longform_voice = os.getenv("DEEPGRAM_LONGFORM_VOICE_MODEL") or "aura-2-hera-en"
        if voice_model:
            self.voice_model = voice_model
        elif is_longform:
            self.voice_model = longform_voice if (not env_voice or env_voice == "aura-2-hermes-en") else env_voice
        else:
            self.voice_model = env_voice or "aura-2-hermes-en"
        self.witness_voice_model = os.getenv("DEEPGRAM_WITNESS_VOICE_MODEL") or "aura-2-hermes-en"
        self.transcribe_model = transcribe_model or os.getenv("DEEPGRAM_TRANSCRIBE_MODEL") or "nova-3"
        env_speed = os.getenv("DEEPGRAM_TTS_SPEED")
        if env_speed:
            if is_longform and env_speed == "1.12":
                self.tts_speed = 1.0
            else:
                self.tts_speed = float(env_speed)
        else:
            self.tts_speed = 1.0 if is_longform else 1.12
        missing = [
            name
            for name, value in (
                ("DEEPGRAM_API_KEY", self.api_key),
                ("DEEPGRAM_BASE_URL", self.base_url),
                ("DEEPGRAM_VOICE_MODEL", self.voice_model),
                ("DEEPGRAM_TRANSCRIBE_MODEL", self.transcribe_model),
            )
            if not value
        ]
        if missing:
            raise ConfigurationError(
                "deepgram provider requires: " + ", ".join(missing) + ". Configure them in .env."
            )

    def _voice_for_beat(self, beat: Any) -> str:
        role = str(getattr(beat, "role", "default") or "default").strip().casefold()
        if role.startswith(("witness", "historical_witness", "interviewee")):
            return self.witness_voice_model
        return self.voice_model

    async def generate_narration(self, beats: list, out_path: Path, lang: str) -> dict[str, Any]:
        text = narration_text(beats)
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        headers = {"Authorization": f"Token {self.api_key}"}
        base_params: dict[str, Any] = {}
        if self.tts_speed and self.tts_speed != 1.0:
            base_params["speed"] = self.tts_speed
        # Deepgram /speak endpoint has a 2000 character limit per request (HTTP 413).
        # Group consecutive beats by speaker voice (Nova female voice vs Historical Witness male voice)
        # while keeping each chunk <= 1500 characters.
        chunks: list[tuple[str, str]] = []
        current_chunk: list[str] = []
        current_voice: str = self.voice_model
        current_len = 0
        for beat in beats:
            beat_text = str(getattr(beat, "text", "") or "").strip()
            if not beat_text:
                continue
            beat_voice = self._voice_for_beat(beat)
            if current_chunk and (beat_voice != current_voice or current_len + len(beat_text) + 1 > 1500):
                chunks.append((current_voice, " ".join(current_chunk)))
                current_chunk = [beat_text]
                current_voice = beat_voice
                current_len = len(beat_text)
            else:
                if not current_chunk:
                    current_voice = beat_voice
                current_chunk.append(beat_text)
                current_len += len(beat_text) + 1
        if current_chunk:
            chunks.append((current_voice, " ".join(current_chunk)))
        if not chunks:
            chunks = [(self.voice_model, text)]

        audio_parts: list[bytes] = []
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
            for chunk_voice, chunk_text in chunks:
                synth_params = {**base_params, "model": chunk_voice}
                synth = await client.post(
                    f"{self.base_url}/speak",
                    params=synth_params,
                    headers={**headers, "Content-Type": "application/json"},
                    json={"text": chunk_text},
                )
                if synth.status_code >= 400:
                    raise ProviderError(f"deepgram synthesis failed with HTTP {synth.status_code}")
                if not synth.content:
                    raise ProviderError("deepgram synthesis returned an empty audio payload")
                audio_parts.append(synth.content)

            full_audio = b"".join(audio_parts)
            out_path.write_bytes(full_audio)

            transcript = await client.post(
                f"{self.base_url}/listen",
                params={"model": self.transcribe_model, "language": lang, "smart_format": "false"},
                headers={**headers, "Content-Type": "audio/mpeg"},
                content=full_audio,
            )
        if transcript.status_code >= 400:
            raise ProviderError(f"deepgram word alignment failed with HTTP {transcript.status_code}")
        words = self._words_from_response(transcript.json())
        duration = max((word["end"] for word in words), default=0.0)
        write_words(
            out_path, words, provider="deepgram", voice_id=self.voice_model,
            lang=lang, duration=duration, source="deepgram_listen",
        )
        return {"vo_path": out_path, "duration": duration, "words": words}

    @staticmethod
    def _words_from_response(payload: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            source_words = payload["results"]["channels"][0]["alternatives"][0]["words"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("deepgram transcription returned no word-level timestamps") from exc
        words = [
            {"text": str(item["word"]), "start": round(float(item["start"]), 3), "end": round(float(item["end"]), 3), "loss": None}
            for item in source_words
            if str(item.get("word") or "").strip()
        ]
        if not words:
            raise ProviderError("deepgram transcription returned an empty word list")
        return words
