"""Four Visual Locks & Motion Contracts (ai-playbooks + HiAPIAI + Script-Weaver).

Enforces:
1. Clothing Lock V2: Era-specific weave, fabric, and cut; bans generic 'ancient clothing'.
2. Movement Lock V2: Bans passive states, mandates active physical labor verbs and kinetics.
3. Equipment Lock V2: Bans modern machinery in ancient eras; strictly era-gated (exempts WWI/modern).
4. Framing & Headroom Lock: Generous top headroom, closed neutral mouths, zero-text shields.

Strictly AST-clean: Zero network calls, zero provider imports.
"""

from __future__ import annotations

import re
from typing import Any

MOVEMENT_LOCK_SUFFIX: str = (
    "Natural continuous body movement, shifting weight, moving fabric, coordinated purposeful labor, and atmospheric wind physics."
)

ATMOSPHERIC_MOTION_SUFFIX: str = (
    "Slow cinematic camera glide with natural volumetric dust motes, shifting directional light, and subtle ambient atmospheric motion."
)

HEADROOM_AND_MOUTH_SHIELD: str = (
    "Generous headroom above head with forehead and hair fully visible inside the frame; closed or neutral mouth with relaxed facial composure; "
    "strictly no on-screen text, no titles, no subtitles, no watermarks, no HUD."
)

_GENERIC_CLOTHING_TERMS: tuple[str, ...] = (
    "ancient clothing", "historical costume", "ancient costume", "period clothing",
    "traditional garb", "ancient outfit", "old robes", "peasant clothes", "peasant garb",
)

_PASSIVE_STATE_TERMS: tuple[str, ...] = (
    "standing still", "idle", "watching passively", "posing for camera", "motionless",
    "staring blankly", "standing motionless", "waiting quietly", "standing quietly",
)

_MODERN_MECHANICAL_TRIGGERS: tuple[str, ...] = (
    "steel cable", "hydraulic", "bulldozer", "excavator", "scaffolding pipe",
    "electric motor", "modern winch", "synthetic rope", "metal pulley",
)

_AUTHENTIC_TIMBER_MECHANICS: str = (
    "hewn cedar timber levers, oiled sledges on mud-brick slipways, counterweighted balance beams, "
    "and coordinated teams of stonemasons using wooden wedges"
)

# Eras that must NOT receive ancient timber/sledge injection
_MODERN_OR_INDUSTRIAL_ERAS: frozenset[str] = frozenset({
    "world_war_i", "victorian", "modern", "modern_expedition", "twentieth_century",
})


def apply_clothing_lock_v2(prompt: str, era: str = "default", truth_sheet: Any = None) -> str:
    """Replace generic clothing descriptions with authentic weave, cut, and consistency anchors."""
    cleaned = prompt
    for term in _GENERIC_CLOTHING_TERMS:
        cleaned = re.sub(rf"\b{re.escape(term)}\b", "", cleaned, flags=re.IGNORECASE)

    era_lower = str(era or "default").casefold()

    if era_lower == "egyptian":
        fabric_anchor = (
            "historically authentic fine pleated unbleached linen kalasiris tunic with hand-woven reed sash; "
            "strictly NO synthetic fabrics, NO modern tactical gear, NO sunglasses, NO wristwatches"
        )
    elif era_lower == "neolithic":
        fabric_anchor = (
            "tailored deerskin and hand-woven flax tunic bound with animal sinew and prehistoric bone pins; "
            "strictly NO metal fasteners, NO synthetic fabrics, NO sunglasses, NO wristwatches"
        )
    elif era_lower == "greco_roman":
        fabric_anchor = (
            "draped natural combed wool chiton or authentic Roman wool tunica and woven himation mantle fastened with bronze fibulae; "
            "strictly NO medieval armor, NO sunglasses, NO wristwatches, NO red fez"
        )
    elif era_lower == "ottoman":
        fabric_anchor = (
            "tailored wool kaftan over silk-woven entari with period sash and leather traveling footwear; "
            "strictly NO synthetic fabrics, NO digital wristwatches"
        )
    elif era_lower == "world_war_i":
        if re.search(r"\bnova\b", cleaned, re.IGNORECASE):
            fabric_anchor = (
                "period-plausible ankle-length charcoal wool skirt, high-neck unbleached linen blouse, heavy olive wool field coat "
                "with hand-stitched seams and small brass buttons, leather ankle boots; no synthetic fabrics or modern tactical gear"
            )
        else:
            fabric_anchor = (
                "1915-era Ottoman khaki wool service tunic with period-correct cut, authentic khaki cloth kabalak (Enveriye) folded sun-hat, "
                "hand-stitched seams, brass buttons, puttees, and worn leather boots; strictly NO red fez, NO fez hat, NO red felt hats, "
                "no synthetic fabric or modern tactical gear"
            )
    else:
        fabric_anchor = "authentic hand-woven linen tunic with natural vegetable-dye threading and leather fastenings"

    # Ensure fabric anchor is present
    if fabric_anchor not in cleaned and "kalasiris" not in cleaned and "chiton" not in cleaned and "deerskin" not in cleaned and "kabalak" not in cleaned:
        cleaned = f"{cleaned.rstrip('. ')}, wearing {fabric_anchor}."
    return cleaned


