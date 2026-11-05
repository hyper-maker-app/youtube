"""Generic character identity and character-sheet management.

Defines a generic, parametric character profile model designed for visual stability
across AI models, supporting dynamic character attributes, wardrobe, and accessories
without hardcoded narrative lore or static personas.
Zero network/provider calls are made in this module.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import config


# Generic default constants (empty / neutral for zero-hardcode invariant)
DEFAULT_TIME_DEVICE: str = ""
ERA_WARDROBE_CATALOG: dict[str, str] = {}
ERA_WITNESS_CATALOG: dict[str, list[dict[str, str]]] = {}


def detect_era(text: str) -> str:
    """Infer era identifier from input or return neutral default."""
    if not text:
        return "default"
    cleaned = str(text).strip().casefold()
    slug = re.sub(r"[^\w]+", "_", cleaned).strip("_")
    return slug or "default"


def get_era_witness(
    era: str = "default",
    slot: int = 1,
    custom_witness: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return a witness profile for the given era and slot."""
    if custom_witness:
        return dict(custom_witness)
    key = (era or "default").strip().casefold()
    pool = ERA_WITNESS_CATALOG.get(key)
    if pool:
        idx = max(0, min(len(pool) - 1, slot - 1))
        return dict(pool[idx])
    return {
        "id": f"witness_{slot}",
        "name": f"Witness {slot}",
        "era_label": era.replace("_", " ").title() if era and era != "default" else "Historical Record",
        "location_stamp": f"{era.replace('_', ' ').upper()} — ON SITE" if era and era != "default" else "HISTORICAL ARCHIVE",
        "appearance": "authentic individual in era-appropriate attire and setting",
    }


@dataclass(frozen=True)
class CharacterProfile:
    """Immutable persistent character identity designed for visual stability across AI models."""

    name: str = "Protagonist"
    gender: str = "unspecified"
    age_range: str = "adult"
    archetype: str = "lead subject"
    face_traits: str = "natural skin texture, authentic facial features, focused and attentive expression"
    hair_traits: str = "natural hair texture, practical cut"
    time_device: str = DEFAULT_TIME_DEVICE
    wardrobe: str = "practical field attire with authentic textures"
    accessories: str = ""
    default_expression: str = "focused, attentive presence"
    wardrobe_catalog: dict[str, str] = field(default_factory=dict)

    def wardrobe_for_era(self, era: str = "default") -> str:
        """Return era-appropriate wardrobe from catalog or fallback to base wardrobe."""
        if self.wardrobe_catalog:
            key = (era or "default").strip().casefold()
            return self.wardrobe_catalog.get(key, self.wardrobe)
        return self.wardrobe

    def anchor_description(self, era: str = "default") -> str:
        """Condensed visual anchor string injected into prompts to lock appearance."""
        active_wardrobe = self.wardrobe_for_era(era) if era else self.wardrobe
        parts = [
            f"{self.name}, a {self.age_range} {self.gender} {self.archetype}",
            f"FACE LOCK: {self.face_traits}",
            f"HAIR: {self.hair_traits}",
        ]
        if self.time_device:
            parts.append(f"SIGNATURE ARTIFACT: {self.time_device}")
        parts.append(f"WARDROBE: wearing {active_wardrobe}")
        if self.accessories:
            parts.append(self.accessories)
        return "; ".join(parts)


DEFAULT_CHARACTER = CharacterProfile()


