from __future__ import annotations

import pytest

import editor
from pipeline import _retime_shots_to_timeline, build_editorial_plan, build_frame_plan
from services.asset_roster import build_roster
from services.script_engine import Beat, Script, Shot, _required_beat_indices, validate_script
from timeline import TimelinePlan


def _shot(block: int, *, mode: str = "mechanism", subject: str = "gastric_mechanism") -> Shot:
    start = (block - 1) * 4.0
    contextual = mode in {"contextual_opening_anchor", "return_to_contextual_anchor_payoff"}
    return Shot(
        block=block, beat_index=_required_beat_indices(6)[block - 1], t_start=start, t_end=start + 4.0,
        subject_id="human_torso_identity" if contextual else subject,
        subject_description="same human torso with visible protected stomach" if contextual else "gastric barrier mechanism",
        start_image_prompt="protected stomach state" if contextual else "mucus barrier state",
        end_image_prompt="calm protected stomach state" if contextual else "barrier changes state",
        motion_prompt="calm digestion visibly continues" if contextual else "fluid neutralizes at the barrier",
        visual_domain="anatomical" if contextual else "biological", scale="medium" if contextual else "macro",
        journey_phase="resolve" if block == 6 else "explore", transition_kind="subject_change",
        continuity_anchor="ctx_human_torso" if contextual else "gastric_barrier",
        entry_state="same torso shows calm digestion" if contextual else "barrier begins buffering acid",
        exit_state="same torso shows intact protected wall" if contextual else "barrier visibly neutralizes acid",
        dominant_event="calm digestion preserves the visible stomach wall" if contextual else "mucus barrier neutralizes acid",
        proof_on_screen="intact protected stomach wall visibly remains calm" if contextual else "acid stops above intact cells",
        location_id="torso_cutaway" if contextual else "stomach_micro_layer",
        presentation_mode=mode, endpoint_mode="first_only" if mode.startswith("return_") else "first_last",
        endpoint_reason="independent terminal hard cut" if mode.startswith("return_") else "",
        payoff_reason="The same protected stomach inside the same torso proves the barrier prevents self-digestion." if mode.startswith("return_") else "",
        contextual_anchor_id="ctx_human_torso" if contextual else "",
        contextual_anchor_subject_id="human_torso_identity" if contextual else "",
        contextual_anchor_kind="human" if contextual else "",
        mechanism_anchor_id="mech_stomach_lumen" if contextual else "",
        contextual_anchor_roster_ids=["environment_void", "human_torso_identity"] if contextual else [],
        contextual_anchor_appearance_contract="same torso identity; closed neutral mouth; no text or lip-sync" if contextual else "",
        contextual_anchor_sheet_ids=["environment_void", "human_torso_identity"] if contextual else [],
    )


def _script() -> tuple[Script, TimelinePlan]:
    timeline = TimelinePlan.for_profile("providers_4s", 24.0)
    shots = [_shot(1, mode="contextual_opening_anchor")] + [_shot(i) for i in range(2, 6)] + [_shot(6, mode="return_to_contextual_anchor_payoff")]
    beat_text = "measured words preserve the required narration budget for contextual anchor validation right now"
    return Script("stomach", [Beat(i, beat_text) for i in range(1, 6)], shots, timeline=timeline), timeline


def test_contextual_payoff_is_independent_roster_only_terminal() -> None:
    script, timeline = _script()
    assert not validate_script(script, timeline)
    plan = build_frame_plan(script)
    assert plan[-1] == {
        "block": 6, "start_frame_id": "kf07", "end_frame_id": None,
        "reference_policy": "contextual_anchor_roster_only", "transition_at_in": "hard_cut",
        "presentation_mode": "return_to_contextual_anchor_payoff", "opening_anchor_id": "",
        "contextual_anchor_id": "ctx_human_torso", "contextual_anchor_subject_id": "human_torso_identity",
        "payoff_reason": script.shots[-1].payoff_reason,
    }
    roster = {entry.id: entry for entry in build_roster(script.shots)}
    assert "human_torso_identity" in roster
    assert "CONTEXTUAL ANCHOR SHEET" in roster["human_torso_identity"].prompt


def test_compiler_persists_contextual_prompt_hash() -> None:
    from services.script_engine import BeatEngine

    script, timeline = _script()
    payload = {"beats": [{"index": index, "text": "measured words preserve required narration budget for contextual anchor validation"} for index in range(1, 6)], "shots": [shot.__dict__ for shot in script.shots]}
    compiled = BeatEngine(None, lang="en", timeline=timeline)._assemble("stomach", payload)  # type: ignore[arg-type]
    assert len(compiled.shots[0].contextual_anchor_prompt_sha256) == 64
    assert compiled.shots[-1].contextual_anchor_prompt_sha256 == compiled.shots[0].contextual_anchor_prompt_sha256


@pytest.mark.parametrize("kind,subject", [("animal", "same_wolf"), ("structure", "same_bridge"), ("vehicle", "same_rocket"), ("object", "same_valve"), ("environment", "same_ice_shelf")])
def test_contextual_identity_categories_reuse_the_same_subject(kind: str, subject: str) -> None:
    script, timeline = _script()
    first, last = script.shots[0], script.shots[-1]
    for shot in (first, last):
        shot.contextual_anchor_kind = kind
        shot.contextual_anchor_subject_id = subject
        shot.subject_id = subject
    assert not validate_script(script, timeline)


