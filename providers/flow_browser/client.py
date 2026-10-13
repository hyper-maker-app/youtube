"""Autonomous Flow Browser Automation Client — provider-layer transport module.

Moved from services/flow_browser_automation.py to providers/flow_browser/client.py
to honour the AST-clean service-layer boundary contract (ADR-005).

Network imports (urllib.request, websockets) belong in providers/, not services/.
"""

from __future__ import annotations

import asyncio
import ctypes
import glob
import json
import logging
import os
import shutil
import time
import urllib.request
from pathlib import Path
from typing import Any

import websockets

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path("C:/Users/bekir/OneDrive/Masaüstü/flow-agent/flow-agent/output")
DOWNLOADS_DIR = Path(os.path.expanduser("~/Downloads"))


class FlowBrowserClient:
    """Zero-manual-intervention autonomous browser client for Google Flow."""

    def __init__(self, ws_url: str = "ws://127.0.0.1:9222", timeout_seconds: int = 240):
        self.ws_url = ws_url
        self.timeout_seconds = timeout_seconds

    # -------------------------------------------------------------------------
    # Win32 Window Focus Utilities
    # -------------------------------------------------------------------------
    @staticmethod
    def focus_flow_window() -> bool:
        """Bring the open Google Flow Chrome window to the foreground."""
        try:
            user32 = ctypes.windll.user32
            hdesk = user32.OpenDesktopW("default", 0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)

            chrome_hwnd = None

            def enum_cb(hwnd, lparam):
                nonlocal chrome_hwnd
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        if "Google Flow" in buff.value and "Chrome" in buff.value:
                            chrome_hwnd = hwnd
                            return 0
                return 1

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

            if chrome_hwnd:
                user32.keybd_event(0x12, 0, 0, 0)  # ALT down
                user32.keybd_event(0x12, 0, 2, 0)  # ALT up
                user32.ShowWindow(chrome_hwnd, 9)  # SW_RESTORE
                user32.BringWindowToTop(chrome_hwnd)
                user32.SetForegroundWindow(chrome_hwnd)
                time.sleep(0.4)
                return True
        except Exception as e:
            logger.warning(f"Could not focus Chrome window via Win32: {e}")
        return False

    # -------------------------------------------------------------------------
    # Strategy 1: WebSocket Extension Bridge (Trusted CDP)
    # -------------------------------------------------------------------------
    async def _generate_via_bridge(
        self, prompt: str, out_path: Path, asset_type: str = "video", aspect: str = "16:9"
    ) -> Path | None:
        """Attempt generation through the Chrome extension bridge on port 9222."""
        initial_assets: set[str] = set()
        new_asset_url: str | None = None
        stop_event = asyncio.Event()

        async def handler(websocket):
            nonlocal new_asset_url
            logger.info("[FLOW BROWSER] Extension connected to bridge on 9222.")

            # 1. Snapshot initial assets
            poll_req = {"id": "poll-init", "op": "flow.ui.poll", "params": {}}
            await websocket.send(json.dumps(poll_req))
            async for m in websocket:
                d = json.loads(m)
                if d.get("id") == "poll-init":
                    res = d.get("result", {})
                    for img in res.get("images", []):
                        if img.get("src"):
                            initial_assets.add(img["src"])
                    for v in res.get("videos", []):
                        if v.get("src"):
                            initial_assets.add(v["src"])
                    break

            # 2. Type prompt and configure aspect
            gen_req = {
                "id": "gen-type",
                "op": "flow.ui.generate",
                "params": {"prompt": prompt, "aspect": aspect},
            }
            await websocket.send(json.dumps(gen_req))
            async for m in websocket:
                d = json.loads(m)
                if d.get("id") == "gen-type":
                    break

            # 3. Wait and dispatch trusted CDP click
            await asyncio.sleep(0.4)
            click_req = {"id": "gen-click", "op": "flow.ui.click_btn", "params": {}}
            await websocket.send(json.dumps(click_req))
            async for m in websocket:
                d = json.loads(m)
                if d.get("id") == "gen-click":
                    break

            # 4. Poll until completion
            start_time = time.time()
            while time.time() - start_time < self.timeout_seconds:
                await asyncio.sleep(3.5)
                pid = {"id": f"poll-{int(time.time())}", "op": "flow.ui.poll", "params": {}}
                await websocket.send(json.dumps(pid))

                async for m in websocket:
                    d = json.loads(m)
                    if d.get("id") == pid["id"]:
                        res = d.get("result", {})
                        if asset_type == "video":
                            for v in res.get("videos", []):
                                src = v.get("src", "")
                                if src and src not in initial_assets:
                                    new_asset_url = src
                                    break
                        else:
                            for img in res.get("images", []):
                                src = img.get("src", "")
                                if src and src not in initial_assets and "googleusercontent" not in src:
                                    new_asset_url = src
                                    break
                        break

                if new_asset_url:
                    break

            stop_event.set()

        try:
            server = await websockets.serve(handler, "127.0.0.1", 9222)
        except Exception:
            return None

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=self.timeout_seconds + 10)
        except asyncio.TimeoutError:
            pass
        finally:
            server.close()
            await server.wait_closed()

        if new_asset_url:
            logger.info(f"[FLOW BROWSER] Downloading asset from CDN to {out_path}...")
            urllib.request.urlretrieve(new_asset_url, str(out_path))
            return out_path

        return None

    # -------------------------------------------------------------------------
    # Strategy 2: Direct UI Automation (PyAutoGUI + Clipboard)
    # -------------------------------------------------------------------------
    def _generate_via_ui(
        self, prompt: str, out_path: Path, asset_type: str = "video", aspect: str = "16:9"
    ) -> Path:
        """Direct OS-level UI automation fallback on the open Google Flow window."""
        import pyautogui
        import pyperclip

        pyautogui.FAILSAFE = False

        logger.info(f"[FLOW BROWSER UI] Submitting {asset_type} prompt directly to Google Flow window...")
        focused = self.focus_flow_window()
        if not focused:
            raise RuntimeError("Google Flow Chrome window is not found or not open.")

        time.sleep(0.4)
        input_x, input_y = 700, 850
        pyautogui.click(input_x, input_y)
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.15)
        pyautogui.press("backspace")
        time.sleep(0.15)
        pyperclip.copy(prompt)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)
        btn_x, btn_y = 1310, 940
        pyautogui.click(btn_x, btn_y)
        time.sleep(1.0)
        pyautogui.press("enter")
        logger.info("[FLOW BROWSER UI] Generation submitted. Waiting for completion...")

        wait_interval = 5.0
        max_wait = self.timeout_seconds
        elapsed = 0
        latest_file = None
        out_parent = Path("C:/Users/bekir/OneDrive/Masaüstü/flow-agent/flow-agent/output")
        before_files = set(glob.glob(str(out_parent / "*"))) | set(glob.glob(str(DOWNLOADS_DIR / "*")))

        while elapsed < max_wait:
            time.sleep(wait_interval)
            elapsed += wait_interval
            current_files = set(glob.glob(str(out_parent / "*"))) | set(glob.glob(str(DOWNLOADS_DIR / "*")))
            new_files = current_files - before_files
            for f in new_files:
                p = Path(f)
                if asset_type == "video" and p.suffix.lower() == ".mp4" and p.stat().st_size > 100_000:
                    latest_file = p
                    break
                elif asset_type == "image" and p.suffix.lower() in [".jpg", ".jpeg", ".png"] and p.stat().st_size > 50_000:
                    latest_file = p
                    break
            if latest_file:
                logger.info(f"[FLOW BROWSER UI] Detected new asset: {latest_file.name}")
                shutil.copy2(str(latest_file), str(out_path))
                return out_path

        logger.info("[FLOW BROWSER UI] Polling timeout reached, checking top-left card in Flow UI...")
        try:
            self.focus_flow_window()
            time.sleep(0.5)
            pyautogui.click(360, 400)
            time.sleep(1.0)
            pyautogui.click(832, 180)
            time.sleep(3.0)
            pyautogui.click(25, 180)
            time.sleep(0.5)
            downloaded = sorted(glob.glob(str(DOWNLOADS_DIR / "*")), key=os.path.getmtime, reverse=True)
            if downloaded:
                cand = Path(downloaded[0])
                if time.time() - cand.stat().st_mtime < 30:
                    shutil.copy2(str(cand), str(out_path))
                    return out_path
        except Exception as e:
            logger.warning(f"Fallback UI download failed: {e}")

        raise RuntimeError(f"Timed out waiting for Flow {asset_type} generation.")

    # -------------------------------------------------------------------------
    # Public Entrypoint
    # -------------------------------------------------------------------------
    async def generate_asset(
        self,
        prompt: str,
        out_path: Path | str,
        asset_type: str = "video",
        aspect: str = "16:9",
    ) -> Path:
        """Generate asset using Chrome extension bridge if attached, or UI fallback."""
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"[FLOW BROWSER] Starting {asset_type} generation (aspect={aspect})")

        # 1. Try Playwright CDP First (Zero mouse movements)
        client = None
        try:
            from services.playwright_flow_client import PlaywrightFlowClient
            client = PlaywrightFlowClient()
            res = await client.generate_asset(prompt, out_path, asset_type, aspect)
            if res and res.is_file():
                return res
        except Exception as e:
            logger.info(f"[FLOW BROWSER] Playwright CDP failed ({e}), falling back to extension bridge.")
        finally:
            if client is not None:
                try:
                    await client.close()
                except Exception:
                    pass

        # 2. Try WebSocket Extension Bridge second (Zero mouse movements)
        try:
            res = await self._generate_via_bridge(prompt, out_path, asset_type, aspect)
            if res and res.is_file():
                return res
        except Exception as e:
            logger.info(f"[FLOW BROWSER] Extension bridge not responding ({e}), falling back to UI automation.")

        # 3. Fallback to Direct UI Automation isolated on Virtual Desktop
        from services.virtual_desktop_runner import VirtualDesktopRunner
        loop = asyncio.get_running_loop()

        def _run_ui() -> Path:
            return self._generate_via_ui(prompt, out_path, asset_type, aspect)

        return await loop.run_in_executor(None, lambda: VirtualDesktopRunner.run_isolated(_run_ui))