@dataclass(frozen=True)
class CharacterSheetSpec:
    """Multi-view reference sheet specifications to generate and preserve a consistent character."""

    character: CharacterProfile
    aspect_ratio: str = "16:9"

    def frontal_portrait_prompt(self, era: str = "default") -> str:
        return (
            f"CHARACTER REFERENCE SHEET [FRONTAL CLOSE-UP]: {self.character.anchor_description(era)}. "
            "Front-facing portrait, eye-level camera, direct gaze at viewer, neutral closed mouth, "
            "subtle friendly confidence. Professional studio lighting, soft fill light, "
            "sharp focus on facial micro-features and skin texture, 8k resolution, cinematic photorealism, "
            f"{self.aspect_ratio} composition. ZERO text, ZERO watermarks."
        )

    def three_quarter_prompt(self, era: str = "default") -> str:
        return (
            f"CHARACTER REFERENCE SHEET [THREE-QUARTER VIEW]: {self.character.anchor_description(era)}. "
            "Three-quarter angle portrait, looking slightly off-camera, curious inquisitive gaze, "
            "cinematic natural backlight, realistic hair strands, sharp eye catchlights, "
            f"documentary photography quality, {self.aspect_ratio} composition. ZERO text, ZERO watermarks."
        )

    def field_action_prompt(self, location_hint: str = "on location", era: str = "default") -> str:
        return (
            f"CHARACTER REFERENCE SHEET [FIELD ACTION]: {self.character.anchor_description(era)}. "
            f"Mid-shot holding camera in vlog style on location at {location_hint}. "
            "Background with cinematic atmospheric depth of field blur, natural lighting, "
            "expressive posture, realistic fabric creases, "
            f"photorealistic 8k documentary frame, {self.aspect_ratio} composition. ZERO text, ZERO watermarks."
        )

    def artifact_macro_prompt(self) -> str:
        item = self.character.time_device or "character signature item"
        return (
            f"CHARACTER REFERENCE SHEET [PROP CLOSE-UP]: Extreme macro close-up of {item}. "
            "Authentic surface textures, fine material details, "
            f"dramatic cinematic directional macro lighting, shallow depth of field, 8k photorealism, {self.aspect_ratio} composition. "
            "ZERO text, ZERO watermarks."
        )

    def era_camouflage_prompt(self, era: str) -> str:
        return (
            f"CHARACTER REFERENCE SHEET [WARDROBE VARIATION - {era.upper()}]: {self.character.anchor_description(era)}. "
            f"Medium full shot of character walking through authentic {era} setting. "
            f"Golden hour atmospheric volumetric lighting, authentic textures, 8k photorealistic cinema, {self.aspect_ratio} composition. "
            "ZERO text, ZERO watermarks."
        )

    def to_manifest(self) -> dict[str, Any]:
        sheets = {
            "frontal": self.frontal_portrait_prompt(),
            "three_quarter": self.three_quarter_prompt(),
            "field_action": self.field_action_prompt(),
            "artifact_macro": self.artifact_macro_prompt(),
        }
        return {
            "name": self.character.name,
            "gender": self.character.gender,
            "anchor": self.character.anchor_description(),
            "sheets": sheets,
            "hash": hashlib.sha256(self.character.anchor_description().encode("utf-8")).hexdigest(),
        }


def get_active_character() -> CharacterProfile:
    """Resolve active character profile from environment or default."""
    char_name = getattr(config, "EXPLORER_CHARACTER_NAME", "") or "Protagonist"
    return CharacterProfile(name=char_name.strip().capitalize())


