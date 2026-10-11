from __future__ import annotations

import config
import editor
import release
from timeline import TimelinePlan
from unittest import mock


def _graph(plan: dict | None = None, *, terminal_payoff: bool = False) -> str:
    return editor.build_filtergraph(
        3,
        # Legacy callers can still supply emphasis timings, but they are no
        # longer a visual-effect source.
        [1.0, 4.0],
        False,
        boundaries=[4.0, 8.0],
        block_durations=[4.0, 4.0, 4.0],
        target_duration=12.0,
        boundary_kinds=["change", "change"],
        editorial_plan=plan,
        terminal_payoff=terminal_payoff,
    )


def test_no_editorial_plan_means_no_word_boundary_punch_or_shake() -> None:
    graph = _graph()
    assert "0.060000" not in graph
    assert "sin(2*PI*time" not in graph
    assert "cos(2*PI*time" not in graph
    assert f"{config.BASE_ZOOM}" in graph


def test_explicit_subtle_impact_is_the_only_ffmpeg_pulse() -> None:
    graph = _graph({"boundaries": [{"time": 4.0, "impact_level": "subtle"}]})
    assert f"*{config.SUBTLE_IMPACT_AMOUNT}" in graph
    assert "sin(2*PI*time" not in graph
    # Strong remains diegetic and therefore has no separate FFmpeg camera pulse.
    strong = _graph({"boundaries": [{"time": 4.0, "impact_level": "strong"}]})
    assert f"*{config.SUBTLE_IMPACT_AMOUNT}" not in strong


def test_terminal_payoff_forces_its_incoming_boundary_to_none() -> None:
    resolved = editor.normalize_editorial_plan(
        {"boundaries": [{"boundary": 2, "impact_level": "subtle"}]},
        [4.0, 8.0],
        3,
        terminal_payoff=True,
    )
    assert resolved[-1]["impact_level"] == "none"
    assert f"*{config.SUBTLE_IMPACT_AMOUNT}" not in _graph(
        {"boundaries": [{"boundary": 2, "impact_level": "subtle"}]}, terminal_payoff=True
    )


def test_release_duration_uses_persisted_final_target_not_a_second_tail() -> None:
    timeline = TimelinePlan.for_profile("providers_4s")
    timeline = timeline.__class__(**{**timeline.__dict__, "target_duration": 32.0, "tail_hold": 1.5})
    final_info = mock.Mock(width=config.WIDTH, height=config.HEIGHT, fps=config.FPS, duration=32.0, has_audio=True)
    with mock.patch.object(release.editor, "probe", return_value=final_info), \
         mock.patch.object(release.Path, "write_text"):
        report = release.write_release_report(
            __import__("pathlib").Path("out"), __import__("pathlib").Path("out/final.mp4"),
            None, None, {"blocks": []}, timeline,
        )
    duration = next(check for check in report["checks"] if check["name"] == "duration")
    assert duration["status"] == "pass"
    assert duration["detail"] == "32.0; expected 32.0"


def test_build_editorial_plan_assigns_subtle_impact_to_domain_and_subject_shifts() -> None:
    from pipeline import build_editorial_plan
    from services.script_engine import Beat, Script, Shot

    shot1 = Shot(
        block=1, beat_index=1, t_start=0.0, t_end=4.0, subject_id="lung_tissue",
        visual_domain="biological", transition_kind="same_subject", journey_phase="descend",
        scale="close",
    )
    # Shot 2 is mechanical analogy transition: visual_domain changes biological -> mechanical
    shot2 = Shot(
        block=2, beat_index=2, t_start=4.0, t_end=8.0, subject_id="detergent_plastic",
        visual_domain="mechanical", transition_kind="subject_change", journey_phase="explore",
        scale="macro",
    )
    # Shot 3 stays in same mechanical domain with same subject
    shot3 = Shot(
        block=3, beat_index=3, t_start=8.0, t_end=12.0, subject_id="detergent_plastic",
        visual_domain="mechanical", transition_kind="same_subject", journey_phase="reveal",
        scale="macro",
    )
    script = Script("analogy_test", [Beat(i, f"beat text {i}") for i in range(1, 6)], [shot1, shot2, shot3])
    plan = build_editorial_plan(script)

    boundaries = plan["boundaries"]
    assert len(boundaries) == 2
    # Boundary 1 (between shot 1 and 2): domain shift -> subtle impact
    assert boundaries[0]["boundary"] == 1
    assert boundaries[0]["impact_level"] == "subtle"
    # Boundary 2 (between shot 2 and 3): same domain, same subject -> none
    assert boundaries[1]["boundary"] == 2
    assert boundaries[1]["impact_level"] == "none"


def test_analogy_explore_prompt_enforces_tactile_macro_lighting() -> None:
    from services.script_engine import Shot, compile_keyframe_prompt, optimize_for_flow

    analogy_shot = Shot(
        block=1, beat_index=1, t_start=0.0, t_end=4.0, subject_id="soap_film",
        subject_description="viscous soap layer between plastic sheets",
        visual_domain="mechanical", journey_phase="explore", scale="macro",
        start_image_prompt="soap entering gap", end_image_prompt="soap easing tension",
        motion_prompt="yellow detergent loosens surface tension", dominant_event="fluid spreads between sheets",
        proof_on_screen="detergent eases plastic adhesion", entry_state="stuck", exit_state="gliding",
    )
    kf_prompt = compile_keyframe_prompt(analogy_shot, "start")
    motion_prompt = optimize_for_flow(analogy_shot)["video_prompt"]

    assert "high-contrast studio rim light, tactile macro surface reflections" in kf_prompt
    assert "high-contrast studio rim light, tactile macro surface reflections" in motion_prompt
