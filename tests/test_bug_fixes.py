import pytest
from services.asset_roster import _build_contextual_roster, _character_prompt, RosterEntry
from services.script_engine import validate_script, Script, Shot, Beat, TimelinePlan
from services.mode_profile import ModeProfile, INCIDENT

def test_task10_secondary_only_subject_is_prop():
    # A subject_id that only appears in secondary_subject_ids must produce kind="prop"
    # and a non-anthropomorphic prompt, even in incident mode where default is character.
    mode = INCIDENT
    
    shot1 = Shot(
        block=1, beat_index=1, t_start=0.0, t_end=4.0,
        subject_id="captain_pilot", subject_description="The captain",
        start_image_prompt="A", end_image_prompt="B", motion_prompt="C",
        target_quadrant="center", end_target_quadrant_value="center", visual_domain="incident",
        dominant_event="E", proof_on_screen="F", entry_state="G", exit_state="H",
        endpoint_mode="first_last", caption_safe_zone="lower_middle", scale="medium",
        journey_phase="explore", transition_kind="same_subject", secondary_subject_ids=["aircraft_exterior"],
        presentation_mode="opening_anchor", opening_anchor_id="captain_pilot",
        location_id="cockpit"
    )
    
    shot2 = Shot(
        block=2, beat_index=1, t_start=4.0, t_end=8.0,
        subject_id="flight_attendant_01", subject_description="The attendant",
        start_image_prompt="A", end_image_prompt="B", motion_prompt="C",
        target_quadrant="center", end_target_quadrant_value="center", visual_domain="incident",
        dominant_event="E", proof_on_screen="F", entry_state="G", exit_state="H",
        endpoint_mode="first_last", caption_safe_zone="lower_middle", scale="medium",
        journey_phase="explore", transition_kind="same_subject", secondary_subject_ids=["aircraft_exterior"],
        presentation_mode="mechanism", location_id="cockpit"
    )
    
    roster = _build_contextual_roster([shot1, shot2], mode)
    
    # Verify aircraft_exterior is present
    aircraft_entry = next((e for e in roster if e.id == "aircraft_exterior"), None)
    assert aircraft_entry is not None, "aircraft_exterior should be in roster"
    
    # It must be a prop, not a character
    assert aircraft_entry.kind == "prop"
    
    # Prompt should have the non-anthropomorphic grounding phrase
    assert "not a character" in aircraft_entry.prompt
    assert "no face" in aircraft_entry.prompt


def test_task11_identity_prompt_strips_action_verbs():
    # action verbs should be stripped from character_prompt but not touch the motion_prompt
    desc = "Male flight attendant diving onto cockpit carpet floor, grabbing ankles, pinned against wall, assisted by second attendant."
    prompt = _character_prompt(desc, "flight_attendant_01")
    
    # Verify verbs are neutralized
    assert "diving" not in prompt.lower()
    assert "grabbing" not in prompt.lower()
    assert "pinned" not in prompt.lower()
    assert "assisted by" not in prompt.lower()
    assert "second attendant" not in prompt.lower()
    
    # Verify neutral pose
    assert "standing neutrally" in prompt.lower()
    assert "isolated single subject" in prompt.lower()


def test_task12_contrast_validator_uses_nearest_preceding_description():
    # The contrast validator should compare against the nearest preceding description.
    # captain_pilot in block 1 & 2 is primary.
    # block 2: "white shirt whipping in wind"
    # block 3: flight_attendant_01 primary, secondary captain_pilot. flight_attendant_01 has "white collared shirt"
    # block 9: captain_pilot primary, "torso pinned horizontally"
    
    shot1 = Shot(
        block=1, beat_index=1, t_start=0.0, t_end=4.0,
        subject_id="captain_pilot", subject_description="captain in white shirt",
        start_image_prompt="A", end_image_prompt="B", motion_prompt="C",
        dominant_event="E", proof_on_screen="F", entry_state="G", exit_state="H",
        presentation_mode="opening_anchor", opening_anchor_id="captain_pilot",
        visual_domain="incident"
    )
    shot2 = Shot(
        block=2, beat_index=1, t_start=4.0, t_end=8.0,
        subject_id="captain_pilot", subject_description="white shirt whipping in wind",
        start_image_prompt="A", end_image_prompt="B", motion_prompt="C",
        dominant_event="E", proof_on_screen="F", entry_state="G", exit_state="H",
        visual_domain="incident"
    )
    shot3 = Shot(
        block=3, beat_index=2, t_start=8.0, t_end=12.0,
        subject_id="flight_attendant_01", subject_description="flight attendant in white collared shirt",
        secondary_subject_ids=["captain_pilot"],
        start_image_prompt="A", end_image_prompt="B", motion_prompt="C",
        dominant_event="E", proof_on_screen="F", entry_state="G", exit_state="H",
        visual_domain="incident"
    )
    shot9 = Shot(
        block=9, beat_index=5, t_start=32.0, t_end=36.0,
        subject_id="captain_pilot", subject_description="torso pinned horizontally",
        start_image_prompt="A", end_image_prompt="B", motion_prompt="C",
        dominant_event="E", proof_on_screen="F", entry_state="G", exit_state="H",
        presentation_mode="return_to_opening_anchor_payoff", opening_anchor_id="captain_pilot",
        endpoint_mode="first_only", payoff_reason="resolution",
        visual_domain="incident"
    )
    
    script = Script(
        topic="Test", lang="en", mode="incident",
        beats=[Beat(1, "A"), Beat(2, "B"), Beat(3, "C"), Beat(4, "D"), Beat(5, "E")],
        shots=[shot1, shot2, shot3, shot9],
        timeline=TimelinePlan.from_dict({
            "source": "providers", "block_count": 4, "keyframe_count": 5,
            "native_clip_duration": 4.0, "total_duration": 16.0,
            "shot_durations": [4.0, 4.0, 4.0, 4.0]
        })
    )
    
    mode = INCIDENT
    problems = validate_script(script, script.timeline, mode)
    
    contrast_errors = [p for p in problems if "contrast violation" in p]
    assert len(contrast_errors) > 0, "Contrast violation should be detected because block 3 should resolve captain_pilot to block 2's description, which shares 'white' and 'shirt'."
    assert any("white" in err and "shirt" in err for err in contrast_errors)