def classify_shot_role(shot_index: int, total_shots: int, journey_phase: str = "explore") -> dict[str, Any]:
    """Classify a shot into Host A-Roll, Eyewitness Interview, or Pure B-Roll."""
    is_opening = (shot_index == 1)
    is_closing = (shot_index == total_shots and total_shots >= 3)
    mid_index = max(2, (total_shots // 2) + 1)
    is_turning_point = (shot_index == mid_index and total_shots >= 6)

    witness_1_idx = max(3, (total_shots * 2) // 7) if total_shots >= 8 else -1
    witness_2_idx = min(total_shots - 2, (total_shots * 5) // 7) if total_shots >= 10 else -1
    if witness_1_idx in {1, mid_index, total_shots}:
        witness_1_idx = max(2, mid_index - 2)
    if witness_2_idx in {1, mid_index, total_shots, witness_1_idx}:
        witness_2_idx = min(total_shots - 1, mid_index + 2)

    if is_opening:
        return {
            "role": "a_roll",
            "speaker": "narrator",
            "is_speaking_avatar": True,
            "is_witness_interview": False,
            "camera_style": "vlog_selfie_host",
            "description": "On-camera host arrival hook: direct address to viewer, introducing site/mystery",
            "lip_sync_required": False,
        }
    if is_closing:
        return {
            "role": "a_roll",
            "speaker": "narrator",
            "is_speaking_avatar": True,
            "is_witness_interview": False,
            "camera_style": "vlog_selfie_host",
            "description": "On-camera host sign-off: closing reflection and key takeaway",
            "lip_sync_required": False,
        }
    if is_turning_point:
        return {
            "role": "a_roll",
            "speaker": "narrator",
            "is_speaking_avatar": True,
            "is_witness_interview": False,
            "camera_style": "vlog_selfie_reaction",
            "description": "On-camera host reaction: reacting to pivotal clue or reveal",
            "lip_sync_required": False,
        }
    if shot_index == witness_1_idx:
        return {
            "role": "witness_interview",
            "speaker": "witness",
            "witness_slot": 1,
            "is_speaking_avatar": False,
            "is_witness_interview": True,
            "camera_style": "historical_witness_interview",
            "description": "Field interview with eyewitness in authentic setting",
            "lip_sync_required": False,
        }
    if shot_index == witness_2_idx:
        return {
            "role": "witness_interview",
            "speaker": "witness",
            "witness_slot": 2,
            "is_speaking_avatar": False,
            "is_witness_interview": True,
            "camera_style": "historical_witness_interview",
            "description": "Field interview with secondary witness in authentic setting",
            "lip_sync_required": False,
        }

    return {
        "role": "b_roll",
        "speaker": "narrator",
        "is_speaking_avatar": False,
        "is_witness_interview": False,
        "camera_style": "cinematic_documentary",
        "description": "Cinematic visual B-roll with voiceover narration: atmospheric environment/mechanism",
        "lip_sync_required": False,
    }


def compile_character_shot_prompt(
    character: CharacterProfile,
    environment_scene: str,
    shot_role_info: dict[str, Any],
    aspect_ratio: str = "16:9",
    era: str = "default",
) -> str:
    """Compile photorealistic prompt for an on-camera character shot incorporating character anchor."""
    style_str = f"{aspect_ratio} widescreen composition, photorealistic 8k documentary cinema"
    camera_style = shot_role_info.get("camera_style", "vlog_selfie_host")

    if camera_style == "vlog_selfie_host":
        framing = (
            "Medium close-up eye-level documentary framing with complete head, hair, and shoulders fully inside frame "
            "(generous headroom above crown of head, NEVER crop forehead or top of head), "
            "host looking directly into the camera lens with a quiet attentive expression, closed neutral mouth, "
            "warm engaged eyes, and confident documentary presence; all narration is external voiceover"
        )
    elif camera_style == "vlog_selfie_reaction":
        framing = (
            "Medium eye-level shot with complete head and shoulders fully inside frame "
            "(generous headroom above head, NEVER crop head), host turning toward camera with wide attentive eyes and a closed neutral mouth, "
            "spontaneous real-time discovery reaction and expressive posture; all narration is external voiceover"
        )
    else:
        framing = "Medium eye-level shot with full headroom, host standing in environment inspecting surroundings with a closed neutral mouth; all narration is external voiceover"

    return (
        f"[CHARACTER A-ROLL]: {character.anchor_description(era=era)}. {framing}. "
        f"Background: {environment_scene}, deep atmospheric perspective, cinematic lighting, "
        f"accurate environmental color grading, authentic field dust and texture, {style_str}. "
        "STRICT VISUAL MANDATE: ZERO text, ZERO printed letters, ZERO typography, ZERO date stamps, "
        "ZERO year numbers written on image, ZERO name plaques, ZERO title banners, ZERO graphic cards, "
        "ZERO caption boxes, ZERO lower thirds, ZERO subtitles, ZERO HUD overlay, ZERO fake watermarks."
    )


def compile_witness_shot_prompt(
    witness: dict[str, str],
    environment_scene: str,
    aspect_ratio: str = "16:9",
    era: str = "default",
) -> str:
    """Compile photorealistic prompt for an interview shot."""
    style_str = f"{aspect_ratio} widescreen composition, photorealistic 8k documentary cinema"
    name = witness.get("name", "Eyewitness")
    era_label = witness.get("era_label", "Setting")
    appearance = witness.get("appearance", "authentic individual in era-appropriate attire")
    return (
        f"[EYEWITNESS INTERVIEW — {name.upper()} ({era_label})]: "
        f"Medium eye-level documentary interview portrait of {appearance}, "
        "complete head and shoulders fully visible inside frame with generous headroom, "
        "quiet attentive expression with a closed neutral mouth; all narration is external voiceover, "
        "natural directional key light on weathered skin textures. "
        f"Background: {environment_scene}, authentic setting atmosphere, shallow depth of field, {style_str}. "
        "STRICT VISUAL MANDATE: ZERO text, ZERO printed letters, ZERO typography, ZERO date stamps, "
        "ZERO year numbers written on image, ZERO name plaques, ZERO title banners, ZERO graphic cards, "
        "ZERO caption boxes, ZERO lower thirds, ZERO subtitles, ZERO watermarks."
    )


def get_host_lipsync_provider() -> str:
    """Return active lip-sync engine name from configuration."""
    return str(getattr(config, "EXPLORER_LIPSYNC_PROVIDER", "live_portrait") or "live_portrait").lower()


def is_lipsync_required_for_shot(shot_role_info: dict[str, Any]) -> bool:
    """Return only an explicit authored opt-in for talking-avatar animation."""
    return bool(shot_role_info.get("lip_sync_required") is True)


def get_grok_character_dna(character: CharacterProfile | None = None, era: str = "default") -> str:
    """Format character into Grok Cinematic Studio [CHARACTER_DNA] token structure."""
    char = character or DEFAULT_CHARACTER
    try:
        import sys
        tools_path = Path(__file__).resolve().parents[1] / "vendor" / "Grok-Imagine-Cinematic-Studio" / "tools"
        if str(tools_path) not in sys.path:
            sys.path.insert(0, str(tools_path))
        import character_dna

        scaffold = character_dna.create_dna_scaffold(
            char.name,
            core_identity=f"{char.age_range} {char.gender} {char.archetype}",
            facial_dna=char.face_traits,
            hair_grooming=char.hair_traits,
            clothing_style=char.wardrobe_for_era(era),
            key_anchors=[char.time_device, char.accessories] if char.time_device or char.accessories else [],
        )
        identity = scaffold.get("core_identity", "")
        return f"[CHARACTER_DNA: {char.name.upper()} = {identity}, {char.face_traits}, {char.hair_traits}, wearing {char.wardrobe_for_era(era)}]"
    except Exception:
        return f"[CHARACTER_DNA: {char.name.upper()} = {char.anchor_description(era)}]"
