"""Vertex AI Gemini screenplay adapter using ADC instead of a direct API key."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from providers.base import BaseLLMProvider, ConfigurationError, ProviderError


CHARACTER_AUDIO_RULE = (
    "Characters never speak. Keep mouths closed in every described shot. "
    "Do not request dialogue, narration spoken by an on-screen character, lip movement, "
    "or subtitles. Only diegetic non-speech sounds may be described."
)


class VertexGeminiProvider(BaseLLMProvider):
    """Generate structured scripts through Vertex AI with local ADC authentication."""

    def __init__(self, *, project: str | None = None, location: str | None = None, model: str | None = None) -> None:
        self.project = project or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEX_PROJECT")
        self.location = location or os.getenv("VERTEX_TEXT_LOCATION") or os.getenv("VERTEX_LOCATION") or os.getenv("GOOGLE_CLOUD_LOCATION")
        self.model = model or os.getenv("VERTEX_TEXT_MODEL")
        missing = [name for name, value in (("GOOGLE_CLOUD_PROJECT or VERTEX_PROJECT", self.project), ("VERTEX_TEXT_LOCATION or VERTEX_LOCATION", self.location), ("VERTEX_TEXT_MODEL", self.model)) if not value]
        if missing:
            raise ConfigurationError("vertex_gemini provider requires: " + ", ".join(missing) + ". Configure them in .env.")
        # Capacity failures are transient. Keep this small and explicit so we
        # neither substitute a different model nor endlessly hold a new run.
        self.retry_429_attempts = max(0, min(4, int(os.getenv("VERTEX_TEXT_429_RETRIES", "2"))))
        self.retry_429_backoff_seconds = max(1.0, min(60.0, float(os.getenv("VERTEX_TEXT_429_BACKOFF_SECONDS", "3"))))

    async def generate_script(self, topic: str, system_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if not topic.strip():
            raise ValueError("topic must not be blank")
        if not isinstance(schema, dict) or not schema:
            raise ValueError("schema must be a non-empty JSON schema object")
        for attempt in range(self.retry_429_attempts + 1):
            try:
                return await asyncio.to_thread(self._generate_sync, topic, system_prompt, schema)
            except ProviderError as exc:
                if not self._is_capacity_error(exc) or attempt >= self.retry_429_attempts:
                    raise
                await asyncio.sleep(self.retry_429_backoff_seconds * (2 ** attempt))
        raise AssertionError("unreachable Vertex Gemini retry state")

    async def generate_topic_selection(self, system_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self.retry_429_attempts + 1):
            try:
                return await asyncio.to_thread(self._generate_sync, "Select one original science-short topic.", system_prompt, schema)
            except ProviderError as exc:
                if not self._is_capacity_error(exc) or attempt >= self.retry_429_attempts:
                    raise
                await asyncio.sleep(self.retry_429_backoff_seconds * (2 ** attempt))
        raise AssertionError("unreachable Vertex Gemini retry state")

    @staticmethod
    def _is_capacity_error(error: BaseException) -> bool:
        current: BaseException | None = error
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            text = str(current).casefold()
            if "429" in text or "resource_exhausted" in text or "too many requests" in text:
                return True
            current = current.__cause__ or current.__context__
        return False

    def _generate_sync(self, topic: str, system_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(vertexai=True, project=self.project, location=self.location)
            response = client.models.generate_content(
                model=self.model,
                # Vertex accepts the broad screenplay contract reliably when it is
                # explicit prompt data. Its SDK schema fields implement a narrower
                # subset and reject several valid storyboard constraints.
                contents=(
                    f"Response schema (return exactly one matching JSON object): {json.dumps(schema, ensure_ascii=False)}\n\n"
                    f"Create the script for this topic: {topic}"
                ),
                config=types.GenerateContentConfig(
                    system_instruction=(
                        system_prompt
                        if "natural speech articulation" in system_prompt.casefold()
                        else f"{system_prompt}\n\n{CHARACTER_AUDIO_RULE}"
                    ),
                    response_mime_type="application/json", temperature=0.35,
                ),
            )
        except ConfigurationError:
            raise
        except Exception as exc:
            raise ProviderError(f"vertex_gemini script request failed: {type(exc).__name__}") from exc
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, dict):
            return parsed
        try:
            value = json.loads((getattr(response, "text", "") or "").strip())
        except json.JSONDecodeError as exc:
            raise ProviderError("vertex_gemini returned invalid JSON for the requested schema.") from exc
        if not isinstance(value, dict):
            raise ProviderError("vertex_gemini returned JSON that is not an object.")
        return value
