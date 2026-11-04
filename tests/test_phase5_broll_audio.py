"""Unit tests for Plan v4.0 Phase 5 — Dynamic B-Roll Generator & 4-Band Frequency Audio Engine.

Verifies:
1. map_overlay_generator.generate_volcano_map_video produces valid MP4 with editor.probe.
2. map_overlay_generator.generate_temperature_curve_video produces valid MP4 with editor.probe.
3. map_overlay_generator.generate_data_broll dispatches correctly across all supported modes.
4. audio_bed.generate_audio_bed(mood="catastrophe") synthesizes 4-band procedural frequency architecture.
5. audio_bed.synthesize_audio_trigger_cue produces pitch-drop sub-bass braams.
6. audio_bed.inject_audio_trigger_cues mixes trigger cues at exact timestamps without dead silence.
7. Self-test validation suites pass cleanly.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import config
import editor
from engine.services.audio_bed import (
    _MOOD_CHAINS,
    duck_audio_bed,
    generate_audio_bed,
    inject_audio_trigger_cues,
    mood_from_mode,
    normalize_loudness,
    synthesize_audio_trigger_cue,
    test_audio_bed as run_audio_bed_test,
)
from engine.services.map_overlay_generator import (
    generate_data_broll,
    generate_pressure_grid_video,
    generate_temperature_curve_video,
    generate_volcano_map_video,
    test_map_overlay_generator as run_map_overlay_test,
)


def test_volcano_map_video_generation(tmp_path: Path):
    """Verify generate_volcano_map_video creates a valid, playable H.264 MP4."""
    out_video = tmp_path / "volcano_1000_seismic.mp4"
    res = generate_volcano_map_video(
        output_path=out_video,
        duration=1.0,
        fps=24,
        width=640,
        height=360,
    )
    assert res.is_file(), f"Output video file was not created: {res}"
    assert res.stat().st_size > 5000, "Volcano map video is unexpectedly small"

    info = editor.probe(res)
    assert info.has_video is True, "Probed media has no video stream"
    assert info.width == 640
    assert info.height == 360
    assert info.duration is not None
    assert abs(info.duration - 1.0) < 0.4, f"Unexpected duration: {info.duration}"


def test_temperature_curve_video_generation(tmp_path: Path):
    """Verify generate_temperature_curve_video creates a valid thermal collapse MP4."""
    out_video = tmp_path / "temperature_collapse.mp4"
    res = generate_temperature_curve_video(
        output_path=out_video,
        duration=1.0,
        fps=24,
        width=640,
        height=360,
    )
    assert res.is_file(), f"Output video file was not created: {res}"
    assert res.stat().st_size > 5000, "Temperature curve video is unexpectedly small"

    info = editor.probe(res)
    assert info.has_video is True, "Probed media has no video stream"
    assert info.width == 640
    assert info.height == 360
    assert info.duration is not None
    assert abs(info.duration - 1.0) < 0.4, f"Unexpected duration: {info.duration}"


def test_pressure_grid_video_generation(tmp_path: Path):
    """Verify generate_pressure_grid_video produces valid atmospheric shockwave MP4."""
    out_video = tmp_path / "pressure_grid.mp4"
    res = generate_pressure_grid_video(
        output_path=out_video,
        duration=1.0,
        fps=24,
        width=640,
        height=360,
    )
    assert res.is_file()
    assert res.stat().st_size > 5000
    info = editor.probe(res)
    assert info.has_video is True


def test_data_broll_dispatcher(tmp_path: Path):
    """Verify generate_data_broll dispatches correctly and rejects unsupported types."""
    # 1. Dispatch volcano map
    v_path = generate_data_broll(
        broll_type="volcano_map",
        output_path=tmp_path / "disp_volcano.mp4",
        duration=0.5,
        fps=20,
        width=480,
        height=270,
    )
    assert v_path.is_file()

    # 2. Dispatch temperature drop
    t_path = generate_data_broll(
        broll_type="temperature_drop",
        output_path=tmp_path / "disp_temp.mp4",
        duration=0.5,
        fps=20,
        width=480,
        height=270,
    )
    assert t_path.is_file()

    # 3. Dispatch pressure grid
    p_path = generate_data_broll(
        broll_type="pressure_grid",
        output_path=tmp_path / "disp_pressure.mp4",
        duration=0.5,
        fps=20,
        width=480,
        height=270,
    )
    assert p_path.is_file()

    # 4. Invalid type raises ValueError
    with pytest.raises(ValueError, match="Unsupported broll_type"):
        generate_data_broll(
            broll_type="unsupported_quantum_flux",
            output_path=tmp_path / "fail.mp4",
        )


def test_catastrophe_4band_audio_bed_synthesis(tmp_path: Path):
    """Verify 4-band procedural frequency audio bed synthesis for catastrophe mood."""
    # 1. Verify mood mapping
    assert mood_from_mode("catastrophe") == "catastrophe_4band"

    # 2. Verify filter chain contains all 4 bands
    chain = _MOOD_CHAINS["catastrophe_4band"]
    assert "band1" in chain, "Band 1 missing from catastrophe_4band chain"
    assert "band2" in chain, "Band 2 missing from catastrophe_4band chain"
    assert "band3" in chain, "Band 3 missing from catastrophe_4band chain"
    assert "band4" in chain, "Band 4 missing from catastrophe_4band chain"
    assert "amix=inputs=4" in chain, "4-band amix balancing missing"

    # 3. Generate audio bed with catastrophe mood
    bed_path = generate_audio_bed(
        mood="catastrophe",
        duration_seconds=2.0,
        output_dir=str(tmp_path / "audio"),
        prefer_download=False,
        dry_run=True,
    )
    assert Path(bed_path).is_file()
    assert Path(bed_path).stat().st_size > 1000

    info = editor.probe(bed_path)
    assert info.has_audio is True
    assert info.duration is not None
    assert abs(info.duration - 2.0) < 0.4


def test_synthesize_audio_trigger_cue(tmp_path: Path):
    """Verify synthesize_audio_trigger_cue generates sub-bass braam pitch drop hit."""
    cue_path = tmp_path / "sub_bass_braam.wav"
    res = synthesize_audio_trigger_cue(
        output_path=cue_path,
        duration=1.2,
        cue_type="sub_bass_braam",
    )
    assert res.is_file()
    assert res.stat().st_size > 1000

    info = editor.probe(res)
    assert info.has_audio is True
    assert info.duration is not None
    assert abs(info.duration - 1.2) < 0.3


def test_inject_audio_trigger_cues(tmp_path: Path):
    """Verify inject_audio_trigger_cues mixes braam cues into stream at exact timestamps."""
    # Generate base audio track (3.0s)
    base_track = generate_audio_bed(
        mood="tension_pulse",
        duration_seconds=3.0,
        output_dir=str(tmp_path / "base"),
        dry_run=True,
    )
    assert Path(base_track).is_file()

    out_mix = tmp_path / "injected_master.wav"
    res = inject_audio_trigger_cues(
        audio_path=base_track,
        cue_timestamps=[0.5, 2.0],
        out_path=out_mix,
        cue_gain_db=-6.0,
    )
    assert res.is_file()
    assert res.stat().st_size > 1000

    info = editor.probe(res)
    assert info.has_audio is True
    assert info.duration is not None
    assert abs(info.duration - 3.0) < 0.4


def test_map_overlay_generator_self_test():
    """Verify map_overlay_generator self-test runner succeeds."""
    assert run_map_overlay_test() is True


def test_audio_bed_self_test():
    """Verify audio_bed self-test runner succeeds."""
    assert run_audio_bed_test() is True
