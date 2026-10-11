"""Unit tests for autonomous audio bed engine."""
from __future__ import annotations

import shutil
import subprocess

import pytest

from services.audio_bed import generate_audio_bed, mood_from_mode


# ---------------------------------------------------------------------------
# mood_from_mode mapping tests
# ---------------------------------------------------------------------------

def test_mood_from_mode_anatomical():
    assert mood_from_mode("anatomical") == "clinical_drone"


def test_mood_from_mode_incident():
    assert mood_from_mode("incident") == "tension_pulse"


def test_mood_from_mode_mechanical():
    assert mood_from_mode("mechanical") == "mechanical_hum"


def test_mood_from_mode_unknown_defaults_to_clinical_drone():
    assert mood_from_mode("unknown_mode") == "clinical_drone"
    assert mood_from_mode("") == "clinical_drone"


# ---------------------------------------------------------------------------
# FFmpeg availability check
# ---------------------------------------------------------------------------

_FFMPEG_AVAILABLE: bool | None = None


def _has_ffmpeg() -> bool:
    global _FFMPEG_AVAILABLE
    if _FFMPEG_AVAILABLE is None:
        try:
            import config
            from pathlib import Path
            bin_path = config.resolve_ffmpeg()
            _FFMPEG_AVAILABLE = bool(bin_path and Path(bin_path).is_file())
        except Exception:
            _FFMPEG_AVAILABLE = False
    return _FFMPEG_AVAILABLE


requires_ffmpeg = pytest.mark.skipif(not _has_ffmpeg(), reason="FFmpeg not found")


# ---------------------------------------------------------------------------
# generate_audio_bed tests (require FFmpeg)
# ---------------------------------------------------------------------------

@requires_ffmpeg
@pytest.mark.parametrize("mood", ["tension_pulse", "clinical_drone", "mechanical_hum"])
def test_generate_audio_bed_creates_file(tmp_path, mood):
    """Verify that generate_audio_bed creates a non-empty WAV file."""
    path = generate_audio_bed(mood, 5.0, str(tmp_path))
    from pathlib import Path
    p = Path(path)
    assert p.exists(), f"Expected file at {path}"
    assert p.stat().st_size > 0, "Generated audio bed must be non-empty"
    assert p.suffix == ".wav"


@requires_ffmpeg
@pytest.mark.parametrize("mood", ["tension_pulse", "clinical_drone", "mechanical_hum"])
def test_generate_audio_bed_duration(tmp_path, mood):
    """Verify that generated audio duration approximately matches requested duration."""
    requested = 10.0
    path = generate_audio_bed(mood, requested, str(tmp_path))
    # Probe duration using wave module
    import wave
    with wave.open(path, "rb") as wf:
        actual_duration = wf.getnframes() / wf.getframerate()
    assert abs(actual_duration - requested) < 0.5, (
        f"Duration mismatch: requested {requested}s, got {actual_duration}s"
    )


@requires_ffmpeg
def test_generate_audio_bed_short_duration(tmp_path):
    """Very short durations should still work without crashing."""
    path = generate_audio_bed("clinical_drone", 1.0, str(tmp_path))
    from pathlib import Path
    assert Path(path).exists()
    assert Path(path).stat().st_size > 0


def test_generate_audio_bed_invalid_mood(tmp_path):
    """Unknown moods must raise ValueError."""
    with pytest.raises(ValueError, match="Unknown audio bed mood"):
        generate_audio_bed("nonexistent_mood", 5.0, str(tmp_path))


def test_generate_audio_bed_zero_duration(tmp_path):
    """Zero or negative duration must raise ValueError."""
    with pytest.raises(ValueError, match="positive"):
        generate_audio_bed("clinical_drone", 0.0, str(tmp_path))
    with pytest.raises(ValueError, match="positive"):
        generate_audio_bed("clinical_drone", -1.0, str(tmp_path))
