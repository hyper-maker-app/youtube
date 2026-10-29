"""Bridge adapter connecting Grok-Imagine-Cinematic-Studio tools to YOUTUBE_STUDIO pipeline.

Compliant with ADR-090 (Zero-hardcoding mandate) and AST clean boundaries.
Imports and orchestrates Production Bible creation, Character DNA locks,
and Wardrobe Continuity from vendor/Grok-Imagine-Cinematic-Studio.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Ensure vendor tools are available on sys.path
_VENDOR_TOOLS = Path(__file__).resolve().parents[1] / "vendor" / "Grok-Imagine-Cinematic-Studio" / "tools"
if _VENDOR_TOOLS.is_dir() and str(_VENDOR_TOOLS) not in sys.path:
    sys.path.insert(0, str(_VENDOR_TOOLS))


def get_cinematic_studio_system_directives(dialogue_style: str = "first_person") -> str:
    """Return genre-agnostic Hollywood 3-act narrative directives.

    Supports multiple generic dialogue modes (ADR-090 compliant, zero-hardcoding):
    - 'first_person': In-world protagonist voice (field logs, internal monologue, comms, or journal).
    - 'external_narrator': Traditional third-person documentary / cinematic narrator.
    """
    if dialogue_style == "first_person":
        dialogue_rule = (
            "5. First-Person Character Voice & In-World Perspective:\n"
            "   - Voiceover is authored in the protagonist's urgent first-person perspective matching the setting (e.g. in-world logs, internal thoughts, situational commentary, or recordings appropriate to the genre).\n"
            "   - Visual Staging: Frame the protagonist's expressive eyes, hands operating setting-appropriate tools/gear, and environmental reactions, keeping mouth posture natural to prevent AI facial distortion."
        )
    elif dialogue_style == "external_narrator":
        dialogue_rule = (
            "5. Cinematic External Narration:\n"
            "   - Voiceover is delivered by an authoritative external narrator detailing the stakes, physics, and causal chain reaction of the protagonist's predicament.\n"
            "   - Visual Staging: The protagonist experiences the physical reality while the external voice guides the viewer through the narrative."
        )
    else:
        dialogue_rule = (
            "5. In-World Narrative Delivery:\n"
            "   - Deliver the audio track organically matching the authored narrative world, preserving facial stability and physical cause-and-effect."
        )

    return (
        "Cinematic Narrative & Arc Rules (Grok Imagine Studio Standard):\n"
        "1. Opening Hook: First scene must immediately establish the physical obstacle, hazard, or active choice.\n"
        "2. Causal Escalation: Every subsequent scene must be the direct physical consequence of the previous action.\n"
        "3. Midpoint Turning Point: At the middle scene, the protagonist must encounter an irreversible threshold, critical choice, or mechanical change.\n"
        "4. Climax & Cliffhanger: The final scene must culminate in a high-stakes pause or unresolved question driving the subsequent episode.\n"
        f"{dialogue_rule}"
    )


def init_series_production_bible(
    series_dir: Path,
    title: str,
    genre: str = "Sci-Fi Survival",
    director_signature: str = "Immersive physical realism",
    target_duration_seconds: int = 60,
    complexity: str = "Medium",
    world_rules: list[str] | None = None,
    dialogue_style: str = "first_person",
) -> dict[str, Any]:
    """Create or load the rich Production Bible for a fiction series."""
    bible_file = series_dir / "series_bible.json"
    if bible_file.is_file():
        try:
            existing = json.loads(bible_file.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                logger.info(f"Loaded existing Production Bible from {bible_file}")
                return existing
        except Exception as exc:
            logger.warning(f"Could not parse existing bible at {bible_file}: {exc}")

    try:
        from cli.production import build_production_bible  # type: ignore
        bible = build_production_bible(
            title,
            genre=genre,
            director_signature=director_signature,
            target_duration_seconds=target_duration_seconds,
            complexity=complexity,
            chat_model="grok-4.20-0309-non-reasoning",
            video_model="flow_omni_flash",
        )
    except Exception as exc:
        logger.warning(f"Fallback to generic bible builder due to import error: {exc}")
        bible = {
            "project_title": title,
            "genre": genre,
            "director_signature": director_signature,
            "target_duration_seconds": target_duration_seconds,
            "complexity": complexity,
        }

    bible["world_rules"] = world_rules or [
        "Physical cause-and-effect strictly governs all mechanisms and environment transitions.",
        "Characters do not speak aloud; external narration provides context while mouths remain closed.",
        "Damage, wear, and inventory state carry over between episodes without reset.",
    ]
    bible["series_id"] = series_dir.name
    bible["dialogue_style"] = dialogue_style

    try:
        bible_file.write_text(json.dumps(bible, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Initialized rich Production Bible at {bible_file}")
    except Exception as exc:
        logger.warning(f"Could not persist series bible to {bible_file}: {exc}")

    return bible


def create_character_dna_lock(
    character_name: str,
    *,
    core_identity: str,
    facial_dna: str,
    hair_grooming: str = "practical cut",
    clothing_style: str = "tactical utility wear",
    wardrobe_label: str = "Primary field attire",
    wardrobe_silhouette: str = "functional workwear",
    wardrobe_condition: str = "worn",
    inject_anchors: list[str] | None = None,
) -> dict[str, Any]:
    """Create a persistent Character DNA and Wardrobe Lock profile using Grok Imagine Studio schemas."""
    try:
        import character_dna  # type: ignore
        import wardrobe_lock  # type: ignore

        anchors = inject_anchors or []
        dna = character_dna.create_dna_scaffold(
            character_name,
            core_identity=core_identity,
            facial_dna=facial_dna,
            hair_grooming=hair_grooming,
            clothing_style=clothing_style,
            key_anchors=anchors,
        )

        valid_condition = wardrobe_condition if wardrobe_condition in wardrobe_lock.CONDITION_VALUES else "worn"
        w_lock = wardrobe_lock.create_wardrobe_lock(
            label=wardrobe_label,
            silhouette=wardrobe_silhouette,
            condition_default=valid_condition,
            inject_anchors=anchors,
        )
        dna["wardrobe_lock"] = w_lock
        return dna
    except Exception as exc:
        logger.warning(f"Could not build vendor Character DNA scaffold: {exc}")
        return {
            "character_name": character_name,
            "core_identity": core_identity,
            "facial_dna": facial_dna,
            "hair_grooming": hair_grooming,
            "clothing_style": clothing_style,
            "key_consistency_anchors": inject_anchors or [],
        }


def format_cinematic_prompt_with_locks(
    base_visual_prompt: str,
    character_dna_lock: dict[str, Any] | None = None,
    continuity_state: str = "",
) -> str:
    """Format visual prompt with [CHARACTER_DNA] and [WARDROBE_LOCK] tokens for Flow video synthesis."""
    if not character_dna_lock:
        if continuity_state:
            return f"{base_visual_prompt}. [CONTINUITY_STATE: {continuity_state}]"
        return base_visual_prompt

    name = str(character_dna_lock.get("character_name", "PROTAGONIST")).upper()
    face = str(character_dna_lock.get("facial_dna", "")).strip()
    clothing = str(character_dna_lock.get("clothing_style", "")).strip()
    anchors = ", ".join(character_dna_lock.get("key_consistency_anchors", []))

    dna_tag = f"[CHARACTER_DNA: {name} = {face}; hair: {character_dna_lock.get('hair_grooming', '')}]"
    wardrobe_tag = f"[WARDROBE_LOCK: {clothing}"
    if anchors:
        wardrobe_tag += f"; anchors: {anchors}"
    wardrobe_tag += "]"

    parts = [dna_tag, wardrobe_tag, base_visual_prompt]
    if continuity_state:
        parts.append(f"[CONTINUITY_STATE: {continuity_state}]")

    return " ".join(parts)
