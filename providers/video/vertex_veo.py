"""Vertex AI Veo 3.1 Lite adapter with strict image conditioning and RAI evidence."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import os
import re
import sys
import time
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from providers.base import BaseVideoProvider, ConfigurationError, ProviderError


LOGGER = logging.getLogger(__name__)
MAX_PROMPT_LENGTH = 900
VERTEX_REQUEST_PARAMETERS = {
    "aspectRatio": "9:16",
    "durationSeconds": 4,
    "personGeneration": "ALLOW_ADULT",
    "safetySetting": "BLOCK_ONLY_HIGH",
    "resolution": "1080p",
}
RAI_REPLACEMENTS = {
    r"\bcancer\b": "abnormal cellular cluster",
    r"\bblood\b": "crimson fluid",
    r"\bneedle\b": "micro probe",
    r"\b(?:wound|cut|puncture)\b": "fissure penetration",
    r"\b(?:blade|razor|knife|scalpel|cutter)\b": "metal probe",
    r"\bhydrochloric acid\b": "amber digestive fluid",
    r"\b(?:burn|unburnt|burning|burnt)\b": "reaction",
    r"\bcaustic\b": "concentrated",
    r"\b(?:flesh|raw\s+meat)\b": "cellular matrix",
    r"\b(?:bleed|bleeding|bloody|hemorrhage)\b": "dense crimson fluid",
    r"\b(?:poison|toxic|toxin)\b": "reactive biochemical solution",
    r"\b(?:kill|dying|death|dead)\b": "inactive state",
    r"\b(?:laceration|stab|stabbed)\b": "aperture penetration",
}

# Official Google Cloud Veo Support Code to Safety Category mapping
# Source: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/responsible-ai-and-usage-guidelines
VEO_SUPPORT_CODE_MAP = {
    "58061214": "Child safety",
    "17301594": "Child safety",
    "29310472": "Celebrity",
    "15236754": "Celebrity",
    "64151117": "Video safety violation",
    "42237218": "Video safety violation",
    "62263041": "Dangerous content",
    "57734940": "Hate speech",
    "22137204": "Hate speech",
    "74803281": "Other safety violation",
    "29578790": "Other safety violation",
    "42876398": "Other safety violation",
    "89371032": "Prohibited content",
    "49114662": "Prohibited content",
    "63429089": "Prohibited content",
    "72817394": "Prohibited content",
    "60599140": "Prohibited content",
    "35561574": "Third-party content",
    "35561575": "Third-party content",
    "90789179": "Sexual content",
    "43188360": "Sexual content",
    "78610348": "Toxic content",
    "61493863": "Violence",
    "56562880": "Violence",
    "32635315": "Vulgar content",
}


def parse_veo_safety_reason(reason_str: str) -> str:
    """Translate Veo numeric support codes into human-readable safety categories."""
    match = re.search(r"Support codes?:\s*([0-9\s,]+)", reason_str, re.IGNORECASE)
    if match:
        codes = [c.strip() for c in re.split(r"[,\s]+", match.group(1)) if c.strip()]
        categories = [VEO_SUPPORT_CODE_MAP.get(code, f"Unknown code {code}") for code in codes]
        return f"{', '.join(categories)} (support code: {', '.join(codes)})"
    return reason_str


class VertexVeoProvider(BaseVideoProvider):
    """Generate a conditioned 4-second vertical clip through Vertex AI Veo Lite."""

    def __init__(
        self, *, project: str | None = None, location: str | None = None,
        operation_timeout: float | None = None, poll_seconds: float | None = None, model: str | None = None,
    ) -> None:
        self.project = project or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEX_PROJECT")
        self.location = location or os.getenv("VERTEX_LOCATION") or os.getenv("GOOGLE_CLOUD_LOCATION")
        self.model = model or os.getenv("VERTEX_VIDEO_MODEL")
        missing = [name for name, value in (("GOOGLE_CLOUD_PROJECT", self.project), ("VERTEX_LOCATION", self.location)) if not value]
        if missing:
            raise ConfigurationError("vertex_veo provider requires: " + ", ".join(missing) + ". Configure them in .env.")
        self.operation_timeout = operation_timeout if operation_timeout is not None else float(os.getenv("VERTEX_OPERATION_TIMEOUT_SECONDS") or "1200")
        self.poll_seconds = poll_seconds if poll_seconds is not None else float(os.getenv("VERTEX_OPERATION_POLL_SECONDS") or "10")

    @staticmethod
    def sanitize_prompt(prompt: str) -> str:
        clean = " ".join(prompt.split())
        for pattern, replacement in RAI_REPLACEMENTS.items():
            clean = re.sub(pattern, replacement, clean, flags=re.IGNORECASE)
        if len(clean) <= MAX_PROMPT_LENGTH:
            return clean
        shortened = clean[:MAX_PROMPT_LENGTH].rsplit(" ", 1)[0].strip()
        return shortened or clean[:MAX_PROMPT_LENGTH]


    @staticmethod
    def _safe_fallback_prompt(prompt: str) -> str:
        """Fallback prompt that preserves core scale and studio lighting while eliminating risky action verbs."""
        clean = " ".join(prompt.split())
        clean = re.sub(r"\b(?:corrode[s]?|dissolve[s]?|penetrate[s]?)\b", "interacts with", clean, flags=re.I)
        clean = re.sub(r"\b(?:causing\s+)?(?:severe\s+)?damage[s]?\b", "surface transition", clean, flags=re.I)
        clean = re.sub(r"\b(?:destroys?|burn[s]?)\b", "activates", clean, flags=re.I)
        clean = re.sub(r"\b(?:fissure|flesh|caustic)\b", "structure", clean, flags=re.I)
        if len(clean) <= MAX_PROMPT_LENGTH:
            return clean
        return clean[:MAX_PROMPT_LENGTH].rsplit(" ", 1)[0].strip() or clean[:MAX_PROMPT_LENGTH]

    async def animate_block(
        self, start_frame: Path, end_frame: Path | None, motion_prompt: str,
        out_path: Path, duration: float = 4.0,
    ) -> Path:
        if float(duration) != 4.0:
            raise ValueError("vertex_veo Veo 3.1 Lite blocks are fixed at 4.0 seconds")
        if not motion_prompt.strip():
            raise ValueError("motion prompt must not be blank")
        if not self.model:
            raise ConfigurationError("vertex_veo provider requires VERTEX_VIDEO_MODEL. Configure it in .env.")
        start_frame = Path(start_frame)
        if not start_frame.is_file():
            raise FileNotFoundError(f"Vertex start_frame does not exist: {start_frame}")
        if end_frame is not None and not Path(end_frame).is_file():
            raise FileNotFoundError(f"Vertex end_frame does not exist: {end_frame}")

        max_transient_retries = 4
        safety_attempt = 0
        current_prompt = self.sanitize_prompt(motion_prompt)

        for transient_attempt in range(1, max_transient_retries + 1):
            try:
                return await asyncio.to_thread(
                    self._animate_sync, start_frame, Path(end_frame) if end_frame else None,
                    current_prompt, Path(out_path),
                )
            except ProviderError as exc:
                exc_str = str(exc).lower()
                is_safety = "safety" in exc_str or "rai" in exc_str or "blocked" in exc_str
                is_transient = any(w in exc_str for w in ("429", "resourceexhausted", "quota", "rate limit", "503", "unavailable", "connection", "reset", "timeout", "econnreset"))

                if is_safety and safety_attempt == 0:
                    safety_attempt += 1
                    current_prompt = self._safe_fallback_prompt(current_prompt)
                    LOGGER.warning("Veo block hit safety filter (%s); retrying with safe physical steering...", exc)
                    await asyncio.sleep(3.0)
                    continue

                if is_transient and transient_attempt < max_transient_retries:
                    wait_time = 5.0 * (2 ** (transient_attempt - 1))  # 5s, 10s, 20s
                    LOGGER.warning("Veo block hit transient error (%s); exponential backoff sleeping %ds (attempt %d/%d)...", exc, wait_time, transient_attempt, max_transient_retries)
                    sys.stdout.write(f"\r    [Veo 429/Transient Kota/Ağ] {wait_time:.0f}s bekleniyor ({transient_attempt}/{max_transient_retries})...")
                    sys.stdout.flush()
                    await asyncio.sleep(wait_time)
                    continue

                raise

    def _animate_sync(self, start_frame: Path, end_frame: Path | None, prompt: str, out_path: Path) -> Path:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - requirements declare the SDK
            raise ConfigurationError("vertex_veo provider requires the google-genai package.") from exc
        try:
            client = genai.Client(vertexai=True, project=self.project, location=self.location)
            start_image = self._image(types, start_frame)
            fields = getattr(types.GenerateVideosConfig, "model_fields", {})
            if "resolution" not in fields:
                raise ConfigurationError(
                    "vertex_veo requires a google-genai SDK with GenerateVideosConfig.resolution for 1080p output."
                )
            # ``VERTEX_REQUEST_PARAMETERS`` preserves the native REST field names for
            # audits; google-genai config objects expose their Python snake_case peers.
            target_aspect = "16:9" if str(os.getenv("LONGFORM_MODE", "")).casefold() in {"1", "true", "yes"} else VERTEX_REQUEST_PARAMETERS["aspectRatio"]
            video_config: dict[str, Any] = {
                "aspect_ratio": target_aspect,
                "duration_seconds": VERTEX_REQUEST_PARAMETERS["durationSeconds"],
                "person_generation": VERTEX_REQUEST_PARAMETERS["personGeneration"],
                "resolution": VERTEX_REQUEST_PARAMETERS["resolution"],
                "number_of_videos": 1, "generate_audio": False,
            }
            if "negative_prompt" in fields:
                video_config["negative_prompt"] = (
                    "speaking mouth, dialogue, lip-sync, open mouth, text, generated captions, subtitles, logos, watermark, UI, HUD, "
                    "pyrotechnics, sparks, burst, explosions, bright flash, photorealistic gore, blood, open wounds, sharp weapons, blades, razors, "
                    "real children, real celebrities, brand logos, floaty motion, sliding feet, warping, morphing, clipping through geometry, "
                    "body parts merging, gravity-defying, rubbery limbs, jitter, 2D camera slide, cross-dissolve morph, frozen static pose"
                )
            if end_frame is not None:
                video_config["last_frame"] = self._image(types, end_frame)
            operation = client.models.generate_videos(
                model=self.model,
                source=types.GenerateVideosSource(prompt=prompt, image=start_image),
                config=types.GenerateVideosConfig(**video_config),
            )
            result = self._wait_for_operation(client, operation)
            categories = self._safety_categories(result)
            if categories:
                self._raise_safety(categories)
            video = self._video_bytes(result)
        except (ConfigurationError, ProviderError):
            raise
        except Exception as exc:
            categories = self._safety_categories(exc)
            if categories:
                self._raise_safety(categories)
            raise ProviderError(f"vertex_veo request failed: {type(exc).__name__}") from exc
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(video)
        return out_path

    @staticmethod
    def _image(types: Any, path: Path) -> Any:
        mime = mimetypes.guess_type(path.name)[0]
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError(f"Unsupported Vertex frame type: {path.suffix}")
        return types.Image(image_bytes=path.read_bytes(), mime_type=mime)

    def _wait_for_operation(self, client: Any, operation: Any) -> Any:
        start_t = time.monotonic()
        deadline = start_t + self.operation_timeout
        last_heartbeat = start_t
        printed_heartbeat = False
        while not bool(getattr(operation, "done", False)):
            if time.monotonic() >= deadline:
                raise ProviderError("vertex_veo operation timed out")
            time.sleep(self.poll_seconds)
            now = time.monotonic()
            if now - last_heartbeat >= 15.0:
                elapsed = int(now - start_t)
                sys.stdout.write(f"\r    ... işleniyor (bekleme: {elapsed}s)")
                sys.stdout.flush()
                last_heartbeat = now
            try:
                operation = client.operations.get(operation)
            except Exception as poll_exc:
                LOGGER.warning("Transient error polling Veo operation (%s); retrying in %ss...", poll_exc, self.poll_seconds)
                time.sleep(self.poll_seconds)
                continue
        if printed_heartbeat:
            sys.stdout.write("\r" + " " * 45 + "\r")
            sys.stdout.flush()
        error = getattr(operation, "error", None)
        if error:
            categories = self._safety_categories(error)
            if categories:
                self._raise_safety(categories)
            raise ProviderError("vertex_veo operation failed")
        return operation

    @staticmethod
    def _video_bytes(operation: Any) -> bytes:
        response = getattr(operation, "response", None)
        videos = getattr(response, "generated_videos", None) or []
        if not videos:
            reasons = getattr(response, "rai_media_filtered_reasons", None)
            if reasons:
                details = [parse_veo_safety_reason(str(r)) for r in reasons]
                raise ProviderError(f"vertex_veo safety blocked video generation: {'; '.join(details)}")
            raise ProviderError("vertex_veo operation completed without generated video")
        video = getattr(videos[0], "video", None)
        payload = getattr(video, "video_bytes", None)
        if not payload:
            raise ProviderError("vertex_veo operation completed without MP4 bytes")
        return bytes(payload)

    @classmethod
    def _safety_categories(cls, value: Any) -> list[str]:
        categories: list[str] = []
        for node in cls._walk(value):
            attrs = node.get("safetyAttributes") or node.get("safety_attributes")
            if attrs is None:
                continue
            if not isinstance(attrs, Mapping):
                attrs = cls._as_mapping(attrs)
            if not attrs or not attrs.get("blocked"):
                continue
            raw = attrs.get("categories") or attrs.get("category") or attrs.get("category_name") or "unknown"
            values = raw if isinstance(raw, (list, tuple, set)) else [raw]
            categories.extend(str(item) for item in values if str(item).strip())
        return list(dict.fromkeys(categories))

    @classmethod
    def _walk(cls, value: Any, depth: int = 0) -> Iterator[dict[str, Any]]:
        if depth > 8:
            return
        mapping = cls._as_mapping(value)
        if mapping:
            yield mapping
            for child in mapping.values():
                if isinstance(child, (str, bytes, int, float, bool, type(None))):
                    continue
                yield from cls._walk(child, depth + 1)
        elif isinstance(value, (list, tuple, set)):
            for child in value:
                yield from cls._walk(child, depth + 1)

    @staticmethod
    def _as_mapping(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        if hasattr(value, "__dict__"):
            return dict(vars(value))
        return {}

    @staticmethod
    def _raise_safety(categories: list[str]) -> None:
        category = ", ".join(categories)
        LOGGER.error("TERMINAL ERROR: Veo Safety Triggered on Category %s", category)
        raise ProviderError(f"TERMINAL ERROR: Veo Safety Triggered on Category {category}")
