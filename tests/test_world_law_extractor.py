from pathlib import Path

import pytest

from engine.services.skill_loader import SkillLoader
from engine.services.world_law_extractor import capture_world_laws, load_world_rule_sets


def test_snapshot_identifies_real_selected_skills():
    snapshot = capture_world_laws(SkillLoader(), "catastrophe")
    director = next(item for item in snapshot if item.role == "director")
    assert director.slug == "catastrophe-director"
    assert len(director.sha256) == 64
    assert director.instructions


def test_missing_skill_cannot_be_reported_as_complete(tmp_path: Path):
    with pytest.raises(ValueError, match="Missing required"):
        capture_world_laws(SkillLoader(tmp_path), "catastrophe")


def test_stale_index_is_rejected(tmp_path: Path):
    source = Path(__file__).resolve().parents[1] / ".grok" / "skills"
    import shutil
    shutil.copytree(source, tmp_path / "skills")
    loader = SkillLoader(tmp_path / "skills")
    path = tmp_path / "skills" / "catastrophe-director" / "SKILL.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nChanged rule\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed since"):
        capture_world_laws(loader, "catastrophe")


def test_structured_world_rule_provenance_and_invalid_rule(tmp_path):
    import json
    import shutil
    source = Path(__file__).resolve().parents[1] / ".grok" / "skills"
    shutil.copytree(source, tmp_path / "skills")
    loader = SkillLoader(tmp_path / "skills")
    snapshot = capture_world_laws(loader, "catastrophe")
    rules = load_world_rule_sets(snapshot)
    assert rules[0].slug == "catastrophe-director"
    assert rules[0].version and len(rules[0].sha256) == 64
    assert {item["id"] for item in rules[0].rules}
    path = Path(rules[0].source)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["rules"].append(data["rules"][0])
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_world_rule_sets(snapshot)
