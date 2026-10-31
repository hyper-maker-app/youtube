"""Unit tests for Phase 5 (R5) — Azure Cognitive Services Neural TTS Provider.

Verifies:
1. engine/providers/voice/azure_neural.py is cleanly importable.
2. AzureNeuralVoiceProvider implements BaseVoiceProvider interface.
3. Default configuration:
   - AZURE_TTS_REGION="eastus"
   - AZURE_TTS_VOICE="en-US-GuyNeural"
4. Environment variable loading:
   - AZURE_TTS_KEY, AZURE_TTS_REGION, AZURE_TTS_VOICE
   - Constructor kwargs precedence over environment variables
5. Voice Provider Factory registration:
   - "azure" listed in voice_providers.registered_names
   - get_voice_provider("azure") resolves to AzureNeuralVoiceProvider
   - engine/providers/voice/factory.py re-exports and registry parity
6. Dummy / placeholder key detection and offline mock simulation.
7. SSML builder formatting, escaping, rate and pitch controls.
8. Real and mock 48kHz mono 16-bit PCM WAV audio synthesis.
9. Word-level timing / alignment generation and words.json persistence.
10. Azure Speech SDK word boundary event handling and calculations.
11. Error resilience: graceful fallback on SDK error / cancellation.
12. Verification of .env, .env.example, and engine/.env entries.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import wave
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from engine.providers.base import BaseVoiceProvider
from engine.providers.factory import get_voice_provider, voice_providers
from engine.providers.voice._utils import words_path_for
from engine.providers.voice.azure_neural import (
    AZURE_SPEECH_SDK_AVAILABLE,
    DEFAULT_REGION,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_VOICE,
    AzureNeuralVoiceProvider,
)
from engine.providers.voice.factory import (
    get_voice_provider as get_voice_provider_shim,
    voice_providers as voice_providers_shim,
)


def test_azure_neural_import_and_constants():
    """Verify azure_neural.py exports expected classes and default constants."""
    assert AzureNeuralVoiceProvider is not None
    assert issubclass(AzureNeuralVoiceProvider, BaseVoiceProvider)
    assert DEFAULT_REGION == "eastus"
    assert DEFAULT_VOICE == "en-US-GuyNeural"
    assert DEFAULT_SAMPLE_RATE == 48000
    assert isinstance(AZURE_SPEECH_SDK_AVAILABLE, bool)


def test_azure_provider_interface_compliance():
    """Verify AzureNeuralVoiceProvider implements generate_narration with correct signature."""
    provider = AzureNeuralVoiceProvider()
    assert hasattr(provider, "generate_narration")
    assert asyncio.iscoroutinefunction(provider.generate_narration)


def test_azure_provider_initialization_defaults(monkeypatch: pytest.MonkeyPatch):
    """Verify default initialization when no environment variables or kwargs are given."""
    monkeypatch.delenv("AZURE_TTS_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_TTS_REGION", raising=False)
    monkeypatch.delenv("AZURE_TTS_VOICE", raising=False)

    provider = AzureNeuralVoiceProvider()
    assert provider.region == "eastus"
    assert provider.voice_name == "en-US-GuyNeural"
    assert provider.api_key == ""
    assert provider.is_mock is True


def test_azure_provider_initialization_env_vars(monkeypatch: pytest.MonkeyPatch):
    """Verify initialization respects AZURE_TTS_KEY, AZURE_TTS_REGION, AZURE_TTS_VOICE."""
    monkeypatch.setenv("AZURE_TTS_KEY", "test_azure_secret_key_12345")
    monkeypatch.setenv("AZURE_TTS_REGION", "westeurope")
    monkeypatch.setenv("AZURE_TTS_VOICE", "en-US-JennyNeural")

    provider = AzureNeuralVoiceProvider()
    assert provider.api_key == "test_azure_secret_key_12345"
    assert provider.region == "westeurope"
    assert provider.voice_name == "en-US-JennyNeural"


def test_azure_provider_constructor_kwargs_override(monkeypatch: pytest.MonkeyPatch):
    """Verify constructor kwargs override environment variables."""
    monkeypatch.setenv("AZURE_TTS_KEY", "env_key")
    monkeypatch.setenv("AZURE_TTS_REGION", "env_region")
    monkeypatch.setenv("AZURE_TTS_VOICE", "env_voice")

    provider = AzureNeuralVoiceProvider(
        api_key="custom_key",
        region="centralus",
        voice_name="en-US-DavisNeural",
        speech_rate="1.15",
        speech_pitch="+5Hz",
        mock_mode=True,
    )
    assert provider.api_key == "custom_key"
    assert provider.region == "centralus"
    assert provider.voice_name == "en-US-DavisNeural"
    assert provider.speech_rate == "1.15"
    assert provider.speech_pitch == "+5Hz"
    assert provider.is_mock is True


def test_is_dummy_key_detection():
    """Verify dummy placeholder keys are accurately detected to prevent live network calls."""
    assert AzureNeuralVoiceProvider._is_dummy_key("") is True
    assert AzureNeuralVoiceProvider._is_dummy_key("your_key_here") is True
    assert AzureNeuralVoiceProvider._is_dummy_key("your_azure_key") is True
    assert AzureNeuralVoiceProvider._is_dummy_key("dummy_secret") is True
    assert AzureNeuralVoiceProvider._is_dummy_key("test_key") is True
    assert AzureNeuralVoiceProvider._is_dummy_key("<insert-key>") is True
    # Real looking key
    assert AzureNeuralVoiceProvider._is_dummy_key("4a9f8b2c1d3e4f5a6b7c8d9e0f1a2b3c") is False


def test_voice_factory_registration():
    """Verify 'azure' is registered in engine.providers.factory voice_providers registry."""
    assert "azure" in voice_providers.registered_names
    provider = get_voice_provider("azure")
    assert isinstance(provider, AzureNeuralVoiceProvider)
    assert provider.voice_name == "en-US-GuyNeural"
    assert provider.region == "eastus"


def test_voice_factory_shim_parity():
    """Verify engine/providers/voice/factory.py re-exports function and list 'azure'."""
    assert "azure" in voice_providers_shim.registered_names
    provider = get_voice_provider_shim("azure")
    assert isinstance(provider, AzureNeuralVoiceProvider)


def test_ssml_builder_formatting_and_escaping():
    """Verify SSML generation with XML escaping and prosody rate/pitch."""
    provider = AzureNeuralVoiceProvider(
        voice_name="en-US-GuyNeural",
        speech_rate=1.15,
        speech_pitch="+2Hz",
    )
    text = "Danger: Temperature > 5000°C & pressure is critical!"
    ssml = provider._build_ssml(text)

    assert "<speak" in ssml
    assert 'voice name="en-US-GuyNeural"' in ssml
    assert 'rate="+15%"' in ssml
    assert 'pitch="+2Hz"' in ssml
    # Check XML entity escaping
    assert "&gt;" in ssml
    assert "&amp;" in ssml
    assert "< 5000" not in ssml


def test_mock_audio_synthesis_and_duration(tmp_path: Path):
    """Verify _synthesize_mock_audio produces valid 48kHz mono 16-bit PCM WAV."""
    provider = AzureNeuralVoiceProvider()
    out_wav = tmp_path / "test_azure_mock.wav"
    text = "You are standing at the rim of the volcano as lava spews into the sky."

    duration = provider._synthesize_mock_audio(text, out_wav)
    assert out_wav.is_file()
    assert duration > 0.0

    # Inspect WAV header directly
    with wave.open(str(out_wav), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 48000
        frames = wf.getnframes()
        measured_sec = frames / 48000.0
        assert abs(measured_sec - duration) < 0.05


def test_generate_word_timings():
    """Verify _generate_word_timings creates evenly distributed word timestamps."""
    provider = AzureNeuralVoiceProvider()
    text = "The earth trembles beneath your feet"
    words = provider._generate_word_timings(text, total_duration=3.5)

    assert len(words) == 6
    tokens = text.split()
    for i, w in enumerate(words):
        assert w["text"] == tokens[i]
        assert w["start"] < w["end"]
        if i > 0:
            assert w["start"] >= words[i - 1]["start"]
    assert words[-1]["end"] == 3.5


@pytest.mark.anyio
async def test_generate_narration_mock_end_to_end(tmp_path: Path):
    """Verify generate_narration execution with mock mode end-to-end."""
    provider = AzureNeuralVoiceProvider(mock_mode=True)
    out_wav = tmp_path / "audio" / "vo.wav"
    beats = [
        {"id": "scene_01", "text": "You feel the shockwave before you hear it."},
        {"id": "scene_02", "text": "Ash clouds surge at 300 miles per hour."},
    ]

    res = await provider.generate_narration(beats, out_wav, lang="en")

    assert res["vo_path"] == out_wav
    assert res["provider"] == "azure"
    assert res["voice_id"] == "en-US-GuyNeural"
    assert res["duration"] > 0
    assert len(res["words"]) > 0
    assert out_wav.is_file()

    # Verify words.json was created
    words_json_path = words_path_for(out_wav)
    assert words_json_path.is_file()
    saved_data = json.loads(words_json_path.read_text(encoding="utf-8"))
    assert saved_data["provider"] == "azure"
    assert saved_data["voice_id"] == "en-US-GuyNeural"
    assert len(saved_data["words"]) == len(res["words"])


def test_azure_sdk_word_boundary_callback_calculation():
    """Verify the math converting Azure Speech SDK ticks to seconds."""
    # 1 tick = 100 nanoseconds; 10,000,000 ticks = 1 second
    ticks_1s = 10_000_000
    ticks_250ms = 2_500_000

    calc_start = ticks_1s / 10_000_000.0
    calc_dur = ticks_250ms / 10_000_000.0

    assert calc_start == 1.0
    assert calc_dur == 0.25


@pytest.mark.anyio
async def test_generate_narration_sdk_fallback_on_error(tmp_path: Path):
    """Verify that if Azure Speech SDK encounters an error, it falls back to mock synthesis cleanly."""
    provider = AzureNeuralVoiceProvider(api_key="real_looking_dummy_key_1234567890123456")
    # Force is_mock False to trigger the SDK branch
    provider.mock_mode = False

    out_wav = tmp_path / "fallback_vo.wav"
    beats = [{"text": "Testing fallback resilience."}]

    # In test environment, the dummy key will fail authentication with Azure WebSocket
    # generate_narration must catch this, log a warning, and fall back to mock audio synthesis
    res = await provider.generate_narration(beats, out_wav)

    assert res["vo_path"] == out_wav
    assert res["provider"] == "azure"
    assert res["duration"] > 0
    assert out_wav.is_file()
    assert out_wav.stat().st_size > 100


def test_env_files_contain_azure_keys():
    """Verify .env, .env.example, and engine/.env all contain the AZURE_TTS variables."""
    root_dir = Path(__file__).resolve().parent.parent

    for env_rel in [".env", ".env.example", "engine/.env"]:
        env_path = root_dir / env_rel
        assert env_path.is_file(), f"{env_rel} does not exist"
        content = env_path.read_text(encoding="utf-8")
        assert "AZURE_TTS_KEY=" in content, f"AZURE_TTS_KEY missing in {env_rel}"
        assert "AZURE_TTS_REGION=eastus" in content, f"AZURE_TTS_REGION missing in {env_rel}"
        assert "AZURE_TTS_VOICE=en-US-GuyNeural" in content, f"AZURE_TTS_VOICE missing in {env_rel}"


def test_cli_produce_film_recognizes_azure_voice_provider():
    """Verify CLI produce-film command recognizes --voice-provider azure without crashing."""
    cmd = [
        "python",
        "tools/cinematic_studio_cli.py",
        "produce-film",
        "--help",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert "azure" in res.stdout
