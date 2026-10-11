from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path

from services.script_engine import Beat, Script, Shot, _required_beat_indices, validate_script, BeatEngine
from timeline import TimelinePlan
import config


def _make_shot(
    block: int,
    scale: str = "medium",
    subject_id: str = "valve_core",
    continuity_anchor: str = "valve_anchor",
    transition_kind: str = "same_subject",
) -> Shot:
    start = (block - 1) * 4.0
    return Shot(
        block=block,
        beat_index=_required_beat_indices(6)[min(block - 1, 5)],
        t_start=start,
        t_end=start + 4.0,
        subject_id=subject_id,
        subject_description="mechanical valve assembly",
        start_image_prompt="valve in starting position",
        end_image_prompt="valve in moved position",
        motion_prompt="valve rotates under mechanical torque",
        target_quadrant="center",
        visual_domain="mechanical",
        scale=scale,
        journey_phase="explore",
        transition_kind=transition_kind,
        continuity_anchor=continuity_anchor,
        entry_state="valve locked",
        exit_state="valve releases fluid",
        dominant_event="valve releases pressurized fluid",
        proof_on_screen="fluid streams through opened gap",
        location_id="valve_chamber",
        presentation_mode="mechanism",
    )


def test_validator_rejects_scale_transition_without_scale_change() -> None:
    timeline = TimelinePlan.for_profile("providers_4s", 24.0)
    shot1 = _make_shot(1, scale="medium", transition_kind="same_subject")
    shot1.presentation_mode = "opening_anchor"
    shot1.opening_anchor_id = "valve_anchor"
    
    shot2 = _make_shot(2, scale="medium", transition_kind="scale_transition")
    shots = [shot1, shot2] + [_make_shot(i) for i in range(3, 7)]
    
    script = Script(
        "valve",
        [Beat(i, f"beat text word count budget check beat {i} here") for i in range(1, 6)],
        shots,
        timeline=timeline,
    )
    problems = validate_script(script, timeline)
    assert any("says scale_transition but scale is unchanged" in p for p in problems)


def test_validator_accepts_valid_scale_transition() -> None:
    timeline = TimelinePlan.for_profile("providers_4s", 24.0)
    shot1 = _make_shot(1, scale="medium", transition_kind="same_subject")
    shot1.presentation_mode = "opening_anchor"
    shot1.opening_anchor_id = "valve_anchor"
    
    shot2 = _make_shot(2, scale="close", transition_kind="scale_transition")
    shots = [shot1, shot2] + [_make_shot(i) for i in range(3, 7)]
    
    script = Script(
        "valve",
        [Beat(i, f"beat text word count budget check beat {i} here") for i in range(1, 6)],
        shots,
        timeline=timeline,
    )
    problems = validate_script(script, timeline)
    assert not any("scale_transition" in p for p in problems)


def test_reverse_correction_converts_false_subject_change_to_same_subject() -> None:
    timeline = TimelinePlan.for_profile("providers_4s", 24.0)
    engine = BeatEngine(None, lang="en", timeline=timeline)  # type: ignore[arg-type]

    payload = {
        "beats": [{"index": i, "text": f"narration beat text number {i} spoken words"} for i in range(1, 6)],
        "shots": [
            _make_shot(1, scale="medium", transition_kind="same_subject").__dict__,
            _make_shot(2, scale="medium", transition_kind="subject_change").__dict__,
        ] + [_make_shot(i).__dict__ for i in range(3, 7)],
    }
    assembled = engine._assemble("valve", payload)
    assert assembled.shots[1].transition_kind == "same_subject"


def test_reverse_correction_preserves_genuine_scale_transition() -> None:
    timeline = TimelinePlan.for_profile("providers_4s", 24.0)
    engine = BeatEngine(None, lang="en", timeline=timeline)  # type: ignore[arg-type]

    payload = {
        "beats": [{"index": i, "text": f"narration beat text number {i} spoken words"} for i in range(1, 6)],
        "shots": [
            _make_shot(1, scale="medium", transition_kind="same_subject").__dict__,
            _make_shot(2, scale="close", transition_kind="scale_transition").__dict__,
        ] + [_make_shot(i).__dict__ for i in range(3, 7)],
    }
    assembled = engine._assemble("valve", payload)
    assert assembled.shots[1].transition_kind == "scale_transition"


def test_reverse_correction_converts_same_subject_with_scale_change_to_scale_transition() -> None:
    timeline = TimelinePlan.for_profile("providers_4s", 24.0)
    engine = BeatEngine(None, lang="en", timeline=timeline)  # type: ignore[arg-type]

    payload = {
        "beats": [{"index": i, "text": f"narration beat text number {i} spoken words"} for i in range(1, 6)],
        "shots": [
            _make_shot(1, scale="medium", transition_kind="same_subject").__dict__,
            _make_shot(2, scale="close", transition_kind="same_subject").__dict__,
        ] + [_make_shot(i).__dict__ for i in range(3, 7)],
    }
    assembled = engine._assemble("valve", payload)
    assert assembled.shots[1].transition_kind == "scale_transition"


def test_reverse_correction_converts_same_subject_with_camera_angle_change_to_scale_transition() -> None:
    timeline = TimelinePlan.for_profile("providers_4s", 24.0)
    engine = BeatEngine(None, lang="en", timeline=timeline)  # type: ignore[arg-type]

    shot1 = _make_shot(1, scale="medium", transition_kind="same_subject")
    shot1.camera_angle = "eye_level"
    shot2 = _make_shot(2, scale="medium", transition_kind="same_subject")
    shot2.camera_angle = "low_angle_macro"

    payload = {
        "beats": [{"index": i, "text": f"narration beat text number {i} spoken words"} for i in range(1, 6)],
        "shots": [shot1.__dict__, shot2.__dict__] + [_make_shot(i).__dict__ for i in range(3, 7)],
    }
    assembled = engine._assemble("valve", payload)
    assert assembled.shots[1].transition_kind == "scale_transition"

