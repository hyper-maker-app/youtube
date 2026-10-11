"""Unit tests for ADR-028 Zero-Rejection Architecture.

Tests cover:
1. Anti-text hard shield in keyframe and motion prompts
2. Domain-bleed isolation (mechanical -> biological mapping in anatomical mode)
3. Domain preservation in mechanical and incident modes
4. Volumetric proof stream compiler (replacing 2D clipart arrows)
5. Scale transition continuity clause
6. Reference sheet anti-text hardening in asset roster
7. Surgical repair categorization and focused directive generation
"""

from __future__ import annotations

from pathlib import Path

from main import parse_args
from pipeline import RunContext, _build_surgical_repair, _categorize_rejection, _SURGICAL_REPAIRS
from services.asset_roster import _ROSTER_ANTI_TEXT_SUFFIX, build_roster
from services.mode_profile import ANATOMICAL, INCIDENT, MECHANICAL
from services.script_engine import (
    _ANATOMICAL_DOMAIN_BLEED_MAP,
    _ANTI_TEXT_SHIELD,
    _CAMERA_VIEWPOINT_MANDATE,
    _INCIDENT_ROLE_COSTUMES,
    Beat,
    Script,
    Shot,
    _canonicalize_model_brief,
    _is_exterior_shot,
    _isolate_domain_bleed,
    _marker_instruction,
    compile_image_prompt,
    compile_keyframe_prompt,
    compile_motion_prompt,
    compile_negative_prompt,
    optimize_for_flow,
    _required_beat_indices,
    validate_script,
    BeatEngine,
)
from timeline import TimelinePlan


def _make_dummy_shot(
    *,
    marker_type: str = "none",
    marker_quadrant: str = "top_right",
    transition_kind: str = "scale_transition",
    normalized_domain: str = "anatomical",
    scale: str = "macro",
    journey_phase: str = "descend",
    start_prompt: str = "Close view of corneal surface with wiper motion",
    end_prompt: str = "Extreme macro view of tear film with dissolved ions",
    motion_prompt: str = "Push in through corneal boundary",
    detail_target: str = "corneal epithelium",
    subject_id: str = "human_eye",
    subject_description: str = "human eye cornea",
    continuity_anchor: str = "cornea",
    entry_state: str = "liquid tear film layer",
    exit_state: str = "saline lattice with dissolved ions",
    dominant_event: str = "tear film resists freezing",
    proof_on_screen: str = "liquid surface remains fluid at minus twenty degrees",
) -> Shot:
    return Shot(
        block=2,
        beat_index=2,
        t_start=4.0,
        t_end=8.0,
        start_image_prompt=start_prompt,
        end_image_prompt=end_prompt,
        motion_prompt=motion_prompt,
        transition_kind=transition_kind,
        visual_domain=normalized_domain,
        detail_target=detail_target,
        entry_state=entry_state,
        exit_state=exit_state,
        subject_id=subject_id,
        subject_description=subject_description,
        continuity_anchor=continuity_anchor,
        dominant_event=dominant_event,
        proof_on_screen=proof_on_screen,
        marker_type=marker_type,
        marker_quadrant=marker_quadrant,
        scale=scale,
        journey_phase=journey_phase,
    )


# ---------------------------------------------------------------------------
# 1. Anti-Text Hard Shield Tests
# ---------------------------------------------------------------------------

def test_anti_text_shield_in_keyframe_prompts():
    """Verify that compile_keyframe_prompt injects the universal anti-text shield."""
    shot = _make_dummy_shot()
    start_prompt = compile_keyframe_prompt(shot, "start", mode=ANATOMICAL)
    end_prompt = compile_keyframe_prompt(shot, "end", mode=ANATOMICAL)

    assert _ANTI_TEXT_SHIELD in start_prompt
    assert _ANTI_TEXT_SHIELD in end_prompt
    assert "ABSOLUTE TEXT PROHIBITION" in start_prompt
    assert "no Na+, no Cl-" in start_prompt
    assert "unlabeled luminous spheres" in start_prompt


