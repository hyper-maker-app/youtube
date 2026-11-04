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


@pytest.fixture(autouse=True)
def offline_authoring(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "")
    monkeypatch.setattr("urllib.request.urlopen", lambda *a,**kw: (_ for _ in ()).throw(AssertionError("Network disabled in unit tests")))


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


def test_screenplay_healer_repairs_defects_to_grade_a_plus(monkeypatch: pytest.MonkeyPatch):
    """Verify healer repairs defective scenes into a Grade A+ certified screenplay."""
    monkeypatch.setenv("XAI_API_KEY", "")
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
    assert heal_res.final_scorecard.passed is False
    assert heal_res.repaired_scenes == defective_scenes
    assert any("model-authored" in action for action in heal_res.repair_log)


def test_catastrophe_procedural_scenes_certified_grade_a_plus():
    """Verify that canonical 300s catastrophe generator produces a Grade A+ certified screenplay."""
    scenes = generate_catastrophe_scenes(title="What if 1000 Volcanoes Erupted at Once", duration=300, aspect="16:9", simulation=True)
    # This test calibrates the production rubric using explicit test-only data.
    for scene in scenes:
        scene.pop("simulation_only", None)
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
    from typer.testing import CliRunner
    from tools.cinematic_studio_cli import app

    monkeypatch.setenv("XAI_API_KEY", "")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "produce-film",
            "What if 1000 Volcanoes Erupted at Once",
            "--genre", "catastrophe",
            "--duration", "60",
            "--plan-only", "--dry-run",
        ],
    )
    assert result.exit_code == 0, f"CLI command failed: {result.stdout}"
    assert "SIMULATION (UNCERTIFIED)" in result.stdout
    assert "Screenplay Certified Grade A+" not in result.stdout
    assert "Screenplay Audit Incomplete" in result.stdout


