"""Unit and integration test suite for Phase 6 (R6) — Skill Files + QA Improvement & Final Integration.

Verifies:
1. Skill files compliance:
   - .grok/skills/catastrophe-director/SKILL.md
   - .grok/skills/thumbnail-designer/SKILL.md
   - .grok/skills/youtube-factory/SKILL.md
   - Strict YAML frontmatter (name, description single-line, no colons/angle brackets, length < 1024)
   - Zero README.md or CHANGELOG.md in skill folders
   - Model Layer (Grok 4.6) block present with model_compatibility
   - Skills registered in scripts/required_skills.manifest
2. Boundary Inspector updates:
   - TRANSITION_SCORE_THRESHOLD == 0.80
   - BoundaryQAReport.to_dict() produces valid serializable dictionary
   - write_qa_report() writes comprehensive qa_report.json with failed_transitions logs
   - inspect_transition_boundary() accepts report_path and persists report
3. SFX Auto-Categorization:
   - extract_sfx_category() extracts explosion, tsunami_water, alarm_siren, earthquake_rumble, etc.
   - Generated audiogen prompts match project specification
   - auto_categorize_scene_sfx() creates timed cues schedule
   - FFmpegLavfiSfxProvider synthesizes catastrophe sound recipes
4. Full Integration verification:
   - scripts/verify_cinematic_studio.py execution succeeds
   - out/<project>/qa_report.json structure and threshold verification
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
if str(ROOT / "engine") not in sys.path:
    sys.path.insert(0, str(ROOT / "engine"))

from engine.providers.sfx.ffmpeg_lavfi import FFmpegLavfiSfxProvider
from engine.services.boundary_inspector import (
    TRANSITION_SCORE_THRESHOLD,
    BoundaryQAReport,
    inspect_transition_boundary,
    write_qa_report,
)
from engine.services.sfx_categorizer import (
    SfxCategoryMatch,
    auto_categorize_scene_sfx,
    extract_sfx_category,
    get_supported_sfx_categories,
)
from scripts.verify_cinematic_studio import (
    parse_frontmatter,
    verify_boundary_inspector,
    verify_models,
    verify_skills,
)

PHASE6_SKILLS = [
    "catastrophe-director",
    "thumbnail-designer",
    "youtube-factory",
]


# =========================================================================
# 1. Skill Files Compliance Tests
# =========================================================================

def test_phase6_skills_exist_and_frontmatter_valid():
    """Verify all 3 Phase 6 skill files exist with strict YAML frontmatter."""
    skills_dir = ROOT / ".grok" / "skills"

    for skill_name in PHASE6_SKILLS:
        skill_dir = skills_dir / skill_name
        skill_md = skill_dir / "SKILL.md"

        assert skill_dir.is_dir(), f"Skill directory missing: {skill_dir}"
        assert skill_md.is_file(), f"SKILL.md missing in {skill_dir}"

        # No README.md or CHANGELOG.md (agent-only rule)
        assert not (skill_dir / "README.md").exists(), f"README.md forbidden in {skill_dir}"
        assert not (skill_dir / "CHANGELOG.md").exists(), f"CHANGELOG.md forbidden in {skill_dir}"

        # Parse YAML frontmatter
        fm = parse_frontmatter(skill_md)
        assert fm.get("name") == skill_name, f"Frontmatter name mismatch in {skill_name}"

        desc = fm.get("description", "")
        assert desc, f"Description missing in {skill_name}"
        assert "\n" not in desc, f"Description must be single-line in {skill_name}"
        assert len(desc) <= 1024, f"Description exceeds 1024 characters in {skill_name}"
        assert "<" not in desc and ">" not in desc, f"Description contains angle brackets in {skill_name}"


def test_phase6_skills_contain_model_layer_grok_46():
    """Verify each Phase 6 skill contains the canonical Model Layer (Grok 4.6) block."""
    skills_dir = ROOT / ".grok" / "skills"

    for skill_name in PHASE6_SKILLS:
        skill_md = skills_dir / skill_name / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")

        assert "## Model Layer (Grok 4.6)" in text, f"Missing Model Layer block in {skill_name}"
        assert "grok-4.6" in text, f"Missing grok-4.6 model reference in {skill_name}"
        assert "model_compatibility:" in text, f"Missing model_compatibility in {skill_name}"


def test_phase6_skills_registered_in_manifest():
    """Verify all 3 Phase 6 skills are listed in scripts/required_skills.manifest."""
    manifest_path = ROOT / "scripts" / "required_skills.manifest"
    assert manifest_path.is_file(), "Manifest file missing"

    content = manifest_path.read_text(encoding="utf-8")
    for skill_name in PHASE6_SKILLS:
        assert skill_name in content, f"Skill '{skill_name}' missing from required_skills.manifest"


# =========================================================================
# 2. Boundary Inspector & QA Report Tests
# =========================================================================

def test_boundary_inspector_threshold_is_80():
    """Verify transition score threshold is lowered from 0.85 to 0.80."""
    assert TRANSITION_SCORE_THRESHOLD == 0.80
    ok, msg = verify_boundary_inspector()
    assert ok is True
    assert "0.80" in msg


def test_boundary_qa_report_to_dict():
    """Verify BoundaryQAReport.to_dict converts cleanly without binary payloads."""
    rep = BoundaryQAReport(
        continuity_score=0.825,
        passed=True,
        violations=[],
        corrective_prompt="",
        triplet_bytes=b"fake_jpeg_bytes_12345",
        inspected_by="opencv_histogram_correlation",
    )
    d = rep.to_dict()
    assert d["continuity_score"] == 0.825
    assert d["passed"] is True
    assert d["threshold"] == 0.80
    assert d["inspected_by"] == "opencv_histogram_correlation"
    assert "triplet_bytes" not in d

    # Ensure JSON serializable
    dumped = json.dumps(d)
    loaded = json.loads(dumped)
    assert loaded["continuity_score"] == 0.825


def test_write_qa_report_creates_json(tmp_path: Path):
    """Verify write_qa_report writes full report and logs failed transitions."""
    qa_file = tmp_path / "qa_report.json"

    reports = [
        BoundaryQAReport(
            continuity_score=0.92,
            passed=True,
            violations=[],
            inspected_by="unit_test",
        ),
        BoundaryQAReport(
            continuity_score=0.45,
            passed=False,
            violations=["Sudden lighting color break", "Camera angle axis jump"],
            corrective_prompt="Lock low-key lighting and match previous camera vector",
            inspected_by="unit_test",
        ),
    ]

    out_path = write_qa_report(reports, qa_file, metadata={"project": "test-catastrophe"})
    assert out_path.is_file()

    data = json.loads(qa_file.read_text(encoding="utf-8"))
    assert data["threshold"] == 0.80
    assert data["total_inspections"] == 2
    assert data["passed_count"] == 1
    assert data["failed_count"] == 1
    assert data["overall_passed"] is False
    assert len(data["failed_transitions"]) == 1
    assert data["failed_transitions"][0]["continuity_score"] == 0.45
    assert len(data["failed_transitions"][0]["violations"]) == 2
    assert data["project"] == "test-catastrophe"


def test_inspect_transition_boundary_report_path_persistence(tmp_path: Path):
    """Verify inspect_transition_boundary writes qa_report.json when report_path is passed."""
    # Create synthetic test videos using opencv / dummy files
    v1 = tmp_path / "block_01.mp4"
    v2 = tmp_path / "block_02.mp4"
    v1.write_bytes(b"0" * 2000)
    v2.write_bytes(b"0" * 2000)
    qa_path = tmp_path / "qa_report.json"

    rep = asyncio.run(inspect_transition_boundary(
        hero_plate_path=None,
        block_n_video=v1,
        block_n_plus_1_video=v2,
        dry_run=True,
        report_path=qa_path,
    ))

    assert rep is not None
    assert qa_path.is_file()
    saved = json.loads(qa_path.read_text(encoding="utf-8"))
    assert saved["threshold"] == 0.80


# =========================================================================
# 3. SFX Auto-Categorization Tests
# =========================================================================

def test_extract_sfx_category_explosion():
    """Verify scene containing volcanic explosion triggers explosion audiogen prompt."""
    scene = {
        "narration": "You watch the supervolcano caldera detonate with catastrophic force.",
        "visual_prompt": "Immense explosion with massive shockwave flattening surrounding forests.",
    }
    match = extract_sfx_category(scene)
    assert match is not None
    assert match.category == "explosion"
    assert match.audiogen_prompt == "large explosion with shockwave"
    assert "explosion" in match.tags


def test_extract_sfx_category_tsunami():
    """Verify scene containing tsunami or water surge triggers tsunami_water prompt."""
    scene = {
        "narration": "A 200-meter megatsunami water surge races toward the coastline.",
        "visual_prompt": "Cataclysmic ocean wave wall crashing into harbor seawall.",
    }
    match = extract_sfx_category(scene)
    assert match is not None
    assert match.category == "tsunami_water"
    assert match.audiogen_prompt == "massive tidal wave roaring impact"
    assert "tsunami" in match.tags


def test_extract_sfx_category_alarm():
    """Verify emergency alert or siren triggers alarm_siren prompt."""
    scene = {
        "narration": "The emergency klaxon siren echoes through the subterranean bunker corridors.",
        "visual_prompt": "Flashing red strobe beacon and loud evacuation warning.",
    }
    match = extract_sfx_category(scene)
    assert match is not None
    assert match.category == "alarm_siren"
    assert match.audiogen_prompt == "emergency klaxon siren"
    assert "alarm" in match.tags


def test_extract_sfx_category_earthquake():
    """Verify tectonic rumble or earthquake triggers earthquake_rumble prompt."""
    scene = {
        "narration": "Deep seismic tectonic rumble tears open a 40-meter wide fault fissure.",
        "visual_prompt": "Violent ground shaking and tectonic tremor splitting concrete highway.",
    }
    match = extract_sfx_category(scene)
    assert match is not None
    assert match.category == "earthquake_rumble"
    assert match.audiogen_prompt == "deep seismic tectonic rumble"
    assert "earthquake" in match.tags


def test_extract_sfx_category_from_string():
    """Verify string input directly works with extract_sfx_category."""
    match = extract_sfx_category("Large explosion with shockwave tearing through mountain pass")
    assert match is not None
    assert match.category == "explosion"
    assert match.audiogen_prompt == "large explosion with shockwave"


def test_auto_categorize_scene_sfx_schedule():
    """Verify auto_categorize_scene_sfx generates a valid chronological cue schedule."""
    scenes = [
        {"duration": 8.0, "narration": "Emergency siren sounds across the city.", "visual_prompt": "Klaxon alert"},
        {"duration": 8.0, "narration": "Ground begins quaking with seismic tremors.", "visual_prompt": "Earthquake fissure"},
        {"duration": 8.0, "narration": "The volcano detonates in a violent blast.", "visual_prompt": "Explosion eruption"},
        {"duration": 8.0, "narration": "A massive tidal wave sweeps the coast.", "visual_prompt": "Tsunami impact"},
    ]
    cues = auto_categorize_scene_sfx(scenes, block_duration=8.0)
    assert len(cues) == 4
    assert cues[0]["category"] == "alarm_siren"
    assert cues[0]["start_time"] == 0.0
    assert cues[1]["category"] == "earthquake_rumble"
    assert cues[1]["start_time"] == 8.0
    assert cues[2]["category"] == "explosion"
    assert cues[2]["start_time"] == 16.0
    assert cues[3]["category"] == "tsunami_water"
    assert cues[3]["start_time"] == 24.0


def test_supported_sfx_categories_contains_core_types():
    """Verify get_supported_sfx_categories includes all required disaster categories."""
    cats = get_supported_sfx_categories()
    for expected in ("explosion", "tsunami_water", "alarm_siren", "earthquake_rumble", "fire_lava"):
        assert expected in cats


def test_ffmpeg_lavfi_catastrophe_sfx_synthesis(tmp_path: Path):
    """Verify local FFmpeg Lavfi provider generates audio files for catastrophe SFX prompts."""
    provider = FFmpegLavfiSfxProvider()
    query = {
        "prompt": "large explosion with shockwave",
        "duration": 1.5,
        "tags": ["explosion", "shockwave"],
        "asset_id": "test_exp_01",
    }
    rec = asyncio.run(provider.resolve_asset(query, cache_dir=tmp_path))
    assert rec is not None
    out_file = Path(rec["local_path"])
    assert out_file.is_file()
    assert out_file.stat().st_size > 500


# =========================================================================
# 4. Final Integration Verification Tests
# =========================================================================

def test_python_verifier_script_passes_all_checks():
    """Verify scripts/verify_cinematic_studio.py checks pass 100% green."""
    passed_skills, failed_skills, errors = verify_skills()
    assert failed_skills == 0, f"Skills verification failed: {errors}"
    assert passed_skills >= 68

    bi_ok, bi_msg = verify_boundary_inspector()
    assert bi_ok is True, f"Boundary inspector check failed: {bi_msg}"

    m_ok, m_msg = verify_models()
    assert m_ok is True, f"Model registry check failed: {m_msg}"
