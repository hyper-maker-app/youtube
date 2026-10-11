"""Small, provider-owned bridge for the local `kodelyx/flow-agent` service.

The upstream project supports both a ``flow`` CLI and an OpenAI-compatible HTTP
server.  Keeping the transport here means image and video adapters share the same
failure semantics without making Flow's browser-session state part of the pipeline.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import shlex
from pathlib import Path
from typing import Any

import httpx

from .base import ConfigurationError, HandoffPending


class FlowAgentClient:
    """Invoke the explicitly configured Flow Agent CLI or local HTTP bridge."""

    def __init__(
        self,
        *,
        session_token: str | None = None,
        cli_path: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.session_token = session_token or os.getenv("FLOW_AGENT_SESSION_TOKEN")
        self.cli_path = cli_path or os.getenv("FLOW_AGENT_CLI_PATH")
        self.base_url = (base_url or os.getenv("FLOW_AGENT_BASE_URL") or "").rstrip("/")
        if not self.session_token and not self.cli_path:
            raise ConfigurationError(
                "flow_agent provider requires FLOW_AGENT_SESSION_TOKEN or FLOW_AGENT_CLI_PATH. "
                "Configure one in .env."
            )
        if self.session_token and not self.cli_path and not self.base_url:
            raise ConfigurationError(
                "flow_agent HTTP mode requires FLOW_AGENT_BASE_URL. Configure it in .env."
            )

    @staticmethod
    def idempotency_key(kind: str, prompt: str, seed: int = 0) -> str:
        digest = hashlib.sha256(f"{kind}\0{seed}\0{prompt}".encode("utf-8")).hexdigest()
        return f"youtube-{kind}-{digest[:32]}"

    @staticmethod
    def data_url(path: Path) -> str:
        path = Path(path)
        mime = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
        }.get(path.suffix.casefold())
        if not mime:
            raise ValueError(f"Unsupported Flow image type: {path.suffix}")
        return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"

    async def image(self, prompt: str, out_path: Path, seed: int, reference_image: Path | None = None,
                    reference_images: list[Path] | None = None, aspect_ratio: str = "9:16") -> Path:
        aspect = {
            "9:16": "portrait",
            "16:9": "landscape",
            "2:3": "2:3",
            "3:2": "3:2",
            "1:1": "square",
        }.get(aspect_ratio)
        if aspect is None:
            raise ValueError(f"Unsupported Flow image aspect ratio: {aspect_ratio}")
        model = os.getenv("FLOW_IMAGE_MODEL", "beluga")
        args = [
            "image", prompt, "--model", model, "--aspect", aspect, "--count", "1",
            "--idempotency-key", self.idempotency_key("image", prompt, seed), "--output", str(out_path),
        ]
        payload = {
            "prompt": prompt, "model": model, "n": 1, "aspect_ratio": aspect_ratio, "response_format": "url",
        }
        references = list(reference_images or [])
        if reference_image is not None:
            references.append(reference_image)
        if references:
            encoded: list[str] = []
            for reference in references:
                reference = Path(reference)
                if not reference.is_file() or reference.stat().st_size <= 0:
                    raise ValueError("Flow image reference must be a non-empty image file")
                args.extend(["--reference", str(reference)])
                encoded.append(self.data_url(reference))
            # The bridge owns its media transport.  CLI mode receives a concrete
            # local reference; HTTP mode receives an explicit image payload.  If an
            # installed Flow Agent lacks either feature it writes a handoff rather
            # than silently reverting to unrelated text-only keyframes.
            payload["reference_images_base64"] = encoded
        return await self._deliver("image", args, payload, out_path)

    async def video(
        self, prompt: str, start_frame: Path, end_frame: Path | None, out_path: Path,
    ) -> Path:
        import config
        video_aspect = "landscape" if getattr(config, "LONGFORM_MODE", False) else "portrait"
        args = [
            "video", prompt, "--aspect", video_aspect, "--duration", "4", "--start", str(start_frame),
        ]
        if end_frame is not None:
            args.extend(["--end", str(end_frame)])
        args.extend([
            "--idempotency-key", self.idempotency_key("video", prompt), "--output", str(out_path),
        ])
        payload: dict[str, Any] = {
            "prompt": prompt, "aspect": video_aspect, "duration": 4, "n": 1,
            "start_image": str(Path(start_frame).resolve()),
        }
        if end_frame is not None:
            payload["end_image"] = str(Path(end_frame).resolve())
        return await self._deliver("video", args, payload, out_path)

    async def _deliver(
        self, kind: str, args: list[str], payload: dict[str, Any], out_path: Path,
    ) -> Path:
        out_path = Path(out_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self.cli_path:
                await self._run_cli(args)
            else:
                await self._run_http(kind, payload, out_path)
            if not out_path.is_file() or out_path.stat().st_size == 0:
                raise RuntimeError("Flow Agent reported success but did not write the requested output")
            return out_path
        except HandoffPending:
            raise
        except Exception as exc:
            handoff = self._write_handoff(kind, args, out_path, exc)
            raise HandoffPending(
                f"Flow Agent {kind} generation is pending after {type(exc).__name__}", handoff,
            ) from exc

    async def _run_cli(self, args: list[str]) -> None:
        command = self.cli_path or "flow"
        env = dict(os.environ)
        if self.session_token:
            # Some older Flow Agent bridges read this value directly.  It never appears
            # in subprocess arguments, stdout, exceptions, or manual handoff files.
            env["FLOW_AGENT_SESSION_TOKEN"] = self.session_token
        try:
            process = await asyncio.create_subprocess_exec(
                command, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env,
            )
        except OSError as exc:
            raise RuntimeError("Flow Agent CLI could not start") from exc
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            detail = (stderr or stdout).decode("utf-8", errors="replace").strip()
            # Exit 3/4 are upstream's documented bridge/session readiness failures;
            # all errors become a manual handoff because replaying a video is billable.
            raise RuntimeError(f"Flow Agent CLI exited {process.returncode}: {detail[:400]}")

    async def _run_http(self, kind: str, payload: dict[str, Any], out_path: Path) -> None:
        headers = {
            "Authorization": f"Bearer {self.session_token}",
            "X-Flow-Agent-Session-Token": str(self.session_token),
            "Idempotency-Key": self.idempotency_key(kind, str(payload.get("prompt") or "")),
        }
        endpoint = "/v1/images/generations" if kind == "image" else "/v1/videos/generations"
        async with httpx.AsyncClient(timeout=httpx.Timeout(900.0, connect=60.0), follow_redirects=True) as client:
            if kind == "video" and payload.get("end_image_base64"):
                uploaded = await client.post(
                    f"{self.base_url}/v1/upload", headers=headers,
                    json={"image_base64": payload.pop("end_image_base64")},
                )
                if uploaded.status_code >= 400:
                    raise RuntimeError(f"Flow Agent endpoint-frame upload HTTP {uploaded.status_code}")
                endpoint_id = str((uploaded.json() or {}).get("media_id") or "")
                if not endpoint_id:
                    raise RuntimeError("Flow Agent endpoint-frame upload returned no media_id")
                payload["end_media_id"] = endpoint_id
            response = None
            for attempt in range(4):
                try:
                    response = await client.post(f"{self.base_url}{endpoint}", headers=headers, json=payload)
                    if response.status_code < 400:
                        break
                    detail = response.text if len(response.text) <= 500 else f"{response.text[:150]} ... {response.text[-350:]}"
                    if response.status_code in {429, 500, 502, 503, 504} and attempt < 3:
                        wait_sec = 45 * (attempt + 1)
                        await asyncio.sleep(wait_sec)
                        continue
                    raise RuntimeError(f"Flow Agent HTTP {response.status_code}: {detail}")
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    if attempt < 3:
                        await asyncio.sleep(15 * (attempt + 1))
                        continue
                    raise RuntimeError(f"Flow Agent network timeout: {exc}") from exc
            if response is None or response.status_code >= 400:
                raise RuntimeError("Flow Agent HTTP request failed")
            result = response.json()
            if kind == "video":
                result = await self._poll_video(client, result, headers)
            url = self._output_url(result)
            media = await client.get(url)
            if media.status_code >= 400 or not media.content:
                raise RuntimeError("Flow Agent media download failed")
            out_path.write_bytes(media.content)

    async def _poll_video(
        self, client: httpx.AsyncClient, result: dict[str, Any], headers: dict[str, str],
    ) -> dict[str, Any]:
        job_id = str(result.get("job_id") or result.get("id") or "")
        if not job_id:
            return result
        for _ in range(225):
            await asyncio.sleep(4)
            response = await client.get(f"{self.base_url}/v1/videos/generations/{job_id}", headers=headers)
            if response.status_code >= 400:
                raise RuntimeError(f"Flow Agent video poll HTTP {response.status_code}")
            result = response.json()
            status = str(result.get("status") or "").casefold()
            if status in {"succeeded", "completed", "success"}:
                return result
            if status in {"failed", "cancelled", "canceled"}:
                raise RuntimeError(f"Flow Agent video job {status}")
        raise RuntimeError("Flow Agent video polling timed out")

    @staticmethod
    def _output_url(result: dict[str, Any]) -> str:
        candidates: list[Any] = [
            result.get("url"), result.get("download_url"), result.get("video"), result.get("data"), result.get("output"),
        ]
        while candidates:
            value = candidates.pop(0)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
            if isinstance(value, dict):
                candidates.extend(value.get(key) for key in ("url", "download_url", "video", "data") if key in value)
            elif isinstance(value, list):
                candidates.extend(value)
        raise RuntimeError("Flow Agent response contained no downloadable media URL")

    @staticmethod
    def _handoff_root(out_path: Path) -> Path:
        return out_path.parent.parent if out_path.parent.name in {"blocks", "keyframes"} else out_path.parent

    def _write_handoff(self, kind: str, args: list[str], out_path: Path, exc: BaseException) -> Path:
        handoff = self._handoff_root(out_path) / "handoff.md"
        command = " ".join(shlex.quote(part) for part in ((self.cli_path or "flow"), *args))
        entry = (
            f"\n## Flow Agent {kind}: {out_path.name}\n\n"
            f"The automated request stopped before `{out_path}` was written. The Flow session, cookie, "
            "extension bridge, or CLI needs attention; no alternate provider was selected.\n\n"
            "1. Open Google Flow, confirm the Flow Agent extension/bridge is ready, then run:\n\n"
            f"```powershell\n{command}\n```\n\n"
            f"2. Confirm the output exists at `{out_path}` and resume this pipeline run.\n\n"
            f"Recorded failure: `{type(exc).__name__}`.\n"
        )
        handoff.parent.mkdir(parents=True, exist_ok=True)
        with handoff.open("a", encoding="utf-8") as stream:
            stream.write(entry)
        return handoff
