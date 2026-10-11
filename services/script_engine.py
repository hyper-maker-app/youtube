"""Provider-neutral screenplay model, validation, and canonical prompt compiler.

This module is deterministic: it contains no HTTP client, SDK, credential lookup, or
provider model choice. Providers receive the already-compiled prompts.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from services.mode_profile import ANATOMICAL, ModeProfile
import config
from providers.base import BaseLLMProvider, ProviderError
from timeline import TimelinePlan

def resolve_subject_description(subject_id: str, shots: list[Any], current_index: int | None = None) -> str:
    """Resolve a subject's description using the nearest preceding shot where it was primary."""
    if current_index is None:
        current_index = len(shots) - 1
    for shot in reversed(shots[:current_index + 1]):
        prim_id = str(getattr(shot, "subject_id", "subject"))
        if prim_id == subject_id:
            desc = str(getattr(shot, "subject_description", ""))
            if desc:
                return desc
    for shot in shots[current_index + 1:]:
        prim_id = str(getattr(shot, "subject_id", "subject"))
        if prim_id == subject_id:
            desc = str(getattr(shot, "subject_description", ""))
            if desc:
                return desc
    return subject_id.replace("_", " ")

_QUADRANT_ALIASES = {
    "upper_left": "top_left", "upper_right": "top_right",
    "lower_left": "bottom_left", "lower_right": "bottom_right",
    "bottom_center": "lower_center", "lower_middle": "lower_center",
    "upper_middle": "upper_center",
}
_QUADRANTS = set(config.QUADRANT_COORDS)
SCALES = ("wide", "medium", "close", "macro", "micro", "nano")
JOURNEY_PHASES = ("establish", "descend", "explore", "reveal", "resolve")
TRANSITION_KINDS = ("same_subject", "subject_change", "scale_transition", "location_change")
MARKER_TYPES = ("none", "arrow", "trajectory")
MAX_SCALE_JUMP = 2

_LIGHTING_MATRIX = {
    "wide": "5600K warm golden directional daylight at 45-degree angle, deep readable contact shadows, 8000K subtle cyan edge separation, sharp cyan rim light",
    "medium": "5600K balanced documentary key light, controlled contrast, clear material separation, sharp cyan rim light",
    "close": "5600K precise studio key, shallow optical depth, crisp surface microtexture, sharp cyan rim light separating subject from void",
    "macro": "transilluminated macro lighting, controlled subsurface scattering (SSS) on tissue, sharp cyan rim light separating subject from void",
    "micro": "cool clinical 6000K key with warm internal bioluminescent practical, controlled optical translucency, sharp cyan rim light",
    "nano": "nanoscale dual-wavelength illumination: X-ray-blue and teal-cyan bioluminescent light passing through translucent lattice, sharp cyan rim light",
}

_SCALE_OPTICS = {
    "wide": "24mm wide-angle lens, f/4.0 deep focus, grounded perspective",
    "medium": "50mm documentary prime lens, f/2.8 natural perspective, balanced depth of field",
    "close": "85mm portrait prime lens, f/1.8 shallow depth of field, subtle cinematic bokeh",
    "macro": "100mm macro lens, f/2.8, extreme shallow depth of field, crisp focal plane with microtexture",
    "micro": "high-magnification clinical lens, f/5.6, controlled flat focal plane",
    "nano": "scanning electron / nanoscale bioluminescent visualization optics",
}

_PHASE_FRAMING = {
    "establish": "dramatic wide optical framing with deep visual perspective",
    "descend": "continuous linear perspective aligned with the physical transition trajectory",
    "explore": "balanced documentary perspective with crisp depth separation",
    "reveal": "tight macro focus locked squarely onto the causal impact point",
    "resolve": "stable resolved framing locking the final physical state",
}

_DOMAIN_PHYSICS_VERBS = {
    "anatomical": "viscous fluid surge, elastic tissue distension under pressure, rhythmic contraction, mucosal deformation",
    "biological": "cellular membrane deformation, viscous fluid flow, pressure-driven elastic stretching",
    "mechanical": "tensile strain, micro-fissure propagation along stress lines, mechanical give under load, structural shear",
    "environmental": "viscous particulate dispersion, atmospheric pressure gradient, convective fluid drift",
    "molecular": "molecular binding kinetics, surface tension deformation, lattice vibrational stress",
    "space": "orbital trajectory inertia, zero-gravity particulate drift, vacuum thermal dissipation",
    "incident": "physical restraint tension, structural door-handle torque, cabin pressure equalization, emergency latch resistance, seat displacement, fabric strap strain",
}

_DOMAIN_AUDIO_CUES = {
    "anatomical": "subtle visceral fluid flow, muted tissue expansion, sterile room tone",
    "biological": "effervescent cellular activity, viscous liquid displacement, low resonant drone",
    "mechanical": "dense metallic friction, subtle mechanical torque click, sterile hum",
    "environmental": "low atmospheric resonance, subtle air pressure shift, muted rush",
    "molecular": "subtle high-frequency resonance, molecular click, sterile quiet",
    "space": "deep vacuum sub-bass drone, faint pressurized hiss",
    "incident": "metallic door latch strain, cabin ambient hum, muffled crowd murmur, seat belt mechanism click, overhead bin rattle",
}

_PHASE_DIRECTION = {
    "establish": "open on the single most dramatic, readable state of the danger or question",
    "descend": "make the move into the relevant mechanism or scale through one visible physical transition",
    "explore": "inspect one structure or mechanism through its active physical behavior",
    "reveal": "make the causal payoff physically visible through the named state change",
    "resolve": "finish with a clean, understandable and stable physical result",
}
_DOMAIN_SCALES = {
    "environmental": {"wide", "medium", "close"}, "mechanical": {"wide", "medium", "close", "macro"},
    "anatomical": set(SCALES), "biological": set(SCALES), "molecular": {"macro", "micro", "nano"},
    "space": {"wide", "medium", "close"},
    "incident": {"wide", "medium", "close", "macro"},
}
_DOMAIN_ALIASES = {
    "object": "mechanical", "human": "anatomical", "medical": "anatomical", "physics": "mechanical",
    "micro": "anatomical", "macro": "anatomical", "nano": "molecular", "cellular": "biological",
    "biology": "biological", "anatomy": "anatomical", "bio": "biological", "biomedical": "anatomical",
    "incident": "incident", "news": "incident", "event": "incident",
    "crime": "incident", "accident": "incident",
}

_CONTRAST_KEYWORDS: set[str] = {
    "dark", "navy", "black", "blue", "white", "gray", "grey", "brown", "red", "maroon",
    "green", "yellow", "orange", "beige", "tan", "khaki",
    "uniform", "jacket", "shirt", "vest", "suit", "hoodie", "coat", "trousers", "pants",
    "sweater", "blazer", "scrubs", "overalls",
}

# ---------------------------------------------------------------------------
# ADR-028: Domain-Bleed Isolation — mechanical metaphor -> biological equivalent
# When anatomical mode uses mechanical analogies (wiper, pump, valve), the image
# model can drift into industrial/factory latent space.  This dictionary maps
# bare mechanical terms to their biological equivalents so prompts stay anchored
# in the organic tissue domain.  Applied only in anatomical/biological modes.
# ---------------------------------------------------------------------------
_ANATOMICAL_DOMAIN_BLEED_MAP: dict[str, str] = {
    "wiper": "sweeping mucosal membrane",
    "wipers": "sweeping mucosal membranes",
    "piston": "rhythmic muscular contraction",
    "pistons": "rhythmic muscular contractions",
    "pump": "biological circulatory organ",
    "pumps": "biological circulatory organs",
    "valve": "muscular sphincter flap",
    "valves": "muscular sphincter flaps",
    "engine": "cellular metabolic engine",
    "engines": "cellular metabolic engines",
    "chassis": "skeletal framework",
    "machine": "biological mechanism",
    "machines": "biological mechanisms",
    "machinery": "biological mechanisms",
    "factory": "cellular production site",
    "factories": "cellular production sites",
    "conveyor": "ciliary transport surface",
    "conveyors": "ciliary transport surfaces",
    "turbine": "rotational cellular organelle",
    "turbines": "rotational cellular organelles",
    "pipe": "vascular conduit",
    "pipes": "vascular conduits",
    "cable": "neural fiber bundle",
    "cables": "neural fiber bundles",
    "gear": "interlocking joint surface",
    "gears": "interlocking joint surfaces",
    "metal": "mineralized tissue",
    "steel": "rigid calcified structure",
    "iron": "hemoglobin-bound mineral",
    "bolt": "ligament attachment point",
    "bolts": "ligament attachment points",
    "spring": "elastic connective tissue",
    "springs": "elastic connective tissues",
    "hose": "flexible tubular vessel",
    "hoses": "flexible tubular vessels",
    "nozzle": "ductal orifice",
    "nozzles": "ductal orifices",
    "tank": "fluid reservoir organ",
    "tanks": "fluid reservoir organs",
}

_DOMAIN_BLEED_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _ANATOMICAL_DOMAIN_BLEED_MAP) + r")\b",
    re.IGNORECASE,
)


def _isolate_domain_bleed(text: str, mode_name: str) -> str:
    """Replace bare mechanical metaphors with biological equivalents in anatomical mode.

    In mechanical or incident modes, the original terms are preserved because
    they are the correct domain vocabulary.
    """
    if mode_name not in {"anatomical", "biological"}:
        return text
    def _replace(match: re.Match[str]) -> str:
        return _ANATOMICAL_DOMAIN_BLEED_MAP.get(match.group(0).lower(), match.group(0))
    return _DOMAIN_BLEED_RE.sub(_replace, text)


# ---------------------------------------------------------------------------
# ADR-028: Universal Anti-Text / Anti-Symbol Shield
# Hardened prohibitions appended to every keyframe and motion prompt to prevent
# Nano Banana Pro / Gemini 3 Pro from hallucinating letters, numbers, chemical
# formulas, or scientific labels onto rendered surfaces.
# ---------------------------------------------------------------------------
_ANTI_TEXT_SHIELD = (
    "ABSOLUTE TEXT PROHIBITION: Pure visual geometry only — the rendered image must be "
    "completely devoid of any letters, numbers, chemical formula symbols (no Na+, no Cl-, "
    "no H2O, no molecular notation), scientific labels, annotations, captions, diagrams, "
    "infographic elements, flat 2D graphic arrows, sticker pointer overlays, or watermarks on any surface, object, or background. "
    "Represent ions, atoms, and molecules as unlabeled luminous spheres or abstract "
    "geometric forms only."
)

_LONGFORM_TEXT_SHIELD = (
    "No readable text, labels, generated captions, diagrams, graphics, logos, or watermarks. "
    "Keep maps and documents visually period-authentic with markings too small to read."
)

_ROSTER_ANTI_TEXT_SUFFIX = (
    " ABSOLUTE PROHIBITION: This reference sheet must contain ZERO text, ZERO letters, "
    "ZERO numbers, ZERO chemical symbols, ZERO labels, ZERO annotations, ZERO watermarks "
    "anywhere in the image. No split-screen, no multi-panel, no diagram layout. "
    "Pure visual geometry and materials only."
)

_CAMERA_VIEWPOINT_MANDATE = (
    "CAMERA VIEWPOINT MANDATE: 100% EXTERIOR perspective. Strictly NO interior elements."
)

_INTERIOR_CLEANSE_RE = re.compile(
    r"\b(?:cockpit\s+interior|inside\s+(?:the\s+)?cabin|flight\s+deck\s+instruments|"
    r"inside\s+(?:the\s+)?cockpit|cockpit\s+flight\s+deck|cockpit\s+cabin|interior\s+cockpit|"
    r"cabin\s+interior|inside\s+(?:the\s+)?flight\s+deck|seated\s+in\s+cockpit|"
    r"seated\s+inside\s+(?:the\s+)?cockpit|sitting\s+in\s+cockpit|cockpit\s+seat|"
    r"flight\s+deck\s+chairs?|flight\s+controls\s+console)\b",
    re.IGNORECASE,
)


# The LLM authors a compact visual brief, but the compiler owns the immutable
# render contract.  Keep generated prose from re-introducing prohibited visual
# modes through the raw brief that is appended to every canonical prompt.
_MODEL_BRIEF_REWRITES: tuple[tuple[str, str], ...] = (
    (r"\bstylized-realistic\b", "glossy stylized 3D"),
    (r"\bphotorealistic\b", "glossy stylized 3D"),
    (r"\breal\s+life\b", "studio-rendered"),
    (r"\b(?:realistic|stock)\s+(?:photo|photography|portrait|image)\b", "clean stylized 3D animation render"),
    (r"\blive-action\b", "3D animated"),
    (r"\bhuman\s+photograph\b", "stylized 3D mannequin"),
    (r"\brealistic\b", "stylized"),
    # RAI Pre-Filtering & Scientific Steering (Veo / Multimodal Safety)
    (r"\b(?:razor(?:\s+blade)?|sharp\s+blade|scalpel|box\s*cutter)\b", "calibrated metallic pellet"),
    (r"\bblade\b", "metallic probe"),
    (r"\b(?:knife|knives)\b", "blunt metallic instrument"),
    (r"\bhydrochloric\s+acid\b", "concentrated amber digestive fluid"),
    (r"\bcaustic(?:\s+acid)?\b", "concentrated digestive liquid"),
    (r"\b(?:burn|burning|burnt|unburnt|searing)\b", "thermal reaction"),
    (r"\b(?:flesh|raw\s+meat)\b", "epithelial cellular matrix"),
    (r"\b(?:blood|bleeding|bloody|hemorrhage)\b", "crimson vital fluid"),
    (r"\b(?:wound|puncture|laceration|stab)\b", "fissure penetration"),
    (r"\bcut\b", "fissure aperture"),
    (r"\b(?:needle|syringe)\b", "micro delivery probe"),
    (r"\b(?:cancer|tumor|malignancy)\b", "abnormal cellular cluster"),
)

# Provider-generated camera choreography routinely produces sliding 2D layers or
# morphing geometry. Keep physical verbs such as "pressure pushes fluid" intact,
# but remove unmistakable cinematography instructions from authored briefs.
# Whitelist allows controlled continuous camera flight transitions (push-through and pull-back reveal).
_CONTROLLED_TRANSITION_PHRASES = (
    r"rapid macro push-in",
    r"camera accelerates smoothly toward",
    r"penetrating the tissue boundary",
    r"penetrate the tissue boundary",
    r"penetrating toward the",
    r"along the oral axis",
    r"along the optical axis",
    r"along the optical penetration axis",
    r"along the penetration axis",
    r"continuous rapid pull-back reveal",
    r"pull-back zoom-out reveal",
    r"rapid pull-back reveal",
    r"pull-back reveal",
    r"pull-out reveal",
    r"zoom-out reveal",
    r"pulling out from the",
    r"camera accelerates backward along",
    r"storyboard interpolation",
    r"push-through",
)
_CONTROLLED_TRANSITION_RE = re.compile(r"|".join(_CONTROLLED_TRANSITION_PHRASES), re.I)

_CAMERA_COMMAND_RE = re.compile(
    r"\b(?:"
    r"(?:the\s+)?camera\s+(?:zooms?|pans?|orbits?|push(?:es)?(?:\s+in)?|doll(?:y|ies)|tracks?|cranes?|slides?|moves?|"
    r"is\s+handheld)(?:\s+(?:in|out|forward|backward|toward|to|from|around|through|slowly|quickly|aggressively))*"
    r"|(?:crash\s+)?zoom(?:s|ing)?"
    r"|(?:dolly|tracking|crane|handheld)(?:\s+\w+){0,4}"
    r")\b",
    re.I,
)
PRESENTATION_MODES = (
    "mechanism", "contextual_opening_anchor", "opening_anchor",
    "return_to_opening_anchor_payoff", "return_to_contextual_anchor_payoff",
)
CONTEXTUAL_ANCHOR_KINDS = ("human", "animal", "object", "vehicle", "structure", "environment", "organ", "science_subject")
_DECORATIVE_PAYOFF_RE = re.compile(r"\b(?:close|closing|end|ending|loop|satisf(?:y|ying)|wrap(?:\s*up)?)\b", re.I)

