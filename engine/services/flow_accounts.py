"""Google Flow CDP Multi-Account Management Service.

Provides isolated browser profile resolution, 24-hour cooldown tracking,
automatic rotation on quota exhaustion, process lifecycle supervision, and
native Windows 10/11 Toast Notifications.
"""

from __future__ import annotations

import asyncio
import base64
import datetime
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

logger = logging.getLogger("flow_accounts")

# Default account identifiers and profiles
DEFAULT_ACCOUNT_PROFILES: dict[int, str] = {
    1: "FlowCDPProfile",
    2: "FlowCDPProfile2",
    3: "FlowCDPProfile3",
    4: "FlowCDPProfile4",
}

DEFAULT_DAILY_QUOTA = 50
DEFAULT_MONTHLY_QUOTA = 1000
COOLDOWN_SECONDS_24H = 86400.0  # 24 hours


def _get_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


_LAST_NOTIFICATIONS: dict[str, float] = {}


def send_windows_notification(title: str, message: str, debounce_seconds: float = 30.0) -> None:
    """Fires a native Windows Toast Notification using PowerShell WinRT API.

    Fails silently on non-Windows platforms or in headless/CI/pytest environments.
    Debounces identical notifications within debounce_seconds to prevent spam.
    """
    if sys.platform != "win32" or os.getenv("PYTEST_CURRENT_TEST"):
        return

    now = time.time()
    cache_key = f"{title}:{message}"
    last_sent = _LAST_NOTIFICATIONS.get(cache_key, 0.0)
    if (now - last_sent) < debounce_seconds:
        logger.debug("Windows toast suppressed by debounce: %s", title)
        return
    _LAST_NOTIFICATIONS[cache_key] = now

    try:
        def _escape_xml(s: str) -> str:
            return (
                s.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;")
            )

        clean_title = _escape_xml(str(title).strip())
        clean_msg = _escape_xml(str(message).strip())

        ps_script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$textNodes = $template.GetElementsByTagName("text")
