import hashlib
import json
from pathlib import Path
import pytest

import sys
_ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

from providers.base import ConfigurationError
from providers.flow_contract import (
    resolve_flow_video_model,
    resolve_flow_image_model,
    get_supported_video_models,
    get_supported_image_models,
    default_capabilities,
    fixture_settings,
    settings,
    mapping,
)
from providers.flow_browser.native_transport import BrowserFlowRequest
from flow_bridge import synthesize_hero_frame, generate_nano_banana_hero_frame


def test_resolve_flow_video_model():
    # Real mode always returns gemini_omni_flash_1_2
    assert resolve_flow_video_model("real") == "gemini_omni_flash_1_2"

    # Test mode before 2026-12-05 returns gemini_omni_flash_1_1
    assert resolve_flow_video_model("test", reference_date="2026-11-01") == "gemini_omni_flash_1_1"
    assert resolve_flow_video_model("test", reference_date="2026-12-04") == "gemini_omni_flash_1_1"

    # Test mode on or after 2026-12-05 returns veo_3_1_lite
    assert resolve_flow_video_model("test", reference_date="2026-12-05") == "veo_3_1_lite"
    assert resolve_flow_video_model("test", reference_date="2027-01-01") == "veo_3_1_lite"


def test_resolve_flow_image_model():
    assert resolve_flow_image_model() == "nano_banana_2_1"


def test_flow_models_json_structure():
    m = mapping()
    # Check video models
    assert "video_models" in m
    v_models = m["video_models"]
    assert "gemini_omni_flash_1_1" in v_models
    assert "gemini_omni_flash_1_2" in v_models
    assert "veo_3_1_lite" in v_models

    # Verify gemini_omni_flash_1_1 retirement
    assert v_models["gemini_omni_flash_1_1"].get("retired_after") == "2026-12-05"

    # Verify gemini_omni_flash_1_2 flagship attributes
    omni_12 = v_models["gemini_omni_flash_1_2"]
    assert omni_12["alias"] == "gemini_omni_flash_1_2"
    assert omni_12["supports_first_frame"] is True
    assert omni_12["supports_first_and_last_frame"] is True
    assert 4 in omni_12["supported_native_durations"]
    assert 6 in omni_12["supported_native_durations"]
    assert 8 in omni_12["supported_native_durations"]
    assert 10 in omni_12["supported_native_durations"]
    assert "720p" in omni_12["supported_qualities"]

    # Verify veo_3_1_lite attributes
    veo_lite = v_models["veo_3_1_lite"]
    assert veo_lite["alias"] == "veo_3_1_lite"
    assert veo_lite.get("credits") == 10
    assert "360p" in veo_lite["supported_qualities"]
    assert "720p" in veo_lite["supported_qualities"]

    # Verify nano_banana_2_1 image model
    assert "image_models" in m
    img_models = m["image_models"]
    assert "nano_banana_2_1" in img_models
    nb21 = img_models["nano_banana_2_1"]
    assert nb21["alias"] == "nano_banana_2_1"
    assert nb21.get("credits") == 0
    assert nb21.get("free") is True
    assert "Nano Banana 2.1" in nb21["display_name"]


def test_browser_flow_request_conditioning_first_frame():
    # first_frame conditioning should be allowed
    req = BrowserFlowRequest(
        prompt="A survivor barricades the metal door.",
        model="gemini_omni_flash_1_2",
        quality="720p",
        duration=8,
        conditioning="first_frame",
        start_image_sha256="abcd1234abcd1234abcd1234abcd1234",
        execution_mode="real",
    )
    # validate should not raise ConfigurationError
    req.validate()
    assert req.conditioning == "first_frame"
    assert req.start_image_sha256 == "abcd1234abcd1234abcd1234abcd1234"


def test_browser_flow_request_rejects_unsupported_conditioning():
    # End frame or references without first_frame should raise
    req = BrowserFlowRequest(
        prompt="A survivor barricades the metal door.",
        model="gemini_omni_flash_1_2",
        quality="720p",
        duration=8,
        conditioning="first_last_frames",
        end_image_sha256="abcd1234abcd1234abcd1234abcd1234",
    )
    with pytest.raises(ConfigurationError, match="supports text-to-video and first_frame"):
        req.validate()


def test_browser_flow_request_supports_all_approved_models():
    for model_alias in ("gemini_omni_flash_1_1", "gemini_omni_flash_1_2", "veo_3_1_lite"):
        req = BrowserFlowRequest(
            prompt="Dramatic catastrophe scene",
            model=model_alias,
            quality="720p",
            duration=8,
            conditioning="text_to_video",
        )
        req.validate()

    with pytest.raises(ConfigurationError, match="Unsupported Flow model alias"):
        BrowserFlowRequest(
            prompt="Dramatic catastrophe scene",
            model="unknown_fantasy_model",
            quality="720p",
            duration=8,
        ).validate()


def test_fixture_settings_dynamic_modes():
    # Real mode
    real_cfg = fixture_settings(test=False)
    assert real_cfg["video_model"] == "gemini_omni_flash_1_2"
    assert real_cfg["image_model"] == "nano_banana_2_1"
    assert real_cfg["quality"] == "720p"
    assert real_cfg["execution_mode"] == "real"

    # Test mode before retirement
    test_cfg = fixture_settings(test=True, reference_date="2026-11-20")
    assert test_cfg["video_model"] == "gemini_omni_flash_1_1"
    assert test_cfg["image_model"] == "nano_banana_2_1"
    assert test_cfg["quality"] == "360p"
    assert test_cfg["execution_mode"] == "test"

    # Test mode after retirement
    test_cfg_future = fixture_settings(test=True, reference_date="2026-12-06")
    assert test_cfg_future["video_model"] == "veo_3_1_lite"
    assert test_cfg_future["quality"] == "360p"


def test_synthesize_hero_frame(tmp_path):
    target = tmp_path / "test_hero.jpg"
    out = synthesize_hero_frame(target, aspect_ratio="9:16", color="#1f2937")
    assert out.is_file()
    assert out.stat().st_size > 500
