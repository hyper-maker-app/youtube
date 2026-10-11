"""Focused regression coverage for the active provider-native path."""

from __future__ import annotations

import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import pytest

import config
import main
import pipeline
from providers.base import ConfigurationError, ProviderError
from providers.bundles import production_bundle
from providers.factory import get_image_provider
from providers.image.nano_banana_pro import NanoBananaProProvider
from providers.llm.vertex_gemini import VertexGeminiProvider
from services.script_engine import Beat, BeatEngine, Script, Shot, optimize_for_flow, transition_boundary_kinds, validate_script
from services.topic_selection import COMPLETED_EXCLUDES, select_topic
from timeline import TimelinePlan


def _timeline(blocks: int = 8) -> TimelinePlan:
    return pipeline.provider_timeline(blocks=blocks)


def _shot(block: int, timeline: TimelinePlan, *, subject: str = "valve", transition: str = "same_subject", scale: str = "medium", marker: str = "none") -> Shot:
    start, end = timeline.shot_window(block)
    return Shot(
        block=block, beat_index=min(block, 5), t_start=start, t_end=end, subject_id=subject,
        subject_description="a connected brass valve and pipe", start_image_prompt="valve closed", end_image_prompt="valve open",
        motion_prompt="the connected valve stem rotates once", target_quadrant="top_left", visual_domain="mechanical",
        entry_state="closed", exit_state="open", dominant_event="the valve stem rotates once", proof_on_screen="the valve aperture opens",
        scale=scale, journey_phase="explore", transition_kind=transition, continuity_anchor="the same brass valve housing",
        detail_target="threaded stem and attached pipe", quality_critical=["attached pipe", "fixed valve body"], location_id="pump_room",
        marker_type=marker, marker_quadrant="top_left" if marker != "none" else None,
    )


def _script(timeline: TimelinePlan) -> Script:
    shots = [_shot(index, timeline, transition="subject_change" if index == 2 else "same_subject", subject="second_valve" if index >= 2 else "valve") for index in range(1, timeline.block_count + 1)]
    return Script("Why valves turn", [Beat(index, f"Beat {index}.") for index in range(1, 6)], shots, timeline=timeline)


def test_full_timeline_and_persisted_resume_contract() -> None:
    timeline = _timeline()
    assert (timeline.block_count, timeline.keyframe_count, timeline.total_duration, config.TAIL_HOLD) == (8, 9, 32.0, 1.5)
    legacy = TimelinePlan.from_dict({"shot_durations": [4.0] * 8, "block_count": 8, "total_duration": 32.0})
    assert legacy.block_count == 8 and legacy.total_duration == 32.0
    assert pipeline.provider_timeline(1).keyframe_count == 2
    with pytest.raises(SystemExit, match="cannot be combined"):
        main.main(["--resume", "any", "--test-blocks", "1"])


def test_measured_voice_locks_visual_timeline_without_rejecting_word_heuristics() -> None:
    provisional = _timeline()
    script = _script(provisional)
    with TemporaryDirectory() as directory:
        ctx = pipeline.RunContext("topic", Path(directory), timeline=provisional)
        locked = pipeline._lock_audio_driven_timeline(ctx, script, {"duration": 37.5}, {})
    assert locked.timeline is not None
    assert locked.timeline.source == "providers_audio_driven"
    assert locked.timeline.block_count == 10
    assert len(locked.shots) == 10
    assert locked.timeline.target_duration == 40.0


def test_resumed_provisional_timeline_locks_from_measured_voice() -> None:
    provisional = _timeline()
    script = _script(provisional)
    with TemporaryDirectory() as directory:
        root = Path(directory)
        ctx = pipeline.RunContext("topic", root, resumed=True, timeline=provisional)
        state: dict[str, object] = {}
        locked = pipeline._lock_audio_driven_timeline(ctx, script, {"duration": 26.355}, state)
        persisted = json.loads((root / "script.json").read_text(encoding="utf-8"))
    assert locked.timeline is not None
    assert locked.timeline.source == "providers_audio_driven"
    assert locked.timeline.block_count == 7
    assert state["audio_timeline_locked"] is True
    assert persisted["timeline"]["source"] == "providers_audio_driven"
    assert persisted["timeline"]["block_count"] == 7