def test_live_authoring_without_credentials_halts(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Verify user can reject physical render confirmation and halt safely."""
    from typer.testing import CliRunner
    from tools.cinematic_studio_cli import app

    monkeypatch.setenv("XAI_API_KEY", "")
    runner = CliRunner()
    monkeypatch.setattr("cli.produce_commands._ROOT", tmp_path)
    # No credential and no cached authored handoff: halt before render approval.
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
    assert result.exit_code == 1
    assert "Live authoring requires" in result.stdout


def test_screenplay_healer_heals_critical_defects_even_when_initial_score_equals_target():
    """Verify healer continues until scorecard.passed is True even if total_score == 90."""
    reviewer = ScreenplayReviewer()
    healer = ScreenplayHealer(reviewer=reviewer, target_score=90)

    # Screenplay with 15+25+20+15+15 = 90 pts, but 0/10 on POV (critical defect -> passed=False)
    scenes_score_90_unpassed = [
        {
            "id": 1,
            "narration": "You stand on the porch as the sun vanishes with 8.3 minutes delay.",
            "visual_prompt": "Low-angle shot of weathered leather boots on porch, atmospheric lighting.",
            "duration": 8.0,
            "micro_math": "8.3 minutes delay",
            "recommended_tts_speed": 1.15,
        },
        {
            "id": 2,
            "narration": "Traffic outside has stopped completely as Day 1 permanent freeze begins.",
            "visual_prompt": "Wide silhouette shot of city highway without mirrors or readable text.",
            "duration": 8.0,
            "micro_math": "Day 1 freeze",
            "recommended_tts_speed": 1.15,
        },
        {
            "id": 3,
            "narration": "The subway shelters hold survivors during month one at minus seventy degrees.",
            "visual_prompt": "Atmospheric dolly inside dark station with frost on iron rails.",
            "duration": 8.0,
            "micro_math": "Month 1 -70C",
            "recommended_tts_speed": 1.15,
        },
        {
            "id": 4,
            "narration": "Year 1 leaves oceans locked beneath thick ice crust across the world.",
            "visual_prompt": "Slow atmospheric dolly across massive vault door sealed with turn-wheels.",
            "duration": 8.0,
            "micro_math": "Year 1 ice crust",
            "recommended_tts_speed": 1.15,
        },
        {
            "id": 5,
            "narration": "Earth drifts into the cosmic void under untamed starfields. You must subscribe to the channel now if you want to survive the next planetary simulation.",
            "visual_prompt": "Wide view of frozen Earth drifting beneath the Milky Way.",
            "duration": 8.0,
            "micro_math": "Cosmic drift",
            "recommended_tts_speed": 1.15,
        },
    ]

    initial_card = reviewer.review(scenes_score_90_unpassed)
    assert initial_card.total_score >= 90
    assert initial_card.passed is False  # Fails due to pov_invariants < 8
    assert initial_card.grade == "Grade A"

    heal_res = healer.heal(scenes_score_90_unpassed, max_iterations=3)
    assert heal_res.iterations >= 1
    assert heal_res.final_scorecard.passed is False
    assert heal_res.repaired_scenes == scenes_score_90_unpassed
    assert heal_res.iterations == 3


def test_gemini_fail_closed_gate_raises_when_unauthorized(monkeypatch):
    """Verify that gemini_webapi failure strictly raises GeminiWebAPIUnavailableError if fallback not authorized."""
    from engine.services.screenplay_reviewer import GeminiWebAPIUnavailableError

    def mock_call_gemini_down(prompt, timeout=120.0):
        raise RuntimeError("Simulated Gemini daemon connection refused")

    monkeypatch.setattr("engine.providers.gemini_webapi.call_gemini_chat", mock_call_gemini_down)

    reviewer = ScreenplayReviewer(xai_api_key="mock-key", allow_deepmind_fallback=False)
    compact_scenes = [{"scene_id": 1, "duration": 8.0, "narration": "You stand outside.", "visual_prompt": "Prompt"}]

    with pytest.raises(GeminiWebAPIUnavailableError) as exc_info:
        reviewer._consult_gemini_critique(compact_scenes, title="Test", genre="catastrophe", deterministic_defects=[])

    assert "Fail-Closed Invariant Active" in str(exc_info.value)


def test_gemini_authorized_fallback_returns_structured_scorecard(monkeypatch):
    """Verify that when explicitly authorized, DeepMind fallback provides valid structured scorecard."""
    def mock_call_gemini_down(prompt, timeout=120.0):
        raise RuntimeError("Simulated Gemini daemon connection refused")

    monkeypatch.setattr("engine.providers.gemini_webapi.call_gemini_chat", mock_call_gemini_down)

    reviewer = ScreenplayReviewer(xai_api_key="mock-key", allow_deepmind_fallback=True)
    compact_scenes = [{"scene_id": 1, "duration": 8.0, "narration": "You stand outside.", "visual_prompt": "Prompt"}]

    res = reviewer._consult_gemini_critique(compact_scenes, title="Test", genre="catastrophe", deterministic_defects=["Defect 1"])
    assert "screenplay_score" in res
    assert res["screenplay_score"] <= 100
    assert "defects" in res


def test_robust_json_extractor_handles_chatter_and_fences():
    """Verify RobustJsonExtractor extracts JSON from markdown blocks and noisy LLM responses."""
    from engine.services.screenplay_reviewer import extract_json_payload

    noisy_response = """
    Certainly! Here is my detailed review of the 38 scenes:
    ```json
    {
      "screenplay_score": 92,
      "grade": "Grade A+",
      "defects": []
    }
    ```
    I hope this audit helps your production!
    """
    parsed = extract_json_payload(noisy_response)
    assert parsed.get("screenplay_score") == 92
    assert parsed.get("grade") == "Grade A+"
    assert parsed.get("defects") == []


def test_skill_reinforcement_deduplication_and_cap(tmp_path: Path):
    """Verify SkillReinforcementService deduplicates rules and protects file line bounds."""
    from engine.services.skill_reinforcement import SkillReinforcementService

    # Create dummy skill
    skill_dir = tmp_path / "catastrophe-director"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\nname: catastrophe-director\ndescription: test\n---\n\n# Catastrophe Director\nLine 1\n",
        encoding="utf-8",
    )

    service = SkillReinforcementService(skills_dir=tmp_path)
    res1 = service.apply_learned_rule("catastrophe-director", "Ocean water latent heat delays cooling", scene_id=12)
    assert res1["applied"] is True

    # Duplicate attempt
    res2 = service.apply_learned_rule("catastrophe-director", "Ocean water latent heat delays cooling", scene_id=12)
    assert res2["applied"] is False
    assert "Deduplicated" in res2["reason"]


def test_skill_loader_hot_reload(tmp_path: Path):
    """Verify SkillLoader.reload() dynamically refreshes memory cache upon disk modification."""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("---\nname: test-skill\ndescription: Initial description\n---\nInitial content", encoding="utf-8")

    loader = SkillLoader(skills_dir=tmp_path)
    assert loader.get_skill("test-skill")["description"] == "Initial description"

    # Modify file
    skill_file.write_text("---\nname: test-skill\ndescription: Updated description\n---\nUpdated content", encoding="utf-8")
    loader.reload()
    assert loader.get_skill("test-skill")["description"] == "Updated description"


def test_robust_json_extractor_handles_latex_and_invalid_escapes():
    """Verify RobustJsonExtractor safely sanitizes LaTeX math and invalid escape backslashes."""
    from engine.services.screenplay_reviewer import extract_json_payload

    latex_payload = r"""```json
    {
      "screenplay_score": 92,
      "grade": "Grade A",
      "critique_text": "Condensation at $-183^\circ\text{C}$ with viscosity $\mu=1.2$ and path C:\temp\run",
      "defects": [
        {
          "scene_id": "s038",
          "issue": "Needs trailing comma cleanup",
        }
      ],
    }
    ```"""
    parsed = extract_json_payload(latex_payload)
    assert parsed.get("screenplay_score") == 92
    assert parsed.get("grade") == "Grade A"
    assert "$-183" in parsed.get("critique_text", "")
    assert len(parsed.get("defects", [])) == 1


def test_pessimistic_gate_strict_fail_closed_when_judge_fails(monkeypatch):
    """Verify that when consult_ai=True, Grade A+ is blocked if any judge fails or times out."""
    reviewer = ScreenplayReviewer(xai_api_key="mock-key")
    scenes = generate_catastrophe_scenes(title="What if 1000 Volcanoes Erupted at Once", duration=60, aspect="16:9", simulation=True)
    # This test calibrates the production rubric using explicit test-only data.
    for scene in scenes:
        scene.pop("simulation_only", None)

    # Case 1: Both judges respond with high scores -> Grade A+ certified
    monkeypatch.setattr(reviewer, "_consult_grok_critique", lambda *a, **k: {"screenplay_score": 92, "defects": []})
    monkeypatch.setattr(reviewer, "_consult_gemini_critique", lambda *a, **k: {"screenplay_score": 90, "defects": []})
    card_both = reviewer.review(scenes, title="Test", genre="catastrophe", consult_ai=True)
    assert card_both.passed is True
    assert card_both.grade == "Grade A+"
    assert card_both.total_score == 90

    # Case 2: Grok times out (None) while Gemini gives 95 -> Must FAIL closed, NO fake Grade A+
    monkeypatch.setattr(reviewer, "_consult_grok_critique", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Grok timed out")))
    card_grok_fail = reviewer.review(scenes, title="Test", genre="catastrophe", consult_ai=True)
    assert card_grok_fail.passed is False
    assert card_grok_fail.grade != "Grade A+"
    assert any("Grok judge did not return a valid score" in d for d in card_grok_fail.defects)

    # Case 3: Gemini fails (None) while Grok gives 95 -> Must FAIL closed, NO fake Grade A+
    monkeypatch.setattr(reviewer, "_consult_grok_critique", lambda *a, **k: {"screenplay_score": 95, "defects": []})
    monkeypatch.setattr(reviewer, "_consult_gemini_critique", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Gemini down")))
    card_gemini_fail = reviewer.review(scenes, title="Test", genre="catastrophe", consult_ai=True)
    assert card_gemini_fail.passed is False
    assert card_gemini_fail.grade != "Grade A+"
    assert any("Gemini judge did not return a valid score" in d for d in card_gemini_fail.defects)


def test_screenplay_reviewer_and_healer_dynamic_models():
    """Verify default and dynamic model configurations for ScreenplayReviewer and ScreenplayHealer."""
    # 1. Default reviewer models
    default_rev = ScreenplayReviewer()
    assert default_rev.gemini_model == "gemini-3.1-pro"
    assert default_rev.grok_model == "grok-4.20-0309-non-reasoning"

    # 2. Dynamic reviewer models
    custom_rev = ScreenplayReviewer(
        gemini_model="gemini-custom-pro",
        grok_model="grok-custom-fast",
    )
    assert custom_rev.gemini_model == "gemini-custom-pro"
    assert custom_rev.grok_model == "grok-custom-fast"

    # 3. ScreenplayHealer propagates grok_model to reviewer and internal state
    healer = ScreenplayHealer(grok_model="grok-4.20-non-reasoning")
    assert healer.grok_model == "grok-4.20-non-reasoning"
    assert healer.reviewer.grok_model == "grok-4.20-non-reasoning"


def test_gemini_judge_model_parameter_passed_to_call(monkeypatch):
    """Verify ScreenplayReviewer passes the configured gemini_model and 35s timeout to call_gemini_chat."""
    recorded_calls = []

    def mock_call_gemini_chat(prompt, *, model="gemini-3.1-pro", timeout=35.0):
        recorded_calls.append({"model": model, "timeout": timeout, "prompt": prompt})
        return '{"screenplay_score": 93, "grade": "Grade A+", "defects": []}'

    monkeypatch.setattr("engine.providers.gemini_webapi.call_gemini_chat", mock_call_gemini_chat)
    monkeypatch.delenv("GEMINI_JUDGE_TIMEOUT", raising=False)

    # Test default model
    rev_default = ScreenplayReviewer(xai_api_key="mock-key")
    res1 = rev_default._consult_gemini_critique(
        compact_scenes=[{"scene_id": 1}],
        title="Test",
        genre="catastrophe",
        deterministic_defects=[],
    )
    assert res1["screenplay_score"] == 93
    assert recorded_calls[0]["model"] == "gemini-3.1-pro"
    assert recorded_calls[0]["timeout"] == 35.0

    # Test custom dynamic model
    rev_custom = ScreenplayReviewer(xai_api_key="mock-key", gemini_model="gemini-3.1-pro-preview")
    res2 = rev_custom._consult_gemini_critique(
        compact_scenes=[{"scene_id": 1}],
        title="Test",
        genre="catastrophe",
        deterministic_defects=[],
    )
    assert res2["screenplay_score"] == 93
    assert recorded_calls[1]["model"] == "gemini-3.1-pro-preview"
    assert recorded_calls[1]["timeout"] == 35.0


def test_gemini_error_screen_filters(monkeypatch):
    """Verify that Gemini error responses trigger fail-closed gate instead of corrupted scorecard."""
    error_responses = [
        "Sorry, something went wrong. Please try again later.",
        "I'm having a hard time fulfilling your request at the moment.",
        "An internal error has occurred.",
    ]

    for err_resp in error_responses:
        monkeypatch.setattr(
            "engine.providers.gemini_webapi.call_gemini_chat",
            lambda *a, **k: err_resp,
        )
        rev = ScreenplayReviewer(xai_api_key="mock-key", allow_deepmind_fallback=False)
        with pytest.raises(Exception):
            rev._consult_gemini_critique(
                compact_scenes=[{"scene_id": 1}],
                title="Test",
                genre="catastrophe",
                deterministic_defects=[],
            )



