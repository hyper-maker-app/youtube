"""xAI Grok adapter for schema-constrained script generation."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from providers.base import BaseLLMProvider, ConfigurationError, ProviderError


class GrokLLMProvider(BaseLLMProvider):
    """Generate structured scripts through xAI Grok API (OpenAI-compatible)."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("XAI_API_KEY")
        self.model = model or os.getenv("XAI_MODEL") or "grok-4.20-0309-non-reasoning"
        self.base_url = base_url or os.getenv("XAI_API_BASE") or "https://api.x.ai/v1"
        if not self.api_key:
            raise ConfigurationError(
                "grok provider requires XAI_API_KEY. Configure it in .env."
            )

    async def generate_script(
        self, topic: str, system_prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        if not topic.strip():
            raise ValueError("topic must not be blank")
        if not isinstance(schema, dict) or not schema:
            raise ValueError("schema must be a non-empty JSON schema object")
        return await asyncio.to_thread(self._generate_sync, topic, system_prompt, schema)

    async def generate_topic_selection(
        self, system_prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._generate_sync,
            "Select one original science-short topic.",
            system_prompt,
            schema,
        )

    def _generate_sync(
        self, topic: str, system_prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ConfigurationError("grok provider requires the openai package.") from exc

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        from services.directing_rules import get_cinematic_guidelines

        guidelines = get_cinematic_guidelines()
        if guidelines and guidelines not in system_prompt:
            full_system_prompt = f"{system_prompt}\n\n{guidelines}"
        else:
            full_system_prompt = system_prompt

        prompt_message = (
            f"Create the script for this topic: {topic}\n\n"
            f"Return ONLY a valid JSON object matching this schema:\n"
            f"{json.dumps(schema)}"
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": full_system_prompt},
                    {"role": "user", "content": prompt_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
            )
        except Exception as exc:
            raise ProviderError(f"grok script request failed: {type(exc).__name__}: {exc}") from exc

        content = ""
        if response.choices and response.choices[0].message:
            content = response.choices[0].message.content or ""
        content = content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
        try:
            value = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"grok returned invalid JSON for the requested schema: {content[:200]}") from exc
        if not isinstance(value, dict):
            raise ProviderError("grok returned JSON that is not an object.")
        return value
