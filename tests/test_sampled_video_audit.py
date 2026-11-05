import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
import pytest

from services.multimodal_audit import AuditParseError
from services.sampled_video_audit import audit_sampled_frames


def test_vision_refuses_missing_image_before_transport(tmp_path, monkeypatch):
    from providers import gemini_webapi
    monkeypatch.setattr(gemini_webapi, "_post_with_retry", lambda *a, **k: pytest.fail("missing frame was submitted"))
    with pytest.raises(FileNotFoundError):
        gemini_webapi.call_gemini_vision("audit", [tmp_path / "missing.jpg"])


@pytest.fixture
def proxy(tmp_path: Path) -> Path:
    path = tmp_path / "proxy.mp4"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=96x64:rate=10:duration=4", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def test_sampled_audit_sends_actual_frames_and_manifest(proxy):
    scenes = [{"block_id": "block_01", "start": 0, "end": 2},
              {"block_id": "block_02", "start": 2, "end": 4}]
    called = []
    def invoke(prompt, paths, *, model, timeout):
        assert model == "model-test"
        assert len(paths) == 6
        assert all(path.read_bytes().startswith(b"\xff\xd8") for path in paths)
        assert '"time_seconds": 0.5' in prompt and '"time_seconds": 3.5' in prompt
        called.extend(paths)
        return json.dumps({"schema_version": "1", "overall_verdict": "PASS", "blocks": [
            {"block_id": x["block_id"], "verdict": "PASS", "confidence": 0.95,
             "evidence": [{"timecode": ("00:00.500 - 00:00.500" if x["block_id"] == "block_01" else "00:02.500 - 00:02.500"), "description": "visible frame"}],
             "defects": []} for x in scenes]})
    response = audit_sampled_frames(proxy, scenes, model="model-test", invoke=invoke)
    assert response["overall_verdict"] == "PASS"
    assert response["audit_scope"] == "sampled_frames_only"
    assert [x["time_seconds"] for x in response["sample_manifest"]] == [0.5, 1.0, 1.5, 2.5, 3.0, 3.5]
    assert all(not path.exists() for path in called)


def test_sampled_audit_rejects_incomplete_provider_coverage(proxy):
    def invoke(*args, **kwargs):
        return json.dumps({"schema_version": "1", "overall_verdict": "PASS", "blocks": [{
            "block_id": "block_01", "verdict": "PASS", "confidence": 0.9,
            "evidence": [{"timecode": "00:00.500 - 00:01.500", "description": "visible"}], "defects": []}]})
    with pytest.raises(AuditParseError, match="cover every"):
        audit_sampled_frames(proxy, [{"block_id": "block_01", "start": 0, "end": 2},
                                    {"block_id": "block_02", "start": 2, "end": 4}],
                             model="model-test", invoke=invoke)


def test_sampled_audit_rejects_evidence_outside_sampled_block(proxy):
    def invoke(*args, **kwargs):
        return json.dumps({"schema_version": "1", "overall_verdict": "PASS", "blocks": [
            {"block_id": "block_01", "verdict": "PASS", "confidence": 0.9,
             "evidence": [{"timecode": "00:02.000 - 00:02.500", "description": "unseen"}], "defects": []}]})
    with pytest.raises(ValueError, match="does not match sampled frames"):
        audit_sampled_frames(proxy, [{"block_id": "block_01", "start": 0, "end": 2}],
                             model="model-test", invoke=invoke)


def test_sampled_audit_rejects_unobserved_interval(proxy):
    def invoke(*args, **kwargs):
        return json.dumps({"schema_version": "1", "overall_verdict": "PASS", "blocks": [
            {"block_id": "block_01", "verdict": "PASS", "confidence": 0.9,
             "evidence": [{"timecode": "00:00.500 - 00:01.500", "description": "unseen interval"}],
             "defects": []}]})
    with pytest.raises(ValueError, match="does not match sampled frames"):
        audit_sampled_frames(proxy, [{"block_id": "block_01", "start": 0, "end": 2}],
                             model="model-test", invoke=invoke)


