from engine.services.screenplay_reviewer import ScreenplayReviewer
from engine.services.screenplay_reviewer import Scorecard
from tools.cli.produce_commands import _mark_partial_review, _review_allows_render
import pytest


def _scene(narration="You survive. You subscribe.", visual="A closed door"):
    return [{"id": "scene_01", "narration": narration, "visual_prompt": visual}]


def _result(reviewer, score=1.0):
    return {
        "category_scores": {key: maximum * score for key, maximum in reviewer._holistic_rubric["categories"].items()},
        "defects": [],
    }


def test_holistic_requires_two_valid_judges_and_records_sources(monkeypatch):
    reviewer = ScreenplayReviewer(xai_api_key="fixture", screenplay_mode="holistic", short_test=True)
    monkeypatch.setattr(reviewer, "_consult_grok_critique", lambda *args: _result(reviewer))
    monkeypatch.setattr(reviewer, "_consult_gemini_critique", lambda *args: _result(reviewer, .95))
    result = reviewer.review(_scene(), consult_ai=True)
    assert result.passed and result.total_score == 95
    assert result.review_context["rubric_version"] == "holistic-v1"
    assert all(len(s["sha256"]) == 64 for s in result.review_context["skills"])
    assert not reviewer.review(_scene(), consult_ai=False).passed


def test_holistic_rejects_missing_categories_and_critical_findings(monkeypatch):
    reviewer = ScreenplayReviewer(xai_api_key="fixture", screenplay_mode="holistic", short_test=True)
    def critical(*args):
        result = _result(reviewer)
        result["defects"] = [{"scene_id": "scene_01", "category": "world_law", "severity": "critical",
                              "responsible_skill": "catastrophe-director", "rule_id": "physics",
                              "issue": "Inconsistent physics", "fix_instruction": "Recheck causality"}]
        return result
    monkeypatch.setattr(reviewer, "_consult_grok_critique", critical)
    monkeypatch.setattr(reviewer, "_consult_gemini_critique", lambda *args: _result(reviewer))
    assert not reviewer.review(_scene(), consult_ai=True).passed
    monkeypatch.setattr(reviewer, "_consult_grok_critique", lambda *args: {"category_scores": {}, "defects": []})
    assert not reviewer.review(_scene(), consult_ai=True).passed


def test_vertical_rejects_cta_and_accepts_cta_free_ending(monkeypatch):
    reviewer = ScreenplayReviewer(xai_api_key="fixture", screenplay_mode="holistic", aspect="9:16")
    monkeypatch.setattr(reviewer, "_consult_grok_critique", lambda *args: _result(reviewer))
    monkeypatch.setattr(reviewer, "_consult_gemini_critique", lambda *args: _result(reviewer))
    assert not reviewer.review(_scene(), consult_ai=True).passed
    assert reviewer.review(_scene("You survive."), consult_ai=True).passed


def test_world_rule_is_genre_scoped(monkeypatch):
    reviewer = ScreenplayReviewer(xai_api_key="fixture", screenplay_mode="holistic", short_test=True)
    monkeypatch.setattr(reviewer, "_consult_grok_critique", lambda *args: _result(reviewer))
    monkeypatch.setattr(reviewer, "_consult_gemini_critique", lambda *args: _result(reviewer))
    scenes = _scene("You see nitrogen snow at -60C. You subscribe.")
    result = reviewer.review(scenes, genre="catastrophe", consult_ai=True)
    assert not result.passed
    assert any("atmospheric-nitrogen-phase" in item for item in result.defects)
    unknown = reviewer.review(scenes, genre="unknown", consult_ai=True)
    assert not unknown.passed and unknown.review_context["director_fallback"]


@pytest.mark.parametrize("genre", ["deepsea-survival", "micro-survival", "planetary-catastrophe", "urban-infiltration"])
def test_director_profiles_review_explicit_battery_state(monkeypatch, genre):
    reviewer = ScreenplayReviewer(xai_api_key="fixture", screenplay_mode="holistic", short_test=True)
    monkeypatch.setattr(reviewer, "_consult_grok_critique", lambda *args: _result(reviewer))
    monkeypatch.setattr(reviewer, "_consult_gemini_critique", lambda *args: _result(reviewer))
    valid = reviewer.review(_scene("You see battery state of charge at 100%. You subscribe."), genre=genre, consult_ai=True)
    assert valid.passed and valid.review_context["selected_director"] == f"{genre}-director"
    rules = valid.review_context["world_rules"][0]["rules"]
    assert any(r.get("kind") == "semantic" and r.get("source_url", "").startswith("https://") for r in rules)
    assert any(r.get("kind") == "semantic" and r["id"] in reviewer._holistic_prompt for r in rules)
    invalid = reviewer.review(_scene("You see battery state of charge at 105%. You subscribe."), genre=genre, consult_ai=True)
    assert not invalid.passed
    assert any("battery-state-of-charge" in item for item in invalid.defects)
    unrelated = reviewer.review(_scene("You see battery state of charge at 80% and humidity at 150%. You subscribe."), genre=genre, consult_ai=True)
    assert not any("battery-state-of-charge" in item for item in unrelated.defects)


