"""Unit tests for youtube-media-inspector MCP tools."""
from __future__ import annotations

from pathlib import Path
from unittest import mock
import pytest

import _media_mcp


def test_missing_parameter_handling():
    assert "error" in _media_mcp.inspect_media("")
    assert "error" in _media_mcp.measure_audio_loudness("")
    assert "error" in _media_mcp.detect_black_or_freeze("")
    assert "error" in _media_mcp.analyze_audio_spectrum("")
    assert "error" in _media_mcp.analyze_video_stability("")


def test_nonexistent_file_handling():
    fake = "nonexistent_media_path_xyz123.mp4"
    assert "File not found" in _media_mcp.inspect_media(fake)["error"]
    assert "File not found" in _media_mcp.measure_audio_loudness(fake)["error"]
    assert "File not found" in _media_mcp.detect_black_or_freeze(fake)["error"]
    assert "File not found" in _media_mcp.analyze_audio_spectrum(fake)["error"]
    assert "File not found" in _media_mcp.analyze_video_stability(fake)["error"]


def test_analyze_audio_spectrum_mocked():
    sample_stderr = '''
    [Parsed_astats_0 @ 0000020aba339e00] Peak level dB: -1.200000
    [Parsed_astats_0 @ 0000020aba339e00] RMS level dB: -18.500000
    [Parsed_astats_0 @ 0000020aba339e00] RMS peak dB: -8.500000
    [Parsed_astats_0 @ 0000020aba339e00] Flat factor: 0.000000
    [Parsed_astats_0 @ 0000020aba339e00] Entropy: 0.820000
    '''
    with mock.patch('pathlib.Path.is_file', return_value=True), \
         mock.patch('pathlib.Path.stat') as mock_stat, \
         mock.patch('subprocess.run') as mock_run:
        mock_stat.return_value = mock.Mock(st_size=1024)
        mock_run.return_value = mock.Mock(stderr=sample_stderr, returncode=0)
        res = _media_mcp.analyze_audio_spectrum(media_path='dummy.wav')

    assert res['peak_level_db'] == -1.2
    assert res['rms_level_db'] == -18.5
    assert res['rms_peak_db'] == -8.5
    assert res['flat_factor'] == 0.0
    assert res['entropy'] == 0.82
    assert res['clipping_detected'] is False
    assert res['broadcast_dynamics_safe'] is True


def test_analyze_video_stability_mocked():
    sample_stderr = '''
    Stream #0:0: Video: h264, 30.0 fps
    frame= 300 fps=0.0 time=00:00:10.00
    '''
    with mock.patch('pathlib.Path.is_file', return_value=True), \
         mock.patch('pathlib.Path.stat') as mock_stat, \
         mock.patch('subprocess.run') as mock_run:
        mock_stat.return_value = mock.Mock(st_size=1024)
        mock_run.return_value = mock.Mock(stderr=sample_stderr, returncode=0)
        res = _media_mcp.analyze_video_stability(video_path='dummy.mp4', sample_seconds=10.0)

    assert res['fps'] == 30.0
    assert res['freeze_count'] == 0
    assert res['black_count'] == 0
    assert res['stability_score'] == 100
    assert res['is_smooth_and_stable'] is True


def test_empty_file_handling(tmp_path: Path):
    empty_file = tmp_path / "empty_sample.mp4"
    empty_file.write_bytes(b"")
    p = str(empty_file)
    assert "File is empty" in _media_mcp.inspect_media(p)["error"]
    assert "File is empty" in _media_mcp.measure_audio_loudness(p)["error"]
    assert "File is empty" in _media_mcp.detect_black_or_freeze(p)["error"]
    assert "File is empty" in _media_mcp.analyze_audio_spectrum(p)["error"]
    assert "File is empty" in _media_mcp.analyze_video_stability(p)["error"]


def test_failed_ffmpeg_handling():
    with mock.patch('pathlib.Path.is_file', return_value=True), \
         mock.patch('pathlib.Path.stat') as mock_stat, \
         mock.patch('subprocess.run') as mock_run:
        mock_stat.return_value = mock.Mock(st_size=1024)
        mock_run.return_value = mock.Mock(stderr="Invalid data found when processing input", returncode=1)
        res_stab = _media_mcp.analyze_video_stability("corrupt.mp4")
        res_spec = _media_mcp.analyze_audio_spectrum("corrupt.mp4")
        res_loud = _media_mcp.measure_audio_loudness("corrupt.mp4")
        res_freeze = _media_mcp.detect_black_or_freeze("corrupt.mp4")
        res_probe = _media_mcp.inspect_media("corrupt.mp4")

    assert "error" in res_stab
    assert "error" in res_spec
    assert "error" in res_loud
    assert "error" in res_freeze
    assert "error" in res_probe

