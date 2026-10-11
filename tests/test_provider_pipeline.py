from __future__ import annotations

import unittest

import config
import editor
from main import parse_args
from pipeline import audio_driven_timeline, provider_timeline


class ProviderPipelineTests(unittest.TestCase):
    def test_provider_timeline_is_eight_native_four_second_blocks(self) -> None:
        timeline = provider_timeline()
        self.assertEqual(timeline.block_count, 12)
        self.assertEqual(timeline.shot_durations, (4.0,) * 12)
        self.assertEqual(timeline.total_duration, 48.0)
        self.assertEqual(config.compute_target_duration(timeline.total_duration), 48.0)
        legacy = provider_timeline(blocks=8)
        self.assertEqual(legacy.block_count, 8)
        self.assertEqual(legacy.total_duration, 32.0)

    def test_audio_driven_timeline_clamps_to_six_through_thirteen_native_blocks(self) -> None:
        short = audio_driven_timeline(20.0)
        forty_one = audio_driven_timeline(41.0)
        forty_two = audio_driven_timeline(42.0)
        self.assertEqual((short.block_count, short.total_duration), (6, 24.0))
        self.assertEqual((forty_one.block_count, forty_one.total_duration), (10, 40.0))
        self.assertEqual((forty_two.block_count, forty_two.total_duration), (11, 44.0))
        with self.assertRaisesRegex(RuntimeError, "13-block Shorts contract"):
            audio_driven_timeline(80.0)
        self.assertEqual(forty_one.keyframe_count, 11)
        self.assertEqual(forty_two.source, "providers_audio_driven")

    def test_filtergraph_keeps_target_windows_inside_32_second_footage(self) -> None:
        graph = editor.build_filtergraph(
            8, [], False, boundaries=[4.0, 8.0, 12.0, 16.0, 20.0, 24.0, 28.0],
            block_durations=[4.0] * 8, target_duration=32.0, quadrants=["top_left"] * 8,
            transitions_enabled=False,
        )
        self.assertIn("concat=n=8:v=1:a=0,tpad=stop_mode=clone:stop_duration=1.5", graph)
        self.assertIn("gte(time,28.000)*lt(time,32.000)", graph)
        self.assertIn("clip(iw*0.2800-(iw/zoom/2),0,iw-(iw/zoom))", graph)

    def test_cli_provider_overrides_are_optional(self) -> None:
        args = parse_args(["--topic", "test", "--llm", "gemini_flash", "--image", "flow_agent", "--voice", "edge_tts", "--video", "manual"])
        self.assertEqual((args.llm, args.image, args.voice, args.video), ("gemini_flash", "flow_agent", "edge_tts", "manual"))
        defaults = parse_args(["--topic", "test"])
        self.assertIsNone(defaults.llm)
        self.assertIsNone(defaults.image)
        self.assertIsNone(defaults.voice)
        self.assertIsNone(defaults.video)

    def test_one_block_smoke_timeline_and_cli_flag(self) -> None:
        timeline = provider_timeline(1)
        self.assertEqual((timeline.block_count, timeline.shot_durations, timeline.total_duration), (1, (4.0,), 4.0))
        self.assertEqual(parse_args(["--topic", "test", "--test-blocks", "1"]).test_blocks, 1)

    def test_script_persists_and_restores_youtube_metadata(self) -> None:
        from services.script_engine import Script, Beat
        yt_meta = {
            "titles": ["Title 1", "Title 2", "Title 3"],
            "description": "Interesting explanation.\n\n#shorts #science",
            "tags": ["science", "shorts", "physics"],
        }
        script = Script(
            topic="Test Topic",
            beats=[Beat(1, "Beat text.")],
            shots=[],
            youtube=yt_meta,
        )
        serialized = script.to_dict()
        self.assertEqual(serialized["youtube"]["titles"], ["Title 1", "Title 2", "Title 3"])
        restored = Script.from_dict(serialized)
        self.assertEqual(restored.youtube, yt_meta)

    def test_metadata_writer_creates_paste_ready_txt_and_json(self) -> None:
        import tempfile
        from pathlib import Path
        import metadata
        from services.script_engine import Script, Beat

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            yt_meta = {
                "titles": ["Stomach Acid Truth", "How Stomach Survives", "Razor Blade Test"],
                "description": "Acid vs stomach wall.\n\n#shorts #science",
                "tags": ["stomach", "acid", "biology"],
            }
            script = Script(
                topic="Why stomach doesn't dissolve",
                beats=[Beat(1, "Beat 1")],
                shots=[],
                youtube=yt_meta,
            )
            txt_path = metadata.write_metadata(script, out_dir)
            self.assertTrue(txt_path.exists())
            self.assertTrue((out_dir / "metadata.json").exists())
            content = txt_path.read_text(encoding="utf-8")
            self.assertIn("YOUTUBE YUKLEME METADATASI", content)
            self.assertIn("BASLIK SECENEKLERI", content)
            self.assertIn("1. Stomach Acid Truth", content)
            self.assertIn("ACIKLAMA:", content)
            self.assertIn("ETIKETLER (virgulle ayirarak yapistir):", content)
            self.assertIn("stomach, acid, biology", content)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
