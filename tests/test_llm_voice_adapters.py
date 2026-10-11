from __future__ import annotations

import asyncio
import os
import unittest
from unittest import mock

from providers.factory import get_llm_provider, get_voice_provider
from providers.llm.gemini_flash import CHARACTER_AUDIO_RULE, GeminiFlashProvider
from providers.voice.deepgram_aura import DeepgramAuraProvider
from providers.voice.elevenlabs import ElevenLabsProvider


class LlmAndVoiceAdapterTests(unittest.TestCase):
    def test_factory_resolves_gemini_and_deepgram_from_environment(self) -> None:
        values = {
            "LLM_PROVIDER": "gemini_flash",
            "GEMINI_API_KEY": "test-key",
            "GEMINI_MODEL": "test-model",
            "VOICE_PROVIDER": "deepgram",
            "DEEPGRAM_API_KEY": "test-key",
            "DEEPGRAM_BASE_URL": "https://provider.test/v1",
            "DEEPGRAM_VOICE_MODEL": "test-voice",
            "DEEPGRAM_TRANSCRIBE_MODEL": "test-transcribe",
        }
        with mock.patch.dict(os.environ, values, clear=False):
            llm = get_llm_provider()
            voice = get_voice_provider()

        self.assertIsInstance(llm, GeminiFlashProvider)
        self.assertIsInstance(voice, DeepgramAuraProvider)

    def test_gemini_adapter_forwards_schema_and_character_audio_rule(self) -> None:
        provider = GeminiFlashProvider(api_key="test-key", model="test-model")
        schema = {"type": "object", "properties": {"title": {"type": "string"}}}
        with mock.patch.object(provider, "_generate_sync", return_value={"title": "ok"}) as generate:
            actual = asyncio.run(provider.generate_script("topic", "system", schema))

        self.assertEqual(actual, {"title": "ok"})
        self.assertEqual(generate.call_args.args, ("topic", "system", schema))
        self.assertIn("Characters never speak", CHARACTER_AUDIO_RULE)

    def test_deepgram_words_are_normalized(self) -> None:
        actual = DeepgramAuraProvider._words_from_response({
            "results": {"channels": [{"alternatives": [{"words": [
                {"word": "Hello", "start": 0, "end": 0.31},
                {"word": "world", "start": 0.31, "end": 0.79},
            ]}]}]}
        })
        self.assertEqual(actual, [
            {"text": "Hello", "start": 0.0, "end": 0.31, "loss": None},
            {"text": "world", "start": 0.31, "end": 0.79, "loss": None},
        ])

    def test_elevenlabs_alignment_is_grouped_into_words(self) -> None:
        actual = ElevenLabsProvider._words_from_alignment({
            "alignment": {
                "characters": list("Hi all"),
                "character_start_times_seconds": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5],
                "character_end_times_seconds": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
            }
        })
        self.assertEqual(actual, [
            {"text": "Hi", "start": 0.0, "end": 0.2, "loss": None},
            {"text": "all", "start": 0.3, "end": 0.6, "loss": None},
        ])
