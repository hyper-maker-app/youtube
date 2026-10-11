"""Nano Banana 2 keyframe adapter backed by the local Flow Agent bridge."""

from __future__ import annotations

from pathlib import Path

from providers._flow_agent import FlowAgentClient
from providers.base import BaseImageProvider


class FlowAgentBananaProvider(BaseImageProvider):
    """Generate one 9:16 Nano Banana 2 (``narwhal``) keyframe per request."""

    def __init__(self, *, client: FlowAgentClient | None = None) -> None:
        self.client = client or FlowAgentClient()

    async def generate_keyframe(
        self, prompt: str, out_path: Path, seed: int, aspect_ratio: str = "9:16",
        reference_image: Path | None = None, is_hero: bool = False, reference_images: list[Path] | None = None,
        negative_prompt: str | None = None,
    ) -> Path:
        if aspect_ratio not in {"9:16", "2:3", "1:1", "16:9", "3:2"}:
            raise ValueError("flow_agent supports only roster 2:3/1:1/9:16/16:9/3:2 aspect ratios")
        if not prompt.strip():
            raise ValueError("keyframe prompt must not be blank")
        # Flow currently exposes one configured image model, so hero selection is
        # intentionally a no-op while retaining the shared provider signature.
        _ = is_hero
        references = list(reference_images or [])
        if reference_image is not None:
            references.append(reference_image)
        if not references:
            # The opening anchor has no predecessor, so legacy Flow Agent bridges
            # remain usable for that single unconditioned call.
            if aspect_ratio == "9:16":
                return await self.client.image(prompt, Path(out_path), seed)
            return await self.client.image(prompt, Path(out_path), seed, aspect_ratio=aspect_ratio)
        if aspect_ratio == "9:16" and len(references) == 1:
            return await self.client.image(prompt, Path(out_path), seed, reference_image=references[0])
        return await self.client.image(prompt, Path(out_path), seed, aspect_ratio=aspect_ratio, reference_images=references)
