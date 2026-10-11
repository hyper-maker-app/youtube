"""Causal-storyboard regressions for the provider-native production pipeline."""

from __future__ import annotations

import pytest

pytest.skip("Archived monolithic generator regression; active screenplay tests are provider-native.", allow_module_level=True)

import hashlib
import json
import subprocess
import tempfile
import inspect
from dataclasses import asdict
from pathlib import Path

import config
import pipeline
import release
from generator import (
    Beat, BeatEngine, ImageForge, Script, Shot, build_script_schema, compile_fal_motion,
    VertexImageForge, lighthouse_anchor_blockers, optimize_for_flow, reusable_refs,
    normalize_lighthouse_v2_exterior_payoff, visual_anchor_for_topic,
)
from narrative import NarrativePlan, NarrativeQualityGate, SceneCard, StoryBeat
from timeline import TimelinePlan


def _story_beats(template: str) -> list[StoryBeat]:
    roles = (
        ("hook", "dark", "signal appears", "signal turns on"),
        ("question" if template == "mechanism_reveal" else "rule", "signal turns on", "power path appears", "battery feeds motor"),
        ("reveal" if template == "mechanism_reveal" else "disruption", "battery feeds motor", "gear moves lens", "lens begins turning"),
        ("constraint" if template == "mechanism_reveal" else "response", "lens begins turning", "storm blocks panel", "stored charge takes over"),
        ("payoff", "stored charge takes over", "beam returns", "same lighthouse is lit"),
    )
    return [
        StoryBeat(
            index=index, role=role, question_in=f"What causes {before}?", answer_out=after,
            cause=f"the prior state causes {event}", visible_event=event,
            state_before=before, state_after=after, new_information=f"new fact {index}",
            open_loop=f"what happens after {after}?", payoff_link="the opening lighthouse signal",
        )
        for index, (role, before, event, after) in enumerate(roles, 1)
    ]


def _cards(count: int = 7) -> list[SceneCard]:
    states = [
        ("dark lighthouse", "lamp ignites", "lit lighthouse"),
        ("lit lighthouse", "panel charges battery", "charged battery"),
        ("charged battery", "battery spins motor", "motor spinning"),
        ("motor spinning", "gear turns lens", "lens rotating"),
        ("lens rotating", "storm covers panel", "panel blocked"),
        ("panel blocked", "stored battery keeps motor running", "motor still spinning"),
        ("motor still spinning", "lens sends the beam over the same island", "lighthouse signal visible"),
    ][:count]
    cards = []
    for index, (entry, event, exit_state) in enumerate(states, 1):
        cards.append(SceneCard(
            scene_id=f"scene{index:02d}", purpose=f"causal step {index}",
            entry_state=entry, exit_state=exit_state, dominant_event=event,
            proof_on_screen=f"visible proof {index}",
            causal_parent_scene_id="" if index == 1 else f"scene{index - 1:02d}",
            next_question="How does the same signal continue?" if index < len(states) else "The opening signal is now explained.",
            asset_states={"lighthouse": "lit" if index else "dark"},
            caption_safe_zone="upper_center", semantic_expected_result=exit_state,
        ))
    return cards


def _plan(template: str = "mechanism_reveal") -> NarrativePlan:
    return NarrativePlan(
        template=template, viewer_question="Why does the lighthouse signal continue?",
        hook_image="a dark island with a beam already sweeping", stake="ships need the beam",
        turn_or_constraint="storm covers the panel", reversal="stored charge takes over",
        final_payoff="The lighthouse signal continues because its stored battery drives the same lens.",
        beats=_story_beats(template),
    )


def _shot(block: int, duration: float = 5.0) -> Shot:
    card = _cards(7)[block - 1]
    return Shot(
        block=block, t_start=(block - 1) * duration, t_end=block * duration,
        subject_id="lighthouse", start_image_prompt="The same lighthouse on its island",
        end_image_prompt="The same lighthouse beam crosses the sea", motion_prompt=card.dominant_event,
        duration=duration, beat_index=min(5, block), start_anchor_id=f"anchor{block:02d}",
        end_anchor_id=f"anchor{block + 1:02d}", continuity_id="lighthouse", endpoint_mode="first_last",
        scene_id=card.scene_id, purpose=card.purpose, entry_state=card.entry_state,
        exit_state=card.exit_state, dominant_event=card.dominant_event,
        proof_on_screen=card.proof_on_screen, causal_parent_scene_id=card.causal_parent_scene_id,
        next_question=card.next_question, asset_states=card.asset_states,
        caption_safe_zone=card.caption_safe_zone, semantic_expected_result=card.semantic_expected_result,
    )


