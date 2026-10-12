"""Unit tests for the Deepgram Flux multi-voice roster and VoiceAssigner."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from providers.voice.deepgram_aura import DeepgramAuraProvider
from services.script_engine import Beat
from services.voice_roster import (
    FEMALE_FLUX_ROSTER,
    MALE_FLUX_ROSTER,
    FluxVoice,
    VoiceAssigner,
)


def test_narrator_and_nova_retain_primary_voice():
    """Verify that narrator and host_nova always receive the primary voice."""
    assigner = VoiceAssigner(primary_voice="aura-2-hera-en")
    assert assigner.assign_voice({"role": "narrator", "text": "Hello"}) == "aura-2-hera-en"
    assert assigner.assign_voice({"role": "host_nova", "text": "Arrival"}) == "aura-2-hera-en"
    assert assigner.assign_voice(Beat(index=1, text="Look here", role="narrator")) == "aura-2-hera-en"


def test_male_round_robin_sequence():
    """Verify that sequential male auxiliary characters cycle through Cliff -> Kit -> Conor -> Donovan."""
    assigner = VoiceAssigner(primary_voice="aura-2-hera-en")
    expected_order = [v.model_id for v in MALE_FLUX_ROSTER]

    # Assign 4 distinct male entities
    v1 = assigner.assign_voice({"role": "witness:Corporal Seyit (1915)", "text": "I lifted the shell"})
    v2 = assigner.assign_voice({"role": "witness:Captain Nihat (1915)", "text": "Fire the battery"})
    v3 = assigner.assign_voice({"role": "witness:Master Baker Neo (79 AD)", "text": "The oven is ready"})
    v4 = assigner.assign_voice({"role": "witness:Marcus Vitruvius", "text": "Architecture demands strength"})

    assert [v1, v2, v3, v4] == expected_order


def test_female_round_robin_sequence():
    """Verify that sequential female auxiliary characters cycle through Hannah -> Alexis -> Maeve -> Sienna -> Bree."""
    assigner = VoiceAssigner(primary_voice="aura-2-hera-en")
    expected_order = [v.model_id for v in FEMALE_FLUX_ROSTER]

    v1 = assigner.assign_voice({"role": "witness:Queen Nefertiti", "text": "We honor the sun"})
    v2 = assigner.assign_voice({"role": "witness:Priestess of Delphi", "text": "The oracle speaks"})
    v3 = assigner.assign_voice({"role": "witness:Nene Hatun", "text": "We defended the redoubt"})
    v4 = assigner.assign_voice({"role": "witness:Valide Sultan", "text": "The court orders it"})
    v5 = assigner.assign_voice({"role": "witness:Empress Theodora", "text": "The empire endures"})

    assert [v1, v2, v3, v4, v5] == expected_order


def test_entity_voice_lock_consistency():
    """Verify that the same character appearing across multiple beats keeps the identical voice model."""
    assigner = VoiceAssigner(primary_voice="aura-2-hera-en")

    # First appearance
    v1 = assigner.assign_voice({"role": "witness:Corporal Seyit (1915)", "text": "Lifting the 215kg shell"})
    # Second appearance with slight title variation
    v2 = assigner.assign_voice({"role": "witness:Seyit Onbaşı", "text": "Loading the Krupp cannon"})
    # Third appearance with plain name
    v3 = assigner.assign_voice({"role": "witness:Seyit", "text": "Direct hit on Bouvet"})

    assert v1 == "flux-cliff-en"
    assert v2 == "flux-cliff-en"
    assert v3 == "flux-cliff-en"


def test_distinct_entities_get_distinct_voices():
    """Verify that distinct entities receive distinct voices from the pool."""
    assigner = VoiceAssigner(primary_voice="aura-2-hera-en")
    v_seyit = assigner.assign_voice({"role": "witness:Seyit Onbaşı", "text": "Shell lifted"})
    v_nihat = assigner.assign_voice({"role": "witness:Captain Nihat", "text": "Fire battery"})

    assert v_seyit != v_nihat
    assert v_seyit == "flux-cliff-en"
    assert v_nihat == "flux-kit-en"


def test_roster_pool_wraparound():
    """Verify that when the auxiliary voice pool is exhausted, it wraps around safely."""
    assigner = VoiceAssigner(primary_voice="aura-2-hera-en")
    num_males = len(MALE_FLUX_ROSTER)

    assigned = []
    for i in range(num_males + 2):
        v = assigner.assign_voice({"role": f"witness:Soldier {i}", "text": "Marching"})
        assigned.append(v)

    # Fifth male should wrap around to the first model (Cliff)
    assert assigned[num_males] == MALE_FLUX_ROSTER[0].model_id
    assert assigned[num_males + 1] == MALE_FLUX_ROSTER[1].model_id


def test_gender_detection_historical_roles():
    """Verify gender detection correctly classifies historical titles and figures."""
    assigner = VoiceAssigner(primary_voice="aura-2-hera-en")
    # Male titles
    assert assigner._detect_gender("witness:Corporal Seyit") == "male"
    assert assigner._detect_gender("witness:Captain Nihat") == "male"
    assert assigner._detect_gender("witness:Master Baker Terentius Neo") == "male"
    assert assigner._detect_gender("witness:Chief Royal Architect Neferhotep") == "male"

    # Female titles
    assert assigner._detect_gender("witness:Nene Hatun") == "female"
    assert assigner._detect_gender("witness:Valide Sultan Kösem") == "female"
    assert assigner._detect_gender("witness:Queen Hatshepsut") == "female"
    assert assigner._detect_gender("witness:Priestess of Apollo") == "female"
    assert assigner._detect_gender("witness:Empress Theodora") == "female"


def test_speak_url_endpoint_routing():
    """Verify that Flux models route to /v2/speak while Aura models route to /v1/speak."""
    provider = DeepgramAuraProvider(
        api_key="mock_key",
        base_url="https://api.deepgram.com/v1",
        voice_model="aura-2-hera-en",
        transcribe_model="nova-3",
    )
    # Aura model must use /v1/speak
    assert provider._speak_url("aura-2-hera-en") == "https://api.deepgram.com/v1/speak"
    assert provider._speak_url("aura-2-hermes-en") == "https://api.deepgram.com/v1/speak"

    # Flux model must use /v2/speak
    assert provider._speak_url("flux-cliff-en") == "https://api.deepgram.com/v2/speak"
    assert provider._speak_url("flux-hannah-en") == "https://api.deepgram.com/v2/speak"


def test_speak_url_normalizes_versioned_base_url():
    """Verify that root URL regex strips /v1 or /v2 before appending new endpoint version."""
    provider1 = DeepgramAuraProvider(
        api_key="mock_key",
        base_url="https://api.deepgram.com/v1/",
        voice_model="aura-2-hera-en",
        transcribe_model="nova-3",
    )
    assert provider1._speak_url("flux-cliff-en") == "https://api.deepgram.com/v2/speak"

    provider2 = DeepgramAuraProvider(
        api_key="mock_key",
        base_url="https://api.deepgram.com",
        voice_model="aura-2-hera-en",
        transcribe_model="nova-3",
    )
    assert provider2._speak_url("flux-cliff-en") == "https://api.deepgram.com/v2/speak"
    assert provider2._speak_url("aura-2-hermes-en") == "https://api.deepgram.com/v1/speak"


def test_legacy_mode_fallback_when_disabled():
    """Verify that when enable_flux_roster=False, legacy 2-voice witness routing is preserved."""
    provider = DeepgramAuraProvider(
        api_key="mock_key",
        base_url="https://api.deepgram.com/v1",
        voice_model="aura-2-hera-en",
        transcribe_model="nova-3",
        enable_flux_roster=False,
    )
    assert provider._voice_assigner is None
    nova_beat = Beat(index=1, text="Hello", role="host_nova")
    witness_beat = Beat(index=2, text="Witness here", role="witness:Soldier")

    assert provider._voice_for_beat(nova_beat) == "aura-2-hera-en"
    assert provider._voice_for_beat(witness_beat) == "aura-2-hermes-en"


def test_ast_cleanliness_voice_roster():
    """Verify that services/voice_roster.py contains zero network or provider imports."""
    file_path = Path("services/voice_roster.py")
    assert file_path.exists()
    tree = ast.parse(file_path.read_text(encoding="utf-8"))

    banned_modules = {"httpx", "requests", "urllib", "http.client", "aiohttp", "socket"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in banned_modules, f"Banned import found: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in banned_modules, f"Banned import-from found: {node.module}"