def test_anti_text_shield_in_motion_prompts():
    """Verify that optimize_for_flow injects the anti-text shield in all branches."""
    # Standard branch
    shot_std = _make_dummy_shot(journey_phase="explore")
    flow_std = optimize_for_flow(shot_std, mode=ANATOMICAL)
    assert _ANTI_TEXT_SHIELD in flow_std["video_prompt"]

    # Push-in branch (descend phase with scale transition into macro/micro)
    shot_push = _make_dummy_shot(journey_phase="descend", scale="micro")
    flow_push = optimize_for_flow(shot_push, mode=ANATOMICAL)
    assert _ANTI_TEXT_SHIELD in flow_push["video_prompt"]

    # Pull-out branch
    shot_pull = _make_dummy_shot(journey_phase="payoff", scale="wide")
    flow_pull = optimize_for_flow(shot_pull, mode=ANATOMICAL)
    assert _ANTI_TEXT_SHIELD in flow_pull["video_prompt"]


# ---------------------------------------------------------------------------
# 2. Domain-Bleed Isolation Tests
# ---------------------------------------------------------------------------

def test_domain_bleed_isolation_replaces_mechanical_terms_in_anatomical():
    """Verify mechanical metaphors are translated to biological equivalents in anatomical mode."""
    test_text = "The eyelid acts like a wiper while the heart acts like a pump with a valve"
    isolated = _isolate_domain_bleed(test_text, "anatomical")

    assert "wiper" not in isolated
    assert "sweeping mucosal membrane" in isolated
    assert "pump" not in isolated
    assert "biological circulatory organ" in isolated
    assert "valve" not in isolated
    assert "muscular sphincter flap" in isolated


def test_domain_bleed_isolation_preserves_terms_in_mechanical_and_incident():
    """Verify mechanical terms remain unchanged in mechanical and incident modes."""
    test_text = "The brake caliper clamps the metal rotor while the piston compresses"
    mech_result = _isolate_domain_bleed(test_text, "mechanical")
    incident_result = _isolate_domain_bleed(test_text, "incident")

    assert "metal" in mech_result
    assert "piston" in mech_result
    assert "metal" in incident_result
    assert "piston" in incident_result


def test_canonicalize_model_brief_applies_domain_bleed_shield():
    """Verify _canonicalize_model_brief sanitizes mechanical terms under anatomical mode."""
    brief = "A clean view of the eye where the lid operates like a wiper over corneal surface"
    sanitized = _canonicalize_model_brief(brief, mode=ANATOMICAL)

    assert "wiper" not in sanitized
    assert "sweeping mucosal membrane" in sanitized


# ---------------------------------------------------------------------------
# 3. Volumetric Proof Stream Compiler Tests
# ---------------------------------------------------------------------------

def test_marker_instruction_arrow_emits_volumetric_stream():
    """Verify arrow marker emits 3D organic stream and explicitly bans 2D clipart stickers."""
    shot = _make_dummy_shot(marker_type="arrow", marker_quadrant="top_right")
    instruction = _marker_instruction(shot)

    assert "organically glowing luminescent energy stream" in instruction
    assert "top_right" in instruction
    assert "STRICTLY NO flat 2D clipart arrows" in instruction
    assert "no graphic sticker overlays" in instruction
    assert "no disconnected floating arrow shapes" in instruction


def test_marker_instruction_trajectory_emits_volumetric_path():
    """Verify trajectory marker emits volumetric path trace and bans clipart."""
    shot = _make_dummy_shot(marker_type="trajectory", marker_quadrant="bottom_left")
    instruction = _marker_instruction(shot)

    assert "softly glowing red volumetric path trace" in instruction
    assert "bottom_left" in instruction
    assert "STRICTLY NO flat 2D clipart arrows" in instruction


def test_marker_instruction_none_emits_no_marker():
    """Verify marker_type='none' emits clean prohibition."""
    shot = _make_dummy_shot(marker_type="none")
    instruction = _marker_instruction(shot)

    assert "No baked arrow, trajectory, neon marker, decorative overlay, or HUD." == instruction


# ---------------------------------------------------------------------------
# 4. Scale Transition Continuity Clause Tests
# ---------------------------------------------------------------------------

def test_scale_transition_clause_in_keyframe_prompt():
    """Verify scale transition clause is included when transition_kind is scale_transition."""
    shot_scale = _make_dummy_shot(transition_kind="scale_transition", scale="micro")
    prompt_scale = compile_keyframe_prompt(shot_scale, "start", mode=ANATOMICAL)

    assert "Scale transition: maintain exact subject identity" in prompt_scale
    assert "micro magnification" in prompt_scale
    assert "seamless perspective continuity" in prompt_scale

    # When not a scale transition, clause should be absent
    shot_cut = _make_dummy_shot(transition_kind="hard_cut", scale="micro")
    prompt_cut = compile_keyframe_prompt(shot_cut, "start", mode=ANATOMICAL)
    assert "Scale transition: maintain exact subject identity" not in prompt_cut