def test_checklist_and_simulation_cannot_certify_production():
    result = Scorecard(100, {}, passed=True, grade="Grade A+")
    _mark_partial_review(result, mode="strict-checklist", short_test=False, simulation=False)
    assert not result.passed and "UNCERTIFIED" in result.grade
    test_result = Scorecard(100, {}, passed=True)
    _mark_partial_review(test_result, mode="strict-checklist", short_test=True, simulation=False)
    assert test_result.passed
    _mark_partial_review(test_result, mode="holistic", short_test=True, simulation=True)
    assert not test_result.passed and "SIMULATION" in test_result.grade


def test_live_render_requires_passed_review_even_with_high_score():
    failed = Scorecard(100, {}, passed=False, defects=["Judge unavailable"])
    assert not _review_allows_render(failed, dry_run=False)
    assert _review_allows_render(failed, dry_run=True)
    assert not _review_allows_render(Scorecard(89, {}, passed=True), dry_run=False)
    assert _review_allows_render(Scorecard(90, {}, passed=True), dry_run=False)


def test_healer_does_not_rewrite_a_provider_outage(monkeypatch):
    from engine.services.screenplay_healer import ScreenplayHealer
    reviewer = ScreenplayReviewer(xai_api_key="fixture", screenplay_mode="holistic", short_test=True)
    healer = ScreenplayHealer(reviewer=reviewer, xai_api_key="fixture")
    monkeypatch.setattr(healer, "_heal_with_full_context_grok",
                        lambda *args, **kwargs: pytest.fail("Provider outage must not cause a rewrite"))
    initial = Scorecard(0, {}, passed=False, defects=["Gemini judge unavailable or invalid: timeout"])
    result = healer.heal(_scene(), title="fixture", genre="catastrophe", consult_ai=True,
                         initial_scorecard=initial)
    assert result.repaired_scenes == _scene()
    assert result.final_scorecard is initial


@pytest.mark.parametrize("genre,limit", [("fixture-alpha", -10), ("fixture-beta", -20), ("fixture-gamma", -30)])
def test_fixture_director_rule_profiles_are_applied(tmp_path, monkeypatch, genre, limit):
    """Fixture-only profiles verify selection and numeric checks, not scientific validity."""
    import json
    import shutil
    from pathlib import Path
    import engine.services.skill_loader as skill_loader
    source = Path(__file__).resolve().parents[1] / ".grok" / "skills"
    root = tmp_path / "skills"
    shutil.copytree(source, root)
    director = root / f"{genre}-director"
    (director / "references").mkdir(parents=True)
    (director / "SKILL.md").write_text(
        f"---\nname: {genre}-director\ndescription: Fixture director\n---\n"
        "## Rules\nSee `references/review_rules.json`.\n", encoding="utf-8")
    rules = {"version": "fixture-only-v1", "rules": [{
        "id": f"{genre}-rule", "category": "thermodynamic_sanity", "scope": "scene",
        "all_patterns": ["fixture"], "quantity_pattern": r"(-\d+)\s*C\b",
        "description": "Fixture bound for test", "violation_if_greater_than": limit, "deduction": 10,
    }]}
    (director / "references" / "review_rules.json").write_text(json.dumps(rules), encoding="utf-8")
    real_loader = skill_loader.SkillLoader
    monkeypatch.setattr(skill_loader, "SkillLoader", lambda: real_loader(root))
    reviewer = ScreenplayReviewer(xai_api_key="fixture", screenplay_mode="holistic", short_test=True)
    monkeypatch.setattr(reviewer, "_consult_grok_critique", lambda *args: _result(reviewer))
    monkeypatch.setattr(reviewer, "_consult_gemini_critique", lambda *args: _result(reviewer))
    bad = reviewer.review(_scene(f"You observe fixture -1C. You subscribe."), genre=genre, consult_ai=True)
    good = reviewer.review(_scene(f"You observe fixture -99C. You subscribe."), genre=genre, consult_ai=True)
    assert not bad.passed and any(f"{genre}-rule" in defect for defect in bad.defects)
    assert good.passed and good.review_context["selected_director"] == f"{genre}-director"
