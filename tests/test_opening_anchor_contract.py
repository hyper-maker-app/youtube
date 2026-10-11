from __future__ import annotations

from services.script_engine import BeatEngine, Shot, optimize_for_flow, validate_script
from timeline import TimelinePlan


def _shot(block: int, *, mode: str = "mechanism", anchor: str = "rocket") -> Shot:
    return Shot(
        block=block, beat_index=1 if block == 1 else 3, t_start=(block - 1) * 4.0, t_end=block * 4.0,
        subject_id=anchor, subject_description="a launch rocket", start_image_prompt="latent engine state",
        end_image_prompt="peak engine state", motion_prompt="camera pushes in while combustion pressure expands",
        target_quadrant="top_left", visual_domain="mechanical", dominant_event="combustion pressure expands",
        proof_on_screen="the nozzle pressure plume expands", entry_state="latent pressure", exit_state="peak pressure",
        continuity_anchor=anchor, location_id="void", presentation_mode=mode,
        opening_anchor_id=anchor if mode != "mechanism" else "",
        payoff_reason="The final stable rocket proves the launch mechanism works." if mode.startswith("return_") else "",
        endpoint_mode="first_only" if mode.startswith("return_") else "first_last",
        endpoint_reason="terminal hard-cut payoff" if mode.startswith("return_") else "",
    )


def test_assemble_persists_opening_anchor_and_sanitizes_camera_direction() -> None:
    timeline = TimelinePlan.legacy_from_shots([_shot(1), _shot(2)])
    engine = BeatEngine(None, lang="en", timeline=timeline)  # type: ignore[arg-type]
    payload = {
        "beats": [{"index": index, "text": f"beat {index}"} for index in range(1, 6)],
        "shots": [
            {**_shot(1).__dict__},
            {**_shot(2, mode="return_to_opening_anchor_payoff").__dict__},
        ],
    }
    script = engine._assemble("rocket", payload)
    assert script.shots[0].presentation_mode == "opening_anchor"
    assert script.shots[0].opening_anchor_id == "rocket"
    assert script.shots[-1].presentation_mode == "return_to_opening_anchor_payoff"
    assert script.shots[-1].endpoint_mode == "first_only"
    assert "camera" not in script.shots[-1].motion_prompt.casefold()
    assert "zoom" not in optimize_for_flow(script.shots[-1])["video_prompt"].casefold()


def test_opening_anchor_payoff_is_terminal_and_reuses_identity() -> None:
    timeline = TimelinePlan.legacy_from_shots([_shot(1), _shot(2)])
    first = _shot(1, mode="opening_anchor")
    final = _shot(2, mode="return_to_opening_anchor_payoff")
    from services.script_engine import Beat, Script

    script = Script("rocket", [Beat(index, f"beat {index}") for index in range(1, 6)], [first, final], timeline=timeline)
    assert not validate_script(script, timeline)
    final.opening_anchor_id = "different_rocket"
    assert any("must reuse" in problem for problem in validate_script(script, timeline))
