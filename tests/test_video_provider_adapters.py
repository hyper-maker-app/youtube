from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from providers._flow_agent import FlowAgentClient
from providers.base import HandoffPending, ProviderError
from providers.factory import get_image_provider, get_video_provider
from providers.image.flow_agent_banana import FlowAgentBananaProvider
from providers.video.flow_agent_veo import FlowAgentVeoProvider
from providers.video.vertex_veo import (
    MAX_PROMPT_LENGTH,
    VERTEX_REQUEST_PARAMETERS,
    VertexVeoProvider,
)


class _RecordingFlow:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def image(self, prompt: str, out_path: Path, seed: int) -> Path:
        self.calls.append(("image", prompt, out_path, seed))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"image")
        return out_path

    async def video(self, prompt: str, start: Path, end: Path | None, out_path: Path) -> Path:
        self.calls.append(("video", prompt, start, end, out_path))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"video")
        return out_path


class VideoProviderAdapterTests(unittest.TestCase):
    def test_vertex_sanitizer_replaces_whole_words_and_caps_prompt(self) -> None:
        prompt = "Cancer blood needle puncture wound cut " + ("continuity " * 100)
        actual = VertexVeoProvider.sanitize_prompt(prompt)
        self.assertIn("abnormal cellular cluster", actual)
        self.assertIn("crimson fluid", actual)
        self.assertIn("micro probe", actual)
        self.assertNotRegex(actual, r"\b(?:cancer|blood|needle|puncture|wound|cut)\b")
        self.assertLessEqual(len(actual), MAX_PROMPT_LENGTH)

    def test_vertex_request_contract_and_safety_evidence_are_explicit(self) -> None:
        self.assertEqual(VERTEX_REQUEST_PARAMETERS, {
            "aspectRatio": "9:16", "durationSeconds": 4,
            "personGeneration": "ALLOW_ADULT", "safetySetting": "BLOCK_ONLY_HIGH",
            "resolution": "1080p",
        })
        from google.genai import types
        self.assertIn("resolution", types.GenerateVideosConfig.model_fields)
        self.assertEqual(types.GenerateVideosConfig(resolution="1080p").resolution, "1080p")
        source = Path("providers/video/vertex_veo.py").read_text(encoding="utf-8")
        self.assertIn('"resolution": VERTEX_REQUEST_PARAMETERS["resolution"]', source)
        self.assertIn('except (ConfigurationError, ProviderError):', source)
        provider = VertexVeoProvider(project="project", location="location")
        categories = provider._safety_categories({
            "response": {"safetyAttributes": {"blocked": True, "categories": ["MEDICAL"]}},
        })
        self.assertEqual(categories, ["MEDICAL"])
        with self.assertRaisesRegex(ProviderError, "TERMINAL ERROR: Veo Safety Triggered on Category MEDICAL"):
            provider._raise_safety(categories)

    def test_vertex_sdk_config_omits_unsupported_safety_setting_but_keeps_local_rai_guard(self) -> None:
        # Current google-genai releases do not accept ``safety_setting`` for Veo.
        # RAI remains fail-closed through prompt sanitization and response inspection.
        source = Path("providers/video/vertex_veo.py").read_text(encoding="utf-8")
        self.assertIn('"safetySetting": "BLOCK_ONLY_HIGH"', source)
        self.assertNotIn('"safety_setting": VERTEX_REQUEST_PARAMETERS["safetySetting"]', source)

    def test_flow_keyframe_and_video_adapter_use_required_vertical_contract(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            flow = _RecordingFlow()
            image = FlowAgentBananaProvider(client=flow)
            keyframe = asyncio.run(image.generate_keyframe("keyframe", root / "keyframes" / "kf01.png", 7))
            video = FlowAgentVeoProvider(client=flow)
            block = asyncio.run(video.animate_block(keyframe, None, "move forward", root / "blocks" / "block01.mp4"))
            self.assertTrue(block.is_file())
            self.assertEqual(flow.calls[0][0:2], ("image", "keyframe"))
            self.assertEqual(flow.calls[1][0:2], ("video", "move forward"))
            with self.assertRaisesRegex(ValueError, "fixed at 4.0 seconds"):
                asyncio.run(video.animate_block(keyframe, None, "move", root / "blocks" / "bad.mp4", duration=8))

    def test_flow_failure_writes_manual_handoff_without_token(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            client = FlowAgentClient(session_token="private-token", cli_path="definitely-not-a-flow-command")
            with self.assertRaises(HandoffPending) as caught:
                asyncio.run(client.image("a frame", root / "keyframes" / "kf01.png", 1))
            handoff = caught.exception.handoff_path
            body = handoff.read_text(encoding="utf-8")
            self.assertTrue(handoff.is_file())
            self.assertIn(" image ", body)
            self.assertNotIn("private-token", body)

    def test_factory_resolves_image_and_vertex_video_by_selected_environment(self) -> None:
        values = {
            "IMAGE_PROVIDER": "flow_agent", "FLOW_AGENT_CLI_PATH": "flow",
            "VIDEO_PROVIDER": "vertex_veo", "GOOGLE_CLOUD_PROJECT": "project", "VERTEX_LOCATION": "location",
        }
        with mock.patch.dict(os.environ, values, clear=False):
            self.assertIsInstance(get_image_provider(), FlowAgentBananaProvider)
            self.assertIsInstance(get_video_provider(), VertexVeoProvider)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
