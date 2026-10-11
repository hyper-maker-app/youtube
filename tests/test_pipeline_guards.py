"""Regression checks for the no-cost reliability guards in the production pipeline."""

from __future__ import annotations

import pytest

pytest.skip("Archived monolithic generator regression; its removed gateway/Fal classes are not active production code.", allow_module_level=True)

import asyncio
import json
import cleanup
import httpx
import subprocess
import shutil
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import config
import editor
import main
import metadata
import pipeline
import research
import release
import run_history
from timeline import TimelinePlan
from generator import (
    Beat, BeatEngine, FalAuthBeforeWorkError, FalError, FalQueueClient, ImageForge, MotionForge, Script, VoiceForge,
    Shot, VertexImageForge, VisualQualityGate, _first_physical_clause, build_script_schema, build_system_prompt, compile_fal_motion,
    optimize_for_flow, VertexVeoError, VertexVeoForge, build_vertex_plan, reusable_refs, validate_vertex_image,
)
from narrative import NarrativePlan, SceneCard


def _shot(block: int, subject_id: str, chained: bool = False, duration: float = 5.0) -> Shot:
    start, end = (block - 1) * duration, block * duration
    return Shot(
        block=block,
        t_start=start,
        t_end=end,
        subject_id=subject_id,
        start_image_prompt="A clear anatomical subject in frame",
        end_image_prompt="The same anatomical subject in frame",
        motion_prompt="the subject expands once",
        chain_from_prev=chained,
        duration=end - start,
        start_anchor_id=f"anchor{block:02d}",
        end_anchor_id=f"anchor{block + 1:02d}",
        continuity_id=subject_id,
        endpoint_mode="first_last" if chained else "cut",
        beat_index=min(5, block),
    )


class PipelineGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Unit tests exercise terminal rejection paths with shared local media fixtures.
        # A developer's production calibration setting moves rejected media into a run's
        # evidence folder, which makes test order affect later tests.  Keep the suite's
        # baseline fail-closed and restore the caller's setting in tearDownClass.
        cls._calibration_mode = config.CALIBRATION_MODE
        config.CALIBRATION_MODE = False
        cls.temp = tempfile.TemporaryDirectory()
        cls.work = Path(cls.temp.name)
        cls.moving = cls.work / "moving.mp4"
        cls.frozen = cls.work / "frozen.mp4"
        cls.closing = cls.work / "closing.mp4"
        cls.voice = cls.work / "voice.mp3"
        ffmpeg = config.resolve_ffmpeg()
        for source, target in (
            ("testsrc2=size=360x640:rate=30:duration=4", cls.moving),
            ("color=c=black:size=360x640:rate=30:duration=4", cls.frozen),
        ):
            subprocess.run(
                [
                    ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", source, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35",
                    "-pix_fmt", "yuv420p", str(target),
                ],
                check=True,
            )
        subprocess.run(
            [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                "-i", "testsrc2=size=360x640:rate=30:duration=6", "-c:v", "libx264",
                "-preset", "ultrafast", "-crf", "35", "-pix_fmt", "yuv420p", str(cls.closing),
            ],
            check=True,
        )
        subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
             "-i", "sine=frequency=220:duration=1", "-c:a", "libmp3lame", str(cls.voice)],
            check=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()
        config.CALIBRATION_MODE = cls._calibration_mode

    def test_quality_gate_accepts_motion_and_rejects_freeze(self) -> None:
        self.assertTrue(editor.verify_block_quality(self.moving).accepted)
        frozen = editor.verify_block_quality(self.frozen)
        self.assertFalse(frozen.accepted)
        self.assertTrue(any("frozen" in reason for reason in frozen.reasons))

    def test_decoded_last_frame_is_written(self) -> None:
        last = editor.extract_last_frame(self.moving, self.work / "last.jpg")
        self.assertTrue(last.exists())
        self.assertGreater(last.stat().st_size, 0)

    def test_quality_frames_include_a_reliable_eof_frame(self) -> None:
        frames = editor.extract_quality_frames(self.moving, self.work / "quality-frames", "moving")
        self.assertEqual(len(frames), 3)
        self.assertTrue(all(frame.exists() and frame.stat().st_size > 0 for frame in frames))

    def test_flow_uses_selected_elevenlabs_daniel_voice(self) -> None:
        old_provider = config.TTS_PROVIDER
        old_key = config.ELEVENLABS_API_KEY
        try:
            config.TTS_PROVIDER = "elevenlabs"
            config.ELEVENLABS_API_KEY = "test-eleven-key"
            ctx = pipeline.RunContext(topic="test", out_dir=self.work, animate="manual")
            forge = VoiceForge(self.work, lang="en")
            self.assertTrue(config.commercial_tts_available())
            self.assertEqual(forge.provider, "elevenlabs")
            self.assertEqual(forge.voice_id, config.DANIEL_VOICE_ID)
            self.assertEqual(pipeline._selected_voice_label(ctx), "ElevenLabs (Daniel)")
            self.assertTrue(config.DANIEL_SAMPLE_PATH.exists())
            self.assertFalse(pipeline._voice_matches_selected_provider(
                ctx, {"voice_id": "en-US-ChristopherNeural"}
            ))
            self.assertTrue(pipeline._voice_matches_selected_provider(
                ctx, {"voice_id": config.DANIEL_VOICE_ID}
            ))
        finally:
            config.TTS_PROVIDER = old_provider
            config.ELEVENLABS_API_KEY = old_key

    def test_deepgram_uses_arcas_and_explicit_fallbacks_are_reusable(self) -> None:
        old_provider = config.TTS_PROVIDER
        old_key = config.DEEPGRAM_API_KEY
        try:
            config.TTS_PROVIDER = "deepgram"
            config.DEEPGRAM_API_KEY = "test-deepgram-key"
            ctx = pipeline.RunContext(topic="test", out_dir=self.work, animate="manual")
            forge = VoiceForge(self.work, lang="en")
            self.assertTrue(config.commercial_tts_available())
            self.assertEqual(forge.voice_id, "aura-2-arcas-en")
            self.assertEqual(pipeline._selected_voice_label(ctx), "Deepgram (aura-2-arcas-en)")
            self.assertTrue(pipeline._voice_matches_selected_provider(ctx, {"provider": "deepgram"}))
            self.assertTrue(pipeline._voice_matches_selected_provider(ctx, {"provider": "elevenlabs"}))
            self.assertTrue(pipeline._voice_matches_selected_provider(ctx, {"provider": "edge"}))
            self.assertFalse(pipeline._voice_matches_selected_provider(ctx, {"provider": "seslab"}))
            self.assertEqual(forge.headers["Authorization"], "Token test-deepgram-key")
        finally:
            config.TTS_PROVIDER = old_provider
            config.DEEPGRAM_API_KEY = old_key

    def test_haiku_validation_failure_retries_once_with_sonnet(self) -> None:
        engine = BeatEngine(provider="anthropic", lang="en")
        expected = Script(topic="test", beats=[], shots=[], lang="en")
        with mock.patch.object(config, "ANTHROPIC_API_KEY", "test-anthropic-key"), \
             mock.patch.object(config, "ANTHROPIC_MODEL", "claude-haiku-4-5"), \
             mock.patch.object(config, "ANTHROPIC_QUALITY_FALLBACK_MODEL", "claude-sonnet-5"), \
             mock.patch.object(engine, "_generate_with_model", side_effect=[RuntimeError("invalid schema"), expected]) as generate:
            actual = engine.generate("test")
        self.assertIs(actual, expected)
        self.assertEqual(generate.call_args_list[0].args, ("test",))
        self.assertEqual(generate.call_args_list[1].args, ("test", "claude-sonnet-5"))

    def test_vertex_validation_failure_uses_anthropic_sonnet_only_as_fallback(self) -> None:
        engine = BeatEngine(provider="vertex", lang="en")
        expected = Script(topic="test", beats=[], shots=[], lang="en")
        calls = []

        def generate(topic, model=None):
            calls.append((engine.provider, topic, model))
            if len(calls) == 1:
                raise RuntimeError("Vertex returned malformed JSON")
            return expected

        with mock.patch.object(config, "ANTHROPIC_API_KEY", "test-anthropic-key"), \
             mock.patch.object(config, "ANTHROPIC_QUALITY_FALLBACK_MODEL", "claude-sonnet-5"), \
             mock.patch.object(engine, "_generate_with_model", side_effect=generate):
            actual = engine.generate("test")

        self.assertIs(actual, expected)
        self.assertEqual(calls, [
            ("vertex", "test", None),
            ("anthropic", "test", "claude-sonnet-5"),
        ])
        self.assertEqual(engine.provider, "vertex")

    def test_flow_trailing_padding_exception_never_accepts_a_short_voice(self) -> None:
        flow = TimelinePlan.for_profile("veo_lite")
        ctx = pipeline.RunContext(topic="test", out_dir=self.work, animate="manual", timeline=flow)
        short = {"duration": 31.0, "words": {"words": [{"end": 30.8}]}}
        padded = {"duration": 40.09, "words": {"words": [{"end": 39.04}]}}
        self.assertFalse(pipeline._flow_voice_has_only_trailing_padding(ctx, short))
        self.assertTrue(pipeline._flow_voice_has_only_trailing_padding(ctx, padded))

    def test_pitch_preserving_conform_allows_a_thirty_percent_voice_timing_drift(self) -> None:
        target = self.work / "voice_conform.mp3"
        ffmpeg = config.resolve_ffmpeg()
        subprocess.run([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
            "-i", "sine=frequency=220:duration=2", "-c:a", "libmp3lame", str(target),
        ], check=True)
        conformed = editor.conform_audio_duration(target, 3.0)
        self.assertAlmostEqual(conformed, 3.0, delta=0.15)

    def test_quality_review_is_persisted_before_a_report_retry(self) -> None:
        from unittest import mock
        shot = _shot(1, "rocket")
        shot.quality_critical = True
        shot.visual_domain = "physical_effect"
        shot.detail_target = "physical_realism"
        ctx = pipeline.RunContext(topic="test", out_dir=self.work / "quality-state", animate="manual")
        ctx.out_dir.mkdir(parents=True, exist_ok=True)
        script = Script(topic="test", beats=[], shots=[shot])
        verdict = {"status": "reviewed", "accepted": True, "score": 9, "reasons": []}
        with mock.patch.object(pipeline.VisualQualityGate, "review", return_value=verdict) as review:
            pipeline._write_quality_report(ctx, script, [self.moving])
            pipeline._write_quality_report(ctx, script, [self.moving])
        self.assertEqual(review.call_count, 1)
        self.assertEqual(ctx.load_state()["block01"]["visual_quality"]["score"], 9)

    def test_lighthouse_exterior_payoff_quality_rubric_drops_inherited_mechanism_target(self) -> None:
        """A payoff can leave a gear close-up without being judged as a missing gear close-up."""
        shot = _shot(5, "lighthouse", duration=8.0)
        shot.visual_anchor = {
            "kind": "lighthouse_empty_island",
            "subject": "the same red-and-white striped lighthouse",
        }
        shot.visual_domain = "technical_mechanism"
        shot.detail_target = "mechanical"
        shot.structure_tags = ["cross_section", "gear"]
        shot.effect_tags = ["atmosphere"]
        shot.quality_critical = True
        shot.end_image_prompt = "Night exterior of the red-and-white striped lighthouse on its rocky island, sweeping a beam over the ocean."
        shot.exit_state = "The lighthouse beam sweeps over open sea waves."
        shot.dominant_event = "The lighthouse projects its signal into darkness."
        shot.proof_on_screen = "A brilliant beam cuts through fog over the sea."
        shot.semantic_expected_result = "Exterior lighthouse payoff on the empty island."
        shot.purpose = "Deliver the lighthouse payoff."

        contract = VisualQualityGate.review_contract(shot)
        rubric = VisualQualityGate.build_rubric(shot)

        self.assertTrue(VisualQualityGate(self.work / "lighthouse-review").applies(shot))
        self.assertEqual(contract["kind"], "lighthouse_exterior_payoff")
        self.assertEqual(contract["visual_domain"], "environment")
        self.assertEqual(contract["detail_target"], "editorial")
        self.assertEqual(contract["structure_tags"], [])
        self.assertIn("domain environment, detail target editorial", rubric)
        self.assertNotIn("detail target mechanical", rubric)
        self.assertIn("Do not reject it solely because its exterior frames omit detail", rubric)
        self.assertIn("discontinuity between the chronological frames", rubric)

        mechanism = _shot(1, "engine")
        mechanism.visual_domain = "technical_mechanism"
        mechanism.detail_target = "mechanical"
        mechanism.structure_tags = ["gear"]
        standard = VisualQualityGate.review_contract(mechanism)
        self.assertEqual(standard["kind"], "standard")
        self.assertIn("domain technical_mechanism, detail target mechanical", VisualQualityGate.build_rubric(mechanism))

    def test_lighthouse_exterior_payoff_regeneration_guide_uses_review_contract(self) -> None:
        shot = _shot(5, "lighthouse", duration=4.0)
        shot.visual_anchor = {"kind": "lighthouse_empty_island"}
        shot.visual_domain = "technical_mechanism"
        shot.detail_target = "mechanical"
        shot.structure_tags = ["cross_section", "gear"]
        shot.effect_tags = ["atmosphere"]
        shot.quality_critical = True
        shot.end_image_prompt = "Night exterior of the lighthouse on a rocky island, beam sweeping across the ocean."
        shot.exit_state = "Lighthouse beam sweeps over open sea waves."
        shot.dominant_event = "Lighthouse signal sweeps into darkness."
        shot.proof_on_screen = "Beam through sea fog."
        shot.semantic_expected_result = "Exterior lighthouse payoff."
        ctx = pipeline.RunContext(topic="test", out_dir=self.work / "lighthouse-review-report", animate="manual")
        ctx.out_dir.mkdir(parents=True, exist_ok=True)
        ctx.save_state({
            "block05": {
                "visual_quality": {"status": "reviewed", "accepted": False, "score": 2, "reasons": ["mock"]},
                "visual_history": [],
            }
        })

        report_path = pipeline._write_quality_report(ctx, Script(topic="test", beats=[], shots=[shot]), [self.moving])
        report = json.loads(report_path.read_text(encoding="utf-8"))
        block = report["blocks"][0]
        self.assertEqual(block["visual_review_contract"]["kind"], "lighthouse_exterior_payoff")
        self.assertIn("Lighthouse exterior payoff", block["flow_regeneration_guide"])
        self.assertNotIn("technical_mechanism detail", block["flow_regeneration_guide"])

    def test_handoff_writes_one_prompt_per_block_with_automatic_detail_constraints(self) -> None:
        critical = _shot(1, "rocket")
        critical.quality_critical = True
        critical.visual_domain = "technical_mechanism"
        critical.structure_tags = ["cooling channels"]
        normal = _shot(2, "keeper", duration=8.0)
        flow = TimelinePlan.for_profile("veo_lite")
        shots = [critical, normal] + [_shot(i, f"subject_{i}", duration=8.0) for i in range(3, 6)]
        critical.t_start, critical.t_end, critical.duration = 0.0, 8.0, 8.0
        ctx = pipeline.RunContext(topic="test", out_dir=self.work / "single-prompt-handoff", animate="manual", timeline=flow)

        handoff = pipeline.write_handoff(ctx, Script(topic="test", beats=[], shots=shots, timeline=flow))

        critical_prompt = (handoff / "block01_video_prompt.txt").read_text(encoding="utf-8")
        normal_prompt = (handoff / "block02_video_prompt.txt").read_text(encoding="utf-8")
        self.assertIn("High-detail scene requirements", critical_prompt)
        self.assertIn("cooling channels", critical_prompt)
        self.assertIn("8-second vertical 9:16 shot for Veo 3.1 Lite", critical_prompt)
        self.assertNotIn("within the first", critical_prompt)
        self.assertIn("full 8-second take", critical_prompt)
        self.assertNotIn("High-detail scene requirements", normal_prompt)
        self.assertFalse(list(handoff.glob("block*_regeneration_prompt.txt")))
        guide = (handoff / "handoff.md").read_text(encoding="utf-8")
        self.assertNotIn("regeneration_prompt", guide)
        self.assertIn("Veo 3.1 Lite", guide)
        self.assertIn("sabit **8 saniye**", guide)

    def test_fiction_contract_repair_does_not_spend_the_hook_on_a_disclaimer(self) -> None:
        engine = BeatEngine(provider="codefast", lang="en", content_type="fiction")
        beats = [
            Beat(i + 1, config.BEAT_TEMPLATE[i]["role"],
                 "This fictional lighthouse story keeps its lonely lantern shining across an empty sea at night while silent gulls circle beneath cold stars.",
                 ["lighthouse"])
            for i in range(5)
        ]
        shots = [_shot(i, "lighthouse_keeper") for i in range(1, 8)]
        shots[4].motion_prompt = 'the keeper hears "come inside" once'
        repaired = engine._repair_fiction_contract(Script(
            topic="test", beats=beats, shots=shots, content_type="fiction"
        ))
        self.assertFalse(repaired.beats[0].text.lower().startswith("imagine this fictional"))
        self.assertLessEqual(len(repaired.beats[0].text.split(".", 1)[0].split()), config.HOOK_MAX_WORDS)
        self.assertNotIn('"', repaired.shots[4].motion_prompt)
        self.assertNotIn("lone figure turns", repaired.shots[-1].end_image_prompt.lower())

    def test_fiction_repair_never_accepts_a_script_without_storyboard_provenance(self) -> None:
        """Mechanical repair cannot bypass the new-run NarrativePlan gate."""
        engine = BeatEngine(provider="codefast", lang="en", content_type="fiction")
        malformed = Script(
            topic="test",
            beats=[Beat(i + 1, "myth", "The empty lighthouse sends a signal across a black sea tonight.", ["lighthouse"])
                   for i in range(5)],
            shots=[_shot(i, "lighthouse_keeper") for i in range(1, 8)],
            content_type="fiction", timeline=engine.timeline,
        )
        with mock.patch.object(engine, "_call", return_value={}), \
             mock.patch.object(engine, "_assemble", return_value=malformed), \
             mock.patch.object(engine, "_validate", return_value=[]), \
             mock.patch.object(config, "SCRIPT_REPAIR_ATTEMPTS", 1):
            with self.assertRaisesRegex(RuntimeError, "Missing NarrativePlan"):
                engine._generate_with_model("test")

    def test_causal_state_label_repair_changes_only_exact_continuity_metadata(self) -> None:
        engine = BeatEngine(provider="codefast", lang="en", content_type="fiction")
        first = SceneCard("scene01", "hook", "dark", "beam flickers", "lamp flickers", "beam", "", "why", {"lamp": "flickering"})
        second = SceneCard("scene02", "answer", "inside tower", "gear turns", "gear turns", "gear", "scene01", "how", {"lamp": "flickering"})
        first_shot, second_shot = _shot(1, "lamp"), _shot(2, "lamp")
        first_shot.scene_id, first_shot.entry_state, first_shot.exit_state = "scene01", "dark", "beam flickers"
        second_shot.scene_id, second_shot.entry_state, second_shot.exit_state = "scene02", "inside tower", "gear turns"
        script = Script("test", [], [first_shot, second_shot], storyboard=[first, second])
        report = {"blockers": ["SceneCard scene02 entry state does not continue the prior exit state; use a causal cut or shared state."]}
        self.assertTrue(engine._repair_causal_card_entries(script, report))
        self.assertEqual(second.entry_state, "beam flickers")
        self.assertEqual(second_shot.entry_state, "beam flickers")
        self.assertEqual(second.dominant_event, "gear turns")

    def test_explicit_anthropic_model_is_a_per_invocation_cli_override(self) -> None:
        args = main.parse_args(["--provider", "anthropic", "--anthropic-model", "claude-sonnet-5"])
        self.assertEqual(args.anthropic_model, "claude-sonnet-5")

    def test_script_assembler_filters_null_tool_array_items(self) -> None:
        engine = BeatEngine(provider="codefast", lang="en", content_type="fiction")
        script = engine._assemble("test", {
            "beats": [None, {"index": 1, "role": "myth", "text": "Imagine a fictional lighthouse.", "emphasis": ["lighthouse"]}],
            "keyframes": [None],
            "shots": [None],
        })
        self.assertEqual(len(script.beats), 1)
        self.assertEqual(script.beats[0].text, "Imagine a fictional lighthouse.")
        self.assertEqual(script.shots, [])

    def test_same_subject_blocks_are_serially_chained(self) -> None:
        script = Script(
            topic="test",
            beats=[],
            shots=[_shot(1, "anchor"), _shot(2, "anchor", chained=True)],
        )

        class RecordingForge(MotionForge):
            def __init__(self, out_dir: Path, clip: Path):
                super().__init__(out_dir, tier=config.TIER_PAID)
                self.clip = clip
                self.seen: list[Path | None] = []

            async def _block(self, script, shot, refs, client, state, previous_last_frame=None):
                self.seen.append(previous_last_frame)
                return shot.block, self.clip

        forge = RecordingForge(self.work / "run", self.moving)
        paths = asyncio.run(forge.generate(script, {}, object(), {}))
        self.assertEqual(paths, [self.moving, self.moving])
        self.assertIsNone(forge.seen[0])
        self.assertIsNotNone(forge.seen[1])
        self.assertTrue(forge.seen[1].exists())
        self.assertFalse(MotionForge._continues(_shot(1, "anchor"), _shot(2, "cell")))

    def test_end_reference_is_withheld_at_a_subject_change(self) -> None:
        forge = MotionForge(self.work / "tail-check", tier=config.TIER_PAID)
        same_subject = Script(
            topic="test", beats=[], shots=[_shot(1, "anchor"), _shot(2, "anchor", chained=True)]
        )
        changed_subject = Script(
            topic="test", beats=[], shots=[_shot(1, "anchor"), _shot(2, "cell", chained=False)]
        )
        same_subject.shots[0].endpoint_mode = "first_last"
        refs = {"kf02": {"url": "https://example.test/end-frame.png"}}
        self.assertEqual(
            forge._tail_url(same_subject, same_subject.shots[0], refs),
            "https://example.test/end-frame.png",
        )
        self.assertIsNone(forge._tail_url(changed_subject, changed_subject.shots[0], refs))

    def test_prompt_is_structured_and_default_is_end_to_end(self) -> None:
        prompt = build_system_prompt("en")
        self.assertIn("<role>", prompt)
        self.assertIn("<instructions>", prompt)
        self.assertIn("<source_facts>", prompt)
        self.assertIn("<timeline>", prompt)
        self.assertIn("<scene_contract>", prompt)
        self.assertIn("<output_contract>", prompt)
        self.assertIn("ONE visible physical action", prompt)
        self.assertEqual(main.parse_args([]).source, "auto")

    def test_source_auto_falls_to_flow_without_fal_key(self) -> None:
        old = config.FAL_KEY
        old_openai = config.OPENAI_API_KEY
        old_deepgram = config.DEEPGRAM_API_KEY
        config.FAL_KEY = None
        try:
            args = main.parse_args(["--source", "auto"])
            args.provider = "openai"  # avoid credential branch under test
            config.OPENAI_API_KEY = config.OPENAI_API_KEY or "test-key"
            config.DEEPGRAM_API_KEY = "test-deepgram-key"
            result = main.preflight(args)
        finally:
            config.FAL_KEY = old
            config.OPENAI_API_KEY = old_openai
            config.DEEPGRAM_API_KEY = old_deepgram
        self.assertEqual((result.effective_source, result.fallback_reason), ("flow", "fal_key_missing"))

    def test_explicit_fal_refuses_missing_key(self) -> None:
        old = config.FAL_KEY
        config.FAL_KEY = None
        try:
            with self.assertRaises(SystemExit):
                main.preflight(main.parse_args(["--source", "fal"]))
        finally:
            config.FAL_KEY = old

    def test_only_preaccepted_fal_auth_error_is_typed_for_flow_fallback(self) -> None:
        async def submit_status(status: int):
            async def handler(request):
                return httpx.Response(status, json={"detail": "test"})
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                fal = FalQueueClient(api_key="test", client=client)
                return await fal.submit("model", {})

        with mock.patch.object(config, "FAL_QUEUE_BASE", "https://provider.test"):
            with self.assertRaises(FalAuthBeforeWorkError):
                asyncio.run(submit_status(401))
            with self.assertRaises(FalError) as error:
                asyncio.run(submit_status(429))
            self.assertNotIsInstance(error.exception, FalAuthBeforeWorkError)

    def test_provider_native_timeline_and_script_contract(self) -> None:
        timeline = TimelinePlan.for_profile("h3_max")
        self.assertEqual((timeline.block_count, timeline.keyframe_count, timeline.total_duration), (7, 8, 35.0))
        script = Script(
            topic="test", beats=[], shots=[_shot(1, "anchor")],
            youtube={"titles": ["T"], "description": "D", "tags": ["tag"]},
            anchors=[{"id": "anchor01", "index": 1, "image_prompt": "start", "subject_id": "anchor"}],
            content_type="fiction", truth_frame="fictional", source_facts=[{"id": "fact_1"}],
            timeline=timeline,
        )
        persisted = script.to_dict()
        self.assertEqual(persisted["youtube"]["titles"], ["T"])
        self.assertEqual(persisted["anchors"][0]["id"], "anchor01")
        self.assertEqual(persisted["content_type"], "fiction")
        self.assertEqual(persisted["timeline"]["motion_model"], "h3_max")

    def test_all_native_profiles_meet_minimum_and_round_up(self) -> None:
        expected = {
            "vertex_veo_lite": (8.0, 5, 40.0),
            "vertex_veo_fast": (8.0, 5, 40.0),
            "vertex_veo": (8.0, 5, 40.0),
            "kling_pro": (5.0, 7, 35.0),
            "veo_fast": (8.0, 5, 40.0),
            "hailuo": (6.0, 6, 36.0),
            "wan": (4.0, 8, 32.0),
        }
        for model, (clip, blocks, total) in expected.items():
            plan = TimelinePlan.for_profile(model)
            self.assertEqual((plan.native_clip_duration, plan.block_count, plan.total_duration), (clip, blocks, total))
            self.assertGreaterEqual(plan.total_duration, 32.0)
        self.assertEqual(TimelinePlan.for_profile("h3_max", 40).shot_durations, (5.0,) * 8)
        self.assertEqual(TimelinePlan.for_profile("veo_lite", 48).shot_durations, (8.0,) * 6)

    def test_vertex_route_has_a_pinned_native_profile(self) -> None:
        args = main.parse_args(["--source", "vertex", "--motion-model", "vertex_veo_fast"])
        self.assertEqual(args.source, "vertex")
        timeline = TimelinePlan.for_profile(main.profile_for_source(args.source, args.motion_model))
        self.assertEqual(timeline.source, "vertex")
        self.assertEqual(timeline.motion_model, "vertex_veo_fast")
        self.assertEqual(timeline.total_duration, 40.0)

    def test_vertex_defaults_to_fast_and_lite_fails_before_request(self) -> None:
        self.assertEqual(main.profile_for_source("vertex", None), "vertex_veo_fast")
        timeline = TimelinePlan.for_profile("vertex_veo_fast")
        script = Script(
            topic="test", beats=[], shots=[_shot(1, "anchor", duration=8.0)], timeline=timeline,
            narrative_plan=NarrativePlan("mechanism_reveal", "why", "hook", "stake", "turn", "reversal", "payoff"),
        )
        with self.assertRaises(VertexVeoError):
            build_vertex_plan(script, "vertex_veo_lite")

    def test_windows_gcloud_resolver_finds_cloud_sdk_outside_path(self) -> None:
        app_data = self.work / "appdata"
        gcloud = app_data / "Google" / "Cloud SDK" / "google-cloud-sdk" / "bin" / "gcloud.cmd"
        gcloud.parent.mkdir(parents=True, exist_ok=True)
        gcloud.write_text("", encoding="utf-8")
        with mock.patch.object(config.os, "name", "nt"), \
             mock.patch.object(config.shutil, "which", return_value=None), \
             mock.patch.dict(config.os.environ, {"LOCALAPPDATA": str(app_data)}, clear=False):
            self.assertEqual(config.gcloud_command(), str(gcloud))

    def test_vertex_plan_is_immutable_across_environment_model_changes(self) -> None:
        timeline = TimelinePlan.for_profile("vertex_veo_fast")
        shot = _shot(1, "anchor", duration=8.0)
        shot.journey_phase = "reveal"
        script = Script(
            topic="test", beats=[], shots=[shot], timeline=timeline,
            narrative_plan=NarrativePlan("mechanism_reveal", "why", "hook", "stake", "turn", "reversal", "payoff"),
        )
        old = config.VERTEX_HERO_VIDEO_MODEL
        try:
            config.VERTEX_HERO_VIDEO_MODEL = "vertex_veo"
            frozen = build_vertex_plan(script, "vertex_veo_fast")
            config.VERTEX_HERO_VIDEO_MODEL = "vertex_veo_fast"
            forge = VertexVeoForge(self.work / "immutable", frozen)
            self.assertEqual(forge.hero_motion_model, "vertex_veo")
            self.assertEqual(frozen["hero_keyframe_indices"], [1])
        finally:
            config.VERTEX_HERO_VIDEO_MODEL = old

    def test_vertex_plan_caps_keyword_promoted_hero_images(self) -> None:
        timeline = TimelinePlan.for_profile("vertex_veo_fast")
        shots = []
        for block in range(1, 6):
            shot = _shot(block, "mechanism", duration=8.0)
            shot.purpose = "Expose the hidden mechanism"
            shot.dominant_event = "A relay circuit closes"
            shot.proof_on_screen = "The mechanism reveals its path"
            shot.quality_critical = True
            shots.append(shot)
        script = Script(
            topic="test", beats=[], shots=shots, timeline=timeline,
            narrative_plan=NarrativePlan("mechanism_reveal", "why", "hook", "stake", "turn", "reversal", "payoff"),
        )
        plan = build_vertex_plan(script, "vertex_veo_fast")
        self.assertEqual(plan["hero_keyframe_indices"], [1, 2])
        self.assertEqual(plan["planned_cost"]["hero_image_requests"], 2)

    def test_vertex_gemini_text_provider_is_explicit_and_does_not_change_visual_source_auto(self) -> None:
        args = main.parse_args(["--provider", "vertex", "--source", "auto"])
        self.assertEqual(args.provider, "vertex")
        self.assertEqual(args.source, "auto")
        engine = BeatEngine(provider="vertex", lang="en")
        self.assertEqual(engine.provider, "vertex")
        self.assertEqual(config.VERTEX_TEXT_MODEL, "gemini-3.8-flash")

    def test_legacy_vertex_resume_is_rejected_before_media_work(self) -> None:
        run = self.work / "legacy-vertex-block"
        run.mkdir(exist_ok=True)
        (run / "script.json").write_text(__import__("json").dumps({
            "topic": "legacy", "beats": [], "shots": [{
                "block": 1, "t_start": 0, "t_end": 4, "subject_id": "x",
                "start_image_prompt": "a", "end_image_prompt": "b", "motion_prompt": "turns",
            }],
        }), encoding="utf-8")
        ctx = pipeline.RunContext(topic="legacy", out_dir=run, resumed=True, effective_source="vertex")
        with self.assertRaises(VertexVeoError):
            pipeline.phase1_script(ctx, {})

    def test_new_vertex_plan_is_persisted_before_assets(self) -> None:
        run = self.work / "new-vertex-plan"
        timeline = TimelinePlan.for_profile("vertex_veo_fast")
        authored = Script(
            topic="test", beats=[], shots=[_shot(1, "anchor", duration=8.0)], timeline=timeline,
            narrative_plan=NarrativePlan("mechanism_reveal", "why", "hook", "stake", "turn", "reversal", "payoff"),
        )
        assets = mock.Mock()
        assets.suggest_assets.return_value = "catalog"
        assets.auto_register_from_shots.return_value = []
        engine = mock.Mock()
        engine.generate.return_value = authored
        ctx = pipeline.RunContext(topic="test", out_dir=run, effective_source="vertex", timeline=timeline)
        with mock.patch.object(pipeline, "AssetLibrary", return_value=assets), \
             mock.patch.object(pipeline, "BeatEngine", return_value=engine), \
             mock.patch.object(pipeline.research, "write_manifest", return_value={"status": "pass"}), \
             mock.patch.object(pipeline, "write_storyboard"), \
             mock.patch.object(pipeline, "_write_prompt_manifest"), \
             mock.patch.object(pipeline.metadata, "write_metadata", return_value=run / "metadata.json"):
            persisted = pipeline.phase1_script(ctx, {})
        self.assertTrue(persisted.vertex_plan)
        saved = __import__("json").loads((run / "script.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["vertex_plan"]["normal_video"]["motion_model"], "vertex_veo_fast")

    def test_vertex_overlay_requires_structured_permission(self) -> None:
        default = VertexImageForge._apply_overlay_policy("An arrow appears in the prose")
        self.assertIn("No arrows or directional markers", default)
        explicit = VertexImageForge._apply_overlay_policy("A vessel", {
            "type": "force_line", "purpose": "show compression", "placement": "left",
        })
        self.assertIn("exactly one non-decorative force line", explicit)
        self.assertIn("No HUD, UI", explicit)

    def test_pending_vertex_operation_is_polled_not_resubmitted(self) -> None:
        run = self.work / "pending-operation"
        frame = run / "keyframes" / "kf01.png"
        frame.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.moving, frame)  # only existence/hash is needed by the mocked poll path
        timeline = TimelinePlan.for_profile("vertex_veo_fast")
        shot = _shot(1, "anchor", duration=4.0)
        script = Script(topic="test", beats=[], shots=[shot], timeline=timeline,
                        narrative_plan=NarrativePlan("mechanism_reveal", "why", "hook", "stake", "turn", "reversal", "payoff"))
        plan = build_vertex_plan(script, "vertex_veo_fast")
        state = {"block01": {"status": "pending", "operation": "operations/already-accepted"}}
        checkpoints = []
        forge = VertexVeoForge(run, plan, checkpoint=lambda value: checkpoints.append(dict(value)))

        def poll_existing(project, operation, output, saved_state, key):
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.moving, output)
            return {"operation": operation, "output_sha256": "mocked"}

        with mock.patch.object(forge, "_resume_one", side_effect=poll_existing) as resume, \
             mock.patch.object(forge, "_submit_and_wait") as submit, \
             mock.patch.object(forge, "_project_id", return_value="test-project"):
            blocks = asyncio.run(forge.generate(script, {"kf01": {"local": str(frame)}}, state))
        self.assertEqual(len(blocks), 1)
        self.assertEqual(resume.call_count, 1)
        submit.assert_not_called()
        self.assertEqual(state["block01"]["quality"], "accepted")
        self.assertTrue(checkpoints)

    def test_vertex_first_last_uses_the_persisted_tail_keyframe(self) -> None:
        """The generated N+1 tail must reach Veo rather than becoming dead metadata."""
        from types import SimpleNamespace

        run = self.work / "vertex-last-frame"
        run.mkdir(exist_ok=True)
        first = run / "first.png"
        tail = run / "tail.png"
        first.write_bytes(b"first-image")
        tail.write_bytes(b"tail-image")
        timeline = TimelinePlan.for_profile("vertex_veo_fast")
        shot = _shot(1, "tower", duration=8.0)
        shot.endpoint_mode = "first_last"
        script = Script(
            topic="test", beats=[], shots=[shot], timeline=timeline,
            narrative_plan=NarrativePlan("mechanism_reveal", "why", "hook", "stake", "turn", "reversal", "payoff"),
        )
        plan = {
            "normal_video": {"motion_model": "vertex_veo_fast", "model_id": "veo-3.1-fast-generate-001"},
            "hero_video": {"motion_model": "vertex_veo_fast", "model_id": "veo-3.1-fast-generate-001"},
            "hero_keyframe_indices": [1],
        }
        forge = VertexVeoForge(run, plan)
        captured = {}

        class FakeModels:
            def generate_videos(self, **kwargs):
                captured.update(kwargs)
                return SimpleNamespace(name="operations/test")

        fake_client = SimpleNamespace(models=FakeModels())
        state = {}
        with mock.patch.object(forge, "_client", return_value=fake_client), \
             mock.patch.object(forge, "_wait_download", return_value={"operation": "operations/test", "output_sha256": "mock"}):
            forge._submit_and_wait(
                "project", "veo-3.1-fast-generate-001", shot, "event", first, tail,
                run / "block01.mp4", state, "block01", {"provider": "vertex_veo"},
            )
        self.assertEqual(captured["config"].last_frame.image_bytes, b"tail-image")
        self.assertEqual(captured["source"].image.image_bytes, b"first-image")
        self.assertEqual(captured["source"].prompt, "event")
        self.assertNotIn("image", captured)
        self.assertNotIn("prompt", captured)
        self.assertEqual(state["block01"]["status"], "pending")

    def test_lighthouse_semantic_rejection_stops_before_later_vertex_requests(self) -> None:
        """A reviewed V2 rejection is evidence, never a cue to bill block 2."""
        run = self.work / "vertex-semantic-stop"
        run.mkdir(exist_ok=True)
        first = run / "keyframes" / "kf01.png"
        first.parent.mkdir(parents=True, exist_ok=True)
        first.write_bytes(b"first-image")
        timeline = TimelinePlan.for_profile("vertex_veo_fast")
        anchor = __import__("generator").visual_anchor_for_topic(
            "The Lighthouse That Still Signals From an Empty Island"
        )
        shot = _shot(1, "lighthouse", duration=8.0)
        shot.visual_anchor = anchor
        shot.scene_id = "scene_1"
        shot.purpose = "Show the lighthouse activation"
        shot.entry_state = "lantern is dark"
        shot.exit_state = "lantern is lit"
        shot.dominant_event = "the lantern begins glowing"
        shot.proof_on_screen = "golden light in the lantern"
        shot.asset_states = {"anchor": "same lighthouse on island"}
        script = Script(
            topic="The Lighthouse That Still Signals From an Empty Island", beats=[], shots=[shot],
            timeline=timeline, narrative_plan=NarrativePlan("mechanism_reveal", "why", "hook", "stake", "turn", "reversal", "payoff"),
            visual_anchor=anchor,
        )
        plan = {
            "normal_video": {"motion_model": "vertex_veo_fast", "model_id": "veo-3.1-fast-generate-001"},
            "hero_video": {"motion_model": "vertex_veo_fast", "model_id": "veo-3.1-fast-generate-001"},
            "hero_keyframe_indices": [1],
            "clip_review": {
                "version": 1, "required": True, "provider": "vertex_gemini_vision",
                "model_id": "gemini-test", "location": "global", "max_output_tokens": 1024,
            },
        }
        forge = VertexVeoForge(run, plan)
        forge._vertex_clip_review.review = mock.Mock(return_value={
            "status": "rejected", "accepted": False, "score": 2, "reasons": ["anchor missing"],
            "visual_quality": {"status": "reviewed", "accepted": True, "score": 9, "reasons": []},
            # Even if compact component summaries look favourable, Gemini's explicit
            # combined verdict must still stop the run.  Otherwise a rejected causal
            # sequence could be accepted by accident.
            "semantic_quality": {"status": "reviewed", "accepted": True, "score": 9, "reasons": []},
        })
        forge._vertex_clip_review.write_report = mock.Mock(return_value=run / "vertex_clip_review_block01.json")
        forge._visual_gate.review = mock.Mock(side_effect=AssertionError("V2 must not call Anthropic visual review"))
        forge._semantic_gate.review = mock.Mock(side_effect=AssertionError("V2 must not call Anthropic semantic review"))
        state = {}
        with self.assertRaisesRegex(VertexVeoError, "no later block and no automatic regeneration"):
            forge._review_lighthouse_block_or_stop(
                script, shot, self.moving, state, "block01", {"provider": "vertex_veo"},
                {"operation": "operations/complete", "output_sha256": "output"},
            )
        self.assertEqual(state["status"], "needs_semantic_review")
        self.assertEqual(state["block01"]["status"], "semantic_rejected")
        self.assertEqual(state["block01"]["quality"], "semantic_rejected")
        forge._vertex_clip_review.review.assert_called_once()
        forge._visual_gate.review.assert_not_called()
        forge._semantic_gate.review.assert_not_called()

        with mock.patch.object(forge, "_project_id", return_value="test-project"), \
             mock.patch.object(forge, "_submit_and_wait") as submit:
            with self.assertRaisesRegex(VertexVeoError, "already rejected"):
                asyncio.run(forge.generate(script, {"kf01": {"local": str(first)}}, state))
        submit.assert_not_called()

    def test_lighthouse_v2_keyframe_preflight_rejection_blocks_every_vertex_video_request(self) -> None:
        """A rejected Gemini keyframe audit is persisted before block 1 can be billed."""
        run = self.work / "vertex-keyframe-preflight-stop"
        run.mkdir(exist_ok=True)
        timeline = TimelinePlan.for_profile("vertex_veo_fast")
        anchor = __import__("generator").visual_anchor_for_topic(
            "The Lighthouse That Still Signals From an Empty Island"
        )
        shot = _shot(1, "lighthouse", duration=8.0)
        shot.visual_anchor = anchor
        shot.scene_id = "scene01"
        shot.purpose = "Show the lighthouse activation"
        shot.entry_state = "lantern is dark"
        shot.exit_state = "lantern is lit"
        shot.dominant_event = "the lantern begins glowing"
        shot.proof_on_screen = "golden light in the lantern"
        script = Script(
            topic="The Lighthouse That Still Signals From an Empty Island", beats=[], shots=[shot],
            timeline=timeline, narrative_plan=NarrativePlan("mechanism_reveal", "why", "hook", "stake", "turn", "reversal", "payoff"),
            visual_anchor=anchor,
        )
        plan = {
            "normal_video": {"motion_model": "vertex_veo_fast", "model_id": "veo-3.1-fast-generate-001"},
            "hero_video": {"motion_model": "vertex_veo_fast", "model_id": "veo-3.1-fast-generate-001"},
            "hero_keyframe_indices": [1],
            "keyframe_preflight": {
                "version": 1, "required": True, "provider": "vertex_gemini_vision",
                "model_id": "gemini-test", "location": "global", "max_output_tokens": 1024,
            },
        }
        checkpoints = []
        forge = VertexVeoForge(run, plan, checkpoint=lambda value: checkpoints.append(dict(value)))
        forge._keyframe_preflight.review = mock.Mock(return_value={
            "status": "rejected", "accepted": False, "score": 2,
            "reasons": ["kf02 loses lighthouse identity"], "summary": "Detached buoy-like object.",
        })
        forge._keyframe_preflight.write_report = mock.Mock(return_value=run / "keyframe_preflight.json")
        state = {}
        with mock.patch.object(forge, "_project_id", return_value="test-project"), \
             mock.patch.object(forge, "_submit_and_wait") as submit:
            with self.assertRaisesRegex(VertexVeoError, "keyframe preflight did not pass"):
                asyncio.run(forge.generate(script, {}, state))
        forge._keyframe_preflight.review.assert_called_once_with(script, {}, "test-project")
        forge._keyframe_preflight.write_report.assert_called_once()
        submit.assert_not_called()
        self.assertEqual(state["status"], "needs_keyframe_review")
        self.assertFalse(state["keyframe_preflight"]["accepted"])
        self.assertEqual(state["keyframe_preflight"]["report_path"], str(run / "keyframe_preflight.json"))
        self.assertTrue(checkpoints)

        # The same rejected state is a terminal review stop.  It cannot consume Gemini
        # again, much less create a fresh Veo operation, on a resume.
        forge._keyframe_preflight.review.reset_mock()
        forge._keyframe_preflight.write_report.reset_mock()
        with mock.patch.object(forge, "_project_id", return_value="test-project"), \
             mock.patch.object(forge, "_submit_and_wait") as submit:
            with self.assertRaisesRegex(VertexVeoError, "already require review"):
                asyncio.run(forge.generate(script, {}, state))
        forge._keyframe_preflight.review.assert_not_called()
        forge._keyframe_preflight.write_report.assert_not_called()
        submit.assert_not_called()

    def test_lighthouse_v2_unavailable_keyframe_preflight_also_fails_closed(self) -> None:
        run = self.work / "vertex-keyframe-preflight-unavailable"
        run.mkdir(exist_ok=True)
        timeline = TimelinePlan.for_profile("vertex_veo_fast")
        anchor = __import__("generator").visual_anchor_for_topic("The Lighthouse That Still Signals From an Empty Island")
        shot = _shot(1, "lighthouse", duration=8.0)
        shot.visual_anchor = anchor
        script = Script(
            topic="The Lighthouse That Still Signals From an Empty Island", beats=[], shots=[shot],
            timeline=timeline, narrative_plan=NarrativePlan("mechanism_reveal", "why", "hook", "stake", "turn", "reversal", "payoff"),
            visual_anchor=anchor,
        )
        plan = {
            "normal_video": {"motion_model": "vertex_veo_fast", "model_id": "veo-3.1-fast-generate-001"},
            "hero_video": {"motion_model": "vertex_veo_fast", "model_id": "veo-3.1-fast-generate-001"},
            "hero_keyframe_indices": [1],
            "keyframe_preflight": {
                "version": 1, "required": True, "provider": "vertex_gemini_vision",
                "model_id": "gemini-test", "location": "global", "max_output_tokens": 1024,
            },
        }
        forge = VertexVeoForge(run, plan)
        forge._keyframe_preflight.review = mock.Mock(side_effect=RuntimeError("ADC unavailable"))
        forge._keyframe_preflight.write_report = mock.Mock(return_value=run / "keyframe_preflight.json")
        state = {}
        with mock.patch.object(forge, "_project_id", return_value="test-project"), \
             mock.patch.object(forge, "_submit_and_wait") as submit:
            with self.assertRaisesRegex(VertexVeoError, "keyframe preflight did not pass"):
                asyncio.run(forge.generate(script, {}, state))
        submit.assert_not_called()
        self.assertEqual(state["status"], "needs_keyframe_review")
        self.assertEqual(state["keyframe_preflight"]["status"], "review_unavailable")

    def test_lighthouse_v2_429_preflight_rechecks_persisted_keyframes_on_resume(self) -> None:
        """A transient Vertex capacity stop may resume without replacing paid assets."""
        run = self.work / "vertex-keyframe-preflight-429-resume"
        run.mkdir(exist_ok=True)
        timeline = TimelinePlan.for_profile("vertex_veo_fast")
        anchor = __import__("generator").visual_anchor_for_topic("The Lighthouse That Still Signals From an Empty Island")
        shot = _shot(1, "lighthouse", duration=8.0)
        shot.visual_anchor = anchor
        script = Script(
            topic="The Lighthouse That Still Signals From an Empty Island", beats=[], shots=[shot],
            timeline=timeline, narrative_plan=NarrativePlan("mechanism_reveal", "why", "hook", "stake", "turn", "reversal", "payoff"),
            visual_anchor=anchor,
        )
        plan = {
            "normal_video": {"motion_model": "vertex_veo_fast", "model_id": "veo-3.1-fast-generate-001"},
            "hero_video": {"motion_model": "vertex_veo_fast", "model_id": "veo-3.1-fast-generate-001"},
            "hero_keyframe_indices": [1],
            "keyframe_preflight": {
                "version": 1, "required": True, "provider": "vertex_gemini_vision",
                "model_id": "gemini-test", "location": "global", "max_output_tokens": 1024,
            },
        }
        forge = VertexVeoForge(run, plan)
        forge._keyframe_preflight.review = mock.Mock(return_value={
            "status": "reviewed", "accepted": True, "score": 9, "reasons": [], "summary": "Accepted.",
        })
        forge._keyframe_preflight.write_report = mock.Mock(return_value=run / "keyframe_preflight.json")
        state = {
            "status": "needs_keyframe_review",
            "keyframe_preflight": {
                "status": "review_unavailable", "accepted": False,
                "reasons": ["ClientError: 429 RESOURCE_EXHAUSTED"],
                "report_path": str(run / "keyframe_preflight.json"),
            },
        }
        asyncio.run(forge._run_keyframe_preflight_or_stop(script, {}, state, "test-project"))
        forge._keyframe_preflight.review.assert_called_once_with(script, {}, "test-project")
        self.assertTrue(state["keyframe_preflight"]["accepted"])
        self.assertNotIn("status", state)
        self.assertEqual(state["keyframe_preflight_resume_attempts"], 1)
        self.assertEqual(
            state["keyframe_preflight_history"][0]["action"],
            "resume_same_keyframes_after_transient_review_gap",
        )

    def test_vertex_image_policy_uses_pro_only_for_hook_and_reveal(self) -> None:
        first = _shot(1, "hook", duration=8.0)
        reveal = _shot(2, "reveal", duration=8.0)
        reveal.journey_phase = "reveal"
        normal = _shot(3, "normal", duration=8.0)
        script = Script(topic="test", beats=[], shots=[first, reveal, normal])
        self.assertTrue(VertexImageForge._is_hero_keyframe(script, 1))
        self.assertTrue(VertexImageForge._is_hero_keyframe(script, 2))
        self.assertFalse(VertexImageForge._is_hero_keyframe(script, 3))
        guarded = VertexImageForge._apply_overlay_policy("A clear scientific crystal cutaway")
        self.assertIn("No arrows", guarded)
        self.assertIn("No arrows", VertexImageForge._apply_overlay_policy("An arrow points at the crystal"))
        permitted = VertexImageForge._apply_overlay_policy("A crystal cutaway", {
            "type": "outline", "purpose": "show the fracture", "placement": "upper_left",
        })
        self.assertIn("exactly one non-decorative outline", permitted)

    def test_flow_schema_and_prompt_are_full_clip_native(self) -> None:
        timeline = TimelinePlan.for_profile("veo_lite")
        schema = build_script_schema(timeline)
        self.assertEqual(schema["properties"]["shots"]["minItems"], 5)
        self.assertEqual(schema["properties"]["keyframes"]["maxItems"], 6)
        self.assertIn("beat_index", schema["properties"]["shots"]["items"]["properties"])
        prompt = build_system_prompt("en", timeline=timeline)
        self.assertIn("total 40s", prompt)
        self.assertIn("5 SHOTS", prompt)
        shot = _shot(1, "anchor", duration=8.0)
        flow = optimize_for_flow(shot)["video_prompt"]
        self.assertIn("full 8-second take", flow)
        self.assertNotIn("within the first", flow)
        self.assertNotIn("hold the achieved", flow)

    def test_fal_retries_are_pinned_to_selected_model(self) -> None:
        forge = MotionForge(self.work / "h3-pinned", motion_model="h3_max")
        attempts = forge._ladder(_shot(1, "engine"))
        self.assertEqual([name for name, *_ in attempts], ["h3_max", "h3_max_retry1", "h3_max_retry2"])
        self.assertTrue(all(fn == forge._h3_max for _, fn, *_ in attempts))
        kling = MotionForge(self.work / "kling-pinned", motion_model="kling_pro")._ladder(_shot(1, "engine"))
        self.assertTrue(all("kling_pro" in name for name, *_ in kling))
        self.assertEqual(kling[0][3]["cfg"], config.KLING_CFG_PRIMARY)
        self.assertEqual(kling[1][3]["cfg"], config.KLING_CFG_RETRY)

    def test_legacy_script_derives_its_own_timeline_without_conversion(self) -> None:
        legacy = Script.from_dict({
            "topic": "legacy", "beats": [], "shots": [
                {"block": 1, "t_start": 0, "t_end": 4, "subject_id": "anchor", "start_image_prompt": "a", "end_image_prompt": "b", "motion_prompt": "the anchor glows"},
                {"block": 2, "t_start": 4, "t_end": 10, "subject_id": "anchor", "start_image_prompt": "b", "end_image_prompt": "c", "motion_prompt": "the anchor turns"},
            ],
        })
        self.assertTrue(legacy.timeline.legacy)
        self.assertEqual(legacy.timeline.shot_durations, (4.0, 6.0))
        self.assertEqual(legacy.timeline.total_duration, 10.0)
        self.assertEqual([shot.duration for shot in legacy.shots], [4.0, 6.0])

    def test_resume_uses_legacy_script_even_without_state_marker(self) -> None:
        run = self.work / "legacy-resume-no-state"
        run.mkdir(exist_ok=True)
        payload = {
            "topic": "legacy", "beats": [], "shots": [
                {"block": 1, "t_start": 0, "t_end": 4, "subject_id": "anchor", "start_image_prompt": "a", "end_image_prompt": "b", "motion_prompt": "the anchor glows"},
                {"block": 2, "t_start": 4, "t_end": 10, "subject_id": "anchor", "start_image_prompt": "b", "end_image_prompt": "c", "motion_prompt": "the anchor turns"},
            ],
        }
        (run / "script.json").write_text(__import__("json").dumps(payload), encoding="utf-8")
        ctx = pipeline.RunContext(
            topic="legacy", out_dir=run, resumed=True,
            timeline=TimelinePlan.for_profile("h3_max"),
        )
        with mock.patch.object(pipeline, "_write_prompt_manifest"), \
             mock.patch.object(pipeline.research, "write_manifest"):
            resumed = pipeline.phase1_script(ctx, {})
        self.assertTrue(resumed.timeline.legacy)
        self.assertEqual(ctx.timeline.shot_durations, (4.0, 6.0))
        self.assertEqual(ctx.timeline.total_duration, 10.0)

    def test_release_visual_blocker_and_subjective_review_are_distinct(self) -> None:
        timeline = TimelinePlan.legacy_from_shots([_shot(1, "anchor", duration=4.0)])
        blocking = {"blocks": [{"accepted": True, "visual_quality_blocker": True, "visual_quality": {"accepted": False}}]}
        report = release.write_release_report(self.work, self.moving, self.work / "captions.ass", None, blocking, timeline)
        checks = {item["name"]: item["status"] for item in report["checks"]}
        self.assertEqual(checks["visual_quality"], "fail")
        subjective = {"blocks": [{"accepted": True, "visual_quality_blocker": False, "visual_quality": {"accepted": False}}]}
        review = release.write_release_report(self.work, self.moving, self.work / "captions.ass", None, subjective, timeline)
        review_checks = {item["name"]: item["status"] for item in review["checks"]}
        self.assertEqual(review_checks["visual_quality"], "pass")
        self.assertEqual(review_checks["visual_review"], "review")

    def test_renderer_honors_legacy_non_uniform_boundaries(self) -> None:
        durations = [4.0] * 7 + [6.0]
        boundaries = [sum(durations[:i]) for i in range(1, len(durations))]
        _, graph = editor.render(
            block_paths=[self.moving] * 7 + [self.closing],
            vo_path=self.voice,
            out_path=self.work / "rendered.mp4",
            punch_times=[],
            boundaries=boundaries,
            final_polish=False,
            dry_run=True,
            target_len=sum(durations),
            boundary_kinds=["change"] * 7,
        )
        self.assertIn("trim=duration=6.000", graph)
        self.assertIn("concat=n=8", graph)
        self.assertNotIn("xfade=", graph)

    def test_image_forge_uses_shared_n_plus_one_anchors(self) -> None:
        timeline = TimelinePlan.for_profile("h3_max")
        shots = [_shot(i, "anchor") for i in range(1, timeline.block_count + 1)]
        anchors = [
            {"id": f"anchor{i:02d}", "index": i, "image_prompt": f"anchor {i} view", "subject_id": "anchor"}
            for i in range(1, timeline.keyframe_count + 1)
        ]
        plan = ImageForge(self.work / "anchors")._build_keyframe_plan(
            Script(topic="test", beats=[], shots=shots, anchors=anchors, timeline=timeline)
        )
        self.assertEqual([item[0] for item in plan], [f"kf{i:02d}" for i in range(1, 9)])
        self.assertIn("anchor 2 view", plan[1][1])

    def test_folklore_and_fiction_metadata_are_framed(self) -> None:
        base = {"titles": ["The Black Dog"], "description": "A dark story.", "tags": ["shorts"]}
        folklore = Script(topic="test", beats=[], shots=[], youtube=base, content_type="folklore")
        fiction = Script(topic="test", beats=[], shots=[], youtube=base, content_type="fiction")
        metadata.write_metadata(folklore, self.work / "folklore")
        metadata.write_metadata(fiction, self.work / "fiction")
        f_meta = __import__("json").loads((self.work / "folklore" / "metadata.json").read_text(encoding="utf-8"))
        x_meta = __import__("json").loads((self.work / "fiction" / "metadata.json").read_text(encoding="utf-8"))
        self.assertIn("folklore", f_meta["titles"][0].lower())
        self.assertTrue(x_meta["titles"][0].lower().startswith("fiction:"))

    def test_cleanup_protects_configuration_and_output(self) -> None:
        protected, _, eligible = cleanup._classification(config.ROOT / "AGENTS.md", "")
        output, _, output_eligible = cleanup._classification(config.OUT_ROOT, "")
        rebuildable, _, rebuildable_eligible = cleanup._classification(config.ROOT / "__pycache__", "")
        self.assertEqual(protected, "required_state")
        self.assertFalse(eligible)
        self.assertEqual(output, "required_state")
        self.assertFalse(output_eligible)
        self.assertEqual(rebuildable, "generated_rebuildable")
        self.assertTrue(rebuildable_eligible)

    def test_motion_sanitizer_keeps_one_physical_action(self) -> None:
        self.assertEqual(
            _first_physical_clause("the chest rises and cells divide"),
            "the chest rises",
        )

    def test_physical_effect_classifier_overrides_low_detail_request(self) -> None:
        profile, tags = config.classify_visual_profile(
            "A rocket lifts from the launch pad with a bright orange plume and dust",
            requested_profile=config.VISUAL_PROFILE_DOCUMENTARY,
        )
        self.assertEqual(profile, config.VISUAL_PROFILE_PHYSICAL)
        self.assertIn("rocket_exhaust", tags)
        self.assertIn("dust", tags)

    def test_physical_effect_prompt_and_motion_include_volumetric_detail(self) -> None:
        shot = _shot(1, "rocket")
        shot.start_image_prompt = "The rocket lifts from the launch pad"
        shot.effect_tags = ["rocket_exhaust", "smoke", "dust"]
        shot.visual_profile = config.VISUAL_PROFILE_PHYSICAL
        shot.endpoint_mode = "first_only"
        prompt = ImageForge(self.work / "physics").build_start_prompt(shot)
        motion = compile_fal_motion(shot)
        self.assertIn("shock diamonds", prompt)
        self.assertIn("volumetric", prompt)
        self.assertIn("volumetric", motion)
        self.assertNotIn("simplified geometric", prompt)

    def test_legacy_script_is_reclassified_when_resumed(self) -> None:
        legacy = Script.from_dict({
            "topic": "test", "beats": [], "shots": [{
                "block": 1, "t_start": 0, "t_end": 4, "subject_id": "rocket",
                "start_image_prompt": "A rocket lifts from a launch pad", "end_image_prompt": "The plume expands",
                "motion_prompt": "the engines ignite", "subject_description": "an SLS rocket", "endpoint_mode": "first_last",
            }],
            "anchors": [{"id": "anchor01", "index": 1, "image_prompt": "A rocket lifts from a launch pad", "subject_description": "an SLS rocket"}],
        })
        self.assertEqual(legacy.shots[0].visual_profile, config.VISUAL_PROFILE_PHYSICAL)
        self.assertIn("rocket_exhaust", legacy.shots[0].effect_tags)
        self.assertEqual(legacy.anchors[0]["visual_domain"], "physical_effect")

    def test_normal_character_stays_documentary_pbr_and_vision_gate_is_not_required(self) -> None:
        shot = _shot(1, "person")
        profile, tags = config.classify_visual_profile("A person explains a mechanism")
        shot.visual_profile, shot.effect_tags = profile, tags
        prompt = ImageForge(self.work / "character").build_start_prompt(shot)
        self.assertEqual(shot.visual_profile, config.VISUAL_PROFILE_DOCUMENTARY)
        self.assertIn("Stylized-realistic 3D documentary", prompt)
        gate = VisualQualityGate(self.work / "vision")
        self.assertEqual(gate.review(shot, self.moving, 1)["status"], "not_required")

    def test_scene_intelligence_classifies_all_high_detail_domains(self) -> None:
        cases = [
            ("A heart wall with coronary vessels and muscle tissue", "anatomy", "clinical", "vessel"),
            ("A cell nucleus shows DNA through a membrane beside mitochondria", "microanatomy", "clinical", "dna"),
            ("An RS-25 turbopump and cooling channel inside an engine nozzle", "technical_mechanism", "mechanical", "cooling_channel"),
            ("Rocket engines ignite as smoke and dust billow from the launch pad", "physical_effect", "physical_realism", "rocket_exhaust"),
            ("A calm person explains a science fact", "character", "editorial", None),
        ]
        for text, domain, target, expected_tag in cases:
            scene = config.classify_scene_intelligence(text)
            self.assertEqual((scene["visual_domain"], scene["detail_target"]), (domain, target))
            if expected_tag:
                self.assertIn(expected_tag, scene["structure_tags"] + scene["effect_tags"])
            self.assertEqual(scene["quality_critical"], domain != "character")

    def test_domain_prompts_keep_clinical_and_mechanical_details_separate(self) -> None:
        anatomy = _shot(1, "heart")
        anatomy.start_image_prompt = "A cross-section of a heart wall with vessels and muscle tissue"
        scene = config.classify_scene_intelligence(anatomy.start_image_prompt)
        anatomy.visual_profile = scene["visual_profile"]
        anatomy.visual_domain = scene["visual_domain"]
        anatomy.detail_target = scene["detail_target"]
        anatomy.structure_tags = scene["structure_tags"]
        anatomy.effect_tags = scene["effect_tags"]
        anatomy.quality_critical = scene["quality_critical"]
        clinical = ImageForge(self.work / "clinical").build_start_prompt(anatomy)
        self.assertIn("Clean clinical 3D medical illustration", clinical)
        self.assertIn("layered tissue", clinical)
        self.assertIn("no surgery, blood splatter", clinical)

        mechanism = _shot(1, "engine")
        mechanism.start_image_prompt = "A turbopump and cooling channel exposed inside a rocket engine nozzle"
        scene = config.classify_scene_intelligence(mechanism.start_image_prompt)
        mechanism.visual_profile = scene["visual_profile"]
        mechanism.visual_domain = scene["visual_domain"]
        mechanism.detail_target = scene["detail_target"]
        mechanism.structure_tags = scene["structure_tags"]
        mechanism.effect_tags = scene["effect_tags"]
        mechanism.quality_critical = scene["quality_critical"]
        mechanical = ImageForge(self.work / "mechanical").build_start_prompt(mechanism)
        self.assertIn("High-detail engineering documentary", mechanical)
        self.assertIn("cooling channels", mechanical)
        self.assertNotIn("clinical 3D medical", mechanical)

    def test_high_detail_domains_use_vision_gate_and_flow_metadata(self) -> None:
        shot = _shot(1, "cell")
        scene = config.classify_scene_intelligence("A cell nucleus and membrane")
        shot.visual_profile = scene["visual_profile"]
        shot.visual_domain = scene["visual_domain"]
        shot.detail_target = scene["detail_target"]
        shot.structure_tags = scene["structure_tags"]
        shot.effect_tags = scene["effect_tags"]
        shot.quality_critical = scene["quality_critical"]
        gate = VisualQualityGate(self.work / "cell-vision")
        self.assertTrue(gate.applies(shot))
        enabled = config.VISUAL_QUALITY_ENABLED
        config.VISUAL_QUALITY_ENABLED = False
        try:
            self.assertEqual(gate.review(shot, self.moving, 1)["status"], "not_required")
        finally:
            config.VISUAL_QUALITY_ENABLED = enabled
        flow = optimize_for_flow(shot)
        self.assertEqual(flow["visual_domain"], "microanatomy")
        self.assertTrue(flow["quality_critical"])

    def test_assembler_repairs_emphasis_to_spoken_word(self) -> None:
        engine = BeatEngine(provider="codefast", lang="en")
        raw = {"beats": [{"index": 1, "role": "myth", "text": "Rocket engines survived for decades.", "emphasis": ["eighties"]}], "keyframes": [], "shots": []}
        script = engine._assemble("test", raw)
        self.assertEqual(script.beats[0].emphasis, ["Rocket"])

    def test_research_gate_requires_trusted_source_for_sensitive_claim(self) -> None:
        untrusted = research.build_manifest(
            "Why the heart resists cancer", "factual",
            [{"url": "https://example.test/wiki", "title": "Summary", "source_type": "secondary", "evidence": "context"}],
            ["The heart never gets cancer."],
        )
        self.assertEqual(untrusted["status"], "review")
        trusted = research.build_manifest(
            "Why the heart resists cancer", "factual",
            [{"url": "https://pubmed.ncbi.nlm.nih.gov/1/", "title": "Study", "source_type": "primary", "evidence": "evidence"}],
            ["Heart tissue has a low rate of cell division."],
        )
        self.assertEqual(trusted["status"], "pass")

    def test_release_report_blocks_unapproved_factual_claims(self) -> None:
        quality = {"blocks": [{"accepted": True}], "contact_sheet": None}
        evidence = {"content_type": "factual", "status": "review"}
        legacy = TimelinePlan.legacy_from_shots([_shot(1, "anchor", duration=4.0)])
        report = release.write_release_report(self.work, self.moving, self.work / "captions.ass", evidence, quality, legacy)
        self.assertFalse(report["publishable"])
        self.assertIn(report["status"], {"fail", "review"})

    def test_run_history_normalizes_and_records(self) -> None:
        db = self.work / "runs.db"
        run_history.record(db, "Why Airplane Windows Have Holes", "factual", "pass", 34.0)
        self.assertEqual(run_history.topic_key("Why airplane windows have holes!"), "why airplane windows have holes")
        with __import__("contextlib").closing(run_history.connect(db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 1)

    def test_run_history_migrates_legacy_cost_columns(self) -> None:
        db = self.work / "legacy-runs.db"
        import sqlite3
        conn = sqlite3.connect(db)
        try:
            conn.execute("CREATE TABLE runs (id INTEGER PRIMARY KEY, topic TEXT, timestamp TEXT, cost REAL, duration REAL)")
            conn.execute("INSERT INTO runs VALUES (1, 'Legacy topic', '2026-01-01', 1.25, 34.0)")
            conn.commit()
        finally:
            conn.close()
        with __import__("contextlib").closing(run_history.connect(db)) as conn:
            row = conn.execute("SELECT topic_key, cost_usd, duration_sec, status FROM runs WHERE id = 1").fetchone()
        self.assertEqual(row, ("legacy topic", 1.25, 34.0, "completed"))


if __name__ == "__main__":
    unittest.main()