def test_contextual_payoff_rejects_wrong_identity_or_decorative_reason() -> None:
    script, timeline = _script()
    script.shots[-1].subject_id = "similar_human"
    assert any("roster identity" in item for item in validate_script(script, timeline))
    script.shots[-1].subject_id = "human_torso_identity"
    script.shots[-1].payoff_reason = "closing"
    assert any("causal non-decorative" in item for item in validate_script(script, timeline))


@pytest.mark.parametrize("blocks", [6, 8, 9, 12, 13])
def test_retime_keeps_contextual_payoff_on_the_last_block(blocks: int) -> None:
    script, _ = _script()
    timeline = TimelinePlan.for_profile("providers_4s", blocks * 4.0)
    retimed = _retime_shots_to_timeline(script, timeline)
    assert retimed.shots[-1].block == blocks
    assert retimed.shots[-1].presentation_mode == "return_to_contextual_anchor_payoff"


def test_retime_prevents_mannequin_leakage_and_preserves_continuous_flight() -> None:
    script, _ = _script()
    # Configure original terminal payoff as continuous flight
    script.shots[-1].endpoint_mode = "first_last"
    script.shots[-1].endpoint_reason = ""
    # Meet 12-block word budget (105..118 words, punchy sentences <= 18 words)
    beat_text = (
        "The stomach wall produces a dense protective mucus barrier against acid. "
        "This prevents the digestive juices from breaking down the living cells."
    )
    script.beats = [Beat(i, beat_text) for i in range(1, 6)]
    timeline = TimelinePlan.for_profile("providers_4s", 12 * 4.0)
    retimed = _retime_shots_to_timeline(script, timeline)

    # 1. Continuous flight mode must be preserved on the terminal payoff
    assert retimed.shots[-1].endpoint_mode == "first_last"

    # 2. No intermediate mechanism shot (shots 1 to 10) may use the external mannequin subject
    for shot in retimed.shots[1:-1]:
        assert shot.subject_id != "human_torso_identity", f"ADR-024 mannequin leak in block {shot.block}"
        assert "human" not in shot.subject_id.casefold()

    # 3. Validation must pass with zero errors
    problems = validate_script(retimed, timeline)
    assert not problems, f"Validation failed: {problems}"


def test_terminal_contextual_graph_has_no_terminal_reframe_or_impact() -> None:
    script, timeline = _script()
    graph = editor.build_filtergraph(
        6, [], False, block_durations=timeline.shot_durations,
        target_duration=timeline.content_duration, coverage=[shot.resolved_coverage_beats for shot in script.shots],
        editorial_plan=build_editorial_plan(script), terminal_payoff=True,
    )
    assert "*lt(time,20.000)" in graph
    assert "xfade=" not in graph


def test_retime_expansion_on_two_shot_outline_enforces_mechanism_mode() -> None:
    """Verify expanding a minimal 2-shot outline converts decomposed middle blocks to presentation_mode='mechanism'."""
    shots = [
        Shot(
            block=1, beat_index=1, t_start=0.0, t_end=4.0,
            subject_id="stylized_mannequin", subject_description="mannequin figure",
            start_image_prompt="start", end_image_prompt="end", motion_prompt="motion",
            visual_domain="anatomical", scale="medium", journey_phase="establish",
            transition_kind="same_subject", dominant_event="event", proof_on_screen="proof",
            entry_state="s1", exit_state="s2", presentation_mode="opening_anchor",
            opening_anchor_id="anchor_mannequin",
        ),
        Shot(
            block=2, beat_index=5, t_start=4.0, t_end=8.0,
            subject_id="stylized_mannequin", subject_description="mannequin figure",
            start_image_prompt="start", end_image_prompt="end", motion_prompt="motion",
            visual_domain="anatomical", scale="medium", journey_phase="resolve",
            transition_kind="same_subject", dominant_event="event", proof_on_screen="proof",
            entry_state="s1", exit_state="s2", presentation_mode="return_to_opening_anchor_payoff",
            opening_anchor_id="anchor_mannequin", payoff_reason="reason here",
            endpoint_mode="first_only", endpoint_reason="terminal quality reason",
        ),
    ]
    timeline2 = TimelinePlan.for_profile("providers_4s", 8.0)
    timeline6 = TimelinePlan.for_profile("providers_4s", 24.0)
    words = "The stomach wall produces a dense protective mucus barrier against acid. This prevents the digestive juices."
    script = Script("test", [Beat(i, words) for i in range(1, 6)], shots, timeline=timeline2)
    retimed = _retime_shots_to_timeline(script, timeline6)

    # Blocks 2 through 5 must be presentation_mode='mechanism'
    for s in retimed.shots[1:-1]:
        assert s.presentation_mode == "mechanism"
        assert s.opening_anchor_id == ""
        assert s.endpoint_mode == "first_last"

    # Terminal block must be the opening-anchor payoff
    assert retimed.shots[-1].presentation_mode == "return_to_opening_anchor_payoff"
    assert retimed.shots[-1].block == 6

