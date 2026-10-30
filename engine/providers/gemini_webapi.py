"""Integration for local gemini-web2api sidecar using Google Pro account via Chrome CDP."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config

logger = logging.getLogger(__name__)

PORT = 8085
BASE_URL = f"http://127.0.0.1:{PORT}/v1"
API_KEY = "local-gemini-key"
VENDOR_DIR = config.ROOT / "vendor" / "gemini_webapi"
COOKIE_FILE = VENDOR_DIR / "cookies.txt"
BINARY = VENDOR_DIR / "bin" / "gemini-web2api.exe"


def kill_server() -> None:
    """Terminate any running gemini-web2api process."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/IM", "gemini-web2api.exe"], capture_output=True, check=False)
    time.sleep(0.5)


async def extract_google_cookies(cdp_port: int = 9223) -> str:
    """Extract live Google authentication cookies from the running Chrome CDP session."""
    from playwright.async_api import async_playwright

    cdp_url = f"http://127.0.0.1:{cdp_port}"
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url)
        try:
            ctx = browser.contexts[0]
            cookies = await ctx.cookies(["https://google.com", "https://gemini.google.com"])
            if not cookies:
                raise RuntimeError("No Google cookies found in Chrome CDP session")

            header_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
            VENDOR_DIR.mkdir(parents=True, exist_ok=True)
            COOKIE_FILE.write_text(header_str, encoding="utf-8")
            logger.info("Synchronized %d Google cookies to %s", len(cookies), COOKIE_FILE)
            return header_str
        finally:
            await browser.close()


def sync_cookies_sync(cdp_port: int = 9223) -> str:
    """Synchronous wrapper for extract_google_cookies."""
    return asyncio.run(extract_google_cookies(cdp_port))


def is_server_alive() -> bool:
    """Check if the gemini-web2api daemon is responding on port 8085."""
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/models",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def ensure_server_running(cdp_port: int = 9223, force_refresh: bool = False) -> None:
    """Ensure gemini-web2api daemon is alive, syncing cookies and spawning if necessary."""
    if force_refresh:
        kill_server()
    elif is_server_alive():
        return

    if not BINARY.is_file():
        raise RuntimeError(f"gemini-web2api binary missing at {BINARY}")

    try:
        sync_cookies_sync(cdp_port=cdp_port)
    except Exception as exc:
        logger.warning("Could not refresh cookies from CDP (%s); using existing file if available", exc)

    if not COOKIE_FILE.is_file() or COOKIE_FILE.stat().st_size == 0:
        raise RuntimeError(f"Cookie file missing or empty at {COOKIE_FILE}")

    cmd = [
        str(BINARY),
        "-port", str(PORT),
        "-cookie-file", str(COOKIE_FILE),
        "-api-key", API_KEY,
    ]
    logger.info("Spawning gemini-web2api server on port %d...", PORT)
    subprocess.Popen(
        cmd,
        cwd=str(BINARY.parent.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )

    for _ in range(24):
        time.sleep(0.5)
        if is_server_alive():
            logger.info("gemini-web2api server is now ready on port %d", PORT)
            return

    raise RuntimeError(f"gemini-web2api failed to start on port {PORT} within timeout")


def _post_with_retry(payload: dict[str, Any], timeout: float = 60.0) -> dict[str, Any]:
    """Execute chat completion request with automatic cookie re-sync and daemon restart on failure."""
    ensure_server_running()

    data_bytes = json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    try:
        req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=data_bytes, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("gemini-web2api request failed (%s); refreshing cookies and restarting...", exc)
        ensure_server_running(force_refresh=True)
        req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=data_bytes, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


def call_gemini_vision(
    prompt: str,
    images: list[Path | str],
    *,
    model: str = "gemini-3.5-flash-lite",
    timeout: float = 60.0,
) -> str:
    """Send sampled video/image frames and prompt to local Gemini Pro/Flash endpoint."""
    content_parts: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

    for img in images:
        path = Path(img).resolve()
        if not path.is_file():
            continue
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        })

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content_parts}],
        "stream": False,
    }

    res = _post_with_retry(payload, timeout=timeout)
    return res["choices"][0]["message"]["content"]


def call_gemini_chat(
    prompt: str,
    *,
    model: str = "gemini-3.5-flash-lite",
    timeout: float = 60.0,
) -> str:
    """Send text prompt to local Gemini Pro/Flash endpoint."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    res = _post_with_retry(payload, timeout=timeout)
    return res["choices"][0]["message"]["content"]
