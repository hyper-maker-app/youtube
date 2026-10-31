"""Unit tests for Phase 3 (R3) — Procedural Catastrophe Niche.

Verifies:
1. GENRE_CATASTROPHE = "catastrophe" constant is properly defined and exported.
2. Title format standardization helpers:
   - format: "What if [large number] [threat] hit [specific location]?"
   - standardize_catastrophe_title()
   - format_catastrophe_title()
   - is_catastrophe_title()
3. generate_catastrophe_scenes() is callable and produces structured scenes:
   - 300s duration produces exactly 38 scenes totaling 300.0s.
   - Arbitrary durations (e.g. 60s) supported with Google Veo tiers.
4. Strict 2nd-person singular perspective:
   - EVERY scene's spoken voiceover narration starts with "You " or "Your ".
   - Zero 3rd-person narration or forbidden directives.
5. Micro-mathematics required:
   - Scene 1 narration contains "At 5,000°C — 200x hotter than your oven".
   - Every scene has 'micro_math' metadata field with concrete metrics.
6. Recommended TTS speed metadata:
   - Every scene contains 'recommended_tts_speed' strictly within [1.12, 1.18].
7. Aspect-aware smart endings:
   - 16:9 cliffhanger / subscribe hook.
   - 9:16 seamless audio loop ("because...").
8. LLM catastrophe system prompt builder:
   - build_llm_catastrophe_system_prompt() enforces all R3 invariants.
   - build_llm_genre_system_prompt() delegates for catastrophe.
"""

from __future__ import annotations

import re
import pytest

from engine.services.universal_narrative import (
    GENRE_CATASTROPHE,
    __all__ as narrative_all,
    build_llm_catastrophe_system_prompt,
    build_llm_genre_system_prompt,
    detect_genre_archetype,
    format_catastrophe_title,
    generate_catastrophe_scenes,
    is_catastrophe_title,
    standardize_catastrophe_title,
)
from tools.cli.produce_commands import generate_local_3act_scenes


def test_genre_catastrophe_exported():
    """Verify GENRE_CATASTROPHE is defined and present in __all__."""
    assert GENRE_CATASTROPHE == "catastrophe"
    assert "GENRE_CATASTROPHE" in narrative_all
    assert "generate_catastrophe_scenes" in narrative_all
    assert "build_llm_catastrophe_system_prompt" in narrative_all
    assert "standardize_catastrophe_title" in narrative_all
    assert "format_catastrophe_title" in narrative_all
    assert "is_catastrophe_title" in narrative_all


def test_title_standardization_and_formatting():
    """Verify title standardization and canonical template formatting."""
    # Canonical format: "What if [large number] [threat] hit [specific location]?"
    formatted = format_catastrophe_title(threat="Supervolcanoes", number=1000, location="Earth")
    assert formatted == "What if 1000 Supervolcanoes Hit Earth?"
    assert is_catastrophe_title(formatted)

    # Standardize already-conforming titles
    t1 = standardize_catastrophe_title("What if 1000 Volcanoes Erupted at Once")
    assert t1.startswith("What if 1000 Volcanoes Erupted at Once")
    assert is_catastrophe_title(t1)

    t2 = standardize_catastrophe_title("what if 500 asteroids hit new york city?")
    assert t2 == "What if 500 asteroids hit new york city?"
    assert is_catastrophe_title(t2)

    # Standardize unstructured titles
    t3 = standardize_catastrophe_title("Volcanoes")
    assert "What if" in t3
    assert "Volcanoes" in t3
    assert is_catastrophe_title(t3)

    t4 = standardize_catastrophe_title("1000 Supervolcanoes Erupting")
    assert t4 == "What if 1000 Supervolcanoes Erupting Hit Earth?"
    assert is_catastrophe_title(t4)

    # Empty / None fallback
    assert standardize_catastrophe_title("") == "What if 1000 Volcanoes Hit Earth?"
    assert not is_catastrophe_title("")


def test_generate_catastrophe_scenes_callable_and_totals():
    """Verify generate_catastrophe_scenes is directly callable and produces 38 scenes totaling 300s."""
    scenes = generate_catastrophe_scenes(
        title="What if 1000 Volcanoes Erupted at Once",
        duration=300,
        aspect="16:9",
    )

    assert isinstance(scenes, list)
    assert len(scenes) == 38
    total_dur = sum(s["duration"] for s in scenes)
    assert total_dur == 300.0

    valid_tiers = {4.0, 6.0, 8.0, 10.0}
    for s in scenes:
        assert s["duration"] in valid_tiers, f"Scene {s['id']} duration {s['duration']} not in Veo tiers"


def test_strict_2nd_person_narration_starts_with_you_or_your():
    """Verify EVERY scene's spoken voiceover narration starts with 'You ' or 'Your '."""
    scenes = generate_catastrophe_scenes(
        title="What if 1000 Volcanoes Erupted at Once",
        duration=300,
        aspect="16:9",
    )

    for s in scenes:
        narration = s["narration"]
        assert narration.startswith(("You ", "Your ")), (
            f"Scene {s['id']} does NOT start with 'You ' or 'Your ': '{narration}'"
        )
        # Check no 3rd person narrator subjects at start
        assert not re.match(r"^(He|She|They|The narrator|Scientists|People|Citizens)\b", narration, re.I)
        # Check no forbidden audio metadata tokens
        assert not any(f in narration.lower() for f in ("act 1", "scene 0", "[sound", "(whispering)"))


