"""Unit tests for the 6 screenplay, visual review, and roster refinements.

Tasks covered:
1. services/asset_roster.py — two-pass roster description backfill
2. services/script_engine.py — character contrast validator and system prompt
3. providers/image/nano_banana_pro.py — fail-closed review gate on error/missing config
4. providers/image/nano_banana_pro.py — expanded review rubric
5. services/script_engine.py — scale anchor for incident macro/close shots
6. services/script_engine.py — persistent damage/trauma into resolution shots
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from providers.image.nano_banana_pro import NanoBananaProProvider
from services.asset_roster import build_roster
from services.mode_profile import INCIDENT
from services.script_engine import (
    Beat,
    Script,
    Shot,
    _required_beat_indices,
    compile_keyframe_prompt,
    optimize_for_flow,
    validate_script,
)
from timeline import TimelinePlan


def test_asset_roster_backfill_prefers_primary_description():
    """Task 1: Two shots reference the same id: first as secondary (no description),

    later as primary (with a real description). Assert the final roster entry
    uses the real description, not the bare id.
    """
    shot1 = Shot(
        block=1,
        beat_index=1,
        t_start=0.0,
        t_end=4.0,
        subject_id="captain_pilot",
        subject_description="Airline Captain: 4 gold stripes on shoulder epaulets",
        secondary_subject_ids=["copilot"],
    )
    shot2 = Shot(
        block=2,
        beat_index=2,
        t_start=4.0,
        t_end=8.0,
        subject_id="copilot",
        subject_description="First Officer Copilot wearing crisp white uniform shirt and 3 stripes",
        secondary_subject_ids=[],
    )
    entries = build_roster([shot1, shot2], mode=INCIDENT)
    copilot_entry = next((e for e in entries if e.id == "copilot"), None)
    assert copilot_entry is not None
    assert "First Officer Copilot wearing crisp white uniform shirt and 3 stripes" in copilot_entry.prompt
    assert "Subject: copilot." not in copilot_entry.prompt


def test_validate_script_flags_character_contrast_violation():
    """Task 2: Two near-identical descriptions sharing dominant color/clothing keywords

    in incident mode must be flagged by validate_script().
    """
    timeline = TimelinePlan.for_profile("providers_4s", 24.0)
    shot1 = Shot(
        block=1,
        beat_index=1,
        t_start=0.0,
        t_end=4.0,
        subject_id="captain_pilot",
        subject_description="Pilot wearing dark navy uniform",
        secondary_subject_ids=["copilot"],
        presentation_mode="opening_anchor",
        opening_anchor_id="captain_pilot",
        start_image_prompt="Captain seated in flight deck",
        end_image_prompt="Captain operating control yoke",
        motion_prompt="Hands on controls",
        entry_state="calm flight deck",
        exit_state="turbulent flight deck",
        dominant_event="cockpit turbulence begins",
        proof_on_screen="flight control yoke rattles",
    )
    shot2 = Shot(
        block=2,
        beat_index=2,
        t_start=4.0,
        t_end=8.0,
        subject_id="copilot",
        subject_description="Copilot wearing dark navy uniform",
        secondary_subject_ids=[],
        start_image_prompt="Copilot reaching for oxygen mask",
        end_image_prompt="Copilot securing oxygen mask",
        motion_prompt="Reaching for emergency controls",
        entry_state="oxygen mask stowed",
        exit_state="oxygen mask secured",
        dominant_event="oxygen mask deployed",
        proof_on_screen="oxygen mask over mouth and nose",
    )
    req_beats = _required_beat_indices(6)
    shots = [shot1, shot2]
    for b in range(3, 7):
        shots.append(Shot(
            block=b,
            beat_index=req_beats[b - 1],
            t_start=(b - 1) * 4.0,
            t_end=b * 4.0,
            subject_id="flight_attendant_01",
            subject_description="Crew member in burgundy vest",
            start_image_prompt="Cabin view",
            end_image_prompt="Cabin secured",
            motion_prompt="Moving through aisle",
            entry_state="cabin alert",
            exit_state="cabin braced",
            dominant_event="cabin secured",
            proof_on_screen="brace position confirmed",
        ))
    beats = [Beat(i, f"Narration sentence one for beat. Narration sentence two for beat {i}.") for i in range(1, 6)]
    script = Script("Contrast Test", beats, shots, timeline=timeline, mode="incident")
    problems = validate_script(script, timeline, mode=INCIDENT)
    contrast_problems = [p for p in problems if "character contrast violation" in p]
    assert len(contrast_problems) >= 1
    assert "captain_pilot" in contrast_problems[0]
    assert "copilot" in contrast_problems[0]


def test_nano_banana_pro_review_gate_fail_closed_on_client_exception(tmp_path: Path):
    """Task 3: Client exception in review_keyframe must return accepted=False

    with status 'reviewed' so caller in pipeline.py treats it as rejection and triggers retry.
    """
    import asyncio
    provider = NanoBananaProProvider(project="test-proj", location="global", model="gemini-image")
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"dummy")

    with patch.dict("os.environ", {"VERTEX_TEXT_MODEL": "gemini-2.5-flash", "VERTEX_TEXT_LOCATION": "global"}):
        with patch.object(provider, "_review_sync", side_effect=Exception("ClientError: 500 Internal Server Error")):
            verdict = asyncio.run(provider.review_keyframe(
                frame,
                previous_frame=None,
                expected_state="valve opens",
                previous_state=None,
                continuity_anchor="valve",
                proof="valve lever displaced 90 degrees",
            ))
            assert verdict["status"] == "reviewed"
            assert verdict["accepted"] is False
            assert "review unavailable: Exception" in verdict["reasons"][0]


def test_nano_banana_pro_review_gate_fail_closed_when_unconfigured(tmp_path: Path, monkeypatch):
    """Task 3: Missing review model configuration must return accepted=False with status 'reviewed'."""
    import asyncio
    monkeypatch.delenv("VERTEX_TEXT_MODEL", raising=False)
    provider = NanoBananaProProvider(project="test-proj", location="global", model="gemini-image")
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"dummy")

    verdict = asyncio.run(provider.review_keyframe(
        frame,
        previous_frame=None,
        expected_state="valve opens",
        previous_state=None,
        continuity_anchor="valve",
        proof="valve lever displaced 90 degrees",
    ))
    assert verdict["status"] == "reviewed"
    assert verdict["accepted"] is False
    assert "Vertex vision review is not configured" in verdict["reasons"][0]


def test_nano_banana_pro_review_rubric_expanded():
    """Task 4: Rubric prompt text in _review_sync must include character distinctness,

    object scale reference, and physics plausibility criteria.
    """
    provider = NanoBananaProProvider(project="test-proj", location="global", model="gemini-image")
    captured_contents = []

    def mock_generate(model, contents, config):
        captured_contents.extend(contents)
        res = MagicMock()
        res.text = '{"accepted": true, "score": 8, "reasons": []}'
        return res

    with patch("google.genai.Client") as mock_client_cls:
        mock_instance = mock_client_cls.return_value
        mock_instance.models.generate_content.side_effect = mock_generate
        with patch.object(provider, "_image", return_value="dummy_part"):
            dummy_frame = Path("dummy.png")
            verdict = provider._review_sync(
                dummy_frame, None, "gemini-text", "global",
                "open", None, "latch", "latch open", False, False
            )
            assert verdict["accepted"] is True
            prompt_text = captured_contents[0]
            assert "Reject if two people are visible together" in prompt_text
            assert "matching clothing color/style" in prompt_text
            assert "Reject if a close/macro shot of a real-world object has no visible scale reference" in prompt_text
            assert "Reject if a described physical force" in prompt_text


def test_incident_macro_scale_anchor_injected():
    """Task 5: Macro/close mechanical/environmental shots in incident mode must inject

    an explicit scale reference phrase if missing, and not duplicate if already present.
    """
    shot = Shot(
        block=3,
        beat_index=3,
        t_start=8.0,
        t_end=12.0,
        subject_id="door_locking_pin",
        subject_description="emergency exit door locking pin assembly",
        scale="macro",
        visual_domain="mechanical",
        start_image_prompt="Macro view of steel locking pin engaging chassis",
        end_image_prompt="Locking pin fully seated in titanium sleeve",
        motion_prompt="Pin slides under hydraulic pressure",
        entry_state="pin retracted",
        exit_state="pin locked in sleeve",
        dominant_event="locking pin secures door",
        proof_on_screen="locking pin engaged in bracket",
    )
    prompt = compile_keyframe_prompt(shot, "start", mode=INCIDENT)
    assert "Scale reference: a visible gloved hand or common reference tool" in prompt

    motion = optimize_for_flow(shot, mode=INCIDENT)["video_prompt"]
    assert "Scale reference: a visible gloved hand or common reference tool" in motion

    # If shot already mentions gloved hand, do not duplicate
    shot_with_scale = Shot(
        block=3,
        beat_index=3,
        t_start=8.0,
        t_end=12.0,
        subject_id="door_locking_pin",
        subject_description="emergency exit door locking pin assembly",
        scale="macro",
        visual_domain="mechanical",
        start_image_prompt="Macro view of locking pin held by gloved hand",
        end_image_prompt="Locking pin fully seated",
        motion_prompt="Gloved hand adjusts pin",
        entry_state="pin retracted",
        exit_state="pin locked",
        dominant_event="pin secured",
        proof_on_screen="pin engaged",
    )
    prompt2 = compile_keyframe_prompt(shot_with_scale, "start", mode=INCIDENT)
    assert prompt2.count("Scale reference:") == 0


def test_resolve_shot_accumulates_physical_trauma_modifier():
    """Task 6: For shots where journey_phase == 'resolve' and subject has earlier

    exit states implying trauma (cold, impact, struggle), an accumulated
    appearance-modifier clause must be appended to the compiled prompt.
    """
    shot_resolve = Shot(
        block=6,
        beat_index=5,
        t_start=20.0,
        t_end=24.0,
        subject_id="captain_pilot",
        subject_description="Airline captain pulled to safety",
        journey_phase="resolve",
        scale="medium",
        visual_domain="incident",
        start_image_prompt="Rescue crew wraps captain in thermal blanket",
        end_image_prompt="Captain seated safely on tarmac surrounded by crew",
        motion_prompt="Paramedics stabilize captain",
        entry_state="captain rescued from exterior breach",
        exit_state="captain stabilized on tarmac",
        dominant_event="safe recovery completed",
        proof_on_screen="thermal blanket wrapped around shoulders",
        prior_exit_states=[
            (["captain_pilot"], "captain pinned against fuselage in sub-zero freezing wind slipstream"),
            (["captain_pilot"], "severe wind impact and decompression pressure"),
            (["captain_pilot", "flight_attendant_01"], "crew struggle holding captain ankles"),
        ],
    )
    prompt = compile_keyframe_prompt(shot_resolve, "start", mode=INCIDENT)
    assert "Accumulated physical trauma:" in prompt
    assert "windswept disheveled hair" in prompt
    assert "frost-marked face" in prompt
    assert "uniform in disarray" in prompt

    motion = optimize_for_flow(shot_resolve, mode=INCIDENT)["video_prompt"]
    assert "Accumulated physical trauma:" in motion
    assert "windswept disheveled hair" in motion


def test_pipeline_keyframe_review_fail_closed_when_unsupported(tmp_path: Path, monkeypatch):
    """Task 7: When image provider does not implement review_keyframe, pipeline must reject

    with accepted=False unless ALLOW_UNREVIEWED_KEYFRAMES=1 is explicitly set.
    """
    import asyncio
    import config
    import pipeline

    class MockImageProviderWithoutReview:
        async def generate_keyframe(self, prompt, path, seed, aspect_ratio, **kwargs):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"mock_image_data")
            return path

    provider = MockImageProviderWithoutReview()
    assert not hasattr(provider, "review_keyframe")

    timeline = TimelinePlan.for_profile("providers_4s", 24.0)
    shot = Shot(
        block=1, beat_index=1, t_start=0.0, t_end=4.0,
        subject_id="hero", subject_description="hero",
        start_image_prompt="hero start", end_image_prompt="hero end",
        motion_prompt="hero motion", entry_state="state 1", exit_state="state 2",
        dominant_event="action", proof_on_screen="proof",
    )
    script = Script("Test", [Beat(i, f"Beat {i}") for i in range(1, 6)], [shot], timeline=timeline)
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"frame")

    # 1. Default (unconfigured / False): must reject with accepted=False
    monkeypatch.delenv("ALLOW_UNREVIEWED_KEYFRAMES", raising=False)
    monkeypatch.setattr(config, "ALLOW_UNREVIEWED_KEYFRAMES", False)
    verdict = asyncio.run(pipeline.admit_keyframe(provider, "kf01", frame, None, script, tmp_path))
    assert verdict["status"] == "not_supported"
    assert verdict["accepted"] is False
    assert "review_keyframe not implemented by this provider" in verdict["reasons"]

    # 2. Opt-out explicitly set: must accept with accepted=True
    monkeypatch.setenv("ALLOW_UNREVIEWED_KEYFRAMES", "1")
    monkeypatch.setattr(config, "ALLOW_UNREVIEWED_KEYFRAMES", True)
    verdict_opted_in = asyncio.run(pipeline.admit_keyframe(provider, "kf01", frame, None, script, tmp_path))
    assert verdict_opted_in["status"] == "not_supported"
    assert verdict_opted_in["accepted"] is True


def test_resolve_damage_clause_scoped_to_subject_history():
    """Task 8: In a multi-character script, prior trauma exit states must be scoped

    only to characters whose subject IDs overlap. Untouched characters must receive no
    "Accumulated physical trauma:" clause.
    """
    prior_exit_states_for_resolutions = [
        (["captain_pilot"], "captain pinned outside fuselage in sub-zero freezing wind slipstream"),
        (["copilot"], "copilot monitors flight navigation displays calmly"),
        (["captain_pilot", "flight_attendant_01"], "crew struggle holding captain ankles against decompression blast"),
        (["copilot"], "copilot executes stabilized descent checklist"),
    ]

    shot_captain_resolve = Shot(
        block=5, beat_index=5, t_start=16.0, t_end=20.0,
        subject_id="captain_pilot",
        subject_description="Airline captain pulled to safety",
        journey_phase="resolve",
        scale="medium",
        visual_domain="incident",
        entry_state="captain stabilized on stretcher",
        exit_state="captain in recovery",
        dominant_event="medical team wraps captain in thermal blanket",
        proof_on_screen="thermal blanket wrapped",
        prior_exit_states=prior_exit_states_for_resolutions,
    )

    shot_copilot_resolve = Shot(
        block=6, beat_index=5, t_start=20.0, t_end=24.0,
        subject_id="copilot",
        subject_description="First officer copilot at tarmac",
        journey_phase="resolve",
        scale="medium",
        visual_domain="incident",
        entry_state="copilot exits flight deck",
        exit_state="copilot debriefs ground crew",
        dominant_event="copilot completes debrief",
        proof_on_screen="flight log handed over",
        prior_exit_states=prior_exit_states_for_resolutions,
    )

    # Captain pilot's resolution shot MUST receive accumulated trauma clause
    capt_prompt = compile_keyframe_prompt(shot_captain_resolve, "start", mode=INCIDENT)
    assert "Accumulated physical trauma:" in capt_prompt
    assert "windswept disheveled hair" in capt_prompt
    capt_motion = optimize_for_flow(shot_captain_resolve, mode=INCIDENT)["video_prompt"]
    assert "Accumulated physical trauma:" in capt_motion

    # Untouched copilot's resolution shot must NOT receive accumulated trauma clause
    copilot_prompt = compile_keyframe_prompt(shot_copilot_resolve, "start", mode=INCIDENT)
    assert "Accumulated physical trauma:" not in copilot_prompt
    copilot_motion = optimize_for_flow(shot_copilot_resolve, mode=INCIDENT)["video_prompt"]
    assert "Accumulated physical trauma:" not in copilot_motion


def test_validate_script_accepts_incident_visual_domain():
    """Task 9: Shot with visual_domain='incident' and valid scale must pass validate_script

    in INCIDENT mode without raising 'invalid visual_domain'.
    """
    timeline = TimelinePlan.for_profile("providers_4s", 24.0)
    req_beats = _required_beat_indices(6)
    shots = [
        Shot(
            block=1,
            beat_index=req_beats[0],
            t_start=0.0,
            t_end=4.0,
            subject_id="unruly_passenger",
            secondary_subject_ids=["flight_attendant_01"],
            subject_description="passenger in cabin aisle in grey hoodie",
            presentation_mode="opening_anchor",
            opening_anchor_id="unruly_passenger",
            start_image_prompt="Passenger approaches exit door in flight",
            end_image_prompt="Passenger grips door handle firmly",
            motion_prompt="Hand pulls emergency latch",
            entry_state="cabin alert begins",
            exit_state="hand on exit latch",
            dominant_event="passenger attempts to pull handle",
            proof_on_screen="emergency latch under hand pressure",
            visual_domain="incident",
            scale="medium",
            location_id="airplane_cabin",
        )
    ]
    for b in range(2, 7):
        shots.append(Shot(
            block=b,
            beat_index=req_beats[b - 1],
            t_start=(b - 1) * 4.0,
            t_end=b * 4.0,
            subject_id="flight_attendant_01",
            subject_description="crew member in burgundy vest",
            start_image_prompt=f"Cabin view step {b}",
            end_image_prompt=f"Cabin view completed {b}",
            motion_prompt=f"Crew motion {b}",
            entry_state=f"crew state {b}",
            exit_state=f"crew state {b + 1}",
            dominant_event=f"event {b}",
            proof_on_screen=f"proof {b}",
            visual_domain="incident",
            scale="close" if b % 2 == 0 else "medium",
            location_id="airplane_cabin",
        ))
    beats = [Beat(i, f"Narration sentence one for beat. Narration sentence two for beat {i}.") for i in range(1, 6)]
    script = Script("Incident Domain Test", beats, shots, timeline=timeline, mode="incident")
    problems = validate_script(script, timeline, mode=INCIDENT)
    domain_problems = [p for p in problems if "invalid visual_domain" in p or ("scale" in p and "not appropriate" in p)]
    assert not domain_problems, f"Unexpected domain/scale problems: {domain_problems}"

