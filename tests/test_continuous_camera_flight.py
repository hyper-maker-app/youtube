from __future__ import annotations

import pytest

from pipeline import build_frame_plan
from services.script_engine import Beat, Script, Shot, _canonicalize_model_brief, optimize_for_flow, validate_script
from timeline import TimelinePlan


def _continuous_flight_script() -> tuple[Script, TimelinePlan]:
    timeline = TimelinePlan.for_profile("providers_4s", 24.0)
    shots = [
        # Block 1: Contextual opening anchor (human eating)
        Shot(
            block=1, beat_index=1, t_start=0.0, t_end=4.0,
            subject_id="young_man_eating", subject_description="Young man eating ice cream",
            start_image_prompt="A man eating ice cream with closed mouth",
            end_image_prompt="A man bringing spoon toward lips",
            motion_prompt="Spoon approaches mouth with sealed lips",
            visual_domain="anatomical", scale="medium", journey_phase="establish",
            transition_kind="same_subject", dominant_event="eating ice cream",
            proof_on_screen="spoon touches closed lips", entry_state="holding spoon",
            exit_state="spoon at mouth", presentation_mode="contextual_opening_anchor",
            contextual_anchor_id="ctx_eater", contextual_anchor_subject_id="young_man_eating",
            contextual_anchor_kind="human", mechanism_anchor_id="mech_palate",
            contextual_anchor_roster_ids=["environment_void", "young_man_eating"],
            contextual_anchor_appearance_contract="same young man with blue crewneck t-shirt; closed neutral mouth",
            contextual_anchor_sheet_ids=["environment_void", "young_man_eating"],
        ),
        # Block 2: Push-Through penetration transition (lips to palate)
        Shot(
            block=2, beat_index=2, t_start=4.0, t_end=8.0,
            subject_id="palate_tissue", subject_description="oral boundary to palate tissue",
            start_image_prompt="Extreme macro on lips boundary",
            end_image_prompt="Macro internal palate tissue cross section",
            motion_prompt="One continuous 4.0-second rapid macro push-in penetrating tissue boundary along oral axis",
            visual_domain="anatomical", scale="macro", journey_phase="descend",
            transition_kind="scale_transition", dominant_event="camera penetrates tissue boundary",
            proof_on_screen="rapid transition into tissue cross-section", entry_state="closed lips exterior",
            exit_state="internal palate cross-section",
        ),
        # Block 3: Mechanism exploration
        Shot(
            block=3, beat_index=3, t_start=8.0, t_end=12.0,
            subject_id="palate_tissue", subject_description="palate tissue",
            start_image_prompt="palate cooling", end_image_prompt="capillary constriction",
            motion_prompt="capillaries constrict rapidly under cold exposure",
            visual_domain="anatomical", scale="macro", journey_phase="explore",
            transition_kind="same_subject", dominant_event="vessel constriction",
            proof_on_screen="vessels narrowing", entry_state="wide vessels",
            exit_state="constricted vessels",
        ),
        # Block 4: Mechanism explore micro
        Shot(
            block=4, beat_index=3, t_start=12.0, t_end=16.0,
            subject_id="palate_vessels", subject_description="palate arterioles",
            start_image_prompt="arterioles dilating", end_image_prompt="nerve stimulation",
            motion_prompt="rebound dilation activates sensory nerve fibers",
            visual_domain="anatomical", scale="micro", journey_phase="explore",
            transition_kind="location_change", dominant_event="nerve signaling",
            proof_on_screen="fibers firing", entry_state="dilating vessels",
            exit_state="active nerve fibers",
        ),
        # Block 5: Trigeminal nerve reveal
        Shot(
            block=5, beat_index=4, t_start=16.0, t_end=20.0,
            subject_id="trigeminal_nerve", subject_description="trigeminal pathway",
            start_image_prompt="nerve signal traveling", end_image_prompt="signal reaching ganglion",
            motion_prompt="impulses travel through the nerve trunk toward skull base",
            visual_domain="anatomical", scale="macro", journey_phase="reveal",
            transition_kind="location_change", dominant_event="impulse conduction",
            proof_on_screen="impulses reaching ganglion", entry_state="impulse ascending",
            exit_state="ganglion convergence",
        ),
        # Block 6: Pull-Back Zoom-Out Reveal to Contextual Anchor Payoff
        Shot(
            block=6, beat_index=5, t_start=20.0, t_end=24.0,
            subject_id="young_man_eating", subject_description="man clutching forehead",
            start_image_prompt="micro nerve pathway",
            end_image_prompt="man holding forehead in relief",
            motion_prompt="Continuous 4.0-second rapid pull-back reveal from glowing nerve pathway through skull to human portrait",
            visual_domain="anatomical", scale="medium", journey_phase="resolve",
            transition_kind="scale_transition", dominant_event="pull-back zoom-out reveal of referred forehead pain",
            proof_on_screen="man clutching forehead in deep dark void", entry_state="glowing micro nerve",
            exit_state="man pressing forehead with closed mouth",
            endpoint_mode="first_last",
            presentation_mode="return_to_contextual_anchor_payoff",
            payoff_reason="Continuous camera flight pulls back to prove referred pain manifests on the forehead of the same young man.",
            contextual_anchor_id="ctx_eater", contextual_anchor_subject_id="young_man_eating",
            contextual_anchor_kind="human", mechanism_anchor_id="mech_palate",
            contextual_anchor_roster_ids=["environment_void", "young_man_eating"],
            contextual_anchor_appearance_contract="same young man with blue crewneck t-shirt; closed neutral mouth",
            contextual_anchor_sheet_ids=["environment_void", "young_man_eating"],
        ),
    ]
    beat_text = "cold dessert hits soft palate and causes sudden sharp intense referred forehead pain"
    script = Script("Brain Freeze", [Beat(i, beat_text) for i in range(1, 6)], shots, timeline=timeline)
    return script, timeline


