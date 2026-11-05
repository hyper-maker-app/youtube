"""Unit tests for Plan v4.0 Phase 6 — YouTube Optimization, DCS LUT, Shorts Multiplexer & E2E CLI.

Verifies:
1. editor.apply_dynamic_contrast_shift applies time-dependent gamma and desaturation correctly.
2. editor.apply_extinction_countdown_overlay overlays the HUD crisis countdown banner in opening seconds.
3. editor.export_shorts_multiplex converts 16:9 master footage to 9:16 (1080x1920) vertical Shorts format.
4. editor.build_video_filter cleanly integrates enable_dcs and enable_countdown flags.
5. tools/cli/produce_commands.py supports --force-render and --export-shorts flags.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

import config
import editor
from tools.cli.produce_commands import produce_film


@pytest.fixture
def sample_16x9_video(tmp_path: Path) -> Path:
    """Generate a lightweight synthetic 16:9 video (1920x1080, 2 seconds) for fast tests."""
    ffmpeg = config.resolve_ffmpeg()
    out_video = tmp_path / "sample_16x9.mp4"
    cmd = [
        ffmpeg, "-hide_banner", "-y",
        "-f", "lavfi", "-i", "color=c=darkblue:s=1920x1080:d=2.0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out_video),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, f"Failed to create test 16:9 video:\n{proc.stderr}"
    return out_video


def test_apply_dynamic_contrast_shift(sample_16x9_video: Path, tmp_path: Path):
    """Verify apply_dynamic_contrast_shift processes video and returns a valid playable file."""
    out_video = tmp_path / "dcs_output.mp4"
    res = editor.apply_dynamic_contrast_shift(
        input_path=sample_16x9_video,
        out_path=out_video,
        duration=1.5,
    )
    assert res.is_file(), f"DCS output video was not created: {res}"
    assert res.stat().st_size > 1000, "DCS output video is suspiciously small"

    info = editor.probe(res)
    assert info.has_video is True, "Probed media has no video stream"
    assert info.width == 1920
    assert info.height == 1080
    assert info.duration is not None
    assert abs(info.duration - 1.5) < 0.4, f"Unexpected duration: {info.duration}"


def test_apply_extinction_countdown_overlay(sample_16x9_video: Path, tmp_path: Path):
    """Verify apply_extinction_countdown_overlay adds red HUD banner overlay without corrupting stream."""
    out_video = tmp_path / "countdown_output.mp4"
    res = editor.apply_extinction_countdown_overlay(
        input_path=sample_16x9_video,
        out_path=out_video,
        countdown_seconds=1.5,
        banner_text="GLOBAL EXTINCTION EVENT: T-MINUS 05:00",
    )
    assert res.is_file(), f"Countdown output video was not created: {res}"
    assert res.stat().st_size > 1000

    info = editor.probe(res)
    assert info.has_video is True
    assert info.width == 1920
    assert info.height == 1080
    assert info.duration is not None
    assert abs(info.duration - 2.0) < 0.4


def test_countdown_does_not_replace_explicit_ffmpeg(tmp_path, monkeypatch):
    import os
    import subprocess
    from types import SimpleNamespace

    if os.name != 'nt':
        pytest.skip('Windows access-violation handling')
    calls = []
    monkeypatch.setattr(editor, 'probe', lambda *args: SimpleNamespace(has_audio=False))
    def fail(args):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0xC0000005, '', 'drawtext crash')
    monkeypatch.setattr(editor, '_run', fail)
    with pytest.raises(RuntimeError, match='drawtext crash'):
        editor.apply_extinction_countdown_overlay(tmp_path / 'input.mp4', tmp_path / 'out.mp4',
                                                  banner_text='TEST', ffmpeg='explicit.exe')
    assert len(calls) == 1 and calls[0][0] == 'explicit.exe'


def test_countdown_retries_only_windows_access_violation(tmp_path, monkeypatch):
    import os
    import subprocess
    from types import SimpleNamespace
    import imageio_ffmpeg

    if os.name != 'nt':
        pytest.skip('Windows access-violation handling')
    monkeypatch.delenv('FFMPEG_BINARY', raising=False)
    monkeypatch.setattr(editor.config, 'resolve_ffmpeg', lambda: 'automatic.exe')
    monkeypatch.setattr(imageio_ffmpeg, 'get_ffmpeg_exe', lambda: 'bundled.exe')
    monkeypatch.setattr(editor, 'probe', lambda *args: SimpleNamespace(has_audio=False))
    calls = []
    def crash_then_pass(args):
        calls.append(args[0])
        return subprocess.CompletedProcess(args, 0xC0000005 if len(calls) == 1 else 0, '', 'crash')
    monkeypatch.setattr(editor, '_run', crash_then_pass)
    editor.apply_extinction_countdown_overlay(tmp_path / 'input.mp4', tmp_path / 'out.mp4', banner_text='TEST')
    assert calls == ['automatic.exe', 'bundled.exe']

    calls.clear()
    def ordinary_failure(args):
        calls.append(args[0])
        return subprocess.CompletedProcess(args, 1, '', 'invalid filter')
    monkeypatch.setattr(editor, '_run', ordinary_failure)
    with pytest.raises(RuntimeError, match='invalid filter'):
        editor.apply_extinction_countdown_overlay(tmp_path / 'input.mp4', tmp_path / 'out.mp4', banner_text='TEST')
    assert calls == ['automatic.exe']


@pytest.mark.parametrize('returncode,override,expected_calls', [
    (0xC0000005, None, 2),
    (1, None, 1),
    (0xC0000005, 'custom.exe', 1),
])
def test_countdown_retry_requires_unconfigured_windows_access_violation(
    tmp_path, monkeypatch, returncode, override, expected_calls
):
    import os
    import subprocess
    from types import SimpleNamespace
    import imageio_ffmpeg

    if os.name != 'nt':
        pytest.skip('Windows access-violation handling')
    if override:
        monkeypatch.setenv('FFMPEG_BINARY', override)
    else:
        monkeypatch.delenv('FFMPEG_BINARY', raising=False)
    monkeypatch.setattr(editor.config, 'resolve_ffmpeg', lambda: override or 'primary.exe')
    monkeypatch.setattr(imageio_ffmpeg, 'get_ffmpeg_exe', lambda: 'bundled.exe')
    monkeypatch.setattr(editor, 'probe', lambda *args: SimpleNamespace(has_audio=False))
    calls = []
    def run(args):
        calls.append(args)
        return subprocess.CompletedProcess(args, returncode if len(calls) == 1 else 0, '', 'failed')
    monkeypatch.setattr(editor, '_run', run)
    kwargs = dict(input_path=tmp_path / 'in.mp4', out_path=tmp_path / 'out.mp4', banner_text='TEST')
    if expected_calls == 1:
        with pytest.raises(RuntimeError):
            editor.apply_extinction_countdown_overlay(**kwargs)
    else:
        editor.apply_extinction_countdown_overlay(**kwargs)
        assert calls[1][0] == 'bundled.exe' and calls[1][1:] == calls[0][1:]
    assert len(calls) == expected_calls


def test_export_shorts_multiplex(sample_16x9_video: Path, tmp_path: Path):
    """Verify export_shorts_multiplex center-crops 16:9 footage into vertical 9:16 1080x1920."""
    out_shorts = tmp_path / "shorts_9x16.mp4"
    res = editor.export_shorts_multiplex(
        input_path=sample_16x9_video,
        out_path=out_shorts,
        max_duration=1.5,
        start_time=0.0,
    )
    assert res.is_file(), f"Shorts video was not created: {res}"
    assert res.stat().st_size > 1000

    info = editor.probe(res)
    assert info.has_video is True
    # Verify strict 9:16 vertical resolution
    assert info.width == 1080, f"Expected width 1080, got {info.width}"
    assert info.height == 1920, f"Expected height 1920, got {info.height}"
    assert info.duration is not None
    assert abs(info.duration - 1.5) < 0.4, f"Expected duration near 1.5s, got {info.duration}"


def test_build_video_filter_dcs_and_countdown_integration():
    """Verify build_video_filter injects DCS formula and countdown overlay into filtergraph."""
    stmts = editor.build_video_filter(
        n_blocks=2,
        punch_times=[],
        block_durations=[4.0, 4.0],
        target_duration=8.0,
        enable_dcs=True,
        enable_countdown=True,
        countdown_seconds=3.0,
        countdown_text="GLOBAL EXTINCTION EVENT: T-MINUS 05:00",
    )
    joined_graph = ";\n".join(stmts)
    # Check that DCS gamma/saturation expression exists
    assert "eq=gamma='max(0.45" in joined_graph
    assert "saturation='max(0.35" in joined_graph
    # Check that drawtext extinction HUD countdown exists
    assert "drawtext=" in joined_graph
    assert "GLOBAL EXTINCTION EVENT" in joined_graph
    assert "enable='between(t,0,3.000)'" in joined_graph


def test_produce_film_cli_flags():
    """Verify CLI argument parsing accepts --force-render and --export-shorts."""
    import inspect
    sig = inspect.signature(produce_film)
    assert "force_render" in sig.parameters, "produce_film missing force_render parameter"
    assert "export_shorts" in sig.parameters, "produce_film missing export_shorts parameter"

    # Default values should be False
    param_force = sig.parameters["force_render"]
    assert param_force.default.default is False
    param_shorts = sig.parameters["export_shorts"]
    assert param_shorts.default.default is False


def test_cli_produce_film_help_displays_phase6_flags():
    """Verify cinematic_studio_cli produce-film --help shows --force-render and --export-shorts."""
    from cli_helpers import run_cli
    res = run_cli("produce-film", "--help")
    assert res.returncode == 0
    assert "--force-render" in res.stdout
    assert "--export-shorts" in res.stdout


def test_cli_produce_film_help_displays_video_qa_flags():
    from cli_helpers import run_cli
    res = run_cli("produce-film", "--help")
    assert res.returncode == 0
    assert "--video-qa" in res.stdout
    assert "--no-video-qa" in res.stdout
    assert "--video-qa-model" in res.stdout
    assert "--max-patch-passes" in res.stdout


def test_produce_film_signature_has_video_qa_defaults():
    import inspect
    from cli.produce_commands import produce_film

    params = inspect.signature(produce_film).parameters
    assert params["video_qa"].default.default is False
    assert params["video_qa_model"].default.default == "gemini-3.1-pro"
    assert params["max_patch_passes"].default.default == 1
def test_cli_produce_film_plan_only_dry_run():
    """Verify produce-film with --plan-only --dry-run runs cleanly end-to-end."""
    from cli_helpers import run_cli
    res = run_cli(
        "produce-film",
        "Short Test Extinction",
        "--genre", "catastrophe",
        "--duration", "60",
        "--plan-only",
        "--dry-run",
    )
    assert res.returncode == 0
    assert "Production Launch v4.0" in res.stdout or "Production Complete" in res.stdout or "Ready for Production Review" in res.stdout