# ---------------------------------------------------------------------------
# 5. Asset Roster Anti-Text Hardening Tests
# ---------------------------------------------------------------------------

def test_asset_roster_prompts_contain_anti_text_suffix():
    """Verify all roster reference sheets have the hard anti-text suffix."""
    shot = _make_dummy_shot()
    entries = build_roster([shot], mode=ANATOMICAL)

    assert len(entries) >= 2  # environment_void + subject
    for entry in entries:
        assert _ROSTER_ANTI_TEXT_SUFFIX.strip() in entry.prompt
        assert "ZERO text, ZERO letters, ZERO numbers" in entry.prompt
        assert "No split-screen, no multi-panel" in entry.prompt


def test_contextual_roster_prompts_contain_anti_text_suffix():
    """Verify contextual roster sheets (incident/mechanical) also have anti-text suffix."""
    shot = _make_dummy_shot()
    entries = build_roster([shot], mode=MECHANICAL)

    for entry in entries:
        assert _ROSTER_ANTI_TEXT_SUFFIX.strip() in entry.prompt


# ---------------------------------------------------------------------------
# 6. Pipeline Surgical Repair Helper Tests
# ---------------------------------------------------------------------------

def test_pipeline_rejection_categorization():
    """Verify rejection categorization patterns match actual archive failure modes."""
    # Test text contamination category
    reasons_text = [
        "Visible text labels on ions violate strict no-text constraint",
        "Contains chemical formula Na+ written on crystal structure",
        "Watermark and logo detected in lower quadrant",
    ]
    text_words = ("text", "label", "caption", "watermark", "letter", "number",
                  "symbol", "logo", "formula", "annotation", "na+", "cl-", "h2o")
    for r in reasons_text:
        assert any(w in r.lower() for w in text_words)

    # Test clipart arrow category
    reasons_clipart = [
        "Required glowing thermal flow arrows radiating from capillaries are absent; only a disconnected green arrow overlay is present",
        "Extraneous graphic arrow artifact violates clean render requirements",
    ]
    clipart_words = ("arrow", "clipart", "sticker", "overlay", "graphic arrow", "disconnected", "floating arrow")
    for r in reasons_clipart:
        assert any(w in r.lower() for w in clipart_words)

    # Test domain bleed category
    reasons_bleed = [
        "Rendered scene drifted into industrial factory setting with steel pipe",
        "Depicts a boiler room instead of human bronchial airway",
    ]
    bleed_words = ("industrial", "factory", "machine", "mechanical", "metal pipe", "conveyor", "boiler", "tank")
    for r in reasons_bleed:
        assert any(w in r.lower() for w in bleed_words)


# ---------------------------------------------------------------------------
# 7. ADR-031: Missing Object Surgical Repair & Deterministic Proof Tests
# ---------------------------------------------------------------------------

def test_missing_object_categorization_and_surgical_repair():
    """Verify that missing element rejections are prioritized and generate targeted injections."""
    reasons = [
        "Missing mobile access stairs on tarmac",
        "Absence of emergency oxygen mask on copilot",
        "Does not show aircraft breach opening",
    ]
    for r in reasons:
        assert _categorize_rejection(r) == "missing_object"

    repair = _build_surgical_repair(["Missing mobile access stairs on tarmac"])
    assert "[MANDATORY CORRECTION — MISSING ELEMENT ENFORCEMENT]" in repair
    assert "Specific elements that MUST appear: Missing mobile access stairs on tarmac." in repair
    assert "Specific review feedback to address: Missing mobile access stairs on tarmac." in repair


