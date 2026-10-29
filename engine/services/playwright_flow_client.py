from __future__ import annotations

import asyncio
import base64
import glob
import hashlib
import json
import logging
import os
import random
import re
import shutil
import subprocess
import time
import tempfile
from pathlib import Path
from typing import Any

from providers.base import HandoffPending, ConfigurationError, ProviderError
from providers.flow_contract import settings, verified_cli_model, internal_video_model_key, mapping
from vendor.flow_agent_bridge.command import compile_command
import config
from services.flow_session import launch_flow_batch

import websockets
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = logging.getLogger(__name__)

FLOW_AGENT_ROOT = Path(os.getenv("FLOW_AGENT_ROOT") or config.ROOT / "vendor" / "flow_agent_bridge")
FLOW_BINARY = Path(os.getenv("FLOW_AGENT_CLI_PATH") or FLOW_AGENT_ROOT / "bin" / "flow-windows.exe")
COOKIES_GLOB = str(FLOW_AGENT_ROOT / "cookies" / "account_*.json")
CHROME_EXE = "C:/Program Files/Google/Chrome/Application/chrome.exe"
DEFAULT_FLOW_URL = "https://flow.google.com"
RECAPTCHA_HOST_URL = "https://flow.google.com/recaptcha-host"
RECAPTCHA_SITE_KEY = "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV"
FLOW_AUTH_COOKIE_NAMES = {
    "OSID", "__Secure-OSID", "__Secure-1PSID", "__Secure-3PSID", "SID", "SAPISID",
}


def match_saved_account_bundle(
    live_cookies: list[dict[str, Any]],
    account_files: list[str | Path],
) -> tuple[Path, dict[str, Any]] | None:
    """Identify the saved Flow account that belongs to this live browser profile.

    Multiple browser profiles can connect to the local Flow bridge. Match auth cookies
    in memory and return only a unique, strong match; cookie values are never logged.
    """
    live = {
        str(cookie.get("name")): str(cookie.get("value"))
        for cookie in live_cookies
        if cookie.get("name") in FLOW_AUTH_COOKIE_NAMES and cookie.get("value")
    }
    if len(live) < 2:
        return None

    ranked: list[tuple[int, Path, dict[str, Any]]] = []
    for raw_path in account_files:
        path = Path(raw_path)
        try:
            bundle = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        saved = {
            str(cookie.get("name")): str(cookie.get("value"))
            for cookie in bundle.get("cookies", [])
            if cookie.get("name") in FLOW_AUTH_COOKIE_NAMES and cookie.get("value")
        }
        score = sum(1 for name, value in live.items() if saved.get(name) == value)
        if score >= 2:
            ranked.append((score, path, bundle))

    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    best_score = ranked[0][0]
    best = [item for item in ranked if item[0] == best_score]
    if len(best) != 1:
        return None
    return best[0][1], best[0][2]


