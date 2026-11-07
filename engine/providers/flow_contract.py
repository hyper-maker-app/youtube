"""Explicit Flow configuration and offline capability snapshot; no client creation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
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


def get_supported_video_models() -> set[str]:
    """Return all approved Flow video model aliases."""
    m = mapping()
    res: set[str] = set()
    if "video" in m and "alias" in m["video"]:
        res.add(m["video"]["alias"])
    if "video_models" in m:
        res.update(m["video_models"].keys())
    return res or {"gemini_omni_flash_1_1", "gemini_omni_flash_1_2", "veo_3_1_lite"}


def get_supported_image_models() -> set[str]:
    """Return all approved Flow image model aliases."""
    m = mapping()
    res: set[str] = set()
    if "image" in m and "alias" in m["image"]:
        res.add(m["image"]["alias"])
    if "image_models" in m:
        res.update(m["image_models"].keys())
    return res or {"nano_banana_pro", "nano_banana_2_1"}


def resolve_flow_video_model(execution_mode: str = "real", reference_date: str | None = None) -> str:
    """Resolve active video model based on execution mode and lifecycle cutoff."""
    if execution_mode == "test":
        ref = reference_date or date.today().isoformat()
        if ref < "2026-12-05":
            return "gemini_omni_flash_1_1"
        return "veo_3_1_lite"
    return "gemini_omni_flash_1_2"


def resolve_flow_image_model() -> str:
    """Resolve active image model (zero credit, free)."""
    return "nano_banana_2_1"


def default_capabilities(model_alias: str | None = None) -> ProviderCapabilities:
    m = mapping()
    if model_alias and "video_models" in m and model_alias in m["video_models"]:
        video = m["video_models"][model_alias]
    elif "video" in m:
        video = m["video"]
    else:
        video = next(iter(m.get("video_models", {}).values()))
    return ProviderCapabilities.from_dict({"video_model": video["alias"], **{
        k: v for k, v in video.items() if k.startswith("supported_") or k.startswith("supports_")}})


def settings(*, test: bool = False, execution_mode: str | None = None, reference_date: str | None = None) -> dict:
    """Require explicit runtime configuration. Fixtures use fixture_settings instead."""
    mode = execution_mode or ("test" if test else "real")
    result = fixture_settings(test=test, execution_mode=mode, reference_date=reference_date)
    valid_videos = get_supported_video_models()
    valid_images = get_supported_image_models()

    env_video = os.environ.get("FLOW_VIDEO_MODEL", "").strip()
    if env_video:
        if env_video not in valid_videos:
            raise ConfigurationError(f"FLOW_VIDEO_MODEL violates the locked Flow production/test contract: {env_video}")
        result["video_model"] = env_video
        caps = default_capabilities(env_video).snapshot()
        result["capabilities"] = caps
        result["allowed_native_durations"] = caps["supported_native_durations"]

    env_image = os.environ.get("FLOW_IMAGE_MODEL", "").strip()
    if env_image:
        if env_image not in valid_images:
            raise ConfigurationError(f"FLOW_IMAGE_MODEL violates the locked Flow production/test contract: {env_image}")
        result["image_model"] = env_image

    if os.environ.get("FLOW_IMAGE_FALLBACK_MODEL", "").strip():
        raise ConfigurationError("FLOW_IMAGE_FALLBACK_MODEL must be empty; Nano Banana is fail-closed")

    allowed_durations_str = os.environ.get("FLOW_ALLOWED_DURATIONS", "").strip()
    if allowed_durations_str:
        try:
            durations = [int(v.strip()) for v in allowed_durations_str.split(",")]
        except ValueError as exc:
            raise ConfigurationError("Invalid FLOW_ALLOWED_DURATIONS") from exc
        if durations != list(result["allowed_native_durations"]):
            raise ConfigurationError("FLOW_ALLOWED_DURATIONS must match the approved capability snapshot")

    policy_str = os.environ.get("FLOW_DURATION_POLICY", "").strip()
    if policy_str:
        if policy_str not in ("adaptive_native_v1", "fixed_8s_v1"):
            raise ConfigurationError("Unknown FLOW_DURATION_POLICY")
        result["duration_policy"] = policy_str

    return result


def validate_snapshot(contract: dict, *, test: bool) -> None:
    """Validate pinned choices without consulting changing live capabilities."""
    valid_videos = get_supported_video_models()
    valid_images = get_supported_image_models()
    if contract.get("video_model") not in valid_videos or contract.get("image_model") not in valid_images:
        raise ConfigurationError("Saved Flow model contract differs; explicit repair required")
    if contract.get("quality") != ("360p" if test else "720p"):
        raise ConfigurationError("Saved Flow quality does not match the real/test execution mode")
    if contract.get("execution_mode") != ("test" if test else "real"):
        raise ConfigurationError("Saved Flow execution mode differs")
    caps = contract.get("capabilities", {})
    if caps.get("video_model") != contract.get("video_model") or not caps.get("supported_native_durations"):
        raise ConfigurationError("Saved Flow capabilities contradict the selected model")
    if any(v not in (4, 6, 8, 10) for v in caps.get("supported_native_durations", ())):
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


def fixture_settings(*, test: bool = True, execution_mode: str | None = None, reference_date: str | None = None) -> dict:
    mode = execution_mode or ("test" if test else "real")
    video_model = resolve_flow_video_model(execution_mode=mode, reference_date=reference_date)
    image_model = resolve_flow_image_model()
    caps = default_capabilities(video_model).snapshot()
    return {"video_model": video_model, "image_model": image_model,
            "quality": "360p" if mode == "test" else "720p", "execution_mode": mode,
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
                             end_frame: bool = False, references: bool = False,
                             model_alias: str | None = None) -> str:
    """Resolve the upstream conditioned key for provenance without claiming identity."""
    if isinstance(duration, bool) or duration not in (4, 6, 8, 10):
        raise ConfigurationError("Native video duration must be exactly 4, 6, 8 or 10")
    if end_frame and not start_frame:
        raise ConfigurationError("End frame requires a start frame")
    if references and (start_frame or end_frame):
        raise ConfigurationError("Reference conditioning cannot be combined with frame conditioning")
    m = mapping()
    video = m.get("video_models", {}).get(model_alias, m["video"]) if model_alias else m["video"]
    dispatch = video.get("conditioning_dispatch", m["video"].get("conditioning_dispatch", {}))
    if references:
        return dispatch["references"].format(duration=int(duration))
    if start_frame and end_frame:
        shape = "start_and_end_frame"
    elif start_frame:
        shape = "start_frame"
    else:
        shape = "text_to_video"
    return dispatch[shape].format(duration=int(duration))
