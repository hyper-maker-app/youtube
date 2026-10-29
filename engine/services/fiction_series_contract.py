"""Fail-closed fiction-series rules, kept separate from legacy explorer code."""
from __future__ import annotations

from copy import deepcopy


STATIC_MOTION_TREATMENTS = {"2.5d_parallax", "ken_burns_push_pan", "authored_detail_reveal", "map_route_trace", "controlled_rack_focus_simulation"}
LEGACY_TOKENS = ("nova", "defne", "hawara", "virtual explorer", "historical witness")


def assert_no_legacy_contamination(value: object) -> None:
    found = [token for token in LEGACY_TOKENS if token in str(value).casefold()]
    if found:
        raise ValueError("Legacy explorer contamination in fiction_series: " + ", ".join(found))


def required_character_fields(character: dict) -> None:
    required = ("id", "identity", "motivation", "short_term_goal", "long_term_value", "fear_or_risk", "decision_style", "visual_identity", "wardrobe_states", "inventory_states", "damage_or_condition_states", "location_states", "allowed_state_transitions")
    missing = [key for key in required if key not in character or character[key] in (None, "")]
    if missing:
        raise ValueError("Canonical character is missing fields: " + ", ".join(missing))


def validate_story_arc(master: dict) -> None:
    scenes = master["scenes"]
    midpoint = [s for s in scenes if s.get("midpoint_relation") == "turning_point"]
    if len(midpoint) != 1 or not midpoint[0].get("character_action") or not midpoint[0].get("consequence"):
        raise ValueError("Fiction manuscript requires one decision-and-consequence midpoint turning point")
    payoff = [s for s in scenes if s.get("midpoint_relation") == "final_payoff"]
    if len(payoff) != 1 or payoff[0] is not scenes[-1] or not payoff[0].get("goal_linked_payoff"):
        raise ValueError("Final scene must be a goal-linked fiction payoff")


def normalize_static_insert(scene: dict) -> dict:
    insert = deepcopy(scene.get("static_insert") or {})
    if scene.get("media_type") in {"illustrated_insert", "info_card"} and insert.get("motion_treatment") not in STATIC_MOTION_TREATMENTS:
        raise ValueError("Static insert needs an authored non-decorative motion treatment")
    return insert
