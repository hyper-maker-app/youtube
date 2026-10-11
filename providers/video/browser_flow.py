"""Google Flow 3rd Method Video Provider via Autonomous Browser Automation.

Controls the open Google Flow window directly (flow.google.com).
Bypasses Flow Agent rate limits, reCAPTCHA failures, and cooldowns.
"""

from __future__ import annotations

import logging
from pathlib import Path

from providers.base import BaseVideoProvider
from services.flow_browser_automation import FlowBrowserClient

logger = logging.getLogger(__name__)


class BrowserFlowVideoProvider(BaseVideoProvider):
    """Generate 16:9 or 9:16 Veo video blocks via direct Google Flow browser automation."""

    def __init__(self, client: FlowBrowserClient | None = None) -> None:
        self.client = client or FlowBrowserClient()

    async def animate_block(
        self,
        start_frame: Path,
        end_frame: Path | None,
        motion_prompt: str,
        out_path: Path,
        duration: float = 4.0,
    ) -> Path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if not motion_prompt.strip():
            raise ValueError("motion prompt must not be blank")

        logger.info(f"[BROWSER FLOW VIDEO] Generating video block ({duration}s): '{motion_prompt[:60]}...'")
        return await self.client.generate_asset(
            prompt=motion_prompt,
            out_path=out_path,
            asset_type="video",
            aspect="16:9",
        )
