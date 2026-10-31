"""Automatic SFX categorization and Audiogen/TangoFlux prompt synthesis.

Analyzes scene narration, visual prompts, and metadata to automatically extract
the primary sound effects category and generate prompt directives for
Audiogen, TangoFlux, or local FFmpeg Lavfi procedural synthesis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SfxCategoryMatch:
    """Matched SFX category with generated synthesis prompt and parameters."""

    category: str
    audiogen_prompt: str
    duration: float
    tags: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)

    @property
    def prompt(self) -> str:
        """Alias for audiogen_prompt for backwards compatibility."""
        return self.audiogen_prompt


# Ordered priority: High-impact crisis events precede ambient background drones
_SFX_CATEGORY_TAXONOMY: list[dict[str, Any]] = [
    {
        "category": "explosion",
        "keywords": (
            "explosion", "explode", "blast", "detonation", "erupt", "eruption",
            "burst", "blow up", "dynamite", "shockwave", "magma blast", "caldera",
            "supervolcano", "volcano", "pyroclastic blast",
        ),
        "audiogen_prompt": "large explosion with shockwave",
        "duration": 2.5,
        "tags": ["explosion", "shockwave", "blast", "foley"],
    },
    {
        "category": "tsunami_water",
        "keywords": (
            "tsunami", "water", "flood", "surge", "tidal wave", "ocean wave",
            "deluge", "splash", "cascade", "submerge", "cataclysmic wave",
            "wave", "torrent",
        ),
        "audiogen_prompt": "massive tidal wave roaring impact",
        "duration": 3.0,
        "tags": ["tsunami", "water", "wave", "impact", "foley"],
    },
    {
        "category": "alarm_siren",
        "keywords": (
            "alarm", "siren", "klaxon", "warning", "alert", "evacuate",
            "emergency", "beacon", "countdown",
        ),
        "audiogen_prompt": "emergency klaxon siren",
        "duration": 2.0,
        "tags": ["alarm", "siren", "klaxon", "emergency", "foley"],
    },
    {
        "category": "earthquake_rumble",
        "keywords": (
            "earthquake", "rumble", "tectonic", "seismic", "tremor",
            "ground shaking", "fissure", "crust", "fault line", "collapse",
            "aftershock", "quaking",
        ),
        "audiogen_prompt": "deep seismic tectonic rumble",
        "duration": 3.0,
        "tags": ["earthquake", "rumble", "seismic", "tectonic", "foley"],
    },
    {
        "category": "fire_lava",
        "keywords": (
            "fire", "inferno", "blaze", "lava", "magma", "flame",
            "conflagration", "molten", "burn", "embers",
        ),
        "audiogen_prompt": "roaring volcanic lava inferno crackle",
        "duration": 2.5,
        "tags": ["fire", "lava", "inferno", "crackle", "foley"],
    },
    {
        "category": "sonar_ping",
        "keywords": (
            "sonar", "ping", "submarine", "depth", "ocean", "trench", "abyssal",
        ),
        "audiogen_prompt": "abyssal submarine sonar ping",
        "duration": 2.0,
        "tags": ["sonar", "ping", "submarine", "depth", "foley"],
    },
    {
        "category": "cyber_glitch",
        "keywords": (
            "glitch", "spark", "circuit", "cyber", "terminal", "hack",
            "retinal", "electric", "short circuit",
        ),
        "audiogen_prompt": "cybernetic electric glitch burst",
        "duration": 1.2,
        "tags": ["glitch", "electric", "cyber", "spark", "foley"],
    },
    {
        "category": "airlock_pneumatic",
        "keywords": (
            "airlock", "vent", "steam", "hiss", "pressure", "depressuriz",
            "decompression", "vacuum", "pneumatic",
        ),
        "audiogen_prompt": "pressurized valve airlock hiss",
        "duration": 1.8,
        "tags": ["airlock", "valve", "steam", "hiss", "pressure", "foley"],
    },
    {
        "category": "metal_impact",
        "keywords": (
            "metal", "blade", "sword", "clash", "portcullis", "shield",
            "arrow", "rampart", "iron", "steel",
        ),
        "audiogen_prompt": "iron metal clash impact",
        "duration": 1.5,
        "tags": ["metal", "clash", "impact", "iron", "foley"],
    },
    {
        "category": "door_impact",
        "keywords": (
            "slam", "door", "lock", "deadbolt", "impact", "crash",
            "collision", "barrier breach",
        ),
        "audiogen_prompt": "sub-bass impact door slam",
        "duration": 1.8,
        "tags": ["slam", "door", "impact", "sub_bass", "foley"],
    },
    {
        "category": "whoosh_transition",
        "keywords": (
            "whoosh", "sprint", "whip", "leap", "burst", "hatch",
            "swoosh", "swipe", "dash",
        ),
        "audiogen_prompt": "cinematic camera whip whoosh transition",
        "duration": 1.5,
        "tags": ["whoosh", "transition", "whip", "motion", "foley"],
    },
    {
        "category": "tension_heartbeat",
        "keywords": (
            "heartbeat", "pulse", "decibel", "breath", "whisper",
            "creeping", "dread", "suspense",
        ),
        "audiogen_prompt": "deep tension heartbeat pulse",
        "duration": 2.2,
        "tags": ["heartbeat", "pulse", "tension", "dread", "foley"],
    },
    {
        "category": "atmospheric_wind",
        "keywords": (
            "rain", "wind", "storm", "fog", "corridor", "drone",
            "radiation", "ash", "pyroclastic", "dust", "haze", "ambient",
        ),
        "audiogen_prompt": "atmospheric wind drone",
        "duration": 2.5,
        "tags": ["wind", "storm", "drone", "atmosphere", "foley"],
    },
]


def extract_sfx_category(scene_or_text: dict[str, Any] | str) -> SfxCategoryMatch | None:
    """Analyze a scene description or narration and extract the matching SFX category.
    
    Args:
        scene_or_text: A scene dictionary containing 'narration', 'visual_prompt',
                       'sfx_cue', or a raw text string.

    Returns:
        SfxCategoryMatch if keywords match an SFX category, else None.
    """
    if isinstance(scene_or_text, dict):
        text_parts = [
            str(scene_or_text.get("sfx_cue", "")),
            str(scene_or_text.get("narration", "")),
            str(scene_or_text.get("visual_prompt", "")),
            str(scene_or_text.get("description", "")),
            str(scene_or_text.get("motion_prompt", "")),
        ]
        combined = " ".join(text_parts).lower()
    else:
        combined = str(scene_or_text).lower()

    if not combined.strip():
        return None

    # Check taxonomy in order of priority
    for spec in _SFX_CATEGORY_TAXONOMY:
        matched: list[str] = [
            kw for kw in spec["keywords"]
            if re.search(r"\b" + re.escape(kw) + r"\b", combined) or kw in combined
        ]
        if matched:
            return SfxCategoryMatch(
                category=spec["category"],
                audiogen_prompt=spec["audiogen_prompt"],
                duration=float(spec["duration"]),
                tags=list(spec["tags"]),
                matched_keywords=matched,
            )

    return None


def auto_categorize_scene_sfx(
    scenes: list[dict[str, Any]],
    block_duration: float = 6.0,
) -> list[dict[str, Any]]:
    """Scan a sequence of scenes and produce a schedule of categorized SFX cues.
    
    Args:
        scenes: List of scene dictionaries.
        block_duration: Default duration per scene if not explicitly specified.

    Returns:
        List of SFX cue metadata dictionaries ready for asset resolution.
    """
    cues: list[dict[str, Any]] = []
    curr_time = 0.0

    for idx, sc in enumerate(scenes):
        sc_dur = float(sc.get("duration", block_duration))
        match = extract_sfx_category(sc)
        if match:
            cues.append({
                "cue_id": f"sfx_sc{idx + 1:02d}_{match.category}",
                "scene_index": idx,
                "category": match.category,
                "prompt": match.audiogen_prompt,
                "audiogen_prompt": match.audiogen_prompt,
                "duration": min(match.duration, sc_dur),
                "tags": match.tags,
                "matched_keywords": match.matched_keywords,
                "start_time": round(curr_time, 3),
                "end_time": round(curr_time + min(match.duration, sc_dur), 3),
            })
        curr_time += sc_dur

    return cues


def get_supported_sfx_categories() -> list[str]:
    """Return a list of all recognized SFX category identifiers."""
    return [spec["category"] for spec in _SFX_CATEGORY_TAXONOMY]
