"""Provider adapter for the repository's local FFmpeg MotionEngine."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import editor
from providers.base import BaseVideoProvider, ProviderError


class MotionEngineProvider(BaseVideoProvider):
    """Render a local, deterministic FFmpeg motion block from its first keyframe."""

    def __init__(self, *, engine: editor.MotionEngine | None = None) -> None:
        self.engine = engine or editor.MotionEngine()

    async def animate_block(
        self, start_frame: Path, end_frame: Path | None, motion_prompt: str,
        out_path: Path, duration: float = 4.0,
    ) -> Path:
        start_frame, out_path = Path(start_frame), Path(out_path)
        if not start_frame.is_file():
            raise FileNotFoundError(f"MotionEngine start_frame does not exist: {start_frame}")
        if duration <= 0:
            raise ValueError("MotionEngine duration must be positive")
        block = self._block_number(out_path)
        try:
            # A local Ken-Burns render has no image-conditioned terminal frame.  The
            # endpoint remains in the neutral signature so factory callers never need a
            # special local code path; continuity is assembled by the editor layer.
            return await asyncio.to_thread(self.engine.render, start_frame, out_path, block, duration)
        except Exception as exc:
            raise ProviderError(f"motion_engine failed for block {block}: {type(exc).__name__}") from exc

    @staticmethod
    def _block_number(out_path: Path) -> int:
        match = re.search(r"block(\d+)", out_path.stem, flags=re.IGNORECASE)
        return int(match.group(1)) if match else 1
