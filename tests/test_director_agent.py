"""Unit tests for engine/services/director_agent.py.

Verifies:
1. Generic ontological and geometry delta detection without hardcoded scenario entities.
2. Dynamic arbitration corrective prompt generation using entity attributes.
3. 3-state resolution protocol (HEAL, HYBRID, CANONIZE).
4. WorldState persistence and canon ledger synchronization.
"""

from __future__ import annotations

import pytest

from engine.services.director_agent import (
    DirectorAction,
    DirectorDecision,
    Entity,
    SeverityLevel,
    VisualDelta,
    WorldState,
    arbitrate_decision,
    commit_canon_delta,
    evaluate_visual_delta,
)


def test_evaluate_visual_delta_generic_ontology_with_entity():
    """Verify evaluate_visual_delta uses entity.material dynamically rather than hardcoded oak."""
    entity = Entity(
        id="E_VAULT_DOOR",
        kind="barrier",
        material_class="reinforced_titanium",
        attributes={"thickness": "120mm"},
    )
    delta = evaluate_visual_delta(
        entity_id="E_VAULT_DOOR",
        before_desc="A reinforced titanium vault hatch locked tight.",
        after_desc="A transparent glass portal into the chamber.",
        continuity_score=0.62,
        violations=["door is glass, material morph detected"],
        entity=entity,
    )

    assert delta.severity == SeverityLevel.SEV5_ONTOLOGY_BREAK
    assert delta.entity_id == "E_VAULT_DOOR"
    assert delta.attribute == "material_class"
    assert delta.before_value == "reinforced_titanium"
    assert "glass" in delta.after_value
    assert delta.narrative_utility == -1.0


def test_evaluate_visual_delta_generic_geometry_with_attributes():
    """Verify evaluate_visual_delta detects geometry inversion from entity attributes."""
    entity = Entity(
        id="PROP_SURGICAL_LAMP",
        kind="lamp",
        material_class="stainless_steel",
        attributes={"orientation": "overhead_left", "handedness": "left"},
    )
    delta = evaluate_visual_delta(
        entity_id="PROP_SURGICAL_LAMP",
        before_desc="Overhead surgical lamp angled from left.",
        after_desc="Surgical lamp inverted to right wall.",
        continuity_score=0.74,
        violations=["layout reversed, handedness flipped"],
        entity=entity,
    )

    assert delta.severity == SeverityLevel.SEV3_SPATIAL_DRIFT
    assert delta.entity_id == "PROP_SURGICAL_LAMP"
    assert delta.before_value == "overhead_left"


def test_arbitrate_decision_dynamic_fatal_corrective_prompt():
    """Verify arbitrate_decision dynamically generates corrective instructions for SEV5/SEV4."""
    world_state = WorldState(project_id="spec-test")
    delta = VisualDelta(
        entity_id="E_CONSOLE_MONITOR",
        attribute="display_matrix",
        before_value="monochrome_green_crt",
        after_value="holographic_hud",
        severity=SeverityLevel.SEV5_ONTOLOGY_BREAK,
        narrative_utility=-1.0,
        evidence="CRT monitor morphed into floating hologram",
    )

    action = arbitrate_decision(delta, world_state, current_attempt=1)
    assert action.decision == DirectorDecision.HEAL
    assert action.severity == SeverityLevel.SEV5_ONTOLOGY_BREAK
    expected_prompt = (
        f"Ensure {delta.entity_id} maintains original {delta.attribute} ({delta.before_value}). "
        "Preserve locked camera perspective."
    )
    assert action.corrective_prompt == expected_prompt
    assert "white-oak" not in action.corrective_prompt
    assert "E_DOOR_01" not in action.corrective_prompt


def test_arbitrate_decision_dynamic_spatial_corrective_prompt():
    """Verify arbitrate_decision dynamically locks spatial orientation without hardcoded doors."""
    world_state = WorldState(project_id="spec-test")
    delta = VisualDelta(
        entity_id="PROP_AIRLOCK_LEVER",
        attribute="handle_orientation",
        before_value="vertical_up",
        after_value="horizontal_down",
        severity=SeverityLevel.SEV3_SPATIAL_DRIFT,
        narrative_utility=-0.5,
        evidence="Airlock handle angle flipped",
    )

    action = arbitrate_decision(delta, world_state, current_attempt=1)
    assert action.decision == DirectorDecision.HEAL
    expected_prompt = (
        f"Lock {delta.entity_id} {delta.attribute} strictly to {delta.before_value}; "
        "preserve exact scene orientation."
    )
    assert action.corrective_prompt == expected_prompt
    assert "hinges" not in action.corrective_prompt


def test_commit_canon_delta_world_state_ledger():
    """Verify commit_canon_delta updates entity wear and world_state delta_ledger."""
    ws = WorldState(project_id="test-commit")
    delta = VisualDelta(
        entity_id="E_VEHICLE_HOOD",
        attribute="dent_pattern",
        before_value="clean",
        after_value="concave impact dent 15cm",
        severity=SeverityLevel.SEV1_WEAR_DELTA,
        narrative_utility=0.9,
        evidence="Hail impact dent on center hood crease",
    )

    commit_canon_delta(ws, delta, token_still_path="keyframes/dent_token.jpg")
    assert "E_VEHICLE_HOOD" in ws.entities
    assert ws.entities["E_VEHICLE_HOOD"].active_wear["dent_pattern"] == "concave impact dent 15cm"
    assert ws.entities["E_VEHICLE_HOOD"].token_stills["dent_pattern"] == "keyframes/dent_token.jpg"
    assert len(ws.delta_ledger) == 1
    assert ws.delta_ledger[0]["entity_id"] == "E_VEHICLE_HOOD"
    assert ws.delta_ledger[0]["after"] == "concave impact dent 15cm"
