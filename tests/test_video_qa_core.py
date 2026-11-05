from __future__ import annotations

from pathlib import Path

import pytest

from engine.services.multimodal_audit import AuditParseError, parse_audit_response
from engine.services.proxy_generator import generate_proxy_hud_ass
from engine.services.surgical_patcher import PatchError, execute_selective_patch


def _clean_payload(block_id: str = "block_01") -> dict:
    return {
        "schema_version": "1",
        "overall_verdict": "PASS",
        "blocks": [
            {
                "block_id": block_id,
                "verdict": "PASS",
                "confidence": 0.96,
                "evidence": [{"timecode": "00:00.000 - 00:02.000", "description": "Observed block"}],
                "defects": [],
            }
        ],
    }


def test_malformed_or_low_confidence_never_passes() -> None:
    with pytest.raises(AuditParseError):
        parse_audit_response('{"schema_version":"1",')
    payload = _clean_payload()
    payload["blocks"][0]["confidence"] = 0.2
    report = parse_audit_response(payload)
    assert report.overall_verdict == "NEEDS_REVIEW"
    assert report.review_required


def test_block_audit_requires_timecoded_evidence() -> None:
    payload = _clean_payload()
    payload["blocks"][0]["evidence"] = []
    with pytest.raises(AuditParseError):
        parse_audit_response(payload)


def test_proxy_hud_contains_only_manifest_identifiers(tmp_path: Path) -> None:
    path = generate_proxy_hud_ass(
        [{"block_id": "block_a", "start": 0, "end": 2}], tmp_path / "hud.ass"
    )
    text = path.read_text(encoding="utf-8")
    assert "BLOCK 01/01 [ID: block_a]" in text
    assert "0:00:00.00-0:00:02.00" in text


def test_patch_loop_dispatches_only_flagged_blocks_and_is_bounded() -> None:
    payload = _clean_payload("block_01")
    payload["blocks"].append({
        "block_id": "block_02", "verdict": "FLAGGED", "confidence": 0.95,
        "evidence": [{"timecode": "00:02.000 - 00:03.000", "description": "Observed issue"}],
        "defects": [{"defect_type": "artifact", "severity": "critical", "description": "Issue",
                      "action": "RE_RENDER_CLIP", "evidence": [{"timecode": "00:02.000 - 00:03.000", "description": "Issue"}]}],
    })
    report = parse_audit_response(payload)
    calls: list[str] = []
    outputs: list[dict[int, str | Path]] = []

    def render(block_id: str, _block: object, _pass: int) -> str:
        calls.append(block_id)
        return f"{block_id}.replacement.mp4"

    def splice(replacements: dict[int, str | Path]) -> Path:
        outputs.append(replacements)
        return Path("patched.mp4")

    result = execute_selective_patch(
        report,
        ["clip_01.mp4", "clip_02.mp4"],
        render,
        splice,
        block_id_for_path=lambda path: Path(path).stem.replace("clip_", "block_"),
    )
    assert result == Path("patched.mp4")
    assert calls == ["block_02"]
    assert outputs == [{1: "block_02.replacement.mp4"}]




def test_video_qa_adapter_injection_accepts_sync_payload() -> None:
    from engine.services.multimodal_audit import audit_with_adapter

    calls: list[Path] = []
    report = audit_with_adapter(
        lambda proxy: (calls.append(Path(proxy)) or _clean_payload()),
        Path("proxy.mp4"),
        expected_block_ids=["block_001"],
    )
    assert report.overall_verdict == "PASS"
    assert calls == [Path("proxy.mp4")]


def test_video_qa_adapter_injection_accepts_async_payload() -> None:
    import asyncio

    async def adapter(_proxy: object) -> dict:
        return _clean_payload()

    assert asyncio.run(adapter(Path("proxy.mp4")))["overall_verdict"] == "PASS"


