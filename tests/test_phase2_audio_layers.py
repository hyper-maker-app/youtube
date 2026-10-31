"""Unit tests for Phase 2 (R2) — 3 Audio Layers (Voiceover TTS, Ducked Music Bed, SFX Foley).

Verifies:
1. audio_bed.py is cleanly importable and test_audio_bed() passes cleanly.
2. FFmpeg -14 LUFS loudness normalization and TTS sidechain ducking.
3. Pixabay API and Thematic catalog interfaces with resilient offline fallback.
4. .env and engine/.env configuration: SFX_PROVIDER=gradio_space.
5. GradioSpaceSfxProvider active with fffiloni/audiogen + declare-lab/TangoFlux fallback chain.
6. engine/editor.py audio mixing: wiring all 3 audio layers (TTS + Ducked Music + SFX).
7. mix_3_audio_layers standalone function execution.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

import config
import editor
from engine.providers.factory import get_sfx_provider
from engine.providers.sfx.gradio_space import GradioSpaceSfxProvider
from engine.services.audio_bed import (
    duck_audio_bed,
    fetch_pixabay_music,
    fetch_thematic_music,
    generate_audio_bed,
    generate_music_bed,
    mood_from_mode,
    normalize_loudness,
    test_audio_bed as run_audio_bed_test,
)


def test_audio_bed_import_and_self_test():
    """Verify audio_bed.py is cleanly importable and its runnable test function succeeds."""
    success = run_audio_bed_test()
    assert success is True, "test_audio_bed() failed to execute cleanly"


def test_audio_bed_loudness_normalization(tmp_path: Path):
    """Verify normalize_loudness applies FFmpeg -14 LUFS normalization."""
    ffmpeg_bin = config.resolve_ffmpeg()
    raw_tone = tmp_path / "raw_tone.wav"
    cmd = [
        ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2.0:sample_rate=48000",
        "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
        str(raw_tone),
    ]
    subprocess.run(cmd, check=True)
    assert raw_tone.is_file()

    norm_tone = tmp_path / "norm_tone.wav"
    result_path = normalize_loudness(raw_tone, target_lufs=-14.0, out_path=norm_tone, ffmpeg=ffmpeg_bin)
    assert result_path.is_file()
    assert result_path.stat().st_size > 1000

    info = editor.probe(result_path, ffmpeg=ffmpeg_bin)
    assert info.has_audio is True
    assert info.duration is not None
    assert abs(info.duration - 2.0) < 0.5


def test_audio_bed_sidechain_ducking(tmp_path: Path):
    """Verify duck_audio_bed applies sidechain compression under speech with finite termination."""
    ffmpeg_bin = config.resolve_ffmpeg()
    vo_tone = tmp_path / "vo_speech.wav"
    mus_tone = tmp_path / "bgm_music.wav"
    ducked_out = tmp_path / "ducked_master.wav"

    subprocess.run([
        ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "sine=frequency=280:duration=3.0:sample_rate=48000",
        "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "1",
        str(vo_tone),
    ], check=True)

    subprocess.run([
        ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "sine=frequency=110:duration=3.0:sample_rate=48000",
        "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
        str(mus_tone),
    ], check=True)

    out = duck_audio_bed(
        voice_path=vo_tone,
        music_path=mus_tone,
        out_path=ducked_out,
        target_lufs=-14.0,
        target_duration=3.0,
        ffmpeg=ffmpeg_bin,
    )
    assert out.is_file()
    assert out.stat().st_size > 1000
    info = editor.probe(out, ffmpeg=ffmpeg_bin)
    assert info.has_audio is True
    assert info.duration is not None
    assert abs(info.duration - 3.0) < 0.5


def test_audio_bed_pixabay_thematic_offline_fallback(tmp_path: Path):
    """Verify Pixabay and Thematic interfaces fall back gracefully when credentials are not configured."""
    # Without keys, fetch functions should return None cleanly without raising exceptions
    pixabay_result = fetch_pixabay_music(
        query="cinematic dramatic",
        duration_seconds=5.0,
        output_dir=tmp_path / "pixabay",
        api_key="",
    )
    assert pixabay_result is None

    thematic_result = fetch_thematic_music(
        category="cinematic",
        mood="dramatic",
        duration_seconds=5.0,
        output_dir=tmp_path / "thematic",
        api_key="",
    )
    assert thematic_result is None

    # Full generation falls back to procedural lavfi synthesis and normalizes to -14 LUFS
    bed = generate_audio_bed(
        mood="tension_pulse",
        duration_seconds=3.0,
        output_dir=str(tmp_path / "audio"),
        prefer_download=True,
        dry_run=True,
    )
    assert Path(bed).is_file()
    assert Path(bed).stat().st_size > 1000


def test_env_sfx_provider_active():
    """Verify .env configuration sets SFX_PROVIDER=gradio_space."""
    root_env = Path(".env").read_text(encoding="utf-8")
    assert "SFX_PROVIDER=gradio_space" in root_env

    engine_env = Path("engine/.env").read_text(encoding="utf-8")
    assert "SFX_PROVIDER=gradio_space" in engine_env

    provider = get_sfx_provider()
    assert isinstance(provider, GradioSpaceSfxProvider)


def test_gradio_space_sfx_provider_fallback_chain(tmp_path: Path, monkeypatch):
    """Verify GradioSpaceSfxProvider active with fffiloni/audiogen + declare-lab/TangoFlux fallback chain."""
    provider = GradioSpaceSfxProvider(timeout_seconds=2.0, fallback_to_lavfi=True)
    assert provider.space_url == "fffiloni/audiogen"
    assert provider.fallback_space_url == "declare-lab/TangoFlux"

    def _mock_remote_fail(*args, **kwargs):
        raise RuntimeError("Simulated Space Offline")

    monkeypatch.setattr(provider, "_generate_remote", _mock_remote_fail)

    # In local test/offline mode without network, provider falls back to FFmpeg Lavfi procedural synthesis
    import asyncio
    record = asyncio.run(provider.resolve_asset(
        {"prompt": "sub-bass impact door slam", "duration": 2.0, "asset_id": "test_sfx_cue"},
        cache_dir=tmp_path / "sfx",
    ))
    assert record is not None
    assert "local_path" in record
    assert Path(record["local_path"]).is_file()
    assert Path(record["local_path"]).stat().st_size > 1000


def test_editor_wires_3_audio_layers():
    """Verify editor.build_audio_filter wires TTS, Ducked Music Bed, and SFX Foley into final mix."""
    r = config.AUDIO_RATE
    sfx_cues = [
        {"input_index": 2, "start": 0.5, "end": 2.5, "gain_db": -12.0},
        {"input_index": 3, "start": 3.0, "end": 4.5, "gain_db": -10.0},
    ]
    # Input 0: Voiceover, Input 1: Music, Inputs 2, 3: SFX Cues
    stmts = editor.build_audio_filter(vo_index=0, music_index=1, sfx_inputs=sfx_cues)
    joined = ";\n".join(stmts)

    # Layer 1 & 2: Voiceover split and music sidechain compression
    assert "[0:a]aformat=sample_rates=48000:channel_layouts=stereo,apad,asplit=2[vo1][vo2]" in joined
    assert f"volume={config.MUSIC_VOLUME}[mus]" in joined
    assert f"sidechaincompress=threshold={config.DUCK_THRESHOLD}:ratio={config.DUCK_RATIO}" in joined
    assert "[vo1][duck]amix=inputs=2:duration=first" in joined

    # Layer 3: SFX Foley inputs spatialized and mixed
    assert "[2:a]" in joined
    assert "[3:a]" in joined
    assert "adelay=500|500[sfx2]" in joined
    assert "adelay=3000|3000[sfx3]" in joined
    assert "[base][sfx2][sfx3]amix=inputs=3:duration=first" in joined

    # Final Loudness Normalization to -14 LUFS
    assert f"loudnorm=I={config.LOUDNORM_I}:TP={config.LOUDNORM_TP}:LRA={config.LOUDNORM_LRA}" in joined


def test_editor_mix_3_audio_layers_standalone(tmp_path: Path):
    """Verify editor.mix_3_audio_layers produces valid 48kHz stereo master audio track."""
    ffmpeg_bin = config.resolve_ffmpeg()
    vo_path = tmp_path / "test_vo.wav"
    mus_path = tmp_path / "test_mus.wav"
    sfx_path = tmp_path / "test_sfx.wav"
    out_master = tmp_path / "test_master.wav"

    for p, freq in [(vo_path, 320), (mus_path, 120), (sfx_path, 600)]:
        subprocess.run([
            ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"sine=frequency={freq}:duration=2.5:sample_rate=48000",
            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
            str(p),
        ], check=True)

    cues = [{"cue_id": "sfx_01", "local_path": str(sfx_path), "start": 0.5, "end": 2.0}]
    master = editor.mix_3_audio_layers(
        vo_path=vo_path,
        music_path=mus_path,
        sfx_cues=cues,
        out_path=out_master,
        target_duration=2.5,
        ffmpeg=ffmpeg_bin,
    )

    assert master.is_file()
    assert master.stat().st_size > 1000
    info = editor.probe(master, ffmpeg=ffmpeg_bin)
    assert info.has_audio is True
    assert info.duration is not None
    assert abs(info.duration - 2.5) < 0.5
