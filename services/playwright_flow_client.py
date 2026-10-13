from __future__ import annotations

import asyncio
import base64
import glob
import json
import logging
import os
import random
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import websockets
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = logging.getLogger(__name__)

FLOW_AGENT_ROOT = Path("C:/Users/bekir/OneDrive/Masaüstü/flow-agent/flow-agent")
FLOW_BINARY = FLOW_AGENT_ROOT / "bin" / "flow-windows.exe"
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
        """Start an isolated minimized Chrome with --remote-debugging-port if not running."""
        profile_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "FlowCDPProfile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            CHROME_EXE,
            f"--remote-debugging-port={self.cdp_port}",
            f"--user-data-dir={profile_dir}",
            "--disable-blink-features=AutomationControlled",
            "--start-minimized",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ]
        logger.info(f"[PLAYWRIGHT CDP] Launching background Chrome on port {self.cdp_port}...")
        det_flags = (
            getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        )
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            creationflags=det_flags,
        )

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
    ) -> Path:
        """Generate an image or video in the background using Playwright CDP + Flow engine."""
        async with self._lock:
            return await self._generate_asset_locked(
                prompt=prompt,
                out_path=out_path,
                asset_type=asset_type,
                aspect_ratio=aspect_ratio,
                start_frame=start_frame,
                reference_images=reference_images,
                duration=duration,
                timeout=timeout,
            )

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
    ) -> Path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        await self.connect()

        if not FLOW_BINARY.is_file():
            raise FileNotFoundError(f"Flow binary not found at {FLOW_BINARY}")

        if asset_type == "image":
            asp = aspect_ratio if aspect_ratio in ("16:9", "9:16", "1:1") else "16:9"
            model = os.getenv("FLOW_IMAGE_MODEL", "gem_pix_2")
            if model == "gem_pix_2" and self._gem_pix_2_quota_exhausted:
                logger.info(
                    "[FLOW AUTO-HEAL] gem_pix_2 günlük kotası bu oturumda tüketildiği için doğrudan 'beluga' kullanılıyor..."
                )
                model = "beluga"
            cmd = [str(FLOW_BINARY), "image", "-prompt", prompt, "-aspect", asp, "-model", model]
        else:
            asp = "landscape" if aspect_ratio in ("16:9", "landscape") else "portrait"
            supported = (4, 6, 8, 10)
            dur_val = min(supported, key=lambda x: abs(x - (duration or 4)))
            cmd = [str(FLOW_BINARY), "generate", "-prompt", prompt, "-aspect", asp, "-duration", str(dur_val), "-quality", "720p"]
            if asp == "landscape":
                if start_frame and Path(start_frame).is_file():
                    start_ref = self._resolve_flow_media_id(Path(start_frame)) or str(Path(start_frame).resolve())
                    cmd.extend(["-reference", start_ref])
                for ref in reference_images or []:
                    if Path(ref).is_file() and (not start_frame or Path(ref).resolve() != Path(start_frame).resolve()):
                        ref_arg = self._resolve_flow_media_id(Path(ref)) or str(Path(ref).resolve())
                        cmd.extend(["-reference", ref_arg])
            else:
                if start_frame and Path(start_frame).is_file():
                    start_ref = self._resolve_flow_media_id(Path(start_frame)) or str(Path(start_frame).resolve())
                    cmd.extend(["-start-image", start_ref])
                else:
                    for ref in reference_images or []:
                        if Path(ref).is_file():
                            ref_arg = self._resolve_flow_media_id(Path(ref)) or str(Path(ref).resolve())
                            cmd.extend(["-reference", ref_arg])

        if self._active_account_path:
            cmd.extend(["-cookies", str(self._active_account_path)])
        active_project_id = self._active_account_bundle.get("project_id")
        if active_project_id:
            cmd.extend(["-project-id", str(active_project_id)])

        stop_event = asyncio.Event()
        responder_task = asyncio.create_task(self._bridge_responder_loop(stop_event))
        launch_time = time.time()
        try:
            logger.info(f"[PLAYWRIGHT CDP] Running background Flow generation ({asset_type}, {aspect_ratio})...")
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(FLOW_AGENT_ROOT),
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise TimeoutError(f"Flow generation timed out after {timeout}s")

            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")
            if proc.returncode != 0:
                err_text = f"{stderr}\n{stdout}"
                is_quota_reached = any(token in err_text for token in (
                    "PUBLIC_ERROR_PER_MODEL_DAILY_QUOTA_REACHED",
                    "PER_MODEL_DAILY_QUOTA_REACHED",
                    "DAILY_QUOTA_REACHED",
                    "quota reached",
                ))
                is_unusual_activity = any(token in err_text for token in (
                    "PUBLIC_ERROR_UNUSUAL_ACTIVITY",
                    "unusual activity",
                    "assessment refused",
                ))
                is_safety_refusal = any(token in err_text for token in (
                    "SAFETY", "refused", "blocked", "policy", "sensitive",
                ))

                if asset_type == "image" and model == "gem_pix_2" and is_quota_reached:
                    self._gem_pix_2_quota_exhausted = True
                    logger.warning(
                        "[FLOW AUTO-HEAL] gem_pix_2 günlük kotası doldu (PUBLIC_ERROR_PER_MODEL_DAILY_QUOTA_REACHED). "
                        "Otomatik olarak kesintisiz 'beluga' (Imagen 3) modeline geçiliyor..."
                    )
                    print(
                        f"\n    [gem_pix_2 Kota Doldu] Google Flow günlük gem_pix_2 kotası doldu. Otomatik çözüm: 'beluga' (Imagen 3) modeliyle kesintisiz üretiliyor...",
                        flush=True,
                    )
                    await asyncio.sleep(4.0)
                    beluga_cmd = list(cmd)
                    for idx_m, arg in enumerate(beluga_cmd):
                        if arg == "-model" and idx_m + 1 < len(beluga_cmd):
                            beluga_cmd[idx_m + 1] = "beluga"
                            break
                    proc = await asyncio.create_subprocess_exec(
                        *beluga_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=str(FLOW_AGENT_ROOT),
                    )
                    try:
                        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                    except asyncio.TimeoutError:
                        proc.kill()
                        await proc.wait()
                        raise TimeoutError(f"Flow generation timed out after {timeout}s on fallback beluga")
                    stdout = stdout_b.decode("utf-8", errors="replace")
                    stderr = stderr_b.decode("utf-8", errors="replace")
                    if proc.returncode != 0:
                        raise RuntimeError(f"Flow engine exited {proc.returncode} on fallback beluga: {(stderr or stdout)[-600:]}")

                elif asset_type == "image" and is_unusual_activity:
                    if model == "gem_pix_2":
                        self._gem_pix_2_quota_exhausted = True
                    logger.warning("[FLOW AUTO-HEAL] Google hesabı geçici soğuma / reCAPTCHA uyarısı tespit edildi. 25s beklenip taze token ile yeniden deneniyor...")
                    print(f"\n    [Flow Cooldown] Google hesabı soğuma süresi bekleniyor (25s), ardından taze token ile tekrar deneniyor...", flush=True)
                    await asyncio.sleep(25.0)
                    retry_cmd = list(cmd)
                    if model == "gem_pix_2":
                        for idx_m, arg in enumerate(retry_cmd):
                            if arg == "-model" and idx_m + 1 < len(retry_cmd):
                                retry_cmd[idx_m + 1] = "beluga"
                                break
                    proc = await asyncio.create_subprocess_exec(
                        *retry_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=str(FLOW_AGENT_ROOT),
                    )
                    try:
                        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                    except asyncio.TimeoutError:
                        proc.kill()
                        await proc.wait()
                        raise TimeoutError(f"Flow generation timed out after {timeout}s on retry")
                    stdout = stdout_b.decode("utf-8", errors="replace")
                    stderr = stderr_b.decode("utf-8", errors="replace")
                    if proc.returncode != 0:
                        if model == "gem_pix_2" and "-model" in retry_cmd:
                            # Try one more fallback directly to beluga
                            logger.warning("[FLOW AUTO-HEAL] gem_pix_2 oturum engeli aşılamadı, 'beluga' modeliyle deneniyor...")
                            print(f"\n    [gem_pix_2 Oturum Hatası] 'beluga' modeliyle otomatik tamamlanıyor...", flush=True)
                            await asyncio.sleep(4.0)
                            beluga_cmd = list(cmd)
                            for idx_m, arg in enumerate(beluga_cmd):
                                if arg == "-model" and idx_m + 1 < len(beluga_cmd):
                                    beluga_cmd[idx_m + 1] = "beluga"
                                    break
                            proc = await asyncio.create_subprocess_exec(
                                *beluga_cmd,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                                cwd=str(FLOW_AGENT_ROOT),
                            )
                            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                            stdout = stdout_b.decode("utf-8", errors="replace")
                            stderr = stderr_b.decode("utf-8", errors="replace")
                            if proc.returncode != 0:
                                raise RuntimeError(f"Flow engine exited {proc.returncode}: {(stderr or stdout)[-600:]}")
                        else:
                            raise RuntimeError(f"Flow engine exited {proc.returncode}: {(stderr or stdout)[-600:]}")

                elif asset_type == "video" and is_unusual_activity:
                    logger.warning("[FLOW AUTO-HEAL] Video üretimi sırasında Google Flow soğuma uyarısı. 30s beklenip yeniden deneniyor...")
                    print(f"\n    [Flow Video Cooldown] 30s bekleniyor, ardından tekrar deneniyor...", flush=True)
                    await asyncio.sleep(30.0)
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=str(FLOW_AGENT_ROOT),
                    )
                    try:
                        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                    except asyncio.TimeoutError:
                        proc.kill()
                        await proc.wait()
                        raise TimeoutError(f"Flow video generation timed out after {timeout}s on retry")
                    stdout = stdout_b.decode("utf-8", errors="replace")
                    stderr = stderr_b.decode("utf-8", errors="replace")
                    if proc.returncode != 0:
                        raise RuntimeError(f"Flow engine exited {proc.returncode} on video retry: {(stderr or stdout)[-600:]}")

                elif asset_type == "image" and is_safety_refusal:
                    sanitized_prompt = self._sanitize_flow_image_prompt(prompt)
                    logger.warning(f"[FLOW AUTO-HEAL] Güvenlik filtresi reddi. Prompt arındırılarak tekrar deneniyor: {sanitized_prompt[:80]}...")
                    print(f"\n    [Prompt Arındırma] Güvenlik filtresi hassas kelimeleri temizlendi, tekrar deneniyor...", flush=True)
                    safe_cmd = list(cmd)
                    for idx_p, arg in enumerate(safe_cmd):
                        if arg == "-prompt" and idx_p + 1 < len(safe_cmd):
                            safe_cmd[idx_p + 1] = sanitized_prompt
                            break
                    proc = await asyncio.create_subprocess_exec(
                        *safe_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=str(FLOW_AGENT_ROOT),
                    )
                    try:
                        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                    except asyncio.TimeoutError:
                        proc.kill()
                        await proc.wait()
                        raise TimeoutError(f"Flow generation timed out after {timeout}s on sanitized prompt retry")
                    stdout = stdout_b.decode("utf-8", errors="replace")
                    stderr = stderr_b.decode("utf-8", errors="replace")
                    if proc.returncode != 0:
                        raise RuntimeError(f"Flow engine exited {proc.returncode}: {(stderr or stdout)[-600:]}")
                else:
                    raise RuntimeError(f"Flow engine exited {proc.returncode}: {(stderr or stdout)[-600:]}")

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

            file_cand = None
            files = parsed.get("files") or []
            if files:
                first = files[0]
                if isinstance(first, dict):
                    file_cand = first.get("path") or first.get("file") or first.get("filename") or first.get("name")
                elif isinstance(first, str):
                    file_cand = first

            if not file_cand and parsed.get("job_id"):
                cand_p = FLOW_AGENT_ROOT / "output" / f"{parsed['job_id']}.mp4"
                if cand_p.is_file():
                    file_cand = str(cand_p)

            if not file_cand:
                ext = ".mp4" if asset_type == "video" else ".jpg"
                out_dir = FLOW_AGENT_ROOT / "output"
                matches = sorted(out_dir.glob(f"*{ext}"), key=os.path.getmtime, reverse=True)
                if matches and matches[0].stat().st_mtime >= (launch_time - 2.0):
                    file_cand = str(matches[0])

            if file_cand:
                src_file = Path(file_cand)
                if not src_file.is_absolute():
                    src_file = FLOW_AGENT_ROOT / src_file
                if src_file.is_file():
                    shutil.copy2(str(src_file), str(out_path))
                    flow_meta_path = out_path.with_name(out_path.stem + ".flow.json")
                    try:
                        flow_meta_payload = {
                            "parsed": parsed,
                            "prompt": prompt,
                            "aspect_ratio": aspect_ratio,
                            "duration": duration,
                            "launch_time": launch_time,
                            "source_file": str(src_file),
                        }
                        flow_meta_path.write_text(json.dumps(flow_meta_payload, indent=2, ensure_ascii=False), encoding="utf-8")
                    except Exception:
                        pass
                    logger.info(f"[PLAYWRIGHT CDP] Saved {asset_type} to {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")
                    await asyncio.sleep(2.5)
                    return out_path

            raise RuntimeError(f"Flow engine did not return output file: {stdout[-400:]}")
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