$textNodes.Item(0).InnerText = "{clean_title}"
$textNodes.Item(1).InnerText = "{clean_msg}"
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Google Flow CDP")
$notifier.Show($toast)
"""
        encoded = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:
        logger.debug("Windows toast notification failed (fail-silent): %s", exc)


@dataclass
class FlowAccount:
    """Represents a single Google Flow CDP browser session account."""

    id: int
    name: str
    profile_dir_name: str
    status: str = "standby"  # "active", "standby", "exhausted", "uninitialized"
    email: str | None = None
    live_credits: int | None = None
    reset_schedule: str | None = None
    exhausted_at: float | None = None
    daily_quota_limit: int = DEFAULT_DAILY_QUOTA
    monthly_quota_limit: int = DEFAULT_MONTHLY_QUOTA
    daily_credits_used: int = 0
    monthly_credits_used: int = 0
    total_blocks_rendered: int = 0
    last_reset_date: str = ""
    last_reset_month: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serializes account state to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FlowAccount:
        """Constructs an account instance filtering out unrecognized keys."""
        valid_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    @property
    def remaining_daily_credits(self) -> int:
        """Available daily credits before exhaustion."""
        return max(0, self.daily_quota_limit - self.daily_credits_used)

    @property
    def remaining_monthly_credits(self) -> int:
        """Available monthly credits before exhaustion."""
        return max(0, self.monthly_quota_limit - self.monthly_credits_used)

    @property
    def is_eligible(self) -> bool:
        """True if account is not exhausted, has not reached 0 live credits, and has remaining daily & monthly credits."""
        return (
            self.status != "exhausted"
            and (self.live_credits is None or self.live_credits > 0)
            and self.daily_credits_used < self.daily_quota_limit
            and self.monthly_credits_used < self.monthly_quota_limit
        )

    def check_and_apply_resets(self, today: str | None = None) -> bool:
        """Applies date rollovers for daily and monthly credit tracking.

        Returns True if state changed.
        """
        changed = False
        today_str = today or datetime.date.today().isoformat()
        month_str = today_str[:7]

        if self.last_reset_date != today_str:
            self.daily_credits_used = 0
            self.last_reset_date = today_str
            changed = True

        if self.last_reset_month != month_str:
            self.monthly_credits_used = 0
            self.last_reset_month = month_str
            changed = True

        return changed


class FlowAccountManager:
    """Central manager for Google Flow accounts, profile routing, and CDP process lifecycles."""

    _instance: FlowAccountManager | None = None
    _instance_lock = threading.Lock()

    def __init__(self, config_path: Path | str | None = None) -> None:
        self._lock = threading.RLock()
        if config_path:
            self.config_path = Path(config_path).resolve()
        else:
            env_override = os.getenv("FLOW_ACCOUNTS_CONFIG_PATH")
            if env_override:
                self.config_path = Path(env_override).resolve()
            else:
                self.config_path = _get_repo_root() / "config" / "flow_accounts.json"

        self.active_account_id: int = 1
        self._accounts: dict[int, FlowAccount] = {}
        self._load_state()

    @classmethod
    def get_instance(cls, config_path: Path | str | None = None) -> FlowAccountManager:
        """Returns the process singleton instance."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(config_path=config_path)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Resets the process singleton instance (useful in unit tests)."""
        with cls._instance_lock:
            cls._instance = None

    def _default_accounts(self) -> dict[int, FlowAccount]:
        today = datetime.date.today().isoformat()
        current_month = today[:7]
        return {
            1: FlowAccount(
                id=1,
                name="Account 1",
                profile_dir_name=DEFAULT_ACCOUNT_PROFILES[1],
                status="active",
                exhausted_at=None,
                daily_quota_limit=DEFAULT_DAILY_QUOTA,
                monthly_quota_limit=DEFAULT_MONTHLY_QUOTA,
                daily_credits_used=0,
                monthly_credits_used=0,
                total_blocks_rendered=0,
                last_reset_date=today,
                last_reset_month=current_month,
            ),
            2: FlowAccount(
                id=2,
                name="Account 2",
                profile_dir_name=DEFAULT_ACCOUNT_PROFILES[2],
                status="standby",
                exhausted_at=None,
                daily_quota_limit=DEFAULT_DAILY_QUOTA,
                monthly_quota_limit=DEFAULT_MONTHLY_QUOTA,
                daily_credits_used=0,
                monthly_credits_used=0,
                total_blocks_rendered=0,
                last_reset_date=today,
                last_reset_month=current_month,
            ),
            3: FlowAccount(
                id=3,
                name="Account 3",
                profile_dir_name=DEFAULT_ACCOUNT_PROFILES[3],
                status="standby",
                exhausted_at=None,
                daily_quota_limit=DEFAULT_DAILY_QUOTA,
                monthly_quota_limit=DEFAULT_MONTHLY_QUOTA,
                daily_credits_used=0,
                monthly_credits_used=0,
                total_blocks_rendered=0,
                last_reset_date=today,
                last_reset_month=current_month,
            ),
            4: FlowAccount(
                id=4,
                name="Account 4",
                profile_dir_name=DEFAULT_ACCOUNT_PROFILES[4],
                status="standby",
                exhausted_at=None,
                daily_quota_limit=DEFAULT_DAILY_QUOTA,
                monthly_quota_limit=DEFAULT_MONTHLY_QUOTA,
                daily_credits_used=0,
                monthly_credits_used=0,
                total_blocks_rendered=0,
                last_reset_date=today,
                last_reset_month=current_month,
            ),
        }

    def _load_state(self) -> None:
        """Loads accounts state from JSON or initializes default configuration."""
        if not self.config_path.is_file():
            self._accounts = self._default_accounts()
            self.active_account_id = 1
            self._save_state()
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.active_account_id = int(data.get("active_account_id", 1))
            self._accounts = {}
            for item in data.get("accounts", []):
                acc = FlowAccount.from_dict(item)
                self._accounts[acc.id] = acc

            # Ensure all 4 accounts exist
            default_map = self._default_accounts()
            missing = False
            for acc_id, default_acc in default_map.items():
                if acc_id not in self._accounts:
                    self._accounts[acc_id] = default_acc
                    missing = True

            if missing:
                self._save_state()

        except Exception as exc:
            logger.error("Failed loading Flow accounts from %s: %s. Using defaults.", self.config_path, exc)
            self._accounts = self._default_accounts()
            self.active_account_id = 1
            self._save_state()

    def _save_state(self) -> None:
        """Safely writes current accounts state to JSON using an atomic replacement."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "1.0.0",
            "active_account_id": self.active_account_id,
            "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "accounts": [self._accounts[k].to_dict() for k in sorted(self._accounts.keys())],
        }

        temp_path = self.config_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            temp_path.replace(self.config_path)
        except Exception as exc:
            logger.error("Failed saving Flow accounts state to %s: %s", self.config_path, exc)
            if temp_path.is_file():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def detect_logged_in_email(self, account_id: int) -> str | None:
        """Inspects the account's Chrome profile directory to detect the signed-in Google email."""
        profile_dir = self.resolve_profile_dir(account_id)
        if not profile_dir.is_dir():
            return None

        # 1. Inspect Default/Preferences
        pref_file = profile_dir / "Default" / "Preferences"
        if pref_file.is_file():
            try:
                data = json.loads(pref_file.read_text(encoding="utf-8", errors="ignore"))
                account_info = data.get("account_info", [])
                if isinstance(account_info, list):
                    for a in account_info:
                        em = a.get("email")
                        if em and "@" in em:
                            return str(em).strip()
                elif isinstance(account_info, dict):
                    for a in account_info.values():
                        em = a.get("email")
                        if em and "@" in em:
                            return str(em).strip()
                signin_email = data.get("google", {}).get("services", {}).get("signin", {}).get("account_id")
                if signin_email and "@" in signin_email:
                    return str(signin_email).strip()
            except Exception:
                pass

        # 2. Inspect Local State
        ls_file = profile_dir / "Local State"
        if ls_file.is_file():
            try:
                ls_data = json.loads(ls_file.read_text(encoding="utf-8", errors="ignore"))
                info_cache = ls_data.get("profile", {}).get("info_cache", {})
                for prof in info_cache.values():
                    un = prof.get("user_name")
                    if un and "@" in un:
                        return str(un).strip()
            except Exception:
                pass

        return None

    def sync_detected_emails(self) -> bool:
        """Automatically updates account email if a new Google email is detected in the Chrome profile."""
        with self._lock:
            changed = False
            for acc in self._accounts.values():
                detected = self.detect_logged_in_email(acc.id)
                if detected and detected != acc.email:
                    logger.info("Auto-detected new email for Account %d: %s -> %s", acc.id, acc.email, detected)
                    acc.email = detected
                    changed = True
            if changed:
                self._save_state()
            return changed

    def _apply_automatic_resets(self) -> bool:
        """Applies 24h cooldown resets and daily/monthly rollovers across all accounts."""
        now = time.time()
        changed = False

        for acc in self._accounts.values():
            # Check date rollover
            if acc.check_and_apply_resets():
                changed = True

            # Check 24-hour cooldown expiry
            if acc.status == "exhausted" and acc.exhausted_at is not None:
                elapsed = now - acc.exhausted_at
                if elapsed >= COOLDOWN_SECONDS_24H:
                    acc.status = "standby"
                    acc.exhausted_at = None
                    acc.daily_credits_used = 0
                    changed = True
                    logger.info("Account %d (%s) 24h cooldown expired. Restored to standby.", acc.id, acc.name)

        if changed:
            self._save_state()

        return changed

    def resolve_profile_dir(self, account_id: int) -> Path:
        """Resolves the physical directory path for the given account profile.

        Expands `%LOCALAPPDATA%\\Google\\Chrome\\<profile_dir_name>`.
        Backward compatibility:
        - If Account 1's `FlowCDPProfile_1` exists, returns it; otherwise `FlowCDPProfile`.
        - If Account 2's `FlowCDPProfile_2` exists, returns it; otherwise `FlowCDPProfile2`.
        - If Account 3's `FlowCDPProfile_3` exists, returns it; otherwise `FlowCDPProfile3`.
        - If Account 4's `FlowCDPProfile_4` exists, returns it; otherwise `FlowCDPProfile4`.
        """
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            chrome_root = Path(local_app_data) / "Google" / "Chrome"
        else:
            chrome_root = Path.home() / "AppData" / "Local" / "Google" / "Chrome"

        account = self.get_account(account_id)
        configured_name = (
            account.profile_dir_name
            if account
            else DEFAULT_ACCOUNT_PROFILES.get(account_id, f"FlowCDPProfile{account_id}")
        )

        underscore_candidate = chrome_root / f"FlowCDPProfile_{account_id}"
        if underscore_candidate.is_dir():
            return underscore_candidate

        return chrome_root / configured_name

    def get_active_account(self) -> FlowAccount:
        """Returns the currently active account, resolving rollovers if needed."""
        with self._lock:
            self._apply_automatic_resets()
            acc = self._accounts.get(self.active_account_id)
            if acc:
                return acc

            # Fallback to first active account
            for account in self._accounts.values():
                if account.status == "active":
                    self.active_account_id = account.id
                    return account

            # Default fallback to account 1
            if 1 in self._accounts:
                self._accounts[1].status = "active"
                self.active_account_id = 1
                return self._accounts[1]

            raise RuntimeError("No Flow accounts configured.")

    def get_account(self, account_id: int) -> FlowAccount | None:
        """Returns the account with the specified ID or None."""
        with self._lock:
            self._apply_automatic_resets()
            return self._accounts.get(account_id)

    def list_accounts(self) -> list[FlowAccount]:
        """Returns all managed accounts sorted by ID, synchronizing any detected profile emails."""
        with self._lock:
            self._apply_automatic_resets()
            self.sync_detected_emails()
            return [self._accounts[k] for k in sorted(self._accounts.keys())]

    def mark_exhausted(self, account_id: int, reason: str = "") -> None:
        """Sets status to 'exhausted', records timestamp, and triggers Windows Toast Notification."""
        with self._lock:
            account = self._accounts.get(account_id)
            if not account:
                logger.warning("Cannot mark unknown account %d as exhausted.", account_id)
                return

            account.status = "exhausted"
            account.exhausted_at = time.time()
            self._save_state()

            msg = f"Account {account.id} ({account.name}) quota exhausted."
            if reason:
                msg += f" {reason}"
            logger.warning(msg)
            self.send_windows_notification("Google Flow Quota Exhausted", msg)

    def rotate_to_next_account(self) -> FlowAccount | None:
        """Finds the next eligible account (checking 24h cooldown expiry first).

        If found, sets it as active and previous as standby/exhausted.
        If all accounts are exhausted, returns None and notifies the operator.
        """
        with self._lock:
            self._apply_automatic_resets()

            account_ids = sorted(self._accounts.keys())
            if not account_ids:
                return None

            current_id = self.active_account_id
            try:
                curr_idx = account_ids.index(current_id)
            except ValueError:
                curr_idx = 0

            # Scan cyclically starting from the account after current_id
            candidates_order = [
                account_ids[(curr_idx + i) % len(account_ids)]
                for i in range(1, len(account_ids) + 1)
            ]

            target_account: FlowAccount | None = None
            for acc_id in candidates_order:
                acc = self._accounts[acc_id]
                if acc.is_eligible:
                    target_account = acc
                    break

            if target_account is None:
                logger.warning("All Flow accounts are exhausted or over quota.")
                total_cnt = len(self._accounts)
                self.send_windows_notification(
                    "Google Flow Quota Alert",
                    f"All {total_cnt} Google Flow accounts are exhausted. Production halted until 24h cooldown.",
                )
                return None

            prev_account = self._accounts.get(current_id)
            if prev_account and prev_account.id != target_account.id:
                if prev_account.status == "active":
                    prev_account.status = "standby"

            target_account.status = "active"
            self.active_account_id = target_account.id
            self._save_state()

            logger.info(
                "Rotated to Flow Account %d (%s). Available credits: %d/%d",
                target_account.id,
                target_account.name,
                target_account.remaining_daily_credits,
                target_account.daily_quota_limit,
            )
            self.send_windows_notification(
                "Google Flow Account Rotated",
                f"Switched to {target_account.name} (ID: {target_account.id}). "
                f"Available: {target_account.remaining_daily_credits} credits.",
            )
            return target_account

    def set_active_account(self, account_id: int) -> FlowAccount:
        """Manually sets the active account."""
        with self._lock:
            account = self._accounts.get(account_id)
            if not account:
                raise ValueError(f"Flow account {account_id} does not exist.")

            for acc in self._accounts.values():
                if acc.id == account_id:
                    acc.status = "active"
                elif acc.status == "active":
                    acc.status = "standby"

            self.active_account_id = account_id
            self._save_state()
            logger.info("Manually set active Flow Account to %d (%s)", account.id, account.name)
            return account

    def reset_all_cooldowns(self) -> None:
        """Resets all exhausted statuses back to standby/active and clears daily usage."""
        with self._lock:
            today = datetime.date.today().isoformat()
            current_month = today[:7]
            for acc in self._accounts.values():
                acc.exhausted_at = None
                acc.daily_credits_used = 0
                acc.last_reset_date = today
                acc.last_reset_month = current_month
                if acc.status == "exhausted":
                    acc.status = "standby"

            # Ensure current active account is active
            active_acc = self._accounts.get(self.active_account_id)
            if active_acc:
                active_acc.status = "active"
            elif 1 in self._accounts:
                self._accounts[1].status = "active"
                self.active_account_id = 1

            self._save_state()
            logger.info("Reset all Flow account cooldowns and daily credit counters.")

    def add_account(
        self,
        name: str | None = None,
        profile_dir_name: str | None = None,
        daily_quota_limit: int = DEFAULT_DAILY_QUOTA,
        monthly_quota_limit: int = DEFAULT_MONTHLY_QUOTA,
    ) -> FlowAccount:
        """Adds a new account to the pool with the next available ID."""
        with self._lock:
            next_id = max(self._accounts.keys(), default=0) + 1
            default_profile = f"FlowCDPProfile{next_id}"
            acc = FlowAccount(
                id=next_id,
                name=name or f"Account {next_id}",
                profile_dir_name=profile_dir_name or default_profile,
                status="standby",
                daily_quota_limit=daily_quota_limit,
                monthly_quota_limit=monthly_quota_limit,
                daily_credits_used=0,
                monthly_credits_used=0,
                total_blocks_rendered=0,
                last_reset_date=datetime.date.today().isoformat(),
                last_reset_month=datetime.date.today().isoformat()[:7],
            )
            detected_email = self.detect_logged_in_email(next_id)
            if detected_email:
                acc.email = detected_email
            self._accounts[next_id] = acc
            self._save_state()
            logger.info("Added new Flow account #%d (%s, profile: %s)", next_id, acc.name, acc.profile_dir_name)
            return acc

    def remove_account(self, account_id: int) -> bool:
        """Removes an account from the pool by ID."""
        with self._lock:
            if account_id in self._accounts:
                del self._accounts[account_id]
                if self.active_account_id == account_id:
                    self.active_account_id = min(self._accounts.keys(), default=1)
                self._save_state()
                logger.info("Removed Flow account #%d", account_id)
                return True
            return False

    def record_block_rendered(self, account_id: int, count: int = 1) -> None:
        """Increments used credits and rendered block counter; marks exhausted if limits reached."""
        with self._lock:
            account = self._accounts.get(account_id)
            if not account:
                logger.warning("Cannot record block for unknown account %d", account_id)
                return

            account.daily_credits_used += count
            account.monthly_credits_used += count
            account.total_blocks_rendered += count

            limit_reached = False
            reason = ""
            if account.daily_credits_used >= account.daily_quota_limit:
                limit_reached = True
                reason = f"Daily quota limit ({account.daily_quota_limit} credits) reached"
            elif account.monthly_credits_used >= account.monthly_quota_limit:
                limit_reached = True
                reason = f"Monthly quota limit ({account.monthly_quota_limit} credits) reached"

            if limit_reached:
                account.status = "exhausted"
                account.exhausted_at = time.time()
                self._save_state()
                msg = f"Account {account.id} ({account.name}) quota exhausted: {reason}"
                logger.warning(msg)
                self.send_windows_notification("Google Flow Quota Exhausted", msg)
            else:
                self._save_state()
                logger.debug(
                    "Recorded %d block(s) for Account %d. Daily used: %d/%d",
                    count,
                    account.id,
                    account.daily_credits_used,
                    account.daily_quota_limit,
                )

    def terminate_flow_chrome(self) -> None:
        """Terminates running Chrome processes attached to Flow CDP profiles on Windows."""
        if sys.platform != "win32":
            logger.debug("terminate_flow_chrome skipped on non-Windows host.")
            return

        try:
            ps_cmd = (
                "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
                "Where-Object { $_.CommandLine -match 'FlowCDPProfile' } | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
            )
            encoded = base64.b64encode(ps_cmd.encode("utf-16le")).decode("ascii")
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                capture_output=True,
                timeout=10,
                check=False,
            )
            time.sleep(1.0)
            logger.info("Terminated existing Flow CDP Chrome processes.")
        except Exception as exc:
            logger.warning("Error terminating Flow Chrome processes: %s", exc)

    def terminate_account_chrome(self, account_id: int) -> None:
        """Terminates Chrome processes for a specific account profile only."""
        if sys.platform != "win32" or os.getenv("PYTEST_CURRENT_TEST"):
            return
        profile_dir = self.resolve_profile_dir(account_id)
        profile_name = profile_dir.name
        # Match profile folder name with delimiter to avoid substring false positives
        pattern = rf"{re.escape(profile_name)}(\\\\|\"|'|\s|$)"
        try:
            ps_cmd = (
                f"Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
                f"Where-Object {{ $_.CommandLine -match '{pattern}' }} | "
                f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}"
            )
            encoded = base64.b64encode(ps_cmd.encode("utf-16le")).decode("ascii")
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                capture_output=True,
                timeout=10,
                check=False,
            )
            time.sleep(0.5)
            logger.info("Terminated existing Chrome processes for Account %d (%s).", account_id, profile_name)
        except Exception as exc:
            logger.warning("Error terminating Chrome for Account %d: %s", account_id, exc)

    def _terminate_temp_chrome(self, proc: subprocess.Popen | None, account_id: int) -> None:
        """Safely terminates a temporary Chrome scanning process without touching other accounts."""
        if proc:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=2.0)
                except (subprocess.TimeoutExpired, Exception):
                    proc.kill()
            except Exception as exc:
                logger.debug("Terminating temp Chrome proc: %s", exc)

            if sys.platform == "win32" and proc.pid:
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        capture_output=True,
                        timeout=5,
                        check=False,
                    )
                except Exception:
                    pass

        # Also terminate any orphan processes for this specific account profile only
        self.terminate_account_chrome(account_id)

    @staticmethod
    def _is_cdp_reachable(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
        """Checks if a Chrome CDP endpoint is responding on the specified port."""
        for h in (host, "localhost" if host != "localhost" else "127.0.0.1"):
            try:
                req = urllib.request.Request(f"http://{h}:{port}/json")
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if resp.status == 200:
                        return True
            except Exception:
                continue
        return False

    def get_profile_name_on_port(self, port: int = 9223) -> str | None:
        """Inspects running Chrome process command lines to find the profile dir name on a given CDP port."""
        if sys.platform != "win32" or os.getenv("PYTEST_CURRENT_TEST"):
            return None
        try:
            ps_cmd = (
                f"Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
                f"Where-Object {{ $_.CommandLine -match '--remote-debugging-port={port}' }} | "
                f"Select-Object -First 1 -ExpandProperty CommandLine"
            )
            encoded = base64.b64encode(ps_cmd.encode("utf-16le")).decode("ascii")
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            out = res.stdout.strip()
            if out:
                m = re.search(r'--user-data-dir=["\']?([^"\'\s]+)', out)
                if m:
                    return Path(m.group(1).rstrip('"\'')).name
        except Exception as exc:
            logger.debug("Failed checking profile on port %d: %s", port, exc)
        return None

    @staticmethod
    def _find_available_cdp_port(preferred_port: int | None = None) -> int:
        """Finds an unused local port for CDP, preferring preferred_port if free."""
        import socket
        if preferred_port and preferred_port != 9223:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    s.bind(("127.0.0.1", preferred_port))
                    return preferred_port
            except OSError:
                pass

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    @staticmethod
    def _clean_credit_number(raw: str) -> int | None:
        """Parses credit string respecting Turkish and international locales.

        Examples:
        - "1.050" -> 1050 (Turkish thousands separator)
        - "1,050" -> 1050 (English thousands separator)
        - "52" -> 52
        """
        if not raw:
            return None
        # Remove dots, commas, spaces and non-digit characters
        clean_str = re.sub(r'[^\d]', '', str(raw).strip())
        if clean_str:
            try:
                return int(clean_str)
            except ValueError:
                return None
        return None

    @staticmethod
    def _find_chrome_binary() -> Path:
        """Locates the Google Chrome binary on the system."""
        env_custom = os.getenv("FLOW_CHROME_EXECUTABLE")
        if env_custom and Path(env_custom).is_file():
            return Path(env_custom)

        candidates = [
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate

        for bin_name in ("chrome", "google-chrome", "google-chrome-stable", "chromium"):
            resolved = shutil.which(bin_name)
            if resolved:
                return Path(resolved)

        raise FileNotFoundError("Google Chrome binary not found on this system.")

    def launch_flow_chrome(
        self,
        account_id: int,
        automation: bool = True,
        cdp_port: int = 9223,
        kill_existing: bool = True,
    ) -> subprocess.Popen:
        """Launches Google Chrome attached to the profile of account_id on cdp_port."""
        profile_dir = self.resolve_profile_dir(account_id)
        profile_dir.mkdir(parents=True, exist_ok=True)

        # Clear running Chrome to prevent profile or port locking
        if kill_existing:
            if cdp_port == 9223:
                self.terminate_flow_chrome()
            else:
                self.terminate_account_chrome(account_id)
        else:
            self.terminate_account_chrome(account_id)

        chrome_path = self._find_chrome_binary()
        args = [
            str(chrome_path),
            f"--remote-debugging-port={cdp_port}",
            f"--user-data-dir={profile_dir}",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        if automation:
            args.append("--start-minimized")
        args.append("https://flow.google.com")

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

        logger.info(
            "Launching Flow Chrome for account %d with profile %s on port %d",
            account_id,
            profile_dir,
            cdp_port,
        )
        return subprocess.Popen(args, creationflags=creationflags)

    def update_live_credits(
        self,
        account_id: int,
        credits: int,
        reset_schedule: str | None = None,
        email: str | None = None,
    ) -> None:
        """Records the live credit balance read directly from the Google Flow web page."""
        with self._lock:
            account = self._accounts.get(account_id)
            if not account:
                return
            prev_credits = account.live_credits
            account.live_credits = credits
            if reset_schedule is not None:
                account.reset_schedule = reset_schedule
            if email is not None and (account.email is None or account.email != email):
                account.email = email
            self._save_state()

            if credits <= 0 and account.status != "exhausted":
                self.mark_exhausted(account_id, reason="Live UI indicates 0 credits remaining.")
            elif credits > 0 and account.status == "exhausted":
                account.status = "active" if account.id == self.active_account_id else "standby"
                account.exhausted_at = None
                self._save_state()
                logger.info("Account %d restored from exhausted as live credits are %d", account_id, credits)
            elif prev_credits != credits:
                logger.info("Account %d live credits updated: %s -> %s", account_id, prev_credits, credits)

    async def scan_account_live_credits(self, account_id: int, timeout_secs: float = 15.0) -> int | None:
        """Launches isolated Chrome for account_id and extracts live credit balance via CDP."""
        account = self.get_account(account_id)
        if not account:
            logger.warning("Cannot scan live credits: Account %d does not exist.", account_id)
            return None

        # Check if port 9223 is listening
        is_9223_listening = self._is_cdp_reachable(9223)

        # Determine if target account is the one currently active on port 9223
        target_profile_name = self.resolve_profile_dir(account_id).name
        active_profile_name_on_9223 = self.get_profile_name_on_port(9223) if is_9223_listening else None

        if is_9223_listening:
            if active_profile_name_on_9223:
                target_is_active_on_9223 = (active_profile_name_on_9223.lower() == target_profile_name.lower())
            else:
                target_is_active_on_9223 = (self.active_account_id == account_id)
        else:
            target_is_active_on_9223 = False

        temp_proc: subprocess.Popen | None = None
        is_temporary_instance = False
        is_9223_temporary = False

        if target_is_active_on_9223:
            cdp_port = 9223
            logger.info("Account %d is already active on port %d; connecting directly.", account_id, cdp_port)
        elif not is_9223_listening and self.active_account_id == account_id:
            # Active account not running, port 9223 free to use
            cdp_port = 9223
            is_temporary_instance = True
            is_9223_temporary = True
            try:
                temp_proc = self.launch_flow_chrome(account_id, automation=True, cdp_port=cdp_port)
            except Exception as exc:
                logger.warning("Failed to launch Chrome for live credit scan on account %d: %s", account_id, exc)
                return None
            await asyncio.sleep(1.5)
        else:
            # Port 9223 is running a DIFFERENT profile (or target is non-active):
            # Allocate isolated temporary port without disturbing port 9223!
            cdp_port = self._find_available_cdp_port(preferred_port=9223 + account_id)
            is_temporary_instance = True
            is_9223_temporary = False
            try:
                temp_proc = self.launch_flow_chrome(
                    account_id, automation=True, cdp_port=cdp_port, kill_existing=False
                )
            except Exception as exc:
                logger.warning("Failed to launch isolated Chrome for account %d on port %d: %s", account_id, cdp_port, exc)
                return None
            await asyncio.sleep(1.5)

        browser = None
        playwright_cm = None
        credits_found: int | None = None
        reset_schedule_found: str | None = None
        email_found: str | None = None
        we_opened_modal = False

        try:
            try:
                from playwright.async_api import async_playwright
            except ImportError:
                logger.warning("playwright package is not installed; cannot scan live credits.")
                return None

            playwright_cm = async_playwright()
            p = await playwright_cm.start()

            max_connect_attempts = 10 if is_temporary_instance else 4
            for _ in range(max_connect_attempts):
                for host in ("127.0.0.1", "localhost"):
                    try:
                        browser = await p.chromium.connect_over_cdp(f"http://{host}:{cdp_port}", timeout=3000)
                        if browser:
                            break
                    except Exception:
                        pass
                if browser:
                    break
                await asyncio.sleep(0.5)

            if not browser:
                logger.warning("Could not connect to Chrome CDP on port %d for account %d", cdp_port, account_id)
                return None

            page = None
            for ctx in browser.contexts:
                for pg in ctx.pages:
                    if "flow.google.com" in pg.url:
                        page = pg
                        break
                if page:
                    break

            if not page:
                for ctx in browser.contexts:
                    for pg in ctx.pages:
                        if "accounts.google.com" in pg.url:
                            page = pg
                            break
                    if page:
                        break

            if not page:
                if browser.contexts and browser.contexts[0].pages:
                    page = browser.contexts[0].pages[0]
                elif browser.contexts:
                    page = await browser.contexts[0].new_page()
                else:
                    ctx = await browser.new_context()
                    page = await ctx.new_page()

            if not page.url or ("flow.google.com" not in page.url and "accounts.google.com" not in page.url):
                try:
                    await page.goto("https://flow.google.com", timeout=8000, wait_until="domcontentloaded")
                except Exception as exc:
                    logger.debug("Page navigation to flow.google.com: %s", exc)

            if "accounts.google.com" in page.url:
                logger.info("Account %d requires login (Google Accounts redirect).", account_id)
                return None

            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass

            if "accounts.google.com" in page.url:
                logger.info("Account %d requires login (Google Accounts redirect).", account_id)
                return None

            panel_selectors = ".flow-account-panel-overlay, .credits-info-wrapper, .credits-count"
            modal_already_open = False
            try:
                overlay_loc = page.locator(panel_selectors)
                count = await overlay_loc.count()
                for i in range(count):
                    if await overlay_loc.nth(i).is_visible():
                        modal_already_open = True
                        break
            except Exception:
                pass

            if not modal_already_open:
                header_candidates = [
                    ".header-user-button",
                    '[role="button"].header-user-button',
                    "button.header-user-button",
                    "a.gb_C",
                    '[aria-label*="Hesap ayrıntıları"]',
                    '[aria-label*="Google Hesabı"]',
                    '[aria-label*="Google Account"]',
                    '[aria-label*="Account details"]',
                ]
                for cand in header_candidates:
                    try:
                        btn = page.locator(cand).first
                        if await btn.count() and await btn.is_visible():
                            await btn.click()
                            we_opened_modal = True
                            break
                    except Exception:
                        continue

                if we_opened_modal:
                    try:
                        await page.wait_for_selector(
                            panel_selectors,
                            state="visible",
                            timeout=3000,
                        )
                    except Exception:
                        pass

            credits_pattern = re.compile(r'([\d\.,]+)\s*(?:Google Flow\s+)?(?:kredisi|credits?)\b', re.IGNORECASE)
            fallback_pattern = re.compile(r'\b(?:credits?|kredi(?:si)?)[:\s]+([\d\.,]+)\b', re.IGNORECASE)

            start_poll = time.time()
            max_poll = min(8.0, timeout_secs)

            while (time.time() - start_poll) < max_poll:
                if "accounts.google.com" in page.url:
                    logger.info("Account %d requires login (Google Accounts redirect).", account_id)
                    return None

                # Search .credits-count
                try:
                    count_loc = page.locator(".credits-count")
                    cnt = await count_loc.count()
                    for i in range(cnt):
                        el = count_loc.nth(i)
                        if await el.is_visible():
                            txt = (await el.inner_text()).strip()
                            m = re.search(r'([\d\.,]+)', txt)
                            if m:
                                val = self._clean_credit_number(m.group(1))
                                if val is not None:
                                    credits_found = val
                                    break
                except Exception:
                    pass

                # Search a.credits-link, .credits-info, .flow-account-panel-overlay
                if credits_found is None:
                    try:
                        for sel in ("a.credits-link", ".credits-info", ".flow-account-panel-overlay"):
                            loc = page.locator(sel)
                            cnt = await loc.count()
                            for i in range(cnt):
                                el = loc.nth(i)
                                if await el.is_visible():
                                    txt = (await el.inner_text()).strip()
                                    m = credits_pattern.search(txt) or fallback_pattern.search(txt)
                                    if m:
                                        val = self._clean_credit_number(m.group(1))
                                        if val is not None:
                                            credits_found = val
                                            break
                            if credits_found is not None:
                                break
                    except Exception:
                        pass

                # Fallback to general credit selectors across page
                if credits_found is None:
                    general_sel = (
                        ".credit-balance, .credits-badge, .credits-pill, [data-testid*='credit'], "
                        "[aria-label*='credit' i], [aria-label*='kredi' i], .user-credits, "
                        "flow-credit-balance, .quota-indicator"
                    )
                    try:
                        loc = page.locator(general_sel)
                        cnt = await loc.count()
                        for i in range(cnt):
                            el = loc.nth(i)
                            if await el.is_visible():
                                txt = (await el.inner_text()).strip()
                                aria = (await el.get_attribute("aria-label")) or ""
                                combined = f"{txt} {aria}"
                                m = credits_pattern.search(combined) or fallback_pattern.search(combined) or re.search(r'\b([\d\.,]+)\b', txt)
                                if m:
                                    val = self._clean_credit_number(m.group(1))
                                    if val is not None:
                                        credits_found = val
                                        break
                    except Exception:
                        pass

                # Fallback to document body text
                if credits_found is None:
                    try:
                        body_text = await page.evaluate("() => document.body ? document.body.innerText : ''")
                        m = credits_pattern.search(body_text) or fallback_pattern.search(body_text)
                        if m:
                            val = self._clean_credit_number(m.group(1))
                            if val is not None:
                                credits_found = val
                    except Exception:
                        pass

                # Reset schedule extraction
                if not reset_schedule_found:
                    try:
                        for sel in (".refresh-daily-label", ".credits-info"):
                            loc = page.locator(sel)
                            cnt = await loc.count()
                            for i in range(cnt):
                                el = loc.nth(i)
                                if await el.is_visible():
                                    raw_txt = (await el.inner_text()).strip()
                                    for line in raw_txt.splitlines():
                                        line_s = line.strip()
                                        if "sıfırlan" in line_s.lower() or "reset" in line_s.lower():
                                            reset_schedule_found = line_s
                                            break
                                    if reset_schedule_found:
                                        break
                                    if "refresh-daily-label" in sel and raw_txt:
                                        reset_schedule_found = raw_txt
                                        break
                            if reset_schedule_found:
                                break
                    except Exception:
                        pass

                # Email extraction
                if not email_found:
                    try:
                        email_links = page.locator('a.credits-link[href*="Email="], a[href*="Email="]')
                        if await email_links.count():
                            href = (await email_links.first.get_attribute("href")) or ""
                            m_em = re.search(r'[?&]Email=([^&]+)', href, re.IGNORECASE)
                            if m_em:
                                email_found = urllib.parse.unquote(m_em.group(1)).strip()

                        if not email_found:
                            gb_elems = page.locator('a.gb_C, [aria-label*="@"]')
                            cnt = await gb_elems.count()
                            for i in range(cnt):
                                aria = (await gb_elems.nth(i).get_attribute("aria-label")) or ""
                                m_em = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', aria)
                                if m_em:
                                    email_found = m_em.group(1).strip()
                                    break

                        if not email_found:
                            panel_loc = page.locator('.panel, .flow-account-panel-overlay')
                            cnt = await panel_loc.count()
                            for i in range(cnt):
                                panel_txt = (await panel_loc.nth(i).inner_text()) or ""
                                m_em = re.search(r'\b([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b', panel_txt)
                                if m_em:
                                    email_found = m_em.group(1).strip()
                                    break
                    except Exception:
                        pass

                if credits_found is not None:
                    break

                await asyncio.sleep(0.5)

            if we_opened_modal:
                try:
                    closed = False
                    for close_sel in ('button.panel-close', 'button:has-text("close")', 'button:has-text("Kapat")', '.header-user-button'):
                        close_btn = page.locator(close_sel).first
                        if await close_btn.count() and await close_btn.is_visible():
                            await close_btn.click()
                            closed = True
                            break
                    if not closed:
                        await page.keyboard.press("Escape")
                except Exception as exc:
                    logger.debug("Restoring modal state: %s", exc)

            if not email_found:
                email_found = self.detect_logged_in_email(account_id)

            if credits_found is not None:
                self.update_live_credits(
                    account_id,
                    credits_found,
                    reset_schedule=reset_schedule_found,
                    email=email_found,
                )
            else:
                leafs = []
                try:
                    leafs = await page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('*'))
                            .filter(e => e.children.length === 0 && (e.innerText || e.getAttribute('aria-label')))
                            .map(e => (e.innerText || e.getAttribute('aria-label') || '').trim())
                            .filter(t => t.length > 0 && t.length < 100);
                    }""")
                except Exception:
                    pass
                logger.info("Live credits undetectable for Account %d. Leaf texts: %r", account_id, leafs[:60])

            return credits_found

        except Exception as exc:
            logger.warning("Error during live credit scan for Account %d: %s", account_id, exc)
            return None
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            if playwright_cm:
                try:
                    await playwright_cm.stop()
                    await asyncio.sleep(0.05)
                except Exception:
                    pass
            if is_temporary_instance:
                if is_9223_temporary:
                    self.terminate_flow_chrome()
                else:
                    self._terminate_temp_chrome(temp_proc, account_id)

    async def scan_accounts_batch(
        self,
        account_ids: list[int],
        timeout_secs: float = 15.0,
    ) -> dict[int, int | None]:
        """Scans live credit balances for specified Google Flow accounts sequentially."""
        results: dict[int, int | None] = {}
        for aid in account_ids:
            try:
                credits = await self.scan_account_live_credits(aid, timeout_secs=timeout_secs)
                results[aid] = credits
            except Exception as exc:
                logger.error("Failed to scan live credits for Account %d in batch: %s", aid, exc)
                results[aid] = None
        return results

    async def scan_all_accounts_live_credits(self, timeout_secs: float = 15.0) -> dict[int, int | None]:
        """Scans live credit balances across all registered Google Flow accounts sequentially."""
        all_ids = [acc.id for acc in self.list_accounts()]
        return await self.scan_accounts_batch(all_ids, timeout_secs=timeout_secs)

    def send_windows_notification(self, title: str, message: str) -> None:
        """Dispatches a native Windows Toast notification."""
        send_windows_notification(title, message)


def get_flow_account_manager() -> FlowAccountManager:
    """Helper function to obtain the FlowAccountManager singleton."""
    return FlowAccountManager.get_instance()
