from __future__ import annotations

import logging
import re
from pathlib import Path

import config
from providers.base import BaseVideoProvider
from providers.base import ConfigurationError
from providers.flow_contract import settings, default_capabilities
from providers.flow_browser.native_transport import BrowserNativeFlowTransport

logger = logging.getLogger(__name__)


def sanitize_flow_prompt(prompt: str) -> str:
    """Normalize transport whitespace without rewriting the author's direction."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Flow motion_prompt must be a non-empty string")
    return " ".join(prompt.split())


class PlaywrightFlowVideoProvider(BaseVideoProvider):
    def __init__(self, *, test_mode=False, client=None):
        self.test_mode = test_mode
        self.allow_text_fallback = False
        self.contract = settings(test=test_mode)
        self.capabilities = default_capabilities()
        self.client = client or BrowserNativeFlowTransport()

    def preflight(self):
        return {"transport": BrowserNativeFlowTransport.VERSION, "runtime": "browser_cdp", "legacy_cli": False}

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
        if self.test_mode:
            raise ConfigurationError("Test mode uses a fixture transport; live Playwright generation is forbidden")
        if duration not in self.capabilities.supported_native_durations:
            raise ConfigurationError("Unsupported native duration; no rounding or fallback allowed")
        clean_prompt = sanitize_flow_prompt(motion_prompt)
        aspect_ratio = "16:9" if getattr(config, "LONGFORM_MODE", False) else "9:16"
        logger.info(f"Generating video with Playwright CDP Flow ({aspect_ratio}): {clean_prompt[:60]}...")
        return await self.client.generate_asset(
            prompt=clean_prompt,
            out_path=out_path,
            asset_type="video",
            aspect_ratio=aspect_ratio,
            start_frame=Path(start_frame) if start_frame else None,
            reference_images=reference_images,
            end_frame=end_frame,
            duration=duration,
            quality=self.contract["quality"], model=self.contract["video_model"],
            test_mode=self.test_mode,
            authorize=True,
            allow_text_fallback=self.allow_text_fallback,
        )

    async def close(self) -> None:
        await self.client.close()
