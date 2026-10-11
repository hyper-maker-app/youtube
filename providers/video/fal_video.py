"""Fal.ai image-to-video adapter and queue client extracted from the legacy layer."""

from __future__ import annotations

import asyncio
import base64
import os
import random
import time
from pathlib import Path
from typing import Any

import httpx

from providers.base import BaseVideoProvider, ConfigurationError, ProviderError


_MODELS = {
    "h3_max": "fal-ai/minimax/h3-max/image-to-video",
    "kling_pro": "fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
    "veo_fast": "fal-ai/veo3.1/fast/image-to-video",
    "hailuo": "fal-ai/minimax/hailuo-02/standard/image-to-video",
    "wan": "fal-ai/wan/v2.2-a14b/image-to-video",
}


class FalQueueClient:
    """Small fail-closed client for Fal's queue endpoints."""

    def __init__(self, api_key: str, queue_base_url: str, *, client: httpx.AsyncClient | None = None) -> None:
        self.api_key = api_key
        self.queue_base_url = queue_base_url.rstrip("/")
        self.client = client
        self._owns_client = client is None

    async def __aenter__(self) -> "FalQueueClient":
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=httpx.Timeout(90.0), follow_redirects=True)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client and self.client is not None:
            await self.client.aclose()

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Key {self.api_key}", "Content-Type": "application/json"}

    async def run(self, model_id: str, payload: dict[str, Any], timeout: float = 900.0) -> dict[str, Any]:
        if self.client is None:
            raise RuntimeError("FalQueueClient must be used as an async context manager")
        response = await self.client.post(f"{self.queue_base_url}/{model_id}", headers=self.headers, json=payload)
        if response.status_code >= 400:
            raise ProviderError(f"fal submit failed with HTTP {response.status_code}")
        handle = response.json()
        started = time.monotonic()
        while True:
            if time.monotonic() - started > timeout:
                raise ProviderError("fal video operation timed out")
            status_url = handle.get("status_url")
            response_url = handle.get("response_url")
            if not status_url or not response_url:
                raise ProviderError("fal submit response had no queue URLs")
            status = await self.client.get(status_url, headers=self.headers)
            if status.status_code >= 400:
                raise ProviderError(f"fal status failed with HTTP {status.status_code}")
            state = str((status.json() or {}).get("status") or "")
            if state == "COMPLETED":
                completed = await self.client.get(response_url, headers=self.headers)
                if completed.status_code >= 400:
                    raise ProviderError(f"fal response failed with HTTP {completed.status_code}")
                return completed.json()
            if state not in {"IN_QUEUE", "IN_PROGRESS"}:
                raise ProviderError(f"fal job ended with unexpected status {state!r}")
            await asyncio.sleep(5)

    async def download(self, url: str, out_path: Path) -> Path:
        if self.client is None:
            raise RuntimeError("FalQueueClient must be used as an async context manager")
        response = await self.client.get(url)
        if response.status_code >= 400 or not response.content:
            raise ProviderError("fal video download failed")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(response.content)
        return out_path

    @staticmethod
    def image_data_url(path: Path) -> str:
        suffix = Path(path).suffix.casefold()
        mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
        return f"data:{mime};base64,{base64.b64encode(Path(path).read_bytes()).decode('ascii')}"


class FalVideoProvider(BaseVideoProvider):
    """Fal I2V adapter pinned to one user-selected model; no cross-model fallback."""

    def __init__(
        self, *, api_key: str | None = None, queue_base_url: str | None = None,
        motion_model: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("FAL_KEY")
        self.queue_base_url = queue_base_url or os.getenv("FAL_QUEUE_BASE_URL")
        self.motion_model = (motion_model or os.getenv("FAL_VIDEO_MODEL") or "h3_max").casefold().replace("-", "_")
        missing = [name for name, value in (("FAL_KEY", self.api_key), ("FAL_QUEUE_BASE_URL", self.queue_base_url)) if not value]
        if missing:
            raise ConfigurationError("fal provider requires: " + ", ".join(missing) + ". Configure them in .env.")
        if self.motion_model not in _MODELS:
            raise ConfigurationError(f"fal provider does not support FAL_VIDEO_MODEL={self.motion_model!r}")

    async def animate_block(
        self, start_frame: Path, end_frame: Path | None, motion_prompt: str,
        out_path: Path, duration: float = 5.0,
    ) -> Path:
        start_frame = Path(start_frame)
        if not start_frame.is_file():
            raise FileNotFoundError(f"Fal start_frame does not exist: {start_frame}")
        if end_frame is not None and not Path(end_frame).is_file():
            raise FileNotFoundError(f"Fal end_frame does not exist: {end_frame}")
        if not motion_prompt.strip() or duration <= 0:
            raise ValueError("Fal requires a motion prompt and a positive native duration")
        payload = self._payload(start_frame, Path(end_frame) if end_frame else None, motion_prompt, duration)
        async with FalQueueClient(self.api_key, self.queue_base_url) as client:
            result = await client.run(_MODELS[self.motion_model], payload)
            url = ((result.get("video") or {}).get("url"))
            if not url:
                raise ProviderError("fal returned no video URL")
            return await client.download(str(url), Path(out_path))

    def _payload(self, start_frame: Path, end_frame: Path | None, prompt: str, duration: float) -> dict[str, Any]:
        image_url = FalQueueClient.image_data_url(start_frame)
        seconds = int(round(duration))
        aspect_ratio = os.getenv("FAL_ASPECT_RATIO", "9:16")
        if self.motion_model == "veo_fast":
            payload: dict[str, Any] = {"prompt": prompt, "image_url": image_url, "aspect_ratio": aspect_ratio, "duration": f"{seconds}s", "generate_audio": False}
            if end_frame is not None:
                # The dedicated first-last endpoint is intentionally not selected here:
                # factory selection pins the named provider/model for the entire run.
                payload["last_frame_url"] = FalQueueClient.image_data_url(end_frame)
            return payload
        if self.motion_model == "kling_pro":
            payload = {"prompt": prompt, "image_url": image_url, "duration": str(seconds), "cfg_scale": 0.5}
            if end_frame is not None:
                payload["tail_image_url"] = FalQueueClient.image_data_url(end_frame)
            return payload
        if self.motion_model == "wan":
            payload = {"prompt": prompt, "image_url": image_url, "aspect_ratio": aspect_ratio, "seed": random.randint(0, 2**31 - 1), "num_frames": seconds * 24 + 1, "frames_per_second": 24}
        else:
            payload = {"prompt": prompt, "image_url": image_url, "duration": seconds, "resolution": "720p"}
        if end_frame is not None:
            payload["end_image_url"] = FalQueueClient.image_data_url(end_frame)
        return payload
