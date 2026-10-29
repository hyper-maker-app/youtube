"""Pluggable Voyslity & ElevenLabs English Voice Provider with Deepgram Nova-3 STT.

Provides 100% English broadcast narration using:
1. Voyslity REST API gateway (browser User-Agent and polling support).
2. Direct ElevenLabs API fallback when ELEVENLABS_API_KEY is configured in .env.
3. Supported voices: Daniel (onwK4e9ZLuTAKqWW03F9), Adam, Rachel, Antoni.
4. Models: eleven_multilingual_v2, eleven_flash_v2_5.
5. Audio standard: Converts output to 48kHz mono PCM WAV via FFmpeg.
6. Forced Alignment: Deepgram Nova-3 English STT + difflib.SequenceMatcher to restore punctuation.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import httpx

import config
from providers.base import BaseVoiceProvider, ConfigurationError, ProviderError
from ._utils import narration_text, write_words

logger = logging.getLogger(__name__)

VOICE_PRESETS = {
    "daniel": "onwK4e9ZLuTAKqWW03F9",
    "adam": "pNInz6obpgDQGcFmaJgB",
    "rachel": "21m00Tcm4TlvDq8ikWAM",
    "antoni": "ErXwobaYiN019PkySvjV",
}


def _restore_punctuation_and_casing(original_text: str, stt_words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Use SequenceMatcher to align STT word timestamps back onto punctuated manuscript words."""
    orig_tokens = original_text.split()
    orig_clean = [re.sub(r"[^\w]", "", t).lower() for t in orig_tokens]
    stt_clean = [re.sub(r"[^\w]", "", w.get("text", "")).lower() for w in stt_words]

    matcher = difflib.SequenceMatcher(None, orig_clean, stt_clean)
    aligned_words: list[dict[str, Any]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                stt_entry = stt_words[j1 + offset]
                aligned_words.append({
                    "text": orig_tokens[i1 + offset],
                    "start": stt_entry["start"],
                    "end": stt_entry["end"],
                    "is_emphasis": False,
                })
        elif tag == "replace":
            # Best-effort interpolation over replaced interval
            if j2 > j1 and i2 > i1:
                start_t = stt_words[j1]["start"]
                end_t = stt_words[j2 - 1]["end"]
                step = (end_t - start_t) / max(1, (i2 - i1))
                for idx, o_idx in enumerate(range(i1, i2)):
                    aligned_words.append({
                        "text": orig_tokens[o_idx],
                        "start": round(start_t + idx * step, 3),
                        "end": round(start_t + (idx + 1) * step, 3),
                        "is_emphasis": False,
                    })
        elif tag == "delete":
            # Words in original missing in STT: interpolate using previous/next timestamps
            prev_end = aligned_words[-1]["end"] if aligned_words else 0.0
            next_start = stt_words[j1]["start"] if j1 < len(stt_words) else prev_end + 0.5
            step = (next_start - prev_end) / max(1, (i2 - i1))
            for idx, o_idx in enumerate(range(i1, i2)):
                aligned_words.append({
                    "text": orig_tokens[o_idx],
                    "start": round(prev_end + idx * step, 3),
                    "end": round(prev_end + (idx + 1) * step, 3),
                    "is_emphasis": False,
                })

    return aligned_words or stt_words


class VoyslityEnglishVoiceProvider(BaseVoiceProvider):
    """Broadcast English Voice Provider with dual Voyslity/ElevenLabs gateway and Deepgram alignment."""

    def __init__(
        self,
        *,
        voice_id: str | None = None,
        model_id: str | None = None,
        voyslity_key: str | None = None,
        voyslity_base_url: str | None = None,
        eleven_key: str | None = None,
        deepgram_key: str | None = None,
    ) -> None:
        self.voyslity_key = voyslity_key or os.getenv("VOYSLITY_API_KEY", "").strip()
        self.voyslity_base_url = (voyslity_base_url or os.getenv("VOYSLITY_BASE_URL", "https://voyslity.com/api.php")).strip()
        self.eleven_key = eleven_key or os.getenv("ELEVENLABS_API_KEY", "").strip()
        self.deepgram_key = deepgram_key or os.getenv("DEEPGRAM_API_KEY", "").strip()

        # Resolve voice ID
        requested_voice = (voice_id or os.getenv("ELEVEN_VOICE_ID") or os.getenv("VOYSLITY_VOICE_ID") or "daniel").lower()
        self.voice_id = VOICE_PRESETS.get(requested_voice, requested_voice)
        self.model_id = model_id or os.getenv("ELEVEN_MODEL") or os.getenv("VOYSLITY_MODEL_ID") or "eleven_flash_v2_5"

        if not self.voyslity_key and not self.eleven_key:
            raise ConfigurationError(
                "Neither VOYSLITY_API_KEY nor ELEVENLABS_API_KEY is configured in .env."
            )

    async def generate_narration(self, beats: list[Any], out_path: Path, lang: str = "en") -> dict[str, Any]:
        """Synthesize 100% English audio, convert to 48kHz WAV, and forced-align word timestamps."""
        text = narration_text(beats)
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        raw_mp3 = out_path.with_suffix(".temp.mp3")

        audio_bytes: bytes | None = None
        used_gateway = "none"

        # Strategy 1: Voyslity REST API
        if self.voyslity_key:
            try:
                logger.info(f"Synthesizing English narration via Voyslity gateway ({self.model_id}, voice={self.voice_id[:8]}...)...")
                audio_bytes = await self._synthesize_voyslity(text)
                used_gateway = "voyslity"
            except Exception as exc:
                logger.warning(f"Voyslity API failed: {exc}. Trying ElevenLabs direct fallback...")

        # Strategy 2: Direct ElevenLabs API Fallback
        if not audio_bytes and self.eleven_key:
            logger.info(f"Synthesizing English narration via ElevenLabs direct API ({self.model_id}, voice={self.voice_id[:8]}...)...")
            audio_bytes = await self._synthesize_elevenlabs(text)
            used_gateway = "elevenlabs"

        if not audio_bytes:
            raise ProviderError("Both Voyslity and ElevenLabs synthesis failed to return audio bytes")

        raw_mp3.write_bytes(audio_bytes)

        # Convert MP3 to broadcast 48kHz mono PCM WAV
        self._convert_to_pcm_wav(raw_mp3, out_path)
        raw_mp3.unlink(missing_ok=True)

        # Measure audio duration
        duration = self._probe_duration(out_path)

        # Strategy 3: Deepgram Nova-3 English Forced Alignment
        words = await self._align_words_with_nova3(out_path, text, lang="en")

        write_words(
            out_path, words, provider=used_gateway, voice_id=self.voice_id,
            lang="en", duration=duration, model=self.model_id
        )

        return {
            "vo_path": out_path,
            "duration": duration,
            "words": words,
            "provider": used_gateway,
            "voice_id": self.voice_id,
        }

    async def _synthesize_voyslity(self, text: str) -> bytes:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Authorization": f"Bearer {self.voyslity_key}",
        }
        payload = {
            "text": text,
            "voice_id": self.voice_id,
            "model_id": self.model_id,
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
            resp = await client.post(self.voyslity_base_url, headers=headers, json=payload)
            if resp.status_code >= 400:
                raise ProviderError(f"Voyslity HTTP {resp.status_code}: {resp.text[:300]}")
            if resp.headers.get("content-type", "").startswith("audio/"):
                return resp.content
            # Handle JSON polling or audio URL response
            try:
                data = resp.json()
                audio_url = data.get("audio_url") or data.get("url")
                if audio_url:
                    dl_resp = await client.get(audio_url, headers=headers)
                    return dl_resp.content
            except Exception:
                pass
            if resp.content and len(resp.content) > 1000:
                return resp.content
            raise ProviderError("Voyslity returned empty or invalid audio payload")

    async def _synthesize_elevenlabs(self, text: str) -> bytes:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key": self.eleven_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.8,
            },
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                raise ProviderError(f"ElevenLabs HTTP {resp.status_code}: {resp.text[:300]}")
            if not resp.content or len(resp.content) < 1000:
                raise ProviderError("ElevenLabs returned empty audio payload")
            return resp.content

    def _convert_to_pcm_wav(self, mp3_path: Path, wav_path: Path) -> None:
        ffmpeg = config.resolve_ffmpeg()
        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(mp3_path),
            "-ar", "48000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(wav_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not wav_path.is_file():
            raise ProviderError(f"FFmpeg MP3 to WAV conversion failed: {res.stderr}")

    def _probe_duration(self, wav_path: Path) -> float:
        ffprobe = config.resolve_ffprobe()
        cmd = [
            ffprobe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(wav_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        try:
            return round(float(res.stdout.strip()), 3)
        except Exception:
            return 10.0

    async def _align_words_with_nova3(self, wav_path: Path, original_text: str, lang: str = "en") -> list[dict[str, Any]]:
        if not self.deepgram_key:
            # Fallback evenly-spaced word timings if no Deepgram key
            return self._fallback_word_timings(original_text, self._probe_duration(wav_path))

        headers = {
            "Authorization": f"Token {self.deepgram_key}",
            "Content-Type": "audio/wav",
        }
        url = "https://api.deepgram.com/v1/listen?model=nova-3&language=en&smart_format=false"
        audio_data = wav_path.read_bytes()

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            resp = await client.post(url, headers=headers, content=audio_data)
            if resp.status_code >= 400:
                logger.warning(f"Deepgram Nova-3 alignment returned HTTP {resp.status_code}. Using interpolation.")
                return self._fallback_word_timings(original_text, self._probe_duration(wav_path))

            data = resp.json()
            try:
                stt_raw = data["results"]["channels"][0]["alternatives"][0]["words"]
                stt_words = [
                    {"text": str(w["word"]), "start": round(float(w["start"]), 3), "end": round(float(w["end"]), 3)}
                    for w in stt_raw if str(w.get("word") or "").strip()
                ]
                return _restore_punctuation_and_casing(original_text, stt_words)
            except Exception as exc:
                logger.warning(f"Failed to parse Nova-3 word timestamps: {exc}. Using interpolation.")
                return self._fallback_word_timings(original_text, self._probe_duration(wav_path))

    def _fallback_word_timings(self, text: str, duration: float) -> list[dict[str, Any]]:
        tokens = text.split()
        if not tokens:
            return []
        step = duration / max(1, len(tokens))
        return [
            {
                "text": w,
                "start": round(i * step, 3),
                "end": round((i + 1) * step, 3),
                "is_emphasis": (i % 6 == 0),
            }
            for i, w in enumerate(tokens)
        ]
