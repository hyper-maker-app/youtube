"""Unit tests for Phase 1 (R1) — Video Length 4:30+ and Catastrophe Niche.

Verifies:
1. generate_universal_scenes() with duration=300 produces exactly 38 scenes (6-8s each, total 300s).
2. 5-Act narrative structure:
   - Scene 1 (0-4s): HOOK — "The moment [X] begins..."
   - Scenes 2-5 (4-40s): "What is happening / Why it matters"
   - Scenes 6-25 (40-200s): Build-up (staged destruction + numerical data)
   - Scenes 26-34 (200-270s): CLIMAX — Peak chaos
   - Scenes 35-38 (270-300s): Aftermath + Subscribe hook
3. Catastrophe genre archetype recognition and invariants.
4. Veo duration tiers conformance across all scenes.
5. 100% English, 2nd-person POV ('you', 'your').
"""

from __future__ import annotations

import re
import pytest

from engine.services.universal_narrative import (
    GENRE_CATASTROPHE,
    _ARCHETYPES,
    detect_genre_archetype,
    generate_catastrophe_scenes,
    generate_universal_scenes,
)


def test_genre_catastrophe_constant_and_detection():
    """Verify GENRE_CATASTROPHE constant and genre detection."""
    assert GENRE_CATASTROPHE == "catastrophe"
    assert "catastrophe" in _ARCHETYPES

    arch = detect_genre_archetype("catastrophe")
    assert arch.slug == "catastrophe"
    assert arch.display_name == "Procedural Catastrophe / Mega-Disaster"

    # Variations
    assert detect_genre_archetype("Supervolcano Eruption").slug == "catastrophe"
    assert detect_genre_archetype("Asteroid Impact Disaster").slug == "catastrophe"
    assert detect_genre_archetype("Mega Tsunami Catastrophe").slug == "catastrophe"


def test_300s_scene_count_and_duration():
    """Verify duration=300 produces ~38 scenes totaling exactly 300.0 seconds."""
    scenes = generate_universal_scenes(
        title="What if 1000 Volcanoes Erupted at Once",
        genre="catastrophe",
        duration=300,
        aspect="16:9",
    )

    # Acceptance criteria: planned scene count >= 34 (~38 scenes)
    assert len(scenes) >= 34
    assert len(scenes) == 38, f"Expected 38 scenes, got {len(scenes)}"

    total_duration = sum(s["duration"] for s in scenes)
    assert total_duration == 300.0, f"Expected 300.0s total, got {total_duration}"

    # Verify all durations conform to Google Veo tiers: [4.0, 6.0, 8.0, 10.0]
    valid_tiers = {4.0, 6.0, 8.0, 10.0}
    for s in scenes:
        assert s["duration"] in valid_tiers, f"Scene {s['id']} has non-Veo duration {s['duration']}"


def test_5act_structure_and_hooks():
    """Verify the 5-act narrative progression, Scene 1 HOOK, and Scene 38 subscribe hook."""
    title = "What if 1000 Volcanoes Erupted at Once"
    scenes = generate_universal_scenes(title=title, genre="catastrophe", duration=300, aspect="16:9")

    # Act 1: Scene 1 (0-4s) — HOOK: "The moment [X] begins..."
    sc1 = scenes[0]
    assert sc1["scene_number"] == 1
    assert sc1["duration"] == 4.0
    assert sc1["narration"].startswith("The moment "), f"Scene 1 must start with 'The moment ...', got: '{sc1['narration']}'"
    assert "begins" in sc1["narration"][:120], f"Scene 1 must contain 'begins', got: '{sc1['narration']}'"

    # Act 2: Scenes 2-5 (4-40s) — "What is happening / Why it matters"
    act2_scenes = scenes[1:5]
    assert len(act2_scenes) == 4
    act2_dur = sum(s["duration"] for s in act2_scenes)
    assert act2_dur == 36.0, f"Act 2 duration should be 36.0s (totaling 40s), got {act2_dur}"

    # Act 3: Scenes 6-25 (40-200s) — Build-up (staged destruction + numerical data)
    act3_scenes = scenes[5:25]
    assert len(act3_scenes) == 20
    act3_dur = sum(s["duration"] for s in act3_scenes)
    assert act3_dur == 160.0, f"Act 3 duration should be 160.0s (totaling 200s), got {act3_dur}"

    # Every scene in Act 3 must include numerical metrics
    has_numbers_pattern = re.compile(r"\b(\d+(\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|twelve|fifteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion)\b", re.I)
    for s in act3_scenes:
        assert has_numbers_pattern.search(s["narration"]), f"Scene {s['id']} missing numerical data: '{s['narration']}'"

    # Act 4: Scenes 26-34 (200-270s) — CLIMAX (Peak chaos)
    act4_scenes = scenes[25:34]
    assert len(act4_scenes) == 9
    act4_dur = sum(s["duration"] for s in act4_scenes)
    assert act4_dur == 70.0, f"Act 4 duration should be 70.0s (totaling 270s), got {act4_dur}"

    # Act 5: Scenes 35-38 (270-300s) — Aftermath + Subscribe hook
    act5_scenes = scenes[34:38]
    assert len(act5_scenes) == 4
    act5_dur = sum(s["duration"] for s in act5_scenes)
    assert act5_dur == 30.0, f"Act 5 duration should be 30.0s (totaling 300s), got {act5_dur}"

    # Scene 38 (Subscribe hook in 16:9)
    sc38 = scenes[37]
    assert sc38["scene_number"] == 38
    assert "subscribe" in sc38["narration"].lower(), f"Scene 38 must contain subscribe call to action, got: '{sc38['narration']}'"


def test_2nd_person_pov_and_invariants():
    """Verify 100% English 2nd-person POV ('you', 'your') and no forbidden markers across all 38 scenes."""
    scenes = generate_universal_scenes("What if 1000 Volcanoes Erupted at Once", "catastrophe", duration=300)
    for s in scenes:
        text = s["narration"].lower()
        assert any(p in text for p in ("you", "your", "yourself")), f"Scene {s['id']} must use 2nd-person POV: '{s['narration']}'"
        assert not any(forbidden in text for forbidden in ("act 1", "scene 0", "[sound", "(whispering)")), f"Scene {s['id']} has forbidden marker: '{s['narration']}'"
        assert s["visual_prompt"], f"Scene {s['id']} missing visual prompt"
        assert s["motion_prompt"], f"Scene {s['id']} missing motion prompt"
        assert s["camera_scale"] in {"wide", "medium", "close", "macro", "micro", "nano"}


def test_aspect_ratio_endings():
    """Verify 16:9 subscribe hook vs 9:16 loop hook for longform."""
    scenes_16_9 = generate_universal_scenes("What if 1000 Volcanoes Erupted at Once", "catastrophe", duration=300, aspect="16:9")
    assert "subscribe" in scenes_16_9[-1]["narration"].lower()

    scenes_9_16 = generate_universal_scenes("What if 1000 Volcanoes Erupted at Once", "catastrophe", duration=300, aspect="9:16")
    assert scenes_9_16[-1]["narration"].endswith("because...")


def test_generate_catastrophe_scenes_helper():
    """Verify generate_catastrophe_scenes() helper produces equivalent output."""
    scenes = generate_catastrophe_scenes("What if 1000 Volcanoes Erupted at Once", duration=300)
    assert len(scenes) == 38
    assert sum(s["duration"] for s in scenes) == 300.0