_ELI12_NARRATION_REWRITES: tuple[tuple[str, str], ...] = (
    (r"\bvasoconstriction\b", "blood vessels panic and slam shut"),
    (r"\bvasodilation\b", "blast open with hot blood"),
    (r"\btrigeminal\s+nerve\b", "major nerve hooked to your forehead"),
    (r"\bcranial\s+pathway\b", "nerve pathway"),
    (r"\bnociceptive\s+signals?\b", "screaming pain signals"),
    (r"\bnociceptive\s+distress\b", "sudden sharp pain"),
    (r"\bcellular\s+necrosis\b", "cells break down and die"),
    (r"\bapoptosis\b", "cell death"),
    (r"\bcerebral\s+cortex\b", "your brain's control center"),
    (r"\bhypothalamus\b", "your brain's master thermostat"),
    (r"\bpathophysiology\b", "the reaction"),
    (r"\balveolar\s+surface\s+tension\b", "sticky liquid pulling air sacs shut"),
    (r"\b(?:pulmonary\s+)?surfactant\b", "natural slippery coating"),
    (r"\bbarotrauma\b", "crushing pressure squeeze"),
    (r"\bischemia\b", "blood starvation"),
    (r"\bhypoxia\b", "oxygen starvation"),
    (r"\bintracranial\s+pressure\b", "pressure inside your skull"),
    (r"\bcerebrospinal\s+fluid\b", "brain cushioning fluid"),
    (r"\b(?:microbial\s+)?pathogens?\b", "harmful microscopic invaders"),
    (r"\bepithelial\s+(?:barrier|layer)\b", "protective cellular shield"),
    (r"\bdifferential\s+pressure\b", "crushing air pressure difference"),
    (r"\bperistalsis\b", "wave-like muscular squeezing"),
    (r"\btympanic\s+membrane\b", "eardrum"),
    (r"\bsphincter\b", "tight muscular ring valve"),
    (r"\b(?:arteriosclerosis|atherosclerosis)\b", "clogged hardened pipes"),
    (r"\bhemostasis\b", "emergency clot seal"),
    (r"\bmyocardial\s+infarction\b", "heart attack shutdown"),
    (r"\bgastroesophageal\s+reflux\b", "acid splashing back up"),
    (r"\bsphenopalatine\s+ganglion\b", "nerve cluster behind your nose"),
    (r"\b(?:erythrocytes|leukocytes)\b", "vital cellular workers"),
)


def sanitize_eli12_narration(text: str) -> str:
    """Ensure narration adheres strictly to ELI12 Zack D. Films style."""
    for pattern, replacement in _ELI12_NARRATION_REWRITES:
        text = re.sub(pattern, replacement, text, flags=re.I)
    return text


def _canonicalize_model_brief(value: object, mode: ModeProfile = ANATOMICAL) -> str:
    """Strip model-authored terms that conflict with the fixed render contract."""
    text = str(value or "")
    is_longform = mode.name == "explorer" or ((getattr(config, "LONGFORM_MODE", False) or getattr(config, "IS_EXPLORER_FORMAT", False)) and mode.name not in {"anatomical", "incident", "mechanical"})
    rewrites = _MODEL_BRIEF_REWRITES[7:] if is_longform else _MODEL_BRIEF_REWRITES
    for pattern, replacement in rewrites:
        text = re.sub(pattern, replacement, text, flags=re.I)
    
    if mode.character_style == "role_based":
        text = re.sub(r"\bstylized 3D mannequin\b", "stylized 3D character", text, flags=re.I)

    # Mode-conditional environment censorship (fail-safe: ANATOMICAL censors)
    if mode.environment_censor:
        text = re.sub(r"\bliving\s+room\b", "deep dark neutral studio void", text, flags=re.I)
        text = re.sub(r"\b(?:hospital|street|bedroom|office|wall|sky)\b", "deep dark neutral studio void", text, flags=re.I)

    saved: dict[str, str] = {}
    def _mask(match: re.Match[str]) -> str:
        key = f"__CTRL_TRANS_{len(saved)}__"
        saved[key] = match.group(0)
        return key
    masked = _CONTROLLED_TRANSITION_RE.sub(_mask, text)
    cleaned = _CAMERA_COMMAND_RE.sub("", masked)
    for key, orig in saved.items():
        cleaned = cleaned.replace(key, orig)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    cleaned = _isolate_domain_bleed(cleaned, mode.name)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def _quadrant(value: object) -> str:
    candidate = str(value or "center").casefold().replace("-", "_").replace(" ", "_")
    candidate = _QUADRANT_ALIASES.get(candidate, candidate)
    return candidate if candidate in _QUADRANTS else "center"


def _domain(value: object) -> str:
    candidate = str(value or "mechanical").casefold().replace("-", "_").replace(" ", "_")
    return _DOMAIN_ALIASES.get(candidate, candidate)


def _is_human_subject(fields: dict[str, object]) -> bool:
    """Identify a human character subject."""
    sid = str(fields.get("subject_id") or "").casefold()
    if re.search(r"\b(?:aircraft|airframe|airplane|plane|jet|airliner|fuselage|cockpit|cabin|wing|engine|hull|vehicle|car|boat|ship|tarmac|runway|door|latch|window|seat|strap|panel|gear|valve|pump)\b", sid):
        return False
    source = " ".join(str(fields.get(name) or "") for name in (
        "subject_id", "subject_description", "start_image_prompt", "end_image_prompt",
    ))
    return bool(re.search(r"\b(?:human(?:\s+body)?|person|man|woman|boy|girl|character|passenger|pilot|captain|copilot|attendant|officer|driver|operator|mechanic|doctor|patient|bystander|traveler|explorer|host|presenter|nova)\b", source, re.I))


@dataclass
class Beat:
    index: int
    text: str
    role: str = "default"
    emphasis: list[str] = field(default_factory=list)


def _parse_prior_exit_states(raw: Any) -> list[Any]:
    if not isinstance(raw, list):
        return []
    parsed = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            subjs, state = item
            subj_list = [str(x) for x in subjs] if isinstance(subjs, (list, tuple, set)) else [str(subjs)]
            parsed.append((subj_list, str(state)))
        elif isinstance(item, dict) and "exit_state" in item:
            subjs = item.get("subjects") or item.get("subject_ids") or []
            subj_list = [str(x) for x in subjs] if isinstance(subjs, (list, tuple, set)) else [str(subjs)]
            parsed.append((subj_list, str(item["exit_state"])))
        elif isinstance(item, str):
            parsed.append(item)
    return parsed


