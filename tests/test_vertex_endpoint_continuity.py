from __future__ import annotations

import pytest

pytest.skip("Archived monolithic generator regression; endpoint continuity now belongs to provider adapters and script-engine tests.", allow_module_level=True)

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import pipeline
from generator import (
    Beat,
    Script,
    Shot,
    VertexVeoError,
    VertexVeoForge,
    lighthouse_v3_endpoint_blockers,
    normalize_lighthouse_v3_endpoint_modes,
    visual_anchor_for_topic,
)
from timeline import TimelinePlan


def _shot(block: int, view: str, endpoint: str = "first_last") -> Shot:
    anchor = visual_anchor_for_topic("The Lighthouse That Still Signals From an Empty Island")
    return Shot(
        block=block, t_start=(block - 1) * 8, t_end=block * 8,
        subject_id="lighthouse", start_image_prompt="The same lighthouse", end_image_prompt="The same lighthouse",
        motion_prompt="the beacon moves", start_anchor_id=f"anchor{block:02d}",
        end_anchor_id=f"anchor{block + 1:02d}", continuity_id="lighthouse",
        endpoint_mode=endpoint, endpoint_requested_mode=endpoint, anchor_view=view,
        visual_anchor=anchor, scene_id=f"scene{block:02d}", entry_state="start",
        exit_state="end", dominant_event="the beacon moves", proof_on_screen="the beacon",
    )


def _script(shots: list[Shot]) -> Script:
    return Script(
        topic="The Lighthouse That Still Signals From an Empty Island",
        beats=[Beat(index=1, role="hook", text="The lighthouse still signals.")],
        shots=shots, timeline=TimelinePlan.for_profile("vertex_veo_fast"),
        visual_anchor=visual_anchor_for_topic("The Lighthouse That Still Signals From an Empty Island"),
    )


def test_v3_exterior_to_tower_interior_normalizes_to_cut() -> None:
    shots = [_shot(1, "exterior"), _shot(2, "tower_interior")]
    normalize_lighthouse_v3_endpoint_modes(shots)
    assert shots[0].endpoint_mode == "cut"
    assert "exterior -> tower_interior" in shots[0].endpoint_normalization_reason


def test_v3_same_exterior_view_keeps_first_last_conditioning() -> None:
    shots = [_shot(1, "exterior"), _shot(2, "exterior")]
    normalize_lighthouse_v3_endpoint_modes(shots)
    assert shots[0].endpoint_mode == "first_last"
    assert "compatible" in shots[0].endpoint_normalization_reason


def test_v3_persisted_cross_view_last_frame_is_precredit_blocker() -> None:
    script = _script([_shot(1, "tower_interior"), _shot(2, "lantern_room")])
    blockers = lighthouse_v3_endpoint_blockers(script)
    assert any("tower_interior -> lantern_room" in blocker for blocker in blockers)


def test_continuity_report_captures_normalization_and_last_frame_plan() -> None:
    shots = [_shot(1, "exterior"), _shot(2, "tower_interior")]
    normalize_lighthouse_v3_endpoint_modes(shots)
    with TemporaryDirectory() as root:
        ctx = pipeline.RunContext(
            topic="test", out_dir=Path(root), effective_source="vertex",
            timeline=TimelinePlan.for_profile("vertex_veo_fast"),
        )
        report = json.loads(pipeline._write_continuity_report(ctx, _script(shots)).read_text(encoding="utf-8"))
    first = report["blocks"][0]
    assert first["start_anchor_view"] == "exterior"
    assert first["end_anchor_view"] == "tower_interior"
    assert first["endpoint_mode"] == "cut"
    assert first["vertex_last_frame_planned"] is False
    assert report["summary"]["normalized_to_cut_blocks"] == [1, 2]


def test_v2_endpoint_is_not_reinterpreted_by_v3_normalizer() -> None:
    old = _shot(1, "exterior")
    old.visual_anchor = {"kind": "lighthouse_empty_island", "version": 2}
    old.endpoint_normalization_reason = ""
    script = Script(topic="legacy", beats=[], shots=[old], visual_anchor=old.visual_anchor)
    assert lighthouse_v3_endpoint_blockers(script) == []
    data = script.to_dict()["shots"][0]
    assert "endpoint_normalization_reason" not in data


def test_exhausted_vertex_resume_does_not_submit_a_fourth_candidate() -> None:
    script = _script([_shot(1, "exterior"), _shot(2, "exterior")])
    plan = {
        "normal_video": {"motion_model": "vertex_veo_fast", "model_id": "veo-3.1-fast-generate-001"},
        "hero_video": {"motion_model": "vertex_veo_fast", "model_id": "veo-3.1-fast-generate-001"},
    }
    with TemporaryDirectory() as root:
        forge = VertexVeoForge(Path(root), plan)
        state = {"status": "calibration_exhausted", "block01": {"status": "calibration_exhausted", "attempts": 3}}
        with mock.patch.object(forge, "_project_id", return_value="project"), \
             mock.patch.object(forge, "_submit_and_wait") as submit:
            try:
                asyncio.run(forge.generate(script, {}, state))
            except VertexVeoError as exc:
                assert "exhausted calibration attempts" in str(exc)
            else:
                raise AssertionError("exhausted resume unexpectedly continued")
        submit.assert_not_called()
