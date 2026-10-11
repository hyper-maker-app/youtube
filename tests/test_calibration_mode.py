from __future__ import annotations

import pytest

pytest.skip("Archived monolithic generator regression; active provider-native pipeline has no VertexVeoForge.", allow_module_level=True)

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import config
import pipeline
from generator import Beat, Script, VertexVeoForge
from timeline import TimelinePlan


def _script(words: int) -> Script:
    text = " ".join("word" for _ in range(words))
    return Script(topic="test", beats=[Beat(index=1, role="hook", text=text, emphasis=["word"])], shots=[])


def test_deepgram_post_tts_gate_uses_the_same_profile_as_script_authoring() -> None:
    timeline = TimelinePlan.for_profile("vertex_veo_fast")
    ctx = pipeline.RunContext(topic="test", out_dir=Path("."), timeline=timeline)
    voice = {"duration": 39.2, "words": {"words": []}}
    prior_wps = config.LANG_PROFILES["en"]["wps"]
    prior_provider = config.TTS_PROVIDER
    try:
        config.TTS_PROVIDER = "deepgram"
        config.LANG_PROFILES["en"]["wps"] = 2.20
        assert pipeline._voice_is_acceptable(ctx, voice, _script(85))
        config.LANG_PROFILES["en"]["wps"] = 2.95
        assert not pipeline._voice_is_acceptable(ctx, voice, _script(85))
    finally:
        config.TTS_PROVIDER = prior_provider
        config.LANG_PROFILES["en"]["wps"] = prior_wps


def test_calibration_state_keeps_attempt_evidence_and_exhaustion() -> None:
    with TemporaryDirectory() as root:
        forge = VertexVeoForge(Path(root), {
            "normal_video": {"motion_model": "vertex_veo_fast", "model_id": "veo-3.1-fast-generate-001"},
            "hero_video": {"motion_model": "vertex_veo_fast", "model_id": "veo-3.1-fast-generate-001"},
        })
        state = {}
        rejected = Path(root) / "candidate.mp4"
        rejected.write_bytes(b"candidate")
        with mock.patch.object(config, "CALIBRATION_MODE", True), mock.patch.object(config, "CALIBRATION_MAX_ATTEMPTS", 3):
            forge._calibration_retry_state(state, "block01", {"provider": "vertex_veo"}, 1, rejected, ["frozen"], "operations/1")
            assert state["block01"]["status"] == "calibration_rejected"
            assert state["block01"]["attempt_history"][0]["operation"] == "operations/1"
            assert state["calibration"]["max_attempts"] == 3
            forge._calibration_exhausted(state, "block01", "no accepted candidate")
        assert state["status"] == "calibration_exhausted"
        assert state["block01"]["status"] == "calibration_exhausted"