def test_deterministic_proof_injection_in_keyframe_prompts():
    """Verify compile_keyframe_prompt injects deterministic proof evidence."""
    shot = _make_dummy_shot(
        proof_on_screen="mobile access stairs rolled against fuselage on tarmac",
        entry_state="stairs docked to aircraft",
        exit_state="passengers deplaning via stairs",
    )
    start_prompt = compile_keyframe_prompt(shot, "start", mode=ANATOMICAL)
    end_prompt = compile_keyframe_prompt(shot, "end", mode=ANATOMICAL)

    assert "[Deterministic Proof Evidence]" in start_prompt
    assert "mobile access stairs rolled against fuselage on tarmac" in start_prompt
    assert "Required endpoint state: 'stairs docked to aircraft'" in start_prompt

    assert "[Deterministic Proof Evidence]" in end_prompt
    assert "Required endpoint state: 'passengers deplaning via stairs'" in end_prompt


# ---------------------------------------------------------------------------
# 8. ADR-031: Spatial Vector, 180-Degree Axis Lock & Role Decoupling Tests
# ---------------------------------------------------------------------------

def test_role_decoupling_and_costume_invariants():
    """Verify role decoupling invariant is injected for multi-character incident scenes."""
    shot = _make_dummy_shot(
        subject_id="captain_pilot",
        subject_description="commercial airline captain in distress",
        normalized_domain="incident",
    )
    shot.secondary_subject_ids = ["copilot", "flight_attendant_01"]

    keyframe_p = compile_keyframe_prompt(shot, "start", mode=INCIDENT)
    assert "[Role & Costume Decoupling Invariant]" in keyframe_p
    assert "4 gold stripes" in keyframe_p
    assert "First Officer / Copilot" in keyframe_p
    assert "Flight Attendant" in keyframe_p

    motion_flow = optimize_for_flow(shot, mode=INCIDENT)
    assert "[Role & Costume Decoupling Invariant]" in motion_flow["video_prompt"]


def test_spatial_vector_and_180_degree_axis_lock():
    """Verify spatial vector and 180-degree axis lock is injected for vehicle/cockpit incidents."""
    shot = _make_dummy_shot(
        subject_id="captain_pilot",
        dominant_event="cockpit windscreen breach pulls captain outward",
        normalized_domain="incident",
    )
    shot.location_id = "cockpit_flight_deck"

    keyframe_p = compile_keyframe_prompt(shot, "start", mode=INCIDENT)
    assert "[Spatial Vector & 180-Degree Axis Lock]" in keyframe_p
    assert "Camera must respect the 180-degree axis" in keyframe_p
    assert "strictly port-side (left)" in keyframe_p

    motion_flow = optimize_for_flow(shot, mode=INCIDENT)
    assert "[Spatial Vector & 180-Degree Axis Lock]" in motion_flow["video_prompt"]


def test_monotonic_causal_state_guard_in_validate_script():
    """Verify validate_script catches when an exterior-pinned character is shown inside the cockpit."""
    timeline = TimelinePlan.for_profile("providers_4s", 24.0)  # 6 blocks
    beats = [
        Beat(1, "What happens if a plane window breaks?", "hook", []),
        Beat(2, "The rapid decompression blows the cockpit windshield outward.", "build", []),
        Beat(3, "The captain is violently pulled halfway out of the plane.", "peak", []),
        Beat(4, "Crew members desperately hold his ankles while the copilot dives.", "twist", []),
        Beat(5, "Miraculously the aircraft lands safely.", "resolution", []),
    ]
    # Create 6 shots matching timeline
    shots = []
    for i in range(1, 7):
        shot = _make_dummy_shot(
            subject_id="captain_pilot" if i in (2, 3, 4) else "copilot",
            normalized_domain="incident",
            scale="medium",
            journey_phase="build" if i <= 5 else "resolve",
        )
        shot.block = i
        shot.beat_index = _required_beat_indices(timeline.block_count)[i - 1]
        shot.t_start = (i - 1) * 4.0
        shot.t_end = i * 4.0
        if i == 2:
            shot.entry_state = "normal cockpit flight"
            shot.exit_state = "exterior_pinned against fuselage"
            shot.dominant_event = "windscreen breach causes captain to be sucked out outside fuselage"
        elif i == 3:
            # Illegal state change: captain was exterior_pinned, but shot describes him inside operating controls
            shot.start_image_prompt = "captain_pilot seated in cockpit operating controls calmly"
            shot.end_image_prompt = "captain_pilot seated in cockpit operating controls calmly"
            shot.dominant_event = "captain_pilot seated in cockpit operating controls calmly"
        shots.append(shot)

    script = Script(
        topic="The Pilot Who Got Sucked Out",
        beats=beats,
        shots=shots,
        lang="en",
        timeline=timeline,
        mode="incident",
    )

    problems = validate_script(script, timeline, mode=INCIDENT)
    causal_errors = [p for p in problems if "monotonic causal state guard" in p]
    assert len(causal_errors) >= 1
    assert "captain_pilot" in causal_errors[0]
    assert "seated in cockpit" in causal_errors[0]


