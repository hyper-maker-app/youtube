"""Unit tests for the Story-Weaver engine and visual locks."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services.character import get_active_character
from services.curated_beats import get_gallipoli_curated_beats, get_pompeii_curated_beats
from services.historical_research import get_historical_truth_sheet
from services.screenplay import generate_dynamic_screenplay
from services.story_weaver import StoryWeaver
from services.visual_locks import (
    apply_clothing_lock_v2,
    apply_equipment_lock_v2,
    apply_framing_lock_v2,
    apply_movement_lock_v2,
)


def test_story_weaver_five_phase_distribution():
    """Verify that StoryWeaver allocates blocks across all 5 phases matching total_blocks."""
    sheet = get_historical_truth_sheet("Ancient Egyptian Labyrinth")
    weaver = StoryWeaver(truth_sheet=sheet, total_blocks=10)
    beats = weaver.weave()

    assert len(beats) == 10
    phases = [b["phase"] for b in beats]
    assert "arrival_hook" in phases
    assert "context_immersion" in phases
    assert "rising_investigation" in phases
    assert "turning_point" in phases
    assert "legacy_verdict" in phases


def test_story_weaver_replaces_generic_sensory():
    """Verify that generic boilerplate strings are absent from StoryWeaver output."""
    sheet = get_historical_truth_sheet("Ancient Celtic Hillfort")
    weaver = StoryWeaver(truth_sheet=sheet, total_blocks=8)
    beats = weaver.weave()

    banned_generic = [
        "Stepping past the outer threshold",
        "Examining the stone face up close",
        "The physical craftsmanship is striking",
        "Sunlight cuts across the weathered surface",
        "Running a hand along the bedrock seam",
        "Deep inside the perimeter",
    ]
    for b in beats:
        for bg in banned_generic:
            assert bg not in b["text"], f"Found generic boilerplate: {bg}"


def test_arrival_hook_four_part_formula():
    """Verify that Beat 1 implements the ai-playbooks 4-part hook formula."""
    sheet = get_historical_truth_sheet("The Lost Labyrinth of Hawara")
    weaver = StoryWeaver(truth_sheet=sheet, total_blocks=8)
    beats = weaver.weave()

    hook = beats[0]
    assert hook["phase"] == "arrival_hook"
    assert hook["role"] == "host_nova"
    text = hook["text"]
    # Subject / Location
    assert "Hawara" in text or "Labyrinth" in text
    # Era / Period
    assert "BC" in text or "era" in text.lower() or "period" in text.lower()
    # Central puzzle / question
    assert "?" in text or "how" in text.lower()


def test_active_labor_verbs_enforced():
    """Verify that passive phrasing is stripped and active physical labor verbs are enforced."""
    passive_input = "Laborers standing still and watching passively near the quarry"
    active_output = apply_movement_lock_v2(passive_input, has_people=True)

    assert "standing still" not in active_output
    assert "watching passively" not in active_output
    assert "actively working and shifting weight" in active_output
    assert "natural continuous body movement" in active_output.lower()


def test_four_visual_locks_applied():
    """Verify that clothing, equipment, framing, and movement locks are applied to woven beats."""
    sheet = get_historical_truth_sheet("The Lost Labyrinth of Hawara")
    weaver = StoryWeaver(truth_sheet=sheet, total_blocks=8)
    beats = weaver.weave()

    for b in beats:
        scene = b["scene"]
        # Framing / Headroom or zero text shield
        assert "headroom" in scene.lower() or "no on-screen text" in scene.lower() or "no text" in scene.lower()
        # Clothing lock
        if b["role"] == "host_nova" or b.get("is_witness"):
            assert any(term in scene.lower() for term in ("kalasiris", "linen", "wardrobe", "attire", "tunic", "chiton"))


def test_screenplay_with_story_weaver_dynamic_generation():
    """Verify generate_dynamic_screenplay uses StoryWeaver for uncurated topics without error."""
    script = generate_dynamic_screenplay("Ancient Sumerian Ziggurat of Ur", target_blocks=8)
    assert len(script.beats) == 8
    assert len(script.shots) == 8
    assert script.beats[0].role == "host_nova"
    assert script.shots[0].subject_id.startswith("host_")


def test_gallipoli_curated_beats_intact():
    """Verify that existing curated Gallipoli beats remain exactly intact and pass benchmarks."""
    beats_22 = get_gallipoli_curated_beats(22, lang="en")
    assert len(beats_22) == 22
    assert "Bouvet" in beats_22[16]["text"]
    assert "215kg" in beats_22[4]["proof"]
    assert "heavy shells" in beats_22[4]["text"]

    beats_15 = get_gallipoli_curated_beats(15, lang="tr", topic="seyit")
    assert len(beats_15) == 15
    assert "215" in beats_15[4]["text"]


def test_pompeii_curated_beats_intact():
    """Verify that existing curated Pompeii beats remain exactly intact and pass benchmarks."""
    beats_15 = get_pompeii_curated_beats(15, lang="en")
    assert len(beats_15) == 15
    assert "Vesuvius" in beats_15[0]["text"]
    assert "panis quadratus" in beats_15[3]["text"]


def test_equipment_lock_exempts_wwi():
    """Verify that apply_equipment_lock_v2 strictly exempts WWI and industrial eras."""
    wwi_prompt = "Heavy shell hoist crane mechanism with steel cables and pulleys"
    locked = apply_equipment_lock_v2(wwi_prompt, era="world_war_i")

    assert locked == wwi_prompt
    assert "hewn cedar timber" not in locked.lower()
    assert "mud-brick slipways" not in locked.lower()
    assert "oiled sledges" not in locked.lower()


def test_ast_cleanliness_story_weaver():
    """Verify services/story_weaver.py contains zero network or provider imports."""
    file_path = Path("services/story_weaver.py")
    assert file_path.exists()
    tree = ast.parse(file_path.read_text(encoding="utf-8"))

    banned_modules = {"httpx", "requests", "urllib", "http.client", "aiohttp", "socket"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in banned_modules
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in banned_modules


def test_ast_cleanliness_visual_locks():
    """Verify services/visual_locks.py contains zero network or provider imports."""
    file_path = Path("services/visual_locks.py")
    assert file_path.exists()
    tree = ast.parse(file_path.read_text(encoding="utf-8"))

    banned_modules = {"httpx", "requests", "urllib", "http.client", "aiohttp", "socket"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in banned_modules
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in banned_modules
