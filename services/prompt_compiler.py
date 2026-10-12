"""Reinforced prompt engineering compiler incorporating ai-playbooks documentary invariants.

Enforces:
1. Clothing Lock: Bans generic 'ancient clothing', mandates specific authentic fabrics/weave/cut.
2. Movement Lock: Bans passive states, mandates continuous purposeful labor verbs and body motion.
3. Ancient Equipment Rule: Bans modern mechanical triggers, enforces authentic human/timber mechanics.
4. Multi-Shot Prompting syntax: Formats multi-shot video prompts ('SHOT 1 [0-3s] ... SHOT 2 [3-6s] ...').

Zero network/transport calls are made in this module (strictly AST-clean).
"""

from __future__ import annotations

import re
from typing import Any

from services.character import CharacterProfile, get_active_character
from services.historical_research import HistoricalTruthSheet, get_historical_truth_sheet


MOVEMENT_LOCK_SUFFIX: str = (
    "Natural continuous body movement, shifting weight, moving fabric, coordinated purposeful labor, and atmospheric wind physics."
)

_GENERIC_CLOTHING_TERMS: tuple[str, ...] = (
    "ancient clothing", "historical costume", "ancient costume", "period clothing",
    "traditional garb", "ancient outfit", "old robes", "peasant clothes",
)

_PASSIVE_STATE_TERMS: tuple[str, ...] = (
    "standing still", "idle", "watching passively", "posing for camera", "motionless",
    "staring blankly", "standing motionless", "waiting quietly",
)

_MODERN_MECHANICAL_TRIGGERS: tuple[str, ...] = (
    "crane", "steel cable", "hydraulic", "bulldozer", "excavator", "scaffolding pipe",
    "electric motor", "modern winch", "synthetic rope", "metal pulley",
)

_AUTHENTIC_TIMBER_MECHANICS: str = (
    "hewn cedar timber levers, oiled sledges on mud-brick slipways, counterweighted balance beams, "
    "and coordinated teams of stonemasons using wooden wedges"
)


def apply_clothing_lock(prompt: str, era: str = "default") -> str:
    """Replace generic clothing descriptions with authentic weave, cut, and consistency anchors."""
    cleaned = prompt
    for term in _GENERIC_CLOTHING_TERMS:
        cleaned = re.sub(rf"\b{re.escape(term)}\b", "", cleaned, flags=re.IGNORECASE)

    era_lower = str(era or "default").casefold()
    if era_lower == "egyptian":
        fabric_anchor = "historically authentic fine pleated unbleached linen kalasiris tunic with hand-woven reed sash"
    elif era_lower == "neolithic":
        fabric_anchor = "tailored deerskin and hand-woven flax tunic bound with animal sinew and prehistoric bone pins"
    elif era_lower == "greco_roman":
        fabric_anchor = (
            "draped natural combed wool chiton or authentic Roman wool tunica and woven himation mantle fastened with bronze fibulae; "
            "strictly NO medieval armor, NO sunglasses, NO wristwatches"
        )
    elif era_lower == "ottoman":
        fabric_anchor = "tailored wool kaftan over silk-woven entari with period sash and leather traveling footwear"
    elif era_lower == "world_war_i":
        if re.search(r"\bnova\b", cleaned, re.IGNORECASE):
            fabric_anchor = "period-plausible ankle-length charcoal wool skirt, high-neck unbleached linen blouse, heavy olive wool field coat with hand-stitched seams and small brass buttons, leather ankle boots; no synthetic fabrics or modern tactical gear"
        else:
            fabric_anchor = (
                "1915-era Ottoman khaki wool service tunic with period-correct cut, authentic khaki cloth kabalak (Enveriye) folded sun-hat, "
                "hand-stitched seams, brass buttons, puttees, and worn leather boots; strictly NO red fez, NO fez hat, NO red felt hats, "
                "no synthetic fabric or modern tactical gear"
            )
    else:
        fabric_anchor = "authentic hand-woven linen tunic with natural vegetable-dye threading and leather fastenings"

    # Ensure fabric anchor is present
    if fabric_anchor not in cleaned and "kalasiris" not in cleaned and "chiton" not in cleaned and "deerskin" not in cleaned:
        cleaned = f"{cleaned.rstrip('. ')}, wearing {fabric_anchor}."
    return cleaned


ATMOSPHERIC_MOTION_SUFFIX: str = (
    "Cinematic volumetric atmosphere, drifting dust motes catching light beams, flickering torch flames, moving natural shadows, and organic wind physics."
)


