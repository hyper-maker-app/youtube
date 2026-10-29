"""Safe browser-native Flow session and project bootstrap helpers.

This module owns only local CDP attachment and visible Flow UI discovery.  It
never logs in, solves CAPTCHA, injects cookies/tokens, or calls a hidden API.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable


DEFAULT_CDP_PORT = 9223
DEFAULT_STARTUP_TIMEOUT = 45.0
DEFAULT_POLL_INTERVAL = 0.5
_LAUNCH_LOCK = asyncio.Lock()


class FlowSessionError(RuntimeError):
    """A Flow session/project could not be established safely."""

    def __init__(self, message: str, *, status: str, blocker: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.blocker = blocker or message


@dataclass(frozen=True)
class FlowBootstrapConfig:
    cdp_port: int = DEFAULT_CDP_PORT
    batch_path: Path | None = None
    startup_timeout: float = DEFAULT_STARTUP_TIMEOUT
    poll_interval: float = DEFAULT_POLL_INTERVAL
    allow_autostart: bool = True
    dry_run: bool = False

    @classmethod
    def from_environment(cls, *, dry_run: bool = False) -> "FlowBootstrapConfig":
        root = Path(__file__).resolve().parents[1]
        raw_path = os.getenv("FLOW_CHROME_BATCH_PATH", "").strip()
        raw_timeout = os.getenv("FLOW_CDP_START_TIMEOUT_SECONDS", str(DEFAULT_STARTUP_TIMEOUT))
        raw_interval = os.getenv("FLOW_CDP_POLL_INTERVAL_SECONDS", str(DEFAULT_POLL_INTERVAL))
        try:
            timeout = max(1.0, float(raw_timeout))
        except ValueError:
            timeout = DEFAULT_STARTUP_TIMEOUT
        try:
            interval = min(5.0, max(0.1, float(raw_interval)))
        except ValueError:
            interval = DEFAULT_POLL_INTERVAL
        return cls(
            cdp_port=int(os.getenv("PLAYWRIGHT_CDP_PORT", str(DEFAULT_CDP_PORT))),
            batch_path=Path(raw_path) if raw_path else root / "chrome_flow.bat",
            startup_timeout=timeout,
            poll_interval=interval,
            allow_autostart=os.getenv("FLOW_AUTOSTART", "true").casefold() not in {"0", "false", "no"},
            dry_run=dry_run,
        )


@dataclass
class BrowserLease:
    lease_id: str
    generation: int
    created_at: float
    expires_at: float
    cdp_port: int
    is_active: bool = True

    def is_valid(self, current_generation: int) -> bool:
        return self.is_active and (self.generation == current_generation) and (time.monotonic() < self.expires_at)

    def renew(self, extension_seconds: float = 180.0) -> None:
        self.expires_at = time.monotonic() + extension_seconds

    def release(self) -> None:
        self.is_active = False


class BrowserLeaseManager:
    """Manages active leases and prevents zombie callbacks via monotonic generation counter."""
    _instance: Optional["BrowserLeaseManager"] = None

    def __init__(self) -> None:
        self._current_generation: int = 1
        self._active_lease: Optional[BrowserLease] = None
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "BrowserLeaseManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def current_generation(self) -> int:
        return self._current_generation

    def bump_generation(self) -> int:
        self._current_generation += 1
        if self._active_lease:
            self._active_lease.release()
            self._active_lease = None
        return self._current_generation

    async def acquire_lease(self, cdp_port: int = DEFAULT_CDP_PORT, duration_seconds: float = 180.0) -> BrowserLease:
        async with self._lock:
            if self._active_lease and self._active_lease.is_valid(self._current_generation):
                self._active_lease.renew(duration_seconds)
                return self._active_lease
            self._current_generation += 1
            now = time.monotonic()
            lease_id = hashlib.sha256(f"lease_{self._current_generation}_{now}".encode()).hexdigest()[:12]
            self._active_lease = BrowserLease(
                lease_id=lease_id,
                generation=self._current_generation,
                created_at=now,
                expires_at=now + duration_seconds,
                cdp_port=cdp_port,
                is_active=True,
            )
            return self._active_lease

    def is_lease_valid(self, lease: BrowserLease) -> bool:
        return lease.is_valid(self._current_generation)


@dataclass(frozen=True)
class FlowSessionResult:
    status: str
    cdp_port: int
    launched_batch: bool
    blocker: str | None = None
    lease: BrowserLease | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.lease:
            data["lease_id"] = self.lease.lease_id
            data["generation"] = self.lease.generation
        return data


@dataclass(frozen=True)
class FlowProjectResult:
    status: str
    project_id: str | None
    project_url: str | None
    source: str
    new_project_clicked: bool
    verified: bool
    session: FlowSessionResult | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        if self.session:
            value["session"] = self.session.to_dict()
        return value


def _project_id(url: str) -> str | None:
    match = re.search(r"/project/([^/?#]+)", url or "")
    return match.group(1) if match else None


def _is_flow_page(page: Any) -> bool:
    return "flow.google.com" in (getattr(page, "url", "") or "")


async def _connect_once(connect: Callable[[], Awaitable[Any]]) -> Any:
    return await connect()


async def connect_flow_browser(
    connect: Callable[[], Awaitable[Any]],
    *,
    config: FlowBootstrapConfig | None = None,
    launch: Callable[[Path], Any] | None = None,
) -> tuple[Any, FlowSessionResult]:
    """Attach to CDP, starting the repository batch only when CDP is absent."""
    config = config or FlowBootstrapConfig.from_environment()
    lease_mgr = BrowserLeaseManager.get_instance()
    try:
        lease = await lease_mgr.acquire_lease(config.cdp_port)
        return await _connect_once(connect), FlowSessionResult("cdp_connected", config.cdp_port, False, lease=lease)
    except Exception as first_error:
        if config.dry_run or not config.allow_autostart:
            raise FlowSessionError(
                f"Flow CDP is unavailable on port {config.cdp_port}",
                status="cdp_unavailable",
                blocker=type(first_error).__name__,
            ) from first_error
        batch_path = Path(config.batch_path or (Path(__file__).resolve().parents[1] / "chrome_flow.bat"))
        if not batch_path.is_file():
            raise FlowSessionError(
                f"Flow launcher batch is missing: {batch_path}",
                status="launcher_missing",
            ) from first_error
        async with _LAUNCH_LOCK:
            try:
                lease = await lease_mgr.acquire_lease(config.cdp_port)
                return await _connect_once(connect), FlowSessionResult("cdp_connected", config.cdp_port, False, lease=lease)
            except Exception:
                if launch is None:
                    launch = _launch_batch
                launch(batch_path)
            deadline = time.monotonic() + config.startup_timeout
            while time.monotonic() < deadline:
                try:
                    browser = await _connect_once(connect)
                    lease = await lease_mgr.acquire_lease(config.cdp_port)
                    return browser, FlowSessionResult("batch_launched", config.cdp_port, True, lease=lease)
                except Exception:
                    await asyncio.sleep(config.poll_interval)
        raise FlowSessionError(
            f"Flow CDP did not become available on port {config.cdp_port}",
            status="cdp_start_timeout",
        ) from first_error


def _launch_batch(batch_path: Path) -> None:
    flags = (
        getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    )
    subprocess.Popen(
        ["cmd.exe", "/d", "/c", "call", str(batch_path), "--automation"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=flags,
    )


def launch_flow_batch(batch_path: Path) -> None:
    """Public sync launcher used by legacy clients after CDP connection fails."""
    _launch_batch(Path(batch_path))


async def _body_text(page: Any) -> str:
    try:
        return str(await page.locator("body").inner_text(timeout=5000))
    except Exception:
        return ""


async def ensure_flow_project(
    browser: Any,
    *,
    saved_project_id: str | None = None,
    state_path: Path | None = None,
    click_new_project: bool = True,
    session: FlowSessionResult | None = None,
) -> FlowProjectResult:
    """Reuse one project or create exactly one from an authenticated landing page."""
    pages = [p for context in browser.contexts for p in context.pages if _is_flow_page(p)]
    project_pages = [p for p in pages if _project_id(getattr(p, "url", ""))]
    if len(project_pages) > 1:
        raise FlowSessionError("Multiple Flow project tabs are open; choose one explicitly", status="ambiguous_projects")
    if project_pages:
        page = project_pages[0]
        project_id = _project_id(page.url)
        if saved_project_id and project_id != saved_project_id:
            raise FlowSessionError("Open Flow project differs from the locked project", status="project_lock_mismatch")
        result = FlowProjectResult("project_open", project_id, page.url, "existing_project", False, bool(project_id), session)
        _write_state(state_path, result)
        return result

    if not pages:
        raise FlowSessionError("No Flow page is open after CDP connection", status="flow_page_missing")
    page = pages[0]
    text = (await _body_text(page)).casefold()
    if any(term in text for term in ("sign in", "giriş yap", "verify you are human", "unusual activity", "captcha")):
        status = "captcha_required" if any(term in text for term in ("verify you are human", "unusual activity", "captcha")) else "login_required"
        raise FlowSessionError("Flow requires visible user action", status=status)
    if not click_new_project:
        raise FlowSessionError("Authenticated Flow landing has no project", status="project_not_open")

    candidates = []
    for name in ("New project", "Yeni proje"):
        try:
            locator = page.get_by_role("button", name=name)
        except Exception:
            continue
        try:
            count = await locator.count()
            if count == 1:
                candidate = locator.first
                if hasattr(candidate, "is_visible") and not await candidate.is_visible():
                    continue
                candidates.append(candidate)
        except Exception:
            pass
    if len(candidates) != 1:
        raise FlowSessionError("Flow landing project button is missing or ambiguous", status="new_project_button_ambiguous")
    await candidates[0].click()
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        for candidate in [p for context in browser.contexts for p in context.pages if _is_flow_page(p)]:
            project_id = _project_id(getattr(candidate, "url", ""))
            if project_id:
                if saved_project_id and project_id != saved_project_id:
                    raise FlowSessionError("New Flow project differs from the locked project", status="project_lock_mismatch")
                result = FlowProjectResult("project_created", project_id, candidate.url, "created_by_bootstrap", True, True, session)
                _write_state(state_path, result)
                return result
        await asyncio.sleep(0.25)
    raise FlowSessionError("New project click did not produce a Flow project URL", status="project_creation_timeout")


def _write_state(path: Path | None, result: FlowProjectResult) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict()
    payload.pop("session", None)
    payload["project_lock_sha256"] = hashlib.sha256(
        f"{result.project_id}|{result.project_url}".encode("utf-8")
    ).hexdigest()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)

