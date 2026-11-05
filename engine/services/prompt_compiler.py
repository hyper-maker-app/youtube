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
) -> str:
    """Compile photorealistic documentary frame prompt enforcing aspect ratio and visual mandates."""
    parts = [
        f"Photorealistic 8k 35mm documentary frame of {scene_description.strip().rstrip('. ')}.",
    ]
    if proof_target.strip():
        parts.append(f"Visible physical evidence: {proof_target.strip().rstrip('. ')}.")
    parts.append(f"Atmospheric volumetric lighting, {aspect_ratio} widescreen, authentic textures, deep shadow contrast.")
    if action_description.strip():
        parts.append(f"Action: {action_description.strip().rstrip('. ')}.")

    parts.append(
        "STRICT VISUAL MANDATE: ZERO text, ZERO printed letters, ZERO typography, ZERO date stamps, "
        "ZERO year numbers written on image, ZERO name plaques, ZERO title banners, ZERO graphic cards, "
        "ZERO caption boxes, ZERO lower thirds, ZERO subtitles, ZERO watermarks. "
        "Pure photographic 35mm cinema only without written words."
    )
    if truth_sheet and truth_sheet.prohibited_anachronisms:
        for forbidden in truth_sheet.prohibited_anachronisms[:6]:
            if forbidden.lower() not in " ".join(parts).lower():
                parts.append(f"NO {forbidden}.")
    return " ".join(parts)


def format_veo_cinematography_prompt(
    shot_type: str,
    subject_labor: str,
    lighting: str = "golden hour sunlight, volumetric dust motes dancing in air",
    historical_atmosphere: str = "authentic documentary atmosphere",
    camera_vector: str = "slow cinematic dolly in",
    fps: str = "24fps",
    era: str = "default",
) -> str:
    """Format prompt adhering strictly to Veo Cinematography ordering:

    [Shot Type] + [Subject & purposeful labor] + [Lighting] + [Atmosphere] + [Camera vector] + [Format]
    """
    st = (shot_type or "Cinematic medium tracking shot").strip().rstrip(",. ")
    subj = subject_labor.strip().rstrip(",. ")
    light = (lighting or "golden hour sunlight, volumetric dust motes dancing in air").strip().rstrip(",. ")
    atm = (historical_atmosphere or "authentic documentary atmosphere").strip().rstrip(",. ")
    vec = (camera_vector or "slow cinematic dolly in").strip().rstrip(",. ")

    return f"{st}, {subj}, {light}, {atm}, {vec}, {fps} motion blur, 35mm photorealistic documentary cinema."


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


def build_contrastive_barrier_clause(
    entity_id: str = "E_DOOR_01",
    material: str = "solid 44mm quarter-sawn white-oak slab",
) -> str:
    """Return contrastive material clause ensuring the diffusion model never renders an opaque door as glass."""
    return (
        f"{entity_id} is a {material}, 100% opaque timber through-and-through, vertical grain. "
        f"It is NOT glass, NOT frosted, NOT a French door, NOT a window in a doorway. "
        f"The hallway behind is completely blocked by the timber slab; specular highlights are surface varnish sheen only, zero optical transmission."
    )


def build_scoped_negatives_for_barrier() -> str:
    """Return targeted negative prompt tokens preventing door-to-window metamorphosis."""
    return (
        "glass door, French door, sidelights, transom glass, transparent door slab, "
        "interior visible through door, door morphing into window, cracked door pane, "
        "frosted-glass entry, window in door core, modern glass sliding door"
    )


def inject_active_deltas_with_visibility_gating(
    prompt: str,
    world_state: Any,
    shot_spec: dict[str, Any] | None = None,
) -> str:
    """Inject active canon deltas strictly if the entity is visible in the frame (Grok 4.6 Mandate).

    Prevents latent space pollution (e.g. injecting door cracks into a macro shot of floor bottles).
    """
    if not world_state or not getattr(world_state, "delta_ledger", None):
        return prompt

    clean = prompt
    p_lower = prompt.lower()
    shot_spec = shot_spec or {}
    declared_visible = set(shot_spec.get("visible_entities", []))
    if shot_spec.get("focus_entity"):
        declared_visible.add(shot_spec["focus_entity"])

    injected_deltas = []
    for delta in world_state.delta_ledger:
        ent_id = delta.get("entity_id", "")
        # Check if entity is visible in frame (either explicitly declared or lexically present)
        is_visible = (
            ent_id in declared_visible
            or ("door" in ent_id.lower() and any(k in p_lower for k in ("door", "portal", "barrier", "entry")))
            or ("bottle" in ent_id.lower() and any(k in p_lower for k in ("bottle", "floor", "tripwire")))
            or ("peep" in ent_id.lower() and any(k in p_lower for k in ("peephole", "optic", "lens")))
            or ("win" in ent_id.lower() and any(k in p_lower for k in ("window", "pane", "glass")))
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
    barrier_entity_id: str = "E_DOOR_01",
    world_state: Any | None = None,
    shot_spec: dict[str, Any] | None = None,
) -> str:
    """Compile visual prompt according to UDSE v4.3 standards:
    1. Lints against unpartitioned coplanar conflation.
    2. If barrier is present, attaches contrastive material clause.
    3. Injects active canon deltas strictly if entities are visible in the frame (Visibility Gating).
    4. Guarantees photographic realism without program syntax leakage.
    """
    clean_p = visual_prompt.strip()
    # Strip any accidental brackets like [INVARIANT: ...]
    clean_p = re.sub(r"\[INVARIANT:[^\]]*\]", "", clean_p, flags=re.IGNORECASE).strip()

    # Apply dispatch linter
    lint_prompt_for_unpartitioned_bleed(clean_p)

    # Attach contrastive barrier anchor if barrier is mentioned
    if "door" in clean_p.lower() and "contrastive" not in clean_p.lower() and "opaque timber" not in clean_p.lower():
        anchor = build_contrastive_barrier_clause(entity_id=barrier_entity_id)
        clean_p = f"{clean_p}. {anchor}"

    # Apply Visibility Gating on active deltas
    if world_state:
        clean_p = inject_active_deltas_with_visibility_gating(clean_p, world_state, shot_spec)

    return clean_p
