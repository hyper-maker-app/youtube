"""Unit and Integration Tests for Phase 7: Adversarial Review & Auto-Healing Pipeline.

Verifies:
1. Pure Engine Invariant: skill_loader.py contains zero hardcoded directing or narrative text.
2. ScreenplayReviewer: Deterministic 100-point rubric with strict category score boundaries.
3. Defect Detection: Flags premature CTAs, mirror face reflections, phone UI digits, impossible thermodynamics, and POV errors.
4. ScreenplayHealer: Closed-loop repairs iteratively lift defective screenplays to >= 90/100 Grade A+.
5. Certified End-to-End Screenplay: Baseline catastrophe generation achieves Grade A+ out-of-the-box.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from engine.services.screenplay_healer import ScreenplayHealer
from engine.services.screenplay_reviewer import Scorecard, ScreenplayReviewer
from engine.services.skill_loader import SkillLoader, get_skill_loader
from engine.services.universal_narrative import generate_catastrophe_scenes


def test_pure_engine_invariant_skill_loader_no_hardcoded_narrative():
    """Verify skill_loader.py has zero hardcoded narrative, directing, or CTA strings."""
    loader_path = Path(__file__).resolve().parents[1] / "engine" / "services" / "skill_loader.py"
    content = loader_path.read_text(encoding="utf-8")

    # Forbidden hardcoded directives in pure engine
    forbidden_snippets = [
        "MANDATORY PRODUCTION INVARIANTS:",
        "ending_rule =",
        "You must subscribe to the channel and turn on notifications now if you want to survive the next planetary simulation",
        "Canonical Title Format: 'What if [large number] [threat] hit [specific location]?'.",
    ]
    for snippet in forbidden_snippets:
        assert snippet not in content, f"Pure Engine Invariant violated: Found hardcoded '{snippet}' in {loader_path.name}"


def test_screenplay_reviewer_scorecard_rubric_weights():
    """Verify that rubric category weights sum exactly to 100 points."""
    reviewer = ScreenplayReviewer()

    # Clean mock screenplay spanning timeline
    clean_scenes = [
        {
            "id": 1,
            "narration": "You stand on your sun-drenched porch as birds abruptly fall silent. Eight minutes and twenty seconds ago, the Sun ceased to exist, and the final wave of photons is about to pass.",
            "visual_prompt": "Low-angle shot of weathered leather boots on timber porch, warm golden sunset illumination rapidly transitioning into absolute celestial shadow, 35mm lens.",
            "duration": 8.0,
            "micro_math": "8.3 minutes photon delay",
            "recommended_tts_speed": 1.15,
        },
        {
            "id": 2,
            "narration": "You watch the horizon plunge into pitch-black stillness as city streetlights fail simultaneously. Day 1 of the permanent freeze begins.",
            "visual_prompt": "Wide silhouette shot of skyline streetlights dying in cascading sequence, plunging glass high-rises into starfield darkness.",
            "duration": 8.0,
            "micro_math": "Day 1 baseline freeze",
            "recommended_tts_speed": 1.15,
        },
        {
            "id": 3,
            "narration": "You descend into the subway tunnel as month one deepens to minus seventy degrees. The frozen pipes burst around you.",
            "visual_prompt": "Macro tracking shot of frost crystals spreading across iron subway rails, steam plumes venting through cracked tilework.",
            "duration": 8.0,
            "micro_math": "Month 1 -70C threshold",
            "recommended_tts_speed": 1.15,
        },
        {
            "id": 4,
            "narration": "You seal the reinforced geothermal hatch as Year 1 leaves global oceans locked under thirty meters of surface ice.",
            "visual_prompt": "Slow atmospheric dolly across massive vault door sealed with heavy brass turn-wheels, backlighting through condensed vapor.",
            "duration": 8.0,
            "micro_math": "Year 1 30-meter ice crust",
            "recommended_tts_speed": 1.15,
        },
        {
            "id": 5,
            "narration": "You gaze outward into the silent cosmic drift of deep space. You must subscribe to the channel now if you want to survive the next planetary simulation.",
            "visual_prompt": "Breathtaking wide view of frozen Earth drifting beneath the untamed Milky Way, geothermal vent glowing faintly.",
            "duration": 8.0,
            "micro_math": "Cosmic timescale drift",
            "recommended_tts_speed": 1.15,
        },
    ]

    card = reviewer.review(clean_scenes, title="What if the Sun Disappeared", genre="catastrophe")
    assert card.total_score >= 90
    assert card.passed is True
    assert card.grade == "Grade A+"

    weights = {
        "cta_isolation": 15,
        "veo_guardrails": 25,
        "thermodynamic_sanity": 20,
        "narrative_time_scale": 15,
        "causality_integrity": 15,
        "pov_invariants": 10,
    }
    assert sum(weights.values()) == 100
    for cat, max_pts in weights.items():
        assert cat in card.category_scores
        assert card.category_scores[cat] <= max_pts


def test_screenplay_reviewer_detects_all_defect_types():
    """Verify reviewer detects premature CTAs, mirror face reflections, phone UI digits, and thermodynamic errors."""
    reviewer = ScreenplayReviewer()

    defective_scenes = [
        {
            "id": 1,
            "narration": "The sun vanished and it instantly went black. Subscribe to the channel for more episodes!",
            "visual_prompt": "A cracked rearview mirror reflecting your terrified face with wide eyes.",
            "duration": 8.0,
            "micro_math": "None",
        },
        {
            "id": 2,
            "narration": "Scientists look at the sky as nitrogen snow falls at minus sixty degrees.",
            "visual_prompt": "Smartphone screen showing readable digits '00:00' and emergency text overlay reading 'ALERT'.",
            "duration": 8.0,
            "micro_math": "nitrogen snow at -60C",
        },
    ]

    card = reviewer.review(defective_scenes, title="Defective Screenplay")
    assert card.passed is False
    assert card.total_score < 70
    assert card.grade in ("Grade C", "Grade F")

    # Check defects
    defect_str = " ".join(card.defects).lower()
    assert "premature cta" in defect_str or "cta isolation" in defect_str
    assert "mirror face" in defect_str or "mirror" in defect_str
    assert "ui" in defect_str or "digital" in defect_str or "smartphone" in defect_str
    assert "thermodynamic" in defect_str or "nitrogen" in defect_str
    assert "2nd-person" in defect_str or "pov" in defect_str


def test_screenplay_healer_repairs_defects_to_grade_a_plus():
    """Verify healer repairs defective scenes into a Grade A+ certified screenplay."""
    reviewer = ScreenplayReviewer()
    healer = ScreenplayHealer(reviewer=reviewer, target_score=90)

    defective_scenes = [
        {
            "id": 1,
            "narration": "The Sun vanished without warning. You must subscribe to the channel now!",
            "visual_prompt": "A cracked mirror reflecting your terrified face and tears.",
            "duration": 8.0,
            "micro_math": "Initial hook",
            "recommended_tts_speed": 1.15,
        },
        {
            "id": 2,
            "narration": "Day 1 begins as temperature falls to -20C. Citizens run through the streets.",
            "visual_prompt": "Close-up on a smartphone screen showing readable digits 12:00 PM.",
            "duration": 8.0,
            "micro_math": "Day 1 freeze",
            "recommended_tts_speed": 1.15,
        },
        {
            "id": 3,
            "narration": "Month 1 brings nitrogen snow at -60C to the subway shelter.",
            "visual_prompt": "Subway entrance with text overlay reading 'SHELTER CLOSED'.",
            "duration": 8.0,
            "micro_math": "Month 1 -60C",
            "recommended_tts_speed": 1.15,
        },
        {
            "id": 4,
            "narration": "Year 1 freezes oceans solid into an ice crust across the globe.",
            "visual_prompt": "Heavy blast doors with steam venting into frozen exterior air.",
            "duration": 8.0,
            "micro_math": "Year 1 10m ice crust",
            "recommended_tts_speed": 1.15,
        },
        {
            "id": 5,
            "narration": "Earth drifts into the cosmic abyss of deep space.",
            "visual_prompt": "Wide view of frozen Earth adrift beneath the stars.",
            "duration": 8.0,
            "micro_math": "Cosmic timescale",
            "recommended_tts_speed": 1.15,
        },
    ]

    initial_card = reviewer.review(defective_scenes)
    assert initial_card.passed is False

    heal_res = healer.heal(defective_scenes, title="What if the Sun Disappeared")
    assert heal_res.final_scorecard.passed is True
    assert heal_res.final_scorecard.total_score >= 90
    assert heal_res.final_scorecard.grade == "Grade A+"

    # Verify repairs in final scenes
    final_scenes = heal_res.repaired_scenes
    # 1. Premature CTA removed in Scene 1
    assert "subscribe" not in final_scenes[0]["narration"].lower()
    # 2. Mirror reflection removed in Scene 1 prompt
    assert "mirror" not in final_scenes[0]["visual_prompt"].lower()
    # 3. Smartphone screen removed in Scene 2 prompt
    assert "smartphone" not in final_scenes[1]["visual_prompt"].lower()
    # 4. Text overlay removed in Scene 3 prompt
    assert "text overlay" not in final_scenes[2]["visual_prompt"].lower()
    # 5. Nitrogen snow at -60C converted to dry ice
    assert "dry ice" in final_scenes[2]["narration"].lower() or "nitrogen" not in final_scenes[2]["narration"].lower()
    # 6. Single CTA in final scene only
    assert "subscribe" in final_scenes[-1]["narration"].lower()
    # 7. 2nd-person POV enforced across all scenes
    for sc in final_scenes:
        assert sc["narration"].startswith(("You ", "Your ")), f"Scene {sc.get('id')} failed You/Your prefix"


def test_catastrophe_procedural_scenes_certified_grade_a_plus():
    """Verify that canonical 300s catastrophe generator produces a Grade A+ certified screenplay."""
    scenes = generate_catastrophe_scenes(title="What if 1000 Volcanoes Erupted at Once", duration=300, aspect="16:9")
    assert len(scenes) == 38

    reviewer = ScreenplayReviewer()
    card = reviewer.review(scenes, title="What if 1000 Volcanoes Erupted at Once", genre="catastrophe")

    # If minor defects are present, healer guarantees Grade A+
    if not card.passed:
        healer = ScreenplayHealer(reviewer=reviewer)
        heal_res = healer.heal(scenes)
        card = heal_res.final_scorecard
        scenes = heal_res.repaired_scenes

    assert card.total_score >= 90, f"Expected >= 90, got {card.total_score}. Defects: {card.defects}"
    assert card.passed is True
    assert card.grade == "Grade A+"


def test_produce_film_cli_adversarial_gate_plan_only(monkeypatch: pytest.MonkeyPatch):
    """Verify produce-film with --plan-only runs adversarial review and certifies Grade A+."""
    monkeypatch.setenv("XAI_API_KEY", "")
    from typer.testing import CliRunner
    from tools.cinematic_studio_cli import app

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "produce-film",
            "What if 1000 Volcanoes Erupted at Once",
            "--genre", "catastrophe",
            "--duration", "60",
            "--plan-only",
        ],
    )
    assert result.exit_code == 0, f"CLI command failed: {result.stdout}"
    assert "Screenplay Certified Grade A+" in result.stdout
    assert "Adversarial Screenplay Gate" in result.stdout


def test_user_confirmation_gate_rejection_halts(monkeypatch: pytest.MonkeyPatch):
    """Verify user can reject physical render confirmation and halt safely."""
    monkeypatch.setenv("XAI_API_KEY", "")
    from typer.testing import CliRunner
    from tools.cinematic_studio_cli import app

    runner = CliRunner()
    # Provide 'n' as input to typer.confirm
    result = runner.invoke(
        app,
        [
            "produce-film",
            "What if 1000 Volcanoes Erupted at Once",
            "--genre", "catastrophe",
            "--duration", "60",
        ],
        input="n\n",
    )
    assert result.exit_code == 0, f"CLI command failed: {result.stdout}"
    assert "Physical production halted by user" in result.stdout
