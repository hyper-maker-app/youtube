"""Lightweight inter-episode continuity persistence (ADR-090 compliant, zero-hardcoding)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_series_continuity(series_dir: Path) -> dict[str, Any] | None:
    """Load previously saved continuity state if available."""
    state_file = series_dir / "continuity_state.json"
    if not state_file.is_file():
        return None
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception as exc:
        logger.warning(f"Could not read continuity state from {state_file}: {exc}")
    return None


def save_series_continuity(
    series_dir: Path,
    episode_num: int,
    ending_state: str,
    telemetry: dict[str, Any] | None = None,
    world_state: dict[str, Any] | None = None,
) -> None:
    """Persist ending state and structured telemetry to inform the next episode."""
    if not ending_state or not ending_state.strip():
        return
    state_file = series_dir / "continuity_state.json"
    payload: dict[str, Any] = {
        "last_completed_episode": episode_num,
        "ending_character_state": ending_state.strip(),
    }
    if telemetry:
        payload["dynamic_telemetry"] = telemetry
    if world_state:
        payload["world_state"] = world_state
    try:
        state_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Saved episode {episode_num} continuity state -> {state_file}")
    except Exception as exc:
        logger.warning(f"Failed to persist continuity state: {exc}")


def build_continuity_prompt_suffix(continuity: dict[str, Any] | None) -> str:
    """Format previous episode ending state as a gentle context instruction for the LLM."""
    if not continuity or not continuity.get("ending_character_state"):
        return ""
    state_str = str(continuity["ending_character_state"]).strip()
    last_ep = continuity.get("last_completed_episode", 1)
    return (
        f"\n\n=== PREVIOUS EPISODE CONTINUITY CONTEXT ===\n"
        f"At the conclusion of Episode {last_ep}, the protagonist's physical state, appearance, injuries, "
        f"wardrobe condition, and held items were:\n\"{state_str}\"\n"
        f"MANDATE: Seamlessly maintain this exact physical appearance and state at the beginning of Episode {last_ep + 1}. "
        f"Do not magically reset or erase damage, torn clothing, or held inventory without an authored in-story cause."
    )