def test_micro_mathematics_in_narration_and_metadata():
    """Verify micro-mathematics are present in narration text and 'micro_math' metadata."""
    scenes = generate_catastrophe_scenes(
        title="What if 1000 Volcanoes Erupted at Once",
        duration=300,
        aspect="16:9",
    )

    # Scene 1 must explicitly include oven temperature comparison
    sc1 = scenes[0]
    assert "At 5,000°C — 200x hotter than your oven" in sc1["narration"], (
        f"Scene 1 missing required oven comparison: '{sc1['narration']}'"
    )
    assert "5,000°C" in sc1["micro_math"]
    assert "200x" in sc1["micro_math"]

    # Every single scene must have non-empty micro_math metadata
    has_metrics = re.compile(
        r"(\d+(\.\d+)?|°C|PSI|ATM|dB|km/h|mph|G|tons|tons/m²|ppm|millibars|lux|meters|km|ft|hours|minutes|seconds|%)",
        re.I,
    )
    for s in scenes:
        assert "micro_math" in s, f"Scene {s['id']} missing 'micro_math' field"
        assert len(s["micro_math"].strip()) > 5, f"Scene {s['id']} 'micro_math' too short"
        assert has_metrics.search(s["micro_math"]), f"Scene {s['id']} micro_math missing metrics: '{s['micro_math']}'"


def test_recommended_tts_speed_metadata():
    """Verify all scenes specify recommended_tts_speed between 1.12 and 1.18."""
    scenes = generate_catastrophe_scenes(
        title="What if 1000 Volcanoes Erupted at Once",
        duration=300,
        aspect="16:9",
    )

    for s in scenes:
        assert "recommended_tts_speed" in s, f"Scene {s['id']} missing 'recommended_tts_speed'"
        speed = s["recommended_tts_speed"]
        assert isinstance(speed, (int, float))
        assert 1.12 <= speed <= 1.18, f"Scene {s['id']} speed {speed} outside [1.12, 1.18]"


def test_aspect_ratio_endings_catastrophe():
    """Verify 16:9 subscribe cliffhanger vs 9:16 seamless audio loop."""
    scenes_16_9 = generate_catastrophe_scenes(
        title="What if 1000 Volcanoes Erupted at Once",
        duration=300,
        aspect="16:9",
    )
    last_16_9 = scenes_16_9[-1]["narration"].lower()
    assert last_16_9.startswith("you must subscribe")
    assert "subscribe" in last_16_9

    scenes_9_16 = generate_catastrophe_scenes(
        title="What if 1000 Volcanoes Erupted at Once",
        duration=300,
        aspect="9:16",
    )
    last_9_16 = scenes_9_16[-1]["narration"]
    assert last_9_16.startswith("You must subscribe")
    assert last_9_16.endswith("because...")


def test_shortform_catastrophe_duration():
    """Verify catastrophe generator supports compact shortform durations (e.g. 60s)."""
    scenes = generate_catastrophe_scenes(
        title="What if 1000 Volcanoes Erupted at Once",
        duration=60,
        aspect="16:9",
    )

    assert len(scenes) >= 5
    total_dur = sum(s["duration"] for s in scenes)
    assert total_dur == 60.0

    for s in scenes:
        assert s["narration"].startswith(("You ", "Your ")), f"Scene {s['id']} does not start with You/Your"
        assert "micro_math" in s
        assert 1.12 <= s["recommended_tts_speed"] <= 1.18


def test_build_llm_catastrophe_system_prompt():
    """Verify LLM catastrophe system prompt builder enforces all R3 requirements."""
    prompt = build_llm_catastrophe_system_prompt(
        title="What if 1000 Volcanoes Erupted at Once",
        duration=300,
        aspect="16:9",
    )

    assert "What if [large number] [threat] hit [specific location]?" in prompt
    assert "2nd-Person Singular" in prompt
    assert "'You ' or 'Your '" in prompt
    assert "5,000°C" in prompt
    assert "micro_math" in prompt
    assert "1.12 and 1.18" in prompt or "1.12–1.18" in prompt

    # Verify build_llm_genre_system_prompt delegates when genre="catastrophe"
    genre_prompt = build_llm_genre_system_prompt("What if 1000 Volcanoes Erupted at Once", "catastrophe", 300)
    assert "'You ' or 'Your '" in genre_prompt
    assert "micro_math" in genre_prompt


def test_produce_commands_generate_local_3act_scenes_integration():
    """Verify produce_commands.generate_local_3act_scenes routes catastrophe genre properly."""
    scenes = generate_local_3act_scenes("What if 1000 Volcanoes Erupted at Once", genre="catastrophe", duration=300)
    assert len(scenes) == 38
    assert scenes[0]["narration"].startswith(("You ", "Your "))
    assert "micro_math" in scenes[0]
    assert 1.12 <= scenes[0]["recommended_tts_speed"] <= 1.18
