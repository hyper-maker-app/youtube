"""Unit tests for tri-modality ModeProfile system."""
from __future__ import annotations

import pytest

from services.mode_profile import ANATOMICAL, INCIDENT, MECHANICAL, detect_mode, mode_from_name
from services.script_engine import (
    Beat,
    BeatEngine,
    Script,
    Shot,
    _canonicalize_model_brief,
    compile_keyframe_prompt,
    optimize_for_flow,
    validate_script,
)
from services.asset_roster import build_roster
from timeline import TimelinePlan


def test_detect_mode_boundary_cases():
    """Verify topic-based mode detection defaults conservatively to ANATOMICAL."""
    # Definite anatomical topics
    assert detect_mode("Why Your Lungs Do Not Collapse") == ANATOMICAL
    assert detect_mode("What Happens When You Swallow a Battery") == ANATOMICAL
    assert detect_mode("The Science of Brain Freeze") == ANATOMICAL
    assert detect_mode("How Your Stomach Dissolves Metal") == ANATOMICAL

    # Definite incident topics
    assert detect_mode("Passenger Tries to Open Airplane Door Mid-Flight") == INCIDENT
    assert detect_mode("Man Arrested for Climbing the Eiffel Tower") == INCIDENT
    assert detect_mode("Frontier Flight Diverted After Passenger Disturbance") == INCIDENT
    assert detect_mode("Bank Robbery Suspect Escaped Through Tunnels") == INCIDENT

    # Mixed topic: "accident" triggers incident, user can override if needed
    assert detect_mode("Lung Damage After a Car Accident") == INCIDENT

    # Turkish signals
    assert detect_mode("Uçakta kapıyı açmaya çalışan yolcu") == INCIDENT
    assert detect_mode("Mide asidi nasıl çalışır") == ANATOMICAL

    # Definite mechanical topics
    assert detect_mode("How a Hydraulic Press Actually Works") == MECHANICAL
    assert detect_mode("What Happens Inside a Turbine Engine") == MECHANICAL
    assert detect_mode("Why Elevator Cables Never Snap") == MECHANICAL
    assert detect_mode("How Bridge Suspension Cables Handle Wind") == MECHANICAL

    # Mixed topic: "accident" triggers incident even with "engine"
    assert detect_mode("Lung Damage After a Car Accident") == INCIDENT


def test_mode_from_name():
    assert mode_from_name("anatomical") == ANATOMICAL
    assert mode_from_name("incident") == INCIDENT
    assert mode_from_name("mechanical") == MECHANICAL
    with pytest.raises(KeyError):
        mode_from_name("unknown_mode")


def test_audio_bed_mood_field():
    """Every ModeProfile must have a valid audio_bed_mood for the audio bed engine."""
    assert ANATOMICAL.audio_bed_mood == "clinical_drone"
    assert INCIDENT.audio_bed_mood == "tension_pulse"
    assert MECHANICAL.audio_bed_mood == "mechanical_hum"


def test_fail_safe_defaults_in_canonicalize():
    """Omitting mode parameter MUST default to ANATOMICAL and censor environments."""
    raw = "The man enters the hospital bedroom and looks at the sky."
    censored_default = _canonicalize_model_brief(raw)
    assert "hospital" not in censored_default
    assert "bedroom" not in censored_default
    assert "sky" not in censored_default
    assert "deep dark neutral studio void" in censored_default

    # Incident mode explicitly preserves environments
    preserved = _canonicalize_model_brief(raw, mode=INCIDENT)
    assert "hospital" in preserved
    assert "bedroom" in preserved
    assert "sky" in preserved