def _lighthouse_anchors(count: int) -> list[dict]:
    """Minimal V2 raw anchors; the compiler owns the repeated composition contract."""
    return [
        {
            "id": f"anchor{index:02d}",
            "index": index,
            "image_prompt": "The same red-and-white lighthouse tower on its rocky island above open sea, with an attached lantern mechanism",
            "subject_id": "lighthouse",
            "subject_description": "the same red-and-white striped lighthouse on its deserted rocky island",
            "camera_angle": "eye_level_front",
            "target_quadrant": "center",
            "visual_profile": "mechanical_detail",
            "effect_tags": [],
            "visual_domain": "technical_mechanism",
            "detail_target": "mechanical",
            "structure_tags": ["circuit"],
            "quality_critical": True,
        }
        for index in range(1, count + 1)
    ]


def test_mechanism_plan_accepts_a_constraint_without_a_myth_bust() -> None:
    report = NarrativeQualityGate().audit(_plan(), _cards(), "The beam is already moving.")
    assert report["accepted"], report


def test_mystery_plan_keeps_the_causal_rule_disruption_response_chain() -> None:
    plan = _plan("mystery_escalation")
    cards = _cards()
    report = NarrativeQualityGate().audit(plan, cards, "The island beam sweeps through a storm.", "fiction")
    assert report["accepted"], report
    assert report["template"] == "mystery_escalation"


def test_storyboard_gate_rejects_static_filler_and_generic_fiction_preamble() -> None:
    cards = _cards()
    cards[3].exit_state = cards[3].entry_state
    report = NarrativeQualityGate().audit(
        _plan("mystery_escalation"), cards,
        "Imagine this fictional story is true. A beam moves across the sea.", "fiction",
    )
    assert not report["accepted"]
    assert any("repeats its entry state" in item for item in report["blockers"])
    assert any("disclaimer consumes" in item for item in report["blockers"])


def test_storyboard_rejects_hud_text_proof_but_allows_a_structured_physical_overlay() -> None:
    cards = _cards()
    cards[1].proof_on_screen = "A full charge HUD gauge reaches 100 percent."
    report = NarrativeQualityGate().audit(_plan(), cards)
    assert not report["accepted"]
    assert any("prohibited hud" in item.lower() for item in report["blockers"])

    cards = _cards()
    cards[1].proof_overlay = {
        "type": "outline", "purpose": "show the relay contact closing", "placement": "left",
    }
    report = NarrativeQualityGate().audit(_plan(), cards)
    assert report["accepted"], report


def test_lighthouse_anchor_rejects_generic_relay_drift_before_provider_work() -> None:
    topic = "The Lighthouse That Still Signals From an Empty Island"
    anchor = visual_anchor_for_topic(topic)
    cards = _cards(7)
    shots = [_shot(index, 8.0) for index in range(1, 8)]
    for shot, card in zip(shots, cards):
        card.asset_states["anchor"] = "same lighthouse on deserted island"
        shot.asset_states = card.asset_states
        shot.asset_refs = ["lighthouse"]
        shot.visual_anchor = anchor
    script = Script(
        topic=topic, beats=[], shots=shots, storyboard=cards, visual_anchor=anchor,
        anchors=_lighthouse_anchors(len(shots) + 1),
    )
    assert not lighthouse_anchor_blockers(script)

    script.shots[1].start_image_prompt = "A generic battery relay device on a laboratory table"
    script.shots[1].end_image_prompt = "The relay closes beside a dashboard"
    script.shots[1].motion_prompt = "the battery indicator decreases"
    blockers = lighthouse_anchor_blockers(script)
    assert any("loses Lighthouse context" in item for item in blockers)
    assert any("unrelated device/building" in item for item in blockers)
    assert any("prohibited indicator" in item for item in blockers)