def test_spatial_vector_not_injected_for_non_cockpit_incidents():
    """Verify non-aviation incident scenes (submarine, elevator, etc.) do NOT get cockpit breach directives."""
    shot = _make_dummy_shot(
        subject_id="elevator_cable",
        dominant_event="emergency brake stops falling cab",
        normalized_domain="incident",
    )
    shot.location_id = "elevator_shaft"

    keyframe_p = compile_keyframe_prompt(shot, "start", mode=INCIDENT)
    assert "[Spatial Vector & 180-Degree Axis Lock]" not in keyframe_p
    assert "aircraft breach" not in keyframe_p

    motion_flow = optimize_for_flow(shot, mode=INCIDENT)
    assert "[Spatial Vector & 180-Degree Axis Lock]" not in motion_flow["video_prompt"]


def test_validate_script_rejects_lower_center_marker():
    """Verify validate_script rejects markers placed in center or lower_center caption safe zone."""
    timeline = TimelinePlan.for_profile("providers_4s", 24.0)
    shot = _make_dummy_shot(
        marker_type="arrow",
        marker_quadrant="lower_center",
    )
    shot.block = 1
    shot.beat_index = 1
    shot.t_start = 0.0
    shot.t_end = 4.0
    shots = [shot]
    for i in range(2, 7):
        s = _make_dummy_shot(marker_type="none")
        s.block = i
        s.beat_index = _required_beat_indices(6)[i - 1]
        s.t_start = (i - 1) * 4.0
        s.t_end = i * 4.0
        shots.append(s)
    script = Script("Marker test", [Beat(i, f"beat {i}") for i in range(1, 6)], shots, timeline=timeline)
    problems = validate_script(script, timeline)
    assert any("marker must use its authored non-center" in p for p in problems)


def test_spatial_vector_not_injected_in_anatomical_or_mechanical_modes_with_cockpit_keywords():
    """Verify non-incident modes (anatomical, mechanical) NEVER receive cockpit breach directives even with cockpit/pilot keywords."""
    shot = _make_dummy_shot(
        subject_id="pilot_retina",
        dominant_event="pilot eye microvasculature constricts in cockpit during high-G flight",
        normalized_domain="anatomical",
    )
    shot.location_id = "aircraft_cockpit"

    for mode in (ANATOMICAL, MECHANICAL):
        keyframe_p = compile_keyframe_prompt(shot, "start", mode=mode)
        assert "[Spatial Vector & 180-Degree Axis Lock]" not in keyframe_p
        assert "aircraft breach" not in keyframe_p
        assert "captain remains pinned" not in keyframe_p

        motion_flow = optimize_for_flow(shot, mode=mode)
        assert "[Spatial Vector & 180-Degree Axis Lock]" not in motion_flow["video_prompt"]


