"""Explicit Flow configuration and offline capability snapshot; no client creation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path

from providers.base import ConfigurationError

MODEL_MAP = Path(__file__).with_name("flow_models.json")


@dataclass(frozen=True)
class ProviderCapabilities:
    video_model: str
    supported_native_durations: tuple[int, ...]
    supported_qualities: tuple[str, ...]
    supported_aspect_ratios: tuple[str, ...]
    supports_text_to_video: bool
    supports_first_frame: bool
    supports_first_and_last_frame: bool
    supports_references: bool
    supports_video_editing: bool
    supports_extend: bool

    @classmethod
    def from_dict(cls, value: dict) -> "ProviderCapabilities":
        values = dict(value)
        for key in ("supported_native_durations", "supported_qualities", "supported_aspect_ratios"):
            values[key] = tuple(values[key])
        return cls(**values)

    def snapshot(self) -> dict:
        return json.loads(json.dumps(asdict(self)))


def mapping() -> dict:
    return json.loads(MODEL_MAP.read_text(encoding="utf-8"))


def default_capabilities() -> ProviderCapabilities:
    video = mapping()["video"]
    return ProviderCapabilities.from_dict({"video_model": video["alias"], **{
        k: v for k, v in video.items() if k.startswith("supported_") or k.startswith("supports_")}})


def settings(*, test: bool = False) -> dict:
    """Require explicit runtime configuration. Fixtures use fixture_settings instead."""
    names = ("FLOW_VIDEO_MODEL", "FLOW_VIDEO_REAL_QUALITY", "FLOW_VIDEO_TEST_QUALITY",
             "FLOW_IMAGE_MODEL", "FLOW_ALLOWED_DURATIONS", "FLOW_DURATION_POLICY")
    missing = [key for key in names if not os.environ.get(key, "").strip()]
    if missing:
        raise ConfigurationError("Flow requires explicit .env settings: " + ", ".join(missing))
    result = fixture_settings(test=test)
    expected = {"FLOW_VIDEO_MODEL": result["video_model"], "FLOW_VIDEO_REAL_QUALITY": "720p",
                "FLOW_VIDEO_TEST_QUALITY": "360p", "FLOW_IMAGE_MODEL": result["image_model"]}
    for key, value in expected.items():
        if os.environ[key].strip() != value:
            raise ConfigurationError(f"{key} violates the locked Flow production/test contract")
    if os.environ.get("FLOW_IMAGE_FALLBACK_MODEL", "").strip():
        raise ConfigurationError("FLOW_IMAGE_FALLBACK_MODEL must be empty; Nano Banana Pro is fail-closed")
    try:
        durations = [int(v.strip()) for v in os.environ["FLOW_ALLOWED_DURATIONS"].split(",")]
    except ValueError as exc:
        raise ConfigurationError("Invalid FLOW_ALLOWED_DURATIONS") from exc
    if durations != result["allowed_native_durations"]:
        raise ConfigurationError("FLOW_ALLOWED_DURATIONS must match the approved capability snapshot")
    result["duration_policy"] = os.environ["FLOW_DURATION_POLICY"].strip()
    if result["duration_policy"] not in ("adaptive_native_v1", "fixed_8s_v1"):
        raise ConfigurationError("Unknown FLOW_DURATION_POLICY")
    return result


def validate_snapshot(contract: dict, *, test: bool) -> None:
    """Validate pinned choices without consulting changing live capabilities."""
    approved = mapping()
    if contract.get("video_model") != approved["video"]["alias"] or contract.get("image_model") != approved["image"]["alias"]:
        raise ConfigurationError("Saved Flow model contract differs; explicit repair required")
    if contract.get("quality") != ("360p" if test else "720p"):
        raise ConfigurationError("Saved Flow quality does not match the real/test execution mode")
    if contract.get("execution_mode") != ("test" if test else "real"):
        raise ConfigurationError("Saved Flow execution mode differs")
    caps = contract["capabilities"]
    if caps["video_model"] != contract["video_model"] or not caps["supported_native_durations"]:
        raise ConfigurationError("Saved Flow capabilities contradict the selected model")
    if any(v not in (4, 6, 8, 10) for v in caps["supported_native_durations"]):
        raise ConfigurationError("Saved Flow native duration is unsupported")
    saved_transport = contract.get("transport_provenance")
    if saved_transport is not None and saved_transport != transport_provenance():
        raise ConfigurationError("Saved Flow transport provenance changed; restore accepted dependency or repair explicitly")
    if saved_transport is None and not test:
        raise ConfigurationError("Saved Flow transport provenance missing; explicit repair required")


def transport_provenance() -> dict:
    """Pin catalog and transport evidence without touching account files or the binary."""
    catalog = mapping()
    return {"evidence_schema_version": catalog["transport"].get("evidence_schema_version"),
            "catalog_sha256": hashlib.sha256(MODEL_MAP.read_bytes()).hexdigest(),
            "source_revision": catalog["transport"]["source_revision"],
            "binary_version": catalog["transport"]["binary_version"],
            "binary_sha256": catalog["transport"]["binary_sha256"],
            "binary_source_verified": catalog["transport"]["binary_source_verified"],
            "display_name_verified": {asset: catalog[asset]["display_name_verified"] for asset in ("video", "image")}}


def fixture_settings(*, test: bool = True) -> dict:
    caps = default_capabilities().snapshot()
    return {"video_model": caps["video_model"], "image_model": mapping()["image"]["alias"],
            "quality": "360p" if test else "720p", "execution_mode": "test" if test else "real",
            "allowed_native_durations": caps["supported_native_durations"],
            "duration_policy": "adaptive_native_v1", "capabilities": caps,
            "transport_provenance": transport_provenance()}


def verified_cli_model(asset_type: str, binary: Path) -> str:
    """Never infer an upstream model from an opaque binary's defaults or help text."""
    model_map = mapping()
    entry = model_map["image" if asset_type == "image" else "video"]
    expected = model_map["transport"].get("verified_binary_sha256")
    evidence = model_map["transport"]
    cli_model = entry.get("cli_name") if asset_type == "image" else entry.get("transport_strategy")
    if not binary.is_file():
        raise ConfigurationError("Flow binary is missing; repair the verified transport dependency")
    if expected and hashlib.sha256(binary.read_bytes()).hexdigest() != expected:
        raise ConfigurationError("Flow binary changed; repair the verified transport dependency")
    if not evidence.get("runtime_policy", {}).get("verified"):
        raise ConfigurationError("Flow runtime policy blocked before browser/paid request: " +
                                 evidence.get("runtime_policy", {}).get("reason", "unreviewed runtime"))
    if (not entry.get("transport_verified") or not cli_model or not expected
            or not entry.get("source_dispatch_verified") or not entry.get("display_name_verified")
            or not evidence.get("binary_source_verified")):
        raise ConfigurationError(f"Flow {entry['display_name']} CLI mapping is unverified; generation blocked. "
                                 "See docs/FLOW_MODELS_AND_LIMITS.md and providers/flow_models.json")
    if not binary.is_file():
        raise ConfigurationError("Flow binary is missing; repair the verified transport dependency")
    if expected and hashlib.sha256(binary.read_bytes()).hexdigest() != expected:
        raise ConfigurationError("Flow binary changed; repair the verified transport dependency")
    if not entry.get("response_contract_verified") or not evidence.get("response_contract_verified"):
        raise ConfigurationError("Flow response contract is unverified; generation blocked before paid request. "
                                 "Model, quality, duration, aspect and asset-type evidence is required")
    return cli_model


def internal_video_model_key(duration: int, *, start_frame: bool = False,
                             end_frame: bool = False, references: bool = False) -> str:
    """Resolve the upstream conditioned key for provenance without claiming identity."""
    if isinstance(duration, bool) or duration not in (4, 6, 8, 10):
        raise ConfigurationError("Native video duration must be exactly 4, 6, 8 or 10")
    if end_frame and not start_frame:
        raise ConfigurationError("End frame requires a start frame")
    if references and (start_frame or end_frame):
        raise ConfigurationError("Reference conditioning cannot be combined with frame conditioning")
    if references:
        return mapping()["video"]["conditioning_dispatch"]["references"].format(duration=int(duration))
    if start_frame and end_frame:
        shape = "start_and_end_frame"
    elif start_frame:
        shape = "start_frame"
    else:
        shape = "text_to_video"
    return mapping()["video"]["conditioning_dispatch"][shape].format(duration=int(duration))
