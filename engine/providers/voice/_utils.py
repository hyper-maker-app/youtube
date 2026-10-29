"""Provider-neutral helpers for narration adapter results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def beat_value(beat: object, name: str, default: Any = None) -> Any:
    """Read the same field from the persisted Beat dataclass or a mapping."""
    if isinstance(beat, dict):
        return beat.get(name, default)
    return getattr(beat, name, default)


def narration_text(beats: list[object]) -> str:
    try:
        from engine.services.text_sanitizer import sanitize_spoken_text
        text = " ".join(sanitize_spoken_text(str(beat_value(beat, "text", ""))) for beat in beats)
    except Exception:
        text = " ".join(str(beat_value(beat, "text", "")).strip() for beat in beats)
    text = " ".join(text.split())
    if not text:
        raise ValueError("generate_narration requires at least one non-empty beat")
    return text


def words_path_for(out_path: Path) -> Path:
    """Keep the existing run-level words.json convention when output is audio/vo.mp3."""
    return out_path.parent.parent / "words.json" if out_path.parent.name == "audio" else out_path.with_name("words.json")


def write_words(
    out_path: Path,
    words: list[dict[str, Any]],
    *,
    provider: str,
    voice_id: str,
    lang: str,
    duration: float,
    **extra: Any,
) -> Path:
    """Persist the existing words.json shape without ever serializing credentials."""
    payload: dict[str, Any] = {
        "provider": provider,
        "voice_id": voice_id,
        "lang": lang,
        "duration": round(float(duration), 3),
        "loss": None,
        "words": words,
        **extra,
    }
    path = words_path_for(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
