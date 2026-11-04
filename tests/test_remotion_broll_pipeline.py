"""Tests for Remotion Motion Graphics B-Roll & Flow CDP Pipeline Integration.

Verifies:
1. `render_remotion_broll` pure engine invocation and parameter passing.
2. `[DATA_BROLL]` bypass of Veo video generator and routing to Remotion.
3. Transition Boundary QA exception for `[DATA_BROLL]` (skips facial DNA checks, verifies resolution).
4. Frame rate normalization to 60 FPS in FFmpeg concat filter chain.
5. CLI subcommands `motion-graphics storm-map` and `motion-graphics telemetry`.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from engine import config
from engine import editor
from engine.flow_bridge import execute_grok_flow_production, is_scene_data_broll
from engine.services.boundary_inspector import inspect_transition_boundary, BoundaryQAReport
from engine.services.remotion_bridge import (
    render_remotion_broll,
    resolve_template_name,
    resolve_browser_executable,
)
from tools.cinematic_studio_cli import app

runner = CliRunner()


def test_remotion_template_name_resolution():
    """Verify alias mapping to canonical Remotion composition IDs."""
    assert resolve_template_name("storm_map") == "GeospatialStormMap"
    assert resolve_template_name("storm-map") == "GeospatialStormMap"
    assert resolve_template_name("radar") == "GeospatialStormMap"
    assert resolve_template_name("telemetry") == "TelemetryCurve"
    assert resolve_template_name("telemetry_curve") == "TelemetryCurve"
    assert resolve_template_name("volcano_map") == "VolcanoSeismicMap"
    assert resolve_template_name("CustomComposition") == "CustomComposition"


def test_is_scene_data_broll_detection():
    """Verify robust zero-hardcode detection of [DATA_BROLL] markers."""
    assert is_scene_data_broll({"visual_prompt": "[DATA_BROLL] Storm radar"})
    assert is_scene_data_broll({"motion_prompt": "Camera pans [DATA_BROLL]"})
    assert is_scene_data_broll({"is_data_broll": True})
    assert is_scene_data_broll({"broll_type": "telemetry"})
    assert not is_scene_data_broll({"visual_prompt": "A lone scientist walks through oak door"})


def test_transition_boundary_qa_skips_facial_dna_for_data_broll(tmp_path: Path):
    """Verify transition boundary QA approves data B-roll without facial DNA checks."""
    async def _run():
        # Synthesize a valid 1920x1080 test video block
        broll_mp4 = tmp_path / "broll_test.mp4"
        prev_mp4 = tmp_path / "prev_block.mp4"
        ffmpeg = config.resolve_ffmpeg()

        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=1920x1080:r=60",
            "-t", "0.5", "-pix_fmt", "yuv420p", "-c:v", "libx264", str(broll_mp4)
        ]
        import subprocess
        subprocess.run(cmd, check=True)
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=1920x1080:r=30", "-t", "0.5", "-pix_fmt", "yuv420p", "-c:v", "libx264", str(prev_mp4)], check=True)

        qa_rep = await inspect_transition_boundary(
            hero_plate_path=None,
            block_n_video=prev_mp4,
            block_n_plus_1_video=broll_mp4,
            dry_run=True,
            is_data_broll=True,
        )

        assert qa_rep.passed is True
        assert qa_rep.continuity_score >= 0.85
        assert qa_rep.inspected_by == "data_broll_resolution_validator"
        assert len(qa_rep.violations) == 0

    asyncio.run(_run())


def test_editor_harmonizes_mixed_frame_rates_to_60fps(tmp_path: Path):
    """Verify editor normalizes Veo 24/30 FPS and Remotion 60 FPS clips to 60 FPS in concat."""
    # Build a video filter with explicit 60 fps
    stmts = editor.build_video_filter(
        n_blocks=2,
        punch_times=[],
        block_durations=[6.0, 6.0],
        target_duration=12.0,
        fps=60,
    )
    joined = ";".join(stmts)
    # Check that both inputs are normalized to fps=60 before concat
    assert "[0:v]trim=duration=6.000,setpts=PTS-STARTPTS,fps=60," in joined
    assert "[1:v]trim=duration=6.000,setpts=PTS-STARTPTS,fps=60," in joined
    # Check that pts normalization uses 60
    assert "setpts=N/60/TB[cat_pts]" in joined
    assert "fps=60[zoom]" in joined


def test_flow_bridge_routes_data_broll_to_remotion(tmp_path: Path):
    """Verify execute_grok_flow_production routes [DATA_BROLL] blocks to Remotion."""
    async def _run():
        scenes = [
            {
                "id": "scene_01",
                "narration": "You monitor the approaching hurricane on radar.",
                "visual_prompt": "[DATA_BROLL] Radar sweeps over approaching hurricane eye.",
                "duration": 4.0,
                "is_data_broll": True,
                "template_name": "GeospatialStormMap",
                "data_payload": {
                    "center": [0, 0], "zoom": 2,
                    "title": "Test", "subtitle": "Test", "coordinatesLabel": "Test",
                    "classification": "Test", "timestampLabel": "Test",
                    "eventCount": 3, "eventCountLabel": "Test", "systemStatus": "Test", "metrics": [],
                },
            },
            {
                "id": "scene_02",
                "narration": "You seal the reinforced storm shutters.",
                "visual_prompt": "First-person POV of your hands locking steel deadbolts.",
                "duration": 4.0,
            },
        ]

        with patch("engine.flow_bridge.render_remotion_broll") as mock_remotion:
            # Mock remotion to produce a dummy file
            def fake_render(template_name, data_payload, output_path, **kwargs):
                p = Path(output_path)
                p.parent.mkdir(parents=True, exist_ok=True)
                # Create a minimal valid video block with ffmpeg
                ffmpeg = config.resolve_ffmpeg()
                cmd = [
                    ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=blue:s=1920x1080:r=60",
                    "-t", str(kwargs["duration_seconds"]), "-pix_fmt", "yuv420p", "-c:v", "libx264", str(p)
                ]
                import subprocess
                subprocess.run(cmd, check=True)
                return p

            mock_remotion.side_effect = fake_render

            out_film = await execute_grok_flow_production(
                project_title="Test Motion Production",
                genre="Sci-Fi",
                scenes=scenes,
                out_dir=tmp_path / "prod",
                dry_run=True,
                no_music=True,
                no_captions=True,
            )

            # Verify remotion_bridge was invoked for the [DATA_BROLL] block
            assert mock_remotion.call_count >= 1
            call_kwargs = mock_remotion.call_args[1]
            assert call_kwargs.get("template_name") == "GeospatialStormMap"
            assert call_kwargs.get("fps") == 60
            assert call_kwargs["data_payload"] == scenes[0]["data_payload"]

    asyncio.run(_run())


def test_cli_motion_graphics_help():
    """Verify CLI motion-graphics root and subcommands."""
    result = runner.invoke(app, ["motion-graphics", "--help"])
    assert result.exit_code == 0
    assert "storm-map" in result.stdout
    assert "telemetry" in result.stdout

    result_storm = runner.invoke(app, ["motion-graphics", "storm-map", "--help"])
    assert result_storm.exit_code == 0
    assert "--output" in result_storm.stdout
    assert "--duration" in result_storm.stdout
    assert "--fps" in result_storm.stdout

    result_telem = runner.invoke(app, ["motion-graphics", "telemetry", "--help"])
    assert result_telem.exit_code == 0
    assert "--metric-name" in result_telem.stdout
    assert "--threshold" in result_telem.stdout
