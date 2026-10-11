"""Unit tests for the longform documentary innovations (HiAPIAI, Script-Weaver, ai-playbooks).

Tests:
1. services/historical_research.py — HistoricalTruthSheet ledger, curated and dynamic generation.
2. services/prompt_compiler.py — Clothing Lock, Movement Lock, Ancient Equipment Rule, Multi-Shot syntax.
3. services/screenplay.py — Dynamic Script-Weaver generation with flexible durations (6s-15s).
4. services/lip_sync.py — LipSyncService interface, engine detection, and graceful Ken Burns fallback.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import config
import pytest
from services.historical_research import HistoricalTruthSheet, get_historical_truth_sheet
from services.lip_sync import LipSyncResult, LipSyncService, generate_host_video
from services.prompt_compiler import (
    MOVEMENT_LOCK_SUFFIX,
    apply_ancient_equipment_rule,
    apply_clothing_lock,
    apply_movement_lock,
    compile_longform_broll_prompt,
    format_multi_shot_prompt,
)
from services.screenplay import generate_dynamic_screenplay
from timeline import TimelinePlan


def test_historical_truth_sheet_curated_and_dynamic():
    """Verify HistoricalTruthSheet compiles authentic materials, figures, and prohibits anachronisms."""
    egypt_sheet = get_historical_truth_sheet("The Lost Labyrinth of Hawara")
    assert egypt_sheet.era == "egyptian"
    assert "Amenemhat III" in egypt_sheet.verified_dates[0]
    assert any("limestone" in m for m in egypt_sheet.architecture_and_materials)
    assert "modern cranes" in egypt_sheet.prohibited_anachronisms
    assert len(egypt_sheet.narrative_beats) == 5

    summary = egypt_sheet.summary_for_prompt()
    assert "HISTORICAL TRUTH SHEET" in summary
    assert "FORBIDDEN ANACHRONISMS" in summary

    # Dynamic fallback topic
    dynamic_sheet = get_historical_truth_sheet("Subterranean Secrets of Derinkuyu")
    assert dynamic_sheet is not None
    assert len(dynamic_sheet.architecture_and_materials) > 0
    assert "modern cranes" in dynamic_sheet.prohibited_anachronisms


def test_prompt_compiler_clothing_and_movement_locks():
    """Verify Clothing Lock, Movement Lock, and Ancient Equipment Rule."""
    # Clothing lock
    raw_clothing = "An architect wearing ancient clothing inspects the foundation."
    locked_clothing = apply_clothing_lock(raw_clothing, era="egyptian")
    assert "ancient clothing" not in locked_clothing
    assert "kalasiris" in locked_clothing or "linen" in locked_clothing

    # Movement lock
    raw_motion = "Laborers are standing still and watching passively while stones arrive."
    locked_motion = apply_movement_lock(raw_motion)
    assert "standing still" not in locked_motion
    assert "watching passively" not in locked_motion
    assert MOVEMENT_LOCK_SUFFIX in locked_motion

    # Ancient equipment rule
    raw_equipment = "Stonemasons operate a heavy crane and steel cable to hoist granite."
    locked_equipment = apply_ancient_equipment_rule(raw_equipment)
    assert "crane" not in locked_equipment
    assert "steel cable" not in locked_equipment
    assert "timber lever" in locked_equipment or "hewn cedar timber levers" in locked_equipment


def test_prompt_compiler_multi_shot_syntax():
    """Verify Multi-Shot Prompting syntax formatting."""
    multi_prompt = format_multi_shot_prompt(
        shot1_action="Camera glides past white limestone columns",
        shot2_action="Sunlight illuminates copper-saw markings on basalt blocks",
        shot1_window=(0.0, 3.5),
        shot2_window=(3.5, 7.0),
    )
    assert "SHOT 1 [0-4s]:" in multi_prompt or "SHOT 1 [0-3s]:" in multi_prompt
    assert "SHOT 2 [4-7s]:" in multi_prompt or "SHOT 2 [3-7s]:" in multi_prompt
    assert MOVEMENT_LOCK_SUFFIX in multi_prompt


def test_dynamic_screenplay_generation_and_flexible_durations():
    """Verify Script-Weaver dynamic screenplay generation with flexible scene durations (6s-15s)."""
    topic = "The Secrets of Göbeklitepe"
    script = generate_dynamic_screenplay(topic, target_blocks=8)
    assert len(script.beats) == 8
    assert len(script.shots) == 8

    # Verify flexible durations (each shot duration is >= 6.0s for longform documentary pacing)
    for shot in script.shots:
        duration = shot.t_end - shot.t_start
        assert duration >= 5.9

    # Verify A-Roll, witness, and B-Roll separation
    witness_shots = [s for s in script.shots if "witness" in s.subject_id]
    assert len(witness_shots) >= 1
    a_roll_shots = [s for s in script.shots if "host_nova" in s.subject_id]
    assert len(a_roll_shots) >= 1


def test_gallipoli_one_minute_flow_fallback_has_fifteen_topic_specific_native_shots():
    """A one-minute Flow plan must stay on Gallipoli facts and 4-second clips."""
    import pipeline

    timeline = pipeline.provider_timeline(blocks=15)
    script = generate_dynamic_screenplay(
        "1915 The Battle of Gallipoli", timeline=timeline, target_blocks=15
    )

    assert len(script.beats) == len(script.shots) == 15
    assert script.timeline.block_count == 15
    assert script.timeline.total_duration == 60.0
    assert all(shot.duration == 4.0 for shot in script.shots)
    assert len({shot.location_id for shot in script.shots}) == 15
    assert "stonework" not in " ".join(beat.text for beat in script.beats).casefold()
    assert any("Nusret" in beat.text for beat in script.beats)
    assert any("Bouvet" in beat.text for beat in script.beats)
    assert any("25 April" in beat.text for beat in script.beats)


def test_flow_roster_assessment_failure_writes_sanitized_resume_handoff(tmp_path):
    from types import SimpleNamespace
    from pipeline import write_flow_asset_handoff

    ctx = SimpleNamespace(out_dir=tmp_path)
    entry = SimpleNamespace(id="environment_test", aspect_ratio="16:9", prompt="historical shoreline")
    handoff = write_flow_asset_handoff(
        ctx, entry, tmp_path / "roster" / "environment_test.png",
        RuntimeError("PUBLIC_ERROR_UNUSUAL_ACTIVITY account acct-private"),
    )
    body = handoff.read_text(encoding="utf-8")
    assert "PUBLIC_ERROR_UNUSUAL_ACTIVITY" in body
    assert "acct-private" not in body
    assert "--resume" in body
    assert "historical shoreline" in body


def test_lip_sync_service_and_graceful_fallback():
    """Verify LipSyncService engine detection and seamless Ken Burns fallback."""
    service = LipSyncService("live_portrait")
    # Engine is not installed in standard test environment, so is_engine_available returns False
    assert isinstance(service.is_engine_available(), bool)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        img_path = tmp_path / "host_test.png"
        audio_path = tmp_path / "host_test.mp3"
        out_mp4 = tmp_path / "host_output.mp4"

        # Create dummy image and audio
        cmd_img = [
            config.resolve_ffmpeg(), "-y",
            "-f", "lavfi", "-i", "color=c=darkgreen:s=1920x1080",
            "-vframes", "1", str(img_path)
        ]
        import subprocess
        subprocess.run(cmd_img, check=True, capture_output=True)

        cmd_audio = [
            config.resolve_ffmpeg(), "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1.0",
            "-c:a", "libmp3lame", str(audio_path)
        ]
        subprocess.run(cmd_audio, check=True, capture_output=True)

        result = service.generate(img_path, audio_path, out_mp4, duration=1.0)
        assert isinstance(result, LipSyncResult)
        assert result.video_path.exists()
        assert result.video_path.stat().st_size > 0
        assert result.fallback_used is True
        assert result.engine_used == "ken_burns_fallback"


def test_dynamic_screenplay_with_default_timeline_preserves_flexible_durations():
    """Verify that passing a default 4s timeline does not collapse longform documentary shot durations to 4s."""
    import pipeline
    tl = pipeline.provider_timeline(blocks=8)
    topic = "The Lost Labyrinth of Hawara"
    script = generate_dynamic_screenplay(topic, timeline=tl, target_blocks=8)
    assert len(script.shots) == 8
    for shot in script.shots:
        duration = shot.t_end - shot.t_start
        assert duration >= 5.9, f"Shot {shot.block} collapsed to {duration}s instead of flexible documentary duration"


def test_longform_fallback_and_dry_script_dynamic_grounding():
    """Verify that LongformEngine fallback and _dry_script use dynamic source-grounded screenplay for all topics."""
    from core.narrative_longform import LongformEngine
    from pipeline import RunContext, _dry_script

    engine = LongformEngine(None)
    script = engine._fallback_script("The Lost Labyrinth of Hawara")
    assert len(script.shots) >= 6
    # Check that shots have flexible durations
    assert script.shots[0].duration >= 5.9

    ctx = RunContext(topic="The Secrets of Göbeklitepe", out_dir=Path("out/test"), format="longform")
    dry = _dry_script(ctx)
    assert len(dry.shots) >= 6
    assert dry.shots[0].duration >= 5.9


def test_lip_sync_gradio_client_engine_fallback():
    """Verify LipSyncService with gradio_client provider falls back gracefully."""
    service = LipSyncService("gradio_client")
    assert isinstance(service.is_engine_available(), bool)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        img_path = tmp_path / "host.png"
        audio_path = tmp_path / "host.mp3"
        out_mp4 = tmp_path / "out.mp4"

        cmd_img = [config.resolve_ffmpeg(), "-y", "-f", "lavfi", "-i", "color=c=navy:s=1920x1080", "-vframes", "1", str(img_path)]
        subprocess.run(cmd_img, check=True, capture_output=True)
        cmd_audio = [config.resolve_ffmpeg(), "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=1.0", "-c:a", "libmp3lame", str(audio_path)]
        subprocess.run(cmd_audio, check=True, capture_output=True)

        res = service.generate(img_path, audio_path, out_mp4, duration=1.0)
        assert res.video_path.exists()
        assert res.fallback_used is True