def apply_movement_lock(motion_prompt: str) -> str:
    """Purge passive states and enforce physical or atmospheric movement."""
    cleaned = motion_prompt
    for term in _PASSIVE_STATE_TERMS:
        cleaned = re.sub(rf"\b{re.escape(term)}\b", "actively working and shifting weight", cleaned, flags=re.IGNORECASE)

    is_no_people = bool(re.search(r"\b(no people|empty|ancient chamber|relic|ruins|megalith|monolith)\b", cleaned, re.IGNORECASE))
    suffix = ATMOSPHERIC_MOTION_SUFFIX if is_no_people else MOVEMENT_LOCK_SUFFIX
    if MOVEMENT_LOCK_SUFFIX not in cleaned and ATMOSPHERIC_MOTION_SUFFIX not in cleaned:
        cleaned = f"{cleaned.rstrip('. ')}. {suffix}"
    return cleaned


def apply_ancient_equipment_rule(prompt: str) -> str:
    """Ban modern mechanical triggers and substitute explicit human and timber mechanics."""
    cleaned = prompt
    found_modern = False
    for term in _MODERN_MECHANICAL_TRIGGERS:
        if term == "crane":
            # Preserve cinematic camera crane moves (e.g. crane shot, crane up, camera crane)
            pattern = r"\bcrane\b(?!\s*(?:shot|camera|movement|move|angle|arm|rig|up|down))\b"
        else:
            pattern = rf"\b{re.escape(term)}\b"
        if re.search(pattern, cleaned, re.IGNORECASE):
            cleaned = re.sub(pattern, "timber lever system", cleaned, flags=re.IGNORECASE)
            found_modern = True

    if found_modern and _AUTHENTIC_TIMBER_MECHANICS not in cleaned:
        cleaned = f"{cleaned.rstrip('. ')}, utilizing {_AUTHENTIC_TIMBER_MECHANICS}."
    return cleaned


def format_multi_shot_prompt(
    shot1_action: str,
    shot2_action: str,
    shot1_window: tuple[float, float] = (0.0, 3.0),
    shot2_window: tuple[float, float] = (3.0, 6.0),
) -> str:
    """Format structured multi-shot motion syntax for video block generation."""
    s1_start, s1_end = int(round(shot1_window[0])), int(round(shot1_window[1]))
    s2_start, s2_end = int(round(shot2_window[0])), int(round(shot2_window[1]))
    
    clean_s1 = apply_ancient_equipment_rule(shot1_action.strip().rstrip(". "))
    clean_s2 = apply_ancient_equipment_rule(shot2_action.strip().rstrip(". "))
    
    return (
        f"SHOT 1 [{s1_start}-{s1_end}s]: {clean_s1}. | "
        f"SHOT 2 [{s2_start}-{s2_end}s]: {clean_s2}. {MOVEMENT_LOCK_SUFFIX}"
    )


