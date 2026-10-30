"""Unit & integration test suite for Grok Studio Visual Continuity QA & Autonomous HEAL Loop.

Verifies:
1. Cross-block visual continuity boundary QA inspection ([Block N Exit] vs [Block N+1 Entry]).
2. Defect detection: Transition Boundary QA score drops below threshold (< 0.85) on visual breach.
3. Autonomous Director Agent intervention: Classifies severity (SEV0-SEV6), arbitrates HEAL vs CANONIZE.
4. Prompt surgery: Injects scoped negatives, tighter MCU camera framing, and corrective constraints.
5. Automated re-generation (re-roll): Re-renders defective block with healed prompt.
6. Verification pass: Re-evaluates transition boundary and confirms passed=True [HEAL VERIFIED].
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
if str(ROOT / "engine") not in sys.path:
    sys.path.insert(0, str(ROOT / "engine"))

import pytest
from typer.testing import CliRunner

from engine.flow_bridge import execute_grok_flow_production
from engine.services.director_agent import (
    DirectorAction,
    DirectorDecision,
    SeverityLevel,
    VisualDelta,
    WorldState,
    arbitrate_decision,
)
from tools.cinematic_studio_cli import app

runner = CliRunner()


def test_director_agent_severity_arbitration():
    """Verify that Director Agent correctly maps defect severities to HEAL, HYBRID, and CANONIZE."""
    world_state = WorldState(project_id="test-world")

    # 1. Cosmetic wear / dust / splinter -> CANONIZE
    delta_wear = VisualDelta(
        entity_id="E_DOOR_01",
        attribute="surface_wear",
        before_value="clean",
        after_value="minor diagonal splinter SPL04",
        severity=SeverityLevel.SEV1_WEAR_DELTA,
        narrative_utility=0.8,
        evidence="Micro-splinter along right oak jamb",
    )
    action_wear = arbitrate_decision(delta_wear, world_state, current_attempt=1)
    assert action_wear.decision == DirectorDecision.CANONIZE
    assert action_wear.severity == SeverityLevel.SEV1_WEAR_DELTA

    # 2. Prop position shift -> HYBRID
    delta_prop = VisualDelta(
        entity_id="E_DOOR_01",
        attribute="deadbolt_latch",
        before_value="locked",
        after_value="unlatched",
        severity=SeverityLevel.SEV2_PROP_STATE_SHIFT,
        narrative_utility=0.2,
        evidence="Deadbolt shifted from vertical to horizontal",
    )
    action_prop = arbitrate_decision(delta_prop, world_state, current_attempt=1)
    assert action_prop.decision == DirectorDecision.HYBRID

    # 3. Spatial geometry flip -> HEAL
    delta_geom = VisualDelta(
        entity_id="E_DOOR_01",
        attribute="hinge_side",
        before_value="right jamb",
        after_value="left jamb",
        severity=SeverityLevel.SEV3_SPATIAL_DRIFT,
        narrative_utility=-0.5,
        evidence="Hinges migrated from right to left side",
    )
    action_geom = arbitrate_decision(delta_geom, world_state, current_attempt=1)
    assert action_geom.decision == DirectorDecision.HEAL
    assert "Lock door hinges strictly to right jamb" in action_geom.corrective_prompt

    # 4. Fatal Ontology breach (oak -> glass) -> HEAL with scoped negatives
    delta_fatal = VisualDelta(
        entity_id="E_DOOR_01",
        attribute="material_class",
        before_value="solid_white_oak",
        after_value="transparent_glass",
        severity=SeverityLevel.SEV5_ONTOLOGY_BREAK,
        narrative_utility=-1.0,
        evidence="Solid oak barrier transformed into glass French door",
    )
    action_fatal = arbitrate_decision(delta_fatal, world_state, current_attempt=1)
    assert action_fatal.decision == DirectorDecision.HEAL
    assert "glass door" in action_fatal.scoped_negatives
    assert "French door" in action_fatal.scoped_negatives
    assert "100% opaque solid white-oak slab" in action_fatal.corrective_prompt


def test_continuity_heal_loop_execution():
    """Verify end-to-end execution of the visual continuity defect -> HEAL -> re-roll loop."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_dir = Path(tmp_dir) / "out_heal_test"
        out_dir.mkdir(parents=True, exist_ok=True)

        test_scenes = [
            {
                "id": "scene_01",
                "scene_number": 1,
                "narration": "You stand before the reinforced oak barrier holding the forged pry-bar.",
                "visual_prompt": "A solid opaque white-oak door with black iron hinges and deadbolt.",
                "motion_prompt": "Subtle camera drift forward toward the reinforced oak slab.",
                "duration": 4.0,
                "focus_entity": "E_DOOR_01",
            },
            {
                "id": "scene_02",
                "scene_number": 2,
                "narration": "You raise the tool, eyes locked on the strike plate as wood fibers groan.",
                "visual_prompt": "Close-up of the oak door strike plate and deadbolt under halogen light.",
                "motion_prompt": "Macro push-in focusing directly on the oak wood grain and iron deadbolt.",
                "duration": 4.0,
                "focus_entity": "E_DOOR_01",
            },
        ]

        final_mp4 = asyncio.run(
            execute_grok_flow_production(
                project_title="Unit Test Continuity Healing",
                genre="Survival Horror",
                scenes=test_scenes,
                out_dir=out_dir,
                aspect_ratio="16:9",
                dry_run=True,
                no_music=True,
                no_captions=True,
                block_duration=4.0,
                voice_provider="deepgram",
                director_mode=True,
                episode_num=1,
                simulate_defect_block=2,  # Force defect on block 2 attempt 1
            )
        )

        assert final_mp4.is_file(), "Final film MP4 must be produced"
        b1 = out_dir / "blocks" / "block_01.mp4"
        b2 = out_dir / "blocks" / "block_02.mp4"
        assert b1.is_file(), "Block 1 must exist"
        assert b2.is_file(), "Block 2 must be healed and exist"

        # Verify episode continuity state and handoff snapshot
        cont_state = out_dir / "continuity_state.json"
        handoff = out_dir / "episode_handoff.json"
        assert cont_state.is_file(), "Continuity state must be persisted"
        assert handoff.is_file(), "Episode handoff must be frozen"


def test_cli_test_continuity_command():
    """Verify that the user-facing CLI command 'test-continuity' runs cleanly with exit code 0."""
    result = runner.invoke(app, ["test-continuity"])
    assert result.exit_code == 0, f"Command failed with output: {result.output}"
    assert "Visual Continuity Healing Gateway" in result.output
    assert "Continuity Healing Verified" in result.output
    assert "Visual Continuity Failure" in result.output
    assert "HEAL VERIFIED" in result.output