def test_beat_engine_assembles_clean_marker_quadrant_outside_lower_center():
    """Verify BeatEngine._assemble reassigns lower_center/lower_middle markers away from caption-safe area."""
    timeline = TimelinePlan.for_profile("providers_4s", 24.0)
    engine = BeatEngine(None, lang="en", timeline=timeline)  # type: ignore[arg-type]

    payload = {
        "beats": [{"index": i, "text": f"narration beat text number {i} spoken words punchy"} for i in range(1, 6)],
        "shots": [
            {
                "block": 1, "beat_index": 1, "subject_id": "cornea", "subject_description": "human eye cornea",
                "start_image_prompt": "clean macro cornea", "end_image_prompt": "clean macro cornea surface",
                "motion_prompt": "steady view of cornea", "target_quadrant": "top_left",
                "visual_domain": "anatomical", "scale": "macro", "journey_phase": "establish",
                "transition_kind": "same_subject", "camera_angle": "eye_level",
                "detail_target": "corneal surface", "continuity_anchor": "cornea_lens",
                "entry_state": "intact cornea", "exit_state": "tear layer coats cornea",
                "dominant_event": "tear coats cornea", "proof_on_screen": "tear fluid boundary",
                "location_id": "eye_macro", "presentation_mode": "opening_anchor", "opening_anchor_id": "cornea_lens",
                "marker_type": "arrow", "marker_quadrant": "lower_middle", "endpoint_mode": "first_last",
                "impact_offset_seconds": 0.0,
            }
        ] + [
            {
                "block": i, "beat_index": i, "subject_id": "cornea", "subject_description": "cornea layer",
                "start_image_prompt": "macro view", "end_image_prompt": "macro view 2",
                "motion_prompt": "motion 2", "target_quadrant": "top_left",
                "visual_domain": "anatomical", "scale": "macro", "journey_phase": "explore",
                "transition_kind": "same_subject", "camera_angle": "eye_level",
                "detail_target": "corneal surface", "continuity_anchor": "cornea_lens",
                "entry_state": "intact cornea", "exit_state": "tear coats",
                "dominant_event": "event", "proof_on_screen": "proof",
                "location_id": "eye_macro", "presentation_mode": "mechanism",
                "marker_type": "none", "endpoint_mode": "first_last",
                "impact_offset_seconds": 0.0,
            } for i in range(2, 7)
        ]
    }

    script = engine._assemble("eye", payload)
    assert script.shots[0].marker_quadrant in {"top_left", "top_right", "bottom_left", "bottom_right", "upper_center"}
    assert script.shots[0].marker_quadrant not in {"center", "lower_center"}


def test_required_beat_indices_guarantees_beat3_shares():
    """Verify _required_beat_indices guarantees Beat 3 (reveal mechanism, 28%) receives its proper share across native plans."""
    # N=6: Beat 3 gets 2 blocks
    assert _required_beat_indices(6) == [1, 2, 3, 3, 4, 5]
    # N=7: Beat 3 gets 2 blocks (not starved to 1)
    b7 = _required_beat_indices(7)
    assert b7.count(3) >= 2
    assert b7 == [1, 2, 3, 3, 4, 4, 5]
    # N=8: legacy outline map
    assert _required_beat_indices(8) == [1, 1, 2, 2, 3, 3, 4, 5]
    # N=12: sweet spot (Beat 3 gets 4 blocks)
    assert _required_beat_indices(12) == [1, 1, 2, 2, 3, 3, 3, 3, 4, 4, 5, 5]


# ---------------------------------------------------------------------------
# ADR Perspective Isolation, Negative Prompts, Critique-Injected Retries
# ---------------------------------------------------------------------------

def _make_exterior_incident_shot() -> Shot:
    return Shot(
        block=3,
        beat_index=2,
        t_start=8.0,
        t_end=12.0,
        subject_id="captain_exterior_pinned",
        subject_description="Airline Captain pinned against exterior cockpit window aperture in 500 knot slipstream",
        start_image_prompt="Exterior airframe view of captain torso pinned through broken windscreen in slipstream, cockpit interior visible behind",
        end_image_prompt="Exterior airframe view of captain firmly held against fuselage in slipstream, flight deck instruments in background",
        motion_prompt="Violent slipstream buffeting against pilot pinned to exterior airframe",
        spatial_anchor="AIRFRAME",
        scale_level="EXTERIOR",
        forbidden_entities=["captain inside cockpit", "pilot seated in chair"],
        entry_state="captain upper torso pinned outside forward windscreen",
        exit_state="captain stabilized against exterior fuselage in slipstream",
        dominant_event="aerodynamic slipstream pins captain against outer fuselage",
        proof_on_screen="frost on exterior window frame and slipstream deflection",
        location_id="airplane_exterior",
    )


def test_perspective_isolation_in_keyframe_prompts():
    """Verify that exterior shots cleanse interior words, prepend camera mandate, and bake vacancy guarantee."""
    shot = _make_exterior_incident_shot()
    assert _is_exterior_shot(shot) is True

    prompt = compile_keyframe_prompt(shot, "start", mode=INCIDENT)

    # 1. Mandate at the very start
    assert prompt.startswith(_CAMERA_VIEWPOINT_MANDATE)

    # 2. Interior tokens cleansed
    assert "cockpit interior" not in prompt.lower()
    assert "flight deck instruments" not in prompt.lower()

    # 3. Vacancy guarantee appended
    assert "The interior pilot seat is entirely empty and vacant." in prompt