def compile_longform_broll_prompt(
    scene_description: str,
    proof_target: str,
    truth_sheet: HistoricalTruthSheet | None = None,
    aspect_ratio: str = "16:9",
    action_description: str = "",
) -> str:
    """Compile photorealistic National Geographic / BBC Earth B-roll plate prompt enforcing all locks."""
    base = (
        f"Photorealistic 8k National Geographic and BBC Earth 35mm documentary frame of {scene_description}. "
        f"Visible physical evidence: {proof_target}. "
        f"Atmospheric volumetric lighting, {aspect_ratio} widescreen, authentic weathered stone and natural materials, "
        "deep shadow contrast. When the authored action names people, they must be clearly visible performing that action, never replaced by an empty landscape or object-only composition. "
        "Natural continuous body movement, shifting weight, moving fabric, coordinated purposeful labor, and atmospheric wind physics. No modern archaeologists, no anachronistic equipment, no text, no watermarks."
    )
    if action_description.strip():
        base += f" Clearly depict the authored historical action: {action_description.strip()}"
        if re.search(r"\b(sailors?|seamen|crewmen|crew|gunners?|soldiers?|troops?|rowers?|workers?|men|women|artillerymen)\b", action_description, re.I):
            base += (
                " The named people are mandatory visible subjects in the foreground or middle distance, "
                "with enough scale to read their coordinated hand and body actions while the historical setting remains identifiable. "
                "Clothing, headwear, tools, and equipment must match the exact 1915 force and role described; no generic ancient costume, modern uniform, or modern safety gear."
            )
        elif re.search(r"\bhands?\b", action_description, re.I):
            base += " Show the specifically authored hand action clearly, attached to a period-correct sleeve; do not invent a face or additional person."

    # Authentic Headwear & Clothing Lock
    has_people = bool(re.search(r"\b(sailors?|seamen|crewmen|crew|gunners?|soldiers?|troops?|rowers?|workers?|men|women|artillerymen)\b", f"{scene_description} {action_description}", re.I))
    if has_people:
        if (truth_sheet and truth_sheet.era == "world_war_i") or re.search(r"\b(1915|gallipoli|canakkale|çanakkale|dardanelles|ottoman)\b", f"{scene_description} {action_description}", re.I):
            base += " Headwear must be authentic khaki cloth kabalak (Enveriye) folded sun-hats; strictly NO red fez, NO fez hat, NO red felt hats."
        elif (truth_sheet and truth_sheet.era == "greco_roman") or re.search(r"\b(rome|roman|pompeii|pompei|greece|greek)\b", f"{scene_description} {action_description}", re.I):
            base += " Wardrobe must be authentic Roman wool tunics; strictly NO medieval armor, NO modern glasses or watches."

    # Prop consistency lock
    text_corpus = f"{scene_description} {proof_target} {action_description}".casefold()
    if re.search(r"\b(cannon|gun|artillery|battery|breech|shell|krupp)\b", text_corpus) and (
        re.search(r"\b(1915|gallipoli|canakkale|çanakkale|dardanelles|ottoman)\b", text_corpus) or (truth_sheet and truth_sheet.era == "world_war_i")
    ):
        base += " Prop Invariant: Heavy 28cm Krupp coastal fortress gun on fixed steel traversing turntable mount in sunken stone embrasure, massive rifled steel barrel, NOT a field gun, NOT wooden wheels."
    elif re.search(r"\b(bakery|oven|pistrinum|mill)\b", text_corpus) and (
        re.search(r"\b(pompeii|pompei|roman|rome)\b", text_corpus) or (truth_sheet and truth_sheet.era == "greco_roman")
    ):
        base += " Prop Invariant: Authentic Roman brick domed baking oven and hourglass-shaped volcanic basalt lava stone grain mills (pistrinum), authentic 79 AD Roman architecture."
    elif re.search(r"\b(vesuvius|vezuv|volcano)\b", text_corpus):
        base += " Prop Invariant: Mount Vesuvius looming on the horizon with dark ash and steam fumaroles rising into the sky."

    # Universal Zero-Text & Zero-Watermark Shield
    base += (
        " STRICT VISUAL MANDATE: ZERO text, ZERO printed letters, ZERO typography, ZERO date stamps, "
        "ZERO year numbers written on image, ZERO name plaques, ZERO title banners, ZERO graphic cards, "
        "ZERO caption boxes, ZERO lower thirds, ZERO subtitles, ZERO watermarks. "
        "Pure photographic 35mm cinema only without written words."
    )

    base = apply_ancient_equipment_rule(base)
    if truth_sheet:
        for forbidden in truth_sheet.prohibited_anachronisms[:6]:
            if forbidden.lower() not in base.lower():
                base = f"{base.rstrip('. ')}, NO {forbidden}."
    return apply_movement_lock(base)


def format_veo_cinematography_prompt(
    shot_type: str,
    subject_labor: str,
    lighting: str = "golden hour sunlight, volumetric dust motes dancing in air",
    historical_atmosphere: str = "authentic prehistoric archaeological atmosphere",
    camera_vector: str = "slow cinematic dolly in",
    fps: str = "24fps",
) -> str:
    """Format prompt adhering strictly to Dowwie & Google Veo Cinematography ordering:
    
    [Shot Type] + [Subject & purposeful labor] + [Lighting: golden hour, volumetric dust] + [Historical Atmosphere] + [Camera vector: slow dolly in, 24fps]
    """
    st = (shot_type or "Cinematic medium tracking shot").strip().rstrip(",. ")
    subj = apply_ancient_equipment_rule(subject_labor.strip().rstrip(",. "))
    subj = apply_movement_lock(subj).rstrip(". ")
    light = (lighting or "golden hour sunlight, volumetric dust motes dancing in air").strip().rstrip(",. ")
    atm = (historical_atmosphere or "authentic historical documentary atmosphere").strip().rstrip(",. ")
    vec = (camera_vector or "slow cinematic dolly in").strip().rstrip(",. ")
    
    prompt = f"{st}, {subj}, {light}, {atm}, {vec}, {fps} motion blur, 35mm photorealistic documentary cinema."
    return apply_ancient_equipment_rule(prompt)