def test_incident_validator_role_based_ids():
    timeline = TimelinePlan.for_profile("providers_4s", 24.0)
    beats = [Beat(i, f"Beat text {i}") for i in range(1, 6)]
    
    # Valid incident shot with role-based primary and secondary IDs
    valid_shot = Shot(
        block=1, beat_index=1, t_start=0.0, t_end=4.0,
        subject_id="unruly_passenger",
        secondary_subject_ids=["flight_attendant_01", "seated_passenger"],
        subject_description="a distressed passenger",
        start_image_prompt="passenger in airplane cabin",
        end_image_prompt="passenger struggling with latch",
        motion_prompt="passenger grabs handle",
        location_id="airplane_cabin",
        visual_domain="incident",
    )
    script_valid = Script("Test Incident", beats, [valid_shot], timeline=timeline, mode="incident")
    problems = validate_script(script_valid, timeline, mode=INCIDENT)
    assert not any("role-based" in p for p in problems)

    # Invalid uppercase or real-name style ID
    invalid_shot = Shot(
        block=1, beat_index=1, t_start=0.0, t_end=4.0,
        subject_id="John_Smith",
        subject_description="John Smith on flight",
        start_image_prompt="passenger in airplane cabin",
        end_image_prompt="passenger struggling with latch",
        motion_prompt="passenger grabs handle",
        location_id="airplane_cabin",
        visual_domain="incident",
    )
    script_invalid = Script("Test Incident", beats, [invalid_shot], timeline=timeline, mode="incident")
    problems_invalid = validate_script(script_invalid, timeline, mode=INCIDENT)
    assert any("must be lowercase role-based" in p for p in problems_invalid)


def test_asset_roster_multi_character_incident():
    """In incident mode, build_roster creates environment plate and character sheets for all actors."""
    shot1 = Shot(
        block=1, beat_index=1, t_start=0.0, t_end=4.0,
        subject_id="unruly_passenger",
        secondary_subject_ids=["flight_attendant_01"],
        subject_description="distressed traveler in grey jacket",
        location_id="airplane_cabin",
    )
    shot2 = Shot(
        block=2, beat_index=2, t_start=4.0, t_end=8.0,
        subject_id="flight_attendant_01",
        secondary_subject_ids=["copilot_01"],
        subject_description="crew member with restraint strap",
        location_id="airplane_cabin",
    )
    entries = build_roster([shot1, shot2], mode=INCIDENT)
    ids = [e.id for e in entries]

    assert "environment_airplane_cabin" in ids
    assert "environment_void" not in ids
    assert "unruly_passenger" in ids
    assert "flight_attendant_01" in ids
    assert "copilot_01" in ids

    # All characters must have 2:3 ratio and kind == 'character'
    for e in entries:
        if e.kind == "character":
            assert e.aspect_ratio == "2:3"
            assert "Character reference sheet" in e.prompt


def test_mechanical_system_prompt():
    timeline = TimelinePlan.for_profile("providers_4s", 24.0)
    engine = BeatEngine(None, lang="en", timeline=timeline, mode=MECHANICAL)
    prompt = engine.system_prompt()
    assert "physics and engineering documentary" in prompt
    assert "mechanical drive axis" in prompt
    assert "internal mechanical assembly" in prompt
    assert "oral axis" not in prompt
    assert "thoracic" not in prompt
    assert "tissue boundary" not in prompt


def test_mechanical_roster_generation():
    shot1 = Shot(
        block=1, beat_index=1, t_start=0.0, t_end=4.0,
        subject_id="hydraulic_piston",
        subject_description="high-pressure steel hydraulic cylinder",
        location_id="machine_shop",
        visual_domain="mechanical",
    )
    shot2 = Shot(
        block=2, beat_index=2, t_start=4.0, t_end=8.0,
        subject_id="steel_cable",
        subject_description="braided steel hoist cable under tension",
        location_id="machine_shop",
        visual_domain="mechanical",
    )
    entries = build_roster([shot1, shot2], mode=MECHANICAL)
    ids = [e.id for e in entries]

    assert "environment_machine_shop" in ids
    assert "environment_void" not in ids
    assert "hydraulic_piston" in ids
    assert "steel_cable" in ids

    # Mechanical subjects must be props with 1:1 aspect ratio and engineering cutaway prompts
    for e in entries:
        if e.id in {"hydraulic_piston", "steel_cable"}:
            assert e.kind == "prop"
            assert e.aspect_ratio == "1:1"
            assert "Engineering and Scientific Cutaway Model Render" in e.prompt
            assert "30-year-old" not in e.prompt
            assert "human" not in e.prompt


def test_mechanical_prompt_compilation():
    shot = Shot(
        block=1, beat_index=1, t_start=0.0, t_end=4.0,
        subject_id="hydraulic_piston",
        subject_description="high-pressure steel hydraulic cylinder",
        visual_domain="mechanical",
        scale="medium",
    )
    prompt = compile_keyframe_prompt(shot, "start", mode=MECHANICAL)
    assert "Glossy Stylized 3D Engineering and Technical Cutaway Visualization Render" in prompt
    assert "Medical and Scientific Cutaway" not in prompt