def test_continuous_camera_flight_frame_plan() -> None:
    script, timeline = _continuous_flight_script()
    problems = validate_script(script, timeline)
    assert not problems, f"Validation errors: {problems}"

    plan = build_frame_plan(script)
    assert len(plan) == 6

    # Block 2 (Push-Through): interpolates kf02 -> kf03
    push_block = plan[1]
    assert push_block["start_frame_id"] == "kf02"
    assert push_block["end_frame_id"] == "kf03"

    # Block 6 (Pull-Out Reveal): interpolates kf06 (internal nerve) -> kf07 (contextual anchor portrait)
    terminal_block = plan[-1]
    assert terminal_block["start_frame_id"] == "kf06"
    assert terminal_block["end_frame_id"] == "kf07"
    assert terminal_block["reference_policy"] == "contextual_anchor_roster_only"
    assert terminal_block["transition_at_in"] == "continuous_flight"


def test_push_through_and_pull_out_prompt_compilation() -> None:
    script, _ = _continuous_flight_script()

    # Block 2: Push-through
    push_compiled = optimize_for_flow(script.shots[1])
    assert "rapid macro push-in" in push_compiled["video_prompt"].casefold()
    assert "oral axis" in push_compiled["video_prompt"].casefold()
    assert "storyboard interpolation" in push_compiled["video_prompt"].casefold()

    # Block 6: Pull-out reveal
    pull_compiled = optimize_for_flow(script.shots[5])
    assert "rapid pull-back reveal" in pull_compiled["video_prompt"].casefold()
    assert "optical axis" in pull_compiled["video_prompt"].casefold()
    assert "storyboard interpolation" in pull_compiled["video_prompt"].casefold()


def test_controlled_transition_whitelist_in_canonicalize() -> None:
    raw = "Camera accelerates smoothly toward the sealed lips, effortlessly penetrating the tissue boundary along the oral axis"
    canonical = _canonicalize_model_brief(raw)
    assert "accelerates smoothly toward" in canonical
    assert "penetrating the tissue boundary" in canonical

    raw_pull = "Continuous 4.0-second rapid pull-back reveal along the optical axis"
    canonical_pull = _canonicalize_model_brief(raw_pull)
    assert "rapid pull-back reveal" in canonical_pull
