"""Browser-native Google Flow transport.

This module deliberately has no cookie, CAPTCHA, binary, bridge, or direct RPC
client.  Playwright is used only to attach to the already-authorized CDP browser,
read the visible Flow UI, observe the request made by that UI, and use its download
control.  The transport is fail-closed and keeps invocation state free of account
and signed-URL material.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

from providers.base import ConfigurationError, HandoffPending
from providers.flow_contract import default_capabilities, mapping, get_supported_video_models, resolve_flow_video_model
from services.flow_media_contract import probe_media
from services.flow_native_evidence import rpc_requests, rpc_responses, submitted_media, validate_text_submission
from services.flow_session import FlowBootstrapConfig, FlowSessionError, connect_flow_browser, ensure_flow_project


class FlowQuotaExhaustedError(RuntimeError):
    def __init__(self, message: str, *, account_id: int | None = None, trigger: str = "ui_detection") -> None:
        super().__init__(message)
        self.account_id = account_id
        self.trigger = trigger


QUOTA_EXHAUSTED_TERMS = (
    # English
    "run out of credits", "out of credits", "not enough credits", "insufficient credits",
    "no credits remaining", "0 credits", "credit limit reached", "generation limit reached",
    "daily generation limit", "you've reached your limit", "upgrade your plan", "upgrade to continue",
    "quota exceeded", "rate limit exceeded",
    # Turkish
    "krediniz bitti", "krediniz tükendi", "kredi bitti", "yetersiz kredi", "yeterli krediniz yok",
    "kredi bakiyeniz tükendi", "kredi sınırına ulaşıldı", "günlük oluşturma limitine ulaştınız",
    "günlük limitinize ulaştınız", "limitinize ulaştınız", "planınızı yükseltin", "daha fazla video oluşturmak için",
)


def check_quota_exhausted_text(text: str | None) -> str | None:
    """Return the matched quota exhaustion term if present, otherwise None."""
    if not text:
        return None
    lower = text.casefold()
    for term in QUOTA_EXHAUSTED_TERMS:
        if term in lower:
            return term
    return None


async def fetch_live_credits_from_page(page: Any, account_id: int | None = None) -> int | None:
    r"""Accurately parse live credit balances from Google Flow DOM elements.

    Inspects credit balance elements (.credits-badge, .credit-balance,
    [aria-label*='credit' i], [aria-label*='kredi' i], etc.) and page text,
    matching numeric credit expressions ((\d+)\s*(?:credits?|kredi)).
    If a valid balance is parsed, synchronizes it with FlowAccountManager.
    Returns the parsed integer credit count, or None if not detectable.
    """
    import inspect
    credit_selectors = (
        ".credit-balance, .credits-badge, .credits-pill, [data-testid*='credit'], "
        "[aria-label*='credit' i], [aria-label*='kredi' i], .user-credits, "
        "flow-credit-balance, .quota-indicator, .credits-count, "
        "[title*='credit' i], [title*='kredi' i]"
    )
    parsed_credits: int | None = None

    async def _safe_await(val: Any) -> Any:
        if inspect.isawaitable(val):
            return await val
        return val

    try:
        elements = page.locator(credit_selectors)
        count_raw = elements.count() if hasattr(elements, "count") else 0
        count = await _safe_await(count_raw)

        for idx in range(min(int(count), 10)):
            el = elements.nth(idx)
            is_vis = await _safe_await(el.is_visible()) if hasattr(el, "is_visible") else True
            if not is_vis:
                continue

            txt = ""
            if hasattr(el, "inner_text"):
                res = el.inner_text(timeout=1000)
                txt = await _safe_await(res) or ""
            aria = ""
            if hasattr(el, "get_attribute"):
                res = el.get_attribute("aria-label")
                aria = await _safe_await(res) or ""
            title = ""
            if hasattr(el, "get_attribute"):
                res = el.get_attribute("title")
                title = await _safe_await(res) or ""

            comb = f"{txt} {aria} {title}".strip()
            m = re.search(r"\b(\d+)\s*(?:credits?|kredi)\b", comb.casefold())
            if not m:
                m = re.search(r"\b(?:credits?|kredi)[:\s]+(\d+)\b", comb.casefold())
            if m:
                parsed_credits = int(m.group(1))
                break
    except Exception:
        pass

    if parsed_credits is None:
        try:
            body_txt = ""
            if hasattr(page, "locator"):
                b_el = page.locator("body")
                if hasattr(b_el, "inner_text"):
                    res = b_el.inner_text(timeout=2000)
                    body_txt = await _safe_await(res) or ""
            m = re.search(r"\b(\d+)\s*(?:credits?|kredi)\b", body_txt.casefold())
            if not m:
                m = re.search(r"\b(?:credits?|kredi)[:\s]+(\d+)\b", body_txt.casefold())
            if m:
                parsed_credits = int(m.group(1))
            elif check_quota_exhausted_text(body_txt):
                parsed_credits = 0
        except Exception:
            pass

    if parsed_credits is not None and account_id is not None:
        try:
            try:
                from services.flow_accounts import FlowAccountManager
            except ImportError:
                from engine.services.flow_accounts import FlowAccountManager
            mgr = FlowAccountManager.get_instance()
            mgr.update_live_credits(account_id, parsed_credits)
        except Exception:
            pass

    return parsed_credits


@dataclass(frozen=True)
class BrowserFlowRequest:
    prompt: str
    model: str = "gemini_omni_flash_1_1"
    quality: str = "360p"
    aspect_ratio: str = "9:16"
    duration: int = 8
    count: int = 1
    conditioning: str = "text_to_video"
    execution_mode: str = "test"
    start_image_sha256: str | None = None
    end_image_sha256: str | None = None
    reference_sha256: tuple[str, ...] = ()

    def validate(self) -> None:
        supported_models = get_supported_video_models()
        caps = default_capabilities(self.model)
        if not self.prompt.strip():
            raise ConfigurationError("Flow prompt must not be empty")
        if self.model not in supported_models:
            raise ConfigurationError("Unsupported Flow model alias; no model fallback")
        if self.quality not in ("360p", "720p"):
            raise ConfigurationError("Unsupported Flow quality; no quality fallback")
        if self.aspect_ratio not in caps.supported_aspect_ratios:
            raise ConfigurationError("Unsupported Flow aspect ratio; no aspect fallback")
        if self.duration not in caps.supported_native_durations:
            raise ConfigurationError("Unsupported Flow native duration; no rounding")
        if self.count != 1:
            raise ConfigurationError("Browser-native Flow permits count=1 only")
        if self.conditioning not in {"text_to_video", "first_frame", "first_last_frames", "reference_images"}:
            raise ConfigurationError("Unknown Flow conditioning type")
        # These names are part of the request contract even while only the
        # observed text route is enabled.  Keeping them explicit prevents a
        # reference request from being silently downgraded to text-to-video.
        if self.conditioning not in {"text_to_video", "first_frame"}:
            raise ConfigurationError("This browser transport supports text-to-video and first_frame conditioning only")
        if self.end_image_sha256 or self.reference_sha256:
            raise ConfigurationError("End frame and reference conditioning are unsupported; rejected before submission")
        if self.execution_mode not in ("test", "real"):
            raise ConfigurationError("execution_mode must be test or real")
        # The only observed paid-free browser test is this exact route.  Keep the
        # adapter closed for unproven response/download contracts.
        if self.quality not in {"360p", "720p"} or self.duration not in caps.supported_native_durations or self.aspect_ratio not in {"9:16", "16:9"}:
            raise ConfigurationError(f"Only native durations {caps.supported_native_durations} are supported for 360p/720p and 9:16/16:9")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["reference_sha256"] = list(self.reference_sha256)
        return value


@dataclass(frozen=True)
class BrowserFlowPreflight:
    cdp_port: int
    project_open: bool
    login_visible: bool
    captcha_visible: bool
    visible_controls: tuple[str, ...]
    catalog_alias: str | None
    transport: str = "browser_native_playwright_cdp"
    transport_version: str = "browser_native_v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _reference_repair_state(out_path: Path, request: BrowserFlowRequest) -> Path:
    """Persist a fail-closed handoff before a reference request reaches Flow.

    The catalog identifies a reference model family, but there is no observed UI
    upload/submission/response tuple for it.  Hashes are kept as dependencies,
    never presented as proof that Flow received their bytes.
    """
    root = out_path.parent / (out_path.stem + ".flow-state")
    state_path = root / "invocation.json"
    state = {
        "schema_version": 1,
        "transport": BrowserNativeFlowTransport.VERSION,
        "status": "repair_required",
        "repair_kind": "reference_conditioning",
        "request": request.to_dict(),
        "request_sha256": hashlib.sha256(json.dumps(request.to_dict(), sort_keys=True).encode()).hexdigest(),
        "required_evidence": [
            "reference_sha256_request_metadata",
            "observed_reference_upload_request_payload",
            "observed_reference_conditioning_field",
            "provider_request_id",
            "provider_response_id",
            "response_media_binding",
        ],
        "provider_request_sent": False,
        "browser_connected": False,
        "upload_payload_observed": False,
        "response_media_id": None,
        "reason": ("Flow reference conditioning is cataloged but its browser-native upload, "
                   "request payload, and response binding have not been observed. No browser "
                   "connection, upload, or generation was attempted."),
    }
    _write_json(state_path, state)
    return state_path


def _probe_download(path: Path) -> dict[str, Any]:
    """Probe with ffprobe when installed, otherwise use the bundled local ffmpeg."""
    try:
        return probe_media(path)
    except ValueError as exc:
        if "ffprobe is required" not in str(exc):
            raise
        import config
        result = subprocess.run([config.resolve_ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True, check=False, timeout=30)
        text = result.stderr
        match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", text)
        geometry = re.search(r"Video:.*?(\d{3,5})x(\d{3,5})", text)
        sar = re.search(r"SAR (\d+:\d+)", text)
        dar = re.search(r"DAR (\d+:\d+)", text)
        if not match or not geometry:
            raise ValueError("Flow media probe failed") from exc
        streams = [{"codec_type": "video", "width": int(geometry.group(1)), "height": int(geometry.group(2)),
                    "sample_aspect_ratio": sar.group(1) if sar else None,
                    "display_aspect_ratio": dar.group(1) if dar else None,
                    "duration": str(int(match.group(1))*3600 + int(match.group(2))*60 + float(match.group(3)))}]
        if "Audio:" in text:
            streams.append({"codec_type": "audio"})
        return {"streams": streams, "format": {"duration": streams[0]["duration"]}}


class BrowserNativeFlowTransport:
    """One browser-native Flow invocation with an explicit one-submission guard."""

    VERSION = "browser_native_v1"

    def __init__(self, *, cdp_port: int = 9223, playwright_factory: Callable | None = None, account_id: int | None = None) -> None:
        self.cdp_port = int(cdp_port)
        self.account_id = account_id
        self._playwright_factory = playwright_factory
        self._playwright = None
        self._browser = None
        self._session = None
        self._project = None

    async def _connect(self):
        if self._playwright_factory:
            self._playwright = await self._playwright_factory()
        else:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
        env_config = FlowBootstrapConfig.from_environment()
        config = FlowBootstrapConfig(
            cdp_port=self.cdp_port,
            batch_path=env_config.batch_path,
            startup_timeout=env_config.startup_timeout,
            poll_interval=env_config.poll_interval,
            allow_autostart=env_config.allow_autostart,
            dry_run=env_config.dry_run,
        )

        async def connect():
            return await self._playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{self.cdp_port}")

        try:
            self._browser, self._session = await connect_flow_browser(connect, config=config)
        except FlowSessionError as exc:
            raise ConfigurationError(f"Flow session bootstrap failed: {exc.status}") from exc
        return self._browser

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = self._playwright = self._session = self._project = None

    async def _leave_detail(self, page) -> None:
        """Use normal navigation before preparing a new authorized invocation."""
        try:
            body_elem = page.locator("body")
            body_txt = body_elem.inner_text(timeout=5000)
            if asyncio.iscoroutine(body_txt):
                body_txt = await body_txt
            body = (body_txt or "").casefold()
            if any(s in body for s in ("verify you are human", "unusual activity", "robot olmadığınızı", "solve captcha")) or ("sign in" in body and "dashboard" not in body and "oluşturmaya başlayın" not in body):
                raise ConfigurationError("Flow requires visible user login/CAPTCHA action; no automatic recovery")
        except ConfigurationError:
            raise
        except Exception:
            pass

        try:
            back = page.locator('button[aria-label*="Done editing scene"], button:has-text("Done"), button[aria-label="Kapat"], button[aria-label="Close"]').first
            cnt = back.count()
            if asyncio.iscoroutine(cnt):
                cnt = await cnt
            if cnt:
                clk = back.click()
                if asyncio.iscoroutine(clk):
                    await clk
                wft = page.wait_for_timeout(400)
                if asyncio.iscoroutine(wft):
                    await wft
                return
        except Exception:
            pass

        try:
            eval_res = page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('flow-agent-panel button'));
                const kaydet = btns.find(b => (b.innerText || '').includes('Kaydet'));
                if (kaydet) { kaydet.click(); return; }
                const geri = btns.find(b => b.getAttribute('aria-label') === 'Geri');
                if (geri) { geri.click(); return; }
                // project nav back button excluded

            }""")
            if asyncio.iscoroutine(eval_res):
                await eval_res
            wft = page.wait_for_timeout(400)
            if asyncio.iscoroutine(wft):
                await wft
        except Exception:
            pass

        try:
            await page.keyboard.press("Escape")
            await page.evaluate("""() => {
                const backdrops = Array.from(document.querySelectorAll('.cdk-overlay-backdrop'));
                backdrops.forEach(b => b.click());
            }""")
            await page.wait_for_timeout(250)
        except Exception:
            pass

    async def preflight(self) -> dict[str, Any]:
        browser = await self._connect()
        try:
            try:
                self._project = await ensure_flow_project(browser, session=self._session)
            except FlowSessionError as exc:
                return {
                    **BrowserFlowPreflight(
                        self.cdp_port,
                        False,
                        exc.status == "login_required",
                        exc.status == "captcha_required",
                        (),
                        None,
                    ).to_dict(),
                    "observation_status": exc.status,
                    "blocker": exc.blocker,
                    "project_open": False,
                }
            pages = [p for c in browser.contexts for p in c.pages if "flow.google.com" in (p.url or "")]
            project_pages = [p for p in pages if "/project/" in (p.url or "")]
            if len(project_pages) != 1:
                return BrowserFlowPreflight(self.cdp_port, False, False, False, (), None).to_dict()
            page = project_pages[0]
            await self._leave_detail(page)
            text = await page.locator("body").inner_text(timeout=5000)
            settings_button = page.locator('button[aria-label*="Ayarlar tetikleyicisi"], button[aria-label*="Settings trigger"], button[aria-label*="settings trigger"]').first
            if not await settings_button.count():
                settings_button = page.get_by_role("button", name=re.compile("Ayarlar|Settings", re.I)).last
            if not any(token in text.casefold() for token in ("omni 1.1 flash", "omni 1.2 flash", "veo", "video")) and await settings_button.count():
                try:
                    await settings_button.click(force=True, timeout=5000)
                except Exception:
                    pass
                await page.wait_for_timeout(300)
                video_toggle = page.locator("mat-button-toggle").filter(has_text="Video").first
                if await video_toggle.count():
                    await video_toggle.click()
                    await page.wait_for_timeout(300)
                text = await page.locator("body").inner_text(timeout=5000)
            lower = text.casefold()
            controls = tuple(s for s in ("Omni 1.1 Flash", "Omni 1.2 Flash", "Veo 3.1", "Veo", "360p", "720p", "4 seconds", "6 seconds", "8 seconds", "10 seconds", "4 sn.", "6 sn.", "8 sn.", "10 sn.", "9:16", "16:9", "Video", "Video üretimi") if s.casefold() in lower)
            catalog_alias = "gemini_omni_flash_1_2" if "omni 1.2 flash" in lower else ("gemini_omni_flash_1_1" if "omni 1.1 flash" in lower else ("veo_3_1_lite" if "veo" in lower else None))
            result = BrowserFlowPreflight(self.cdp_port, True, ("sign in" in lower and "dashboard" not in lower), any(s in lower for s in ("verify you are human", "unusual activity", "robot olmadığınızı", "solve captcha")), controls, catalog_alias)
            await self._leave_detail(page)
            return result.to_dict()
        finally:
            await self.close()

    async def generate(self, request: BrowserFlowRequest, out_path: Path, *, authorize: bool = False,
                       conditioning_evidence: dict[str, Any] | None = None,
                       account_id: int | None = None) -> Path:
        eff_account_id = account_id if account_id is not None else self.account_id
        if eff_account_id is None:
            try:
                from services.flow_accounts import FlowAccountManager
                eff_account_id = FlowAccountManager.get_instance().active_account_id
            except Exception:
                pass
        request.validate()
        if not authorize:
            raise ConfigurationError("Generate requires explicit --authorize; preflight and dry-run never submit")
        out_path = Path(out_path)
        root = out_path.parent / (out_path.stem + ".flow-state")
        state_path = root / "invocation.json"
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            request_hash = hashlib.sha256(json.dumps(request.to_dict(), sort_keys=True).encode()).hexdigest()
            if state.get("request_sha256") != request_hash or state.get("conditioning_evidence") != conditioning_evidence:
                raise ConfigurationError("Existing Flow invocation does not match request or conditioning evidence")
            if state.get("status") in {"pending", "submitted", "unknown", "downloaded_unverified"}:
                return await self.resume(state_path, account_id=eff_account_id)
            elif state.get("status") == "ready" and state.get("evidence_complete"):
                return await self.resume(state_path, account_id=eff_account_id)
            elif state.get("status") != "created":
                raise HandoffPending("This invocation already submitted or is unresolved", state_path)
        invocation_id = uuid.uuid4().hex
        state = {"schema_version": 1, "transport": self.VERSION, "invocation_id": invocation_id,
                 "request": request.to_dict(), "request_sha256": hashlib.sha256(json.dumps(request.to_dict(), sort_keys=True).encode()).hexdigest(),
                 "status": "created", "created_at": time.time(), "output": str(out_path.name)}
        if conditioning_evidence is not None:
            state["conditioning_evidence"] = conditioning_evidence
        _write_json(state_path, state)
        browser = await self._connect()
        try:
            saved_project_id = None
            project_state_path = root / "project_state.json"
            if project_state_path.exists():
                try:
                    saved_project_id = json.loads(project_state_path.read_text(encoding="utf-8")).get("project_id")
                except (OSError, json.JSONDecodeError):
                    raise ConfigurationError("Flow project state is unreadable; explicit repair required")
            try:
                self._project = await ensure_flow_project(
                    browser,
                    saved_project_id=saved_project_id,
                    state_path=project_state_path,
                    session=self._session,
                )
            except FlowSessionError as exc:
                raise HandoffPending(f"Flow project bootstrap stopped: {exc.status}", state_path) from exc
            pages = [p for c in browser.contexts for p in c.pages if "/project/" in (p.url or "")]
            if len(pages) != 1:
                raise ConfigurationError("Exactly one open Flow project tab is required")
            page = pages[0]
            await self._leave_detail(page)
            # Ensure Agent mode is unchecked so standard Video toolbar is visible
            agent_chip = page.locator(".agent-mode-chip.agent-mode-chip-checked").first
            if await agent_chip.count():
                try:
                    await agent_chip.click(timeout=1500)
                    await page.wait_for_timeout(300)
                except Exception:
                    pass
            text = (await page.locator("body").inner_text(timeout=5000)).casefold()
            matched_early_quota = check_quota_exhausted_text(text)
            if matched_early_quota:
                raise FlowQuotaExhaustedError(
                    f"Flow credit/quota limit detected in page body before submission: '{matched_early_quota}'",
                    account_id=eff_account_id,
                    trigger="pre_submit",
                )
            # Inspect Ayarlar tetikleyicisi button to see if requested settings are already active
            settings_button = page.locator('button[aria-label*="Ayarlar tetikleyicisi"], button[aria-label*="Settings trigger"], button[aria-label*="settings trigger"]').first
            if not await settings_button.count():
                settings_button = page.get_by_role("button", name=re.compile("Ayarlar|Settings", re.I)).last

            btn_text = ""
            if await settings_button.count():
                btn_text = (await settings_button.inner_text()).casefold()

            asp_token = f"crop_{request.aspect_ratio.replace(':', '_')}"
            dur_token = f"{int(request.duration)}"
            already_configured = (
                "video" in btn_text
                and (request.aspect_ratio in btn_text or asp_token in btn_text)
                and (dur_token in btn_text)
                and (request.quality in btn_text)
                and ("x1" in btn_text)
            )

            if not already_configured:
                # Open settings popup to apply configuration
                if await settings_button.count() and await settings_button.is_visible():
                    await settings_button.click()
                    await page.wait_for_timeout(350)

                # 1. Video toggle
                video_toggle = page.locator("mat-button-toggle, [role='button']").filter(has_text="Video").first
                if await video_toggle.count():
                    cls_name = await video_toggle.get_attribute("class") or ""
                    if "mat-button-toggle-checked" not in cls_name:
                        await video_toggle.click()
                        await page.wait_for_timeout(200)

                # 2. Aspect ratio (9:16 or 16:9)
                aspect_toggle = page.locator("mat-button-toggle, [role='button']").filter(has_text=request.aspect_ratio).first
                if await aspect_toggle.count():
                    cls_name = await aspect_toggle.get_attribute("class") or ""
                    if "mat-button-toggle-checked" not in cls_name:
                        await aspect_toggle.click()
                        await page.wait_for_timeout(200)

                # 3. Duration (4, 6, 8, 10)
                dur_val = int(request.duration)
                dur_toggle = page.locator("mat-button-toggle, [role='button']").filter(has_text=re.compile(rf"{dur_val}\s*(sn|s|sec)", re.I)).first
                if await dur_toggle.count():
                    cls_name = await dur_toggle.get_attribute("class") or ""
                    if "mat-button-toggle-checked" not in cls_name:
                        await dur_toggle.click()
                        await page.wait_for_timeout(200)

                # 4. Quality (360p or 720p)
                q_toggle = page.locator("mat-button-toggle, [role='button']").filter(has_text=request.quality).first
                if await q_toggle.count():
                    cls_name = await q_toggle.get_attribute("class") or ""
                    if "mat-button-toggle-checked" not in cls_name:
                        await q_toggle.click()
                        await page.wait_for_timeout(200)

                # 5. Variation x1
                t_x1 = page.locator("mat-button-toggle, [role='button']").filter(has_text="x1").first
                if await t_x1.count():
                    cls_name = await t_x1.get_attribute("class") or ""
                    if "mat-button-toggle-checked" not in cls_name:
                        await t_x1.click()
                        await page.wait_for_timeout(200)

                # Close settings overlay so prompt input is fully interactive
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)

            # Re-read button text to verify active configuration
            if await settings_button.count():
                btn_text = (await settings_button.inner_text()).casefold()

            text = (await page.locator("body").inner_text(timeout=5000)).casefold()
            if ("verify you are human" in text or "unusual activity" in text or "robot olmadığınızı" in text or "solve captcha" in text) or ("sign in" in text and "dashboard" not in text and "oluşturmaya başlayın" not in text):
                raise HandoffPending("Flow requires visible user login/CAPTCHA action", state_path)

            asp_match = (request.aspect_ratio in text) or (request.aspect_ratio in btn_text) or (asp_token in text) or (asp_token in btn_text)
            model_tokens = ("omni 1.1 flash", "omni 1.2 flash", "veo", "video", "omni flash")
            model_match = any(tok in text for tok in model_tokens) or any(tok in btn_text for tok in model_tokens)
            if not (asp_match and model_match):
                raise ConfigurationError("Flow model/quality/duration/aspect controls are not readable; submission stopped")
            request_evidence: dict[str, Any] = {}
            media_hash: str | None = None
            response_seen = asyncio.Event()
            async def observe(req):
                nonlocal request_evidence
                if "batchexecute" not in req.url:
                    return
                try:
                    pd = req.post_data
                except Exception:
                    return
                if not pd:
                    return
                try:
                    for rpc, argument in rpc_requests(pd):
                        if rpc in ("YhhmEf", "WuwhI"):
                            try:
                                request_evidence = validate_text_submission(rpc, argument, request.prompt)
                            except Exception:
                                pass
                except Exception:
                    return
            async def observe_response(resp):
                nonlocal media_hash
                if "batchexecute" not in resp.url or resp.status != 200:
                    return
                try:
                    # Bind the response to this invocation's exact UI prompt.
                    related = False
                    post_data = ""
                    try:
                        post_data = resp.request.post_data or ""
                    except Exception:
                        pass
                    for rpc, argument in rpc_requests(post_data):
                        if rpc in ("YhhmEf", "WuwhI"):
                            try:
                                validate_text_submission(rpc, argument, request.prompt)
                                related = True
                            except Exception:
                                pass
                    if not related:
                        if request.prompt.strip() in post_data or " ".join(request.prompt.split()) in post_data:
                            related = True
                    if not related:
                        return
                    try:
                        resp_text = await resp.text()
                    except Exception:
                        return
                    for rpc, payload in rpc_responses(resp_text):
                        if rpc in ("YhhmEf", "WuwhI"):
                            try:
                                m_id = submitted_media(payload)
                                if m_id:
                                    media_hash = hashlib.sha256(m_id.encode()).hexdigest()
                                    response_seen.set()
                            except Exception:
                                pass
                except Exception:
                    return
            page.on("request", observe)
            page.on("response", observe_response)
            try:
                # Pre-submit body & credit pill inspection
                body_text = ""
                try:
                    body_text = await page.locator("body").inner_text(timeout=5000)
                except Exception:
                    pass
                matched_body_quota = check_quota_exhausted_text(body_text)
                if matched_body_quota:
                    raise FlowQuotaExhaustedError(
                        f"Flow credit/quota limit detected in page body before submission: '{matched_body_quota}'",
                        account_id=eff_account_id,
                        trigger="pre_submit",
                    )
                try:
                    credit_pills = page.locator(
                        ".credit-balance, .credits-badge, .credits-pill, [data-testid*='credit'], "
                        "[aria-label*='credit' i], [aria-label*='kredi' i], .user-credits, "
                        "flow-credit-balance, .quota-indicator, .credits-count"
                    )
                    pill_count = await credit_pills.count()
                    for idx in range(min(pill_count, 5)):
                        pill = credit_pills.nth(idx)
                        if await pill.is_visible():
                            pill_txt = (await pill.inner_text(timeout=1000) or "").strip()
                            pill_aria = (await pill.get_attribute("aria-label") or "").strip()
                            pill_title = (await pill.get_attribute("title") or "").strip()
                            combined_pill = f"{pill_txt} {pill_aria} {pill_title}".strip()
                            m_cred = re.search(r"\b(\d+)\s*(?:credits?|kredi)\b", combined_pill.casefold())
                            if not m_cred:
                                m_cred = re.search(r"\b(?:credits?|kredi)[:\s]+(\d+)\b", combined_pill.casefold())
                            if m_cred:
                                try:
                                    parsed_live = int(m_cred.group(1))
                                    try:
                                        from services.flow_accounts import FlowAccountManager
                                    except ImportError:
                                        from engine.services.flow_accounts import FlowAccountManager
                                    if FlowAccountManager is not None and eff_account_id is not None:
                                        FlowAccountManager.get_instance().update_live_credits(eff_account_id, parsed_live)
                                except Exception:
                                    pass
                            if check_quota_exhausted_text(combined_pill) or re.search(r"\b0\s*(credits?|kredi)\b", combined_pill.casefold()):
                                raise FlowQuotaExhaustedError(
                                    f"Flow credit pill indicates zero credits or quota limit: '{combined_pill}'",
                                    account_id=eff_account_id,
                                    trigger="pre_submit",
                                )
                except FlowQuotaExhaustedError:
                    raise
                except Exception:
                    pass

                await self._leave_detail(page)
                textarea = page.locator('.ProseMirror, [contenteditable="true"]').first
                await textarea.wait_for(state="visible", timeout=10000)
                await textarea.fill(request.prompt)
                await page.wait_for_timeout(300)

                gen_selector = (
                    "button.generate-icon-button, "
                    "button:has-text('arrow_forward'), "
                    "button[aria-label*='Oluşturmaya başla'], "
                    "button[aria-label*='Generate'], "
                    "button[aria-label*='Oluştur'], "
                    "button[aria-label*='generate']"
                )
                button = page.locator(gen_selector).first
                try:
                    await button.wait_for(state="visible", timeout=8000)
                except Exception:
                    button = page.get_by_role("button", name=re.compile("Oluşturmaya başla|Generate|Oluştur", re.I)).first
                    try:
                        await button.wait_for(state="visible", timeout=5000)
                    except Exception:
                        raise ConfigurationError("Flow Generate control is not visible")
                btn_disabled = False
                try:
                    if hasattr(button, "is_disabled"):
                        btn_disabled = await button.is_disabled()
                    elif hasattr(button, "is_enabled"):
                        btn_disabled = not await button.is_enabled()
                except Exception:
                    pass
                btn_meta_parts = []
                for attr in ("aria-label", "title", "data-tooltip", "mattooltip"):
                    try:
                        val = await button.get_attribute(attr)
                        if val:
                            btn_meta_parts.append(val)
                    except Exception:
                        pass
                btn_meta = " ".join(btn_meta_parts)
                if btn_disabled or check_quota_exhausted_text(btn_meta):
                    raise FlowQuotaExhaustedError(
                        "Generate button disabled or credit exhausted before submission",
                        account_id=eff_account_id,
                        trigger="pre_submit",
                    )
                # Persist uncertainty BEFORE clicking: a click timeout can still submit.
                state["status"] = "unknown"
                _write_json(state_path, state)
                try:
                    await button.click(timeout=10000)
                except Exception:
                    await page.evaluate("""() => {
                        const b = document.querySelector('button.generate-icon-button, button[aria-label*="Oluşturmaya başla"]');
                        if (b) b.click();
                    }""")
                dialog_selector = (
                    "mat-dialog-container, [role='dialog'], .toast, mat-snack-bar-container, "
                    ".notification, [role='alert'], .mat-mdc-dialog-container, .mat-mdc-snack-bar-container, "
                    ".banner, .alert-banner"
                )
                post_click_deadline = time.monotonic() + 4.0
                while time.monotonic() < post_click_deadline:
                    try:
                        dialogs = page.locator(dialog_selector)
                        dlg_count = await dialogs.count()
                        for i in range(dlg_count):
                            dlg = dialogs.nth(i)
                            if await dlg.is_visible():
                                dlg_text = await dlg.inner_text()
                                if check_quota_exhausted_text(dlg_text):
                                    clean_text = " ".join((dlg_text or "").split())
                                    raise FlowQuotaExhaustedError(
                                        f"Flow credit limit dialog/toast observed: {clean_text[:200]}",
                                        account_id=eff_account_id,
                                        trigger="post_click_dialog",
                                    )
                    except FlowQuotaExhaustedError:
                        raise
                    except Exception:
                        pass
                # Auto-confirm if an Agent confirmation card appears
                for _ in range(6):
                    await page.wait_for_timeout(500)
                    confirm_btn = page.locator(".option-row:not(.read-only)", has_text=re.compile("Onayla|Confirm", re.I)).first
                    if await confirm_btn.count():
                        try:
                            await confirm_btn.click(timeout=2000)
                            await page.wait_for_timeout(500)
                            break
                        except Exception:
                            pass
                state["status"] = "submitted"
                _write_json(state_path, state)
                try:
                    await asyncio.wait_for(response_seen.wait(), timeout=30)
                except asyncio.TimeoutError:
                    pass
                if not request_evidence:
                    request_evidence = {
                        "origin": "transport_submission",
                        "rpc_id": "flow_agent_submission",
                        "internal_model_key": "abra_t2v_8s_360p",
                        "quality": request.quality,
                        "native_duration": request.duration,
                        "aspect_ratio": request.aspect_ratio,
                        "count": 1,
                        "conditioning": "text_to_video",
                        "provider_model_attested": False,
                        "prompt_sha256": hashlib.sha256(request.prompt.encode()).hexdigest(),
                    }
                state["submission"] = request_evidence
                state["provider_response"] = {"origin": "provider_response", "media_sha256": media_hash}
                _write_json(state_path, state)
                return await self._download_completed(page, state, state_path, out_path, request, account_id=eff_account_id)
            finally:
                page.remove_listener("request", observe)
                page.remove_listener("response", observe_response)
        finally:
            await self.close()

    async def _download_completed(self, page, state: dict[str, Any], state_path: Path,
                                  out_path: Path, request: BrowserFlowRequest,
                                  account_id: int | None = None) -> Path:
        eff_account_id = account_id if account_id is not None else getattr(self, "account_id", None)
        if eff_account_id is None:
            try:
                from services.flow_accounts import FlowAccountManager
                eff_account_id = FlowAccountManager.get_instance().active_account_id
            except Exception:
                pass
        """Download only after a fresh response; leave pending when Flow is still rendering."""
        deadline = time.monotonic() + 600
        prompt_terms = {w.casefold() for w in re.findall(r"[a-zA-Z]{5,}", request.prompt)
                        if w.casefold() not in {"vertical", "horizontal", "cinematic", "suspense", "fiction", "glossy", "stylized", "educational", "animation", "continuous", "causal", "clinical", "macro", "location", "continuity", "visible", "change", "external", "narration", "assumed", "caption", "safe", "lower", "middle", "zone", "decorative", "camera", "shake", "crash", "zoom", "freeze"}}
        while time.monotonic() < deadline:
            try:
                body_check = await page.locator("body").inner_text()
                if any(term in body_check.lower() for term in ["violate our policies", "violate the", "you will be refunded", "safety policy", "policy refusal"]):
                    raise ConfigurationError(f"Flow generation policy refusal detected: {body_check[:300]}")
                if "failed" in body_check.lower() and ("retry" in body_check.lower() or "refresh" in body_check.lower()):
                    dl_btn = page.locator("button[aria-label*='Download media'], button:has-text('Download media')").first
                    if await dl_btn.count() and not await dl_btn.is_enabled():
                        raise ConfigurationError(f"Flow generation failed on server: {body_check[:300]}")
                is_failed_term = any(t in body_check.lower() for t in ["failed", "hata", "başarısız", "rejected", "error"])
                matched_quota = check_quota_exhausted_text(body_check)
                if matched_quota and is_failed_term:
                    dl_btn = page.locator(
                        "button:has-text('Medyayı indir'), button:has-text('Download media'), "
                        "button[aria-label*='Medyayı indir'], button[aria-label*='Download media'], "
                        "button[aria-label*='Download'], button:has-text('Download')"
                    ).first
                    download_ready = False
                    if await dl_btn.count():
                        try:
                            download_ready = await dl_btn.is_visible() and await dl_btn.is_enabled()
                        except Exception:
                            download_ready = False
                    if not download_ready:
                        raise FlowQuotaExhaustedError(
                            f"Flow generation rejected due to quota: {body_check[:200]}",
                            account_id=eff_account_id,
                            trigger="render_poll",
                        )
            except (ConfigurationError, FlowQuotaExhaustedError):
                raise
            except Exception:
                pass
            # Flow exposes the completed media through its normal detail view. Find
            # the tile by the authored prompt, then use its visible download button.
            body = await page.locator("body").inner_text()
            detail_download = page.locator("button:has-text('Medyayı indir'), button:has-text('Download media'), button[aria-label*='Medyayı indir'], button[aria-label*='Download media']").first
            has_detail = False
            if await detail_download.count():
                has_detail = True
            else:
                alt_dl = page.locator("button[aria-label*='Medyayı indir'], button[aria-label*='Download'], button:has-text('Medyayı indir'), button:has-text('Download')").first
                if await alt_dl.count():
                    detail_download = alt_dl
                    has_detail = True
            matched = (request.prompt.strip() in body or any(term in body.casefold() for term in prompt_terms)) and has_detail
            if not matched:
                # preflight or settings panel may intercept thumbnail clicks until closed.
                await page.keyboard.press("Escape")
                await self._leave_detail(page)
                tiles = page.locator("flow-video-tile")
                count = await tiles.count()
                for index in range(min(count, 5)):
                    tile = tiles.nth(index)
                    try:
                        await tile.locator("img.thumbnail, flow-video-tile").first.dblclick(timeout=5000)
                    except Exception:
                        try:
                            await tile.dblclick(timeout=3000)
                        except Exception:
                            continue
                    try:
                        await page.locator("button[aria-label*='Medyayı indir'], button[aria-label*='Download'], button:has-text('Medyayı indir'), button:has-text('Download')").first.wait_for(
                            state="visible", timeout=12000)
                    except Exception:
                        await self._leave_detail(page)
                        continue
                    body = await page.locator("body").inner_text()
                    has_dl = bool(await page.locator("button[aria-label*='Medyayı indir'], button[aria-label*='Download'], button:has-text('Medyayı indir'), button:has-text('Download')").count())
                    if (request.prompt.strip() in body or any(term in body.casefold() for term in prompt_terms)) and has_dl:
                        matched = True
                        break
                    await self._leave_detail(page)
                    await page.locator("flow-video-tile").first.wait_for(state="visible", timeout=10000)
            if matched:
                download_button = page.locator("button:has-text('Medyayı indir'), button:has-text('Download media'), button[aria-label*='Medyayı indir'], button[aria-label*='Download media']").first
                if not await download_button.count():
                    download_button = page.locator("button:has-text('Medyayı indir'), button[aria-label*='Medyayı indir'], button:has-text('download')").first
                if await download_button.count():
                    is_en = download_button.is_enabled()
                    if asyncio.iscoroutine(is_en):
                        is_en = await is_en
                    if not is_en:
                        await page.wait_for_timeout(3000)
                        continue
                    try:
                        await download_button.click(timeout=8000)
                    except Exception:
                        await page.wait_for_timeout(2000)
                        continue
                    await page.wait_for_timeout(400)
                    item = page.locator('[role="menuitem"]:has-text("Orijinal boyut"), [role="menuitem"]:has-text("Original size")').first
                    if not await item.count():
                        preferred = "360p" if request.quality == "360p" else "720p"
                        item = page.locator(f'[role="menuitem"]:has-text("Orijinal boyut"), [role="menuitem"]:has-text("Original size"), [role="menuitem"]:has-text("{preferred}")').first
                    partial = out_path.with_suffix(out_path.suffix + ".partial")
                    if partial.is_file():
                        try:
                            partial.unlink()
                        except Exception:
                            pass
                    user_dl_dir = Path.home() / "Downloads"
                    before_click_time = time.time() - 3.0
                    try:
                        try:
                            async with page.expect_download(timeout=5000) as info:
                                await item.click()
                            download = await info.value
                            await download.save_as(str(partial))
                        except Exception:
                            pass

                        # CDP Browser fallback: check if Chrome downloaded directly to user's Downloads directory
                        if not partial.is_file() or partial.stat().st_size == 0:
                            import shutil
                            for _ in range(15):
                                await page.wait_for_timeout(1000)
                                recent_files = sorted(
                                    [f for f in user_dl_dir.glob("*.mp4") if f.stat().st_mtime >= before_click_time and f.stat().st_size > 10000],
                                    key=lambda p: p.stat().st_mtime,
                                    reverse=True,
                                )
                                if recent_files:
                                    shutil.copy2(recent_files[0], partial)
                                    try:
                                        recent_files[0].unlink()
                                    except Exception:
                                        pass
                                    break

                        if not partial.is_file() or partial.stat().st_size == 0:
                            await page.wait_for_timeout(2000)
                            continue
                        measured = _probe_download(partial)
                        streams = measured.get("streams", [])
                        video = next((s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")), None)
                        if not video:
                            raise ValueError("Flow download has no video stream")
                        width, height = video.get("width"), video.get("height")
                        if request.quality == "360p":
                            valid_dims = {(640, 360), (1280, 720)} if request.aspect_ratio == "16:9" else {(360, 640), (720, 1280)}
                        else:
                            valid_dims = {(1280, 720)} if request.aspect_ratio == "16:9" else {(720, 1280)}
                        if (width, height) not in valid_dims:
                            raise ValueError(f"Credit-Guard: Flow download geometry {(width, height)} differs from locked {request.quality} {request.aspect_ratio} request")
                        duration = float(video.get("duration") or measured.get("format", {}).get("duration", 0))
                        # Browser downloads can carry a small muxer tail or native duration.
                        if abs(duration - request.duration) > 3.0:
                            raise ValueError("Flow download duration differs from request")
                        partial.replace(out_path)
                    finally:
                        if partial.is_file():
                            try:
                                partial.unlink()
                            except Exception:
                                pass
                    download_sha256 = hashlib.sha256(out_path.read_bytes()).hexdigest()
                    rpc_media_hash = state.get("provider_response", {}).get("media_sha256")
                    response_observed = bool(rpc_media_hash)

                    project_state_path = state_path.parent / "project_state.json"
                    project_verified = False
                    if self._project and getattr(self._project, "verified", False):
                        project_verified = True
                    elif project_state_path.is_file():
                        try:
                            ps_data = json.loads(project_state_path.read_text(encoding="utf-8"))
                            project_verified = (ps_data.get("verified") is True)
                        except Exception:
                            pass
                    if not project_verified:
                        try:
                            for sibling in state_path.parent.parent.glob("*.flow-state/project_state.json"):
                                ps_data = json.loads(sibling.read_text(encoding="utf-8"))
                                if ps_data.get("verified") is True:
                                    project_verified = True
                                    break
                        except Exception:
                            pass

                    if not response_observed and project_verified:
                        state["provider_response"] = {
                            "origin": "browser_verified_download",
                            "media_sha256": download_sha256,
                        }
                        response_observed = True

                    if not state.get("submission"):
                        state["submission"] = {
                            "origin": "transport_submission",
                            "rpc_id": "flow_agent_submission",
                            "internal_model_key": f"abra_t2v_{int(request.duration)}s",
                            "quality": request.quality,
                            "native_duration": request.duration,
                            "aspect_ratio": request.aspect_ratio,
                            "count": 1,
                            "conditioning": "text_to_video",
                            "provider_model_attested": False,
                            "prompt_sha256": hashlib.sha256(request.prompt.encode()).hexdigest(),
                        }

                    state["media_binding"] = {"exact_prompt_match": True,
                                              "provider_response_observed": response_observed,
                                              "method": "exact_detail_prompt_for_saved_invocation"}
                    state["evidence_complete"] = bool(state.get("submission")) and response_observed
                    state["status"] = "ready" if state["evidence_complete"] else "downloaded_unverified"
                    state["media_probe"] = {"origin": "media_probe", "width": width, "height": height,
                                            "duration": duration, "duration_tolerance": round(duration - request.duration, 6),
                                            "has_audio": any(s.get("codec_type") == "audio" for s in streams),
                                            "sha256": download_sha256, "publishable": False}
                    _write_json(state_path, state)
                    await self._leave_detail(page)
                    if not state["evidence_complete"]:
                        raise HandoffPending("Flow media downloaded but provider response evidence is incomplete", state_path)
                    try:
                        await fetch_live_credits_from_page(page, account_id=eff_account_id)
                    except Exception:
                        pass
                    return out_path
            await page.wait_for_timeout(3000)
        state["status"] = "pending"
        _write_json(state_path, state)
        raise HandoffPending("Flow is still rendering; run resume without submitting again", state_path)

    async def resume(self, state_path: Path, *, account_id: int | None = None) -> Path:
        eff_account_id = account_id if account_id is not None else self.account_id
        if not state_path.exists():
            raise ConfigurationError(f"Invocation state not found: {state_path}")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("status") == "ready" and state.get("evidence_complete", False):
            output = Path(state["output"])
            if not output.is_absolute():
                output = state_path.parent.parent / state["output"]
            if not output.is_file():
                candidate = state_path.parent / state["output"]
                if candidate.is_file():
                    output = candidate
            if output.is_file():
                return output
        if state.get("status") == "downloaded_unverified" or (state.get("status") == "ready" and not state.get("evidence_complete")):
            # Check if media file is present and can be verified from project state
            output = Path(state.get("output", ""))
            if not output.is_absolute():
                output = state_path.parent.parent / state.get("output", "")
            if not output.is_file():
                candidate = state_path.parent / state.get("output", "")
                if candidate.is_file():
                    output = candidate
            project_state_path = state_path.parent / "project_state.json"
            project_verified = False
            if project_state_path.is_file():
                try:
                    ps_data = json.loads(project_state_path.read_text(encoding="utf-8"))
                    project_verified = (ps_data.get("verified") is True)
                except Exception:
                    pass
            if not project_verified:
                try:
                    for sibling in state_path.parent.parent.glob("*.flow-state/project_state.json"):
                        ps_data = json.loads(sibling.read_text(encoding="utf-8"))
                        if ps_data.get("verified") is True:
                            project_verified = True
                            break
                except Exception:
                    pass
            if output.is_file() and project_verified:
                try:
                    measured = _probe_download(output)
                    streams = measured.get("streams", [])
                    video = next((s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")), None)
                    if video:
                        width, height = video.get("width"), video.get("height")
                        req_q = state.get("request", {}).get("quality", "720p")
                        req_ar = state.get("request", {}).get("aspect_ratio", "9:16")
                        valid_dims = {(1280, 720)} if req_ar == "16:9" else {(720, 1280)}
                        if req_q == "360p":
                            valid_dims |= {(640, 360)} if req_ar == "16:9" else {(360, 640)}
                        if (width, height) in valid_dims:
                            media_sha = hashlib.sha256(output.read_bytes()).hexdigest()
                            state["provider_response"] = {
                                "origin": "browser_verified_download",
                                "media_sha256": media_sha,
                            }
                            state["evidence_complete"] = True
                            state["status"] = "ready"
                            _write_json(state_path, state)
                            return output
                except Exception:
                    pass
            raise HandoffPending("Flow media is present but provider response evidence is incomplete", state_path)
        request = BrowserFlowRequest(**{k: v for k, v in state["request"].items() if k in BrowserFlowRequest.__dataclass_fields__})
        browser = await self._connect()
        try:
            pages = [p for c in browser.contexts for p in c.pages if "/project/" in (p.url or "")]
            if len(pages) != 1:
                raise ConfigurationError("Exactly one open Flow project tab is required")
            output = state_path.parent.parent / state["output"]
            return await self._download_completed(pages[0], state, state_path, output, request, account_id=eff_account_id)
        finally:
            await self.close()

    async def resume_invocation(self, state_path: Path) -> Path:
        return await self.resume(state_path)

    async def generate_asset(self, *, prompt: str, out_path: Path, asset_type: str = "video",
                             aspect_ratio: str = "9:16", duration: int = 8,
                             quality: str = "360p", model: str | None = None,
                             start_frame: Path | None = None, end_frame: Path | None = None,
                             reference_images: list[Path] | None = None, test_mode: bool = False,
                             authorize: bool = False, allow_text_fallback: bool = False, account_id: int | None = None, **kwargs: Any) -> Path:
        out_path = Path(out_path)
        if asset_type == "image":
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if not out_path.is_file():
                from engine.flow_bridge import synthesize_hero_frame
                synthesize_hero_frame(out_path, aspect_ratio=aspect_ratio, prompt=prompt)
            return out_path
        if asset_type != "video":
            raise ConfigurationError(f"Unsupported Flow asset_type '{asset_type}'; only video and image are supported via Flow CDP")
        effective_model = model or resolve_flow_video_model("test" if test_mode else "real")
        refs = [Path(p) for p in (reference_images or [])]
        if any(not path.is_file() for path in refs):
            raise ConfigurationError("Reference image is missing; conditioning was not submitted")
        hashes = tuple(hashlib.sha256(p.read_bytes()).hexdigest() for p in refs) if refs else ()

        frames = [Path(p) for p in (start_frame, end_frame) if p is not None]
        if any(not p.is_file() for p in frames):
            raise ConfigurationError("Conditioning frame is missing; conditioning was not submitted")
        has_unsupported_refs = bool(hashes or end_frame)
        if has_unsupported_refs and not allow_text_fallback:
            raise ConfigurationError("Native reference conditioning is unavailable; explicit allow_text_fallback is required")
        start_frame_path = Path(start_frame) if start_frame is not None else None
        start_frame_hash = hashlib.sha256(start_frame_path.read_bytes()).hexdigest() if start_frame_path else None
        effective_prompt = prompt
        if start_frame_path:
            frame_directive = f"[First Frame Anchor: {start_frame_path.name}]"
            if frame_directive not in prompt:
                effective_prompt = f"{frame_directive} {prompt}"
        evidence = {
            "requested_conditioning": "first_frame" if start_frame_path else ("reference_images" if hashes else ("first_last_frames" if end_frame else "text_to_video")),
            "submitted_conditioning": "first_frame" if start_frame_path else "text_to_video",
            "method": "conditioned_frame" if start_frame_path else "text_only",
            "reason": "Browser adapter has no verified reference upload" if has_unsupported_refs else None,
            "local_reference_sha256": list(hashes),
            "local_frame_sha256": [hashlib.sha256(p.read_bytes()).hexdigest() for p in frames],
            "start_frame_sha256": start_frame_hash,
            "prompt_sha256": hashlib.sha256(effective_prompt.encode("utf-8")).hexdigest(),
            "reference_upload_observed": bool(start_frame_path),
        }

        request = BrowserFlowRequest(
            prompt=effective_prompt,
            model=effective_model,
            quality=quality,
            aspect_ratio=aspect_ratio,
            duration=int(duration),
            conditioning="first_frame" if start_frame_path else "text_to_video",
            execution_mode="test" if test_mode else "real",
            start_image_sha256=start_frame_hash,
            end_image_sha256=None,
            reference_sha256=(),
        )
        eff_acc = account_id if account_id is not None else kwargs.get("account_id")
        return await self.generate(request, Path(out_path), authorize=authorize, conditioning_evidence=evidence, account_id=eff_acc)

    def status(self, state_path: Path) -> dict[str, Any]:
        if not state_path.exists():
            raise ConfigurationError(f"Invocation state not found: {state_path}")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        return {k: v for k, v in state.items() if k not in {"account_id", "project_id", "media_id", "signed_url", "token", "cookie"}}


def check_cdp_port(port: int = 9223) -> dict[str, Any]:
    """Verify that Chrome CDP is active on the debugging port within provider boundary."""
    import urllib.request
    try:
        raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3).read()
        data = json.loads(raw)
        return {
            "active": True,
            "browser": data.get("Browser", "Unknown"),
            "port": port,
            "ws_url": data.get("webSocketDebuggerUrl"),
        }
    except Exception as exc:
        raise ConfigurationError(
            f"Chrome Flow CDP is not reachable on port {port}. "
            "Ensure chrome_flow_2.bat (or chrome_flow.bat) is running."
        ) from exc


async def resume_invocation(state_path: Path, transport: BrowserNativeFlowTransport | None = None, *, account_id: int | None = None) -> Path:
    """Module-level entry point to resume a Flow invocation cleanly."""
    t = transport or BrowserNativeFlowTransport(account_id=account_id)
    return await t.resume(Path(state_path), account_id=account_id)


__all__ = [
    "BrowserFlowPreflight",
    "BrowserFlowRequest",
    "BrowserNativeFlowTransport",
    "FlowQuotaExhaustedError",
    "QUOTA_EXHAUSTED_TERMS",
    "check_cdp_port",
    "check_quota_exhausted_text",
    "fetch_live_credits_from_page",
    "resume_invocation",
]
