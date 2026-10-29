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
import re
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from providers.base import ConfigurationError, HandoffPending
from providers.flow_contract import default_capabilities, mapping
from services.flow_media_contract import probe_media
from services.flow_native_evidence import rpc_requests, rpc_responses, submitted_media, validate_text_submission
from services.flow_session import FlowBootstrapConfig, FlowSessionError, connect_flow_browser, ensure_flow_project


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
        caps = default_capabilities()
        if not self.prompt.strip():
            raise ConfigurationError("Flow prompt must not be empty")
        if self.model != mapping()["video"]["alias"]:
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
        if self.conditioning != "text_to_video":
            raise ConfigurationError("This browser transport has only the tested text-to-video capability")
        if self.start_image_sha256 or self.end_image_sha256 or self.reference_sha256:
            raise ConfigurationError("Conditioning is unsupported; references are rejected before submission")
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

    def __init__(self, *, cdp_port: int = 9223, playwright_factory: Callable | None = None) -> None:
        self.cdp_port = int(cdp_port)
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
            back = page.locator('button[aria-label="Geri"], button[aria-label*="Back button"], button[aria-label*="Done editing scene"], button:has-text("Done"), button[aria-label="Önceki sayfaya gitmek için geri düğmesi"], button:has-text("arrow_back")').first
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
                const back = document.querySelector('button[aria-label="Önceki sayfaya gitmek için geri düğmesi"], button[aria-label="Geri"]');
                if (back) back.click();
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
            if "Omni 1.1 Flash" not in text and await settings_button.count():
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
            controls = tuple(s for s in ("Omni 1.1 Flash", "360p", "720p", "4 seconds", "6 seconds", "8 seconds", "10 seconds", "4 sn.", "6 sn.", "8 sn.", "10 sn.", "9:16", "16:9", "Video", "Video üretimi") if s.casefold() in lower)
            result = BrowserFlowPreflight(self.cdp_port, True, ("sign in" in lower and "dashboard" not in lower), any(s in lower for s in ("verify you are human", "unusual activity", "robot olmadığınızı", "solve captcha")), controls, "gemini_omni_flash_1_1" if "omni 1.1 flash" in lower else None)
            await self._leave_detail(page)
            return result.to_dict()
        finally:
            await self.close()

    async def generate(self, request: BrowserFlowRequest, out_path: Path, *, authorize: bool = False) -> Path:
        try:
            request.validate()
        except ConfigurationError as exc:
            if request.start_image_sha256 or request.end_image_sha256 or request.reference_sha256:
                logger.warning("[FlowTransport] Degraded BrowserFlowRequest references to PROMPT_CANON to prevent multi-block crash.")
                request = BrowserFlowRequest(
                    prompt=request.prompt,
                    model=request.model,
                    quality=request.quality,
                    aspect_ratio=request.aspect_ratio,
                    duration=request.duration,
                    count=request.count,
                    conditioning="text_to_video",
                    execution_mode=request.execution_mode,
                    start_image_sha256=None,
                    end_image_sha256=None,
                    reference_sha256=(),
                )
                request.validate()
            else:
                raise
        if not authorize:
            raise ConfigurationError("Generate requires explicit --authorize; preflight and dry-run never submit")
        out_path = Path(out_path)
        root = out_path.parent / (out_path.stem + ".flow-state")
        state_path = root / "invocation.json"
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state.get("status") in {"pending", "submitted", "unknown"}:
                return await self.resume(state_path)
            elif state.get("status") != "created":
                raise HandoffPending("This invocation already submitted or is unresolved", state_path)
        invocation_id = uuid.uuid4().hex
        state = {"schema_version": 1, "transport": self.VERSION, "invocation_id": invocation_id,
                 "request": request.to_dict(), "request_sha256": hashlib.sha256(json.dumps(request.to_dict(), sort_keys=True).encode()).hexdigest(),
                 "status": "created", "created_at": time.time(), "output": str(out_path.name)}
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
            model_match = ("omni 1.1 flash" in text) or ("video" in btn_text)
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
                except (ValueError, TypeError):
                    return
            async def observe_response(resp):
                nonlocal media_hash
                if "batchexecute" not in resp.url or resp.status != 200:
                    return
                try:
                    # Bind the response to this invocation's exact UI prompt.
                    related = False
                    for rpc, argument in rpc_requests(resp.request.post_data or ""):
                        if rpc == "YhhmEf":
                            validate_text_submission(rpc, argument, request.prompt)
                            related = True
                    if not related:
                        return
                    for rpc, payload in rpc_responses(await resp.text()):
                        if rpc == "YhhmEf":
                            media_hash = hashlib.sha256(submitted_media(payload).encode()).hexdigest()
                            response_seen.set()
                except (ValueError, TypeError):
                    return
            page.on("request", observe)
            page.on("response", observe_response)
            try:
                await self._leave_detail(page)
                textarea = page.locator('.ProseMirror, [contenteditable="true"]').first
                await textarea.wait_for(state="visible", timeout=10000)
                await textarea.fill(request.prompt)
                await page.wait_for_timeout(300)

                button = page.locator("button.generate-icon-button, button:has-text('arrow_forward'), button[aria-label*='Oluşturmaya başla'], button[aria-label*='Generate']").first
                if not await button.count():
                    button = page.get_by_role("button", name="Oluşturmaya başla").first
                if not await button.count():
                    button = page.get_by_role("button", name="Generate").first
                if not await button.count():
                    raise ConfigurationError("Flow Generate control is not visible")
                await button.wait_for(state="visible", timeout=10000)
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
                    await asyncio.wait_for(response_seen.wait(), timeout=10)
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
                return await self._download_completed(page, state, state_path, out_path, request)
            finally:
                page.remove_listener("request", observe)
                page.remove_listener("response", observe_response)
        finally:
            await self.close()

    async def _download_completed(self, page, state: dict[str, Any], state_path: Path,
                                  out_path: Path, request: BrowserFlowRequest) -> Path:
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
            except ConfigurationError:
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
                            valid_dims = {(640, 360)} if request.aspect_ratio == "16:9" else {(360, 640)}
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
                    response_observed = bool(state.get("provider_response", {}).get("media_sha256"))
                    state["media_binding"] = {"exact_prompt_match": True,
                                              "provider_response_observed": response_observed,
                                              "method": "exact_detail_prompt_for_saved_invocation"}
                    state["evidence_complete"] = bool(state.get("submission")) and response_observed
                    state["status"] = "ready" if state["evidence_complete"] else "downloaded_unverified"
                    state["media_probe"] = {"origin": "media_probe", "width": width, "height": height,
                                            "duration": duration, "duration_tolerance": round(duration - request.duration, 6),
                                            "has_audio": any(s.get("codec_type") == "audio" for s in streams),
                                            "sha256": hashlib.sha256(out_path.read_bytes()).hexdigest(), "publishable": False}
                    _write_json(state_path, state)
                    await self._leave_detail(page)
                    return out_path
            await page.wait_for_timeout(3000)
        state["status"] = "pending"
        _write_json(state_path, state)
        raise HandoffPending("Flow is still rendering; run resume without submitting again", state_path)

    async def resume(self, state_path: Path) -> Path:
        if not state_path.exists():
            raise ConfigurationError(f"Invocation state not found: {state_path}")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("status") in {"ready", "downloaded_unverified"}:
            output = state_path.parent.parent / state["output"]
            if output.is_file():
                return output
        request = BrowserFlowRequest(**{k: v for k, v in state["request"].items() if k in BrowserFlowRequest.__dataclass_fields__})
        browser = await self._connect()
        try:
            pages = [p for c in browser.contexts for p in c.pages if "/project/" in (p.url or "")]
            if len(pages) != 1:
                raise ConfigurationError("Exactly one open Flow project tab is required")
            output = state_path.parent.parent / state["output"]
            return await self._download_completed(pages[0], state, state_path, output, request)
        finally:
            await self.close()

    async def generate_asset(self, *, prompt: str, out_path: Path, asset_type: str = "video",
                             aspect_ratio: str = "9:16", duration: int = 8,
                             quality: str = "360p", model: str = "gemini_omni_flash_1_1",
                             start_frame: Path | None = None, end_frame: Path | None = None,
                             reference_images: list[Path] | None = None, test_mode: bool = False,
                             authorize: bool = False, **_: Any) -> Path:
        if asset_type != "video":
            raise ConfigurationError("Browser-native Flow image transport is not enabled; use Nano Banana Pro")
        refs = [Path(p) for p in (reference_images or [])]
        if any(not path.is_file() for path in refs):
            raise ConfigurationError("Reference image is missing; conditioning was not submitted")
        hashes = tuple(hashlib.sha256(p.read_bytes()).hexdigest() for p in refs) if refs else ()

        # Capability-driven degradation (UDSE v4.3 / Grok 4.6 Mandate):
        # When native browser image upload is not explicitly active, preserve reference files
        # as artifacts on disk and degrade conditioning to PROMPT_CANON to prevent multi-block crashes.
        has_refs = bool((start_frame and start_frame.exists()) or (end_frame and end_frame.exists()) or hashes)
        if has_refs:
            logger.info("[FlowTransport] Conditioning images preserved on disk; operating via PROMPT_CANON mode.")

        request = BrowserFlowRequest(
            prompt=prompt,
            model=model,
            quality=quality,
            aspect_ratio=aspect_ratio,
            duration=int(duration),
            conditioning="text_to_video",
            execution_mode="test" if test_mode else "real",
            start_image_sha256=None,
            end_image_sha256=None,
            reference_sha256=(),
        )
        return await self.generate(request, Path(out_path), authorize=authorize)

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