def test_perspective_isolation_in_motion_prompts():
    """Verify that motion prompt also cleanses interior tokens and adds camera mandate."""
    shot = _make_exterior_incident_shot()
    motion_compiled = optimize_for_flow(shot, mode=INCIDENT)["video_prompt"]

    assert _CAMERA_VIEWPOINT_MANDATE in motion_compiled
    assert "The interior pilot seat is entirely empty and vacant." in motion_compiled


def test_compile_aliases():
    """Verify compile_image_prompt and compile_motion_prompt helper functions."""
    shot = _make_exterior_incident_shot()
    img_p = compile_image_prompt(shot, "start", mode=INCIDENT)
    kf_p = compile_keyframe_prompt(shot, "start", mode=INCIDENT)
    assert img_p == kf_p

    mot_p = compile_motion_prompt(shot, mode=INCIDENT)
    opt_m = optimize_for_flow(shot, mode=INCIDENT)["video_prompt"]
    assert mot_p == opt_m


def test_negative_prompt_compiler_incident():
    """Verify compile_negative_prompt for incident exterior shot."""
    shot = _make_exterior_incident_shot()
    neg = compile_negative_prompt(shot, mode=INCIDENT)

    # Must contain explicit forbidden entities
    assert "captain inside cockpit" in neg
    assert "pilot seated in chair" in neg

    # Must contain exterior-specific interior bans
    assert "cockpit interior" in neg
    assert "cabin seating" in neg

    # Must contain universal bans
    assert "text" in neg
    assert "split-screen" in neg


def test_negative_prompt_compiler_anatomical():
    """Verify compile_negative_prompt for medical / anatomical shot."""
    shot = Shot(
        block=2,
        beat_index=2,
        t_start=4.0,
        t_end=8.0,
        subject_id="corneal_epithelium",
        subject_description="microscopic cross-section of corneal surface",
        start_image_prompt="Close view of tear film layer",
        end_image_prompt="Macro cross-section of cornea",
        motion_prompt="Fluid motion across corneal cells",
        spatial_anchor="MACRO_ORGAN",
        forbidden_entities=["healthy cornea", "frozen liquid"],
        entry_state="liquid tear film layer",
        exit_state="dissolved sodium chloride lattice",
        dominant_event="osmotic concentration prevents ice crystal nucleation",
        proof_on_screen="unfrozen fluid layer at minus twenty degrees",
        location_id="human_eye",
    )
    neg = compile_negative_prompt(shot, mode=ANATOMICAL)

    assert "healthy cornea" in neg
    assert "frozen liquid" in neg
    assert "text" in neg


def test_critique_prefix_formatting():
    """Verify critique injection formatting for attempt 2+."""
    rejection_reasons = [
        "Pilot torso is inside the cabin rather than blown through windscreen into slipstream",
        "Interior flight controls visible",
    ]
    rejection_summary = "; ".join(rejection_reasons)
    critique_prefix = f"CRITICAL CORRECTION FROM ART DIRECTOR: {rejection_summary}. YOU MUST FIX THIS ERROR IMMEDIATELY. "

    base_prompt = "A clean 3D render of airplane exterior."
    repair = _build_surgical_repair(rejection_reasons)
    candidate_prompt = f"{critique_prefix}{base_prompt}{repair}"

    assert candidate_prompt.startswith("CRITICAL CORRECTION FROM ART DIRECTOR: Pilot torso is inside the cabin")
    assert "YOU MUST FIX THIS ERROR IMMEDIATELY." in candidate_prompt


def test_stage_and_skip_video_cli_args():
    """Verify --stage and --skip-video CLI flags."""
    args_keyframes = parse_args(["--stage", "keyframes"])
    assert args_keyframes.stage == "keyframes"
    assert args_keyframes.skip_video is False

    args_skip = parse_args(["--skip-video"])
    assert args_skip.skip_video is True

    # Check default
    args_default = parse_args([])
    assert args_default.stage == "all"
    assert args_default.skip_video is False


def test_run_context_stage_attributes():
    """Verify RunContext carries stage and skip_video fields."""
    ctx = RunContext(
        topic="test",
        out_dir=Path("out/test"),
        stage="keyframes",
        skip_video=True,
    )
    assert ctx.stage == "keyframes"
    assert ctx.skip_video is True



