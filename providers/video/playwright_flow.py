from __future__ import annotations

import logging
from pathlib import Path

import config
from providers.base import BaseVideoProvider
from providers.video.vertex_veo import VertexVeoProvider
from services.playwright_flow_client import PlaywrightFlowClient

logger = logging.getLogger(__name__)


def sanitize_flow_prompt(prompt: str) -> str:
    """Normalize whitespace without applying Vertex-specific prompt truncation."""
    return " ".join(prompt.split())


class PlaywrightFlowVideoProvider(BaseVideoProvider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = PlaywrightFlowClient()

    async def animate_block(
        self,
        start_frame: Path,
        end_frame: Path | None,
        motion_prompt: str,
        out_path: Path,
        duration: float = 4.0,
    ) -> Path:
        return await self.animate_block_with_references(start_frame, end_frame, motion_prompt, out_path, duration)

    async def animate_block_with_references(
        self,
        start_frame: Path,
        end_frame: Path | None,
        motion_prompt: str,
        out_path: Path,
        duration: float = 4.0,
        reference_images: list[Path] | None = None,
    ) -> Path:
        # Flow has its own prompt budget and is not subject to Vertex's 900-char cap.
        # Keep the full authored camera/action/lighting contract intact.
        clean_prompt = sanitize_flow_prompt(motion_prompt)
        aspect_ratio = "16:9" if getattr(config, "LONGFORM_MODE", False) else "9:16"
        logger.info(f"Generating video with Playwright CDP Flow ({aspect_ratio}): {clean_prompt[:60]}...")
        try:
            return await self.client.generate_asset(
                prompt=clean_prompt,
                out_path=out_path,
                asset_type="video",
                aspect_ratio=aspect_ratio,
                start_frame=Path(start_frame) if start_frame else None,
                reference_images=reference_images,
                duration=int(round(duration)) if int(round(duration)) in (4, 6, 8, 10) else 4,
            )
        finally:
            await self.client.close()