def test_sampled_audit_batches_complete_blocks_and_merges_verdicts(proxy):
    scenes = [{"block_id": f"block_{i:02d}", "start": i - 1, "end": i} for i in range(1, 5)]
    calls = []
    def invoke(prompt, paths, **kwargs):
        manifest = json.loads(prompt.split("Sampled image manifest: ", 1)[1])
        assert len(paths) <= 6
        assert [item["image"] for item in manifest] == list(range(1, len(paths) + 1))
        calls.append(manifest)
        rows = []
        for block in dict.fromkeys(item["block_id"] for item in manifest):
            seconds = next(item["time_seconds"] for item in manifest if item["block_id"] == block)
            timestamp = f"00:{seconds:06.3f}"
            rows.append({"block_id": block, "verdict": "PASS", "confidence": .95,
                         "evidence": [{"timecode": f"{timestamp} - {timestamp}", "description": "visible"}],
                         "defects": []})
        return json.dumps({"schema_version": "1", "overall_verdict": "PASS", "blocks": rows})
    result = audit_sampled_frames(proxy, scenes, model="test", invoke=invoke, max_images_per_request=6)
    assert len(calls) == 2
    assert len(result["blocks"]) == 4 and len(result["sample_manifest"]) == 12
    assert [batch["image_count"] for batch in result["batches"]] == [6, 6]
    assert result["overall_verdict"] == "PASS"


def test_sampled_audit_batch_limits_fail_before_provider_request(proxy):
    calls = []
    scenes = [{"block_id": f"block_{i}", "start": i - 1, "end": i} for i in range(1, 5)]
    with pytest.raises(ValueError, match="more requests"):
        audit_sampled_frames(proxy, scenes, model="test", invoke=lambda *a, **k: calls.append(1),
                             max_images_per_request=3, max_requests=2)
    assert not calls


def test_sampled_audit_batch_uncertainty_cannot_become_pass(proxy):
    scenes = [{"block_id": f"block_{i}", "start": i - 1, "end": i} for i in range(1, 3)]
    def invoke(prompt, paths, **kwargs):
        manifest = json.loads(prompt.split("Sampled image manifest: ", 1)[1])
        seconds = manifest[0]["time_seconds"]
        timestamp = f"00:{seconds:06.3f}"
        row = {"block_id": manifest[0]["block_id"], "verdict": "PASS", "confidence": .5,
               "evidence": [{"timecode": f"{timestamp} - {timestamp}", "description": "uncertain"}], "defects": []}
        return json.dumps({"schema_version": "1", "overall_verdict": "PASS", "blocks": [row]})
    result = audit_sampled_frames(proxy, scenes, model="test", invoke=invoke, max_images_per_request=3)
    assert result["overall_verdict"] == "NEEDS_REVIEW"


def test_sampled_audit_rejects_incomplete_later_batch(proxy):
    scenes = [{"block_id": f"block_{i}", "start": i - 1, "end": i} for i in range(1, 4)]
    calls = []
    def invoke(prompt, paths, **kwargs):
        manifest = json.loads(prompt.split("Sampled image manifest: ", 1)[1])
        calls.append(manifest)
        seconds = manifest[0]["time_seconds"]
        timestamp = f"00:{seconds:06.3f}"
        row = {"block_id": manifest[0]["block_id"], "verdict": "PASS", "confidence": .9,
               "evidence": [{"timecode": f"{timestamp} - {timestamp}", "description": "visible"}], "defects": []}
        if len(calls) == 2:
            row["block_id"] = "block_1"
        return json.dumps({"schema_version": "1", "overall_verdict": "PASS", "blocks": [row]})
    with pytest.raises(AuditParseError, match="Unexpected block_id"):
        audit_sampled_frames(proxy, scenes, model="test", invoke=invoke, max_images_per_request=3)
    assert len(calls) == 2


def test_batch_level_uncertainty_survives_flagged_other_batch(proxy):
    from services.multimodal_audit import parse_audit_response
    scenes = [{"block_id": f"block_{i}", "start": i - 1, "end": i} for i in range(1, 3)]
    def invoke(prompt, paths, **kwargs):
        entry = json.loads(prompt.split("Sampled image manifest: ", 1)[1])[0]
        timestamp = f"00:{entry['time_seconds']:06.3f}"
        evidence = [{"timecode": f"{timestamp} - {timestamp}", "description": "visible"}]
        is_second = entry["block_id"] == "block_2"
        row = {"block_id": entry["block_id"], "verdict": "FLAGGED" if is_second else "PASS",
               "confidence": .9, "evidence": evidence, "defects": []}
        if is_second:
            row["defects"] = [{"defect_type": "artifact", "severity": "moderate", "description": "visible",
                               "action": "RE_RENDER_CLIP", "evidence": evidence}]
        return json.dumps({"schema_version": "1", "overall_verdict": "FLAGGED" if is_second else "NEEDS_REVIEW", "blocks": [row]})
    result = audit_sampled_frames(proxy, scenes, model="test", invoke=invoke, max_images_per_request=3)
    assert result["overall_verdict"] == "NEEDS_REVIEW"
    assert parse_audit_response(result).overall_verdict == "NEEDS_REVIEW"
