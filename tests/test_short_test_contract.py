from engine.services.screenplay_reviewer import ScreenplayReviewer


def test_short_test_requires_cta_only_in_last_sentence():
    reviewer = ScreenplayReviewer(short_test=True)
    scenes = [{"narration": "You wait.", "visual_prompt": "A closed door"} for _ in range(5)]
    assert reviewer.review(scenes).category_scores["cta_isolation"] == 0
    scenes[-1]["narration"] = "You subscribe now. You wait."
    assert reviewer.review(scenes).category_scores["cta_isolation"] == 0
    scenes[-1]["narration"] = "You wait. You subscribe."
    assert reviewer.review(scenes).category_scores["cta_isolation"] == 15
    scenes[0]["narration"] = "You subscribe."
    assert reviewer.review(scenes).category_scores["cta_isolation"] == 0


def test_short_test_is_explicit_opt_in():
    assert ScreenplayReviewer().short_test is False
    assert ScreenplayReviewer(short_test=True).short_test is True


def test_short_test_cannot_force_render():
    from typer.testing import CliRunner
    from tools.cinematic_studio_cli import app

    result = CliRunner().invoke(app, ["produce-film", "Test", "--genre", "catastrophe",
                                      "--duration", "40", "--short-test", "--force-render"])
    assert result.exit_code == 1
    assert "cannot bypass" in result.stdout


def test_short_test_requires_both_skill_exceptions():
    import asyncio
    import pytest
    from engine.services.universal_narrative import _generate_script_async

    class Loader:
        def build_unified_system_prompt(self, **kwargs):
            return "rules"

        def load_skill_instructions(self, slug, max_chars=0):
            if slug == "catastrophe-director":
                return "For an explicitly marked short integration test only, test contract."
            return "ordinary rules"

    with pytest.raises(ValueError, match="viral-retention-director"):
        asyncio.run(_generate_script_async("Test", "catastrophe", 40, "16:9", None, Loader(), True))


def test_short_test_handoff_is_not_resumed_by_production(monkeypatch, tmp_path):
    import json
    from typer.testing import CliRunner
    from tools.cinematic_studio_cli import app
    import cli.produce_commands as commands

    monkeypatch.setattr(commands, "_ROOT", tmp_path)
    monkeypatch.setenv("XAI_API_KEY", "")
    runner = CliRunner()
    base = ["produce-film", "Isolation check", "--duration", "40"]
    test_run = runner.invoke(app, base + ["--short-test", "--dry-run", "--plan-only"])
    assert test_run.exit_code == 0, test_run.stdout
    assert "--short-test" in test_run.stdout
    test_path = tmp_path / "sequences" / "test-only-isolation-check_handoff.json"
    handoff = json.loads(test_path.read_text(encoding="utf-8"))
    assert handoff["short_test"] is True
    assert handoff["production_certified"] is False
    # Even a handoff that appears review-ready cannot cross the mode boundary.
    handoff["adversarial_review"].update(passed=True, total_score=99)
    for scene in handoff["scenes"]:
        scene.pop("simulation_only", None)
    production_path = tmp_path / "sequences" / "isolation-check_handoff.json"
    production_path.write_text(json.dumps(handoff), encoding="utf-8")
    live = runner.invoke(app, base + ["--plan-only"])
    assert live.exit_code == 1
    assert "Live authoring requires" in live.stdout


def test_unreviewed_draft_survives_qa_failure_and_is_reaudited(monkeypatch, tmp_path):
    import json
    from typer.testing import CliRunner
    from tools.cinematic_studio_cli import app
    import cli.produce_commands as commands

    monkeypatch.setattr(commands, "_ROOT", tmp_path)
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    calls = []
    scenes = [{"narration": "You wait.", "visual_prompt": "A door", "micro_math": "1 second"} for _ in range(5)]
    def author(*args, **kwargs):
        calls.append("author")
        return scenes
    def failed_review(*args, **kwargs):
        calls.append("review")
        raise RuntimeError("judge unavailable")
    monkeypatch.setattr(commands.UniversalNarrativeEngine, "generate_screenplay", author)
    monkeypatch.setattr(ScreenplayReviewer, "review", failed_review)
    args = ["produce-film", "Draft test", "--duration", "40", "--short-test", "--plan-only"]
    first = CliRunner().invoke(app, args)
    assert first.exit_code != 0
    draft = next((tmp_path / "sequences").glob("*_draft_*.json"))
    payload = json.loads(draft.read_text(encoding="utf-8"))
    assert payload["review_status"] == "not_reviewed"
    assert payload["production_certified"] is False
    assert not list((tmp_path / "sequences").glob("*_handoff.json"))
    second = CliRunner().invoke(app, args)
    assert second.exit_code != 0
    assert calls == ["author", "review", "review"]
    assert "unreviewed TEST-ONLY draft" in second.stdout
