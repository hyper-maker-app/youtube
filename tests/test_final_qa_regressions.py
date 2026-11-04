"""Independent final-QA regressions for rejected and missing video sources."""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

import engine.flow_bridge as flow
from engine.services.boundary_inspector import BoundaryQAReport


def install_offline_providers(monkeypatch, *, produce_video=True):
    async def voice(**kwargs):
        kwargs["out_path"].write_bytes(b"x" * 10001)
        return {"vo_path": kwargs["out_path"], "duration": 8, "words": []}

    async def video(**kwargs):
        if produce_video:
            kwargs["out_path"].write_bytes(b"x" * 1001)

    async def no_wait(*args):
        pass

    monkeypatch.setattr(flow, "get_voice_provider", lambda *args: SimpleNamespace(generate_narration=voice))
    monkeypatch.setattr(flow, "get_video_provider", lambda *args: SimpleNamespace(animate_block=video))
    monkeypatch.setattr(flow.asyncio, "sleep", no_wait)
    monkeypatch.setattr(flow, "extract_video_frame", lambda *args, **kwargs: None)
    monkeypatch.setattr(flow, "validate_video_source", lambda *args, **kwargs: None)
    monkeypatch.setattr(flow, "get_sfx_provider", lambda *args: pytest.fail("Rejected video reached assembly"))


@pytest.mark.parametrize("broll", [False, True])
def test_new_failed_transition_never_reaches_assembly_without_director(tmp_path, monkeypatch, broll):
    install_offline_providers(monkeypatch)

    async def qa(**kwargs):
        return BoundaryQAReport(.4, False, violations=["Invalid transition source"])

    def remotion(**kwargs):
        Path(kwargs["output_path"]).write_bytes(b"x" * 1001)

    monkeypatch.setattr(flow, "inspect_transition_boundary", qa)
    monkeypatch.setattr(flow, "render_remotion_broll", remotion)
    scenes = [{"id": "first", "duration": 4, "visual_prompt": "fixture"},
              {"id": "second", "duration": 4, "visual_prompt": "fixture"}]
    if broll:
        scenes[1].update(is_data_broll=True, template_name="TelemetryCurve", data_payload={"fixture": True})
    with pytest.raises(RuntimeError, match="Transition failed QA"):
        asyncio.run(flow.execute_grok_flow_production(
            project_title="QA fixture", scenes=scenes, out_dir=tmp_path, director_mode=False))
    assert not flow.cache_sidecar(tmp_path / "blocks" / "block_02.mp4").exists()


def test_missing_renderer_output_never_receives_cache_sidecar(tmp_path, monkeypatch):
    install_offline_providers(monkeypatch, produce_video=False)
    with pytest.raises(RuntimeError, match="Renderer did not produce"):
        asyncio.run(flow.execute_grok_flow_production(
            project_title="Missing fixture", scenes=[{"id": "first", "duration": 8}], out_dir=tmp_path))
    assert not flow.cache_sidecar(tmp_path / "blocks" / "block_01.mp4").exists()


@pytest.mark.parametrize("key,value", [
    ("narration", None), ("visual_prompt", None), ("duration", True),
    ("duration", "4"), ("is_data_broll", "false"), ("data_payload", None),
    ("narration", "[Sound of wind]"),
])
def test_live_authoring_rejects_values_outside_its_schema(key, value):
    from engine.services.universal_narrative import generate_5act_script

    class Provider:
        async def generate_script(self, **kwargs):
            scene = {"narration": "You inspect a fixture.", "visual_prompt": "Opaque fixture",
                     "motion_prompt": "", "micro_math": "4s", "duration": 4}
            scene[key] = value
            return {"scenes": [scene]}

    with pytest.raises(ValueError):
        generate_5act_script("Validation fixture", duration=20, llm_provider=Provider())


def test_universal_helper_preserves_default_genre_with_explicit_simulation():
    from engine.services.universal_narrative import generate_universal_scenes
    assert all(scene["simulation_only"] for scene in
               generate_universal_scenes("Explicit fixture", duration=16, simulation=True))


def test_only_broll_source_must_have_full_resolution(tmp_path, monkeypatch):
    import numpy as np
    validator = flow.validate_video_source
    install_offline_providers(monkeypatch)
    monkeypatch.setattr(flow, "validate_video_source", validator)
    monkeypatch.setattr(flow, "extract_video_frame", lambda *args, **kwargs: np.zeros((144, 256, 3), dtype=np.uint8))

    def remotion(**kwargs):
        Path(kwargs["output_path"]).write_bytes(b"x" * 1001)

    monkeypatch.setattr(flow, "render_remotion_broll", remotion)
    with pytest.raises(RuntimeError, match="Invalid B-roll source resolution"):
        asyncio.run(flow.execute_grok_flow_production(project_title="Resolution fixture", out_dir=tmp_path,
            scenes=[{"id": "chart", "duration": 8, "is_data_broll": True,
                     "template_name": "TelemetryCurve", "data_payload": {"fixture": True}}], director_mode=False))
    assert not flow.cache_sidecar(tmp_path / "blocks" / "block_01.mp4").exists()


def test_provider_preserves_authored_words_instead_of_substituting_them():
    from engine.providers.video.playwright_flow import sanitize_flow_prompt
    authored = "A pale figure with exposed bone crosses the reflection."
    assert sanitize_flow_prompt("  " + authored + "  ") == authored
    with pytest.raises(ValueError):
        sanitize_flow_prompt(None)


def test_state_cache_deletion_cannot_escape_production(tmp_path):
    root = tmp_path / "production"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(RuntimeError, match="escapes"):
        flow.remove_flow_state_cache(outside, root)
    assert sentinel.read_text(encoding="utf-8") == "keep"
    contained = root / "block.flow-state"
    contained.mkdir()
    flow.remove_flow_state_cache(contained, root)
    assert not contained.exists()


def test_simulation_is_blocked_by_reviewer_and_physical_factory(tmp_path, monkeypatch):
    from engine.services.universal_narrative import generate_catastrophe_scenes
    from engine.services.screenplay_reviewer import ScreenplayReviewer
    scenes = generate_catastrophe_scenes("Explicit simulation", duration=16, simulation=True)
    reviewer = ScreenplayReviewer(xai_api_key="test-only")
    monkeypatch.setattr(reviewer, "_consult_grok_critique", lambda *args: {"screenplay_score": 99})
    monkeypatch.setattr(reviewer, "_consult_gemini_critique", lambda *args: {"screenplay_score": 99})
    assert not reviewer.review(scenes, consult_ai=True).passed
    monkeypatch.setattr(flow, "get_voice_provider", lambda *args: pytest.fail("Simulation spent voice credits"))
    with pytest.raises(ValueError, match="Simulation scenes"):
        asyncio.run(flow.execute_grok_flow_production(project_title="Explicit simulation", scenes=scenes, out_dir=tmp_path))
