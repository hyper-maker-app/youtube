from __future__ import annotations

import pytest

import config
import editor
from pipeline import audio_driven_timeline
from services.asset_roster import build_roster, manifest
from services.script_engine import Shot, compile_keyframe_prompt, optimize_for_flow, sanitize_eli12_narration


def _shot() -> Shot:
    return Shot(
        block=1, beat_index=1, t_start=0.0, t_end=4.0, subject_id="heart_valve",
        subject_description="an anatomical heart valve", start_image_prompt="latent valve opening",
        end_image_prompt="peak valve opening", motion_prompt="rhythmic muscular contraction opens the valve",
        dominant_event="muscle pressure opens the valve", proof_on_screen="the valve aperture widens",
        entry_state="latent closed valve", exit_state="peak open valve", continuity_anchor="same valve",
        visual_domain="anatomy", detail_target="layered tissue", location_id="void", target_quadrant="top_left",
    )


@pytest.mark.parametrize(("voice", "blocks"), [(23.0, 6), (35.0, 9), (47.0, 12)])
def test_audio_locked_plan_persists_tail_inside_final_target(voice: float, blocks: int) -> None:
    plan = audio_driven_timeline(voice)
    data = plan.to_dict()
    assert plan.block_count == blocks
    assert data["n_blocks"] == blocks
    assert data["footage_duration"] == blocks * 4.0
    assert data["target_duration"] >= voice + 0.4
    assert data["content_duration"] == pytest.approx(data["target_duration"] - config.TAIL_HOLD)


def test_roster_uses_run_local_ratios_and_subject_bleed_guard() -> None:
    entries = build_roster([_shot()])
    by_id = {entry.id: entry for entry in entries}
    assert by_id["environment_void"].aspect_ratio == "9:16"
    assert "ABSOLUTELY NO people, NO animals, NO characters, NO subject" in by_id["environment_void"].prompt
    assert by_id["heart_valve"].aspect_ratio == "1:1"
    persisted = manifest(entries, {entry.id: f"roster/{entry.id}.png" for entry in entries})
    assert all(entry["prompt_sha256"] and entry["local"] for entry in persisted["entries"])


def test_canonical_prompt_uses_diegetic_motion_and_hard_coverage_windows() -> None:
    shot = _shot()
    compiled = compile_keyframe_prompt(shot, "start") + optimize_for_flow(shot)["video_prompt"]
    assert "dark neutral 3D studio void" in compiled
    assert "sharp cyan rim light" in compiled
    assert "camera push" not in compiled.casefold()
    assert "camera zoom" not in compiled.casefold()
    assert all(term not in compiled.casefold() for term in ("photorealistic", "realistic", "real life", "stylized-realistic"))
    graph = editor.build_filtergraph(
        1, [], False, boundaries=[], block_durations=[2.5], target_duration=2.5,
        coverage=[shot.resolved_coverage_beats], transitions_enabled=False,
    )
    assert "xfade=" not in graph
    assert "gte(time," in graph and "*lt(time," in graph
    assert "clip(iw*" in graph and "iw-(iw/zoom)" in graph


def test_material_domain_shaders_and_continuous_flight_coverage() -> None:
    rubber_shot = Shot(
        block=1, beat_index=1, t_start=0.0, t_end=4.0, subject_id="rubber_hose",
        subject_description="a vulcanized rubber hose under hydraulic pressure",
        start_image_prompt="hose latent", end_image_prompt="hose peak",
        motion_prompt="pressure expands the elastomer hose",
        dominant_event="hydraulic pressure expands hose", proof_on_screen="hose wall strains",
        entry_state="relaxed", exit_state="expanded", continuity_anchor="same hose",
        visual_domain="mechanical", detail_target="vulcanized elastomer rubber hose",
    )
    rubber_prompt = compile_keyframe_prompt(rubber_shot, "start")
    assert "matte vulcanized elastomer" in rubber_prompt
    assert "Glossy Stylized 3D Medical and Scientific Cutaway Visualization Render" in rubber_prompt
    assert "Mannequin" not in rubber_prompt

    flight_shot = Shot(
        block=1, beat_index=1, t_start=0.0, t_end=4.0, subject_id="cornea",
        subject_description="corneal tissue surface",
        start_image_prompt="surface", end_image_prompt="deep tissue",
        motion_prompt="optical camera accelerates inward penetrating tissue boundary",
        dominant_event="camera penetrates cornea", proof_on_screen="retinal layer visible",
        entry_state="cornea", exit_state="retina", continuity_anchor="eye",
        visual_domain="anatomical", transition_kind="scale_transition", scale="micro",
        journey_phase="descend",
        coverage_beats=[{"duration": 1.333, "quadrant": "top_left"}, {"duration": 2.667, "quadrant": "top_right"}],
    )
    beats = flight_shot.resolved_coverage_beats
    assert all(b["quadrant"] == "center" for b in beats)

    # Bone & Fluid PBR domain shaders
    bone_shot = Shot(
        block=1, beat_index=1, t_start=0.0, t_end=4.0, subject_id="femur_bone",
        subject_description="cortical bone cross section under tension",
        start_image_prompt="bone", end_image_prompt="bone peak",
        motion_prompt="tensile load stresses cortical bone",
        dominant_event="micro-stress on bone", proof_on_screen="enamel and bone micro-grooves",
        entry_state="latent", exit_state="stressed", continuity_anchor="femur",
        visual_domain="anatomical", detail_target="mineralized cortical bone and teeth enamel",
    )
    bone_prompt = compile_keyframe_prompt(bone_shot, "start")
    assert "mineralized cortical bone texture" in bone_prompt
    assert "ivory enamel micro-structure" in bone_prompt

    fluid_shot = Shot(
        block=1, beat_index=1, t_start=0.0, t_end=4.0, subject_id="alveolar_surfactant",
        subject_description="viscous surfactant fluid barrier",
        start_image_prompt="fluid", end_image_prompt="fluid peak",
        motion_prompt="viscous surfactant fluid flows over membrane",
        dominant_event="fluid spreads", proof_on_screen="liquid surface tension",
        entry_state="latent", exit_state="flowing", continuity_anchor="surfactant",
        visual_domain="biological", detail_target="viscous surfactant fluid droplet",
    )
    fluid_prompt = compile_keyframe_prompt(fluid_shot, "start")
    assert "viscous non-Newtonian fluid dynamics" in fluid_prompt

    # Roster mannequin decoupling on cutaway objects
    cutaway_roster = build_roster([_shot()])
    valve_entry = next(e for e in cutaway_roster if e.id == "heart_valve")
    assert "Glossy Stylized 3D Medical and Scientific Cutaway Model Render" in valve_entry.prompt
    assert "Mannequin" not in valve_entry.prompt

    # ELI12 expansions
    assert sanitize_eli12_narration("peristalsis pushes food") == "wave-like muscular squeezing pushes food"
    assert sanitize_eli12_narration("the tympanic membrane vibrates") == "the eardrum vibrates"
    assert sanitize_eli12_narration("the sphincter closes") == "the tight muscular ring valve closes"

