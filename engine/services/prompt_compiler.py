"""Reinforced prompt engineering compiler incorporating documentary and UDSE standards.

Enforces:
1. Pure execution pipeline: Zero hardcoded creative lexical substitutions or narrative dictionaries.
2. Structured multi-shot motion syntax formatting.
3. UDSE v4.3 standards: Entity-Attribute Binding, Dispatch Linter, and Contrastive Anchoring.

Zero network/transport calls are made in this module (strictly AST-clean).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from services.character import CharacterProfile, get_active_character


@dataclass
class HistoricalTruthSheet:
    era: str = "default"
    prohibited_anachronisms: tuple[str, ...] = ()


# Empty neutral constants for zero-hardcode invariant
MOVEMENT_LOCK_SUFFIX: str = ""
ATMOSPHERIC_MOTION_SUFFIX: str = ""


def apply_clothing_lock(prompt: str, era: str = "default", wardrobe: str = "") -> str:
    """Pass through prompt or optionally attach explicit parametric wardrobe description.

    Engines do not inject hardcoded era clothing strings (kalasiris, chiton, kabalak, etc.);
    all stylistic and wardrobe directives originate from markdown skills or scenario payloads.
    """
    cleaned = prompt.strip()
    if wardrobe and wardrobe.casefold() not in cleaned.casefold():
        cleaned = f"{cleaned.rstrip('. ')}, wearing {wardrobe}."
    return cleaned


def apply_movement_lock(motion_prompt: str, suffix: str = "") -> str:
    """Pass through motion prompt without hardcoded narrative text injection."""
    cleaned = motion_prompt.strip()
    if suffix and suffix not in cleaned:
        cleaned = f"{cleaned.rstrip('. ')}. {suffix.strip()}"
    return cleaned


def apply_ancient_equipment_rule(prompt: str, era: str = "default") -> str:
    """Pass through prompt without creative lexical substitution."""
    return prompt.strip()


def format_multi_shot_prompt(
    shot1_action: str,
    shot2_action: str,
    shot1_window: tuple[float, float] = (0.0, 3.0),
    shot2_window: tuple[float, float] = (3.0, 6.0),
) -> str:
    """Format structured multi-shot motion syntax for video block generation."""
    s1_start, s1_end = int(round(shot1_window[0])), int(round(shot1_window[1]))
    s2_start, s2_end = int(round(shot2_window[0])), int(round(shot2_window[1]))
    clean_s1 = shot1_action.strip().rstrip(". ")
    clean_s2 = shot2_action.strip().rstrip(". ")
    return f"SHOT 1 [{s1_start}-{s1_end}s]: {clean_s1}. | SHOT 2 [{s2_start}-{s2_end}s]: {clean_s2}."


def compile_longform_broll_prompt(
    scene_description: str,
    proof_target: str = "",
    truth_sheet: HistoricalTruthSheet | None = None,
    aspect_ratio: str = "16:9",
    action_description: str = "",
    visual_style: str = "Photorealistic 8k 35mm documentary frame",
    lighting: str = "Atmospheric volumetric lighting, authentic textures, deep shadow contrast",
) -> str:
    """Compile photorealistic frame prompt enforcing aspect ratio and visual mandates."""
    style_prefix = visual_style.strip().rstrip(". ")
    parts = [
        f"{style_prefix} of {scene_description.strip().rstrip('. ')}.",
    ]
    if proof_target.strip():
        parts.append(f"Visible physical evidence: {proof_target.strip().rstrip('. ')}.")
    light_str = lighting.strip().rstrip(". ")
    if light_str:
        parts.append(f"{light_str}, {aspect_ratio} widescreen.")
    else:
        parts.append(f"{aspect_ratio} widescreen.")
    if action_description.strip():
        parts.append(f"Action: {action_description.strip().rstrip('. ')}.")

    parts.append(
        "STRICT VISUAL MANDATE: ZERO text, ZERO printed letters, ZERO typography, ZERO date stamps, "
        "ZERO year numbers written on image, ZERO name plaques, ZERO title banners, ZERO graphic cards, "
        "ZERO caption boxes, ZERO lower thirds, ZERO subtitles, ZERO watermarks. "
        "Pure photographic cinema only without written words."
    )
    if truth_sheet and truth_sheet.prohibited_anachronisms:
        for forbidden in truth_sheet.prohibited_anachronisms[:6]:
            if forbidden.lower() not in " ".join(parts).lower():
                parts.append(f"NO {forbidden}.")
    return " ".join(parts)


def format_veo_cinematography_prompt(
    shot_type: str,
    subject_labor: str,
    lighting: str = "cinematic atmospheric lighting",
    historical_atmosphere: str = "authentic atmosphere",
    camera_vector: str = "slow cinematic dolly in",
    fps: str = "24fps",
    era: str = "default",
    visual_style: str = "photorealistic cinema",
) -> str:
    """Format prompt adhering strictly to Veo Cinematography ordering:

    [Shot Type] + [Subject & purposeful labor] + [Lighting] + [Atmosphere] + [Camera vector] + [Format]
    """
    st = (shot_type or "Cinematic medium tracking shot").strip().rstrip(",. ")
    subj = subject_labor.strip().rstrip(",. ")
    light = lighting.strip().rstrip(",. ") if lighting else ""
    atm = historical_atmosphere.strip().rstrip(",. ") if historical_atmosphere else ""
    vec = camera_vector.strip().rstrip(",. ") if camera_vector else ""
    style = visual_style.strip().rstrip(",. ") if visual_style else "photorealistic cinema"

    elements = [st, subj]
    if light:
        elements.append(light)
    if atm:
        elements.append(atm)
    if vec:
        elements.append(vec)
    elements.append(f"{fps} motion blur")
    elements.append(style)

    return ", ".join(e for e in elements if e) + "."


# ---------------------------------------------------------------------------
# UDSE v4.2: Entity-Attribute Binding (EAB), Dispatch Linter & Contrastive Anchoring
# ---------------------------------------------------------------------------


class DispatchLintError(ValueError):
    """Raised when a prompt violates spatial separation between competing materials."""


def lint_prompt_for_unpartitioned_bleed(prompt: str) -> None:
    """Deterministic AST Linter: Reject prompts that conflate door and glass/window without metric partition."""
    p_lower = prompt.lower()
    sentences = re.split(r"[.!?]\s+", p_lower)

    for s in sentences:
        has_door = bool(re.search(r"\b(door|barrier|entryway|portal)\b", s))
        has_competing_glass = bool(re.search(r"\b(cracked window|window pane|glass window|window glass)\b", s))
        if has_door and has_competing_glass:
            # Must contain explicit spatial partition keyword
            has_partition = bool(re.search(r"\b(metric|meter|meters|left wall|right wall|different wall|separate opening|out of frame)\b", s))
            if not has_partition:
                raise DispatchLintError(
                    f"DispatchLintError: Coplanar glass and door detected in sentence without metric partition: '{s[:80]}...'. "
                    "Enforce spatial separation (e.g. 'on left wall, 2.1m from door') to prevent Veo material morphing."
                )


def inject_active_deltas_with_visibility_gating(
    prompt: str,
    world_state: Any,
    shot_spec: dict[str, Any] | None = None,
) -> str:
    """Inject active canon deltas strictly if the entity is visible in the frame (Pure Engine Gating).

    Prevents latent space pollution across unrelated frames.
    Driven generically by entity registry / attributes or generic token visibility.
    """
    if not world_state or not getattr(world_state, "delta_ledger", None):
        return prompt

    clean = prompt
    p_lower = prompt.lower()
    shot_spec = shot_spec or {}
    declared_visible = set(shot_spec.get("visible_entities", []))
    if shot_spec.get("focus_entity"):
        declared_visible.add(shot_spec["focus_entity"])

    entity_source = (
        getattr(world_state, "entity_registry", None)
        or getattr(world_state, "entities", None)
    )

    injected_deltas = []
    for delta in world_state.delta_ledger:
        ent_id = delta.get("entity_id", "")
        if not ent_id:
            continue

        # Collect keywords for generic visibility gating
        entity_keywords: set[str] = set()

        # Check entity object from registry or entities dictionary
        entity_obj = None
        if isinstance(entity_source, dict):
            entity_obj = entity_source.get(ent_id)

        if entity_obj:
            if isinstance(entity_obj, dict):
                kws = entity_obj.get("keywords", [])
                kind = entity_obj.get("kind", "")
                mat = entity_obj.get("material_class", "") or entity_obj.get("material", "")
                name = entity_obj.get("name", "")
            else:
                kws = getattr(entity_obj, "keywords", [])
                kind = getattr(entity_obj, "kind", "")
                mat = getattr(entity_obj, "material_class", "") or getattr(entity_obj, "material", "")
                name = getattr(entity_obj, "name", "")

            if isinstance(kws, (list, tuple, set)):
                entity_keywords.update(str(k).lower().strip() for k in kws if k)
            if kind:
                entity_keywords.add(str(kind).lower().strip())
            if mat:
                entity_keywords.add(str(mat).lower().strip())
            if name:
                entity_keywords.add(str(name).lower().strip())

        # Generic token derivation from entity_id (e.g. ENTITY_DOOR_01 -> door, PROP_FLASHLIGHT -> flashlight)
        id_tokens = [
            token.lower().strip()
            for token in re.split(r"[_\W]+", ent_id)
            if token and not token.isdigit() and len(token) > 1 and token.lower() not in ("e", "ent", "entity", "prop")
        ]
        entity_keywords.update(id_tokens)
        entity_keywords.add(ent_id.lower().strip())

        # Generic visibility check: declared explicitly, or keyword found in prompt text
        is_visible = (
            ent_id in declared_visible
            or any(
                re.search(r"\b" + re.escape(kw) + r"\b", p_lower)
                for kw in entity_keywords
                if len(kw) > 1
            )
        )

        if is_visible:
            evidence = delta.get("evidence", "")
            attr = delta.get("attribute", "")
            after = delta.get("after", "")
            if evidence:
                injected_deltas.append(f"{ent_id} maintains {evidence}")
            elif attr and after:
                injected_deltas.append(f"{ent_id} {attr} is {after}")

    if injected_deltas:
        clean = f"{clean}. Continuous physical state: {'; '.join(injected_deltas)}."

    return clean


def compile_udse_prompt(
    visual_prompt: str,
    scene_type: str = "standard",
    world_state: Any | None = None,
    shot_spec: dict[str, Any] | None = None,
    **kwargs: Any,
) -> str:
    """Compile visual prompt according to UDSE standards:
    1. Lints against unpartitioned coplanar conflation.
    2. Injects active canon deltas strictly if entities are visible in the frame (Visibility Gating).
    3. Guarantees photographic realism without program syntax leakage.
    """
    clean_p = visual_prompt.strip()
    # Strip any accidental brackets like [INVARIANT: ...]
    clean_p = re.sub(r"\[INVARIANT:[^\]]*\]", "", clean_p, flags=re.IGNORECASE).strip()

    # Apply dispatch linter
    lint_prompt_for_unpartitioned_bleed(clean_p)

    # Apply Visibility Gating on active deltas
    if world_state:
        clean_p = inject_active_deltas_with_visibility_gating(clean_p, world_state, shot_spec)

    return clean_p

# ---------------------------------------------------------------------------
# Gemini Omni Flash 1.1 Video Prompt Compilation & Sanitization
# ---------------------------------------------------------------------------

_OMNI_FLASH_FORBIDDEN_PATTERNS = [
    re.compile(r"\btrending\s+on\s+artstation\b", re.IGNORECASE),
    re.compile(r"\bartstation\b", re.IGNORECASE),
    re.compile(r"\bunreal\s+engine(?:\s*5)?\b", re.IGNORECASE),
    re.compile(r"\bue5\b", re.IGNORECASE),
    re.compile(r"\boctane(?:\s+render)?\b", re.IGNORECASE),
    re.compile(r"\bv-?ray(?:\s+render)?\b", re.IGNORECASE),
    re.compile(r"\bhyper-?realistic\b", re.IGNORECASE),
    re.compile(r"\bhyper\s+realistic\b", re.IGNORECASE),
    re.compile(r"\bphoto-?realistic(?:\s*8k)?\b", re.IGNORECASE),
    re.compile(r"\bphoto\s+realistic(?:\s*8k)?\b", re.IGNORECASE),
    re.compile(r"\b8k(?:\s+uhd)?\b", re.IGNORECASE),
    re.compile(r"\b16k\b", re.IGNORECASE),
    re.compile(r"\b4k(?:\s+uhd)?\b", re.IGNORECASE),
    re.compile(r"\bmasterpiece\b", re.IGNORECASE),
    re.compile(r"\baward[\s-]winning\b", re.IGNORECASE),
    re.compile(r"\bbest\s+quality\b", re.IGNORECASE),
    re.compile(r"\bultra[\s-]detailed\b", re.IGNORECASE),
    re.compile(r"\bintricate\s+details\b", re.IGNORECASE),
]


def sanitize_omni_flash_prompt(prompt: str) -> str:
    """Sanitize prompt for Omni Flash by removing penalized keyword stuffing terms.

    Removes artificial quality boosters (hyperrealistic, photorealistic 8k,
    trending on artstation, unreal engine 5, octane render, etc.) while
    preserving physical and optical cinematography terminology (dolly zoom,
    locked off, macro grip, anamorphic lens flare, etc.).
    """
    if not prompt:
        return ""

    text = prompt
    for pattern in _OMNI_FLASH_FORBIDDEN_PATTERNS:
        text = pattern.sub("", text)

    # Clean up punctuation and whitespace artifacts
    text = re.sub(r"\s*,\s*(?:,\s*)+", ", ", text)
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r",\s*$", "", text)
    text = re.sub(r"^\s*[,;\s]+", "", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"([.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)

    cleaned = text.strip()
    if cleaned and not cleaned.endswith((".", "!", "?")):
        cleaned += "."

    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]

    return cleaned


def compile_omni_flash_prompt(
    subject_and_look: str,
    action: str,
    setting: str,
    camera_movement: str,
    lighting_atmosphere: str,
    audio_cue: str | None = None,
    first_frame_active: bool = False,
    unbroken_take: bool = True,
) -> str:
    """Compile structured cinematography prompt for Gemini Omni Flash 1.1 video generation.

    Syntax Order:
    [Subject & Distinct Features] + [Action / Physical Physics] + [Setting / Environment]
    + [Camera & Movement Vector] + [Lighting & Atmosphere]

    - When first_frame_active=True: Attaches explicit frame reference locking facial geometry,
      wardrobe, and physical attributes.
    - When unbroken_take=True: Appends directive preventing AI jump-cuts or unwanted montage edits.
    - When audio_cue is provided: Attaches synchronized audio cue description.
    - Cleans keyword stuffing terms via sanitize_omni_flash_prompt.
    """
    parts: list[str] = []

    if first_frame_active:
        parts.append(
            "Using the provided image reference as the starting frame, "
            "keep facial geometry, wardrobe, and physical attributes strictly identical."
        )

    # Core 5-part Omni Flash syntax:
    # [Subject & Distinct Features] + [Action / Physical Physics] + [Setting / Environment]
    # + [Camera & Movement Vector] + [Lighting & Atmosphere]
    core_items = [
        item.strip().rstrip("., ")
        for item in (subject_and_look, action, setting, camera_movement, lighting_atmosphere)
        if item and item.strip()
    ]

    if unbroken_take:
        core_items.append("one continuous shot, a single unbroken take")

    if core_items:
        core_text = ", ".join(core_items)
        if core_text and core_text[0].islower():
            core_text = core_text[0].upper() + core_text[1:]
        if not core_text.endswith((".", "!", "?")):
            core_text += "."
        parts.append(core_text)

    if audio_cue and audio_cue.strip():
        cue = audio_cue.strip().rstrip("., ")
        if cue.lower().startswith(("synchronized audio:", "audio:", "audio cue:", "sound:")):
            parts.append(f"{cue}.")
        else:
            parts.append(f"Synchronized audio: {cue}.")

    compiled = " ".join(parts)
    return sanitize_omni_flash_prompt(compiled)