def test_retiming_marks_new_cross_subject_neighbors_as_match_cuts() -> None:
    original = _script(_timeline())
    for shot in original.shots[2:]:
        shot.subject_id = "motor"
        shot.continuity_anchor = "the same motor chassis"
        shot.location_id = "motor_bay"
    original.shots[2].transition_kind = "subject_change"
    original.shots[3].transition_kind = "same_subject"
    shortened = TimelinePlan.for_profile("providers_4s", 24.0)
    retimed = pipeline._retime_shots_to_timeline(original, shortened)
    # Six-block sampling keeps authored shot four but omits its original motor
    # predecessor, so it must become an explicit subject Match-Cut from valve.
    assert retimed.shots[2].subject_id == "motor"
    assert retimed.shots[2].transition_kind in {"subject_change", "location_change"}
    assert not any("same_subject" in problem for problem in validate_script(retimed, shortened))


def test_canonical_keyframe_compiler_and_marker_rules() -> None:
    timeline = _timeline()
    shot = _shot(1, timeline, marker="arrow")
    compiled = optimize_for_flow(shot)
    for token in ("Glossy Stylized 3D", "Vertical 9:16", "Continuity anchor", "caption-safe", "closed or neutral mouths", "watermark", "dark neutral", "cyan rim", "Instead of any burst or spark"):
        assert token.casefold() in (compiled["start_prompt"] + compiled["end_prompt"] + compiled["video_prompt"]).casefold()
    assert "camera must" not in compiled["video_prompt"].casefold()
    broken = _shot(1, timeline, marker="arrow")
    broken.marker_quadrant = "bottom_left"
    assert any("marker" in issue for issue in validate_script(Script("x", [Beat(i, "x") for i in range(1, 6)], [broken] * 8, timeline=timeline), timeline))


def test_keyframes_form_an_actual_sequential_match_cut_chain() -> None:
    timeline = _timeline()
    script = _script(timeline)
    jobs = pipeline._keyframe_jobs(script, Path("out"))
    assert [key for key, *_ in jobs] == [f"kf{i:02d}" for i in range(1, 10)]
    # kf02 must represent block one\'s exit, not a separately imagined block-two entry.
    assert script.shots[0].exit_state in jobs[1][1]
    assert script.shots[-1].exit_state in jobs[-1][1]
    assert "supplied previous keyframe as the exact visual reference" in jobs[1][1]
    assert "only to carry camera energy" in jobs[2][1]
    assert jobs[0][4] is True
    assert all(not job[4] for job in jobs[1:])
    script.shots[0].journey_phase = "reveal"
    assert pipeline._keyframe_jobs(script, Path("out"))[1][4] is True


