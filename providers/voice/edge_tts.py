"""Edge TTS adapter with beat-level prosody and real FFmpeg silence."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import config
import editor
from providers.base import BaseVoiceProvider, ConfigurationError, ProviderError
from ._utils import beat_value, write_words


_TICKS_PER_SECOND = 10_000_000


class EdgeTTSProvider(BaseVoiceProvider):
    """Generate one MP3 per beat, then concatenate with true silent audio samples."""

    def __init__(self, *, voice: str | None = None) -> None:
        self.voice = voice or os.getenv("EDGE_TTS_VOICE")
        if not self.voice:
            raise ConfigurationError("edge_tts provider requires EDGE_TTS_VOICE. Configure it in .env.")

    @staticmethod
    def _rate_str(percent: int) -> str:
        return f"{percent:+d}%"

    @staticmethod
    def _clamp_rate(base: int, adjustment: int) -> int:
        ceiling = config.EDGE_RATE_MAX_PCT
        return max(-ceiling, min(ceiling, int(base) + int(adjustment)))

    @staticmethod
    def _connector():
        import aiohttp

        return aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())

    async def _synthesize(self, text: str, rate: int, pitch: str, voice: str | None = None) -> tuple[bytes, list[dict[str, Any]]]:
        try:
            import edge_tts
        except ImportError as exc:  # pragma: no cover - declared in requirements.txt
            raise ConfigurationError("edge_tts provider requires the edge-tts package.") from exc

        audio = bytearray()
        words: list[dict[str, Any]] = []
        target_voice = voice or self.voice
        try:
            communication = edge_tts.Communicate(
                text,
                voice=target_voice,
                rate=self._rate_str(rate),
                pitch=pitch,
                boundary="WordBoundary",
                connector=self._connector(),
            )
            async for chunk in communication.stream():
                if chunk["type"] == "audio":
                    audio.extend(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    start = float(chunk["offset"]) / _TICKS_PER_SECOND
                    words.append({
                        "text": str(chunk["text"]),
                        "start": round(start, 3),
                        "end": round(start + float(chunk["duration"]) / _TICKS_PER_SECOND, 3),
                        "loss": None,
                    })
        except Exception as exc:
            raise ProviderError(f"edge_tts synthesis failed: {type(exc).__name__}") from exc
        if not audio or not words:
            raise ProviderError("edge_tts returned incomplete audio or word boundaries")
        return bytes(audio), words

    async def _synth_beats(
        self, beats: list[object], audio_dir: Path, adjustment: int, lang: str = "en"
    ) -> tuple[list[Path], list[list[dict[str, Any]]], list[float], list[dict[str, Any]]]:
        paths: list[Path] = []
        boundaries: list[list[dict[str, Any]]] = []
        durations: list[float] = []
        details: list[dict[str, Any]] = []
        is_tr = (lang or "").strip().casefold() == "tr"
        for ordinal, beat in enumerate(beats, start=1):
            text = str(beat_value(beat, "text", "")).strip()
            if not text:
                raise ValueError(f"beat {ordinal} has no narration text")
            role = str(beat_value(beat, "role", "default"))
            profile = config.beat_voice(role)
            rate = self._clamp_rate(profile["rate"], adjustment)
            pitch = str(profile["pitch"])
            if is_tr:
                target_voice = "tr-TR-EmelNeural" if role.casefold() in {"host_nova", "nova"} else config.lang_profile("tr")["voice"]
            else:
                target_voice = self.voice
            audio, words = await self._synthesize(text, rate, pitch, voice=target_voice)
            index = int(beat_value(beat, "index", ordinal))
            part = audio_dir / f"vo_b{index:02d}.mp3"
            part.write_bytes(audio)
            duration = editor.probe(part).duration
            if duration is None or duration <= 0:
                raise ProviderError(f"edge_tts part {index} has no measurable duration")
            paths.append(part)
            boundaries.append(words)
            durations.append(float(duration))
            details.append({
                "index": index,
                "role": role,
                "rate": self._rate_str(rate),
                "pitch": pitch,
                "pause_after": float(profile["pause_after"]),
                "duration": round(float(duration), 3),
                "voice": target_voice,
            })
        return paths, boundaries, durations, details

    @staticmethod
    def _rebase_boundaries(
        boundaries: list[list[dict[str, Any]]], durations: list[float], pauses: list[float]
    ) -> list[dict[str, Any]]:
        cursor = config.BEAT_LEAD_SILENCE
        words: list[dict[str, Any]] = []
        for part_words, duration, pause in zip(boundaries, durations, pauses):
            for word in part_words:
                words.append({
                    "text": word["text"],
                    "start": round(float(word["start"]) + cursor, 3),
                    "end": round(float(word["end"]) + cursor, 3),
                    "loss": None,
                })
            cursor += duration + pause
        return words

    async def generate_narration(self, beats: list, out_path: Path, lang: str) -> dict[str, Any]:
        if not beats:
            raise ValueError("generate_narration requires at least one beat")
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pauses = [float(config.beat_voice(str(beat_value(beat, "role", "default")))["pause_after"]) for beat in beats]
        pauses[-1] = 0.0
        paths, boundaries, durations, details = await self._synth_beats(beats, out_path.parent, 0, lang=lang)

        # The adapter preserves the authored beat prosody. It does not ask another voice
        # provider to recover an overrun; the bounded single re-synthesis only adjusts
        # Edge's own rate while retaining each role's pitch profile.
        speech = sum(durations)
        adjustment = 0
        budget = config.speech_budget_seconds(sum(durations) + sum(pauses) + config.BEAT_LEAD_SILENCE)
        if speech > budget:
            adjustment = min(config.EDGE_RATE_MAX_PCT, max(1, round((speech / budget - 1.0) * 100)))
            paths, boundaries, durations, details = await self._synth_beats(beats, out_path.parent, adjustment, lang=lang)
            speech = sum(durations)

        try:
            editor.concat_audio_with_pauses(
                paths, pauses, out_path, lead_silence=config.BEAT_LEAD_SILENCE
            )
        except Exception as exc:
            raise ProviderError(f"edge_tts audio assembly failed: {type(exc).__name__}") from exc
        duration = editor.probe(out_path).duration
        if duration is None or duration <= 0:
            raise ProviderError("edge_tts output has no measurable duration")
        words = self._rebase_boundaries(boundaries, durations, pauses)
        active_voice = config.lang_profile("tr")["voice"] if (lang or "").casefold() == "tr" else self.voice
        write_words(
            out_path, words, provider="edge_tts", voice_id=active_voice, lang=lang,
            duration=duration, source="edge_wordboundary", speech_duration=round(speech, 3),
            rate_adjustment=self._rate_str(adjustment), beats=details,
        )
        return {"vo_path": out_path, "duration": float(duration), "words": words}
