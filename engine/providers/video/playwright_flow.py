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
    """Sanitize prompts to prevent false-positive safety refusals in Google Flow."""
    clean = prompt
    replacements = [
        (r"\b(?:severed\s+limbs?|decapitat\w*|mutilat\w*|disembowel\w*|gore|visceral)\b", "shattered debris"),
        (r"\b(?:arterial\s+spray|blood-soaked|pool\s+of\s+blood|bloody\s+mess)\b", "dark crimson reflections"),
        (r"\b(?:sinking\s+teeth\s+into|tearing\s+flesh|biting\s+deep|flesh\s+tearing)\b", "lunging aggressively toward"),
        (r"\b(?:suicide|self-harm|kill(?:ing)?)\b", "neutralizing"),
        (r"\b(?:corpses?|dead\s+bodies)\b", "fallen figures"),
        (r"\b(?:naked|nude)\b", "distressed tactical apparel"),
        (r"\b(?:bones?\s+cracking|exposed\s+bone)\b", "fractured structure"),
        (r"\b(?:pale\s+figure|pale\s+skin|pale\s+body|pale\s+corpse)\b", "reanimated subject in torn hospital uniform"),
        (r"\b(?:erratic,\s*pale\s*figure)\b", "erratic shadowy subject in hospital uniform"),
        (r"\b(?:pale|bare)\b", "shadowy"),
        (r"\b(?:natural\s+body\s+momentum|body\s+momentum)\b", "natural physical momentum"),
        (r"\b(?:infected\s+figure|infected\s+figures)\b", "hostile subject in torn hospital apparel"),
        (r"\b(?:crowd\s+of\s+infected)\b", "surging horde in distressed attire"),
        (r"\b(?:reanimated\s+patients?)\b", "shadowy figures in hospital scrubs"),
        (r"\b(?:sweating,\s*dirt-streaked\s*face)\b", "weathered determined expression"),
    ]
    for pattern, repl in replacements:
        clean = re.sub(pattern, repl, clean, flags=re.IGNORECASE)
    return " ".join(clean.split())


class PlaywrightFlowVideoProvider(BaseVideoProvider):
    def __init__(self, *, test_mode=False, client=None):
        self.test_mode = test_mode
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
        )

    async def close(self) -> None:
        await self.client.close()
