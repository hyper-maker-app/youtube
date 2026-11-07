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


class DynamicSfxPrompt(str):
    """Dynamic SFX prompt string that can also be called as a factory with scene parameters."""

    category: str
    default_prompt: str

    def __new__(cls, default_prompt: str, category: str = "") -> DynamicSfxPrompt:
        obj = super().__new__(cls, default_prompt)
        obj.category = category
        obj.default_prompt = default_prompt
        return obj

    def synthesize(
        self,
        *,
        action: str = "",
        physical_context: str = "",
        parameters: dict[str, Any] | None = None,
        matched_keywords: list[str] | None = None,
    ) -> str:
        """Dynamically build an Audiogen/TangoFlux prompt from action, physical context, and parameters."""
        if not action and not physical_context and not parameters:
            return self.default_prompt

        parts: list[str] = []
        if physical_context:
            parts.append(physical_context.strip().rstrip(". "))
        if action:
            parts.append(action.strip().rstrip(". "))

        if parameters:
            for k, v in parameters.items():
                if v and isinstance(v, str):
                    parts.append(f"{k}: {v.strip()}")

        if not parts:
            return self.default_prompt

        synthesized = " ".join(parts)
        if self.default_prompt and not any(k in synthesized.lower() for k in self.default_prompt.lower().split()[:2]):
            return f"{synthesized} {self.default_prompt}".strip()
        return synthesized

    def __call__(
        self,
        *,
        action: str = "",
        physical_context: str = "",
        parameters: dict[str, Any] | None = None,
        matched_keywords: list[str] | None = None,
    ) -> str:
        return self.synthesize(
            action=action,
            physical_context=physical_context,
            parameters=parameters,
            matched_keywords=matched_keywords,
        )


# Ordered priority: High-impact crisis events precede ambient background drones
_SFX_CATEGORY_TAXONOMY: list[dict[str, Any]] = [
    {
        "category": "explosion",
        "keywords": (
            "explosion", "explode", "blast", "detonation", "erupt", "eruption",
            "burst", "blow up", "dynamite", "shockwave", "magma blast", "caldera",
            "supervolcano", "volcano", "pyroclastic blast",
        ),
        "audiogen_prompt": DynamicSfxPrompt("large explosion with shockwave", "explosion"),
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
        "audiogen_prompt": DynamicSfxPrompt("massive tidal wave roaring impact", "tsunami_water"),
        "duration": 3.0,
        "tags": ["tsunami", "water", "wave", "impact", "foley"],
    },
    {
        "category": "alarm_siren",
        "keywords": (
            "alarm", "siren", "klaxon", "warning", "alert", "evacuate",
            "emergency", "beacon", "countdown",
        ),
        "audiogen_prompt": DynamicSfxPrompt("emergency klaxon siren", "alarm_siren"),
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
        "audiogen_prompt": DynamicSfxPrompt("deep seismic tectonic rumble", "earthquake_rumble"),
        "duration": 3.0,
        "tags": ["earthquake", "rumble", "seismic", "tectonic", "foley"],
    },
    {
        "category": "fire_lava",
        "keywords": (
            "fire", "inferno", "blaze", "lava", "magma", "flame",
            "conflagration", "molten", "burn", "embers",
        ),
        "audiogen_prompt": DynamicSfxPrompt("roaring volcanic lava inferno crackle", "fire_lava"),
        "duration": 2.5,
        "tags": ["fire", "lava", "inferno", "crackle", "foley"],
    },
    {
        "category": "sonar_ping",
        "keywords": (
            "sonar", "ping", "submarine", "depth", "ocean", "trench", "abyssal",
        ),
        "audiogen_prompt": DynamicSfxPrompt("abyssal submarine sonar ping", "sonar_ping"),
        "duration": 2.0,
        "tags": ["sonar", "ping", "submarine", "depth", "foley"],
    },
    {
        "category": "cyber_glitch",
        "keywords": (
            "glitch", "spark", "circuit", "cyber", "terminal", "hack",
            "retinal", "electric", "short circuit",
        ),
        "audiogen_prompt": DynamicSfxPrompt("cybernetic electric glitch burst", "cyber_glitch"),
        "duration": 1.2,
        "tags": ["glitch", "electric", "cyber", "spark", "foley"],
    },
    {
        "category": "airlock_pneumatic",
        "keywords": (
            "airlock", "vent", "steam", "hiss", "pressure", "depressuriz",
            "decompression", "vacuum", "pneumatic",
        ),
        "audiogen_prompt": DynamicSfxPrompt("pressurized valve airlock hiss", "airlock_pneumatic"),
        "duration": 1.8,
        "tags": ["airlock", "valve", "steam", "hiss", "pressure", "foley"],
    },
    {
        "category": "metal_impact",
        "keywords": (
            "metal", "blade", "sword", "clash", "portcullis", "shield",
            "arrow", "rampart", "iron", "steel",
        ),
        "audiogen_prompt": DynamicSfxPrompt("iron metal clash impact", "metal_impact"),
        "duration": 1.5,
        "tags": ["metal", "clash", "impact", "iron", "foley"],
    },
    {
        "category": "door_impact",
        "keywords": (
            "slam", "door", "lock", "deadbolt", "impact", "crash",
            "collision", "barrier breach",
        ),
        "audiogen_prompt": DynamicSfxPrompt("sub-bass impact door slam", "door_impact"),
        "duration": 1.8,
        "tags": ["slam", "door", "impact", "sub_bass", "foley"],
    },
    {
        "category": "whoosh_transition",
        "keywords": (
            "whoosh", "sprint", "whip", "leap", "burst", "hatch",
            "swoosh", "swipe", "dash",
        ),
        "audiogen_prompt": DynamicSfxPrompt("cinematic camera whip whoosh transition", "whoosh_transition"),
        "duration": 1.5,
        "tags": ["whoosh", "transition", "whip", "motion", "foley"],
    },
    {
        "category": "tension_heartbeat",
        "keywords": (
            "heartbeat", "pulse", "decibel", "breath", "whisper",
            "creeping", "dread", "suspense",
        ),
        "audiogen_prompt": DynamicSfxPrompt("deep tension heartbeat pulse", "tension_heartbeat"),
        "duration": 2.2,
        "tags": ["heartbeat", "pulse", "tension", "dread", "foley"],
    },
    {
        "category": "atmospheric_wind",
        "keywords": (
            "rain", "wind", "storm", "fog", "corridor", "drone",
            "radiation", "ash", "pyroclastic", "dust", "haze", "ambient",
        ),
        "audiogen_prompt": DynamicSfxPrompt("atmospheric wind drone", "atmospheric_wind"),
        "duration": 2.5,
        "tags": ["wind", "storm", "drone", "atmosphere", "foley"],
    },
]