def apply_movement_lock_v2(motion_prompt: str, has_people: bool = True) -> str:
    """Ban passive poses ('standing still', 'idle'). Mandate active physical labor verbs and kinetics."""
    cleaned = motion_prompt
    for term in _PASSIVE_STATE_TERMS:
        cleaned = re.sub(rf"\b{re.escape(term)}\b", "actively working and shifting weight", cleaned, flags=re.IGNORECASE)

    if has_people:
        if "natural continuous body movement" not in cleaned.casefold():
            cleaned = f"{cleaned.rstrip('. ')}. {MOVEMENT_LOCK_SUFFIX}"
    else:
        if "dust motes" not in cleaned.casefold() and "atmospheric" not in cleaned.casefold():
            cleaned = f"{cleaned.rstrip('. ')}. {ATMOSPHERIC_MOTION_SUFFIX}"
    return cleaned


def apply_equipment_lock_v2(prompt: str, era: str = "default", truth_sheet: Any = None) -> str:
    """Ban modern mechanical triggers in ancient contexts. Strictly era-gated (exempts WWI/industrial)."""
    era_lower = str(era or "default").casefold()
    # AUDIT REVISION: Strictly exempt modern and WWI industrial eras from ancient cedar timber injection!
    if era_lower in _MODERN_OR_INDUSTRIAL_ERAS:
        return prompt

    cleaned = prompt
    # Check for modern machinery triggers
    for term in _MODERN_MECHANICAL_TRIGGERS:
        cleaned = re.sub(rf"\b{re.escape(term)}\b", "wooden mechanical lever", cleaned, flags=re.IGNORECASE)

    # Isolated crane check: preserve cinematography crane terms
    cleaned = re.sub(
        r"(?<!camera\s)(?<!cinematic\s)\bcrane\b(?!\sshot)",
        "counterweighted timber beam",
        cleaned,
        flags=re.IGNORECASE,
    )

    if "wooden" not in cleaned and "timber" not in cleaned and "sledge" not in cleaned and "lever" not in cleaned:
        cleaned = f"{cleaned.rstrip('. ')}, employing {_AUTHENTIC_TIMBER_MECHANICS}."
    return cleaned


def apply_framing_lock_v2(prompt: str, is_character_shot: bool = False) -> str:
    """Enforce generous top headroom, closed/neutral mouth, and zero-text shields."""
    cleaned = prompt
    if is_character_shot:
        if "headroom" not in cleaned.casefold():
            cleaned = f"{cleaned.rstrip('. ')}. {HEADROOM_AND_MOUTH_SHIELD}"
    else:
        if "strictly no on-screen text" not in cleaned.casefold() and "no text" not in cleaned.casefold():
            cleaned = f"{cleaned.rstrip('. ')}. Strictly no on-screen text, no titles, no subtitles, no watermarks, no HUD."
    return cleaned