def test_nano_banana_pro_conditions_an_endpoint_on_its_previous_keyframe(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = NanoBananaProProvider(project="test-project", location="test-location", model_normal="normal", model_hero="hero")
    captured: dict[str, Path | str | None] = {}

    def generate(_prompt: str, path: Path, _seed: int, reference: Path | None = None, model: str | None = None) -> Path:
        captured["reference"] = reference
        captured["model"] = model
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")
        return path

    with TemporaryDirectory() as directory:
        root = Path(directory)
        previous = root / "kf01.png"
        previous.write_bytes(b"prior")
        provider._generate_sync = generate  # type: ignore[method-assign]
        output = __import__("asyncio").run(
            provider.generate_keyframe("endpoint", root / "kf02.png", 2, reference_image=previous)
        )
        assert output.is_file()
        assert captured["reference"] == previous
        assert captured["model"] == "normal"


def test_nano_banana_pro_selects_the_configured_model() -> None:
    provider = NanoBananaProProvider(project="test-project", location="global", model_normal="normal-model", model_hero="hero-model")
    selected: list[str | None] = []

    def generate(_prompt: str, path: Path, _seed: int, _reference: Path | None = None, model: str | None = None) -> Path:
        selected.append(model)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")
        return path

    with TemporaryDirectory() as directory:
        root = Path(directory)
        provider._generate_sync = generate  # type: ignore[method-assign]
        asyncio = __import__("asyncio")
        asyncio.run(provider.generate_keyframe("normal", root / "normal.png", 1))
        asyncio.run(provider.generate_keyframe("hero", root / "hero.png", 2, is_hero=True))
    assert selected == ["normal-model", "hero-model"]


def test_nano_banana_pro_uses_its_explicit_model_location(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NANO_BANANA_PRO_LOCATION", "global")
    provider = NanoBananaProProvider(project="test-project", model="gemini-3-pro-image")
    assert provider.location == "global"


def test_scale_progression_and_mechanical_artifact_rejection() -> None:
    timeline = _timeline()
    first = _shot(1, timeline, scale="wide")
    second = _shot(2, timeline, scale="nano")
    rest = [_shot(index, timeline) for index in range(3, 9)]
    script = Script("x", [Beat(i, "x") for i in range(1, 6)], [first, second, *rest], timeline=timeline)
    issues = validate_script(script, timeline)
    assert any("max scale jump" in issue for issue in issues)
    assert any("not appropriate for mechanical" in issue for issue in issues)
    first.motion_prompt = "floating parts and random sparks appear"
    assert any("fragile mechanical artifact" in issue for issue in validate_script(script, timeline))


def test_boundary_kind_reaches_editor_and_visual_impacts_are_opt_in() -> None:
    timeline = _timeline()
    script = _script(timeline)
    assert transition_boundary_kinds(script.shots) == ["change", "same", "same", "same", "same", "same", "same"]
    with TemporaryDirectory() as directory:
        root = Path(directory)
        ctx = pipeline.RunContext("x", root, captions=False, timeline=timeline)
        with mock.patch.object(pipeline.editor, "render") as render:
            pipeline.phase5_edit(ctx, script, [root / "block.mp4"] * 8, {"vo_path": root / "voice.wav", "words": []})
        assert render.call_args.kwargs["boundary_kinds"][0] == "change"
    assert (config.PUNCH_AMOUNT, config.BOUNDARY_PUNCH_AMT, config.SHAKE_AMPLITUDE_PX) == (0.0, 0.0, 0)


def test_atomic_json_is_bom_free_and_topic_selection_is_explicit_fallback() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "artifact.json"
        pipeline.atomic_write_json(path, {"ok": True})
        assert not path.read_bytes().startswith(b"\xef\xbb\xbf")
        assert json.loads(path.read_text(encoding="utf-8")) == {"ok": True}
        selected = select_topic(root / "history.db")
    assert selected["trend_status"] == "unavailable"
    assert selected["selection_mode"] == "evergreen_fallback"
    assert selected["selected_topic"]
    assert COMPLETED_EXCLUDES


def test_resume_reuses_only_exact_keyframes_and_legacy_voice_artifacts() -> None:
    timeline = _timeline()
    script = _script(timeline)
    with TemporaryDirectory() as directory:
        root = Path(directory)
        jobs = pipeline._keyframe_jobs(script, root)
        manifest = pipeline._prompt_manifest(jobs)
        refs = {}
        for key, _, path, _, _ in jobs:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"frame")
            refs[key] = {"local": str(path)}
        pipeline.atomic_write_json(root / "prompt_manifest.json", manifest)
        pipeline.atomic_write_json(root / "refs.json", refs)
        assert pipeline._valid_reusable_refs(root / "refs.json", root / "prompt_manifest.json", manifest) == refs
        assert manifest["kf01"]["tier"] == "nano_banana_pro"
        assert manifest["kf01"]["model"] == config.NANO_BANANA_PRO_MODEL
        assert manifest["kf02"]["tier"] == "nano_banana_pro"
        assert manifest["kf02"]["model"] == config.NANO_BANANA_PRO_MODEL
        stale_model_manifest = json.loads(json.dumps(manifest))
        stale_model_manifest["kf01"]["model"] = "different-model"
        pipeline.atomic_write_json(root / "prompt_manifest.json", stale_model_manifest)
        assert "kf01" not in pipeline._valid_reusable_refs(root / "refs.json", root / "prompt_manifest.json", manifest)
        pipeline.atomic_write_json(root / "prompt_manifest.json", manifest)
        # A stale alias must not be accepted even if it names a real file.
        alias = root / "keyframes" / "stale.png"
        alias.write_bytes(b"old")
        refs["kf01"] = {"local": str(alias)}
        pipeline.atomic_write_json(root / "refs.json", refs)
        assert "kf01" not in pipeline._valid_reusable_refs(root / "refs.json", root / "prompt_manifest.json", manifest)
        (root / "audio").mkdir()
        (root / "audio" / "vo.mp3").write_bytes(b"voice")
        pipeline.atomic_write_json(root / "words.json", {"duration": 4.0, "words": [{"text": "Beat", "start": 0, "end": 0.2}]})
        # A legacy state flag cannot bless unrelated/transcribed-wrong voice audio.
        assert pipeline._reusable_narration(pipeline.RunContext("x", root), script, {"voice": True}) is None


def test_unmanifested_keyframes_are_not_reused_without_model_provenance() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        jobs = pipeline._keyframe_jobs(_script(_timeline()), root)
        first_path = jobs[0][2]
        first_path.parent.mkdir(parents=True, exist_ok=True)
        first_path.write_bytes(b"unknown-tier-frame")
        assert pipeline._recover_unmanifested_exact_refs(jobs, root / "refs.json", root / "prompt_manifest.json") == {}


def test_two_bundles_and_factory_fail_closed() -> None:
    assert production_bundle("vertex").image_provider == "nano_banana_pro"
    assert production_bundle("flow").video_provider == "flow_agent"
    with pytest.raises(ConfigurationError, match="refusing"):
        production_bundle("vertex", "flow_agent")
    with pytest.raises(ConfigurationError, match="Unknown image provider"):
        get_image_provider("not_a_provider")


def test_nano_banana_pro_retries_only_capacity_errors_without_losing_the_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NANO_BANANA_PRO_MAX_CONCURRENCY", "1")
    monkeypatch.setenv("NANO_BANANA_PRO_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("NANO_BANANA_PRO_429_RETRIES", "1")
    monkeypatch.setenv("NANO_BANANA_PRO_429_BACKOFF_SECONDS", "0.1")
    provider = NanoBananaProProvider(project="test-project", location="us-central1", model="test-model")
    calls = 0

    def generate(_prompt: str, path: Path, _seed: int, _reference: Path | None = None, _model: str | None = None) -> Path:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConfigurationError("429 RESOURCE_EXHAUSTED")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")
        return path

    with TemporaryDirectory() as directory, mock.patch("providers.image.nano_banana_pro.asyncio.sleep", new=mock.AsyncMock()) as sleep:
        provider._generate_sync = generate  # type: ignore[method-assign]
        output = __import__("asyncio").run(provider.generate_keyframe("prompt", Path(directory) / "kf01.png", 1))
        assert output.is_file() and output.read_bytes() == b"image"
    assert calls == 2
    sleep.assert_awaited_once_with(0.1)


def test_nano_banana_pro_times_out_without_submitting_an_unknown_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NANO_BANANA_PRO_REQUEST_TIMEOUT_SECONDS", "15")
    provider = NanoBananaProProvider(project="test-project", location="global", model="gemini-3-pro-image")

    def generate(_prompt: str, _path: Path, _seed: int, _reference: Path | None = None, _model: str | None = None) -> Path:
        time.sleep(0.05)
        return Path("never-written.png")

    provider.request_timeout_seconds = 0.01
    provider._generate_sync = generate  # type: ignore[method-assign]
    with pytest.raises(ProviderError, match="timed out"):
        __import__("asyncio").run(provider.generate_keyframe("prompt", Path("out") / "kf01.png", 1))


def test_vertex_gemini_retries_only_transient_capacity_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERTEX_TEXT_429_RETRIES", "1")
    monkeypatch.setenv("VERTEX_TEXT_429_BACKOFF_SECONDS", "1")
    provider = VertexGeminiProvider(project="test-project", location="global", model="gemini-3.8-flash")
    calls = 0

    def generate(_topic: str, _system_prompt: str, _schema: dict[str, object]) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ProviderError("vertex_gemini script request failed: ClientError") from ConfigurationError("429 RESOURCE_EXHAUSTED")
        return {"beats": []}

    with mock.patch("providers.llm.vertex_gemini.asyncio.sleep", new=mock.AsyncMock()) as sleep:
        provider._generate_sync = generate  # type: ignore[method-assign]
        output = __import__("asyncio").run(provider.generate_script("topic", "system", {"type": "object"}))
    assert output == {"beats": []}
    assert calls == 2
    sleep.assert_awaited_once_with(1.0)


def test_script_repair_uses_configured_budget_and_preserves_targeted_feedback() -> None:
    timeline = _timeline()
    llm = mock.Mock()
    llm.generate_script = mock.AsyncMock(return_value={})
    engine = BeatEngine(llm, lang="en", timeline=timeline)
    candidate = _script(timeline)
    with mock.patch.object(engine, "_assemble", return_value=candidate), \
         mock.patch("services.script_engine.validate_script", side_effect=[["shot 2 exceeds max scale jump"], []]), \
         mock.patch.object(config, "SCRIPT_REPAIR_ATTEMPTS", 2):
        output = __import__("asyncio").run(engine.generate("topic"))
    assert output is candidate
    assert llm.generate_script.await_count == 2
    repair_prompt = llm.generate_script.await_args_list[1].args[1]
    assert "Return the complete corrected JSON object" in repair_prompt
    assert "max scale jump" in repair_prompt


def test_noninteractive_missing_video_emits_only_route_question(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main.sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit) as exc:
        main.main([])
    assert str(exc.value) == main.ROUTE_QUESTION
