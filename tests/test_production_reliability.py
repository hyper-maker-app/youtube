"""No-network regression coverage for script-route and Lighthouse reliability guards."""

from __future__ import annotations

import pytest

pytest.skip("Archived monolithic generator regression; active provider-native reliability coverage is separate.", allow_module_level=True)

from types import SimpleNamespace
import unittest
from unittest import mock

import config
from generator import (
    BeatEngine, Script, Shot, lighthouse_anchor_blockers, normalize_lighthouse_v2_exterior_payoff,
    visual_anchor_for_topic,
)
from narrative import NarrativePlan, SceneCard
from timeline import TimelinePlan


class ProductionReliabilityTests(unittest.TestCase):
    def test_deepgram_english_budget_is_duration_derived(self) -> None:
        profiles = dict(config.LANG_PROFILES)
        profiles["en"] = {**profiles["en"], "wps": 2.95}
        with mock.patch.object(config, "TTS_PROVIDER", "deepgram"), \
             mock.patch.object(config, "LANG_PROFILES", profiles):
            forty = config.narration_profile("en", 39.2)
            shorter = config.narration_profile("en", 34.2)
        self.assertEqual((forty["target"], forty["min"], forty["max"]), (112, 108, 116))
        self.assertEqual(shorter["target"], round(2.95 * config.speech_budget_seconds(34.2)))
        self.assertEqual(shorter["min"], round(shorter["target"] * 0.96))
        self.assertEqual(shorter["max"], round(shorter["target"] * 1.04))

    def test_vertex_output_prompt_is_json_only_and_tools_stay_on_tool_routes(self) -> None:
        engine = BeatEngine(provider="vertex", lang="en")
        vertex = engine._provider_system_prompt("vertex")
        anthropic = engine._provider_system_prompt("anthropic")
        self.assertIn("exactly one JSON object", vertex)
        self.assertNotIn("emit_script", vertex)
        self.assertNotIn("tool result", vertex)
        self.assertIn("calling emit_script", anthropic)

    def test_vertex_transport_retries_and_provenance_are_redacted(self) -> None:
        engine = BeatEngine(provider="vertex", lang="en")
        response = SimpleNamespace(
            candidates=[SimpleNamespace(finish_reason="STOP")],
            text='{"beats": [], "shots": [], "keyframes": [], "narrative_plan": {}, "youtube": {}}',
        )
        fake_types = SimpleNamespace(HttpOptions=lambda **kwargs: kwargs)
        fake_client = SimpleNamespace()
        fake_genai = SimpleNamespace(Client=lambda **kwargs: fake_client)
        with mock.patch.object(config, "vertex_ai_available", return_value=[]), \
             mock.patch.object(config, "vertex_project_id", return_value="test-project"), \
             mock.patch.dict("sys.modules", {"google": SimpleNamespace(genai=fake_genai), "google.genai": SimpleNamespace(types=fake_types)}), \
             mock.patch.object(engine, "_vertex_generate_once", side_effect=[TimeoutError("secret endpoint"), ConnectionError("secret connection"), response]) as request, \
             mock.patch("generator.time.sleep") as sleep:
            raw = engine._call_vertex("test", None)
        self.assertEqual(request.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 5])
        provenance = raw["_script_generation_provenance"]
        self.assertEqual((provenance["provider"], provenance["output_mode"], provenance["retry_count"]), ("vertex", "json", 2))
        self.assertEqual(provenance["error_class"], "network")
        self.assertNotIn("secret", repr(provenance))

    def test_vertex_fallback_restores_provider_and_records_no_raw_error(self) -> None:
        engine = BeatEngine(provider="vertex", lang="en")
        result = Script(topic="test", beats=[], shots=[])
        def generated(_topic, _model=None):
            if engine.provider == "vertex":
                engine._script_generation_provenance = {"retry_count": 2, "error_class": "timeout"}
                raise RuntimeError("secret model output")
            return result
        with mock.patch.object(config, "ANTHROPIC_API_KEY", "test-key"), \
             mock.patch.object(config, "ANTHROPIC_QUALITY_FALLBACK_MODEL", "claude-sonnet-5"), \
             mock.patch.object(engine, "_generate_with_model", side_effect=generated):
            actual = engine.generate("test")
        self.assertIs(actual, result)
        self.assertEqual(engine.provider, "vertex")
        self.assertEqual(actual.script_generation_provenance["provider"], "anthropic")
        self.assertTrue(actual.script_generation_provenance["fallback"])
        self.assertNotIn("secret", repr(actual.script_generation_provenance))

    def _v3_script(self) -> Script:
        timeline = TimelinePlan.for_profile("vertex_veo_fast")
        anchor = visual_anchor_for_topic("Why the lighthouse still signals")
        views = ["exterior", "lantern_room", "tower_interior", "lighthouse_attached_mechanism", "exterior"]
        shots, cards, anchors = [], [], []
        for block, view in enumerate(views, 1):
            prompt = "red-and-white lighthouse tower on rocky island above open sea" if view == "exterior" else "real lighthouse architecture with attached relay equipment"
            card = SceneCard(f"scene{block:02d}", "advance proof", "dark state", "lit state", "relay closes", "attached relay contacts", "" if block == 1 else f"scene{block - 1:02d}", "what changes next", {"anchor": "same lighthouse"}, "upper_center", "relay is visibly attached", {}, view)
            cards.append(card)
            start, end = timeline.shot_window(block)
            shots.append(Shot(block, start, end, "lighthouse", prompt, prompt, "relay closes", asset_refs=["lighthouse"], scene_id=card.scene_id, purpose=card.purpose, entry_state=card.entry_state, exit_state=card.exit_state, dominant_event=card.dominant_event, proof_on_screen=card.proof_on_screen, asset_states=card.asset_states, anchor_view=view, visual_anchor=anchor))
            anchors.append({"index": block, "image_prompt": prompt})
        anchors.append({"index": 6, "image_prompt": "red-and-white lighthouse tower on rocky island above open sea"})
        return Script("Why the lighthouse still signals", [], shots, timeline=timeline, narrative_plan=NarrativePlan("mechanism_reveal", "why", "hook", "stake", "turn", "reversal", "payoff"), storyboard=cards, anchors=anchors, visual_anchor=anchor)

    def test_lighthouse_v3_view_rules_and_v1_v2_resume_serialization(self) -> None:
        script = self._v3_script()
        self.assertEqual(script.visual_anchor["version"], 3)
        self.assertEqual(lighthouse_anchor_blockers(script), [])
        script.shots[0].anchor_view = "lantern_room"
        self.assertIn("opening/final payoff", " ".join(lighthouse_anchor_blockers(script)))
        for version in (1, 2):
            legacy = self._v3_script()
            legacy.visual_anchor = __import__("generator")._lighthouse_anchor_contract(version)
            legacy.shots[0].anchor_view = ""
            payload = legacy.to_dict()
            self.assertNotIn("anchor_view", payload["shots"][0])
            self.assertNotIn("anchor_view", payload["storyboard"][0])

    def test_lighthouse_v3_payoff_normalization_repairs_interior_handoff_and_scale_chain(self) -> None:
        script = self._v3_script()
        script.shots[-1].purpose = "final payoff"
        script.shots[-2].scale = "macro"
        script.shots[-2].start_camera_angle = "interior"
        script.shots[-2].end_camera_angle = "interior"
        self.assertTrue(normalize_lighthouse_v2_exterior_payoff(script.shots, script.anchors, 5))
        self.assertEqual(script.shots[-2].transition_hint, "match_cut")
        self.assertEqual(script.shots[-2].endpoint_mode, "cut")
        scale = {name: index for index, name in enumerate(config.CAMERA_SCALES)}
        self.assertTrue(all(
            abs(scale[right.scale] - scale[left.scale]) <= config.MAX_SCALE_JUMP
            for left, right in zip(script.shots, script.shots[1:])
        ))


if __name__ == "__main__":
    unittest.main()