def test_new_lighthouse_script_persists_anchor_into_cards_and_compiled_vertex_prompt() -> None:
    topic = "The Lighthouse That Still Signals From an Empty Island"
    anchor = visual_anchor_for_topic(topic)
    card = _cards(1)[0]
    card.asset_states["anchor"] = "same lighthouse on deserted island"
    shot = _shot(1, 8.0)
    shot.asset_states = card.asset_states
    shot.asset_refs = ["lighthouse"]
    shot.visual_anchor = anchor
    compiled = optimize_for_flow(shot, visual_anchor=anchor)["video_prompt"].lower()
    assert "immutable visual anchor" in compiled
    assert "no hud, ui, gauge" in compiled
    assert "same red-and-white striped lighthouse" in compiled
    restored = Script.from_dict(Script(topic=topic, beats=[], shots=[shot], visual_anchor=anchor).to_dict())
    assert restored.visual_anchor == anchor
    assert restored.shots[0].visual_anchor == anchor


def test_lighthouse_v2_keyframes_carry_contextual_cable_and_relay_proof() -> None:
    topic = "The Lighthouse That Still Signals From an Empty Island"
    anchor = visual_anchor_for_topic(topic)
    cards = _cards(5)
    cards[1] = SceneCard(
        scene_id="scene02", purpose="Reveal the solar route into the same tower.",
        entry_state="the lantern is lit while the roof solar route remains connected",
        exit_state="stored battery power reaches the same open brass relay",
        dominant_event="the camera follows the same cable from roof panel to open relay",
        proof_on_screen="one uninterrupted copper cable visibly enters the relay housing",
        causal_parent_scene_id="scene01", next_question="What physically closes the relay?",
        asset_states={"anchor": "same lighthouse on deserted island"},
        caption_safe_zone="upper_left", semantic_expected_result="the open relay is reached by the same cable",
    )
    cards[2] = SceneCard(
        scene_id="scene03", purpose="Show the physical relay closure.",
        entry_state="the same brass relay contacts are separated and filament is dark",
        exit_state="the same contacts touch and the same filament is lit",
        dominant_event="the relay arm drops and closes the same brass contacts",
        proof_on_screen="the two contact fingers visibly touch beside the tungsten filament",
        causal_parent_scene_id="scene02", next_question="What does the closed circuit turn?",
        asset_states={"anchor": "same lighthouse on deserted island"},
        caption_safe_zone="upper_right", semantic_expected_result="the completed relay powers the same filament",
    )
    shots = [_shot(index, 8.0) for index in range(1, 6)]
    for shot, card in zip(shots, cards):
        card.asset_states = {"anchor": "same lighthouse on deserted island", **card.asset_states}
        shot.scene_id = card.scene_id
        shot.purpose = card.purpose
        shot.entry_state = card.entry_state
        shot.exit_state = card.exit_state
        shot.dominant_event = card.dominant_event
        shot.proof_on_screen = card.proof_on_screen
        shot.causal_parent_scene_id = card.causal_parent_scene_id
        shot.next_question = card.next_question
        shot.asset_states = card.asset_states
        shot.caption_safe_zone = card.caption_safe_zone
        shot.semantic_expected_result = card.semantic_expected_result
        shot.asset_refs = ["lighthouse"]
        shot.visual_anchor = anchor

    anchors = _lighthouse_anchors(6)
    anchors[1]["image_prompt"] = "Weathered solar panels on the red lighthouse roof, heavy cable entering the tower"
    anchors[2]["image_prompt"] = "Extreme macro photoresistor and separated brass relay contacts on lantern frame"
    anchors[3]["image_prompt"] = "Macro brass relay contacts closed beside an ignited tungsten filament"
    script = Script(
        topic=topic, beats=[], shots=shots, storyboard=cards,
        anchors=anchors, visual_anchor=anchor,
    )

    prompts = {key: prompt.casefold() for key, prompt, _ in ImageForge(Path("."))._build_keyframe_plan(script)}
    cable = prompts["kf02"]
    relay = prompts["kf03"]
    for prompt in (cable, relay):
        assert "lighthouse keyframe contract" in prompt
        assert "red-and-white tower" in prompt
        assert "rocky island" in prompt
        assert "open sea" in prompt
        assert "isolated macro" in prompt
    assert "roof solar panels" in cable
    assert "same open brass relay" in cable
    assert "camera follows the same cable" in cable
    assert "extreme macro" not in relay
    assert "relay contact fingers are visibly separated" in relay
    assert "brass contacts visibly touch" in relay
    assert not lighthouse_anchor_blockers(script)


