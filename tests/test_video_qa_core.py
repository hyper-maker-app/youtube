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


def test_live_video_qa_without_adapter_or_key_fails_closed(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    import engine.flow_bridge as flow

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="requires an injected adapter or GEMINI_API_KEY"):
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