def test_video_qa_review_required_blocks_assembly(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    import engine.flow_bridge as flow

    monkeypatch.setattr(flow.editor, "render", lambda **kwargs: Path(kwargs["out_path"]).write_bytes(b"proxy"))
    monkeypatch.setattr(flow, "build_audit_proxy", lambda source, proxy, scenes, aspect_ratio: Path(proxy).write_bytes(b"proxy"))
    payload = _clean_payload()
    payload["blocks"][0]["review_required"] = True
    with pytest.raises(RuntimeError, match="blocked final assembly"):
        asyncio.run(flow._run_video_qa_gate(
            out_dir=tmp_path,
            block_paths=[tmp_path / "block_01.mp4"],
            aligned_scenes=[{"audio_t0": 0.0, "audio_t1": 4.0}],
            vo_path=tmp_path / "vo.wav",
            measured_duration=4.0,
            aspect_ratio="16:9",
            dry_run=False,
            video_qa_model="test-model",
            max_patch_passes=1,
            video_qa_adapter=lambda _proxy: payload,
        ))


def test_live_video_qa_provider_failure_fails_closed(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    import engine.flow_bridge as flow

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(flow.editor, "render", lambda **kwargs: Path(kwargs["out_path"]).write_bytes(b"proxy"))
    monkeypatch.setattr(flow, "build_audit_proxy", lambda source, proxy, scenes, aspect_ratio: Path(proxy).write_bytes(b"proxy"))
    def unavailable(*args, **kwargs):
        raise RuntimeError("sampled provider unavailable")
    monkeypatch.setattr(flow, "audit_sampled_frames", unavailable)
    with pytest.raises(RuntimeError, match="sampled provider unavailable"):
        asyncio.run(flow._run_video_qa_gate(
            out_dir=tmp_path,
            block_paths=[tmp_path / "block_01.mp4"],
            aligned_scenes=[{"audio_t0": 0.0, "audio_t1": 4.0}],
            vo_path=tmp_path / "vo.wav",
            measured_duration=4.0,
            aspect_ratio="16:9",
            dry_run=False,
            video_qa_model="test-model",
            max_patch_passes=1,
            video_qa_adapter=None,
        ))


@pytest.mark.parametrize("stage", ["render", "proxy"])
def test_proxy_failure_records_needs_review(tmp_path: Path, monkeypatch, stage: str) -> None:
    import asyncio
    import json
    import engine.flow_bridge as flow

    def fail(*args, **kwargs):
        raise ValueError("fixture failure")

    monkeypatch.setattr(flow.editor, "render", fail if stage == "render" else lambda **kw: Path(kw["out_path"]).write_bytes(b"source"))
    monkeypatch.setattr(flow, "build_audit_proxy", fail)
    with pytest.raises(ValueError, match="fixture failure"):
        asyncio.run(flow._run_video_qa_gate(
            out_dir=tmp_path, block_paths=[tmp_path / "block.mp4"],
            aligned_scenes=[{"audio_t0": 0, "audio_t1": 1}], vo_path=tmp_path / "voice.wav",
            measured_duration=1, aspect_ratio="16:9", dry_run=False,
            video_qa_model="test", max_patch_passes=0, video_qa_adapter=lambda _: {},
        ))
    report = json.loads((tmp_path / "video_qa_report.json").read_text(encoding="utf-8"))
    assert report["overall_verdict"] == "NEEDS_REVIEW"
    assert report["error_type"] == "ValueError"


def test_video_qa_clean_pass_allows_assembly(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    import engine.flow_bridge as flow

    monkeypatch.setattr(flow.editor, "render", lambda **kwargs: Path(kwargs["out_path"]).write_bytes(b"proxy"))
    monkeypatch.setattr(flow, "build_audit_proxy", lambda source, proxy, scenes, aspect_ratio: Path(proxy).write_bytes(b"proxy"))
    payload = _clean_payload()
    asyncio.run(flow._run_video_qa_gate(
        out_dir=tmp_path,
        block_paths=[tmp_path / "block_01.mp4"],
        aligned_scenes=[{"audio_t0": 0.0, "audio_t1": 4.0}],
        vo_path=tmp_path / "vo.wav",
        measured_duration=4.0,
        aspect_ratio="16:9",
        dry_run=False,
        video_qa_model="test-model",
        max_patch_passes=1,
        video_qa_adapter=lambda _proxy: payload,
    ))
    report = (tmp_path / "video_qa_report.json").read_text(encoding="utf-8")
    assert '"overall_verdict": "PASS"' in report
    assert '"patch_status": "not_needed"' in report


def test_video_qa_preserves_sample_manifest(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    import json
    import engine.flow_bridge as flow

    monkeypatch.setattr(flow.editor, "render", lambda **kw: Path(kw["out_path"]).write_bytes(b"source"))
    monkeypatch.setattr(flow, "build_audit_proxy", lambda source, proxy, scenes, aspect_ratio: Path(proxy).write_bytes(b"proxy"))
    payload = _clean_payload("block_01")
    payload["sample_manifest"] = [{"image": 1, "block_id": "block_01", "time_seconds": 0.25}]
    payload["batches"] = [{"batch": 1, "block_ids": ["block_01"], "image_count": 3}]
    payload["max_images_per_request"] = 12
    asyncio.run(flow._run_video_qa_gate(
        out_dir=tmp_path, block_paths=[tmp_path / "block.mp4"],
        aligned_scenes=[{"audio_t0": 0, "audio_t1": 1}], vo_path=tmp_path / "voice.wav",
        measured_duration=1, aspect_ratio="16:9", dry_run=False,
        video_qa_model="test", max_patch_passes=0, video_qa_adapter=lambda _: payload,
    ))
    report = json.loads((tmp_path / "video_qa_report.json").read_text(encoding="utf-8"))
    assert report["sample_manifest"] == payload["sample_manifest"]
    assert report["batch_metadata"] == {"batches": payload["batches"], "max_images_per_request": 12}


def test_patch_budget_rejects_persistent_defect() -> None:
    report = parse_audit_response({
        "schema_version": "1", "overall_verdict": "FLAGGED", "blocks": [{
            "block_id": "block_001", "verdict": "FLAGGED", "confidence": 0.9,
            "evidence": [{"timecode": "00:00.000 - 00:01.000", "description": "Issue"}],
            "defects": [{"defect_type": "artifact", "severity": "critical", "description": "Issue",
                          "action": "RE_RENDER_CLIP", "evidence": [{"timecode": "00:00.000 - 00:01.000", "description": "Issue"}]}],
        }],
    })
    with pytest.raises(PatchError):
        execute_selective_patch(
            report,
            ["block_001.mp4"],
            lambda *_: "replacement.mp4",
            lambda _: Path("patched.mp4"),
            max_passes=0,
        )


def _two_block_audit(flag_second: bool) -> dict:
    payload = _clean_payload("block_01")
    second = _clean_payload("block_02")["blocks"][0]
    if flag_second:
        second.update({
            "verdict": "FLAGGED",
            "defects": [{
                "defect_type": "artifact", "severity": "critical", "description": "Issue",
                "action": "RE_RENDER_CLIP",
                "evidence": [{"timecode": "00:02.000 - 00:03.000", "description": "Issue"}],
            }],
        })
        payload["overall_verdict"] = "FLAGGED"
    payload["blocks"].append(second)
    return payload


@pytest.mark.parametrize("persistent,validation_pass", [(False, True), (True, True), (False, False)])
def test_video_qa_patches_only_flagged_block_and_reaudits_once(tmp_path: Path, monkeypatch, persistent: bool, validation_pass: bool) -> None:
    import asyncio
    import json
    import engine.flow_bridge as flow

    blocks = [tmp_path / "block_01.mp4", tmp_path / "block_02.mp4"]
    originals = list(blocks)
    for block in blocks:
        block.write_bytes(b"original")
    vo = tmp_path / "vo.wav"
    vo.write_bytes(b"audio")
    monkeypatch.setattr(flow.editor, "render", lambda **kwargs: Path(kwargs["out_path"]).write_bytes(b"master"))
    monkeypatch.setattr(flow, "build_audit_proxy", lambda source, proxy, scenes, aspect_ratio: Path(proxy).write_bytes(Path(source).read_bytes()))
    splice_calls = []

    def splice(master, replacements, all_blocks, output, **kwargs):
        splice_calls.append((Path(master), dict(replacements), list(all_blocks)))
        Path(output).write_bytes(b"patched")
        return Path(output)

    monkeypatch.setattr(flow, "surgically_splice_timeline", splice)
    render_calls = []

    async def render_block(index: int, output_path: Path) -> Path:
        await asyncio.sleep(0)
        render_calls.append(index)
        output_path.write_bytes(b"replacement")
        return output_path

    audit_sources = []

    async def audit(proxy: Path) -> dict:
        await asyncio.sleep(0)
        audit_sources.append(Path(proxy).read_bytes())
        return _two_block_audit(flag_second=len(audit_sources) == 1 or persistent)

    async def run_gate():
        return await flow._run_video_qa_gate(
            out_dir=tmp_path, block_paths=blocks,
            aligned_scenes=[{"audio_t0": 0.0, "audio_t1": 2.0}, {"audio_t0": 2.0, "audio_t1": 4.0}],
            vo_path=vo, measured_duration=4.0, aspect_ratio="16:9", dry_run=False,
            video_qa_model="test-model", max_patch_passes=1, video_qa_adapter=audit,
            render_block=render_block, validate_patch=lambda *_: {"passed": validation_pass},
        )

    if persistent or not validation_pass:
        with pytest.raises(RuntimeError, match="blocked final assembly"):
            asyncio.run(run_gate())
    else:
        asyncio.run(run_gate())
    assert render_calls == [1]
    assert len(splice_calls) == 1
    assert set(splice_calls[0][1]) == {1}
    assert splice_calls[0][2] == originals
    if not persistent and validation_pass:
        assert blocks[0] == originals[0]
        assert blocks[1] == splice_calls[0][1][1]
    else:
        assert blocks == originals
    assert audit_sources == [b"master", b"patched"]
    report = json.loads((tmp_path / "video_qa_report.json").read_text(encoding="utf-8"))
    assert report["overall_verdict"] == ("NEEDS_REVIEW" if persistent or not validation_pass else "PASS")


def test_video_qa_zero_patch_budget_blocks_without_render(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    import engine.flow_bridge as flow

    monkeypatch.setattr(flow.editor, "render", lambda **kwargs: Path(kwargs["out_path"]).write_bytes(b"master"))
    monkeypatch.setattr(flow, "build_audit_proxy", lambda source, proxy, scenes, aspect_ratio: Path(proxy).write_bytes(b"proxy"))
    calls = []

    async def render_block(index: int, output_path: Path) -> Path:
        calls.append(index)
        return output_path

    with pytest.raises(RuntimeError, match="blocked final assembly"):
        asyncio.run(flow._run_video_qa_gate(
            out_dir=tmp_path, block_paths=[tmp_path / "block_01.mp4", tmp_path / "block_02.mp4"],
            aligned_scenes=[{"audio_t0": 0.0, "audio_t1": 2.0}, {"audio_t0": 2.0, "audio_t1": 4.0}],
            vo_path=tmp_path / "vo.wav", measured_duration=4.0, aspect_ratio="16:9", dry_run=False,
            video_qa_model="test-model", max_patch_passes=0, video_qa_adapter=lambda _: _two_block_audit(True),
            render_block=render_block,
        ))
    assert calls == []


def test_patched_av_timeline_rejects_drift(tmp_path: Path) -> None:
    from engine.services.surgical_patcher import validate_av_timeline
    streams = [{"codec_type": "video", "start_time": "0", "duration": "4"},
               {"codec_type": "audio", "start_time": "0", "duration": "4"}]
    assert validate_av_timeline(tmp_path / "candidate", probe=lambda _: {"streams": streams})["audio_duration"] == 4
    streams[1]["start_time"] = "0.5"
    with pytest.raises(PatchError, match="timings differ"):
        validate_av_timeline(tmp_path / "candidate", probe=lambda _: {"streams": streams})


@pytest.mark.parametrize("duration,passes", [(4.0, True), (3.0, False)])
def test_final_timeline_qa_updates_report(tmp_path, monkeypatch, duration, passes):
    import json
    import engine.flow_bridge as flow
    report = tmp_path / "video_qa_report.json"
    report.write_text(json.dumps({"overall_verdict": "PASS", "review_required": False}), encoding="utf-8")
    monkeypatch.setattr(flow, "validate_av_timeline", lambda _: {
        "video_start": 0.0, "audio_start": 0.0,
        "video_duration": duration, "audio_duration": duration,
    })
    if passes:
        flow._verify_final_qa_timeline(tmp_path / "final.mp4", 4.0, report)
    else:
        with pytest.raises(RuntimeError, match="Final timeline QA failed"):
            flow._verify_final_qa_timeline(tmp_path / "final.mp4", 4.0, report)
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["final_timeline"]["status"] == ("PASS" if passes else "NEEDS_REVIEW")
    assert result["overall_verdict"] == ("PASS" if passes else "NEEDS_REVIEW")


def test_final_timeline_with_pyav_and_real_media(tmp_path, monkeypatch):
    import json
    import subprocess
    import imageio_ffmpeg
    import engine.flow_bridge as flow
    import services.surgical_patcher as patcher
    pytest.importorskip("av")
    source = tmp_path / "final.mp4"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error",
                    "-f", "lavfi", "-i", "color=black:s=64x64:r=30:d=2",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                    "-t", "2", "-c:v", "libx264", "-c:a", "aac", str(source)], check=True)
    monkeypatch.setattr(patcher, "find_ffprobe", lambda: None)
    report = tmp_path / "video_qa_report.json"
    report.write_text(json.dumps({"overall_verdict": "PASS", "review_required": False}), encoding="utf-8")
    flow._verify_final_qa_timeline(source, 2.0, report)
    assert json.loads(report.read_text(encoding="utf-8"))["final_timeline"]["status"] == "PASS"

@pytest.mark.parametrize("detected", [False, True])
def test_simulated_defect_requires_actual_audit_detection(tmp_path: Path, monkeypatch, detected: bool) -> None:
    import asyncio
    import json
    import engine.flow_bridge as flow

    blocks = [tmp_path / "block_01.mp4", tmp_path / "block_02.simulated-defect.mp4"]
    monkeypatch.setattr(flow.editor, "render", lambda **kw: Path(kw["out_path"]).write_bytes(b"master"))
    monkeypatch.setattr(flow, "build_audit_proxy", lambda source, proxy, scenes, aspect_ratio: Path(proxy).write_bytes(b"proxy"))
    monkeypatch.setattr(flow, "surgically_splice_timeline", lambda master, replacements, paths, output, **kw: Path(output))
    audit_calls, render_calls = [], []

    async def audit(_path):
        audit_calls.append(True)
        return _two_block_audit(detected and len(audit_calls) == 1)

    async def render(index, path):
        render_calls.append(index)
        return path

    async def run():
        await flow._run_video_qa_gate(
            out_dir=tmp_path, block_paths=blocks,
            aligned_scenes=[{"audio_t0": 0, "audio_t1": 2}, {"audio_t0": 2, "audio_t1": 4}],
            vo_path=tmp_path / "vo.wav", measured_duration=4, aspect_ratio="16:9", dry_run=False,
            video_qa_model="test", max_patch_passes=1, video_qa_adapter=audit, render_block=render,
            validate_patch=lambda *_: {"passed": True},
            simulated_defect={"block_id": "block_02", "kind": "simulated_blackout"},
        )

    if detected:
        asyncio.run(run())
    else:
        with pytest.raises(RuntimeError, match="NEEDS_REVIEW"):
            asyncio.run(run())
    report = json.loads((tmp_path / "video_qa_report.json").read_text(encoding="utf-8"))
    assert report["simulation_detected_by_video_qa"] is detected
    assert report["initial_audit"]["overall_verdict"] == ("FLAGGED" if detected else "PASS")
    assert render_calls == ([1] if detected else [])
    assert len(audit_calls) == (2 if detected else 1)


def test_simulated_blackout_creates_separate_media_with_matching_signature(tmp_path: Path) -> None:
    import shutil
    import subprocess
    import cv2
    import imageio_ffmpeg
    import engine.flow_bridge as flow
    from engine.services.surgical_patcher import media_signature

    from engine.services.media_tools import find_ffprobe
    if not find_ffprobe():
        pytest.skip("ffprobe is required")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    original, defect = tmp_path / "flow.mp4", tmp_path / "defect.mp4"
    subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "color=red:s=64x64:r=30:d=2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(original)], check=True)
    original_hash = flow.file_fingerprint(original)
    record = flow._simulate_block_blackout(original, defect)
    assert flow.file_fingerprint(original) == original_hash == record["source_sha256"]
    assert record["test_sha256"] != original_hash
    assert media_signature(original) == media_signature(defect)
    cap = cv2.VideoCapture(str(defect))
    cap.set(cv2.CAP_PROP_POS_MSEC, 1000)
    ok, frame = cap.read()
    cap.release()
    assert ok and frame.mean() < 5


def test_simulated_defect_with_extra_flag_does_not_render(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    import json
    import engine.flow_bridge as flow

    monkeypatch.setattr(flow.editor, "render", lambda **kw: Path(kw["out_path"]).write_bytes(b"master"))
    monkeypatch.setattr(flow, "build_audit_proxy", lambda source, proxy, scenes, aspect_ratio: Path(proxy).write_bytes(b"proxy"))
    payload = _two_block_audit(True)
    payload["blocks"][0] = dict(payload["blocks"][1], block_id="block_01")
    calls = []
    async def render(index, path):
        calls.append(index)
        return path
    with pytest.raises(RuntimeError, match="NEEDS_REVIEW"):
        asyncio.run(flow._run_video_qa_gate(
            out_dir=tmp_path, block_paths=[tmp_path / "block_01.mp4", tmp_path / "block_02.mp4"],
            aligned_scenes=[{"audio_t0": 0, "audio_t1": 2}, {"audio_t0": 2, "audio_t1": 4}],
            vo_path=tmp_path / "vo.wav", measured_duration=4, aspect_ratio="16:9", dry_run=False,
            video_qa_model="test", max_patch_passes=1, video_qa_adapter=lambda _: payload,
            render_block=render, simulated_defect={"block_id": "block_02"},
        ))
    assert calls == []
    report = json.loads((tmp_path / "video_qa_report.json").read_text(encoding="utf-8"))
    assert report["simulation_detected_by_video_qa"] is True
    assert "additional blocks" in report["patch_message"]


def test_patch_rejects_unmapped_audit_id_before_render() -> None:
    report = parse_audit_response(_two_block_audit(True))
    calls = []
    with pytest.raises(PatchError, match="map uniquely"):
        execute_selective_patch(report, ["block_01.mp4"], lambda *args: calls.append(args),
                                lambda _: Path("patched.mp4"))
    assert calls == []


def test_splice_never_overwrites_master_or_blocks(tmp_path: Path) -> None:
    from engine.services.surgical_patcher import surgically_splice_timeline
    master, block, replacement = (tmp_path / name for name in ("master.mp4", "block.mp4", "replacement.mp4"))
    for path in (master, block, replacement):
        path.write_bytes(b"original")
    for output in (master, block, replacement):
        with pytest.raises(PatchError, match="must not overwrite"):
            surgically_splice_timeline(master, {0: replacement}, [block], output)
        assert output.read_bytes() == b"original"
