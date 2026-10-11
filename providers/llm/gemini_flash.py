"""Gemini Flash adapter for schema-constrained script generation."""

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


class GeminiFlashProvider(BaseLLMProvider):
    """Generate one JSON script through the Google GenAI SDK with an explicit API key."""

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL")
        missing = [
            name
            for name, value in (("GEMINI_API_KEY", self.api_key), ("GEMINI_MODEL", self.model))
            if not value
        ]
        if missing:
            raise ConfigurationError(
                "gemini_flash provider requires: " + ", ".join(missing) + ". Configure them in .env."
            )

    async def generate_script(
        self, topic: str, system_prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        if not topic.strip():
            raise ValueError("topic must not be blank")
        if not isinstance(schema, dict) or not schema:
            raise ValueError("schema must be a non-empty JSON schema object")
        return await asyncio.to_thread(self._generate_sync, topic, system_prompt, schema)

    async def generate_topic_selection(self, system_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._generate_sync, "Select one original science-short topic.", system_prompt, schema)

    def _generate_sync(
        self, topic: str, system_prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - declared in requirements.txt
            raise ConfigurationError("gemini_flash provider requires the google-genai package.") from exc

        client = genai.Client(api_key=self.api_key)
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=f"Create the script for this topic: {topic}",
                config=types.GenerateContentConfig(
                    system_instruction=(
                        system_prompt
                        if "natural speech articulation" in system_prompt.casefold()
                        else f"{system_prompt}\n\n{CHARACTER_AUDIO_RULE}"
                    ),
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
        except Exception as exc:
            raise ProviderError(f"gemini_flash script request failed: {type(exc).__name__}") from exc

        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, dict):
            return parsed
        raw = (getattr(response, "text", "") or "").strip()
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderError("gemini_flash returned invalid JSON for the requested schema.") from exc
        if not isinstance(value, dict):
            raise ProviderError("gemini_flash returned JSON that is not an object.")
        return value
