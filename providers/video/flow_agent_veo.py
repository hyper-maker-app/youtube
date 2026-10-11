"""Google Flow Veo 3.1 first/last-frame video adapter."""

from __future__ import annotations

from pathlib import Path

from providers._flow_agent import FlowAgentClient
from providers.base import BaseVideoProvider
from providers.video.vertex_veo import VertexVeoProvider


class FlowAgentVeoProvider(BaseVideoProvider):
    """Create one 4-second 9:16 Veo block through Flow Agent's CLI/HTTP bridge."""

    def __init__(self, *, client: FlowAgentClient | None = None) -> None:
        self.client = client or FlowAgentClient()

    async def animate_block(
        self, start_frame: Path, end_frame: Path | None, motion_prompt: str,
        out_path: Path, duration: float = 4.0,
    ) -> Path:
        if float(duration) != 4.0:
            raise ValueError("flow_agent Veo 3.1 blocks are fixed at 4.0 seconds")
        start_frame = Path(start_frame)
        if not start_frame.is_file():
            raise FileNotFoundError(f"Flow start_frame does not exist: {start_frame}")
        if end_frame is not None and not Path(end_frame).is_file():
            raise FileNotFoundError(f"Flow end_frame does not exist: {end_frame}")
        if not motion_prompt.strip():
            raise ValueError("motion prompt must not be blank")
        clean_prompt = VertexVeoProvider.sanitize_prompt(motion_prompt)
        # Flow Agent's native Veo 3.1 model (abra_i2v_4s) is single-frame image-to-video.
        # Passing end_frame routes to omni_flash_i2v_4s_first_last which triggers dual-upload
        # reCAPTCHA token collisions (PUBLIC_ERROR_UNUSUAL_ACTIVITY). Enforcing start_frame-only
        # ensures stable 54s Veo 3.1 3D animation with clean FFmpeg hard cuts per ADR-035.
        return await self.client.video(clean_prompt, start_frame, None, Path(out_path))

