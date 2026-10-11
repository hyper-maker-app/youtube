"""Google Flow 3rd Method Image Provider via Autonomous Browser Automation.

Controls the open Google Flow window directly (flow.google.com).
Bypasses Flow Agent rate limits, reCAPTCHA failures, and cooldowns.
"""

from __future__ import annotations

import logging
from pathlib import Path

from providers.base import BaseImageProvider
from services.flow_browser_automation import FlowBrowserClient

logger = logging.getLogger(__name__)


class BrowserFlowImageProvider(BaseImageProvider):
    """Generate keyframes via direct Google Flow browser automation."""

    def __init__(self, client: FlowBrowserClient | None = None) -> None:
        self.client = client or FlowBrowserClient()

    async def generate_keyframe(
        self,
        prompt: str,
        out_path: Path,
        seed: int,
        aspect_ratio: str = "16:9",
        reference_image: Path | None = None,
        is_hero: bool = False,
        reference_images: list[Path] | None = None,
        negative_prompt: str | None = None,
    ) -> Path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if not prompt.strip():
            raise ValueError("keyframe prompt must not be blank")

        logger.info(f"[BROWSER FLOW IMAGE] Generating image keyframe ({aspect_ratio}): '{prompt[:60]}...'")
        return await self.client.generate_asset(
            prompt=prompt,
            out_path=out_path,
            asset_type="image",
            aspect=aspect_ratio,
        )