@dataclass
class Shot:
    block: int
    beat_index: int
    t_start: float
    t_end: float
    subject_id: str
    subject_description: str = ""
    start_image_prompt: str = ""
    end_image_prompt: str = ""
    motion_prompt: str = ""
    target_quadrant: str = "center"
    end_target_quadrant_value: str | None = None
    visual_domain: str = "mechanical"
    dominant_event: str = ""
    proof_on_screen: str = ""
    entry_state: str = ""
    exit_state: str = ""
    endpoint_mode: str = "first_last"
    caption_safe_zone: str = "lower_middle"
    scale: str = "medium"
    journey_phase: str = "explore"
    transition_kind: str = "same_subject"
    camera_angle: str = "three_quarter"
    camera_vector: str = ""
    detail_target: str = ""
    structure_tags: list[str] = field(default_factory=list)
    quality_critical: list[str] = field(default_factory=list)
    continuity_anchor: str = ""
    marker_type: str = "none"
    marker_quadrant: str | None = None
    location_id: str = ""
    secondary_subject_ids: list[str] = field(default_factory=list)
    endpoint_reason: str = ""
    # Opening anchors are roster-backed identities, not a request to morph from
    # the preceding mechanism shot.  The terminal payoff is rendered separately
    # by the pipeline from the persisted identity below.
    presentation_mode: str = "mechanism"
    opening_anchor_id: str = ""
    payoff_reason: str = ""
    # Contextual anchors deliberately identify the viewer-facing subject separately
    # from the organ/material/mechanism that the story subsequently enters.
    contextual_anchor_id: str = ""
    contextual_anchor_subject_id: str = ""
    contextual_anchor_kind: str = ""
    mechanism_anchor_id: str = ""
    contextual_anchor_roster_ids: list[str] = field(default_factory=list)
    contextual_anchor_appearance_contract: str = ""
    contextual_anchor_prompt_sha256: str = ""
    contextual_anchor_sheet_ids: list[str] = field(default_factory=list)
    # Editorial reframes are rendered locally; providers receive no camera movement
    # instruction.  Values are persisted as [{duration, quadrant}] and tile a block.
    coverage_beats: list[dict[str, Any]] = field(default_factory=list)
    impact_offset_seconds: float = 1.8
    prior_exit_states: list[Any] = field(default_factory=list)
    spatial_anchor: str = ""
    scale_level: str = ""
    forbidden_entities: list[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return round(self.t_end - self.t_start, 3)

    @property
    def start_target_quadrant(self) -> str:
        return _quadrant(self.target_quadrant)

    @property
    def end_target_quadrant(self) -> str:
        return _quadrant(self.end_target_quadrant_value or self.target_quadrant)

    @property
    def push_quadrant(self) -> str:
        return self.end_target_quadrant if self.end_target_quadrant != "center" else self.start_target_quadrant

    @property
    def normalized_domain(self) -> str:
        return _domain(self.visual_domain)

    @property
    def resolved_coverage_beats(self) -> list[dict[str, Any]]:
        is_flight = (
            self.transition_kind == "scale_transition"
            and (self.journey_phase in {"descend", "reveal", "resolve"} or self.scale in {"macro", "micro", "nano"})
        )
        if is_flight:
            return [
                {"duration": 1.333, "quadrant": "center"},
                {"duration": 1.334, "quadrant": "center"},
                {"duration": 1.333, "quadrant": "center"},
            ]
        if self.coverage_beats:
            return self.coverage_beats
        # Three 1.333-second editorial views satisfy the 1.0–1.6 second pacing
        # target while preserving one provider-native four-second physical event.
        return [
            {"duration": 1.333, "quadrant": self.start_target_quadrant},
            {"duration": 1.334, "quadrant": "center"},
            {"duration": 1.333, "quadrant": self.end_target_quadrant},
        ]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Shot":
        start = float(value.get("t_start", 0.0))
        end = float(value.get("t_end", start + float(value.get("duration", 4.0))))
        return cls(
            block=int(value.get("block", 0)), beat_index=int(value.get("beat_index", 1)), t_start=start, t_end=end,
            subject_id=str(value.get("subject_id") or "subject"), subject_description=str(value.get("subject_description") or ""),
            start_image_prompt=str(value.get("start_image_prompt") or value.get("image_prompt") or ""), end_image_prompt=str(value.get("end_image_prompt") or ""),
            motion_prompt=str(value.get("motion_prompt") or ""), target_quadrant=str(value.get("target_quadrant") or "center"),
            end_target_quadrant_value=value.get("end_target_quadrant") or value.get("push_quadrant"), visual_domain=str(value.get("visual_domain") or "mechanical"),
            dominant_event=str(value.get("dominant_event") or ""), proof_on_screen=str(value.get("proof_on_screen") or ""),
            entry_state=str(value.get("entry_state") or ""), exit_state=str(value.get("exit_state") or ""), endpoint_mode=str(value.get("endpoint_mode") or "first_last"),
            caption_safe_zone=str(value.get("caption_safe_zone") or "lower_middle"), scale=str(value.get("scale") or "medium"), journey_phase=str(value.get("journey_phase") or "explore"),
            transition_kind=str(value.get("transition_kind") or "same_subject"), camera_angle=str(value.get("camera_angle") or "three_quarter"), camera_vector=str(value.get("camera_vector") or ""),
            detail_target=str(value.get("detail_target") or ""), structure_tags=[str(x) for x in value.get("structure_tags") or []], quality_critical=[str(x) for x in value.get("quality_critical") or []],
            continuity_anchor=str(value.get("continuity_anchor") or ""), marker_type=str(value.get("marker_type") or "none"), marker_quadrant=value.get("marker_quadrant"),
            location_id=str(value.get("location_id") or ""),
            secondary_subject_ids=[str(x) for x in value.get("secondary_subject_ids") or []],
            endpoint_reason=str(value.get("endpoint_reason") or ""),
            presentation_mode=str(value.get("presentation_mode") or "mechanism"),
            opening_anchor_id=str(value.get("opening_anchor_id") or ""), payoff_reason=str(value.get("payoff_reason") or ""),
            contextual_anchor_id=str(value.get("contextual_anchor_id") or ""), contextual_anchor_subject_id=str(value.get("contextual_anchor_subject_id") or ""),
            contextual_anchor_kind=str(value.get("contextual_anchor_kind") or ""), mechanism_anchor_id=str(value.get("mechanism_anchor_id") or ""),
            contextual_anchor_roster_ids=[str(item) for item in value.get("contextual_anchor_roster_ids") or []],
            contextual_anchor_appearance_contract=str(value.get("contextual_anchor_appearance_contract") or ""),
            contextual_anchor_prompt_sha256=str(value.get("contextual_anchor_prompt_sha256") or ""),
            contextual_anchor_sheet_ids=[str(item) for item in value.get("contextual_anchor_sheet_ids") or []],
            coverage_beats=[dict(item) for item in value.get("coverage_beats") or [] if isinstance(item, dict)],
            impact_offset_seconds=float(value.get("impact_offset_seconds", 1.8)),
            prior_exit_states=_parse_prior_exit_states(value.get("prior_exit_states")),
            spatial_anchor=str(value.get("spatial_anchor") or ""),
            scale_level=str(value.get("scale_level") or ""),
            forbidden_entities=[
                str(x) for x in (
                    value.get("forbidden_entities")
                    or (value.get("state_tracking", {}) if isinstance(value.get("state_tracking"), dict) else {}).get("forbidden_entities")
                    or []
                )
            ],
        )


@dataclass
class Script:
    topic: str
    beats: list[Beat]
    shots: list[Shot]
    lang: str = "en"
    timeline: TimelinePlan | None = None
    mode: str = "anatomical"
    # These are locked after narration timing, before any paid keyframe request.
    # Keeping them on the script makes a resume a replay of the approved edit, not
    # a reinterpretation based on newer defaults.
    frame_plan: list[dict[str, Any]] = field(default_factory=list)
    editorial_plan: dict[str, Any] = field(default_factory=dict)
    youtube: dict[str, Any] | None = None

    @property
    def narration(self) -> str:
        return " ".join(beat.text.strip() for beat in self.beats if beat.text.strip())

    @property
    def word_count(self) -> int:
        return len(self.narration.split())

    def to_dict(self) -> dict[str, Any]:
        data = {"topic": self.topic, "lang": self.lang, "mode": self.mode, "beats": [asdict(item) for item in self.beats],
                "shots": [asdict(item) | {"end_target_quadrant": item.end_target_quadrant, "coverage_beats": item.resolved_coverage_beats} for item in self.shots],
                "timeline": self.timeline.to_dict() if self.timeline else None,
                "frame_plan": self.frame_plan, "editorial_plan": self.editorial_plan}
        if self.youtube:
            data["youtube"] = self.youtube
        return data

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Script":
        timeline_data = value.get("timeline")
        timeline = TimelinePlan.from_dict(timeline_data) if isinstance(timeline_data, dict) else None
        beats = [Beat(int(item.get("index", i + 1)), str(item.get("text") or ""), str(item.get("role") or "default"), list(item.get("emphasis") or [])) for i, item in enumerate(value.get("beats") or [])]
        return cls(str(value.get("topic") or "Untitled"), beats, [Shot.from_dict(item) for item in value.get("shots") or []], str(value.get("lang") or "en"), timeline,
                   mode=str(value.get("mode") or "anatomical"),
                   frame_plan=[dict(item) for item in value.get("frame_plan") or [] if isinstance(item, dict)],
                   editorial_plan=dict(value.get("editorial_plan") or {}),
                   youtube=value.get("youtube"))


def transition_boundary_kinds(shots: list[Shot]) -> list[str]:
    """Translate persisted storyboard transitions into editor's intentional two-state API."""
    return ["change" if (right.transition_kind in {"subject_change", "location_change"} or left.subject_id != right.subject_id) else "same" for left, right in zip(shots, shots[1:])]


def _required_beat_indices(block_count: int) -> list[int]:
    """Map every native block to its narrated causal step, aligned with BEAT_TEMPLATE shares."""
    if block_count == 8:
        return [1, 1, 2, 2, 3, 3, 4, 5]
    if block_count < 5:
        # Smoke plans still need an ordered progression without redefining the full-run map.
        return [min(5, 1 + ((index - 1) * 5) // max(1, block_count)) for index in range(1, block_count + 1)]
    # BEAT_TEMPLATE shares: hook=0.16, question=0.20, reveal=0.28, turn=0.20, payoff=0.16
    cum = [0.16, 0.36, 0.64, 0.84, 1.00]
    ends = [round(c * block_count) for c in cum]
    for b in range(4):
        ends[b] = max(b + 1, min(ends[b], block_count - (4 - b)))
    ends[4] = block_count
    for b in range(1, 5):
        if ends[b] <= ends[b - 1]:
            ends[b] = ends[b - 1] + 1
    # Ensure Beat 3 (reveal mechanism, 28% weight) gets at least 2 blocks for N >= 6
    if block_count >= 6 and ends[2] - ends[1] < 2:
        if ends[1] - ends[0] > 1:
            ends[1] -= 1
        elif ends[3] - ends[2] > 1:
            ends[2] += 1
    result: list[int] = []
    beat = 1
    for i in range(1, block_count + 1):
        while beat < 5 and i > ends[beat - 1]:
            beat += 1
        result.append(beat)
    return result


def _marker_instruction(shot: Shot) -> str:
    if shot.marker_type == "none":
        return "No baked arrow, trajectory, neon marker, decorative overlay, or HUD."
    if shot.marker_type == "arrow":
        marker_desc = (
            "solid 3D glowing volumetric arrows (solid 3D conical arrowheads with glowing cylindrical shafts, "
            "NOT flat hollow outline arrows), organically glowing luminescent energy stream showing directional flow, "
            "integrated naturally into the 3D scene lighting and fluid/tissue dynamics"
        )
    else:
        marker_desc = (
            "softly glowing red volumetric path trace embedded within the 3D scene "
            "geometry, following the physical motion path with subsurface light emission"
        )
    return (
        f"Bake only this authored proof marker: {marker_desc} visible in the "
        f"{shot.marker_quadrant} quadrant; keep it outside the lower-middle caption-safe zone. "
        "STRICTLY NO flat 2D clipart arrows, no hollow neon outline arrows, no graphic sticker overlays, no disconnected "
        "floating arrow shapes — the marker must appear as a natural volumetric element of "
        "the 3D-rendered scene with matching lighting and depth."
    )


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
    "driver": (
        "Driver: bare male forearms with warm natural skin tone, no sleeves, no jacket, no watch, "
        "plain white crew-neck t-shirt, blue denim jeans, warm tan/beige leather interior."
    ),
    "driver_occupant": (
        "Driver: bare male forearms with warm natural skin tone, no sleeves, no jacket, no watch, "
        "plain white crew-neck t-shirt, blue denim jeans, warm tan/beige leather interior."
    ),
}


def _role_decoupling_clause(shot: Shot, *, is_baseline: bool = False) -> str:
    """Generate explicit costume and role boundaries preventing diffusion model role swaps."""
    roles = [shot.subject_id] + list(shot.secondary_subject_ids or [])
    clauses: list[str] = []
    for sid in roles:
        s = sid.casefold()
        for role_key, role_spec in _INCIDENT_ROLE_COSTUMES.items():
            if role_key in s or s in role_key:
                spec = role_spec
                if is_baseline:
                    spec = re.sub(r"\s*In cockpit breach emergencies:.*?(?=\.|$)", "", spec, flags=re.I)
                    spec = re.sub(r",?\s*wearing emergency oxygen mask", "", spec, flags=re.I)
                    spec = re.sub(r",?\s*positioned lying flat/prone on cockpit floor.*?(?=\.|$)", "", spec, flags=re.I)
                clauses.append(f"[{sid}]: {spec.strip()}")
                break
    if clauses:
        return " [Role & Costume Decoupling Invariant]: Characters must never swap roles or garments: " + "; ".join(clauses) + "."
    return ""


def _spatial_vector_clause(shot: Shot, mode: ModeProfile = ANATOMICAL, *, is_baseline: bool = False) -> str:
    """Generate spatial topology and 180-degree axis lock to prevent flipped perspective in vehicle/cockpit scenes."""
    if mode.name != "incident":
        return ""
    is_cockpit_or_vehicle = any(kw in f"{shot.location_id} {shot.subject_id} {shot.subject_description} {shot.dominant_event}".casefold() for kw in ("cockpit", "aircraft", "airplane", "fuselage", "windscreen", "pilot", "flight deck"))
    is_submerged_car = any(kw in f"{shot.location_id} {shot.subject_id} {shot.subject_description} {shot.dominant_event}".casefold() for kw in ("car", "lake", "submerged", "sinking", "vehicle", "driver", "windshield", "door_handle", "seatbelt"))
    if not is_cockpit_or_vehicle and not is_submerged_car:
        return ""
    if is_submerged_car:
        if is_baseline:
            return (
                " [Spatial Vector & POV Lock]: First-person driver cockpit POV looking forward through windshield. "
                "Warm tan/beige leather steering wheel and dashboard console, bare driver forearms gripping wheel. "
                "Vehicle approaches calm lake on a sunny day, cabin fully dry, no self-harm or violent crash phrasing."
            )
        is_swim = any(kw in f"{shot.location_id} {shot.subject_id} {shot.subject_description} {shot.dominant_event}".casefold() for kw in ("swim", "surface", "egress", "escape"))
        is_cutaway = any(kw in f"{shot.location_id} {shot.subject_id} {shot.subject_description} {shot.dominant_event}".casefold() for kw in ("cutaway", "circuit", "gear", "motor", "waterlog", "switch", "wiring"))
        if is_swim:
            return (
                " [Spatial Vector & Underwater Swimming POV Lock]: First-person upward swimming POV looking directly up "
                "toward the bright shimmering sunlit lake water surface. Two bare male arms performing breaststroke motions. "
                "Stream of rising translucent air bubbles, dark deep blue lake below, brilliant glowing teal rays from above."
            )
        if is_cutaway:
            return (
                " [Spatial Vector & Mechanical Cutaway Lock]: Macro technical circular cutaway section inside car door trim. "
                "Bright yellow circular power window motor and green PCB circuit board flooded with cascading murky lake water. "
                "Top edge shows driver's bare finger pressing the matte-black power window toggle switch."
            )
        return (
            " [Spatial Vector & Underwater POV Lock]: First-person driver POV inside sealed car cabin. "
            "Dim cool-blue underwater interior ambient lighting and dark blue lake water outside the side window. "
            "Sealed-cabin physics: interior cabin remains completely dry, exterior water pressure pins door shut. "
            "No faces or heads reflected in the glass, no chin or neck intrusion at bottom edge."
        )
    if is_baseline:
        return (
            " [Spatial Vector & 180-Degree Axis Lock]: Camera must respect the 180-degree axis: "
            "port-side (left) pilot seat on the left, starboard (right) copilot seat on the right. "
            "Forward windscreen intact, fully sealed, and undamaged. NEVER mirror or flip left/right seating positions."
        )
    return (
        " [Spatial Vector & 180-Degree Axis Lock]: Camera must respect the 180-degree axis. "
        "The aircraft breach is strictly port-side (left) forward cockpit windscreen, and any ejected crew or airflow vector "
        "is outward toward the left exterior fuselage. The captain remains pinned on the PORT (left) exterior fuselage "
        "throughout all middle shots. NEVER mirror, flip, or render the breach on the starboard (right) side."
    )


def _environment_clause(shot: Shot, lighting: str, mode: ModeProfile = ANATOMICAL) -> str:
    """Build the environment clause for keyframe/motion prompts."""
    is_longform = mode.name == "explorer" or ((getattr(config, "LONGFORM_MODE", False) or getattr(config, "IS_EXPLORER_FORMAT", False)) and mode.name not in {"anatomical", "incident", "mechanical"})
    if is_longform:
        location_desc = (shot.location_id or "contextual environment matching the scene").replace("_", " ")
        return f"Background: {location_desc}, authentic cinematic photorealistic documentary environment with natural atmospheric depth. Lighting: {lighting}."
    if mode.environment_style == "void":
        return f"Background: deep dark neutral 3D studio void; no room, hospital, street, wall, sky, or landscape. Lighting: {lighting}."
    location_desc = (shot.location_id or "contextual environment matching the scene").replace("_", " ")
    return f"Background: {location_desc}, rendered in glossy stylized 3D with dramatic studio-quality lighting. Lighting: {lighting}."


def _incident_scale_reference_clause(shot: Shot, mode: ModeProfile = ANATOMICAL) -> str:
    """Ensure incident-mode macro/close mechanical/environmental shots carry an in-frame scale anchor."""
    if (
        mode.name != "incident"
        or shot.scale not in {"macro", "close"}
        or shot.normalized_domain not in {"mechanical", "environmental"}
    ):
        return ""
    fields_text = f"{shot.start_image_prompt} {shot.end_image_prompt} {shot.motion_prompt} {shot.detail_target} {shot.proof_on_screen} {shot.subject_description}".casefold()
    has_scale = bool(re.search(r"\b(?:gloved\s+hand|human\s+hand|hand|finger|fingers|tool|wrench|screwdriver|ruler|caliper|dimension|scale\s+reference|millimeter|mm|cm|inches?)\b", fields_text))
    if has_scale:
        return ""
    return " Scale reference: a visible gloved hand or common reference tool adjacent to the structure establishes precise real-world physical scale."


def _resolve_damage_clause(shot: Shot, prior_shots: list[Shot] | None = None, mode: ModeProfile = ANATOMICAL) -> str:
    """Append accumulated trauma/exposure appearance modifier to resolution shots derived from exit_state history."""
    if shot.journey_phase != "resolve":
        return ""
    history: list[str] = []
    if prior_shots:
        all_subjects = {shot.subject_id} | set(shot.secondary_subject_ids or [])
        for ps in prior_shots:
            ps_subjects = {ps.subject_id} | set(ps.secondary_subject_ids or [])
            if (all_subjects & ps_subjects) and ps.exit_state:
                history.append(ps.exit_state)
            elif ps.exit_state:
                history.append(ps.exit_state)
    elif shot.prior_exit_states:
        all_subjects = {shot.subject_id} | set(shot.secondary_subject_ids or [])
        for item in shot.prior_exit_states:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                item_subjects, exit_state = item
                item_subj_set = set(item_subjects) if isinstance(item_subjects, (list, tuple, set)) else {str(item_subjects)}
                if (all_subjects & item_subj_set) and exit_state:
                    history.append(str(exit_state))
            elif isinstance(item, dict):
                item_subjects = item.get("subjects") or item.get("subject_ids") or []
                item_subj_set = set(item_subjects) if isinstance(item_subjects, (list, tuple, set)) else {str(item_subjects)}
                exit_state = item.get("exit_state", "")
                if (all_subjects & item_subj_set) and exit_state:
                    history.append(str(exit_state))
            elif isinstance(item, str):
                history.append(item)

    if not history:
        return ""

    history_text = " ".join(history).casefold()
    modifiers: list[str] = []

    # Cold / freezing / wind trauma
    if any(k in history_text for k in ("cold", "freeze", "freezing", "frost", "sub-zero", "hypothermia", "wind", "slipstream", "chill")):
        modifiers.extend(["windswept disheveled hair", "frost-marked face"])

    # Decompression / impact / ejection trauma
    if any(k in history_text for k in ("decompression", "impact", "pinned", "sucked out", "blowout", "crush", "bruis", "abrasion", "collision", "blast")):
        modifiers.append("uniform in disarray")

    # Physical struggle / restraint strain
    if any(k in history_text for k in ("struggle", "restraint", "tackle", "hold", "grip", "resist", "exhaustion", "strain", "fatigue")):
        modifiers.append("signs of physical exhaustion and strain")

    if not modifiers:
        return ""

    unique_modifiers = list(dict.fromkeys(modifiers))
    return f" Accumulated physical trauma: {', '.join(unique_modifiers)} reflecting earlier physical exposure and struggle."


def _is_exterior_shot(shot: Shot) -> bool:
    """Detect if a shot depicts an exterior perspective (e.g. aircraft exterior, slipstream, airframe)."""
    scale_lvl = (getattr(shot, "scale_level", "") or "").upper()
    spatial_anc = (getattr(shot, "spatial_anchor", "") or "").upper()
    if scale_lvl in {"EXTERIOR", "AIRFRAME", "EXTERIOR_AIRFRAME", "AIRCRAFT_EXTERIOR", "MACRO_ORGAN"}:
        return True
    if spatial_anc in {"EXTERIOR", "AIRFRAME", "EXTERIOR_AIRFRAME", "AIRCRAFT_EXTERIOR", "MACRO_ORGAN"}:
        return True
    fields_to_check = (
        getattr(shot, "subject_id", ""),
        getattr(shot, "subject_description", ""),
        getattr(shot, "entry_state", ""),
        getattr(shot, "exit_state", ""),
        getattr(shot, "start_image_prompt", ""),
        getattr(shot, "end_image_prompt", ""),
        getattr(shot, "motion_prompt", ""),
        getattr(shot, "dominant_event", ""),
        getattr(shot, "location_id", ""),
    )
    combined = " ".join(str(f) for f in fields_to_check).lower()
    return bool(re.search(
        r"\b(?:exterior|airframe|outside\s+fuselage|outside\s+cabin|sucked\s+out|blown\s+through|"
        r"windscreen\s+exterior|slipstream|exterior\s+slipstream|pinned\s+against\s+outer|"
        r"pinned\s+to\s+outer|outer\s+cockpit\s+window|exterior\s+cockpit\s+window|"
        r"captain_exterior_pinned|captain_pinned_exterior|aircraft_exterior)\b",
        combined,
        re.I,
    ))


def _vacancy_guarantee_clause(shot: Shot) -> str:
    """Inject positive vacancy guarantee when forbidden entities or exterior state require it."""
    forbidden = [str(x).lower() for x in (getattr(shot, "forbidden_entities", []) or [])]
    is_ext = _is_exterior_shot(shot)
    is_cockpit_incident = any(
        "cockpit" in f or "pilot" in f or "captain" in f for f in forbidden
    ) or any(
        kw in str(getattr(shot, field_name, "")).lower()
        for field_name in ("subject_id", "location_id", "dominant_event")
        for kw in ("pilot", "captain", "cockpit")
    )
    if is_ext or any("inside" in f or "seat" in f or "seated" in f for f in forbidden):
        if is_cockpit_incident:
            return " The interior pilot seat is entirely empty and vacant."
    return ""


def compile_negative_prompt(shot: Shot, mode: ModeProfile = ANATOMICAL) -> str:
    """Compile deterministic negative constraints from forbidden entities and domain rules."""
    negatives: list[str] = []
    for entity in (getattr(shot, "forbidden_entities", []) or []):
        e = str(entity).strip()
        if e and e not in negatives:
            negatives.append(e)

    if _is_exterior_shot(shot):
        ext_forbids = [
            "cockpit interior",
            "cabin seating",
            "flight deck controls",
            "enclosed cockpit",
            "dashboard console",
            "pilot sitting in chair",
            "pilot seated inside",
            "captain inside cockpit",
        ]
        for item in ext_forbids:
            if item not in negatives:
                negatives.append(item)

    is_submerged_or_car = any(
        kw in f"{shot.location_id} {shot.subject_id} {shot.subject_description} {shot.dominant_event}".casefold()
        for kw in ("car", "lake", "submerged", "sinking", "vehicle", "driver", "windshield")
    )
    if is_submerged_or_car:
        car_forbids = [
            "faces or heads reflected in the glass",
            "face reflections",
            "chin or neck intrusion at bottom edge",
            "dry street or parking lot outside submerged glass",
            "flat hollow outline arrows",
            "flat 2D clipart stickers",
        ]
        for item in car_forbids:
            if item not in negatives:
                negatives.append(item)

    universal_forbids = [
        "text", "letters", "numbers", "captions", "subtitles", "labels",
        "split-screen", "multi-panel", "watermark", "logo", "photograph", "live action",
    ]
    for item in universal_forbids:
        if item not in negatives:
            negatives.append(item)

    return ", ".join(negatives)


def compile_image_prompt(shot: Shot, endpoint: str = "start", mode: ModeProfile = ANATOMICAL, *, prior_shots: list[Shot] | None = None) -> str:
    """Compile the image prompt for a keyframe endpoint (alias for compile_keyframe_prompt)."""
    return compile_keyframe_prompt(shot, endpoint, mode=mode, prior_shots=prior_shots)


def compile_motion_prompt(shot: Shot, mode: ModeProfile = ANATOMICAL, *, prior_shots: list[Shot] | None = None, **kw: Any) -> str:
    """Compile the motion prompt for a shot."""
    return optimize_for_flow(shot, mode=mode, prior_shots=prior_shots, **kw)["video_prompt"]


def compile_keyframe_prompt(shot: Shot, endpoint: str, mode: ModeProfile = ANATOMICAL, *, prior_shots: list[Shot] | None = None) -> str:
    raw = _canonicalize_model_brief(shot.start_image_prompt if endpoint == "start" else shot.end_image_prompt, mode=mode)
    is_longform = mode.name == "explorer" or ((getattr(config, "LONGFORM_MODE", False) or getattr(config, "IS_EXPLORER_FORMAT", False)) and mode.name not in {"anatomical", "incident", "mechanical"})
    state = shot.entry_state if endpoint == "start" else shot.exit_state
    optics = _SCALE_OPTICS.get(shot.scale, _SCALE_OPTICS["close"])
    lighting = _LIGHTING_MATRIX.get(shot.scale, _LIGHTING_MATRIX["close"])
    if is_longform:
        lighting = "period-accurate natural light and weather matching the authored scene"
    if mode.environment_style != "void":
        lighting = lighting.replace("separating subject from void", "separating subject from background")
    if shot.journey_phase == "explore" and shot.normalized_domain == "mechanical":
        lighting = f"{lighting}, high-contrast studio rim light, tactile macro surface reflections"

    # Domain-tailored shader and render fidelity for Blender Cycles & Octane aesthetic
    raw_desc = f"{shot.detail_target or ''} {shot.subject_description or ''} {shot.start_image_prompt or ''}".lower()
    if any(w in raw_desc for w in ("polymer", "plastic", "polyethylene", "hdpe", "bottle", "tube", "acrylic")):
        domain_shaders = "translucent high-density polyethylene, smooth specular roughness 0.15, subsurface light bleed, ray-traced ambient bounce"
    elif any(w in raw_desc for w in ("rubber", "elastomer", "tire", "hose", "gasket", "seal", "tread")):
        domain_shaders = "matte vulcanized elastomer, micro-porous surface friction, dynamic elongation strain, tactile PBR contact shadows"
    elif any(w in raw_desc for w in ("glass", "ice", "frost", "lens", "crystal", "cornea", "window")):
        domain_shaders = "optical refractive dispersion, Abbe number 55, Fresnel reflectance, internal stress birefringence, crisp specular caustics"
    elif any(w in raw_desc for w in ("bone", "cartilage", "teeth", "tooth", "enamel", "dentin", "skull", "skeleton")):
        domain_shaders = "mineralized cortical bone texture, ivory enamel micro-structure, high specular hardness, subtle subsurface amber glow, PBR micro-grooves"
    elif any(w in raw_desc for w in ("fluid", "mucus", "saliva", "liquid", "surfactant", "droplet", "bile")):
        domain_shaders = "viscous non-Newtonian fluid dynamics, ray-traced liquid surface tension, refractive index 1.33, internal suspended micro-particulates, specular wet gloss"
    elif shot.normalized_domain in {"anatomical", "biological"}:
        domain_shaders = "ray-traced subsurface scattering (SSS radius 1.2, deep amber-red scattering), transillumination, optical tissue translucency, specular wet sheen, refractive index 1.33, cellular microgeometry"
    elif shot.normalized_domain in {"mechanical", "incident"}:
        domain_shaders = "brushed anisotropic metallic sheen, photoelastic stress concentration fringes, micro-fissure propagation under load, high-speed macro optics capture aesthetic, tactile PBR contact shadows"
    else:
        domain_shaders = "premium PBR materials, natural anatomical proportions, soft skin subsurface scattering (SSS), refined textural microgeometry"
    secondary_clause = (
        f" Secondary subjects present: {', '.join(sid.replace('_', ' ') for sid in shot.secondary_subject_ids)} (spatially distinct from primary subject, positioned at scene periphery/aisle)."
        if shot.secondary_subject_ids else ""
    )

    is_char = _is_human_subject({
        "subject_id": shot.subject_id, "subject_description": shot.subject_description,
        "start_image_prompt": shot.start_image_prompt, "end_image_prompt": shot.end_image_prompt,
    }) and not (shot.scale in {"macro", "micro", "nano"} and mode.name != "incident")

    if is_char:
        char_trait = "expressive smooth character design, natural anatomical proportions, "
        render_entity_type = "Glossy Stylized 3D Mannequin / Character Animation Render" if mode.character_style == "mannequin" else "Glossy Stylized 3D Character Animation Render"
    elif mode.name == "incident":
        char_trait = "3D cinematic incident and physical reconstruction visualization, "
        render_entity_type = "Glossy Stylized 3D Incident Reconstruction Render"
    elif mode.name == "mechanical":
        char_trait = "3D engineering and technical cutaway visualization, "
        render_entity_type = "Glossy Stylized 3D Engineering and Technical Cutaway Visualization Render"
    else:
        char_trait = "3D medical and scientific cutaway visualization, "
        render_entity_type = "Glossy Stylized 3D Medical and Scientific Cutaway Visualization Render"

    if is_longform:
        lighting_style = "period-accurate natural light and weather, photorealistic historical documentary lighting"
    elif mode.environment_style == "void":
        lighting_style = "minimalist dark studio void lighting"
    else:
        lighting_style = "dramatic 3D cinematic environment lighting"

    scale_transition_clause = ""
    if shot.transition_kind == "scale_transition":
        scale_transition_clause = (
            f" Scale transition: maintain exact subject identity and materials at {shot.scale} magnification; "
            "seamless perspective continuity with no perspective break or domain jump."
        )

    if endpoint == "start":
        proof_injection = (
            f"[Deterministic Proof Evidence]: Required visible physical proof: '{shot.proof_on_screen}' baseline setup. "
            f"The 3D render MUST explicitly model the intact baseline state '{state}' with all structural components stable and undamaged prior to incident. "
            f"Required endpoint state: '{state}'."
        )
    else:
        proof_injection = (
            f"[Deterministic Proof Evidence]: Required visible physical proof: '{shot.proof_on_screen}'. "
            f"The 3D render MUST explicitly model and visibly depict all physical objects, structural components, "
            f"or mechanical evidence specified here in clear, unambiguous 3D geometry without omission. "
            f"Required endpoint state: '{state}'."
        )
    is_baseline = (endpoint == "start" and any(w in state.casefold() for w in ("normal", "cruise", "intact", "baseline", "before", "seated_normal_cruise")))
    spatial_axis_clause = _spatial_vector_clause(shot, mode, is_baseline=is_baseline)
    role_decouple = _role_decoupling_clause(shot, is_baseline=is_baseline)
    scale_anchor = _incident_scale_reference_clause(shot, mode)
    damage_clause = _resolve_damage_clause(shot, prior_shots=prior_shots, mode=mode)

    preserved_items = list(shot.quality_critical)
    if endpoint == "start":
        preserved_items = [
            item for item in preserved_items
            if not re.search(r"\b(?:breach|rupture|damage|sever|fracture|blowout|fail|broken|shatter|detache?d?)\b", item.replace("_", " "), re.I)
        ]

    if is_longform:
        subj_id_low = (shot.subject_id or "").casefold()
        is_broll_shot = subj_id_low.startswith("broll")
        is_witness_shot = not is_broll_shot and (
            any(k in subj_id_low for k in ("witness", "interview", "historian", "chronicler", "architect", "builder", "carver", "elder"))
            or "historical eyewitness interview" in raw.casefold()
        )
        is_nova_host = not is_broll_shot and not is_witness_shot and (
            is_char or any(k in subj_id_low for k in ("nova", "host"))
        )
        longform_proof = (
            f"[Deterministic Proof Evidence]: Required visible physical proof: '{shot.proof_on_screen}'. "
            f"The photorealistic documentary frame MUST explicitly depict '{state}' and all specified architectural or historical evidence clearly."
        )
        if is_nova_host:
            from services.character import get_active_character, detect_era
            char = get_active_character()
            detected_era = detect_era(f"{shot.subject_description} {shot.detail_target} {shot.dominant_event} {shot.location_id}")
            char_anchor = char.anchor_description(era=detected_era)
            style_part = (
                f"[Style & Render]: Photorealistic 8k cinematic documentary frame, National Geographic and BBC Earth 35mm film aesthetic, "
                f"[SOLO TIME-TRAVELER HOST A-ROLL]: {char_anchor}, natural skin texture, visible fine skin pores, subtle faint freckles, realistic hair strands, "
                f"natural fabric drape and physics, authentic atmospheric volumetric lighting, 16:9 widescreen composition. "
                "Complete head, hair, and shoulders framed comfortably inside frame with generous headroom above crown of head (NEVER crop forehead or top of head). "
                "ZERO plastic sheen, ZERO 3D mannequin look, ZERO CGI cartoon distortion. Absolutely no amateur vlog graphics or fake HUD."
            )
            speech_directive = "Closed or neutral mouth; the host never speaks or lip-syncs, with narration delivered as voiceover."
        elif is_witness_shot:
            style_part = (
                f"[Style & Render]: Photorealistic 8k cinematic documentary frame, National Geographic and BBC Earth 35mm film aesthetic, "
                f"[HISTORICAL EYEWITNESS INTERVIEW]: {shot.subject_description}, authentic period-accurate historical figure and attire, "
                "weathered natural skin texture, expressive eyes, complete head and shoulders framed with generous headroom (NEVER crop forehead or top of head), "
                f"authentic atmospheric volumetric lighting, 16:9 widescreen composition, {lighting_style}. "
                "NO modern safari hats, NO modern clothing, ZERO plastic sheen, ZERO 3D mannequin look."
            )
            speech_directive = "Closed or neutral mouth; the historical figure does not speak or lip-sync, with narration delivered as voiceover."
        else:
            style_part = (
                f"[Style & Render]: Photorealistic 8k cinematic documentary B-roll frame, National Geographic and BBC Earth 35mm film aesthetic, "
                f"anamorphic lens optics, authentic atmospheric volumetric lighting, hyper-detailed textures, authentic historical weathering, "
                f"natural dust motes, 16:9 widescreen composition, {lighting_style}. "
                "Include historically appropriate people only when the authored scene calls for them; no modern visitors or archaeologists. "
                "ZERO CGI plastic sheen, ZERO 3D mannequin look, ZERO artificial graphics."
            )
            has_authored_people = bool(re.search(
                r"\b(sailors?|seamen|crewmen|crew|gunners?|soldiers?|troops?|rowers?|workers?|men|women)\b",
                shot.dominant_event or "",
                re.I,
            ))
            speech_directive = (
                "Mandatory authored human subjects: clearly show the named crew or workers performing the specific action in the foreground or middle distance; "
                "use force- and role-accurate 1915 clothing and equipment, never generic ancient costume; do not omit them."
                if has_authored_people
                else "Historically grounded environment; show people only when the authored scene specifies them, in period-correct clothing and purposeful action."
            )
        framing_part = (
            f"[Framing & Subject]: Horizontal 16:9 widescreen composition, {shot.camera_angle or 'eye-level cinematic framing'}, "
            f"{shot.subject_description or shot.subject_id}.{secondary_clause} Domain: {shot.normalized_domain}; scale: {shot.scale}. "
            f"Optics: {optics}. Strictly level landscape horizon.{scale_transition_clause}{spatial_axis_clause}{role_decouple}{scale_anchor}"
        )
        state_part = (
            f"[State & Anchor]: Endpoint state: {state}. Continuity anchor: {shot.continuity_anchor or shot.subject_id}. "
            f"Detail target: {shot.detail_target or 'physically accurate authentic historical and archaeological structure'}; "
            f"preserve: {', '.join(preserved_items) or 'connected geometry and authentic architecture'}. {longform_proof}{damage_clause}"
        )
        env_part = f"[Environment & Lighting]: {_environment_clause(shot, lighting, mode)}"
        directives_part = (
            f"[Directives]: {_marker_instruction(shot)} Important proof in {shot.push_quadrant} when applicable. "
            f"Reserve the lower-third caption safe zone. {raw} Single continuous cinematic widescreen scene only, no split-screen, no side-by-side panels. "
            f"{_LONGFORM_TEXT_SHIELD} {speech_directive} No dialogue subtitles, text overlays, channel watermark, UI, or HUD."
        )
        parts = (style_part, framing_part, state_part, env_part, directives_part)
    else:
        parts = (
            f"[Style & Render]: A clean, high-end 3D animated cinematic frame, {lighting_style}, {char_trait}dramatic side-shadows, 9:16 vertical aspect ratio, vivid colors, hyper-detailed textures, matching the style of modern educational mystery shorts, Blender Cycles and Octane Render aesthetic, {render_entity_type}, {domain_shaders}. Absolutely no live-action photograph or video footage.",
            f"[Framing & Subject]: Vertical 9:16 composition, {shot.camera_angle or 'eye-level cinematic framing'}, {shot.subject_description or shot.subject_id}.{secondary_clause} Domain: {shot.normalized_domain}; scale: {shot.scale}. Optics: {optics}. Strictly upright vertical 9:16 orientation with level horizon: floor/ground at bottom, ceiling/sky at top; never rotate sideways 90 degrees.{scale_transition_clause}{spatial_axis_clause}{role_decouple}{scale_anchor}",
            f"[State & Anchor]: Endpoint state: {state}. Continuity anchor: {shot.continuity_anchor or shot.subject_id}. Detail target: {shot.detail_target or 'physically accurate material and structure'}; preserve: {', '.join(preserved_items) or 'connected geometry and stable attachments'}. {proof_injection}{damage_clause}",
            f"[Environment & Lighting]: {_environment_clause(shot, lighting, mode)}",
            f"[Directives]: {_marker_instruction(shot)} Important proof in {shot.push_quadrant} when applicable. Reserve the lower-middle caption-safe zone. {raw} Single continuous 3D scene only, no split-screen, no side-by-side panels. {_ANTI_TEXT_SHIELD} Characters have closed or neutral mouths. No dialogue, lip-sync, text, generated captions, logos, watermark, UI, or HUD. Instead of any burst or spark, plain physical structural failure only; no light flash, debris shower, or pyrotechnics.",
        )
    prompt = " ".join(part for part in parts if part)
    if _is_exterior_shot(shot):
        prompt = _INTERIOR_CLEANSE_RE.sub("", prompt)
        vacancy = _vacancy_guarantee_clause(shot)
        prompt = f"{_CAMERA_VIEWPOINT_MANDATE} {prompt}{vacancy}"
    if endpoint == "start":
        prompt = re.sub(
            r"\b(?:drives?\s+off\s+(?:the\s+)?(?:shoreline|road|cliff)\s+(?:straight\s+)?into\s+a\s+lake|crashes?\s+into\s+a\s+lake|suicidal\s+drive)\b",
            "driving forward on an asphalt road toward a calm blue lake on a clear sunny day",
            prompt,
            flags=re.I,
        )
    return prompt


def _environment_motion_clause(shot: Shot, mode: ModeProfile = ANATOMICAL, *, scale: str = "") -> str:
    """Build the environment clause for motion prompts."""
    is_longform = mode.name == "explorer" or ((getattr(config, "LONGFORM_MODE", False) or getattr(config, "IS_EXPLORER_FORMAT", False)) and mode.name not in {"anatomical", "incident", "mechanical"})
    if is_longform:
        location_desc = (shot.location_id or "scene-appropriate setting").replace("_", " ")
        scale_suffix = f", scale {scale}" if scale else ""
        return f"Contextual environment: {location_desc}{scale_suffix}, photorealistic 35mm cinematic documentary setting."
    if mode.environment_style == "void":
        scale_suffix = f", scale {scale}" if scale else ""
        return f"Deep dark neutral 3D studio void{' background' if not scale else ''}{scale_suffix}."
    location_desc = (shot.location_id or "scene-appropriate setting").replace("_", " ")
    scale_suffix = f", scale {scale}" if scale else ""
    return f"Contextual environment: {location_desc}{scale_suffix}, rendered in glossy stylized 3D."


def optimize_for_flow(shot: Shot, mode: ModeProfile = ANATOMICAL, *, prior_shots: list[Shot] | None = None, **kw: Any) -> dict[str, str]:
    """Compile matching canonical keyframes and a provider-appropriate motion instruction."""
    is_longform = mode.name == "explorer" or ((getattr(config, "LONGFORM_MODE", False) or getattr(config, "IS_EXPLORER_FORMAT", False)) and mode.name not in {"anatomical", "incident", "mechanical"})
    phase = _PHASE_DIRECTION.get(shot.journey_phase, _PHASE_DIRECTION["explore"])
    framing = _PHASE_FRAMING.get(shot.journey_phase, _PHASE_FRAMING["explore"])
    physics_verbs = (
        "natural continuous physical action, authentic fabric and water motion, environmental movement grounded in the shot"
        if is_longform
        else _DOMAIN_PHYSICS_VERBS.get(shot.normalized_domain, _DOMAIN_PHYSICS_VERBS["anatomical"])
    )
    if is_longform and re.search(
        r"\b(sailors?|seamen|crewmen|crew|gunners?|soldiers?|troops?|rowers?|workers?|men|women)\b",
        shot.dominant_event or "",
        re.I,
    ):
        physics_verbs += (
            ", named people remain clearly visible throughout, actively completing the authored hand and body actions; "
            "do not replace them with an empty landscape, ship-only, or object-only view"
        )
    audio_cue = (
        "ambient historical courtyard air and natural documentary room tone"
        if is_longform
        else _DOMAIN_AUDIO_CUES.get(shot.normalized_domain, _DOMAIN_AUDIO_CUES["anatomical"])
    )
    raw_motion = _canonicalize_model_brief(shot.motion_prompt, mode=mode)
    text_shield = _LONGFORM_TEXT_SHIELD if is_longform else _ANTI_TEXT_SHIELD
    spatial_clause = _spatial_vector_clause(shot, mode)
    role_clause = _role_decoupling_clause(shot)
    scale_anchor = _incident_scale_reference_clause(shot, mode)
    damage_clause = _resolve_damage_clause(shot, prior_shots=prior_shots, mode=mode)
    secondary_clause = (
        f" Secondary subjects present: {', '.join(sid.replace('_', ' ') for sid in shot.secondary_subject_ids)} (spatially distinct from primary subject, positioned at scene periphery/aisle)."
        if shot.secondary_subject_ids else ""
    )

    # Detect Push-Through (dıştan içe dalış) vs Pull-Back Reveal (içten dışa çıkış)
    is_push_through = (
        shot.transition_kind == "scale_transition"
        and (shot.journey_phase == "descend" or shot.scale in {"macro", "micro", "nano"} or bool(re.search(r"\b(?:push|penetrat|inward|oral|mouth|lip|tissue|dive)\b", f"{shot.motion_prompt} {shot.dominant_event}", re.I)))
    )
    is_pull_out = (
        (shot.presentation_mode in {"return_to_contextual_anchor_payoff", "return_to_opening_anchor_payoff"} and shot.endpoint_mode == "first_last")
        or (shot.transition_kind == "scale_transition" and shot.journey_phase in {"reveal", "resolve"} and bool(re.search(r"\b(?:pull|reveal|retreat|zoom\s*out|outward|forehead|face|head|human)\b", f"{shot.motion_prompt} {shot.dominant_event}", re.I)))
    )

    if is_push_through:
        target_struct = shot.detail_target or shot.continuity_anchor or ("internal technical cross-section" if (mode.name == "mechanical" or shot.normalized_domain in {"mechanical", "physics", "engineering"}) else "internal anatomical cross-section")
        raw_text = f"{shot.motion_prompt} {shot.dominant_event}".lower()
        if mode.name == "mechanical" or shot.normalized_domain in {"mechanical", "physics", "engineering"}:
            axis_desc = "along the mechanical drive axis to reveal the 3D internal components"
            boundary_desc = "outer chassis, effortlessly penetrating the protective casing"
            interpolation_desc = "Storyboard interpolation from external machine assembly to internal technical cross-section."
            lighting_motion = f"{_environment_motion_clause(shot, mode)} 5600K directional key shifting into high-contrast macro mechanical lighting with sharp cyan rim light."
            audio_motion = audio_cue or "subtle tactile mechanical hum, metal strain, sterile room tone"
        elif any(w in raw_text for w in ("oral", "mouth", "lip", "teeth", "tongue", "palate")):
            axis_desc = "along the oral axis to reveal the 3D internal palate"
            boundary_desc = "sealed lips, effortlessly penetrating the tissue boundary"
            interpolation_desc = "Storyboard interpolation from external subject to internal anatomical cross-section."
            lighting_motion = f"{_environment_motion_clause(shot, mode)} 5600K key shifting into transilluminated macro tissue lighting with sharp cyan rim light."
            audio_motion = audio_cue or "subtle visceral fluid flow, sterile room tone"
        elif any(w in raw_text for w in ("ocular", "eye", "pupil", "cornea", "retina", "vision")):
            axis_desc = "along the optical visual axis to reveal the 3D retinal layers"
            boundary_desc = "pupil aperture, effortlessly penetrating the corneal boundary"
            interpolation_desc = "Storyboard interpolation from external subject to internal anatomical cross-section."
            lighting_motion = f"{_environment_motion_clause(shot, mode)} 5600K key shifting into transilluminated macro tissue lighting with sharp cyan rim light."
            audio_motion = audio_cue or "subtle visceral fluid flow, sterile room tone"
        elif any(w in raw_text for w in ("vascular", "vein", "artery", "vessel", "capillary")):
            axis_desc = "along the intravascular lumen axis to reveal the 3D vascular endothelium"
            boundary_desc = "vessel wall, effortlessly penetrating the endothelial boundary"
            interpolation_desc = "Storyboard interpolation from external subject to internal anatomical cross-section."
            lighting_motion = f"{_environment_motion_clause(shot, mode)} 5600K key shifting into transilluminated macro tissue lighting with sharp cyan rim light."
            audio_motion = audio_cue or "subtle visceral fluid flow, sterile room tone"
        elif any(w in raw_text for w in ("skin", "pore", "dermis", "epiderm", "follicle")):
            axis_desc = "along the transdermal depth axis to reveal the 3D subcutaneous tissue"
            boundary_desc = "stratum corneum, effortlessly penetrating the dermal boundary"
            interpolation_desc = "Storyboard interpolation from external subject to internal anatomical cross-section."
            lighting_motion = f"{_environment_motion_clause(shot, mode)} 5600K key shifting into transilluminated macro tissue lighting with sharp cyan rim light."
            audio_motion = audio_cue or "subtle visceral fluid flow, sterile room tone"
        elif any(w in raw_text for w in ("stomach", "gut", "intestin", "digest", "gastric", "esophag")):
            axis_desc = "along the gastrointestinal tract to reveal the 3D mucosal lining"
            boundary_desc = "digestive lumen, effortlessly penetrating the mucosal boundary"
            interpolation_desc = "Storyboard interpolation from external subject to internal anatomical cross-section."
            lighting_motion = f"{_environment_motion_clause(shot, mode)} 5600K key shifting into transilluminated macro tissue lighting with sharp cyan rim light."
            audio_motion = audio_cue or "subtle visceral fluid flow, sterile room tone"
        elif any(w in raw_text for w in ("chest", "lung", "alveoli", "trachea", "bronch", "breath")):
            axis_desc = "along the optical penetration axis to reveal the 3D respiratory tract"
            boundary_desc = "chest wall, effortlessly penetrating the tissue boundary"
            interpolation_desc = "Storyboard interpolation from external subject to internal anatomical cross-section."
            lighting_motion = f"{_environment_motion_clause(shot, mode)} 5600K key shifting into transilluminated macro tissue lighting with sharp cyan rim light."
            audio_motion = audio_cue or "subtle visceral fluid flow, sterile room tone"
        elif any(w in raw_text for w in ("ear", "canal", "drum", "hearing")):
            axis_desc = "along the optical penetration axis to reveal the 3D tympanic canal"
            boundary_desc = "auditory boundary, effortlessly penetrating the tissue boundary"
            interpolation_desc = "Storyboard interpolation from external subject to internal anatomical cross-section."
            lighting_motion = f"{_environment_motion_clause(shot, mode)} 5600K key shifting into transilluminated macro tissue lighting with sharp cyan rim light."
            audio_motion = audio_cue or "subtle visceral fluid flow, sterile room tone"
        else:
            axis_desc = f"along the optical penetration axis to reveal the 3D {target_struct}"
            boundary_desc = "entry boundary, effortlessly penetrating the tissue boundary"
            interpolation_desc = "Storyboard interpolation from external subject to internal anatomical cross-section."
            lighting_motion = f"{_environment_motion_clause(shot, mode)} 5600K key shifting into transilluminated macro tissue lighting with sharp cyan rim light."
            audio_motion = audio_cue or "subtle visceral fluid flow, sterile room tone"

        if is_longform:
            lighting_motion = f"{_environment_motion_clause(shot, mode)} Period-accurate natural light and weather matching the scene."
            parts = (
                f"[Scene & Motion]: One continuous {shot.duration:.1f}-second cinematic macro push-in. Horizontal 16:9 widescreen framing. Camera accelerates smoothly toward {shot.detail_target or shot.subject_id}, {boundary_desc} {axis_desc}. Zero jump cuts, no flashing.",
                f"[Subject & Physics]: Maintain continuity anchor {shot.continuity_anchor or shot.subject_id}.{secondary_clause} Transition from {shot.entry_state} to {shot.exit_state}. Animate only diegetic scene physics: {physics_verbs}. Proof: {shot.proof_on_screen}.{scale_anchor}{damage_clause}",
                f"[Lighting & Environment]: {lighting_motion}",
                f"[Style]: Photorealistic National Geographic / BBC Earth documentary cinematography, natural 35mm motion physics.",
                f"[Directives]: {_marker_instruction(shot)} Reserve lower-third caption space. {raw_motion}{spatial_clause}{role_clause} {text_shield} Closed or neutral mouths, no dialogue or lip-sync; narration is voiceover. No text, subtitles, logos, watermark, UI, or HUD.",
            )
        else:
            parts = (
                f"[Scene & Motion]: One continuous 4.0-second rapid macro push-in. Vertical 9:16 framing. Camera accelerates smoothly toward the subject, {boundary_desc} {axis_desc}. {interpolation_desc} Zero jump cuts, no flashing.",
                f"[Subject & Physics]: Maintain continuity anchor {shot.continuity_anchor or shot.subject_id}.{secondary_clause} Transition from {shot.entry_state} to {shot.exit_state}. Animate only diegetic scene physics: {physics_verbs}. Proof: {shot.proof_on_screen}.{scale_anchor}{damage_clause}",
                f"[Lighting & Environment]: {lighting_motion}",
                f"[Style & Audio]: Zack D. Films 3D documentary animation style, Blender Cycles render aesthetic. Audio: {audio_motion}.",
                f"[Directives]: {_marker_instruction(shot)} Keep lower-middle caption-safe space clear. {raw_motion}{spatial_clause}{role_clause} {text_shield} Characters have closed or neutral mouths. No dialogue, lip-sync, text, generated captions, logos, watermark, UI, or HUD. Instead of any burst or spark, plain physical structural failure only; no light flash, debris shower, or pyrotechnics.",
            )
    elif is_pull_out:
        is_mech = mode.name == "mechanical" or shot.normalized_domain in {"mechanical", "physics", "engineering"}
        target_struct = shot.detail_target or shot.continuity_anchor or ("internal mechanism" if is_mech else "internal anatomical structure")
        revealed_subject = shot.subject_description or shot.subject_id or "subject"
        boundary_phrase = "through the protective mechanical casing" if is_mech else "through the tissue boundary"
        interp_phrase = "Storyboard interpolation from micro structure to resolved machine assembly." if is_mech else "Storyboard interpolation from micro structure to resolved subject."
        lighting_pull = f"{_environment_motion_clause(shot, mode)} Macro mechanical sheen resolving into 5600K studio key light, sharp cyan rim light." if is_mech else f"{_environment_motion_clause(shot, mode)} Clinical macro glow resolving into 5600K studio key light, sharp cyan rim light."
        audio_pull = audio_cue or ("subtle tactile mechanical hum, metal strain, sterile room tone" if is_mech else "subtle visceral fluid flow, sterile room tone")
        if is_longform:
            lighting_pull = f"{_environment_motion_clause(shot, mode)} Period-accurate natural light and weather matching the scene."
            parts = (
                f"[Scene & Motion]: Continuous {shot.duration:.1f}-second cinematic pull-back reveal. Horizontal 16:9 widescreen framing. Camera accelerates backward along the optical axis, pulling out from {target_struct} {boundary_phrase} to settle into a {shot.scale} shot of {revealed_subject}. {interp_phrase} Zero jump cuts, no flashing.",
                f"[Subject & Physics]: Maintain continuity anchor {shot.continuity_anchor or shot.subject_id}.{secondary_clause} Show causal physical payoff: {shot.dominant_event}. Animate only diegetic scene physics: {physics_verbs}. Proof: {shot.proof_on_screen}.{scale_anchor}{damage_clause}",
                f"[Lighting & Environment]: {lighting_pull}",
                f"[Style]: Photorealistic National Geographic / BBC Earth documentary cinematography, natural 35mm motion physics.",
                f"[Directives]: {_marker_instruction(shot)} Reserve lower-third caption space. {raw_motion}{spatial_clause}{role_clause} {text_shield} Closed or neutral mouths, no dialogue or lip-sync; narration is voiceover. No text, subtitles, logos, watermark, UI, or HUD.",
            )
        else:
            parts = (
                f"[Scene & Motion]: Continuous 4.0-second rapid pull-back reveal. Vertical 9:16 framing. Camera accelerates backward along the optical axis, pulling out from the glowing {target_struct} {boundary_phrase} to settle into a {shot.scale} shot of the {revealed_subject}. {interp_phrase} Zero jump cuts, no flashing.",
                f"[Subject & Physics]: Maintain continuity anchor {shot.continuity_anchor or shot.subject_id}.{secondary_clause} Show causal physical payoff: {shot.dominant_event}. Animate only diegetic scene physics: {physics_verbs}. Proof: {shot.proof_on_screen}.{scale_anchor}{damage_clause}",
                f"[Lighting & Environment]: {lighting_pull}",
                f"[Style & Audio]: Zack D. Films 3D documentary animation style, Blender Cycles render aesthetic. Audio: {audio_pull}.",
                f"[Directives]: {_marker_instruction(shot)} Keep lower-middle caption-safe space clear. {raw_motion}{spatial_clause}{role_clause} {text_shield} Characters have closed or neutral mouths. No dialogue, lip-sync, text, generated captions, logos, watermark, UI, or HUD. Instead of any burst or spark, plain physical structural failure only; no light flash, debris shower, or pyrotechnics.",
            )
    else:
        lighting_clause = "5600K warm golden directional key, sharp cyan rim light"
        if is_longform:
            lighting_clause = "period-accurate natural light consistent with the authored scene and weather"
        if shot.journey_phase == "explore" and shot.normalized_domain == "mechanical":
            lighting_clause = f"{lighting_clause}, high-contrast studio rim light, tactile macro surface reflections"
        if is_longform:
            parts = (
                f"[Scene & Motion]: One coherent {shot.duration:.1f}-second 16:9 widescreen cinematic documentary scene. Framing: {framing}. Move from {shot.entry_state} to {shot.exit_state}.",
                f"[Subject & Physics]: Maintain continuity anchor {shot.continuity_anchor or shot.subject_id}.{secondary_clause} Show causal physical payoff: {shot.dominant_event}. Animate only diegetic scene physics: {physics_verbs}. Proof: {shot.proof_on_screen}.{scale_anchor}{damage_clause}",
                f"[Lighting & Environment]: {_environment_motion_clause(shot, mode, scale=shot.scale)} {lighting_clause}.",
                f"[Style]: Photorealistic National Geographic / BBC Earth documentary cinematography, natural 35mm motion physics.",
                f"[Directives]: {_marker_instruction(shot)} Reserve lower-third caption space. {raw_motion}{spatial_clause}{role_clause} {text_shield} Closed or neutral mouths, no dialogue or lip-sync; narration is voiceover. No text, subtitles, logos, watermark, UI, or HUD.",
            )
        else:
            parts = (
                f"[Scene & Motion]: One coherent 4.0-second vertical 9:16 science-documentary scene. Framing: {framing}. Move from {shot.entry_state} to {shot.exit_state}.",
                f"[Subject & Physics]: Maintain continuity anchor {shot.continuity_anchor or shot.subject_id}.{secondary_clause} Show exactly one causal physical state change: {shot.dominant_event}. Animate only diegetic scene physics: {physics_verbs}. Begin in latent seed state, end in peak state so physical transformation is asymmetric. Proof: {shot.proof_on_screen}.{scale_anchor}{damage_clause}",
                f"[Lighting & Environment]: {_environment_motion_clause(shot, mode, scale=shot.scale)} {lighting_clause}.",
                f"[Style & Audio]: Zack D. Films 3D documentary animation style, Blender Cycles render aesthetic. Audio: {audio_cue}.",
                f"[Directives]: {_marker_instruction(shot)} Keep lower-middle caption-safe space clear. {raw_motion}{spatial_clause}{role_clause} {text_shield} Characters have closed or neutral mouths. No dialogue, lip-sync, text, generated captions, logos, watermark, UI, or HUD. Instead of any burst or spark, plain physical structural failure only; no light flash, debris shower, or pyrotechnics.",
            )

    motion = " ".join(part for part in parts if part)
    if _is_exterior_shot(shot):
        motion = _INTERIOR_CLEANSE_RE.sub("", motion)
        vacancy = _vacancy_guarantee_clause(shot)
        motion = f"{_CAMERA_VIEWPOINT_MANDATE} {motion}{vacancy}"
    is_submerged_car = any(
        kw in f"{shot.location_id} {shot.subject_id} {shot.subject_description} {shot.dominant_event}".casefold()
        for kw in ("car", "lake", "submerged", "sinking", "vehicle", "driver", "windshield")
    )
    if is_submerged_car and "sealed-cabin" not in motion.casefold():
        motion = f"{motion} Sealed-cabin plunge physics: water splashes and rises outside the glass windshield while the interior cabin remains completely dry. Dim cool-blue underwater interior ambient lighting and dark blue lake water outside the side window."
    return {"start_prompt": compile_keyframe_prompt(shot, "start", mode=mode, prior_shots=prior_shots), "end_prompt": compile_keyframe_prompt(shot, "end", mode=mode, prior_shots=prior_shots), "video_prompt": motion, "visual_domain": shot.normalized_domain, "detail_target": shot.detail_target or "physical structure"}


def validate_script(script: Script, timeline: TimelinePlan, mode: ModeProfile = ANATOMICAL) -> list[str]:
    """Explicit local validator used before any remote provider work is permitted."""
    problems: list[str] = []
    if len(script.beats) != 5: problems.append(f"expected 5 beats, got {len(script.beats)}")
    elif [beat.index for beat in script.beats] != [1, 2, 3, 4, 5]: problems.append("beat indices must be exactly 1, 2, 3, 4, 5")
    if timeline.source in {"providers", "providers_audio_driven"}:
        profile = config.narration_profile(script.lang, timeline.total_duration + config.TAIL_HOLD)
        if not profile["min"] <= script.word_count <= profile["max"]:
            problems.append(f"narration needs {profile['min']}..{profile['max']} words for the persisted {timeline.total_duration + config.TAIL_HOLD:.1f}s voice budget; got {script.word_count}")
    if len(script.shots) != timeline.block_count: problems.append(f"expected {timeline.block_count} shots, got {len(script.shots)}")
    if timeline.keyframe_count != timeline.block_count + 1: problems.append(f"production timeline requires exactly {timeline.block_count + 1} Match-Cut keyframes; got {timeline.keyframe_count}")
    anchor_contract = any(
        shot.presentation_mode != "mechanism" or shot.opening_anchor_id or shot.contextual_anchor_id or shot.payoff_reason
        for shot in script.shots
    )
    opening_anchor_id = script.shots[0].opening_anchor_id if script.shots else ""
    contextual_opening = next((shot for shot in script.shots if shot.presentation_mode == "contextual_opening_anchor"), None)
    if anchor_contract and script.shots:
        if script.shots[0].presentation_mode not in {"opening_anchor", "contextual_opening_anchor"}:
            problems.append("first shot must declare presentation_mode opening_anchor or contextual_opening_anchor")
        if script.shots[0].presentation_mode == "opening_anchor" and not opening_anchor_id:
            problems.append("opening anchor requires a stable opening_anchor_id")
    prior: Shot | None = None
    for expected, shot in enumerate(script.shots, start=1):
        label = f"shot {expected}"
        if shot.block != expected: problems.append(f"{label} has invalid block number")
        required_beats = _required_beat_indices(timeline.block_count)
        if shot.beat_index != required_beats[expected - 1]: problems.append(f"{label} must map to beat_index {required_beats[expected - 1]} to preserve the causal narration sequence")
        if abs(shot.duration - timeline.native_clip_duration) > 0.01: problems.append(f"{label} does not use persisted native duration")
        if not all((shot.start_image_prompt, shot.end_image_prompt, shot.motion_prompt)): problems.append(f"{label} needs start image, end image, and motion prompt")
        if not all((shot.entry_state, shot.exit_state, shot.dominant_event, shot.proof_on_screen)): problems.append(f"{label} needs entry/exit state, dominant event, and physical proof")
        if shot.entry_state.casefold() == shot.exit_state.casefold(): problems.append(f"{label} entry_state and exit_state must visibly differ")
        if shot.scale not in SCALES: problems.append(f"{label} has invalid scale {shot.scale!r}")
        if shot.journey_phase not in JOURNEY_PHASES: problems.append(f"{label} has invalid journey_phase {shot.journey_phase!r}")
        if shot.transition_kind not in TRANSITION_KINDS: problems.append(f"{label} has invalid transition_kind {shot.transition_kind!r}")
        if shot.presentation_mode not in PRESENTATION_MODES: problems.append(f"{label} has invalid presentation_mode {shot.presentation_mode!r}")
        if shot.presentation_mode == "opening_anchor":
            if expected != 1: problems.append(f"{label} opening_anchor is allowed only on the first shot")
            if not shot.opening_anchor_id.strip(): problems.append(f"{label} opening_anchor requires opening_anchor_id")
        if shot.presentation_mode == "contextual_opening_anchor":
            if expected != 1: problems.append(f"{label} contextual_opening_anchor is allowed only on the first shot")
            if not all((shot.contextual_anchor_id.strip(), shot.contextual_anchor_subject_id.strip(), shot.contextual_anchor_appearance_contract.strip())):
                problems.append(f"{label} contextual opening requires stable id, subject id, and appearance contract")
            if shot.contextual_anchor_kind not in CONTEXTUAL_ANCHOR_KINDS:
                problems.append(f"{label} has invalid contextual_anchor_kind")
            if shot.subject_id != shot.contextual_anchor_subject_id:
                problems.append(f"{label} contextual opening subject must equal contextual_anchor_subject_id")
        if shot.presentation_mode == "return_to_opening_anchor_payoff":
            if expected != len(script.shots): problems.append(f"{label} opening-anchor payoff is allowed only on the final shot")
            if not shot.opening_anchor_id.strip() or shot.opening_anchor_id != opening_anchor_id:
                problems.append(f"{label} payoff must reuse the first shot's opening_anchor_id")
            if not shot.payoff_reason.strip(): problems.append(f"{label} payoff requires a non-decorative payoff_reason")
            if shot.endpoint_mode != "first_only": problems.append(f"{label} opening-anchor payoff must use first_only endpoint_mode")
        if shot.presentation_mode == "return_to_contextual_anchor_payoff":
            if expected != len(script.shots): problems.append(f"{label} contextual payoff is allowed only on the final shot")
            if contextual_opening is None: problems.append(f"{label} contextual payoff requires a first-shot contextual_opening_anchor")
            else:
                if shot.contextual_anchor_id != contextual_opening.contextual_anchor_id:
                    problems.append(f"{label} contextual payoff must reuse the first contextual_anchor_id")
                if shot.subject_id != contextual_opening.contextual_anchor_subject_id or shot.contextual_anchor_subject_id != contextual_opening.contextual_anchor_subject_id:
                    problems.append(f"{label} contextual payoff must reuse the contextual roster identity")
                if shot.contextual_anchor_appearance_contract != contextual_opening.contextual_anchor_appearance_contract:
                    problems.append(f"{label} contextual payoff must reuse the contextual appearance contract")
            if not shot.mechanism_anchor_id.strip(): problems.append(f"{label} contextual payoff requires mechanism_anchor_id")
            if not shot.payoff_reason.strip() or _DECORATIVE_PAYOFF_RE.fullmatch(shot.payoff_reason.strip()): problems.append(f"{label} contextual payoff requires a causal non-decorative payoff_reason")
            if shot.endpoint_mode not in {"first_only", "first_last"}: problems.append(f"{label} contextual payoff must use first_only or first_last endpoint_mode")
        if shot.normalized_domain not in _DOMAIN_SCALES: problems.append(f"{label} has invalid visual_domain {shot.visual_domain!r}")
        elif shot.scale not in _DOMAIN_SCALES[shot.normalized_domain]: problems.append(f"{label} scale {shot.scale} is not appropriate for {shot.normalized_domain}")
        if shot.endpoint_mode not in {"first_last", "first_only"}: problems.append(f"{label} has invalid endpoint_mode")
        if shot.endpoint_mode == "first_only" and not shot.endpoint_reason.strip(): problems.append(f"{label} first_only endpoint_mode requires an explicit quality reason")
        if shot.marker_type not in MARKER_TYPES: problems.append(f"{label} has invalid marker_type")
        if shot.marker_type != "none":
            mq = _quadrant(shot.marker_quadrant)
            if mq in {"center", "lower_center"} or mq != shot.push_quadrant:
                problems.append(f"{label} marker must use its authored non-center, non-caption target quadrant")
            if shot.caption_safe_zone != "lower_middle": problems.append(f"{label} marker must preserve lower-middle caption-safe zone")
            if not (shot.proof_on_screen.startswith("ANNOTATION REQUIRED:") or any(k in shot.proof_on_screen.casefold() for k in ("arrow", "trajectory", "vector", "direction", "flow", "pressure", "force", "marker"))):
                problems.append(f"{label} marker is decorative; physical proof must be shown without a marker unless proof_on_screen explicitly describes directional force/flow or starts ANNOTATION REQUIRED:")
        if shot.location_id and "|" in shot.location_id: problems.append(f"{label} contains multiple remote locations")
        beats = shot.resolved_coverage_beats
        if not 2 <= len(beats) <= 4: problems.append(f"{label} needs 2..4 coverage beats")
        elif any(not 1.0 <= float(item.get("duration") or 0.0) <= 1.6 for item in beats): problems.append(f"{label} coverage beats must be 1.0..1.6 seconds")
        elif abs(sum(float(item.get("duration") or 0.0) for item in beats) - shot.duration) > 0.02: problems.append(f"{label} coverage beats must tile the native block")
        text_contract = " ".join((shot.start_image_prompt, shot.end_image_prompt, shot.motion_prompt)).casefold()
        if re.search(r"\b(?:photorealistic|realistic|real life|stylized-realistic)\b", text_contract): problems.append(f"{label} contains prohibited realism language")
        human_subject = _is_human_subject({
            "subject_id": shot.subject_id, "subject_description": shot.subject_description,
            "start_image_prompt": shot.start_image_prompt, "end_image_prompt": shot.end_image_prompt,
        })
        if mode.single_shot_human_anchor:
            if human_subject and expected > 1 and shot.presentation_mode not in {"return_to_opening_anchor_payoff", "return_to_contextual_anchor_payoff"} and shot.normalized_domain not in {"anatomical", "biological"}: problems.append(f"{label} must use anatomical or biological cutaway content after the establish shot")
        if mode.environment_censor:
            if re.search(r"\b(?:hospital|street|bedroom|living room|office|wall|sky)\b", text_contract): problems.append(f"{label} violates the dark-void background contract")
        unstable = re.search(r"\b(floating parts?|geometry morph(?:ing)?|disappearing (?:bolt|pipe|connection)|random sparks?|random beams?|spark explosion|violent (?:mechanical )?fracture|crisp particle sparks?|decorative explosion)\b", f"{shot.motion_prompt} {shot.dominant_event} {' '.join(shot.quality_critical)}", re.I)
        if unstable: problems.append(f"{label} requests fragile mechanical artifact: {unstable.group(1)}")
        if prior:
            if abs(SCALES.index(shot.scale) - SCALES.index(prior.scale)) > MAX_SCALE_JUMP: problems.append(f"{label} exceeds max scale jump from {prior.scale} to {shot.scale}")
            if shot.transition_kind == "same_subject" and prior.subject_id != shot.subject_id: problems.append(f"{label} says same_subject but subject_id changes")
            if prior.continuity_anchor and shot.continuity_anchor and prior.continuity_anchor != shot.continuity_anchor and shot.transition_kind == "same_subject": problems.append(f"{label} breaks same-subject continuity anchor")
            if shot.transition_kind == "scale_transition" and shot.scale == prior.scale and shot.camera_angle == prior.camera_angle: problems.append(f"{label} says scale_transition but scale is unchanged from {prior.scale}")
        prior = shot
        compiled = optimize_for_flow(shot, mode=mode)
        required = ("Vertical 9:16", "caption-safe", "No dialogue", "watermark", "dark neutral", "cyan rim")
        if any(token.casefold() not in (compiled["start_prompt"] + compiled["end_prompt"] + compiled["video_prompt"]).casefold() for token in required) and mode.environment_style == "void": problems.append(f"{label} canonical compiler safety contract is incomplete")
        if mode.name != "explorer" and not getattr(config, "LONGFORM_MODE", False):
            if re.search(r"\b(?:photorealistic|realistic|real life|stylized-realistic)\b", (compiled["start_prompt"] + compiled["end_prompt"] + compiled["video_prompt"]), re.I): problems.append(f"{label} compiler emitted prohibited realism language")
        motion_check = _CONTROLLED_TRANSITION_RE.sub("", compiled["video_prompt"])
        if _CAMERA_COMMAND_RE.search(motion_check): problems.append(f"{label} compiler emitted a camera command")

    # --- Incident mode: real-person safety validators ---
    if not mode.single_shot_human_anchor:  # incident mode
        for i_shot, shot in enumerate(script.shots, 1):
            label = f"shot {i_shot}"
            all_ids = [shot.subject_id] + list(shot.secondary_subject_ids or [])
            for sid in all_ids:
                if not re.fullmatch(r"[a-z][a-z0-9_]*", sid):
                    problems.append(f"{label} subject ID '{sid}' must be lowercase role-based (e.g. 'unruly_passenger', 'flight_attendant_01')")
        if script.narration:
            proper_names = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", script.narration)
            allowed = {"United States", "New York", "Los Angeles", "Frontier Airlines", "American Airlines", "Delta Airlines", "Southwest Airlines", "Federal Aviation Administration", "Los Angeles International", "Miami International"}
            suspicious = [n for n in proper_names if n not in allowed]
            if suspicious:
                problems.append(f"Narration contains potential real person names: {', '.join(suspicious[:3])}. Use role-based descriptions instead.")

        # Character visual contrast check (incident mode):
        # Prevent visually indistinguishable characters sharing dominant color/clothing keywords.
        for i_shot, shot in enumerate(script.shots, 1):
            label = f"shot {i_shot}"
            prim_desc = shot.subject_description or resolve_subject_description(shot.subject_id, script.shots, i_shot - 1)
            if not prim_desc or not shot.secondary_subject_ids:
                continue
            prim_tokens = set(re.findall(r"\b[a-z]+\b", prim_desc.casefold()))
            for sec_id in shot.secondary_subject_ids:
                sec_desc = resolve_subject_description(sec_id, script.shots, i_shot - 1)
                if not sec_desc:
                    continue
                sec_tokens = set(re.findall(r"\b[a-z]+\b", sec_desc.casefold()))
                shared = (prim_tokens & sec_tokens) & _CONTRAST_KEYWORDS
                if shared:
                    problems.append(
                        f"{label} character contrast violation: '{shot.subject_id}' and '{sec_id}' "
                        f"share dominant color/clothing keywords ({', '.join(sorted(shared))}); "
                        f"incident mode requires visually contrasting descriptions (e.g. navy jacket vs plain white shirt)"
                    )

        # ADR-031: Monotonic causal physical state guard
        # A character ejected or pinned outside fuselage cannot perform internal cockpit operations in middle shots.
        exterior_subjects: set[str] = set()
        for i_shot, shot in enumerate(script.shots, 1):
            is_terminal_payoff = shot.presentation_mode in {"return_to_opening_anchor_payoff", "return_to_contextual_anchor_payoff"} or shot.journey_phase == "resolve"
            state_text = f"{shot.entry_state} {shot.exit_state} {shot.dominant_event}".casefold()
            if any(kw in state_text for kw in ("exterior_pinned", "sucked out", "outside fuselage", "pulled outward", "airborne outside", "pinned against", "exterior slipstream", "pinned to outer")):
                exterior_subjects.add(shot.subject_id)

            if not is_terminal_payoff and exterior_subjects:
                for ext_id in exterior_subjects:
                    shot_text = f"{shot.start_image_prompt} {shot.end_image_prompt} {shot.dominant_event}".casefold()
                    if ext_id in shot_text:
                        internal_action = re.search(rf"\b{ext_id}\b.*?\b(?:standing|standing in|seated in cockpit|hands on yoke|diving forward|grabbing ankles|inside flight deck|operating controls)\b", shot_text)
                        if internal_action:
                            problems.append(
                                f"shot {i_shot} violates monotonic causal state guard: '{ext_id}' is already in an exterior/pinned "
                                f"physical state and cannot be depicted performing interior cockpit operations ({internal_action.group(0)}) before resolution"
                            )

    for beat in script.beats:
        for s in re.split(r"[.!?]+", beat.text):
            words = [w for w in s.strip().split() if w]
            if len(words) > 20:
                problems.append(f"beat {beat.index} sentence exceeds length limit ({len(words)} words); Zack D. Films staccato narration requires punchy sentences under 16-20 words")

    if not script.narration: problems.append("narration is empty")
    return problems


class BeatEngine:
    """Validate/repair structured LLM screenplay payloads through one injected adapter."""
    def __init__(self, llm: BaseLLMProvider, *, lang: str, timeline: TimelinePlan, mode: ModeProfile = ANATOMICAL) -> None:
        self.llm, self.lang, self.timeline, self.mode = llm, lang, timeline, mode

    @property
    def schema(self) -> dict[str, Any]:
        beat = {
            "type": "object",
            "properties": {
                "index": {"type": "integer"}, "text": {"type": "string", "minLength": 1},
                "role": {"type": "string"}, "emphasis": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["index", "text"], "additionalProperties": True,
        }
        shot = {
            "type": "object",
            "properties": {
                "beat_index": {"type": "integer", "minimum": 1, "maximum": 5}, "subject_id": {"type": "string", "minLength": 1}, "subject_description": {"type": "string", "minLength": 1},
                "start_image_prompt": {"type": "string", "minLength": 1}, "end_image_prompt": {"type": "string", "minLength": 1},
                "motion_prompt": {"type": "string", "minLength": 1}, "target_quadrant": {"type": "string"}, "end_target_quadrant": {"type": "string"},
                "visual_domain": {"type": "string", "enum": sorted(_DOMAIN_SCALES)}, "scale": {"type": "string", "enum": list(SCALES)},
                "journey_phase": {"type": "string", "enum": list(JOURNEY_PHASES)}, "transition_kind": {"type": "string", "enum": list(TRANSITION_KINDS)},
                "camera_angle": {"type": "string"}, "camera_vector": {"type": "string"}, "detail_target": {"type": "string"},
                "structure_tags": {"type": "array", "items": {"type": "string"}}, "quality_critical": {"type": "array", "items": {"type": "string"}},
                "continuity_anchor": {"type": "string", "minLength": 1}, "entry_state": {"type": "string", "minLength": 1},
                "exit_state": {"type": "string", "minLength": 1}, "dominant_event": {"type": "string", "minLength": 1},
                "proof_on_screen": {"type": "string", "minLength": 1}, "location_id": {"type": "string", "minLength": 1},
                "marker_type": {"type": "string", "enum": list(MARKER_TYPES)}, "marker_quadrant": {"type": "string"},
                "endpoint_mode": {"type": "string", "enum": ["first_last", "first_only"]}, "endpoint_reason": {"type": "string"},
                "presentation_mode": {"type": "string", "enum": list(PRESENTATION_MODES)},
                "opening_anchor_id": {"type": "string"}, "payoff_reason": {"type": "string"},
                "contextual_anchor_id": {"type": "string"}, "contextual_anchor_subject_id": {"type": "string"},
                "contextual_anchor_kind": {"type": "string", "enum": list(CONTEXTUAL_ANCHOR_KINDS)}, "mechanism_anchor_id": {"type": "string"},
                "contextual_anchor_roster_ids": {"type": "array", "items": {"type": "string"}}, "contextual_anchor_appearance_contract": {"type": "string"},
                "contextual_anchor_prompt_sha256": {"type": "string"}, "contextual_anchor_sheet_ids": {"type": "array", "items": {"type": "string"}},
                "secondary_subject_ids": {"type": "array", "items": {"type": "string"}, "description": "Additional characters present in this shot (role-based IDs)"},
                "impact_offset_seconds": {"type": "number", "minimum": 0.2, "maximum": 3.8, "description": "Time in seconds from shot start when primary physical impact/foley contact occurs"},
                "spatial_anchor": {"type": "string", "description": "Physical environment anchor: e.g. EXTERIOR, AIRFRAME, COCKPIT, CABIN, MACRO_ORGAN, etc."},
                "scale_level": {"type": "string", "description": "Camera scale level: e.g. EXTERIOR, MACRO, MICRO, NANO, WIDE, CLOSEUP"},
                "forbidden_entities": {"type": "array", "items": {"type": "string"}, "description": "Entities or states strictly forbidden in this shot"},
                "state_tracking": {
                    "type": "object",
                    "properties": {
                        "forbidden_entities": {"type": "array", "items": {"type": "string"}},
                    },
                    "additionalProperties": True,
                },
            },
            "required": ["beat_index", "subject_id", "subject_description", "start_image_prompt", "end_image_prompt", "motion_prompt", "target_quadrant", "visual_domain", "scale", "journey_phase", "transition_kind", "camera_angle", "detail_target", "continuity_anchor", "entry_state", "exit_state", "dominant_event", "proof_on_screen", "location_id", "marker_type", "endpoint_mode", "presentation_mode", "opening_anchor_id", "impact_offset_seconds"],
            "additionalProperties": True,
        }
        youtube = {
            "type": "object",
            "properties": {
                "titles": {"type": "array", "minItems": 3, "maxItems": 5, "items": {"type": "string"}},
                "description": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "pinned_comment": {"type": "string", "description": "Engaging discussion question for the pinned comment"},
            },
            "required": ["titles", "description", "tags"],
            "additionalProperties": True,
        }
        return {
            "type": "object",
            "properties": {
                "beats": {"type": "array", "minItems": 5, "maxItems": 5, "items": beat},
                # The initial screenplay matches the timeline block count, then measured
                # voice locks a 6..13 block plan before keyframe generation.
                "shots": {"type": "array", "minItems": min(config.MIN_BLOCKS, self.timeline.block_count), "maxItems": max(config.MAX_BLOCKS, self.timeline.block_count), "items": shot},
                # Match-Cut endpoints are compiled deterministically from shots, but
                # keep this declared contract visible to structured-output providers.
                "keyframes": {"type": "array", "minItems": min(config.MIN_BLOCKS + 1, self.timeline.keyframe_count), "maxItems": max(config.MAX_BLOCKS + 1, self.timeline.keyframe_count), "items": {"type": "object"}},
                "youtube": youtube,
            },
            "required": ["beats", "shots", "youtube"],
            "additionalProperties": False,
        }

    def system_prompt(self) -> str:
        if self.mode.name == "incident":
            return self._incident_system_prompt()
        elif self.mode.name == "mechanical":
            return self._mechanical_system_prompt()
        return self._anatomical_system_prompt()

    def _anatomical_system_prompt(self) -> str:
        profile = config.narration_profile(self.lang, self.timeline.total_duration + config.TAIL_HOLD)
        mapping = _required_beat_indices(self.timeline.block_count)
        return (
            f"Write a {self.lang} vertical Zack D. Films-style science documentary with exactly five narration beats and {self.timeline.block_count} visual shots. "
            f"Each shot is exactly {self.timeline.native_clip_duration:.1f} seconds. Narration must contain {profile['min']} to {profile['max']} spoken words total across the 5 beats (target exactly {profile['target']} words total, approximately {profile['target'] // 5} words per beat). Count words carefully so the total is strictly within {profile['min']}..{profile['max']}. "
            "ELI12 Tone & Staccato Rhythm: Explain like the viewer is 12 years old. Use short, punchy active sentences (strictly 6–10 words per sentence). "
            "Use em-dashes (—) and ellipses (...) to inject suspenseful micro-pauses and a rhythmic staccato pulse into the voiceover. "
            "Strictly NO Latin or academic medical/biological jargon: do NOT use 'vasoconstriction' (say 'blood vessels panic and slam shut'), 'vasodilation' (say 'blast wide open with hot blood'), 'trigeminal nerve / cranial pathway' (say 'a major nerve hooked to your forehead'), 'nociceptive signal' (say 'screaming pain signals'), 'cellular necrosis' (say 'cells break down and die'), 'cerebral cortex' (say 'your brain's control center'), or 'pathophysiology'. Personify organs and cells as characters dealing with an emergency. "
            "Beat 1 (Paradox Hook): Open with a direct second-person address ('You') and a visceral sensory paradox in the very first sentence (max 12 words), contrasting what you feel with where it happens. "
            "Beat 3 (Everyday Analogy): Must include a clear, tangible real-world analogy from daily life or the kitchen/household (e.g. 'Like a frozen garden hose blasted with boiling water...'). "
            "Beat 5 (Resolution & Loop): Clearly answer the paradox, ending with a satisfying conclusion that connects seamlessly back to the opening hook when the video loops. "
            f"Shot beat_index values must be exactly {mapping}: every beat must visibly advance the same causal answer, from hook through mechanism to payoff. "
            "Single-Shot Exterior Anchor & Rapid Penetration: Shot 1 (0 to 4s) establishes the paradox: an exterior human character is shown ONLY in Shot 1, and at t=2.0s the camera accelerates in a rapid push-through penetrating into the internal anatomy along the oral or thoracic penetration axis. Shot 2 MUST begin directly inside internal tissue or organ structures (trachea, bronchi, alveoli, blood vessels, etc.). NEVER show the exterior human character in Shot 2 or any middle shot. Middle shots show the mechanism in ordered physical steps, and final shots prove the payoff. "
            "Shot 1 camera_vector must NEVER be 'static'; it must use 'forward rapid push-through along penetration axis' or dynamic forward movement into the subject. "
            "Anti-Stagnation & Asymmetric State Change: Each shot must depict a distinct, irreversible physical step (Keyframe 1 latent/seed state -> Keyframe 2 peak/event state). No two consecutive shots may show the same physical contact or static state; adjacent shots must advance the causal domino chain to the next phase. "
            "Use fields beat_index, scale (wide/medium/close/macro/micro/nano), visual_domain, journey_phase, transition_kind, camera_angle, detail_target, continuity_anchor, entry_state, exit_state, dominant_event, proof_on_screen, and impact_offset_seconds. "
            "Specify impact_offset_seconds for each shot: the exact timestamp (between 0.2 and 3.6s from shot start) when the primary physical impact, puncture, collision, or mechanical contact occurs, to drive millisecond-accurate tactile Foley sync. "
            "Plan adjacent shots as one continuous chain before writing JSON: between neighbors scale may move by at most one step in the listed scale order. When transition_kind is same_subject, copy the exact same subject_id, continuity_anchor, and location_id from the prior shot; use subject_change or location_change only for an intentional Match-Cut. "
            "quality_critical must name every discrete countable object that must retain its exact count and position across the shot, for example 'exactly 3 cable clamps, evenly spaced, unchanged position'. "
            "One shot has one visible causal state change and one location. Characters never speak; mouths stay closed. Mechanical scenes show only the physical evidence needed to understand the mechanism: never invent decorative sparks, flash bursts, explosions, fireworks, or neon effects. Instead, state the plain readable physical alternative such as a widening crack, separating fibers, or slow structural give. No generated text, captions, logos, watermarks, HUDs, dialogue, or lip-sync. "
            "Visual Proof & Markers: Use marker_type 'arrow' or 'trajectory' with matching marker_quadrant when the physical proof involves directional fluid flow, air currents, surface tension vectors, or localized force; when using a marker, state 'ANNOTATION REQUIRED: [directional arrow showing force/flow]' in proof_on_screen. Otherwise set marker_type to 'none'. "
            " If a wide viewer-facing subject materially establishes the question, the first shot must use contextual_opening_anchor and declare a stable contextual_anchor_id, contextual_anchor_subject_id, contextual_anchor_kind, mechanism_anchor_id, and appearance contract. Otherwise the first shot uses opening_anchor. All ordinary shots use mechanism. "
            "CPIG Character Consistency: Exterior character must be a minimalist 3D animated stylized mannequin (Blender Cycles render aesthetic, smooth stylized facial features, 30-year-old average person, short brown hair, simple solid-colored crewneck t-shirt, neutral expression, neutral closed mouth, soft skin SSS). STRICTLY NO photograph or live-action imagery, no wrinkles, no skin pores, no live-action human depiction. "
            "Continuous Camera Flight & Bridge Keyframe: For transitions from the external human subject into internal anatomy/organs, author a Bridge Keyframe shot (scale_transition with extreme close-up on the tissue/oral entry boundary along the penetration axis) to enable continuous push-through camera flight. "
            "Only if returning to the opening visual subject materially proves the final narration beat, the final shot may use return_to_opening_anchor_payoff with the exact same opening_anchor_id and a concrete payoff_reason; it must be first_only and is an independent terminal hard cut, never a morph. "
            "Only if returning to the contextual subject materially proves the final narration beat, the final shot may instead use return_to_contextual_anchor_payoff with the exact same contextual_anchor_id and contextual roster identity, a concrete causal payoff_reason, and first_only or first_last endpoint mode (use first_last for continuous pull-back zoom-out reveal storyboard interpolation from the internal mechanism back to the contextual human subject). "
            "Do not write unauthorized camera panning or shaking instructions. Describe only diegetic physical motion or authorized continuous camera flight along the optical penetration axis."
            " Perspective Isolation: Use spatial_anchor (e.g. 'EXTERIOR_FACE', 'AIRFRAME', 'MACRO_ORGAN') and forbidden_entities to explicitly forbid premature or unrequested entities (e.g. ['healthy cornea', 'frozen liquid']). "
            " Include a youtube object with 3-5 punchy title options, an engaging 2-sentence description ending with relevant #shorts hashtags, and 10-15 comma-separated SEO keyword tags."
        )

    def _incident_system_prompt(self) -> str:
        profile = config.narration_profile(self.lang, self.timeline.total_duration + config.TAIL_HOLD)
        mapping = _required_beat_indices(self.timeline.block_count)
        return (
            f"Write a {self.lang} vertical Zack D. Films-style animated documentary reconstructing a real-world news event or incident with exactly five narration beats and {self.timeline.block_count} visual shots. "
            f"Each shot is exactly {self.timeline.native_clip_duration:.1f} seconds. Narration must contain {profile['min']} to {profile['max']} spoken words total across the 5 beats (target exactly {profile['target']} words total, approximately {profile['target'] // 5} words per beat). Count words carefully so the total is strictly within {profile['min']}..{profile['max']}. "
            f"Staccato Narrative Rhythm & Exact Beat Lengths: Each of the 5 beats must contain exactly two punchy sentences totaling approximately {profile['target'] // 5} words per beat (e.g. 10 words + 10 words = 20 words per beat). The grand total across all 5 beats must strictly fall within {profile['min']}..{profile['max']} words. Explain clearly and factually like an investigative news documentary. "
            "Beat 1 (Incident Hook): Open with a direct second-person address ('You') or immediate shock scenario in the very first sentence (max 12 words), establishing where it happens and what goes wrong. "
            "Beat 3 (The Physical Mechanism / Conflict): Explain the exact mechanical, procedural, or physical reality of what happened (e.g. why an emergency door cannot open under differential cabin pressure, how mechanical locking pins resist force, or how a restraint was applied). "
            "Beat 5 (Resolution & Consequence): Deliver the decisive conclusion—how the situation was safely resolved or controlled, leaving a memorable takeaway that loops cleanly back to the opening hook. "
            f"Shot beat_index values must be exactly {mapping}: every beat must visibly advance the chronological timeline of the event. "
            "Shot 1 presentation_mode must be 'opening_anchor' (or 'contextual_opening_anchor'). Middle shots (shots 2 through N-1) MUST use presentation_mode 'mechanism'. The final shot may use 'mechanism' or 'return_to_opening_anchor_payoff'. "
            "Contextual Real-World Environment & Persistence: Set scenes in realistic, detailed 3D environments (e.g. 'airplane_cabin' with passenger rows, windows, overhead bins, cockpit door; or 'airport_tarmac', 'street', 'building_interior'). The environment persists across shots unless an intentional location change occurs. "
            "Multi-Character & Role-Based Identity: When people interact in a scene, put the primary actor in subject_id (e.g. 'unruly_passenger'). List any other visible people in secondary_subject_ids as role-based IDs (e.g. ['flight_attendant_01', 'seated_passenger']). "
            "STRICT PRIVACY & NON-SPECULATION: NEVER use real person names or surnames under any circumstances. Always use descriptive lowercase role IDs (e.g. 'unruly_passenger', 'flight_attendant_01', 'responding_officer'). Do NOT invent unverified dialogue or malicious intent. Reconstruct documented physical actions only. "
            "Characters NEVER speak; mouths strictly closed and neutral. No dialogue, lip-sync, text, generated captions, logos, watermark, UI, or HUD. "
            "Blender Cycles Aesthetic & Glossy Stylized 3D: High-end 3D animated documentary render, dramatic studio key light and cyan rim light, PBR materials, stylized character anatomy. Absolutely no live-action photograph or video footage. "
            "Anti-Stagnation & Asymmetric State Change: Each shot depicts a distinct, irreversible physical step (Keyframe 1 latent state -> Keyframe 2 event state). "
            "Visual Proof & Markers: Use marker_type 'arrow' or 'trajectory' with matching marker_quadrant ONLY when showing physical force, trajectory, or mechanical locking pins; state 'ANNOTATION REQUIRED: [directional arrow showing force]' in proof_on_screen. Otherwise set marker_type to 'none'. "
            "Set visual_domain to 'incident' or 'mechanical'. "
            "Camera Scales & Step Continuity: Allowed scale values in order from widest to narrowest are: 'wide', 'medium', 'close', 'macro', 'micro', 'nano'. Plan adjacent shots so between neighbors scale moves by at most ONE step in this list (e.g. wide <-> medium <-> close). Never jump across multiple scale steps (e.g. jumping directly between macro and wide is strictly forbidden). "
            "Specify impact_offset_seconds for each shot (between 0.2 and 3.6s from shot start) when the primary physical contact or impact occurs to drive millisecond-accurate tactile Foley sync. "
            "Costume & Role Decoupling Invariant: In multi-character scenes, every character must have distinct uniforms, physical roles, and locations. Captain pilot has 4 gold stripes on epaulets, white shirt, graying hair (torso pinned outside port windscreen); Copilot has 3 gold stripes on epaulets, seated in starboard (right) cockpit seat holding control yoke with oxygen mask; Flight attendant wears dark navy vest with tie, lying flat on cockpit floor gripping captain's ankles. NEVER swap or blend character roles, garments, or physical positions. "
            "Character Contrast Invariant: If two or more subject_ids appear together in one shot (subject_id + secondary_subject_ids, or two shots linked by transition_kind=same_subject), their subject_description values MUST specify contrasting colors/materials/silhouette so a viewer can never confuse them (e.g. navy jacket vs plain white shirt, not two dark uniforms). "
            "Spatial Vector & 180-Degree Axis Lock: Maintain strict 180-degree axis continuity across all shots. The cockpit breach is strictly on the port-side (left) forward windscreen. The captain is pulled outward onto the port (left) exterior fuselage. Camera must respect the 180-degree line of action. NEVER flip the camera across the axis or depict the breach on the starboard (right) side. "
            "Monotonic Causal State Guard: If a character is pulled outside the cockpit or exterior_pinned (e.g. captain_pilot), they MUST remain in that exterior/pinned physical state in all subsequent middle shots. They can NEVER stand inside the cockpit, sit at the controls, or grab another person's ankles before the safe landing and rescue in Beat 5. All subsequent middle shots must preserve this monotonic physical state. "
            "Perspective Isolation & Exterior Anchor: When a shot depicts an exterior scene (e.g. pilot sucked out onto exterior fuselage, exterior airframe in slipstream), set spatial_anchor to 'EXTERIOR' or 'AIRFRAME' and forbidden_entities to ['captain inside cockpit', 'pilot seated inside', 'cockpit interior']. Exterior shots must strictly focus on the exterior airframe and slipstream, with the interior pilot seat visibly empty. "
            "Include a youtube object with 3-5 punchy title options, an engaging 2-sentence description ending with relevant #shorts hashtags, and 10-15 comma-separated SEO keyword tags."
        )

    def _mechanical_system_prompt(self) -> str:
        profile = config.narration_profile(self.lang, self.timeline.total_duration + config.TAIL_HOLD)
        mapping = _required_beat_indices(self.timeline.block_count)
        return (
            f"Write a {self.lang} vertical Zack D. Films-style physics and engineering documentary with exactly five narration beats and {self.timeline.block_count} visual shots. "
            f"Each shot is exactly {self.timeline.native_clip_duration:.1f} seconds. Narration must contain {profile['min']} to {profile['max']} spoken words total across the 5 beats (target exactly {profile['target']} words total, approximately {profile['target'] // 5} words per beat). Count words carefully so the total is strictly within {profile['min']}..{profile['max']}. "
            "ELI12 Tone & Staccato Rhythm: Explain physical mechanisms like the viewer is 12 years old. Use short, punchy active sentences (strictly 6–10 words per sentence). "
            "Use em-dashes (—) and ellipses (...) to inject suspenseful micro-pauses and a rhythmic staccato pulse into the voiceover. "
            "Strictly NO dry engineering equations or textbook jargon: do NOT write complex mathematical derivations. Personify mechanical forces and components (e.g. 'the steel cable screams under tension', 'the brake wedges bite into the guide rail'). "
            "Beat 1 (Physical Paradox Hook): Open with a direct second-person address ('You') and a sudden mechanical catastrophe or physical question in the very first sentence (max 12 words). "
            "Beat 3 (Everyday Analogy): Must include a clear, tangible household or kitchen analogy (e.g. 'Like a bicycle brake clamping onto a spinning rim...'). "
            "Beat 5 (Resolution & Loop): Conclude with the definitive mechanical safeguard, looping cleanly back to the opening hook when the video loops. "
            f"Shot beat_index values must be exactly {mapping}: every beat must visibly advance the causal mechanical explanation. "
            "Single-Shot Machine Context & Rapid Penetration: Shot 1 establishes the exterior machine, vehicle, or physical apparatus in its environment. At t=2.0s, the camera accelerates in a rapid push-in penetrating the outer chassis/casing along the mechanical drive axis. Shot 2 MUST begin directly inside the internal mechanical assembly (gears, pistons, cables, hydraulic chambers). NEVER introduce human anatomy, organs, or medical tissue. Middle shots show ordered mechanical cause-and-effect steps, and final shots prove the structural payoff. "
            "Shot 1 camera_vector must NEVER be 'static'; it must use 'forward rapid push-through along penetration axis' or dynamic forward movement into the machine. "
            "Anti-Stagnation & Asymmetric State Change: Each shot must depict a distinct, irreversible physical step (Keyframe 1 latent/seed state -> Keyframe 2 peak/event state). No two consecutive shots may show the same physical contact or static state; adjacent shots must advance the causal domino chain to the next phase. "
            "Use fields beat_index, scale (wide/medium/close/macro/micro/nano), visual_domain, journey_phase, transition_kind, camera_angle, detail_target, continuity_anchor, entry_state, exit_state, dominant_event, proof_on_screen, and impact_offset_seconds. "
            "Specify impact_offset_seconds for each shot: the exact timestamp (between 0.2 and 3.6s from shot start) when the primary physical impact, puncture, collision, or mechanical contact occurs, to drive millisecond-accurate tactile Foley sync. "
            "Plan adjacent shots as one continuous chain before writing JSON: between neighbors scale may move by at most one step in the listed scale order. When transition_kind is same_subject, copy the exact same subject_id, continuity_anchor, and location_id from the prior shot; use subject_change or location_change only for an intentional Match-Cut. "
            "quality_critical must name every discrete countable object that must retain its exact count and position across the shot, for example 'exactly 4 steel cables, evenly spaced, unchanged position'. "
            "One shot has one visible causal state change and one location. Mechanical scenes show only the physical evidence needed to understand the mechanism: never invent decorative sparks, flash bursts, explosions, fireworks, or neon effects. Instead, state the plain readable physical alternative such as a widening crack, separating fibers, or slow structural give. No generated text, captions, logos, watermarks, HUDs, dialogue, or lip-sync. "
            "Visual Proof & Markers: Use marker_type 'arrow' or 'trajectory' with matching marker_quadrant ONLY when showing force vectors, stress lines, or mechanical locking pins; when using a marker, state 'ANNOTATION REQUIRED: [directional arrow showing force/flow]' in proof_on_screen. Otherwise set marker_type to 'none'. "
            "If a wide viewer-facing machine materially establishes the question, the first shot must use contextual_opening_anchor and declare a stable contextual_anchor_id, contextual_anchor_subject_id, contextual_anchor_kind, mechanism_anchor_id, and appearance contract. Otherwise the first shot uses opening_anchor. All ordinary shots use mechanism. "
            "CPIG Consistency: If an operator/human is visible in Shot 1, use a stylized 3D mannequin (Blender Cycles render aesthetic, smooth stylized facial features, neutral expression, neutral closed mouth). Middle shots show purely the mechanical cutaway model with brushed anisotropic metallic sheen and photoelastic stress fringes. STRICTLY NO photograph or live-action imagery. "
            "Continuous Camera Flight & Bridge Keyframe: For transitions from the external machine into internal mechanisms, author a Bridge Keyframe shot (scale_transition with extreme close-up on the chassis entry boundary along the mechanical drive axis) to enable continuous push-through camera flight. "
            "Only if returning to the opening visual subject materially proves the final narration beat, the final shot may use return_to_opening_anchor_payoff with the exact same opening_anchor_id and a concrete payoff_reason; it must be first_only and is an independent terminal hard cut, never a morph. "
            "Only if returning to the contextual machine materially proves the final narration beat, the final shot may instead use return_to_contextual_anchor_payoff with the exact same contextual_anchor_id and contextual roster identity, a concrete causal payoff_reason, and first_only or first_last endpoint mode. "
            "Do not write unauthorized camera panning or shaking instructions. Describe only diegetic physical motion or authorized continuous camera flight along the mechanical drive axis."
            " Include a youtube object with 3-5 punchy title options, an engaging 2-sentence description ending with relevant #shorts hashtags, and 10-15 comma-separated SEO keyword tags."
        )

    async def generate(self, topic: str) -> Script:
        feedback = ""
        profile = config.narration_profile(self.lang, self.timeline.total_duration + config.TAIL_HOLD)
        attempts = max(3, getattr(config, "SCRIPT_REPAIR_ATTEMPTS", 2))
        for _ in range(attempts):
            script = self._assemble(topic, await self.llm.generate_script(topic, self.system_prompt() + feedback, self.schema))
            problems = validate_script(script, self.timeline, mode=self.mode)
            if not problems: return script
            scale_note = " Valid camera scales from widest to narrowest: wide, medium, close, macro, micro, nano (adjacent shots must differ by at most 1 step)." if any("scale jump" in p for p in problems) else ""
            feedback = (
                f"\nReturn the complete corrected JSON object. Repair every violation exactly: {'; '.join(problems)}.{scale_note} "
                f"Your previous draft had {script.word_count} words; adjust your 5 beat texts so the total word count strictly falls within {profile['min']}..{profile['max']} words."
            )
        raise ProviderError("LLM script failed validation: " + feedback.removeprefix("\nReturn the complete corrected JSON object. Repair every violation exactly: "))

    def _assemble(self, topic: str, payload: dict[str, Any]) -> Script:
        beats = [Beat(int(item.get("index", i + 1)), sanitize_eli12_narration(str(item.get("text") or "")), str(item.get("role") or "default"), list(item.get("emphasis") or [])) for i, item in enumerate(payload.get("beats") or [])]
        shots = []
        prior: Shot | None = None
        opening_anchor_id = ""
        contextual: dict[str, object] = {}
        payload_shots = payload.get("shots") or []
        for index, item in enumerate(payload_shots, start=1):
            start, end = self.timeline.shot_window(index)
            merged = dict(item)
            # These fields are LLM-authored input, not optional style overrides.
            # Strip model-authored camera commands and prohibited realism language
            # before validation and before the canonical compiler appends them to
            # endpoint/motion prompts.
            for field_name in (
                "start_image_prompt", "end_image_prompt", "motion_prompt",
                "subject_description", "detail_target", "continuity_anchor",
                "entry_state", "exit_state", "proof_on_screen", "dominant_event",
            ):
                if field_name in merged:
                    merged[field_name] = _canonicalize_model_brief(merged.get(field_name), mode=self.mode)
            if isinstance(merged.get("quality_critical"), list):
                merged["quality_critical"] = [_canonicalize_model_brief(item, mode=self.mode) for item in merged["quality_critical"]]
            if index == 1 and str(merged.get("presentation_mode") or "") == "contextual_opening_anchor":
                contextual = {
                    "contextual_anchor_id": str(merged.get("contextual_anchor_id") or f"ctx_{merged.get('subject_id') or 'subject'}"),
                    "contextual_anchor_subject_id": str(merged.get("contextual_anchor_subject_id") or merged.get("subject_id") or "contextual_subject"),
                    "contextual_anchor_kind": str(merged.get("contextual_anchor_kind") or "science_subject"),
                    "contextual_anchor_appearance_contract": str(merged.get("contextual_anchor_appearance_contract") or "Stable roster identity; closed neutral mouth; no dialogue, lip-sync, or text."),
                }
                contextual["contextual_anchor_prompt_sha256"] = hashlib.sha256(
                    (str(contextual["contextual_anchor_subject_id"]) + "\n" + str(contextual["contextual_anchor_appearance_contract"])).encode("utf-8")
                ).hexdigest()
                merged.update(contextual)
                merged.setdefault("mechanism_anchor_id", str(merged.get("continuity_anchor") or "mechanism"))
                merged.setdefault("contextual_anchor_roster_ids", ["environment_void", contextual["contextual_anchor_subject_id"]])
                merged.setdefault("contextual_anchor_sheet_ids", list(merged["contextual_anchor_roster_ids"]))
            elif index == 1:
                # The opening identity is compiler-owned so every new run has a
                # stable roster key even when an LLM omits the optional mode.
                merged["presentation_mode"] = "opening_anchor"
                opening_anchor_id = str(merged.get("opening_anchor_id") or merged.get("subject_id") or "opening_subject")
                merged["opening_anchor_id"] = opening_anchor_id
            elif str(merged.get("presentation_mode") or "mechanism") == "return_to_opening_anchor_payoff":
                merged["opening_anchor_id"] = opening_anchor_id
                merged["endpoint_mode"] = "first_only"
                merged.setdefault("endpoint_reason", "Terminal opening-anchor payoff avoids a morph from the preceding mechanism.")
            elif str(merged.get("presentation_mode") or "mechanism") == "return_to_contextual_anchor_payoff":
                merged.update(contextual)
                merged["subject_id"] = str(contextual.get("contextual_anchor_subject_id") or merged.get("subject_id") or "contextual_subject")
                mode = str(merged.get("endpoint_mode") or "")
                if mode != "first_last":
                    merged["endpoint_mode"] = "first_only"
                merged.setdefault("endpoint_reason", "Terminal contextual-anchor payoff connects back to the opening contextual subject.")
            else:
                if merged.get("presentation_mode") in {"opening_anchor", "contextual_opening_anchor"}:
                    merged["presentation_mode"] = "mechanism"
            merged["visual_domain"] = _domain(merged.get("visual_domain"))
            if index < len(payload_shots) and merged.get("endpoint_mode") == "first_only" and not str(merged.get("endpoint_reason") or "").strip():
                merged["endpoint_mode"] = "first_last"
            if merged.get("marker_type") in {"arrow", "trajectory"}:
                mq = _quadrant(merged.get("marker_quadrant"))
                tq = _quadrant(merged.get("target_quadrant"))
                if mq not in {"center", "lower_center"}:
                    chosen = mq
                elif tq not in {"center", "lower_center"}:
                    chosen = tq
                else:
                    chosen = "top_right"
                merged["marker_quadrant"] = chosen
                merged["target_quadrant"] = chosen
                merged["end_target_quadrant"] = chosen
                pos = str(merged.get("proof_on_screen") or "")
                if not (pos.startswith("ANNOTATION REQUIRED:") or any(k in pos.casefold() for k in ("arrow", "trajectory", "vector", "direction", "flow", "pressure", "force", "marker"))):
                    merged["proof_on_screen"] = f"ANNOTATION REQUIRED: {pos or 'directional flow vector'}"
            if self.mode.single_shot_human_anchor and index > 1 and _is_human_subject(merged):
                # The post-establish rule is compiler-owned: raw LLM labels such
                # as "mechanical" cannot authorize an exterior human shot.
                merged["visual_domain"] = "anatomical"
            merged.update({"block": index, "t_start": start, "t_end": end})
            prior_states: list[tuple[list[str], str]] = []
            for s in shots:
                if s.exit_state:
                    s_subjects = list(dict.fromkeys([s.subject_id] + list(s.secondary_subject_ids or [])))
                    prior_states.append((s_subjects, s.exit_state))
            merged["prior_exit_states"] = prior_states
            shot = Shot.from_dict(merged)
            if prior and shot.transition_kind == "same_subject" and (
                shot.subject_id != prior.subject_id or shot.continuity_anchor != prior.continuity_anchor
            ):
                # A changed identity/anchor cannot be a same-subject continuation.
                # Preserve the authored change as an explicit Match-Cut instead of
                # accepting a contradictory transition label.
                shot.transition_kind = "subject_change"
            elif prior and shot.transition_kind == "same_subject" and (
                shot.subject_id == prior.subject_id and (shot.scale != prior.scale or shot.camera_angle != prior.camera_angle)
            ):
                # Same subject but scale or camera angle differs across shots: this is a genuine scale transition.
                shot.transition_kind = "scale_transition"
            elif prior and shot.transition_kind == "scale_transition" and (
                shot.subject_id != prior.subject_id and shot.continuity_anchor != prior.continuity_anchor
            ):
                # A scale transition requires the same underlying subject or anchor.
                # When both subject_id and continuity_anchor differ completely, it is
                # an intentional Match-Cut to a new subject, not a scale zoom.
                shot.transition_kind = "subject_change"
            elif prior and shot.transition_kind in {"subject_change", "scale_transition"} and (
                shot.subject_id == prior.subject_id and shot.continuity_anchor == prior.continuity_anchor
            ):
                # Reverse correction: the LLM labelled this as a subject change or
                # scale transition, but both subject_id and continuity_anchor are
                # identical to the prior shot. A real scale_transition is valid only
                # when the scale or camera angle actually changes; otherwise it's same_subject.
                if shot.transition_kind == "scale_transition" and (shot.scale != prior.scale or shot.camera_angle != prior.camera_angle):
                    pass  # genuine scale transition with identical subject — keep it
                elif shot.scale != prior.scale or shot.camera_angle != prior.camera_angle:
                    shot.transition_kind = "scale_transition"
                else:
                    shot.transition_kind = "same_subject"
            elif prior and shot.transition_kind == "scale_transition" and shot.scale == prior.scale and shot.camera_angle == prior.camera_angle:
                if shot.location_id != prior.location_id:
                    shot.transition_kind = "location_change"
                else:
                    shot.transition_kind = "subject_change"
            shots.append(shot)
            prior = shot
        youtube = payload.get("youtube") if isinstance(payload.get("youtube"), dict) else None
        return Script(topic, beats, shots, self.lang, self.timeline, mode=self.mode.name, youtube=youtube)

    def _validate(self, script: Script) -> list[str]:
        return validate_script(script, self.timeline, mode=self.mode)


def annotate_words(beats: list[Beat], words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    emphasis = {token.casefold() for beat in beats for token in beat.emphasis}
    single_word_emphasis = set(emphasis)
    for phrase in list(emphasis):
        for part in re.findall(r"[\w']+", phrase):
            if len(part) >= 4:
                single_word_emphasis.add(part.casefold())

    beat_tokens: list[tuple[str, str, str, str]] = []
    for beat in beats:
        raw_role = str(getattr(beat, "role", "") or "default").strip()
        role_low = raw_role.casefold()
        if role_low.startswith(("witness", "historical_witness", "interviewee")):
            speaker = "witness"
            if ":" in raw_role:
                speaker_label = raw_role.split(":", 1)[1].strip()
            else:
                speaker_label = "Historical Witness"
        else:
            speaker = "nova"
            speaker_label = getattr(config, "EXPLORER_CHARACTER_NAME", "Nova") or "Nova"
        toks = re.findall(r"[\w']+", str(beat.text or "").casefold(), flags=re.UNICODE)
        if not toks:
            toks = [""]
        for tok in toks:
            beat_tokens.append((tok, raw_role, speaker, speaker_label))

    annotated: list[dict[str, Any]] = []
    cursor = 0
    total_bt = len(beat_tokens)
    total_w = max(1, len(words))

    for idx, word in enumerate(words):
        raw_text = str(word.get("text") or "")
        clean_tok = re.sub(r"[^\w']", "", raw_text.casefold(), flags=re.UNICODE)
        is_emp = raw_text.casefold() in single_word_emphasis or clean_tok in single_word_emphasis

        if total_bt > 0:
            matched_pos = None
            for look in range(cursor, min(total_bt, cursor + 6)):
                if beat_tokens[look][0] == clean_tok and clean_tok:
                    matched_pos = look
                    break
            if matched_pos is not None:
                cursor = matched_pos + 1
                _, b_role, b_speaker, b_label = beat_tokens[matched_pos]
            else:
                prop_idx = min(total_bt - 1, max(cursor, int(idx * total_bt / total_w)))
                _, b_role, b_speaker, b_label = beat_tokens[prop_idx]
        else:
            b_role, b_speaker, b_label = "default", "nova", "Nova"

        annotated.append({
            **word,
            "is_emphasis": bool(word.get("is_emphasis")) or is_emp,
            "role": str(word.get("role") or b_role),
            "speaker": str(word.get("speaker") or b_speaker),
            "speaker_label": str(word.get("speaker_label") or b_label),
        })
    return annotated

