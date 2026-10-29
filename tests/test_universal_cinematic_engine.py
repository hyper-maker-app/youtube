"""Unit test suite for Grok Imagine Cinematic Studio v4.0 Universal Cinematic Engine.

Verifies:
1. Genre archetype detection and normalizer across all 5 canonical genres.
2. 100% English Invariant, 2nd-person singular POV ("You"), and in-media-res hooks.
3. Aspect-ratio smart endings: 16:9 cliffhangers vs 9:16 seamless audio loops.
4. Text Sanitizer gateway stripping all metadata, Act/Scene markers, and bracketed cues.
5. FFmpeg Lavfi procedural synthesis across all 8 sound archetypes.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from engine.providers.sfx.ffmpeg_lavfi import FFmpegLavfiSfxProvider
from engine.services.text_sanitizer import sanitize_spoken_text
from engine.services.universal_narrative import (
    _ARCHETYPES,
    detect_genre_archetype,
    generate_universal_scenes,
)


def test_genre_archetype_detection():
    """Verify keyword mapping to canonical genre archetypes."""
    assert detect_genre_archetype("Sci-Fi").slug == "sci_fi"
    assert detect_genre_archetype("Deep Space Thriller").slug == "sci_fi"
    assert detect_genre_archetype("Cyberpunk Infiltration").slug == "cyberpunk"
    assert detect_genre_archetype("Tactical Noir Hacker").slug == "cyberpunk"
    assert detect_genre_archetype("Deep-Sea Trench").slug == "deep_sea"
    assert detect_genre_archetype("Submarine Abyssal").slug == "deep_sea"
    assert detect_genre_archetype("Medieval Siege").slug == "medieval_siege"
    assert detect_genre_archetype("Castle Knight Defense").slug == "medieval_siege"
    assert detect_genre_archetype("Survival Horror").slug == "survival_horror"
    assert detect_genre_archetype("Unknown Zombie Post-Apocalyptic").slug == "survival_horror"


@pytest.mark.parametrize("genre_slug", ["sci_fi", "cyberpunk", "deep_sea", "survival_horror", "medieval_siege"])
def test_universal_scenes_invariants(genre_slug: str):
    """Verify narrative invariants across all 5 genres."""
    archetype = _ARCHETYPES[genre_slug]
    scenes = generate_universal_scenes(
        title=f"Test {archetype.display_name}",
        genre=genre_slug,
        duration=24,
        aspect="16:9",
    )

    assert len(scenes) >= 3, f"Expected at least 3 scenes, got {len(scenes)}"

    total_duration = sum(s["duration"] for s in scenes)
    assert 20.0 <= total_duration <= 30.0

    for sc in scenes:
        narration = sc["narration"]
        assert narration, "Narration must not be empty"

        # 100% English & 2nd Person POV check
        assert any(p in narration.lower() for p in ("you", "your", "yourself")), (
            f"Scene {sc['id']} must use 2nd-person perspective: '{narration}'"
        )

        # Check for forbidden metadata markers
        assert not any(tag in narration.lower() for tag in ("act 1", "scene 0", "[sound", "(whisper")), (
            f"Scene {sc['id']} contains forbidden directive: '{narration}'"
        )

        # Verify visual prompt is enriched
        vp = sc["visual_prompt"]
        assert "zero face distortion" in vp
        assert "cinematography" in vp.lower()


def test_aspect_ratio_smart_endings():
    """Verify 16:9 cliffhanger vs 9:16 seamless audio loop."""
    # 16:9 should have high tension cliffhanger beat
    scenes_16_9 = generate_universal_scenes("Event Horizon", "Sci-Fi", duration=32, aspect="16:9")
    last_16_9 = scenes_16_9[-1]["narration"]
    assert any(w in last_16_9.lower() for w in ("blast doors", "begins to turn", "splits wide", "unseal", "flares", "laser")), (
        f"16:9 should end on dramatic cliffhanger beat: {last_16_9}"
    )

    # 9:16 should end with an open-ended loop connector ("because...")
    scenes_9_16 = generate_universal_scenes("Event Horizon", "Sci-Fi", duration=24, aspect="9:16")
    last_9_16 = scenes_9_16[-1]["narration"]
    assert last_9_16.strip().endswith("because..."), (
        f"9:16 must end on seamless audio loop hook 'because...': got '{last_9_16}'"
    )


def test_text_sanitizer_edge_cases():
    """Verify regex stripper removes all metadata directives."""
    dirty_script = (
        "Act 1: Scene 03 - [Sound of heavy sirens] You grab the wrench. "
        "(whispering) Keep your head down. Narrator: The radiation spikes [SFX: Geiger counter]."
    )
    clean = sanitize_spoken_text(dirty_script)
    assert clean == "You grab the wrench. Keep your head down. The radiation spikes."
    assert "[" not in clean and "]" not in clean
    assert "Act 1" not in clean
    assert "Narrator:" not in clean


def test_lavfi_8_archetypes_synthesis():
    """Verify that FFmpeg lavfi synthesizes all 8 procedural sound archetypes."""
    prov = FFmpegLavfiSfxProvider()
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_path = Path(tmp_dir)

        archetype_cues = [
            ("whoosh", "cinematic camera whip whoosh"),
            ("sonar_ping", "abyssal submarine sonar ping chirp"),
            ("electric_glitch", "cybernetic electric glitch burst"),
            ("valve_hiss", "pressurized airlock valve hiss depressurize"),
            ("metal_clash", "iron sword blade clash impact"),
            ("tension_heartbeat", "deep suspense tension heartbeat pulse"),
            ("wind_drone", "atmospheric dark wind drone"),
            ("sub_bass_thud", "sub-bass impact door slam"),
        ]

        async def _run_all():
            results = []
            for arc_id, prompt in archetype_cues:
                rec = await prov.resolve_asset(
                    {"prompt": prompt, "duration": 1.0, "asset_id": f"test_{arc_id}"},
                    cache_dir=cache_path,
                )
                results.append((arc_id, rec))
            return results

        results = asyncio.run(_run_all())
        assert len(results) == 8

        for arc_id, rec in results:
            wav_file = Path(rec["local_path"])
            assert wav_file.is_file(), f"WAV fixture for {arc_id} was not created"
            assert wav_file.stat().st_size > 1000, f"WAV fixture for {arc_id} is too small ({wav_file.stat().st_size} bytes)"