def test_lighthouse_v1_resume_keeps_its_existing_prompt_contract() -> None:
    topic = "The Lighthouse That Still Signals From an Empty Island"
    anchor = dict(visual_anchor_for_topic(topic))
    anchor["version"] = 1
    anchor["anchor_id"] = "lighthouse_empty_island_v1"
    anchor.pop("keyframe_composition", None)
    cards = _cards(1)
    cards[0].asset_states["anchor"] = "same lighthouse on deserted island"
    shot = _shot(1, 8.0)
    shot.asset_refs = ["lighthouse"]
    shot.asset_states = cards[0].asset_states
    shot.visual_anchor = anchor
    script = Script(topic=topic, beats=[], shots=[shot], storyboard=cards, visual_anchor=anchor)

    compiled = ImageForge(Path("."))._build_keyframe_plan(script)[0][1].casefold()
    assert "lighthouse keyframe contract" not in compiled
    assert "medium contextual lighthouse-attached detail" not in compiled
    assert not lighthouse_anchor_blockers(script)


def test_lighthouse_v2_never_reuses_v1_keyframes_with_a_different_submitted_prompt() -> None:
    """Prompt provenance must include the anchor suffix exactly as Vertex received it."""
    from PIL import Image

    topic = "The Lighthouse That Still Signals From an Empty Island"
    v1_anchor = dict(visual_anchor_for_topic(topic))
    v1_anchor["version"] = 1
    v1_anchor["anchor_id"] = "lighthouse_empty_island_v1"
    v1_anchor.pop("keyframe_composition", None)
    card = _cards(1)[0]
    card.asset_states["anchor"] = "same lighthouse on deserted island"
    shot = _shot(1, 8.0)
    shot.asset_refs = ["lighthouse"]
    shot.asset_states = card.asset_states
    shot.visual_anchor = v1_anchor
    vertex_plan = {
        "normal_image": {"model_id": config.NANO_BANANA_PRO_MODEL, "location": config.VERTEX_LOCATION, "tier": "nano_banana_pro"},
        "hero_image": {"model_id": config.NANO_BANANA_PRO_MODEL, "location": "global", "tier": "nano_banana_pro"},
        "hero_keyframe_indices": [1],
    }
    script = Script(
        topic=topic, beats=[], shots=[shot], storyboard=[card], anchors=_lighthouse_anchors(2),
        visual_anchor=v1_anchor, vertex_plan=vertex_plan,
    )

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        refs: dict[str, dict] = {}
        for kf_id, base_prompt, subject_id in ImageForge(root)._build_keyframe_plan(script):
            index = int(kf_id[2:])
            hero = index in {1}
            policy = vertex_plan["hero_image" if hero else "normal_image"]
            image_path = root / f"{kf_id}.png"
            Image.new("RGB", (90, 160), color=(30, 40, 50)).save(image_path)
            shot_for_overlay = script.shots[index - 1] if index <= len(script.shots) else None
            submitted = VertexImageForge._apply_overlay_policy(
                base_prompt, shot_for_overlay.proof_overlay if shot_for_overlay else {},
            )
            submitted = VertexImageForge._apply_visual_anchor(submitted, script.visual_anchor)
            refs[kf_id] = {
                "kf_id": kf_id, "local": str(image_path),
                "seed": config.deterministic_seed(script.topic, subject_id),
                "provider": "vertex_gemini_image", "model_id": policy["model_id"],
                "tier": "hero" if hero else "normal", "mime_type": "image/png",
                "location": policy["location"], "prompt_sha256": hashlib.sha256(submitted.encode("utf-8")).hexdigest(),
                "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            }
        (root / "refs.json").write_text(json.dumps(refs), encoding="utf-8")

        assert {"kf01", "kf02"}.issubset(reusable_refs(root, script, vertex_plan=vertex_plan))
        v2_anchor = visual_anchor_for_topic(topic)
        script.visual_anchor = v2_anchor
        script.shots[0].visual_anchor = v2_anchor
        assert not [key for key in reusable_refs(root, script, vertex_plan=vertex_plan) if key.startswith("kf")]


def test_lighthouse_v2_uses_safe_first_last_conditioning_for_cable_and_relay() -> None:
    timeline = TimelinePlan.for_profile("vertex_veo_fast")
    cards = _cards(5)
    cards[1] = SceneCard(
        scene_id="scene02", purpose="Reveal solar route.", entry_state="solar route connected",
        exit_state="power reaches open relay", dominant_event="the camera follows cable to relay",
        proof_on_screen="cable enters relay", causal_parent_scene_id="scene01",
        next_question="What closes it?", asset_states={}, caption_safe_zone="upper_left",
        semantic_expected_result="open relay is reached",
    )
    cards[2] = SceneCard(
        scene_id="scene03", purpose="Close relay.", entry_state="contacts open",
        exit_state="contacts closed and filament lit", dominant_event="relay arm closes contacts",
        proof_on_screen="contact fingers touch beside filament", causal_parent_scene_id="scene02",
        next_question="What turns next?", asset_states={}, caption_safe_zone="upper_right",
        semantic_expected_result="filament is lit",
    )
    subjects = ["lighthouse", "solar_route", "relay", "relay", "lens", "lighthouse"]
    keyframes = []
    for index, subject_id in enumerate(subjects, 1):
        keyframes.append({
            "index": index, "subject_id": subject_id,
            "subject_description": "the same red-and-white lighthouse and attached mechanism",
            "scale": "medium", "camera_angle": "low_angle" if index == 6 else "eye_level_front",
            "image_prompt": "The same red-and-white lighthouse tower on its rocky island above open sea, with attached lantern mechanism",
            "target_quadrant": "center", "asset_refs": ["lighthouse"],
            "visual_profile": "mechanical_detail", "effect_tags": [],
            "visual_domain": "technical_mechanism", "detail_target": "mechanical",
            "structure_tags": ["circuit"], "quality_critical": True,
        })
    raw = {
        "narrative_plan": _plan().to_dict(),
        "beats": [
            {"index": index, "role": "hook", "text": "The same lighthouse keeps its signal alive through the empty island night with a visible physical mechanism.", "emphasis": ["lighthouse"]}
            for index in range(1, 6)
        ],
        "keyframes": keyframes,
        "youtube": {"titles": ["A", "B", "C"], "description": "D", "tags": ["shorts"]},
        "shots": [
            {
                "block": index, "beat_index": index, "start_keyframe_index": index,
                "end_keyframe_index": index + 1, "motion_prompt": card.dominant_event,
                "chain_from_prev": index > 1,
                "transition_hint": "match_cut" if index == 5 else "none",
                "endpoint_mode": "cut", "scene_card": asdict(card),
            }
            for index, card in enumerate(cards, 1)
        ],
    }
    script = BeatEngine(provider="codefast", lang="en", content_type="fiction", timeline=timeline)._assemble(
        "The Lighthouse That Still Signals From an Empty Island", raw,
    )
    assert script.visual_anchor["version"] == 2
    assert script.shots[1].endpoint_mode == "first_last"  # cable route
    assert script.shots[2].endpoint_mode == "first_last"  # relay closure
    assert script.shots[4].endpoint_mode == "cut"  # deliberately unsafe match cut remains untouched


def test_lighthouse_v2_final_beam_payoff_normalizes_to_a_stable_exterior_anchor() -> None:
    """Only a V2 final beam payoff replaces an inherited gear/match-cut setup."""
    anchor = visual_anchor_for_topic("The Lighthouse That Still Signals From an Empty Island")
    payoff = _shot(5, 8.0)
    payoff.visual_anchor = anchor
    payoff.purpose = "Final lighthouse payoff"
    payoff.dominant_event = "The lighthouse beam sweeps across the open sea"
    payoff.proof_on_screen = "A beam sweeps through fog"
    payoff.start_image_prompt = "Interior macro of gears around a filament"
    payoff.end_image_prompt = "Exterior lighthouse beam"
    payoff.transition_hint = "match_cut"
    payoff.structure_tags = ["gear", "cross_section", "circuit"]
    prior = _shot(4, 8.0)
    prior.visual_anchor = anchor
    anchors = [
        {"index": 5, "image_prompt": payoff.start_image_prompt, "structure_tags": ["gear", "cross_section"]},
        {"index": 6, "image_prompt": payoff.end_image_prompt, "structure_tags": ["gear"]},
    ]

    assert normalize_lighthouse_v2_exterior_payoff([prior, payoff], anchors, 5)
    assert payoff.endpoint_mode == "first_last"
    assert payoff.transition_hint == "none"
    assert payoff.start_camera_angle == payoff.end_camera_angle == "eye_level_front"
    assert {"gear", "cross_section"}.isdisjoint(payoff.structure_tags)
    for prompt in (payoff.start_image_prompt, anchors[0]["image_prompt"]):
        lowered = prompt.casefold()
        assert "red-and-white striped lighthouse tower" in lowered
        assert "rocky island" in lowered
        assert "open sea" in lowered
        assert "lantern glass" in lowered
    assert prior.end_image_prompt == payoff.start_image_prompt

    v1 = _shot(5, 8.0)
    v1.visual_anchor = {"kind": "lighthouse_empty_island", "version": 1}
    original = (v1.start_image_prompt, v1.transition_hint, list(v1.structure_tags))
    assert not normalize_lighthouse_v2_exterior_payoff([v1], [], 5)
    assert (v1.start_image_prompt, v1.transition_hint, v1.structure_tags) == original


def test_phase2_only_allows_timing_repair_in_explicit_calibration_mode() -> None:
    source = inspect.getsource(pipeline.phase2_3_assets)
    assert "config.CALIBRATION_MODE" in source
    assert "_rewrite_script_for_timing" in source


def test_new_schema_requires_storyboard_not_a_camera_journey() -> None:
    schema = build_script_schema(TimelinePlan.for_profile("h3_max"))
    assert "narrative_plan" in schema["required"]
    assert "journey" not in schema["required"]
    assert "scene_card" in schema["properties"]["shots"]["items"]["required"]


def test_event_prompt_uses_scene_card_without_phase_vfx_injection() -> None:
    shot = _shot(1, 8.0)
    flow = optimize_for_flow(shot)["video_prompt"].lower()
    fal = compile_fal_motion(shot).lower()
    for forbidden in ("fissure", "corona", "neon-green", "red trajectory"):
        assert forbidden not in flow
        assert forbidden not in fal
    assert "lamp ignites" in flow
    assert "upper_center" in flow
    assert "full 8-second take" in flow


def test_assembler_persists_new_narrative_plan_and_scene_cards() -> None:
    timeline = TimelinePlan.for_profile("h3_max")
    plan = _plan()
    cards = _cards()
    beats = [
        {"index": index, "role": "hook" if index == 1 else "reveal", "text": "The lighthouse beam changes because its hidden power path keeps moving through the storm tonight.", "emphasis": ["lighthouse"]}
        for index in range(1, 6)
    ]
    keyframes = [
        {
            "index": index, "subject_id": "lighthouse", "subject_description": "the same white lighthouse on one rocky island",
            "scale": "medium", "camera_angle": "eye_level_front", "image_prompt": "The same lighthouse on a rocky island",
            "target_quadrant": "center", "asset_refs": ["lighthouse"], "visual_profile": "documentary_pbr",
            "effect_tags": [], "visual_domain": "character", "detail_target": "editorial", "structure_tags": [], "quality_critical": False,
        }
        for index in range(1, timeline.keyframe_count + 1)
    ]
    raw = {
        "narrative_plan": plan.to_dict(), "beats": beats, "keyframes": keyframes,
        "youtube": {"titles": ["A", "B", "C"], "description": "D", "tags": ["shorts"]},
        "shots": [
            {
                "block": index, "beat_index": min(5, index), "start_keyframe_index": index,
                "end_keyframe_index": index + 1, "motion_prompt": card.dominant_event,
                "chain_from_prev": index > 1, "transition_hint": "none", "scene_card": asdict(card),
            }
            for index, card in enumerate(cards, 1)
        ],
    }
    script = BeatEngine(provider="codefast", lang="en", timeline=timeline)._assemble("test", raw)
    assert script.narrative_plan and script.narrative_plan.template == "mechanism_reveal"
    assert [shot.scene_id for shot in script.shots] == [card.scene_id for card in cards]
    saved = Script.from_dict(script.to_dict())
    assert len(saved.storyboard) == 7
    assert not saved.shots[0].journey_phase


def test_storyboard_artifacts_and_legacy_resume_stay_separate() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        timeline = TimelinePlan.for_profile("h3_max")
        shots = [_shot(block) for block in range(1, 8)]
        script = Script(
            topic="test", beats=[Beat(i, "hook", "A beam moves.", ["beam"]) for i in range(1, 6)],
            shots=shots, timeline=timeline, narrative_plan=_plan(), storyboard=_cards(),
            storyboard_report=NarrativeQualityGate().audit(_plan(), _cards()),
        )
        ctx = pipeline.RunContext(topic="test", out_dir=root, timeline=timeline, animate="manual")
        paths = pipeline.write_storyboard(ctx, script)
        assert paths and all(path.exists() for path in paths)
        handoff = pipeline.write_handoff(ctx, script)
        assert (handoff / "storyboard.json").exists()
        assert (handoff / "storyboard.md").exists()
        assert len(list(handoff.glob("block*_video_prompt.txt"))) == 7
        assert not list(handoff.glob("block*_regeneration_prompt.txt"))

        legacy = Script.from_dict({
            "topic": "legacy", "beats": [], "shots": [{
                "block": 1, "t_start": 0, "t_end": 4, "subject_id": "old", "start_image_prompt": "a",
                "end_image_prompt": "b", "motion_prompt": "the old lamp turns",
            }],
        })
        legacy_ctx = pipeline.RunContext(topic="legacy", out_dir=root / "legacy", timeline=legacy.timeline, resumed=True)
        assert pipeline.write_storyboard(legacy_ctx, legacy) is None
        assert not (legacy_ctx.out_dir / "storyboard.json").exists()


def test_lighthouse_style_legacy_fixture_is_diagnosed_without_upgrading_it() -> None:
    legacy = Script.from_dict({
        "topic": "The lighthouse that still signals", "content_type": "fiction",
        "beats": [{"index": 1, "role": "myth", "text": "Imagine this fictional story is true. The island is empty but its light turns.", "emphasis": ["light"]}],
        "shots": [{
            "block": 1, "t_start": 0, "t_end": 4, "subject_id": "lighthouse",
            "start_image_prompt": "An empty lighthouse with a solar bank", "end_image_prompt": "Clockwork gears and falling weights",
            "motion_prompt": "the lens turns", "journey_phase": "establish",
        }],
    })
    report = NarrativeQualityGate().audit_legacy_script(legacy, {
        "blocks": [{"visual_quality": {"reasons": ["industrial metal crushing and debris replace the lighthouse"]}}],
    })
    assert not report["accepted"]
    assert report["legacy_fixture"]
    assert any("fiction disclaimer" in item for item in report["blockers"])
    assert any("power chains" in item for item in report["blockers"])
    assert any("drifts away" in item for item in report["blockers"])
    assert legacy.narrative_plan is None
    assert legacy.timeline.legacy


def test_semantic_blocker_is_never_publishable() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        final = root / "final.mp4"
        ffmpeg = config.resolve_ffmpeg()
        subprocess.run([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
            "-i", "testsrc2=size=360x640:rate=12:duration=1", "-f", "lavfi", "-i", "sine=frequency=220:duration=1",
            "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35", "-pix_fmt", "yuv420p", "-c:a", "aac", str(final),
        ], check=True)
        timeline = TimelinePlan.legacy_from_shots([_shot(1, 1.0)])
        report = release.write_release_report(
            root, final, None, None,
            {"blocks": [{"accepted": True, "semantic_quality_blocker": True, "semantic_quality": {"accepted": False}}]},
            timeline,
        )
        assert not report["publishable"]
        checks = {item["name"]: item["status"] for item in report["checks"]}
        assert checks["semantic_continuity"] == "fail"