def extract_sfx_category(
    scene_or_text: dict[str, Any] | str,
    action: str = "",
    physical_context: str = "",
) -> SfxCategoryMatch | None:
    """Analyze a scene description or narration and extract the matching SFX category.
    
    Args:
        scene_or_text: A scene dictionary containing 'narration', 'visual_prompt',
                       'sfx_cue', or a raw text string.
        action: Optional specific action verb or description for dynamic prompt synthesis.
        physical_context: Optional physical material/environment context (e.g. "concrete bunker").

    Returns:
        SfxCategoryMatch if keywords match an SFX category, else None.
    """
    scene_action = action
    scene_phys = physical_context

    if isinstance(scene_or_text, dict):
        text_parts = [
            str(scene_or_text.get("sfx_cue", "")),
            str(scene_or_text.get("narration", "")),
            str(scene_or_text.get("visual_prompt", "")),
            str(scene_or_text.get("description", "")),
            str(scene_or_text.get("motion_prompt", "")),
        ]
        combined = " ".join(text_parts).lower()
        if not scene_action:
            scene_action = str(scene_or_text.get("action", "") or scene_or_text.get("sfx_action", "")).strip()
        if not scene_phys:
            scene_phys = str(scene_or_text.get("physical_context", "") or scene_or_text.get("sfx_context", "")).strip()
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
            prompt_obj = spec["audiogen_prompt"]
            if isinstance(prompt_obj, DynamicSfxPrompt):
                if scene_action or scene_phys:
                    prompt_str = prompt_obj.synthesize(
                        action=scene_action,
                        physical_context=scene_phys,
                        matched_keywords=matched,
                    )
                else:
                    prompt_str = prompt_obj.default_prompt
            elif callable(prompt_obj):
                prompt_str = prompt_obj(
                    action=scene_action,
                    physical_context=scene_phys,
                    matched_keywords=matched,
                )
            else:
                prompt_str = str(prompt_obj)

            return SfxCategoryMatch(
                category=spec["category"],
                audiogen_prompt=prompt_str,
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
