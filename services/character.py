"""Virtual Explorer character identity and character-sheet management.

Defines the persistent persona (default: female explorer 'Nova') and enforces
strict visual face/wardrobe locks across generations, with balanced A-Roll
(on-camera lip-sync) vs B-Roll (cinematic voiceover) screen time pacing.
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


DEFAULT_TIME_DEVICE: str = (
    "signature time-traveler artifact: an intricate celestial brass-and-bronze temporal chronometer wrist device "
    "with subtle glowing gyroscopic rings and engraved astronomical glyphs worn on her left wrist, "
    "accompanied by an antique miniature hourglass pendant on a slender bronze chain"
)

ERA_WARDROBE_CATALOG: dict[str, str] = {
    "default": (
        "weathered olive-green canvas safari utility jacket with rolled cuffs over a dark charcoal "
        "moisture-wicking henley shirt, rugged tactical pocket detailing, practical field expedition trousers"
    ),
    "modern_expedition": (
        "weathered olive-green canvas safari utility jacket with rolled cuffs over a dark charcoal "
        "moisture-wicking henley shirt, rugged tactical pocket detailing, practical field expedition trousers"
    ),
    "egyptian": (
        "historically authentic fine pleated unbleached linen kalasiris tunic with subdued earthy embroidery, "
        "period-accurate braided sash, subtle sand-worn desert traveler draping"
    ),
    "greco_roman": (
        "draped natural wool chiton and woven himation mantle in muted terracotta and ecru tones, "
        "fastened with discreet antique bronze fibula brooches, authentic classical leather traveler sandals"
    ),
    "ottoman": (
        "tailored silk-and-wool entari robe with delicate floral cordwork over wide fine-cotton salvar trousers, "
        "understated traveling kaftan with subtle leather belt and period footwear"
    ),
    "neolithic": (
        "expertly tailored stitched deerskin and soft woven flax tunic, natural sinew bindings, "
        "raw-edge earthy fur-trimmed shoulder mantle, prehistoric amber bead accents"
    ),
    "world_war_i": (
        "period-plausible ankle-length charcoal wool skirt, high-neck unbleached linen blouse, heavy olive wool field coat "
        "with hand-stitched seams and small brass buttons, leather ankle boots; no synthetic fabrics or modern tactical gear"
    ),
    "medieval": (
        "sturdy wool cotehardie dress with fitted sleeves, under-chemise of bleached flax, "
        "earthy moss-green traveler cloak with hood, understated leather girdle belt"
    ),
    "mesopotamian": (
        "fringed woolen kaunakes wrap with geometric woven border, layered unbleached linen under-tunic, "
        "hammered copper wrist ornament"
    ),
    "victorian": (
        "tailored 19th-century naturalist explorer ensemble, tailored tweed riding jacket with brass buttons, "
        "high-collar linen blouse, pleated walking skirt, sturdy lace-up leather boots"
    ),
}


def detect_era(text: str) -> str:
    """Infer historical era from topic or text keywords for wardrobe camouflage."""
    lower = str(text or "").casefold()
    if any(k in lower for k in ("gallipoli", "canakkale", "çanakkale", "1915", "world war i", "wwi", "first world war", "anzac", "ottoman empire", "dardanelles campaign", "seyit onbasi", "seyit onbaşı", "mecidiye", "pxixpeatiqc")):
        return "world_war_i"
    if any(k in lower for k in ("gobekli", "göbekli", "tepe", "neolithic", "stone age", "cave", "prehistoric", "ice age", "mammoth", "karahan", "tas tepeler", "taş tepeler", "catalhoyuk", "çatalhöyük")):
        return "neolithic"
    if any(k in lower for k in ("egypt", "pyramid", "pharaoh", "nile", "hawara", "tomb", "sphinx", "mummy", "luxor", "cairo")):
        return "egyptian"
    if any(k in lower for k in ("rome", "roman", "greek", "greece", "athens", "pompeii", "pompei", "vesuvius", "vezüv", "vezuv", "caesar", "sparta", "olympia", "gladiator", "qzzoxhjtliw")):
        return "greco_roman"
    if any(k in lower for k in ("ottoman", "istanbul", "constantinople", "sultan", "bazaar", "topkapi", "byzantine", "anatolia")):
        return "ottoman"
    if any(k in lower for k in ("medieval", "castle", "knight", "middle ages", "crusade", "viking", "feudal")):
        return "medieval"
    if any(k in lower for k in ("mesopotamia", "sumer", "babylon", "uruk", "tigris", "euphrates", "cuneiform")):
        return "mesopotamian"
    if any(k in lower for k in ("victorian", "19th century", "steampunk", "industrial", "darwin")):
        return "victorian"
    if any(k in lower for k in ("chernobyl", "nuclear", "reactor", "meltdown", "radiation", "titanic", "disaster", "explosion", "fire", "crash")):
        return "modern_disaster"
    if any(k in lower for k in ("apollo", "nasa", "space", "rocket", "astronaut", "moon landing", "shuttle", "iss", "satellite")):
        return "modern_space"
    return "default"


ERA_WITNESS_CATALOG: dict[str, list[dict[str, str]]] = {
    "egyptian": [
        {
            "id": "witness_egypt_architect",
            "name": "Chief Royal Architect Neferhotep",
            "era_label": "1840 BC — Middle Kingdom Egypt",
            "location_stamp": "HAWARA, EGYPT — 1840 BC",
            "appearance": (
                "50-year-old ancient Egyptian royal master architect from the 12th Dynasty reign of Pharaoh Amenemhat III, "
                "weathered sun-bronzed Middle Eastern male facial features, deep intelligent dark eyes, closely shaved head, "
                "wearing authentic Middle Kingdom fine pleated unbleached white linen shendyt kilt and broad collar, "
                "holding an unrolled papyrus architectural blueprint scroll and bronze plumb-bob tool"
            ),
        },
        {
            "id": "witness_greek_historian",
            "name": "Historian Herodotus of Halicarnassus",
            "era_label": "450 BC — Classical Antiquity",
            "location_stamp": "LAKE MOERIS, FAIYUM — 450 BC",
            "appearance": (
                "45-year-old ancient Greek traveler and historian Herodotus visiting Egypt, "
                "bearded Mediterranean male scholar with gray-streaked dark curls, expressive weathered face, "
                "wearing authentic classical draped natural wool chiton and terracotta himation travel cloak, "
                "holding a wooden wax writing tablet and bronze stylus"
            ),
        },
    ],
    "greco_roman": [
        {
            "id": "witness_roman_engineer",
            "name": "Master Engineer Marcus Vitruvius",
            "era_label": "25 BC — Roman Empire",
            "location_stamp": "ROME, ITALY — 25 BC",
            "appearance": (
                "52-year-old Roman imperial civil engineer and architect, stern weathered Mediterranean male face, "
                "short cropped gray hair, wearing authentic wool tunic and off-white toga praetexta with bronze fibula, "
                "holding a Roman groma surveying rod and wax parchment scroll"
            ),
        },
        {
            "id": "witness_greek_chronicler",
            "name": "Chronicler Pausanias",
            "era_label": "160 AD — Greco-Roman Era",
            "location_stamp": "MEDITERRANEAN BASIN — 160 AD",
            "appearance": (
                "48-year-old Greek geographer and eyewitness traveler, full trimmed beard, deep-set observant eyes, "
                "wearing woven linen chiton and weathered travel cloak, holding an ancient parchment codex"
            ),
        },
        {
            "id": "witness_pompeii_baker",
            "name": "Master Baker Terentius Neo",
            "era_label": "79 AD — Pompeii, Roman Empire",
            "location_stamp": "PISTRINUM, POMPEII — 79 AD",
            "appearance": (
                "40-year-old Roman baker and pistrinum owner in Pompeii, weathered olive-skinned Mediterranean male face, "
                "short dark curls, light dusting of flour on cheeks, wearing authentic Roman unbleached wool tunica with rope belt, "
                "leather worker sandals, holding a wooden baker's peel beside a circular lava-stone grain mill and brick oven; "
                "strictly NO medieval armor, NO sunglasses, NO wristwatches"
            ),
        },
    ],
    "world_war_i": [
        {
            "id": "witness_seyit_onbasi",
            "name": "Corporal Seyit (Seyit Onbaşı)",
            "era_label": "18 March 1915 — Mecidiye Bastion, Gallipoli",
            "location_stamp": "RUMELİ MECİDİYE BASTION, ÇANAKKALE — 18 MARCH 1915",
            "appearance": (
                "26-year-old broad-shouldered muscular Ottoman artillery corporal Seyit Çabuk, "
                "weathered Anatolian male face covered in powder soot and sweat, determined intense eyes, thick dark mustache, "
                "wearing authentic 1915 Ottoman khaki wool service uniform, khaki cloth kabalak (Enveriye) folded sun-hat, "
                "leather ammunition belt and worn field boots; strictly NO red fez, NO fez hat; "
                "holding artillery rammer and grease cloth beside the 28cm Krupp coastal gun"
            ),
        },
        {
            "id": "witness_battery_commander",
            "name": "Battery Commander Captain Nihat Bey",
            "era_label": "18 March 1915 — Mecidiye Bastion",
            "location_stamp": "DARDANELLES SHORE BATTERY — 1915",
            "appearance": (
                "35-year-old Ottoman artillery officer, dignified focused face with field mustache, soot on cheek, "
                "wearing authentic 1915 Ottoman officer khaki wool field tunic with collar insignia, khaki cloth kabalak sun-hat, "
                "leather map case and brass binoculars; strictly NO red fez, NO red felt hat"
            ),
        },
    ],
    "ottoman": [
        {
            "id": "witness_ottoman_architect",
            "name": "Imperial Architect Sinan's Chief Kalfa Davud",
            "era_label": "1557 AD — Ottoman Empire",
            "location_stamp": "KONSTANTINIYYE — 1557 AD",
            "appearance": (
                "50-year-old Ottoman imperial master mason and hydraulic engineer, dignified bearded Anatolian male face, "
                "wearing authentic 16th-century Ottoman quilted kavuk turban and earth-toned wool kaftan over silk entari, "
                "holding brass dividers and an illuminated Ottoman architectural plan"
            ),
        },
        {
            "id": "witness_ottoman_traveler",
            "name": "Traveler Evliya Çelebi",
            "era_label": "1648 AD — Ottoman Era",
            "location_stamp": "ISTANBUL — 1648 AD",
            "appearance": (
                "42-year-old Ottoman court chronicler and world traveler, sharp observant eyes, neatly trimmed mustache and beard, "
                "wearing authentic dark green traveling kaftan and leather belt with brass inkhorn and reed pen"
            ),
        },
    ],
    "neolithic": [
        {
            "id": "witness_neolithic_carver",
            "name": "Master Stone Carver Torkhan",
            "era_label": "9600 BC — Pre-Pottery Neolithic",
            "location_stamp": "TAŞ TEPELER, ANATOLIA — 9600 BC",
            "appearance": (
                "45-year-old Pre-Pottery Neolithic master monolith carver, rugged sun-weathered prehistoric male face, "
                "long braided dark hair with bone beads, wearing stitched deerskin tunic and woven flax wrap, "
                "holding a knapped flint chisel and heavy basalt hammerstone"
            ),
        },
        {
            "id": "witness_neolithic_elder",
            "name": "Enclosure Keeper Arukh",
            "era_label": "9500 BC — Pre-Pottery Neolithic",
            "location_stamp": "GÖBEKLİTEPE — 9500 BC",
            "appearance": (
                "58-year-old Neolithic ritual astronomer and elder, gray-bearded weathered face with ochre markings, "
                "wearing fur-trimmed hide mantle and carved limestone pendant"
            ),
        },
    ],
    "default": [
        {
            "id": "witness_ancient_builder",
            "name": "Master Builder Kaelen",
            "era_label": "Ancient Era — Primary Construction Phase",
            "location_stamp": "HISTORICAL SITE — ANTIQUITY",
            "appearance": (
                "50-year-old historical master stonemason and chief architect of the era, "
                "weathered authentic period-accurate male face, intelligent eyes, wearing historically authentic woven linen and wool craftsman attire, "
                "holding period bronze measuring calipers and carved stone schematic"
            ),
        },
        {
            "id": "witness_ancient_chronicler",
            "name": "Eyewitness Chronicler Damon",
            "era_label": "Classical Era — Historical Record",
            "location_stamp": "HISTORICAL ARCHIVE — ANTIQUITY",
            "appearance": (
                "46-year-old historical scholar and eyewitness chronicler, bearded weathered face, "
                "wearing authentic period traveler cloak and natural linen tunic, holding an ancient manuscript scroll"
            ),
        },
    ],
}


def get_era_witness(era: str = "default", slot: int = 1) -> dict[str, str]:
    """Return a deterministic historical witness profile for the given era and slot (1 or 2)."""
    key = (era or "default").strip().casefold()
    pool = ERA_WITNESS_CATALOG.get(key) or ERA_WITNESS_CATALOG["default"]
    idx = max(0, min(len(pool) - 1, slot - 1))
    return dict(pool[idx])


@dataclass(frozen=True)
class CharacterProfile:
    """Immutable persistent character identity designed for visual stability across AI models."""

    name: str = "Nova"
    gender: str = "female"
    age_range: str = "28 years old"
    archetype: str = "adventurous field explorer & chronological time traveler"
    face_traits: str = (
        "striking hazel eyes with warm amber flecks, high defined cheekbones, natural photorealistic skin texture "
        "with subtle faint freckles across nose bridge and upper cheeks, soft arched dark-brown eyebrows, "
        "warm light-olive skin tone, symmetrical feminine facial bone structure, confident, intelligent, charismatic expression"
    )
    hair_traits: str = "dark chestnut-brown textured wavy hair, shoulder-length, practical loose adventurer cut"
    time_device: str = DEFAULT_TIME_DEVICE
    wardrobe: str = ERA_WARDROBE_CATALOG["default"]
    accessories: str = "compact wireless lapel microphone clipped to collar, distressed dark leather field wristband"
    default_expression: str = "focused curiosity, adventurous enthusiasm, warm engaging presence"

    def wardrobe_for_era(self, era: str = "default") -> str:
        """Return era-appropriate camouflage wardrobe."""
        key = (era or "default").strip().casefold()
        return ERA_WARDROBE_CATALOG.get(key, ERA_WARDROBE_CATALOG["default"])

    def anchor_description(self, era: str = "default") -> str:
        """Condensed visual anchor string injected into prompts to lock appearance."""
        active_wardrobe = self.wardrobe_for_era(era) if era else self.wardrobe
        return (
            f"{self.name}, a {self.age_range} {self.gender} {self.archetype}; "
            f"FACE LOCK: {self.face_traits}; HAIR: {self.hair_traits}; "
            f"SIGNATURE ARTIFACT: {self.time_device}; "
            f"WARDROBE CAMOUFLAGE: wearing {active_wardrobe}; {self.accessories}"
        )


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
            "subtle friendly confidence. Professional documentary studio lighting, soft fill light, "
            "sharp focus on facial micro-features and skin pores, 8k resolution, cinematic photorealism, "
            f"{self.aspect_ratio} composition. ZERO text, ZERO watermarks."
        )

    def three_quarter_prompt(self, era: str = "default") -> str:
        return (
            f"CHARACTER REFERENCE SHEET [THREE-QUARTER VIEW]: {self.character.anchor_description(era)}. "
            "Three-quarter angle portrait, looking slightly off-camera, curious inquisitive gaze, "
            "cinematic natural backlight, realistic hair strands, sharp eye catchlights, "
            f"documentary photography quality, {self.aspect_ratio} composition. ZERO text, ZERO watermarks."
        )

    def field_action_prompt(self, location_hint: str = "ancient expedition site", era: str = "default") -> str:
        return (
            f"CHARACTER REFERENCE SHEET [FIELD VLOG ACTION]: {self.character.anchor_description(era)}. "
            f"Mid-shot holding camera in selfie/vlog style on location at {location_hint}. "
            "Expedition background with cinematic atmospheric depth of field blur, natural golden hour lighting, "
            "expressive speech posture, realistic fabric creases on utility jacket, "
            f"photorealistic 8k documentary frame, {self.aspect_ratio} composition. ZERO text, ZERO watermarks."
        )

    def artifact_macro_prompt(self) -> str:
        return (
            f"CHARACTER REFERENCE SHEET [TEMPORAL ARTIFACT CLOSE-UP]: Extreme macro close-up of {self.character.time_device}. "
            "Worn on female wrist with natural warm olive skin and subtle fine freckles, intricate rotating brass gears, "
            "subtle glowing gyroscopic astrolabe rings, crystalline sapphire face, ancient celestial engravings. "
            f"Dramatic cinematic directional macro lighting, shallow depth of field, 8k photorealism, {self.aspect_ratio} composition. "
            "ZERO text, ZERO watermarks."
        )

    def era_camouflage_prompt(self, era: str) -> str:
        return (
            f"CHARACTER REFERENCE SHEET [ERA CAMOUFLAGE - {era.upper()}]: {self.character.anchor_description(era)}. "
            f"Medium full shot of host walking through historically authentic {era} setting, perfectly blending in with local population "
            "while her subtle glowing temporal chronometer wrist device remains discreetly visible on her left wrist. "
            f"Golden hour atmospheric volumetric lighting, authentic textures, 8k photorealistic cinema, {self.aspect_ratio} composition. "
            "ZERO text, ZERO watermarks."
        )

    def to_manifest(self) -> dict[str, Any]:
        era_sheets = {
            f"camouflage_{era}": self.era_camouflage_prompt(era)
            for era in ("egyptian", "greco_roman", "ottoman", "neolithic", "medieval", "victorian")
        }
        sheets = {
            "frontal": self.frontal_portrait_prompt(),
            "three_quarter": self.three_quarter_prompt(),
            "field_action": self.field_action_prompt(),
            "temporal_artifact": self.artifact_macro_prompt(),
            **era_sheets,
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
    char_name = getattr(config, "EXPLORER_CHARACTER_NAME", "Nova")
    if char_name and char_name.strip().casefold() != "nova":
        return CharacterProfile(name=char_name.strip().capitalize())
    return DEFAULT_CHARACTER


def classify_shot_role(shot_index: int, total_shots: int, journey_phase: str = "explore") -> dict[str, Any]:
    """Classify a shot into Nova Solo A-Roll, Historical Witness Interview, or Pure Architectural B-Roll.

    User Invariant:
    - Both Nova's solo time-traveler segments AND face-to-face historical witness interviews exist,
      and are clearly differentiated from each other and from pure B-Roll.
    - Nova on-camera A-Roll is strictly bounded to 3 pivotal shots (Opening, Midpoint, Closing).
    - When total_shots >= 8, 2 dedicated Historical Witness Interview shots are scheduled
      at ~28% and ~72% of the timeline (e.g. Shot 8 and Shot 20 in a 28-shot documentary).
    - All remaining shots are 100% people-free architectural/archaeological B-Roll.
    """
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

    # lip_sync_required is True only in Longform documentary mode (LONGFORM_MODE=True)
    # for Nova on-camera A-roll shots. In 9:16 Shorts mode ADR-002 mandates zero lip-sync.
    # Witness shots never require lip-sync (closed-mouth documentary framing only).
    _longform = bool(getattr(config, "LONGFORM_MODE", False))

    if is_opening:
        return {
            "role": "a_roll",
            "speaker": "nova",
            "is_speaking_avatar": True,
            "is_witness_interview": False,
            "camera_style": "vlog_selfie_host",
            "description": "On-camera host arrival hook: direct address to viewer, introducing site/mystery",
            "lip_sync_required": _longform,
        }
    if is_closing:
        return {
            "role": "a_roll",
            "speaker": "nova",
            "is_speaking_avatar": True,
            "is_witness_interview": False,
            "camera_style": "vlog_selfie_host",
            "description": "On-camera host sign-off: closing reflection and key takeaway",
            "lip_sync_required": _longform,
        }
    if is_turning_point:
        return {
            "role": "a_roll",
            "speaker": "nova",
            "is_speaking_avatar": True,
            "is_witness_interview": False,
            "camera_style": "vlog_selfie_reaction",
            "description": "On-camera host reaction: reacting to pivotal clue or shocking reveal",
            "lip_sync_required": _longform,
        }
    if shot_index == witness_1_idx:
        return {
            "role": "witness_interview",
            "speaker": "witness",
            "witness_slot": 1,
            "is_speaking_avatar": False,
            "is_witness_interview": True,
            "camera_style": "historical_witness_interview",
            "description": "Field interview with primary historical eyewitness in authentic period setting",
            "lip_sync_required": False,  # Witness: closed-mouth, ADR-002
        }
    if shot_index == witness_2_idx:
        return {
            "role": "witness_interview",
            "speaker": "witness",
            "witness_slot": 2,
            "is_speaking_avatar": False,
            "is_witness_interview": True,
            "camera_style": "historical_witness_interview",
            "description": "Field interview with secondary historical chronicler in authentic period setting",
            "lip_sync_required": False,  # Witness: closed-mouth, ADR-002
        }

    return {
        "role": "b_roll",
        "speaker": "nova",
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
    """Compile photorealistic prompt for a Nova A-Roll shot incorporating the character anchor."""
    style_str = f"{aspect_ratio} widescreen composition, photorealistic 8k documentary cinema"
    camera_style = shot_role_info.get("camera_style", "vlog_selfie_host")

    if camera_style == "vlog_selfie_host":
        framing = (
            "Medium close-up eye-level documentary framing with complete head, hair, and shoulders fully inside frame "
            "(generous headroom above crown of head, NEVER crop forehead or top of head), "
            "host observing the scene with a warm, engaged gaze and a neutral closed mouth; communicate through eye direction and restrained gestures, "
            "with no visible dialogue or lip movement because narration remains voiceover"
        )
    elif camera_style == "vlog_selfie_reaction":
        framing = (
            "Medium eye-level shot with complete head and shoulders fully inside frame "
            "(generous headroom above head, NEVER crop head), host turning toward camera and gesturing toward background phenomenon "
            "with wide amazed eyes, spontaneous real-time discovery reaction"
        )
    else:
        framing = "Medium eye-level shot with full headroom, host standing in environment inspecting surroundings"

    return (
        f"[SOLO TIME-TRAVELER HOST A-ROLL]: {character.anchor_description(era=era)}. {framing}. "
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
    """Compile photorealistic prompt for a Historical Witness field interview shot (distinct from Nova A-Roll)."""
    style_str = f"{aspect_ratio} widescreen composition, photorealistic 8k historical documentary cinema"
    name = witness.get("name", "Historical Eyewitness")
    era_label = witness.get("era_label", "Antiquity")
    appearance = witness.get("appearance", "authentic historical figure in period attire")
    return (
        f"[HISTORICAL EYEWITNESS INTERVIEW — {name.upper()} ({era_label})]: "
        f"Medium eye-level documentary interview portrait of {appearance}, "
        "complete head and shoulders fully visible inside frame with generous headroom, "
        "speaking directly with expressive gravitas and natural mouth articulation, "
        "warm flickering torchlight and natural directional key light on weathered skin textures. "
        f"Background: {environment_scene}, authentic historical era atmosphere, shallow depth of field, {style_str}. "
        "NO modern safari hats, NO modern clothing. "
        "STRICT VISUAL MANDATE: ZERO text, ZERO printed letters, ZERO typography, ZERO date stamps, "
        "ZERO year numbers written on image, ZERO name plaques, ZERO title banners, ZERO graphic cards, "
        "ZERO caption boxes, ZERO lower thirds, ZERO subtitles, ZERO watermarks."
    )


def get_host_lipsync_provider() -> str:
    """Return active lip-sync engine name from configuration."""
    return str(getattr(config, "EXPLORER_LIPSYNC_PROVIDER", "live_portrait") or "live_portrait").lower()


def is_lipsync_required_for_shot(shot_role_info: dict[str, Any]) -> bool:
    """Determine whether a shot requires on-camera talking avatar animation."""
    return bool(shot_role_info.get("lip_sync_required") or shot_role_info.get("is_speaking_avatar") or shot_role_info.get("is_witness_interview"))


