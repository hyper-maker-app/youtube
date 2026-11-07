"""Autonomous AI Director Agent for Grok Imagine Cinematic Studio (Grok 4.6 UDSE v4.2).

Arbitrates visual boundary QA reports and emergent diffusion video deltas across
4 orthogonal axes:
1. Ontology (Does an entity change kind? e.g. oak door -> glass door) -> Fatal -> HEAL
2. Geometry & Camera Grammar (180-degree axis break, eyeline mismatch) -> Fatal -> HEAL
3. Causal Continuity (Unexplained state jump: locked -> open) -> Fatal -> HEAL
4. Narrative Utility (Photoreal micro-continuity: wood splinter, dent, flicker) -> CANONIZE

Implements 3-state resolution:
- HEAL: Surgical re-roll with first-frame anchor + scoped negative + 2-attempt cap
- CANONIZE: Commit structured delta, crop token still, patch downstream visible scenes
- HYBRID: Freeze legal entities, heal illegal region in tighter/masked pass
"""

from __future__ import annotations

import enum
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SeverityLevel(enum.IntEnum):
    SEV0_COSMETIC_EMERGENT = 0   # Grain, dust motes, flicker cadence, smear shape -> CANONIZE
    SEV1_WEAR_DELTA = 1          # Dent, chip, blood smear, condensation, splinter map -> CANONIZE
    SEV2_PROP_STATE_SHIFT = 2    # Latch position, peephole cover, bottle knocked -> HYBRID
    SEV3_SPATIAL_DRIFT = 3       # Furniture migrated, door handedness flipped -> HEAL
    SEV4_CAMERA_GRAMMAR = 4      # 180 break, eyeline mismatch, impossible paraxial jump -> HEAL
    SEV5_ONTOLOGY_BREAK = 5      # Material class change (oak -> glass), set morph -> HEAL
    SEV6_NARRATIVE_FATAL = 6     # Plot object missing/transformed, wound healed -> HEAL


class DirectorDecision(str, enum.Enum):
    HEAL = "heal"
    CANONIZE = "canonize"
    HYBRID = "hybrid"


@dataclass
class VisualDelta:
    entity_id: str
    attribute: str
    before_value: Any
    after_value: Any
    severity: SeverityLevel
    narrative_utility: float  # -1.0 (destructive) to +1.0 (high photoreal value)
    evidence: str = ""
    token_crop_path: Optional[str] = None


@dataclass
class DirectorAction:
    decision: DirectorDecision
    severity: SeverityLevel
    reason: str
    corrective_prompt: str = ""
    scoped_negatives: list[str] = field(default_factory=list)
    reframe_strategy: str = "keep_framing"  # 'keep_framing' | 'tighter_mcu' | 'insert'
    max_heal_attempts: int = 2
    downstream_patch: dict[str, Any] = field(default_factory=dict)
    token_still_path: Optional[str] = None


@dataclass
class Entity:
    id: str
    kind: str = "prop"
    material_class: str = "unknown"
    opacity: float = 1.0
    transmission: float = 0.0
    scale: str = "full"
    freeze_attributes: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    active_wear: dict[str, Any] = field(default_factory=dict)
    token_stills: dict[str, str] = field(default_factory=dict)
    material: str = ""

    def __post_init__(self) -> None:
        if not self.material and self.material_class != "unknown":
            self.material = self.material_class
        elif self.material and self.material_class == "unknown":
            self.material_class = self.material


@dataclass
class WorldState:
    project_id: str
    entities: dict[str, Entity] = field(default_factory=dict)
    invariants: dict[str, Any] = field(default_factory=dict)
    delta_ledger: list[dict[str, Any]] = field(default_factory=list)
    active_camera_axis: float = 0.0  # degrees on action line

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "entities": {
                k: {
                    "id": v.id,
                    "kind": v.kind,
                    "material_class": v.material_class,
                    "material": v.material,
                    "opacity": v.opacity,
                    "transmission": v.transmission,
                    "scale": v.scale,
                    "freeze_attributes": v.freeze_attributes,
                    "attributes": v.attributes,
                    "active_wear": v.active_wear,
                    "token_stills": v.token_stills,
                }
                for k, v in self.entities.items()
            },
            "invariants": self.invariants,
            "delta_ledger": self.delta_ledger,
            "active_camera_axis": self.active_camera_axis,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldState":
        entities = {}
        for k, v in data.get("entities", {}).items():
            entities[k] = Entity(
                id=v.get("id", k),
                kind=v.get("kind", "prop"),
                material_class=v.get("material_class", "unknown"),
                material=v.get("material", ""),
                opacity=float(v.get("opacity", 1.0)),
                transmission=float(v.get("transmission", 0.0)),
                scale=v.get("scale", "full"),
                freeze_attributes=list(v.get("freeze_attributes", [])),
                attributes=dict(v.get("attributes", {})),
                active_wear=dict(v.get("active_wear", {})),
                token_stills=dict(v.get("token_stills", {})),
            )
        return cls(
            project_id=data.get("project_id", "project"),
            entities=entities,
            invariants=dict(data.get("invariants", {})),
            delta_ledger=list(data.get("delta_ledger", [])),
            active_camera_axis=float(data.get("active_camera_axis", 0.0)),
        )