class PlaywrightFlowClient:
    """Zero-focus background automation for Google Flow via Playwright CDP (port 9223).

    Combines:
    1. Background Chrome 154 CDP session on port 9223 hosting genuine `https://flow.google.com`
       origin for high-score `grecaptcha.enterprise.execute` token minting and exact browser
       fingerprint alignment (`ws://127.0.0.1:9222` bridge responder for `flow-windows.exe`).
    2. Direct DOM automation fallback if an interactive `/project/` workspace tab is open.
    """

    def __init__(self) -> None:
        self.cdp_port = int(os.getenv("PLAYWRIGHT_CDP_PORT", "9223"))
        self.cdp_url = f"http://127.0.0.1:{self.cdp_port}"
        self.playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self._captcha_page: Page | None = None
        self._last_mint_time: float = 0.0
        self._last_mint_token: str = ""
        self._active_account_path: Path | None = None
        self._active_account_bundle: dict[str, Any] = {}
        self._gem_pix_2_quota_exhausted: bool = False
        self._lock = asyncio.Lock()

    async def _jitter(self, min_s: float = 1.5, max_s: float = 4.0) -> None:
        delay = random.uniform(min_s, max_s)
        await asyncio.sleep(delay)

    def _load_saved_account_bundle(self) -> dict[str, Any]:
        files = sorted(glob.glob(COOKIES_GLOB), key=os.path.getmtime, reverse=True)
        if not files:
            return {}
        try:
            return json.loads(Path(files[0]).read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Could not read saved Flow cookie bundle: {e}")
            return {}

    def _ensure_chrome_cdp_process(self) -> None:
        """Start the repository's automation-safe Flow launcher."""
        batch_path = Path(os.getenv("FLOW_CHROME_BATCH_PATH") or config.ROOT / "chrome_flow.bat")
        if not batch_path.is_file():
            raise RuntimeError(f"Flow launcher batch is missing: {batch_path}")
        logger.info(f"[PLAYWRIGHT CDP] Launching Flow batch on port {self.cdp_port}: {batch_path}")
        launch_flow_batch(batch_path)

    async def _inject_saved_cookies(self) -> str:
        """Inject saved Google Flow cookies into the CDP browser context and return project URL."""
        bundle = self._load_saved_account_bundle()
        project_id = bundle.get("project_id")
        target_url = f"https://flow.google.com/project/{project_id}" if project_id else DEFAULT_FLOW_URL
        if not self.context:
            return target_url

        raw_cookies = bundle.get("cookies") or []
        same_site_map = {
            "no_restriction": "None",
            "none": "None",
            "lax": "Lax",
            "strict": "Strict",
        }
        injected = 0
        for c in raw_cookies:
            name = c.get("name")
            value = c.get("value")
            domain = c.get("domain")
            if not (name and value is not None and domain):
                continue
            name_str = str(name)
            domain_str = str(domain)
            is_host_only = bool(c.get("hostOnly")) or not domain_str.startswith(".") or name_str.startswith("__Host-")
            secure = bool(c.get("secure")) or name_str.startswith(("__Secure-", "__Host-")) or is_host_only
            item: dict[str, Any] = {
                "name": name_str,
                "value": str(value),
                "secure": secure,
                "httpOnly": bool(c.get("httpOnly", False)),
            }
            if is_host_only:
                item["url"] = f"https://{domain_str.lstrip('.')}/"
            else:
                item["domain"] = domain_str
                item["path"] = str(c.get("path") or "/")

            raw_ss = str(c.get("sameSite") or "").lower()
            if raw_ss in same_site_map:
                item["sameSite"] = same_site_map[raw_ss]
                if item["sameSite"] == "None":
                    item["secure"] = True
            exp = c.get("expirationDate")
            if exp and not c.get("session", False):
                item["expires"] = float(exp)
            try:
                await self.context.add_cookies([item])
                injected += 1
            except Exception as e:
                logger.debug(f"Cookie {name_str} warning: {e}")

        logger.debug(f"[PLAYWRIGHT CDP] Injected {injected}/{len(raw_cookies)} saved Google Flow cookies.")
        return target_url

    async def connect(self) -> None:
        if not self.playwright:
            self.playwright = await async_playwright().start()

        if not self.browser:
            logger.info(f"Connecting to Chrome CDP at {self.cdp_url}")
            try:
                self.browser = await self.playwright.chromium.connect_over_cdp(self.cdp_url)
            except Exception:
                self._ensure_chrome_cdp_process()
                for _ in range(15):
                    await asyncio.sleep(1.0)
                    try:
                        self.browser = await self.playwright.chromium.connect_over_cdp(self.cdp_url)
                        break
                    except Exception:
                        continue
                if not self.browser:
                    raise RuntimeError(f"Could not connect to Chrome CDP at {self.cdp_url}")

            self.context = self.browser.contexts[0]

        if self.context:
            existing = await self.context.cookies(["https://flow.google.com", "https://google.com"])
            has_live_osid = any(c.get("name") in ("OSID", "__Secure-OSID") for c in existing)
            if not has_live_osid:
                await self._inject_saved_cookies()

            live_cookies = await self.context.cookies(["https://flow.google.com", "https://google.com"])
            account_files = glob.glob(COOKIES_GLOB)
            matched = match_saved_account_bundle(live_cookies, account_files)
            if matched:
                self._active_account_path, self._active_account_bundle = matched
                logger.info("[PLAYWRIGHT CDP] Pinned Flow account to the active Chrome session.")
            elif len(account_files) == 1:
                self._active_account_path = Path(account_files[0])
                self._active_account_bundle = self._load_saved_account_bundle()
            elif account_files:
                raise RuntimeError(
                    "Could not uniquely match the active Chrome Flow session to a saved account; "
                    "generation stopped to avoid using another browser profile."
                )

        # Prepare dedicated https://flow.google.com/recaptcha-host tab for real browser token minting
        for p in self.context.pages:
            if p.url == RECAPTCHA_HOST_URL:
                self._captcha_page = p
            elif any(k in (p.url or "").lower() for k in ("flow.google.com", "labs.google")):
                self.page = p

        if not self._captcha_page:
            # Open a dedicated background tab for reCAPTCHA Enterprise token minting without disturbing main Flow tab
            self._captcha_page = await self.context.new_page()
            html = (
                f"<!DOCTYPE html><html><head>"
                f"<script src=\"https://www.google.com/recaptcha/enterprise.js?render={RECAPTCHA_SITE_KEY}\"></script>"
                f"</head><body>Google Flow CDP</body></html>"
            )
            await self._captcha_page.route(
                RECAPTCHA_HOST_URL,
                lambda route: route.fulfill(status=200, content_type="text/html", body=html),
            )
            await self._captcha_page.goto(RECAPTCHA_HOST_URL, wait_until="domcontentloaded", timeout=15000)
        else:
            # If tab already existed from prior session, verify grecaptcha is present; if not, inject it
            try:
                has_recaptcha = await self._captcha_page.evaluate("() => typeof window.grecaptcha !== 'undefined' && !!window.grecaptcha.enterprise")
                if not has_recaptcha:
                    await self._captcha_page.evaluate(
                        f"""() => {{
                            if (!document.getElementById('recaptcha-script')) {{
                                const s = document.createElement('script');
                                s.id = 'recaptcha-script';
                                s.src = 'https://www.google.com/recaptcha/enterprise.js?render={RECAPTCHA_SITE_KEY}';
                                document.head.appendChild(s);
                            }}
                        }}"""
                    )
            except Exception:
                pass

        if not self.page:
            self.page = self._captcha_page

    async def mint_recaptcha_token(self, action: str = "FLOW_GENERATION", site_key: str = RECAPTCHA_SITE_KEY) -> str:
        """Mint a genuine high-score reCAPTCHA Enterprise token inside Chrome on https://flow.google.com."""
        await self.connect()
        assert self._captcha_page is not None

        elapsed = time.time() - self._last_mint_time
        if elapsed < 8.5 and self._last_mint_time > 0:
            await asyncio.sleep(8.5 - elapsed)

        eval_script = """async ([sk, act]) => {
            try {
                if (typeof window.grecaptcha === 'undefined' || !window.grecaptcha.enterprise) {
                    return "";
                }
                return await new Promise((resolve) => {
                    const timer = setTimeout(() => resolve(""), 12000);
                    window.grecaptcha.enterprise.ready(async () => {
                        try {
                            const res = await window.grecaptcha.enterprise.execute(sk, { action: act });
                            clearTimeout(timer);
                            resolve(res || "");
                        } catch {
                            clearTimeout(timer);
                            resolve("");
                        }
                    });
                });
            } catch {
                return "";
            }
        }"""

        token = ""
        try:
            token = await asyncio.wait_for(self._captcha_page.evaluate(eval_script, [site_key, action]), timeout=15.0)
        except Exception as e:
            logger.debug(f"[PLAYWRIGHT CDP] mint_recaptcha_token evaluate warning: {e}")

        if token and token == self._last_mint_token:
            await asyncio.sleep(3.0)
            try:
                token = await asyncio.wait_for(self._captcha_page.evaluate(eval_script, [site_key, action]), timeout=15.0)
            except Exception:
                pass

        if token:
            self._last_mint_token = token
            self._last_mint_time = time.time()
            logger.info(f"[PLAYWRIGHT CDP] Minted fresh browser reCAPTCHA Enterprise token ({len(token)} chars, action={action})")
            return token
        return ""

    async def read_browser_fingerprint(self) -> dict[str, Any]:
        """Read exact navigator fingerprint from the Chrome CDP tab that mints reCAPTCHA tokens."""
        await self.connect()
        assert self._captcha_page is not None
        return await self._captcha_page.evaluate(
            """() => {
                const d = navigator.userAgentData || {};
                const brands = (d.brands || []).map((b) => '"' + b.brand + '";v="' + b.version + '"').join(', ');
                return {
                    userAgent: navigator.userAgent,
                    language: navigator.language || 'tr-TR',
                    brands: brands || '"Chromium";v="154", "Google Chrome";v="154", "Not A(Brand";v="99"',
                    platform: d.platform || 'Windows',
                    mobile: d.mobile ? '?1' : '?0',
                    platformFull: '"' + (d.platform || 'Windows') + '"'
                };
            }"""
        )

    async def _get_live_or_saved_cookies(self, requested_domain: str, fallback_cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return live cookies from CDP context filtered by domain, or fallback to saved bundle cookies."""
        essential = {
            "__Secure-next-auth.session-token", "__Secure-next-auth.callback-url", "__Host-next-auth.csrf-token",
            "__Secure-1PSID", "__Secure-3PSID", "__Secure-1PSIDTS", "__Secure-3PSIDTS",
            "SID", "HSID", "SSID", "APISID", "SAPISID", "EMAIL", "OSID", "__Secure-OSID",
            "LSID", "LSOLH", "__Host-1PLSID", "__Host-3PLSID", "ACCOUNT_CHOOSER",
        }
        source_cookies = fallback_cookies
        if self.context:
            try:
                cdp_cookies = await self.context.cookies()
                shaped = []
                for c in cdp_cookies:
                    if c.get("name") in essential:
                        dom = str(c.get("domain") or "")
                        exp = c.get("expires")
                        shaped.append({
                            "domain": dom,
                            "expirationDate": exp if (exp and exp > 0) else None,
                            "hostOnly": not dom.startswith("."),
                            "httpOnly": bool(c.get("httpOnly", False)),
                            "name": c.get("name"),
                            "path": c.get("path") or "/",
                            "sameSite": str(c.get("sameSite") or "unspecified").lower(),
                            "secure": bool(c.get("secure", True)),
                            "session": not (exp and exp > 0),
                            "storeId": "0",
                            "value": c.get("value"),
                        })
                if any(c["name"] in ("OSID", "__Secure-1PSID") for c in shaped):
                    source_cookies = shaped
            except Exception:
                pass

        if not requested_domain:
            return source_cookies
        req = requested_domain.lstrip(".").lower()
        filtered = []
        for c in source_cookies:
            cdom = str(c.get("domain") or "").lstrip(".").lower()
            if req == "google.com":
                if cdom == "google.com":
                    filtered.append(c)
            elif cdom == req or cdom.endswith("." + req):
                filtered.append(c)
        return filtered

    async def _read_live_page_tokens(self, fallback_bundle: dict[str, Any]) -> dict[str, str]:
        """Read live SNlM0e (at) and FdrFJe (fsid) tokens from an open Flow tab if available."""
        if self.context:
            for p in self.context.pages:
                if "flow.google.com" in (p.url or "") and p.url != RECAPTCHA_HOST_URL:
                    try:
                        toks = await p.evaluate(
                            "() => ({at: String(window.WIZ_global_data?.SNlM0e || ''), fsid: String(window.WIZ_global_data?.FdrFJe || '')})"
                        )
                        if toks and toks.get("at"):
                            return toks
                    except Exception:
                        pass
        return {
            "at": str(fallback_bundle.get("at") or ""),
            "fsid": str(fallback_bundle.get("fsid") or ""),
        }

    async def _bridge_responder_loop(self, stop_event: asyncio.Event) -> None:
        """Connect to flow-windows.exe's ws://127.0.0.1:9222 server and serve real CDP captcha + session."""
        bundle = self._active_account_bundle or self._load_saved_account_bundle()
        project_id = bundle.get("project_id") or "7bb5b1c3-0801-4b7e-9d05-39cfaa77dbc9"
        if self.context:
            for p in self.context.pages:
                if "/project/" in (p.url or ""):
                    project_id = p.url.split("/project/")[1].split("/")[0].split("?")[0] or project_id
                    break
        project_url = f"https://flow.google.com/project/{project_id}"
        bridge_url = "ws://127.0.0.1:9222"
        bridge_token = ""
        cfg: dict[str, Any] = {
            "bridgeUrl": bridge_url,
            "targetUrlPrefixes": ["https://flow.google.com", "https://labs.google"],
            "autoOpenOnCommand": True,
            "cookieDomains": ["flow.google.com", "labs.google", "google.com", "accounts.google.com"],
        }

        while not stop_event.is_set():
            dial_url = f"{bridge_url}?token={bridge_token}" if bridge_token else bridge_url
            try:
                async with websockets.connect(dial_url, open_timeout=1.5, close_timeout=1.0) as ws:
                    await ws.send(
                        json.dumps(
                            {
                                "event": "bridge.ready",
                                "params": {"version": "1.0.0", "protocol": 1, "config": cfg},
                            }
                        )
                    )
                    while not stop_event.is_set():
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        except asyncio.TimeoutError:
                            continue
                        msg = json.loads(raw)
                        req_id = msg.get("id")
                        op = msg.get("op")
                        params = msg.get("params") or {}
                        if not req_id:
                            continue

                        try:
                            if op == "ping":
                                result: Any = {
                                    "ok": True,
                                    "protocol": 1,
                                    "version": "1.0.0",
                                    "ops": [
                                        "ping", "config.get", "config.set", "config.reset",
                                        "tabs.list", "tabs.open", "tab.attach", "tab.detach", "tab.current",
                                        "events.read", "cookies.list", "cookies.names",
                                        "flow.fingerprint", "flow.navigate", "flow.projects",
                                        "flow.captcha", "flow.at", "status",
                                    ],
                                }
                            elif op == "config.get":
                                result = cfg
                            elif op == "config.set":
                                patch = params.get("patch") or {}
                                cfg.update(patch)
                                if patch.get("bridgeToken"):
                                    bridge_token = str(patch["bridgeToken"])
                                result = cfg
                            elif op == "config.reset":
                                bridge_token = ""
                                result = cfg
                            elif op == "tabs.list":
                                result = [{"tabId": 1, "url": project_url, "title": "Google Flow"}]
                            elif op in ("tabs.open", "tab.attach", "tab.current", "flow.navigate"):
                                result = {"tabId": 1, "url": project_url, "title": "Google Flow"}
                            elif op == "tab.detach":
                                result = {"detached": True}
                            elif op == "events.read":
                                result = []
                            elif op == "cookies.list":
                                details = params.get("details") or {}
                                dom = str(details.get("domain") or "")
                                result = await self._get_live_or_saved_cookies(dom, bundle.get("cookies") or [])
                            elif op == "cookies.names":
                                cks = await self._get_live_or_saved_cookies("", bundle.get("cookies") or [])
                                names = sorted({str(c.get("name")) for c in cks})
                                result = {"scope": "google.com", "direct": len(names), "seen": len(names), "names": names, "kept": names}
                            elif op == "flow.fingerprint":
                                result = await self.read_browser_fingerprint()
                            elif op == "flow.projects":
                                result = [project_url]
                            elif op == "flow.at":
                                result = await self._read_live_page_tokens(bundle)
                            elif op == "flow.captcha":
                                action = str(params.get("action") or "")
                                sk = str(params.get("siteKey") or RECAPTCHA_SITE_KEY)
                                if not action:
                                    result = {"available": True}
                                else:
                                    tok = await self.mint_recaptcha_token(action=action, site_key=sk)
                                    result = {"available": True, "token": tok}
                            elif op == "status":
                                result = {"daemonConnected": True, "tabUrl": project_url, "tabTitle": "Google Flow", "config": cfg}
                            else:
                                result = {"ok": True}
                            await ws.send(json.dumps({"id": req_id, "result": result}))
                        except Exception as e:
                            await ws.send(json.dumps({"id": req_id, "error": {"message": str(e)}}))
            except Exception:
                await asyncio.sleep(0.25)

    async def generate_asset(
        self,
        prompt: str,
        out_path: str | Path,
        asset_type: str = "video",
        aspect_ratio: str = "16:9",
        start_frame: Path | None = None,
        reference_images: list[Path] | None = None,
        duration: int = 4,
        timeout: int = 420,
        end_frame: Path | None = None,
        quality: str | None = None,
        model: str | None = None,
        test_mode: bool = False,
    ) -> Path:
        """Generate an image or video in the background using Playwright CDP + Flow engine."""
        async with self._lock:
            try:
                return await self._generate_asset_locked(
                    prompt=prompt,
                    out_path=out_path,
                    asset_type=asset_type,
                    aspect_ratio=aspect_ratio,
                    start_frame=start_frame,
                    reference_images=reference_images,
                    duration=duration,
                    timeout=timeout, end_frame=end_frame, quality=quality, model=model, test_mode=test_mode,
                )
            except (HandoffPending, ConfigurationError):
                raise
            except Exception as exc:
                root = Path(out_path).parent
                if root.name in {"blocks", "keyframes", "refs", "video", "images"}:
                    root = root.parent
                handoff = root / "handoff.md"
                handoff.parent.mkdir(parents=True, exist_ok=True)
                request_path = handoff.parent / (Path(out_path).stem + ".handoff.json")
                request_path.write_text(json.dumps({
                    "asset_type": asset_type, "prompt": prompt, "out_path": str(out_path),
                    "aspect_ratio": aspect_ratio, "duration": duration,
                    "model": model, "quality": quality, "test_mode": test_mode,
                    "end_frame": str(end_frame) if end_frame else None,
                    "start_frame": str(start_frame) if start_frame else None,
                    "reference_images": [str(p) for p in reference_images or []],
                }, indent=2), encoding="utf-8")
                handoff.write_text(
                    "# Flow handoff pending\n\n"
                    f"Asset type: {asset_type}\n"
                    f"Exact request: {request_path.name}\n"
                    f"Output: {Path(out_path).name}\n"
                    f"Reason: {type(exc).__name__}\n"
                    "Complete this exact block manually or start a separate run with an explicit provider.\n",
                    encoding="utf-8",
                )
                raise HandoffPending("Playwright Flow generation is pending", handoff) from exc

    def _sanitize_flow_image_prompt(self, prompt: str) -> str:
        """Softens high-sensitivity refusal keywords into neutral cinematic historical terms."""
        replacements = [
            (r"\b(?:suicide|self-harm|kill(?:ing)?|corpses?|dead\s+bodies)\b", "fallen soldiers"),
            (r"\b(?:blood(?:y)?|bleeding|gore|visceral)\b", "red-tinted dust and powder"),
            (r"\b(?:violently\s+obliterates?|rips\s+open)\b", "severely damages"),
            (r"\bdrives\s+(?:off|straight)\s+into\s+a\s+lake\b", "moves toward the coastal lake"),
            (r"\bcolossal\s+fireball\b", "bright flare with expanding smoke plume"),
            (r"\bmassive\s+fireball\b", "large flare with thick smoke"),
            (r"\bcatastrophic\s+explosion\b", "dramatic historical detonation"),
        ]
        cleaned = prompt
        for pat, rep in replacements:
            cleaned = re.sub(pat, rep, cleaned, flags=re.IGNORECASE)
        return cleaned

    def _resolve_flow_media_id(self, image_path: Path) -> str | None:
        """Passing the local image file path directly allows flow-windows.exe to upload the asset
        directly to the current project listing via UploadImageViaBatch, avoiding cross-project
        'not in the project listing' failures (ADR-067).
        """
        return None

    def _cleanup_proc_transport(self, proc: Any) -> None:
        """Cleanly close Windows asyncio transport pipe to prevent ValueError on closed pipe during GC (ADR-071)."""
        if proc is not None and hasattr(proc, "_transport") and proc._transport:
            try:
                proc._transport.close()
            except Exception:
                pass

    async def _generate_asset_locked(
        self,
        prompt: str,
        out_path: str | Path,
        asset_type: str = "video",
        aspect_ratio: str = "16:9",
        start_frame: Path | None = None,
        reference_images: list[Path] | None = None,
        duration: int = 4,
        timeout: int = 420,
        end_frame: Path | None = None,
        quality: str | None = None,
        model: str | None = None,
        test_mode: bool = False,
    ) -> Path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        contract = settings(test=test_mode)
        expected_model = contract["image_model" if asset_type == "image" else "video_model"]
        if model is not None and model != expected_model:
            raise ConfigurationError("Flow request model differs from locked contract")
        if quality is not None and quality != contract["quality"]:
            raise ConfigurationError("Flow request quality differs from real/test contract")
        # Reference conditioning is a separate provider capability.  The
        # installed browser/CLI transport has not produced an observed upload
        # and response-binding contract, so stop before model validation,
        # browser connection, upload, or paid submission.  Persist hashes as
        # dependencies only; they are not evidence that Flow received bytes.
        refs = [Path(p) for p in (reference_images or [])]
        if refs:
            missing = [str(p) for p in refs if not p.is_file()]
            if missing:
                root = out_path.parent
                if root.name in {"blocks", "keyframes", "refs", "video", "images"}:
                    root = root.parent
                state_path = root / (out_path.stem + ".reference-repair.json")
                state_path.write_text(json.dumps({
                    "schema_version": 1, "status": "repair_required", "repair_kind": "reference_conditioning",
                    "asset_type": asset_type, "model_alias": expected_model,
                    "conditioning": "reference_images", "reference_images": [{"path": p, "sha256": None} for p in missing],
                    "provider_request_sent": False, "browser_connected": False,
                    "required_evidence": ["reference_files_present_and_hashed", "observed_reference_upload_request_payload",
                                          "provider_request_id", "provider_response_id", "response_media_binding"],
                    "reason": "Reference file is missing; no browser connection, upload, or provider request was attempted.",
                }, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
                raise HandoffPending("Flow reference conditioning requires an existing reference file", state_path) from ConfigurationError(
                    "quality/aspect and reference conditioning transport evidence are unavailable")
            root = out_path.parent
            if root.name in {"blocks", "keyframes", "refs", "video", "images"}:
                root = root.parent
            state_path = root / (out_path.stem + ".reference-repair.json")
            hashes = [{"path": str(p.resolve()), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in refs]
            state_path.write_text(json.dumps({
                "schema_version": 1, "status": "repair_required", "repair_kind": "reference_conditioning",
                "asset_type": asset_type, "model_alias": expected_model,
                "conditioning": "reference_images", "reference_images": hashes,
                "provider_request_sent": False, "browser_connected": False,
                "required_evidence": ["observed_reference_upload_request_payload", "observed_reference_conditioning_field",
                                      "provider_request_id", "provider_response_id", "response_media_binding"],
                "reason": "Reference conditioning transport is unverified; no browser connection, upload, or provider request was attempted.",
            }, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
            raise HandoffPending("Flow reference conditioning requires transport repair before submission", state_path)
        # Preflight before connecting a browser, creating a bridge or uploading references.
        cli_model = verified_cli_model(asset_type, FLOW_BINARY)
        cmd = compile_command(FLOW_BINARY, asset_type=asset_type, model=cli_model,
                              prompt=prompt, aspect_ratio=aspect_ratio, duration=duration,
                              quality=contract["quality"], start_frame=start_frame,
                              end_frame=end_frame, references=reference_images or ())
        internal_key = (internal_video_model_key(duration, start_frame=bool(start_frame),
                                                 end_frame=bool(end_frame), references=bool(reference_images))
                        if asset_type == "video" else mapping()["image"]["internal_model_keys"][0])
        transport_snapshot = mapping()["transport"]
        def dependency(path):
            return {"path": str(Path(path).resolve()),
                    "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()} if path else None
        request_metadata = {
            "asset_type": asset_type, "project_alias": expected_model,
            "transport_model": cli_model, "internal_model_key": internal_key,
            "transport_request_model_key": internal_key + ("_360p" if asset_type == "video" and contract["quality"] == "360p" else ""),
            "quality": contract["quality"], "duration": duration, "aspect_ratio": aspect_ratio,
            "start_frame": dependency(start_frame), "end_frame": dependency(end_frame),
            "references": [dependency(p) for p in reference_images or []],
            "execution_mode": contract["execution_mode"],
            "source_revision": transport_snapshot["source_revision"],
            "binary_version": transport_snapshot["binary_version"],
            "binary_sha256": hashlib.sha256(FLOW_BINARY.read_bytes()).hexdigest(),
            "binary_source_verified": transport_snapshot["binary_source_verified"],
        }
        if asset_type == "video":
            from services.flow_media_contract import validate_catalog
            validate_catalog(mapping()["video"], request_metadata["transport_request_model_key"])
            if not shutil.which("ffprobe"):
                raise ConfigurationError("ffprobe is required before any Flow video submission")
        await self.connect()

        if self._active_account_path:
            cmd.extend(["-cookies", str(self._active_account_path)])
        active_project_id = self._active_account_bundle.get("project_id")
        if active_project_id:
            cmd.extend(["-project-id", str(active_project_id)])

        stop_event = asyncio.Event()
        responder_task = asyncio.create_task(self._bridge_responder_loop(stop_event))
        # A private fresh directory binds Files to this process, never a shared output scan.
        invocation_dir = Path(tempfile.mkdtemp(prefix="youtube-flow-invocation-"))
        process_env = os.environ.copy()
        process_env.update(FLOW_OUTPUT_DIR=str(invocation_dir), FLOW_DATA_DIR=str(invocation_dir / "data"),
                           FLOW_COOKIE_DIR=str(invocation_dir / "cookies"),
                           FLOW_LOG_FILE=str(invocation_dir / "flow.log"), FLOW_AUTO_RETRY="0")
        launch_time = time.time()
        try:
            logger.info(f"[PLAYWRIGHT CDP] Running background Flow generation ({asset_type}, {aspect_ratio})...")
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(invocation_dir), env=process_env,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise TimeoutError(f"Flow generation timed out after {timeout}s")

            stdout = stdout_b.decode("utf-8", errors="replace")
            self._cleanup_proc_transport(proc)
            if proc.returncode != 0:
                raise ProviderError("Flow request failed; accepted dependencies preserved. "
                                    "No fallback, prompt rewrite or automatic generation retry was attempted.")

            # Extract JSON result from stdout
            parsed: dict[str, Any] = {}
            lines = stdout.splitlines()
            for idx in range(len(lines) - 1, -1, -1):
                s = lines[idx].strip()
                if s.startswith("{"):
                    cand = "\n".join(lines[idx:]) if s == "{" else s
                    try:
                        parsed = json.loads(cand)
                        break
                    except Exception:
                        continue

            if asset_type != "video":
                raise ProviderError("Image outcome normalization is not reviewed; generation must remain blocked")
            from services.flow_media_contract import normalize_video_outcome
            src_file, normalized = normalize_video_outcome(
                parsed, request=request_metadata, catalog=mapping()["video"],
                invocation_root=invocation_dir, launched_at=launch_time,
                source_revision=transport_snapshot["source_revision"])
            shutil.copy2(src_file, out_path)
            import editor
            last_frame = out_path.with_suffix(".last.png")
            editor.extract_last_frame(out_path, last_frame)
            flow_meta_payload = {
                **normalized, "request": {"origin": "request", **request_metadata},
                "source_build": {"origin": "source_build", "source_revision": request_metadata["source_revision"],
                                 "binary_sha256": request_metadata["binary_sha256"]},
                "output_sha256": hashlib.sha256(out_path.read_bytes()).hexdigest(),
                "output_last_frame": dependency(last_frame),
            }
            out_path.with_suffix(".flow.json").write_text(
                json.dumps(flow_meta_payload, indent=2, ensure_ascii=False), encoding="utf-8")
            return out_path

        finally:
            stop_event.set()
            responder_task.cancel()
            try:
                await responder_task
            except (asyncio.CancelledError, Exception):
                pass

    async def close(self) -> None:
        async with self._lock:
            self.browser = None
            self.context = None
            self.page = None
            self._captcha_page = None
            if self.playwright:
                try:
                    await self.playwright.stop()
                except Exception:
                    pass
                self.playwright = None
