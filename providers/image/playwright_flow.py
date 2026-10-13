from __future__ import annotations

import logging
from pathlib import Path

from providers.base import BaseImageProvider
from services.playwright_flow_client import PlaywrightFlowClient

logger = logging.getLogger(__name__)


class PlaywrightFlowImageProvider(BaseImageProvider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = PlaywrightFlowClient()

    async def generate_keyframe(
        self,
        prompt: str,
        out_path: Path,
        seed: int = 42,
        aspect_ratio: str = "9:16",
        reference_image: Path | None = None,
        is_hero: bool = False,
        reference_images: list[Path] | None = None,
        negative_prompt: str | None = None,
    ) -> Path:
        _ = (seed, is_hero, negative_prompt)
        refs = list(reference_images or [])
        if reference_image is not None:
            refs.append(reference_image)
        logger.info(f"Generating image with Playwright CDP Flow ({aspect_ratio}): {prompt[:60]}...")
        return await self.client.generate_asset(
            prompt=prompt,
            out_path=out_path,
            asset_type="image",
            aspect_ratio=aspect_ratio,
            reference_images=refs,
        )

    async def close(self) -> None:
        await self.client.close()
