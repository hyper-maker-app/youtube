from engine.services.screenplay_healer import ScreenplayHealer
from engine.services.skill_reinforcement import SkillReinforcementService


def test_skill_writes_require_explicit_opt_in(tmp_path):
    skill = tmp_path / "example" / "SKILL.md"
    skill.parent.mkdir()
    original = "# Example\n## Universal Physics & Causality Invariants\n- Existing rule\n"
    skill.write_text(original, encoding="utf-8")
    service = SkillReinforcementService(tmp_path)
    result = service.reinforce_from_defects([{
        "responsible_skill": "example", "rule_to_learn": "Another invariant"
    }])
    assert result[0]["applied"] is False
    assert skill.read_text(encoding="utf-8") == original
    assert ScreenplayHealer(xai_api_key="").reinforcement_service.allow_writes is False
    assert ScreenplayHealer(xai_api_key="", allow_skill_writes=True).reinforcement_service.allow_writes is True


def test_opted_in_write_preserves_long_skill_and_following_sections(tmp_path):
    skill = tmp_path / "example" / "SKILL.md"
    skill.parent.mkdir()
    original = ("# Example\n" + "intro\n" * 150
                + "## Universal Physics & Causality Invariants\n- Old invariant\n"
                + "## Following section\nRetain this content.\n")
    skill.write_text(original, encoding="utf-8")
    result = SkillReinforcementService(tmp_path, allow_writes=True).apply_learned_rule(
        "example", "A distinct universal invariant"
    )
    updated = skill.read_text(encoding="utf-8")
    assert result["applied"] is True
    assert "- Old invariant\n## Following section\nRetain this content.\n" in updated
    assert "A distinct universal invariant" in updated
