"""Nano Banana Pro keyframe adapter through Vertex AI's Gemini image endpoint."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

from providers.base import BaseImageProvider, ConfigurationError, ProviderError


class NanoBananaProProvider(BaseImageProvider):
    """Generate each roster sheet and keyframe with Nano Banana Pro only."""

    def __init__(
        self, *, project: str | None = None, location: str | None = None,
        model_normal: str | None = None, model_hero: str | None = None,
        model: str | None = None,
    ) -> None:
        self.project = project or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEX_PROJECT")
        # Image model availability may differ from Veo's regional endpoint.  Keep
        # this explicit instead of rerouting the selected model/provider.
        self.location = location or os.getenv("NANO_BANANA_PRO_LOCATION") or "global"
        # ``model`` remains a compatibility override for direct callers/tests; in
        # production each tier is independently explicit in .env.
        self.normal_model = model_normal or model or os.getenv("NANO_BANANA_PRO_MODEL")
        self.hero_model = model_hero or model or os.getenv("NANO_BANANA_PRO_MODEL")
        missing = [name for name, value in (
            ("GOOGLE_CLOUD_PROJECT or VERTEX_PROJECT", self.project),
            ("VERTEX_LOCATION or GOOGLE_CLOUD_LOCATION", self.location),
            ("NANO_BANANA_PRO_MODEL", self.normal_model),
        ) if not value]
        if missing:
            raise ConfigurationError("nano_banana_pro provider requires: " + ", ".join(missing) + ". Configure them in .env.")
        # The pipeline currently submits keyframes sequentially, but keep the safety
        # boundary with the selected Vertex adapter as well: future callers cannot turn
        # a harmless gather() into a burst that consumes the project's token bucket.
        self.max_concurrency = max(1, min(2, int(os.getenv("NANO_BANANA_PRO_MAX_CONCURRENCY", "1"))))
        self.min_interval_seconds = max(0.0, float(os.getenv("NANO_BANANA_PRO_MIN_INTERVAL_SECONDS", "1.0")))
        self.retry_429_attempts = max(0, min(6, int(os.getenv("NANO_BANANA_PRO_429_RETRIES", "4"))))
        self.retry_429_backoff_seconds = max(0.1, float(os.getenv("NANO_BANANA_PRO_429_BACKOFF_SECONDS", "2.0")))
        # Content generation is synchronous at the SDK surface. Bound the caller
        # wait so an unavailable endpoint leaves a resumable run rather than
        # holding production forever. A timed-out call is never auto-retried
        # because server-side completion would be unknown.
        self.request_timeout_seconds = max(15.0, min(300.0, float(os.getenv("NANO_BANANA_PRO_REQUEST_TIMEOUT_SECONDS", "120"))))
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self._pacing_lock = asyncio.Lock()
        self._next_request_at = 0.0

    async def generate_keyframe(
        self, prompt: str, out_path: Path, seed: int, aspect_ratio: str = "9:16",
        reference_image: Path | None = None, is_hero: bool = False, reference_images: list[Path] | None = None,
        negative_prompt: str | None = None,
    ) -> Path:
        if aspect_ratio not in {"9:16", "2:3", "1:1", "16:9", "3:2"}:
            raise ValueError("nano_banana_pro supports only roster 2:3/3:2/1:1 and video 9:16/16:9 aspect ratios")
        references = [Path(item) for item in (reference_images or [])]
        if reference_image is not None:
            references.append(Path(reference_image))
        if any(not item.is_file() or item.stat().st_size <= 0 for item in references):
            raise ValueError("nano_banana_pro references must be non-empty image files")
        selected_model = self.hero_model if is_hero else self.normal_model
        async with self._semaphore:
            await self._wait_for_request_slot()
            for attempt in range(self.retry_429_attempts + 1):
                try:
                    # Preserve the long-standing callable shape for direct tests and
                    # legacy monkeypatches; only roster/multi-reference work needs
                    # the extended provider-owned transport signature.
                    if aspect_ratio == "9:16" and len(references) <= 1 and not negative_prompt:
                        request = asyncio.to_thread(self._generate_sync, prompt, Path(out_path), seed, references[0] if references else None, selected_model)
                    elif aspect_ratio == "9:16" and len(references) <= 1:
                        request = asyncio.to_thread(self._generate_sync, prompt, Path(out_path), seed, references[0] if references else None, selected_model, "9:16", negative_prompt)
                    else:
                        request = asyncio.to_thread(self._generate_sync, prompt, Path(out_path), seed, references, selected_model, aspect_ratio, negative_prompt)
                    return await asyncio.wait_for(request, timeout=self.request_timeout_seconds)
                except (asyncio.TimeoutError, TimeoutError) as exc:
                    raise ProviderError(
                        f"nano_banana_pro keyframe request timed out after {self.request_timeout_seconds:.0f}s"
                    ) from exc
                except ProviderError as exc:
                    if not self._is_capacity_error(exc) or attempt >= self.retry_429_attempts:
                        raise
                    # Back off without replacing the selected provider or mutating a
                    # completed keyframe.  pipeline.py commits each successful image
                    # atomically, so the next process resumes only missing identities.
                    await asyncio.sleep(self.retry_429_backoff_seconds * (2 ** attempt))
                    await self._wait_for_request_slot()

        raise AssertionError("unreachable Vertex keyframe retry state")

    async def _wait_for_request_slot(self) -> None:
        """Reserve a process-local request start time under the configured QPS ceiling."""
        async with self._pacing_lock:
            now = time.monotonic()
            wait = max(0.0, self._next_request_at - now)
            self._next_request_at = max(now, self._next_request_at) + self.min_interval_seconds
        if wait:
            await asyncio.sleep(wait)

    @staticmethod
    def _is_capacity_error(error: BaseException) -> bool:
        """Recognize transport-neutral Vertex capacity signals without exposing details."""
        current: BaseException | None = error
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            text = str(current).casefold()
            if "429" in text or "resource_exhausted" in text or "too many requests" in text or "no image bytes" in text:
                return True
            current = current.__cause__ or current.__context__
        return False

    def _generate_sync(
        self, prompt: str, out_path: Path, seed: int,
        reference_images: list[Path] | None = None, model: str | None = None, aspect_ratio: str = "9:16",
        negative_prompt: str | None = None,
    ) -> Path:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(vertexai=True, project=self.project, location=self.location)
            effective_prompt = prompt
            if negative_prompt and str(negative_prompt).strip():
                effective_prompt = f"{prompt}\n[Negative Constraints]: Absolutely NEVER include: {negative_prompt.strip()}."
            contents = [effective_prompt]
            if isinstance(reference_images, Path):
                reference_images = [reference_images]
            for reference_image in reference_images or []:
                # Nano Banana Pro sees the preceding *accepted pixels*, not only a repeated
                # noun phrase.  This is the missing half of a real N+1 Match-Cut
                # chain: it preserves framing, materials and identity while the
                # prompt requests exactly one next causal state.
                contents.append(self._image(types, reference_image))
            response = client.models.generate_content(
                model=model or self.normal_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"], image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
                ),
            )
            payload = None
            for candidate in list(getattr(response, "candidates", []) or []):
                content = getattr(candidate, "content", None)
                for part in list(getattr(content, "parts", []) or []):
                    inline = getattr(part, "inline_data", None)
                    data = getattr(inline, "data", None)
                    if data:
                        payload = bytes(data)
                        break
                if payload:
                    break
            if not payload:
                raise RuntimeError("Vertex image response contained no image bytes")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(payload)
            return out_path
        except ConfigurationError:
            raise
        except Exception as exc:
            raise ProviderError(f"nano_banana_pro keyframe request failed: {type(exc).__name__}") from exc

    @staticmethod
    def _image(types: object, path: Path) -> object:
        import mimetypes

        mime = mimetypes.guess_type(path.name)[0]
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError(f"Unsupported Vertex reference image type: {path.suffix}")
        # ``generate_content`` accepts multimodal media as a Part.  ``types.Image``
        # is correct for the Veo video endpoint but Vertex content generation
        # requires a byte Part (otherwise the SDK asks for a file URI).
        return types.Part.from_bytes(data=path.read_bytes(), mime_type=mime)

    async def review_keyframe(
        self, frame: Path, *, previous_frame: Path | None, expected_state: str,
        previous_state: str | None, continuity_anchor: str, proof: str,
        allow_subject_change: bool = False, is_scale_transition: bool = False,
    ) -> dict[str, object]:
        """Use the configured Vertex text/vision model to admit a paid endpoint.

        This is intentionally a narrow visual admission check, not a request to
        re-author the scene.  A malformed review response remains visible in the
        run artifact, while a clear rejection prevents Veo from consuming a known
        bad keyframe pair.
        """
        model = os.getenv("VERTEX_TEXT_MODEL")
        location = os.getenv("VERTEX_TEXT_LOCATION") or self.location
        if not model or not location:
            return {"status": "reviewed", "accepted": False, "score": 0, "reasons": ["Vertex vision review is not configured"]}
        try:
            return await asyncio.to_thread(
                self._review_sync, Path(frame), Path(previous_frame) if previous_frame else None,
                str(model), str(location), expected_state, previous_state, continuity_anchor, proof,
                allow_subject_change, is_scale_transition,
            )
        except Exception as exc:
            return {"status": "reviewed", "accepted": False, "score": 0, "reasons": [f"review unavailable: {type(exc).__name__}"]}

    def _review_sync(
        self, frame: Path, previous_frame: Path | None, model: str, location: str,
        expected_state: str, previous_state: str | None, continuity_anchor: str, proof: str,
        allow_subject_change: bool, is_scale_transition: bool,
    ) -> dict[str, object]:
        try:
            from google import genai
            from google.genai import types

            # Three-branch reviewer semantics:
            # 1. allow_subject_change=True: deliberate Match-Cut, old subject MUST be replaced
            # 2. is_scale_transition=True: same subject, different scale/crop expected
            # 3. both False: strict same_subject continuity, nothing may change
            if previous_frame and allow_subject_change:
                transition_instruction = (
                    f"The first image is the accepted prior state ({previous_state}). "
                    "This is an intentional Match-Cut to a new subject or domain: the scene deliberately transitions to the authored current endpoint. "
                    "Accept if the current image clearly depicts the expected state with consistent cinematic lighting palette and camera energy. "
                    "Do NOT reject because the old subject, old materials, or old domain changed — this replacement is authored and expected."
                )
            elif previous_frame and is_scale_transition:
                transition_instruction = (
                    f"The first image is the accepted prior state ({previous_state}). "
                    "This is a scale or component transition: the subject or parent mechanism must be preserved (identity, materials, "
                    "geometry, lighting direction, environment) while scale, crop, or detail focus changes to make the "
                    "endpoint state visibly readable. Do NOT reject because the old subject/environment persists. "
                    "Reject only if visual domain/materials completely break, or if scale/detail did not visibly change, "
                    "or if an unrequested event was introduced."
                )
            elif previous_frame:
                transition_instruction = (
                    f"The first image is the accepted prior state ({previous_state}); "
                    "reject if the current image changes identity, materials, environment, lens/framing, "
                    "or introduces an unrequested event."
                )
            else:
                transition_instruction = "This is the opening anchor; judge clarity, geometry, and the no-text rule."

            prompt = " ".join(part for part in (
                "You are the strict visual admission gate for one vertical 3D science-documentary keyframe.",
                "Return only JSON with accepted (boolean), score (integer 0-10), and reasons (array of short strings).",
                "Reject if there is any visible text, caption, logo, watermark, UI, split-screen, wrong 9:16 framing,",
                "or if the image does not show one readable physical state with attached, plausible geometry.",
                "Reject if the image deviates from the benchmark Zack D. Films glossy stylized 3D animation aesthetic (reject flat 2D cartoon, Pixar-style caricature, photorealistic live-action human photography, or CAD wireframes).",
                "Reject if an aircraft, vehicle, machine, or anatomical structure has cartoon anthropomorphism such as eyes, mouth, or facial features (machines and vehicles must be realistic 3D engineering models).",
                "Reject if flat 2D graphic arrows, neon pointer stickers, or infographic clipart overlays are painted onto the image. Visual markers must be 100% physically embedded 3D volumetric light rays, photon streams, or fluid dynamics.",
                "Curved organic texture, subtle arm/hand reaching motions, restraint tightening dynamics, and contact adhesion dynamics belong to the video motion model, not keyframe geometry; do not reject keyframes for pre-contact postures, loosely looped restraints, or static poses.",
                "Per ADR-028, visual proof markers and annotations are rendered as integrated volumetric 3D energy streams, subtle luminescence, or directional force vectors; strictly do not reject keyframes for missing 2D graphic sticker arrows or flat clipart when volumetric lighting or stress vectors are visible.",
                "Directional flow propagation, fluid wave expansion, dynamic force vectors, and arrow angles belong to the video motion model; do not reject static keyframes for subtle arrow orientation, missing graphic arrows, or static fluid boundaries when the required physical substances, objects, and environment are clearly present.",
                "Reject if two people are visible together (or across paired same_subject shots) and look like the same person (matching clothing color/style) when they are meant to be different individuals. Reject if a close/macro shot of a real-world object has no visible scale reference and its apparent size relative to any visible surroundings is implausible. Reject if a described physical force (wind, pressure, impact) is not visibly acting on the subject in a physically plausible way.",
                f"Expected current state: {expected_state}. Continuity anchor: {continuity_anchor}.",
                f"Required visual proof: {proof}.",
                transition_instruction,
                "Accept only when score is at least 7 and every stated contract is visibly satisfied.",
            ))
            contents: list[object] = [prompt]
            if previous_frame is not None:
                contents.append(self._image(types, previous_frame))
            contents.append(self._image(types, frame))
            client = genai.Client(vertexai=True, project=self.project, location=location)
            last_exc: Exception | None = None
            response = None
            for r_attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=model, contents=contents,
                        config=types.GenerateContentConfig(response_mime_type="application/json"),
                    )
                    break
                except Exception as exc:
                    last_exc = exc
                    if r_attempt < 2:
                        time.sleep(2.0 * (r_attempt + 1))
            if response is None and last_exc is not None:
                raise last_exc
            raw = str(getattr(response, "text", "") or "").strip()
            if raw.startswith("```"):
                lines = raw.splitlines()
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw = "\n".join(lines).strip()
            parsed = json.loads(raw)
            accepted = bool(parsed.get("accepted")) and int(parsed.get("score") or 0) >= 7
            reasons = parsed.get("reasons")
            return {
                "status": "reviewed", "accepted": accepted, "score": int(parsed.get("score") or 0),
                "reasons": [str(reason) for reason in reasons] if isinstance(reasons, list) else [],
            }
        except Exception as exc:
            # A capacity or parser fault is not a fabricated passing verdict.
            # Return accepted: False with reviewed status so caller treats as rejection and triggers surgical repair.
            return {"status": "reviewed", "accepted": False, "score": 0, "reasons": [f"review unavailable: {type(exc).__name__}"]}
