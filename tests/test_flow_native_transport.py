import asyncio
import hashlib
import json
from pathlib import Path
import pytest

from engine.services.flow_native_evidence import submitted_media, validate_text_submission
from engine.providers.flow_browser.native_transport import BrowserNativeFlowTransport, resume_invocation


def test_reference_requires_explicit_fallback(tmp_path, monkeypatch):
    transport = BrowserNativeFlowTransport()
    image = tmp_path / "hero.jpg"
    image.write_bytes(b"reference")
    calls = []

    async def fake_generate(request, out_path, **kwargs):
        calls.append((request, kwargs))
        return out_path

    monkeypatch.setattr(transport, "generate", fake_generate)
    with pytest.raises(Exception, match="explicit allow_text_fallback"):
        asyncio.run(transport.generate_asset(prompt="scene", out_path=tmp_path / "out.mp4", reference_images=[image]))
    assert not calls
    asyncio.run(transport.generate_asset(prompt="scene", out_path=tmp_path / "out.mp4", reference_images=[image], allow_text_fallback=True))
    request, options = calls[0]
    evidence = options["conditioning_evidence"]
    assert request.conditioning == "text_to_video"
    assert evidence["requested_conditioning"] == "reference_images"
    assert evidence["reference_upload_observed"] is False
    assert evidence["local_reference_sha256"] == [hashlib.sha256(b"reference").hexdigest()]


def test_first_frame_conditioning_allowed_without_fallback(tmp_path, monkeypatch):
    transport = BrowserNativeFlowTransport()
    image = tmp_path / "hero.jpg"
    image.write_bytes(b"reference")
    calls = []

    async def fake_generate(request, out_path, **kwargs):
        calls.append((request, kwargs))
        return out_path

    monkeypatch.setattr(transport, "generate", fake_generate)
    # start_frame should succeed without allow_text_fallback
    asyncio.run(transport.generate_asset(prompt="scene", out_path=tmp_path / "out.mp4", start_frame=image, allow_text_fallback=False))
    assert len(calls) == 1
    request, options = calls[0]
    evidence = options["conditioning_evidence"]
    assert request.conditioning == "first_frame"
    assert request.start_image_sha256 == hashlib.sha256(b"reference").hexdigest()
    assert "[First Frame Anchor: hero.jpg] scene" in request.prompt
    assert evidence["requested_conditioning"] == "first_frame"
    assert evidence["submitted_conditioning"] == "first_frame"
    assert evidence["reference_upload_observed"] is True
    assert evidence["local_frame_sha256"] == [hashlib.sha256(b"reference").hexdigest()]


def test_submitted_media_resilience():
    # 1. Classic YhhmEf format
    assert submitted_media([None, None, [["media_classic_01"]]]) == "media_classic_01"

    # 2. Nested list format
    assert submitted_media([None, [["media_nested_02"]]]) == "media_nested_02"

    # 3. Element row format
    assert submitted_media([None, ["media_row_03", "extra"]]) == "media_row_03"

    # 4. Dict format
    assert submitted_media({"mediaId": "media_dict_04"}) == "media_dict_04"
    assert submitted_media({"id": "media_dict_05"}) == "media_dict_05"

    # 5. CAE asset row format
    assert submitted_media([["cid", "pid", "media_cae_06", "CAE", "x", "y"]]) == "media_cae_06"

    # 6. Fallback structured data
    assert "fallback" in submitted_media({"other_key": "fallback"})


def test_validate_text_submission_variations():
    # YhhmEf 360p
    arg_360 = [[[ [[None, None, [[["You look into the dark hallway."]]]]], "abra_t2v_8s_360p", 2, 1 ]]]
    res_360 = validate_text_submission("YhhmEf", arg_360, "You look into the dark hallway.")
    assert res_360["quality"] == "360p"
    assert res_360["aspect_ratio"] == "9:16"
    assert res_360["internal_model_key"] == "abra_t2v_8s_360p"

    # YhhmEf 720p 16:9
    arg_720 = [[[ [[None, None, [[["You run toward the bunker."]]]]], "abra_t2v_8s_720p", 1, 1 ]]]
    res_720 = validate_text_submission("YhhmEf", arg_720, "You run toward the bunker.")
    assert res_720["quality"] == "720p"
    assert res_720["aspect_ratio"] == "16:9"
    assert res_720["internal_model_key"] == "abra_t2v_8s_720p"

    # WuwhI RPC
    arg_wuwhi = [[[ [[None, None, [[["You hold your breath."]]]]], "wuwhi_model", 2, 1 ]]]
    res_wuwhi = validate_text_submission("WuwhI", arg_wuwhi, "You hold your breath.")
    assert res_wuwhi["rpc_id"] == "WuwhI"


def test_resume_ready_returns_path_without_browser(tmp_path):
    video_file = tmp_path / "block_01.mp4"
    video_file.write_bytes(b"dummy_video_bytes")

    state_dir = tmp_path / "block_01.flow-state"
    state_dir.mkdir()
    state_file = state_dir / "invocation.json"
    state = {
        "status": "ready",
        "evidence_complete": True,
        "output": "block_01.mp4",
        "request": {
            "prompt": "Test prompt",
            "model": "gemini_omni_flash_1_1",
            "quality": "720p",
            "aspect_ratio": "9:16",
            "duration": 8,
        },
    }
    state_file.write_text(json.dumps(state), encoding="utf-8")

    transport = BrowserNativeFlowTransport()
    res = asyncio.run(transport.resume(state_file))
    assert res == video_file


def test_resume_downloaded_unverified_heals_when_project_verified(tmp_path, monkeypatch):
    video_file = tmp_path / "block_02.mp4"
    video_file.write_bytes(b"dummy_video_data_12345")

    state_dir = tmp_path / "block_02.flow-state"
    state_dir.mkdir()
    state_file = state_dir / "invocation.json"
    project_state_file = state_dir / "project_state.json"

    # Project is verified
    project_state = {"verified": True, "project_id": "test_proj_123"}
    project_state_file.write_text(json.dumps(project_state), encoding="utf-8")

    # Initial state with unverified download (like in live live oxygen-patch run)
    state = {
        "status": "downloaded_unverified",
        "evidence_complete": False,
        "output": "block_02.mp4",
        "provider_response": {"origin": "provider_response", "media_sha256": None},
        "request": {
            "prompt": "You search for oxygen tanks in the dark.",
            "model": "gemini_omni_flash_1_1",
            "quality": "720p",
            "aspect_ratio": "9:16",
            "duration": 8,
        },
    }
    state_file.write_text(json.dumps(state), encoding="utf-8")

    # Mock probe to return valid 720x1280 geometry and 8s duration
    mock_probe = {
        "streams": [{"codec_type": "video", "width": 720, "height": 1280, "duration": "8.0"}],
        "format": {"duration": "8.0"},
    }
    import engine.providers.flow_browser.native_transport as nt
    monkeypatch.setattr(nt, "_probe_download", lambda _: mock_probe)

    transport = BrowserNativeFlowTransport()
    # Test both resume and resume_invocation alias
    res = asyncio.run(resume_invocation(state_file, transport))
    assert res == video_file

    # Check that invocation state has been healed
    updated_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert updated_state["status"] == "ready"
    assert updated_state["evidence_complete"] is True
    assert updated_state["provider_response"]["origin"] == "browser_verified_download"
    expected_sha = hashlib.sha256(b"dummy_video_data_12345").hexdigest()
    assert updated_state["provider_response"]["media_sha256"] == expected_sha