def evaluate_visual_delta(
    *,
    entity_id: str,
    before_desc: str = "",
    after_desc: str = "",
    continuity_score: float = 1.0,
    violations: list[str],
    entity: Entity | None = None,
    world_state: WorldState | None = None,
) -> VisualDelta:
    """Classify a detected transition deviation into typed severity and narrative utility."""
    v_text = " ".join(violations).lower()

    target_entity = entity
    if target_entity is None and world_state is not None:
        target_entity = world_state.entities.get(entity_id)

    # 1. Ontological Break: material or kind transformed
    if any(k in v_text for k in ("glass door", "wood to glass", "material morph", "door is glass", "transparent door", "material change", "transformed into")):
        mat_before = "canonical_material"
        if target_entity:
            mat_before = (
                getattr(target_entity, "material", "")
                or getattr(target_entity, "material_class", "")
                or target_entity.attributes.get("material", "")
                or mat_before
            )
        mat_after = "unauthorized_material"
        for candidate in ("glass", "transparent", "acrylic", "mesh", "open_air", "metal", "liquid"):
            if candidate in v_text:
                mat_after = f"{candidate}_structure"
                break

        return VisualDelta(
            entity_id=entity_id,
            attribute="material_class",
            before_value=mat_before,
            after_value=mat_after,
            severity=SeverityLevel.SEV5_ONTOLOGY_BREAK,
            narrative_utility=-1.0,
            evidence=f"Entity {entity_id} material transformed from {mat_before} to {mat_after}.",
        )

    # 2. Camera Grammar / 180 break
    if any(k in v_text for k in ("180 break", "axis break", "eyeline mismatch", "jump cut", "reversed angle")):
        return VisualDelta(
            entity_id=entity_id,
            attribute="camera_axis",
            before_value="line_of_action_left",
            after_value="line_of_action_right",
            severity=SeverityLevel.SEV4_CAMERA_GRAMMAR,
            narrative_utility=-0.8,
            evidence="Camera crossed the 180-degree action line.",
        )

    # 3. Spatial Drift / Geometry
    if any(k in v_text for k in ("hinge side flipped", "room scale change", "geometry inversion", "handedness flipped", "axis flipped", "layout reversed")):
        geom_attr = "spatial_geometry"
        geom_before = "canonical_orientation"
        geom_after = "inverted_orientation"

        if target_entity and hasattr(target_entity, "attributes") and target_entity.attributes:
            for k in ("geometry", "orientation", "handedness", "hinge_side"):
                if k in target_entity.attributes:
                    geom_attr = k
                    geom_before = target_entity.attributes[k]
                    geom_after = f"inverted_{geom_before}"
                    break

        return VisualDelta(
            entity_id=entity_id,
            attribute=geom_attr,
            before_value=geom_before,
            after_value=geom_after,
            severity=SeverityLevel.SEV3_SPATIAL_DRIFT,
            narrative_utility=-0.5,
            evidence=f"Set geometry or prop handedness flipped for {entity_id}.",
        )

    # 4. Prop State Shift
    if any(k in v_text for k in ("latch moved", "flashlight toggled", "bottle knocked")):
        return VisualDelta(
            entity_id=entity_id,
            attribute="prop_state",
            before_value="static",
            after_value="shifted",
            severity=SeverityLevel.SEV2_PROP_STATE_SHIFT,
            narrative_utility=0.2,
            evidence="Diegetic prop shifted position or state.",
        )

    # 5. Wear Delta: authentic scratches, fractures, tape tension
    if any(k in v_text for k in ("splinter", "crack in wood", "tape peeled", "blood", "dent", "wear")):
        return VisualDelta(
            entity_id=entity_id,
            attribute="active_wear",
            before_value="clean",
            after_value="wear_pattern",
            severity=SeverityLevel.SEV1_WEAR_DELTA,
            narrative_utility=0.9,
            evidence="Photoreal emergent wear, splinter, or tension damage.",
        )

    # 6. Default: Cosmetic Emergent
    return VisualDelta(
        entity_id=entity_id,
        attribute="cosmetic_texture",
        before_value="nominal",
        after_value="emergent_grain",
        severity=SeverityLevel.SEV0_COSMETIC_EMERGENT,
        narrative_utility=0.5,
        evidence="Natural ambient variations in lighting, grain, or dust motes.",
    )


