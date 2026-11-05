from pathlib import Path

import pytest

from engine.services import media_tools


def test_ffprobe_override_takes_precedence(tmp_path, monkeypatch):
    binary = tmp_path / "ffprobe"
    binary.write_bytes(b"test")
    monkeypatch.setenv("FFPROBE_BINARY", str(binary))
    monkeypatch.setattr(media_tools.shutil, "which", lambda name: pytest.fail("unexpected PATH lookup"))
    assert media_tools.find_ffprobe() == str(binary)


def test_invalid_override_is_not_silently_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("FFPROBE_BINARY", str(tmp_path / "missing"))
    with pytest.raises(ValueError, match="FFPROBE_BINARY"):
        media_tools.find_ffprobe()


def test_ffmpeg_sibling_is_used_when_probe_not_on_path(tmp_path, monkeypatch):
    ffmpeg = tmp_path / "ffmpeg"
    ffprobe = tmp_path / ("ffprobe.exe" if media_tools.os.name == "nt" else "ffprobe")
    ffprobe.write_bytes(b"test")
    monkeypatch.delenv("FFPROBE_BINARY", raising=False)
    monkeypatch.setenv("FFMPEG_BINARY", str(ffmpeg))
    monkeypatch.setattr(media_tools.shutil, "which", lambda name: None)
    assert Path(media_tools.find_ffprobe()) == ffprobe
