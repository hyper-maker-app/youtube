"""Run-scoped reference-sheet planning with no provider transport code."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any

from services.mode_profile import ANATOMICAL, ModeProfile
from services.script_engine import resolve_subject_description
import config


def _is_longform_roster(mode: ModeProfile = ANATOMICAL) -> bool:
    return mode.name == "explorer" or ((getattr(config, "LONGFORM_MODE", False) or getattr(config, "IS_EXPLORER_FORMAT", False)) and mode.name not in {"anatomical", "incident", "mechanical"})


def _env_ratio(mode: ModeProfile = ANATOMICAL) -> str:
    return "16:9" if _is_longform_roster(mode) else "9:16"


def _char_ratio(mode: ModeProfile = ANATOMICAL) -> str:
    return "3:2" if _is_longform_roster(mode) else "2:3"


ROSTER_VERSION = 2

# ADR-028: Hard Anti-Text & Anti-Symbol Shield for Reference Sheets
# Reference sheets are the root source of keyframe contamination. If a reference
# sheet contains hallucinated letters or symbols, every downstream keyframe inherits it.
_ROSTER_ANTI_TEXT_SUFFIX = (
    " ABSOLUTE PROHIBITION: This reference sheet must contain ZERO text, ZERO letters, "
    "ZERO numbers, ZERO chemical symbols, ZERO labels, ZERO annotations, ZERO watermarks "
    "anywhere in the image. No split-screen, no multi-panel, no diagram layout. "
    "Pure visual geometry and materials only."
)


@dataclass(frozen=True)
class RosterEntry:
    id: str
    kind: str
    aspect_ratio: str
    prompt: str

    @property
    def prompt_sha256(self) -> str:
        return hashlib.sha256(self.prompt.encode("utf-8")).hexdigest()


def _kind_for(subject_id: str, description: str) -> str:
    # 1. Structural / vehicle / mechanical keywords in subject_id always imply prop
    if re.search(r"\b(?:aircraft|airframe|airplane|plane|jet|airliner|fuselage|cockpit|cabin|wing|engine|hull|vehicle|car|boat|ship|tarmac|runway|door|latch|window|seat|strap|panel|gear|valve|pump|piston|cable)\b", subject_id, re.I):
        return "prop"
    # 2. Explicit human role in subject_id always implies character
    if re.search(r"\b(?:pilot|captain|copilot|attendant|officer|passenger|crew|paramedic|mechanic|doctor|surgeon|patient|person|man|woman|boy|girl|bystander|traveler|worker|technician|character|eater|human)\b", subject_id, re.I):
        return "character"
    # 3. Disambiguate by description: vehicles/props first
    text = f"{subject_id} {description}".casefold()
    if re.search(r"\b(?:aircraft|airframe|airplane|plane|jet|airliner|fuselage|hull|vehicle|car|boat|ship)\b", text):
        return "prop"
    # 4. Human terms (require human noun, not bare 'body' or 'face')
    return "character" if re.search(r"\b(?:human(?:\s+body)?|person|man|woman|boy|girl|character|passenger|pilot|captain|copilot|attendant|officer|driver|operator|mechanic|doctor|patient|bystander|traveler)\b", text) else "prop"


def build_roster(shots: list[Any], mode: ModeProfile = ANATOMICAL) -> list[RosterEntry]:
    """Build deterministic, run-local sheets; no global catalog mutation occurs."""
    if mode.environment_style != "void":
        return _build_contextual_roster(shots, mode)
    entries: list[RosterEntry] = [RosterEntry(
        "environment_void", "environment", _env_ratio(mode),
        "ENVIRONMENT SHEET — EMPTY LOCATION PLATE. Deep dark neutral 3D studio void only. "
        "ABSOLUTELY NO people, NO animals, NO characters, NO subject, NO object, NO text. "
        f"45-degree warm golden key light falloff and cyan rim-light atmosphere, {'horizontal 16:9' if _is_longform_roster(mode) else 'vertical 9:16'}."
        + _ROSTER_ANTI_TEXT_SUFFIX,
    )]
    seen: set[str] = set()
    # Contextual identity is first-class: it can differ from a later stomach,
    # engine, cell, or material mechanism subject but must remain stable on return.
    contextual = next((shot for shot in shots if getattr(shot, "presentation_mode", "") == "contextual_opening_anchor"), None)
    if contextual is not None:
        subject_id = str(getattr(contextual, "contextual_anchor_subject_id", "") or getattr(contextual, "subject_id", "contextual_subject"))
        description = str(getattr(contextual, "subject_description", "") or subject_id)
        kind = _kind_for(subject_id, description)
        ratio = _char_ratio(mode) if kind == "character" else "1:1"
        contract = str(getattr(contextual, "contextual_anchor_appearance_contract", "") or "stable roster identity")
        entries.append(RosterEntry(subject_id, kind, ratio,
            "A clean, high-end 3D animated cinematic frame, minimalist dark studio void lighting, "
            f"expressive smooth character design, dramatic side-shadows, {'16:9 horizontal aspect ratio' if _is_longform_roster(mode) else '9:16 vertical aspect ratio'}, "
            "vivid colors, hyper-detailed textures, Blender Cycles render aesthetic. "
            f"CONTEXTUAL ANCHOR SHEET — {contract}. Subject: {description}. "
            "Same run-local identity, shape, material and attachments on every contextual appearance. "
            "Consistent 30-year-old character, short brown hair, simple crewneck t-shirt, consistent facial features, "
            "neutral expression, centered composition, mouth strictly sealed and closed. "
            "Glossy Stylized 3D Mannequin / Medical Animation Render; premium PBR, dark neutral studio void, warm golden key and cyan rim light. "
            "Closed or neutral mouth. No text, captions, logos, watermark, UI, dialogue, lip-sync, or live-action presentation."
            + _ROSTER_ANTI_TEXT_SUFFIX))
        seen.add(subject_id)
    for shot in shots:
        subject_id = str(getattr(shot, "subject_id", "subject"))
        if subject_id in seen:
            continue
        seen.add(subject_id)
        description = str(getattr(shot, "subject_description", "") or subject_id)
        kind = _kind_for(subject_id, description)
        ratio = _char_ratio(mode) if kind == "character" else "1:1"
        subject_contract = (
            "Character reference sheet (CPIG), 30-year-old average person with short brown hair wearing a simple crewneck t-shirt, neutral expression, neutral closed mouth, single identity, stylized 3D character modeling with natural anatomical proportions, premium PBR materials"
            if kind == "character" else
            "Object or anatomical reference sheet, isolated single subject, readable materials and cutaway structure"
        )
        style_trait = (
            "expressive smooth character design, natural anatomical proportions, "
            if kind == "character" else
            "3D medical and technical cutaway model, "
        )
        render_trait = (
            "Glossy Stylized 3D Mannequin / Character Animation Render; "
            if kind == "character" else
            "Glossy Stylized 3D Medical and Scientific Cutaway Model Render; "
        )
        entries.append(RosterEntry(
            subject_id, kind, ratio,
            "A clean, high-end 3D animated cinematic frame, minimalist dark studio void lighting, "
            f"{style_trait}dramatic side-shadows, {'16:9 horizontal aspect ratio' if _is_longform_roster(mode) else '9:16 vertical aspect ratio'}, "
            "vivid colors, hyper-detailed textures, Blender Cycles and Octane Render aesthetic. "
            f"{subject_contract}. Subject: {description}. "
            f"{render_trait}"
            "premium PBR, strong subsurface scattering where applicable, dark neutral studio void, warm golden key and cyan rim light. "
            "No text, captions, logos, watermark, UI, or live-action presentation."
            + _ROSTER_ANTI_TEXT_SUFFIX,
        ))
    return entries


_INCIDENT_ROLE_COSTUMES: dict[str, str] = {
    "captain_pilot": (
        "Airline Captain: 4 gold stripes on shoulder epaulets, crisp white pilot shirt, navy blue pilot trousers, "
        "graying hair, middle-aged stylized 3D male figure."
    ),
    "copilot": (
        "First Officer / Copilot: 3 gold stripes on shoulder epaulets, white pilot shirt, navy blue pilot trousers, "
        "seated firmly in the starboard (right-hand) cockpit seat, hands gripping flight control yoke."
    ),
    "copilot_officer": (
        "First Officer / Copilot: 3 gold stripes on shoulder epaulets, white pilot shirt, navy blue pilot trousers, "
        "seated firmly in the starboard (right-hand) cockpit seat, hands gripping flight control yoke."
    ),
    "flight_attendant_01": (
        "Flight Attendant: dark navy vest with burgundy/gold tie cabin crew uniform, white collared shirt, "
        "navy blue trousers."
    ),
    "unruly_passenger": (
        "Unruly Passenger: casual maroon hoodie or civilian clothing, disheveled posture, "
        "distinct from all uniformed flight and security crew."
    ),
    "responding_officer": (
        "Responding Officer: tactical police or security uniform with yellow high-visibility insignia, "
        "duty belt, distinctly authoritative posture."
    ),
}


def _character_prompt(description: str, subject_id: str = "") -> str:
    """Build a role-based character reference sheet prompt with Soul ID consistency and costume decoupling."""
    costume_clause = ""
    sid = subject_id.casefold()
    for role_key, role_spec in _INCIDENT_ROLE_COSTUMES.items():
        if role_key in sid or sid in role_key:
            costume_clause = f" Strict Role & Costume Invariant: {role_spec}."
            break
            
    verbs = (
        r"grab(?:s|bed|bing)?|"
        r"grip(?:s|ped|ping)?|"
        r"clasp(?:s|ed|ing)?|"
        r"clamp(?:s|ed|ing)?|"
        r"seize(?:s|d|ing)?|"
        r"lock(?:s|ed|ing)?\s+onto|"
        r"embrace(?:s|d|ing)?|"
        r"assist(?:s|ed|ing)?|"
        r"pin(?:s|ned|ning)?|"
        r"strain(?:s|ed|ing)?|"
        r"div(?:e|es|ed|ing)|"
        r"wrestl(?:e|es|ed|ing)|"
        r"clutch(?:es|ed|ing)?|"
        r"hold(?:s|ing)?|held|"
        r"pull(?:s|ed|ing)?|"
        r"push(?:es|ed|ing)?|"
        r"drag(?:s|ged|ging)?|"
        r"lift(?:s|ed|ing)?"
    )
    safe_desc = re.sub(rf"\b(?:{verbs})\b", "standing neutrally", description, flags=re.I)
    safe_desc = re.sub(r"\b(?:assisted\s+by|second\s+(?:attendant|pilot|officer|person|man|woman|character))\b", "isolated single subject", safe_desc, flags=re.I)
            
    return (
        "A clean, high-end 3D animated cinematic frame, "
        "expressive smooth character design, dramatic side-shadows, "
        "9:16 vertical aspect ratio, vivid colors, hyper-detailed textures, "
        "Blender Cycles and Octane Render aesthetic. "
        f"Character reference sheet (CPIG / Soul ID consistency), {safe_desc},{costume_clause} "
        "stylized 3D character, natural anatomical proportions, consistent facial features, "
        "neutral expression, neutral closed mouth, ray-traced soft skin subsurface scattering (SSS), premium PBR materials. "
        f"Subject: {safe_desc}. Zack D. Films aesthetic, studio clinical lighting, neutral closed mouth, no speech, no lip-sync, "
        "NO CARTOON EXAGGERATION, NO PIXAR CARICATURE, NO 2D STICKER ARROWS, NO LIVE ACTION. "
        "No text, captions, logos, watermark, UI, or live-action presentation."
        + _ROSTER_ANTI_TEXT_SUFFIX
    )


def _mechanical_prop_prompt(description: str) -> str:
    """Build an engineering/mechanical prop reference sheet prompt with PBR metallic sheen."""
    return (
        "A clean, high-end 3D animated cinematic frame, dramatic 3D cinematic environment lighting, "
        "3D engineering and technical cutaway model, dramatic side-shadows, 1:1 aspect ratio, "
        "vivid colors, hyper-detailed textures, Blender Cycles and Octane Render aesthetic. "
        f"Object or mechanical reference sheet, isolated single subject, readable materials and cutaway structure. Subject: {description}. "
        "Glossy Stylized 3D Engineering and Scientific Cutaway Model Render; "
        "premium PBR, brushed anisotropic metallic sheen, photoelastic stress concentration fringes, high-contrast studio rim light. "
        "No people, no characters, no text, captions, logos, watermark, UI, or live-action presentation."
        + _ROSTER_ANTI_TEXT_SUFFIX
    )


def _build_contextual_roster(shots: list[Any], mode: ModeProfile) -> list[RosterEntry]:
    """Incident/news or mechanical mode: real environment plates + role-based character and prop roster."""
    entries: list[RosterEntry] = []

    # 1. Environment plates from location_id (not void)
    locations_seen: set[str] = set()
    for shot in shots:
        loc = str(getattr(shot, "location_id", "") or "")
        if loc and loc not in locations_seen:
            locations_seen.add(loc)
            loc_label = loc.upper().replace("_", " ")
            env_render_desc = (
                f"Photorealistic 8k cinematic documentary environment plate of {loc.replace('_', ' ')}, "
                "National Geographic and BBC Earth cinematography, authentic historical atmospheric volumetric lighting, "
                if _is_longform_roster(mode)
                else f"Glossy stylized 3D render of {loc.replace('_', ' ')}, "
            )
            entries.append(RosterEntry(
                f"environment_{loc}", "environment", _env_ratio(mode),
                f"ENVIRONMENT SHEET — {loc_label} LOCATION PLATE. "
                f"{env_render_desc}"
                f"{'horizontal 16:9 landscape orientation' if _is_longform_roster(mode) else 'strictly upright vertical 9:16 portrait orientation with level horizon: floor/ground at the bottom, ceiling/sky at the top, perfectly upright perspective with zero camera tilt or sideways rotation.'} "
                "dramatic cinematic lighting, warm golden key light, cyan rim-light atmosphere, "
                f"{'horizontal 16:9' if _is_longform_roster(mode) else 'vertical 9:16'}. ABSOLUTELY NO people, NO animals, NO characters, NO text."
                + _ROSTER_ANTI_TEXT_SUFFIX,
            ))

    # 2. All subjects (primary + secondary) — two passes for robust description backfill
    # Pass 1: scan ALL shots and build a dict {subject_id: best_subject_description},
    # preferring the shot where that id is the PRIMARY subject_id over any shot
    # where it only appears in secondary_subject_ids.
    best_descriptions: dict[str, str] = {}
    subject_shot_meta: dict[str, Any] = {}
    primary_subjects: set[str] = set()

    for i, shot in enumerate(shots):
        prim_id = str(getattr(shot, "subject_id", "subject"))
        primary_subjects.add(prim_id)
        if prim_id not in best_descriptions:
            best_descriptions[prim_id] = resolve_subject_description(prim_id, shots, i)
            subject_shot_meta[prim_id] = shot

        for sec_id in list(getattr(shot, "secondary_subject_ids", None) or []):
            sec_id = str(sec_id)
            if sec_id not in best_descriptions:
                best_descriptions[sec_id] = resolve_subject_description(sec_id, shots, i)
                subject_shot_meta[sec_id] = shot

    # Pass 2: build roster entries from that resolved dict, not from first-seen order
    for subject_id, description in best_descriptions.items():
        shot = subject_shot_meta.get(subject_id)
        bare_id = subject_id.replace("_", " ")
        is_bare = subject_id not in primary_subjects

        if mode.name == "incident":
            # 1. Structural / vehicle / mechanical keywords in subject_id always imply prop
            if re.search(r"\b(?:door|latch|handle|window|lever|panel|gear|piston|cable|lock|valve|switch|aircraft|airframe|airplane|plane|jet|airliner|fuselage|cockpit|cabin|wing|engine|hull|vehicle|tarmac|runway|seat_belt|seat|strap)\b", subject_id, re.I):
                kind = "prop"
            # 2. Human roles in subject_id always imply character
            elif re.search(r"\b(?:pilot|captain|copilot|attendant|officer|passenger|crew|paramedic|mechanic|doctor|surgeon|patient|person|man|woman|boy|girl|bystander|traveler|worker|character)\b", subject_id, re.I):
                kind = "character"
            else:
                is_prop = bool(re.search(r"\b(?:door|latch|handle|window|lever|panel|gear|piston|cable|lock|valve|switch|aircraft|airframe|airplane|plane|jet|airliner|fuselage|cockpit|cabin|wing|engine|hull|vehicle|tarmac|runway)\b", f"{subject_id} {description}", re.I))
                is_human = bool(re.search(r"\b(?:person|man|woman|boy|girl|pilot|captain|copilot|attendant|officer|passenger|crew|mechanic|paramedic|traveler)\b", f"{subject_id} {description}", re.I))
                kind = "character" if (is_human and not is_prop) else "prop"
        else:
            # In mechanical and other modes, sniffer determines character vs prop
            kind = _kind_for(subject_id, description)

        if is_bare:
            kind = "prop"

        if mode.name == "explorer":
            from services.character import CharacterSheetSpec, detect_era, get_active_character
            char = get_active_character()
            sid_low = subject_id.casefold()
            era = detect_era(f"{subject_id} {description} {getattr(shot, 'location_id', '')}")
            if "nova" in sid_low or "host" in sid_low:
                spec = CharacterSheetSpec(char, aspect_ratio=_char_ratio(mode))
                entries.append(RosterEntry(
                    subject_id, "character", _char_ratio(mode),
                    spec.frontal_portrait_prompt(era=era),
                ))
            elif not sid_low.startswith("broll") and ("witness" in sid_low or kind == "character"):
                entries.append(RosterEntry(
                    subject_id, "character", _char_ratio(mode),
                    f"CHARACTER REFERENCE SHEET [HISTORICAL EYEWITNESS PORTRAIT]: {description}. "
                    "Front-facing eye-level documentary portrait with complete head and shoulders inside frame, "
                    "authentic historical period wardrobe, weathered natural skin texture, soft fill lighting, "
                    f"8k photorealistic cinema, {_char_ratio(mode)} composition. "
                    "NO modern safari hats, NO modern clothing, ZERO text, ZERO watermarks."
                    + _ROSTER_ANTI_TEXT_SUFFIX,
                ))
            elif not sid_low.startswith("broll"):
                ratio = "16:9" if _is_longform_roster(mode) else "9:16"
                entries.append(RosterEntry(
                    subject_id, "prop", ratio if _is_longform_roster(mode) else "1:1",
                    f"OBJECT / SITE REFERENCE SHEET: {description}. Photorealistic 8k documentary visual reference, "
                    f"authentic historical materials, cinematic lighting, {ratio} composition. "
                    "ABSOLUTELY NO people, NO human figures, NO characters, pure architectural and archaeological reference only. "
                    "ZERO text, ZERO watermarks."
                    + _ROSTER_ANTI_TEXT_SUFFIX
                ))
            continue

        if kind == "character":
            entries.append(RosterEntry(
                subject_id, "character", _char_ratio(mode),
                _character_prompt(description, subject_id=subject_id),
            ))
        else:
            is_mech = mode.name == "mechanical" or (shot is not None and getattr(shot, "normalized_domain", "") in {"mechanical", "physics", "engineering"})
            is_vehicle = bool(re.search(r"\b(?:aircraft|airframe|airplane|plane|jet|airliner|fuselage|cockpit|vehicle|car|train|boat|ship)\b", f"{subject_id} {description}", re.I))
            vehicle_clause = " mechanical only, no face, no eyes, not a character. Strictly realistic mechanical engineering geometry and industrial design. ZERO cartoon anthropomorphism: NO face, NO cartoon eyes, NO mouth on windshield or fuselage, NOT a living character. Pure mechanical aerodynamic engineering materials." if is_vehicle else ""
            
            if is_bare:
                prop_prompt = (
                    f"ENVIRONMENT SHEET — {bare_id.upper()} LOCATION PLATE. "
                    f"Glossy stylized 3D render of {bare_id}, "
                    "strictly upright vertical 9:16 portrait orientation with level horizon: floor/ground at the bottom, "
                    "ceiling/sky at the top, perfectly upright perspective with zero camera tilt or sideways rotation. "
                    "dramatic cinematic lighting, warm golden key light, cyan rim-light atmosphere, "
                    f"vertical 9:16.{vehicle_clause} "
                    "ABSOLUTELY NO people, NO animals, NO characters, NO text."
                    + _ROSTER_ANTI_TEXT_SUFFIX
                )
            else:
                prop_prompt = _mechanical_prop_prompt(description) if is_mech else (
                    "A clean, high-end 3D animated cinematic frame, dramatic 3D cinematic environment lighting, "
                    "3D medical and scientific cutaway model, dramatic side-shadows, 1:1 aspect ratio, "
                    "vivid colors, hyper-detailed textures, Blender Cycles and Octane Render aesthetic. "
                    f"Object reference sheet, isolated single subject, readable materials and cutaway structure. Subject: {description}. "
                    "Glossy Stylized 3D Medical and Scientific Cutaway Model Render; "
                    "premium PBR, strong subsurface scattering where applicable, high-contrast studio rim light. "
                    f"{vehicle_clause}"
                    "No people, no characters, no text, captions, logos, watermark, UI, or live-action presentation."
                    + _ROSTER_ANTI_TEXT_SUFFIX
                )
            entries.append(RosterEntry(
                subject_id, "prop", "1:1",
                prop_prompt,
            ))

    return entries


def manifest(entries: list[RosterEntry], files: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "schema_version": ROSTER_VERSION,
        "entries": [asdict(entry) | {"prompt_sha256": entry.prompt_sha256, "local": (files or {}).get(entry.id)} for entry in entries],
    }
