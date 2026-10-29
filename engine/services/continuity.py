"""Lightweight inter-episode continuity persistence and EpisodeHandoff (UDSE v4.3 / Grok 4.6 Standard).

Guarantees seamless narrative continuity across episodes (survivor injuries, wardrobe condition,
held inventory items, and resource levels) via cryptographically verifiable immutable snapshots.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Standardized Resource Registry (Grok 4.6 Mandate: enum/registry based, zero loose string hacking)
RECOGNISED_RESOURCES: frozenset[str] = frozenset({
    "flashlight_battery_pct",
    "pry_bar_integrity_pct",
    "duct_tape_layers",
    "water_ml",
    "rations_cal",
    "decibel_threshold_db",
    "barricade_integrity_pct",
})


@dataclass
class CharacterHandoffState:
    id: str
    injuries: list[str] = field(default_factory=list)
    wardrobe: str = ""
    held_items: list[str] = field(default_factory=list)
    resources: dict[str, Any] = field(default_factory=dict)
    scars: list[str] = field(default_factory=list)


@dataclass
class EpisodeHandoff:
    from_episode: int
    to_episode: int
    world_snapshot_id: str
    characters: list[CharacterHandoffState] = field(default_factory=list)
    set_states: dict[str, Any] = field(default_factory=dict)
    unresolved_deltas: list[dict[str, Any]] = field(default_factory=list)
    continuity_hash: str = ""

    def calculate_hash(self) -> str:
        data = {
            "from_episode": self.from_episode,
            "to_episode": self.to_episode,
            "world_snapshot_id": self.world_snapshot_id,
            "characters": [asdict(c) for c in self.characters],
            "set_states": self.set_states,
            "unresolved_deltas": self.unresolved_deltas,
        }
        canonical_bytes = json.dumps(data, sort_keys=True, ensure_ascii=True).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()

    def freeze(self, out_dir: Path) -> Path:
        """Freeze into an immutable handoff snapshot artifact."""
        self.continuity_hash = self.calculate_hash()
        out_dir.mkdir(parents=True, exist_ok=True)
        handoff_path = out_dir / "episode_handoff.json"
        payload = {
            "from_episode": self.from_episode,
            "to_episode": self.to_episode,
            "world_snapshot_id": self.world_snapshot_id,
            "characters": [asdict(c) for c in self.characters],
            "set_states": self.set_states,
            "unresolved_deltas": self.unresolved_deltas,
            "continuity_hash": self.continuity_hash,
        }
        handoff_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"[EpisodeHandoff] Frozen Episode {self.from_episode} -> {self.to_episode} (hash: {self.continuity_hash[:12]}...)")
        return handoff_path

    @classmethod
    def thaw(cls, handoff_path: Path) -> "EpisodeHandoff":
        """Thaw and cryptographically verify previous episode handoff."""
        if not handoff_path.is_file():
            raise FileNotFoundError(f"Continuity handoff artifact not found: {handoff_path}")
        data = json.loads(handoff_path.read_text(encoding="utf-8"))
        chars = [
            CharacterHandoffState(
                id=c.get("id", "survivor"),
                injuries=list(c.get("injuries", [])),
                wardrobe=c.get("wardrobe", ""),
                held_items=list(c.get("held_items", [])),
                resources=dict(c.get("resources", {})),
                scars=list(c.get("scars", [])),
            )
            for c in data.get("characters", [])
        ]
        handoff = cls(
            from_episode=int(data.get("from_episode", 1)),
            to_episode=int(data.get("to_episode", 2)),
            world_snapshot_id=str(data.get("world_snapshot_id", "")),
            characters=chars,
            set_states=dict(data.get("set_states", {})),
            unresolved_deltas=list(data.get("unresolved_deltas", [])),
            continuity_hash=str(data.get("continuity_hash", "")),
        )
        expected_hash = handoff.calculate_hash()
        if handoff.continuity_hash and handoff.continuity_hash != expected_hash:
            logger.warning(
                f"[EpisodeHandoff] Continuity hash mismatch! Got {handoff.continuity_hash[:8]}, expected {expected_hash[:8]}"
            )
        return handoff


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
    character_id: str | None = None,
    wardrobe: str | None = None,
    held_items: list[str] | None = None,
    set_states: dict[str, Any] | None = None,
) -> None:
    """Persist ending state and structured telemetry to inform the next episode (ADR-090 Zero-Hardcoding)."""
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

        # Extract dynamic entity and character state (ADR-090 compliant, zero-hardcoding)
        active_char_id = character_id or "protagonist"
        active_wardrobe = wardrobe or ""
        active_items = held_items or []
        dynamic_sets = set_states or {}

        if world_state and "entities" in world_state:
            for ent_id, ent_info in world_state["entities"].items():
                if isinstance(ent_info, dict):
                    if ent_info.get("kind") in ("character", "protagonist", "actor"):
                        active_char_id = ent_id
                        if not active_wardrobe and "active_wear" in ent_info:
                            active_wardrobe = str(ent_info.get("active_wear", ""))
                    elif ent_info.get("kind") in ("set", "prop", "barrier"):
                        if ent_id not in dynamic_sets:
                            dynamic_sets[ent_id] = ent_info.get("active_wear") or ent_info.get("material_class", "intact")

        char_state = CharacterHandoffState(
            id=active_char_id,
            wardrobe=active_wardrobe,
            held_items=active_items,
            resources=telemetry or {},
        )
        handoff = EpisodeHandoff(
            from_episode=episode_num,
            to_episode=episode_num + 1,
            world_snapshot_id=f"ep_{episode_num:02d}_final",
            characters=[char_state],
            set_states=dynamic_sets,
            unresolved_deltas=world_state.get("delta_ledger", []) if world_state else [],
        )
        handoff.freeze(series_dir)
    except Exception as exc:
        logger.warning(f"Failed to persist continuity state: {exc}")


def apply_handoff_to_scenes(
    scenes: list[dict[str, Any]],
    handoff: EpisodeHandoff,
) -> list[dict[str, Any]]:
    """Inject thawed continuity invariants into initial scenes for seamless multi-episode continuation."""
    if not scenes or not handoff:
        return scenes

    first_scene = dict(scenes[0])
    vp = first_scene.get("visual_prompt", "")

    invariants: list[str] = []
    for char in handoff.characters:
        if char.wardrobe:
            invariants.append(f"{char.id} wears {char.wardrobe}")
        if char.held_items:
            invariants.append(f"holding {', '.join(char.held_items)}")
        if char.injuries:
            invariants.append(f"visible injuries: {', '.join(char.injuries)}")

    for set_id, state in handoff.set_states.items():
        if state:
            invariants.append(f"{set_id} state is {state}")

    if invariants:
        continuity_clause = f"Established continuity from Episode {handoff.from_episode}: {'; '.join(invariants)}."
        first_scene["visual_prompt"] = f"{vp}. {continuity_clause}" if vp else continuity_clause
        first_scene["continuity_thawed"] = True
        scenes[0] = first_scene
        logger.info(f"[EpisodeHandoff] Successfully injected Episode {handoff.from_episode} continuity into Scene 01.")

    return scenes


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