def arbitrate_decision(
    delta: VisualDelta,
    world_state: WorldState,
    current_attempt: int = 1,
) -> DirectorAction:
    """Core autonomous director arbitration function (Grok 4.6 UDSE v4.2).

    Rules:
    - SEV4 - SEV6: Must HEAL. Ontology / grammar errors are fatal.
    - SEV3: HEAL geometry; if attempt >= 2, reframe to tighter shot.
    - SEV2: HYBRID. Canonize state if causal stitch possible.
    - SEV0 - SEV1: CANONIZE. Record into WorldState, update downstream prompts.
    """
    # Fatal violations -> HEAL
    if delta.severity >= SeverityLevel.SEV4_CAMERA_GRAMMAR:
        scoped_negs = [
            "glass door", "French door", "sidelights", "transparent door slab",
            "seeing through the door", "door morphing into a window", "frosted-glass entry",
            "reverse 180 camera angle", "distorted anatomy",
        ]
        reframe = "tighter_mcu" if current_attempt >= 2 else "keep_framing"
        return DirectorAction(
            decision=DirectorDecision.HEAL,
            severity=delta.severity,
            reason=f"Fatal continuity breach ({delta.severity.name}): {delta.evidence}",
            corrective_prompt=(
                f"Ensure {delta.entity_id} maintains original {delta.attribute} ({delta.before_value}). "
                "Preserve locked camera perspective."
            ),
            scoped_negatives=scoped_negs,
            reframe_strategy=reframe,
            max_heal_attempts=2,
        )

    # Spatial drift -> HEAL geometry
    if delta.severity == SeverityLevel.SEV3_SPATIAL_DRIFT:
        return DirectorAction(
            decision=DirectorDecision.HEAL,
            severity=delta.severity,
            reason=f"Spatial geometry flipped ({delta.evidence})",
            corrective_prompt=f"Lock {delta.entity_id} {delta.attribute} strictly to {delta.before_value}; preserve exact scene orientation.",
            scoped_negatives=["hinge on left", "reversed layout"],
            reframe_strategy="tighter_mcu" if current_attempt >= 2 else "keep_framing",
        )

    # Prop State Shift -> HYBRID
    if delta.severity == SeverityLevel.SEV2_PROP_STATE_SHIFT:
        return DirectorAction(
            decision=DirectorDecision.HYBRID,
            severity=delta.severity,
            reason=f"Diegetic prop state shift ({delta.evidence}); committing state.",
            downstream_patch={delta.entity_id: {delta.attribute: delta.after_value}},
        )

    # Cosmetic / Wear Delta -> CANONIZE
    logger.info(f"[DirectorAgent] CANONIZING photoreal emergent delta: {delta.evidence}")
    return DirectorAction(
        decision=DirectorDecision.CANONIZE,
        severity=delta.severity,
        reason=f"High-utility photoreal emergence ({delta.severity.name}): {delta.evidence}",
        downstream_patch={delta.entity_id: {delta.attribute: delta.after_value}},
    )


def commit_canon_delta(
    world_state: WorldState,
    delta: VisualDelta,
    token_still_path: Optional[str] = None,
) -> None:
    """Record verified emergent delta into WorldState ledger for downstream injection."""
    ent = world_state.entities.get(delta.entity_id)
    if not ent:
        ent = Entity(id=delta.entity_id, kind="prop", material_class="generic")
        world_state.entities[delta.entity_id] = ent

    ent.active_wear[delta.attribute] = delta.after_value
    if token_still_path:
        ent.token_stills[delta.attribute] = token_still_path

    world_state.delta_ledger.append({
        "entity_id": delta.entity_id,
        "attribute": delta.attribute,
        "before": delta.before_value,
        "after": delta.after_value,
        "severity": int(delta.severity),
        "evidence": delta.evidence,
        "token_still": token_still_path,
    })
    logger.info(f"[DirectorAgent] Committed {delta.entity_id}.{delta.attribute} to WorldState ledger.")
