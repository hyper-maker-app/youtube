"""Deepgram Aura synthesis adapter with Deepgram word-level transcription."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from providers.base import BaseVoiceProvider, ConfigurationError, ProviderError
from ._utils import narration_text, write_words
from services.narration_audio import assemble, probe_audio
from services.narration_delivery import delivery_profile, transport_chunks
from ._utils import beat_value


class DeepgramAuraProvider(BaseVoiceProvider):
    """Synthesize MP3 with Aura/Flux, then align that exact MP3 through Deepgram Listen."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        voice_model: str | None = None,
        transcribe_model: str | None = None,
        enable_flux_roster: bool | None = None,
        initial_locks: dict[str, str] | None = None,
        speed: float | None = None,
        expressivity: int | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        self.base_url = (base_url or os.getenv("DEEPGRAM_BASE_URL") or "").rstrip("/")
        parsed_url = urlsplit(self.base_url)
        if self.base_url and (parsed_url.scheme not in ("https", "http") or parsed_url.username or parsed_url.password or
                              parsed_url.query or parsed_url.fragment or parsed_url.path not in ("", "/v1", "/v2")):
            raise ConfigurationError("Deepgram base URL requires a credential-free root or version path")
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
        configured_speed = float(os.getenv("DEEPGRAM_TTS_SPEED") or "1.0")
        # Keep the requested natural baseline.  Legacy .env files may still carry
        # the former 1.12 Shorts setting; do not let it silently become the new
        # Flux default (and longform is always explicitly natural-paced).
        if speed is not None:
            self.tts_speed = float(speed)
        elif is_longform or (self.voice_model.startswith("flux-") and abs(configured_speed - 1.12) < 1e-9):
            self.tts_speed = 1.0
        else:
            self.tts_speed = configured_speed
        self.expressivity = expressivity if expressivity is not None else int(os.getenv("DEEPGRAM_TTS_EXPRESSIVITY", "0"))
        self.output_encoding = os.getenv("DEEPGRAM_TTS_ENCODING", "linear16").casefold()
        self.output_container = os.getenv("DEEPGRAM_TTS_CONTAINER", "wav").casefold()
        self.output_sample_rate = int(os.getenv("DEEPGRAM_TTS_SAMPLE_RATE", "48000"))

        # Initialize Flux Multi-Voice Roster if requested or configured
        flux_flag = enable_flux_roster if enable_flux_roster is not None else (
            str(os.getenv("DEEPGRAM_FLUX_ROSTER", "")).casefold() in {"1", "true", "yes"}
        )
        if flux_flag:
            from services.voice_roster import VoiceAssigner

            self._voice_assigner: VoiceAssigner | None = VoiceAssigner(
                primary_voice=self.voice_model,
                initial_locks=initial_locks,
            )
        else:
            self._voice_assigner = None

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
        # Fail closed before any request; aliases and unsupported output are never guessed.
        if self.voice_model.startswith("flux-") and not re.fullmatch(r"flux-[a-z0-9]+-en", self.voice_model):
            raise ConfigurationError("Flux voice must be an explicit flux-{voice}-en model")
        if self.output_encoding != "linear16" or self.output_container != "wav" or self.output_sample_rate != 48000:
            raise ConfigurationError("Narration output is pinned to linear16/wav/48000 for canonical assembly")

    def _speak_url(self, voice_model: str) -> str:
        """Select Deepgram /speak endpoint version based on model prefix and root URL."""
        root_url = re.sub(r"/v\d+/?$", "", self.base_url)
        if re.fullmatch(r"flux-[a-z0-9]+-en", voice_model):
            return f"{root_url}/v2/speak"
        if re.fullmatch(r"aura(?:-2)?-[a-z0-9]+-[a-z]{2}", voice_model):
            return f"{root_url}/v1/speak"
        raise ConfigurationError("Explicit Aura or Flux voice model required; aliases are unsupported")

    def invocation_settings(self) -> dict:
        delivery_profile({}, self.voice_model, self.tts_speed, self.expressivity)
        return {"provider": "deepgram", "model_alias": self.voice_model, "voice_id": self.voice_model,
                "model": self.voice_model, "endpoint": self._speak_url(self.voice_model),
                "transport": "rest", "speed": self.tts_speed, "expressivity": self.expressivity,
                "encoding": self.output_encoding, "container": self.output_container,
                "sample_rate": self.output_sample_rate, "native_audio": False,
                "alignment_model": self.transcribe_model, "locked_voices": self._voice_assigner.get_locked_voices() if self._voice_assigner else {}}

    @staticmethod
    async def _post(client, *args, **kwargs):
        try:
            return await client.post(*args, **kwargs)
        except httpx.HTTPError:
            raise ProviderError("Deepgram transport failed; credentials and response omitted") from None

    def _voice_for_beat(self, beat: Any) -> str:
        # New authored delivery uses one narrator unless a second voice is justified.
        if beat_value(beat, "delivery", None):
            requested = beat_value(beat, "delivery", {}).get("voice_id", self.voice_model)
            if requested != self.voice_model and not beat_value(beat, "voice_reason", ""):
                raise ConfigurationError("Secondary voice requires authored voice_reason")
            return requested
        if self._voice_assigner is not None:
            return self._voice_assigner.assign_voice(beat)
        role = str(beat_value(beat, "role", "default") or "default").strip().casefold()
        if role.startswith(("witness", "historical_witness", "interviewee")):
            return self.witness_voice_model
        return self.voice_model

    def narration_chunks(self, beats: list, limit: int = 1500) -> list[tuple[str, str]]:
        return [(voice, text) for voice, text, _ in self.delivery_chunks(beats, limit)]

    def delivery_chunks(self, beats: list, limit: int = 1500) -> list[tuple[str, str, dict]]:
        """Keep authored beat/delivery boundaries while batching complete sentences."""
        if limit < 1:
            raise ValueError("Chunk limit must be positive")
        chunks: list[tuple[str, str, dict]] = []
        for beat in beats:
            voice = self._voice_for_beat(beat)
            text = str(beat_value(beat, "text", "") or "").strip()
            if re.search(r"<[^>]+>|\{(?:pause|emotion|word|pronounce)\b|\[(?:sad|happy|excited|angry)\]", text, re.I):
                raise ConfigurationError("Spoken manuscript contains unsupported inline control; author delivery separately")
            authored = beat_value(beat, "delivery", None)
            profile = delivery_profile(authored, voice, self.tts_speed, self.expressivity)
            if profile["voice_id"] != voice and not beat_value(beat, "voice_reason", ""):
                raise ConfigurationError("Secondary voice requires authored voice_reason")
            parts = [part for paragraph in re.split(r"\n\s*\n", text)
                     for part in transport_chunks(paragraph, limit - 40 if profile.get("pause_after_ms") else limit)]
            for i, part in enumerate(parts):
                if i == len(parts)-1 and profile.get("pause_after_ms"):
                    part += f" {{pause:{{duration_ms:{profile['pause_after_ms']}}}}}"
                chunks.append((profile["voice_id"], part, profile))
        return chunks

    async def generate_narration(self, beats: list, out_path: Path, lang: str) -> dict[str, Any]:
        text = narration_text(beats)
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        headers = {"Authorization": f"Token {self.api_key}"}
        base_params: dict[str, Any] = {"encoding": self.output_encoding, "container": self.output_container,
                                       "sample_rate": self.output_sample_rate, "speed": self.tts_speed}
        # Deepgram /speak endpoint has a 2000 character limit per request (HTTP 413).
        # Group consecutive beats by speaker voice while keeping each chunk <= 1500 characters.
        invocation = self.invocation_settings()
        chunks = self.delivery_chunks(beats)
        if not chunks:
            raise ValueError("No narration text")

        audio_parts: list[Path] = []
        part_dir = out_path.parent / (out_path.stem + "_parts")
        part_dir.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
            for index, (chunk_voice, chunk_text, profile) in enumerate(chunks):
                synth_params = {**base_params, "model": chunk_voice}
                synth_params["speed"] = float(profile["pace"])
                if chunk_voice.startswith("flux-"):
                    synth_params["expressivity"] = int(profile["expressivity"])
                elif synth_params["speed"] == 1.0:
                    synth_params.pop("speed", None)
                speak_url = self._speak_url(chunk_voice)
                synth = None
                for attempt in range(3):
                    synth = await self._post(client,
                        speak_url,
                        params=synth_params,
                        headers={**headers, "Content-Type": "application/json"},
                        json={"text": chunk_text},
                    )
                    if synth.status_code in (429, 503) and attempt < 2:
                        await asyncio.sleep(1.0 * (2 ** attempt))
                        continue
                    break

                if synth is None or synth.status_code >= 400:
                    status = synth.status_code if synth is not None else "timeout"
                    raise ProviderError(f"deepgram synthesis failed with HTTP {status}")
                if not synth.content:
                    raise ProviderError("deepgram synthesis returned an empty audio payload")
                part_path = part_dir / f"part{index:04d}.wav"
                part_path.write_bytes(synth.content)
                probe_audio(part_path)
                audio_parts.append(part_path)

            measured = assemble(audio_parts, out_path, part_dir)
            full_audio = out_path.read_bytes()

            transcript = await self._post(client,
                re.sub(r"/v\d+/?$", "", self.base_url) + "/v1/listen",
                params={"model": self.transcribe_model, "language": lang, "smart_format": "false"},
                headers={**headers, "Content-Type": "audio/wav" if out_path.suffix.lower() == ".wav" else "audio/mpeg"},
                content=full_audio,
            )
        if transcript.status_code >= 400:
            raise ProviderError(f"deepgram word alignment failed with HTTP {transcript.status_code}")
        try:
            words = self._words_from_response(transcript.json())
        except (ValueError, TypeError, KeyError):
            raise ProviderError("Deepgram alignment response invalid; response omitted") from None
        duration = float(measured["duration"])
        if any(w["start"] < 0 or w["end"] < w["start"] or w["end"] > duration + .15 for w in words):
            raise ProviderError("Word alignment lies outside probed audio duration")
        extra_meta: dict[str, Any] = {}
        if self._voice_assigner is not None:
            extra_meta["locked_voices"] = self._voice_assigner.get_locked_voices()
        write_words(
            out_path, words, provider="deepgram", voice_id=self.voice_model,
            lang=lang, duration=duration, source="deepgram_listen", timing_origin="stt_word_alignment",
            audio_probe=measured, endpoint=self._speak_url(self.voice_model),
            model=self.voice_model, speed=self.tts_speed, expressivity=self.expressivity,
            encoding=self.output_encoding, container=self.output_container,
            sample_rate=self.output_sample_rate, invocation=invocation,
            delivery=[p for _, _, p in chunks], alignment_end=max(w["end"] for w in words), **extra_meta,
        )
        return {"vo_path": out_path, "duration": duration, "words": words,
                "audio_probe": measured, "provenance": invocation,
                "delivery": [p for _, _, p in chunks], "alignment_end": max(w["end"] for w in words)}

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
