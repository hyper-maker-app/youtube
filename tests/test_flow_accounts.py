"""Tests for Google Flow CDP Multi-Account Management Service."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.flow_accounts import (
    DEFAULT_ACCOUNT_PROFILES,
    COOLDOWN_SECONDS_24H,
    FlowAccount,
    FlowAccountManager,
    get_flow_account_manager,
    send_windows_notification,
)


@pytest.fixture
def temp_accounts_config(tmp_path: Path) -> Path:
    """Fixture providing an isolated temporary JSON config path."""
    return tmp_path / "flow_accounts_test.json"


@pytest.fixture
def manager(temp_accounts_config: Path) -> FlowAccountManager:
    """Fixture providing a fresh FlowAccountManager pointing to temp config."""
    FlowAccountManager.reset_instance()
    return FlowAccountManager(config_path=temp_accounts_config)


def test_default_initialization(manager: FlowAccountManager, temp_accounts_config: Path) -> None:
    assert temp_accounts_config.is_file()
    accounts = manager.list_accounts()
    assert len(accounts) == 4

    acc1 = manager.get_account(1)
    assert acc1 is not None
    assert acc1.id == 1
    assert acc1.name == "Account 1"
    assert acc1.profile_dir_name == "FlowCDPProfile"
    assert acc1.status == "active"
    assert acc1.daily_quota_limit == 50
    assert acc1.monthly_quota_limit == 1000
    assert acc1.daily_credits_used == 0
    assert acc1.total_blocks_rendered == 0

    acc2 = manager.get_account(2)
    assert acc2 is not None
    assert acc2.id == 2
    assert acc2.profile_dir_name == "FlowCDPProfile2"
    assert acc2.status == "standby"

    acc3 = manager.get_account(3)
    assert acc3 is not None
    assert acc3.profile_dir_name == "FlowCDPProfile3"
    assert acc3.status == "standby"

    acc4 = manager.get_account(4)
    assert acc4 is not None
    assert acc4.profile_dir_name == "FlowCDPProfile4"
    assert acc4.status == "standby"

    assert manager.get_active_account().id == 1


def test_resolve_profile_dir(manager: FlowAccountManager, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_localappdata = tmp_path / "AppData" / "Local"
    fake_chrome = fake_localappdata / "Google" / "Chrome"
    fake_chrome.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LOCALAPPDATA", str(fake_localappdata))

    # Standard fallback when no underscore directory exists
    p1 = manager.resolve_profile_dir(1)
    assert p1 == fake_chrome / "FlowCDPProfile"

    p2 = manager.resolve_profile_dir(2)
    assert p2 == fake_chrome / "FlowCDPProfile2"

    p3 = manager.resolve_profile_dir(3)
    assert p3 == fake_chrome / "FlowCDPProfile3"

    p4 = manager.resolve_profile_dir(4)
    assert p4 == fake_chrome / "FlowCDPProfile4"

    # Backward compatibility: if FlowCDPProfile_1 exists, it takes precedence
    under_1 = fake_chrome / "FlowCDPProfile_1"
    under_1.mkdir(parents=True, exist_ok=True)
    assert manager.resolve_profile_dir(1) == under_1

    # Same for FlowCDPProfile_2
    under_2 = fake_chrome / "FlowCDPProfile_2"
    under_2.mkdir(parents=True, exist_ok=True)
    assert manager.resolve_profile_dir(2) == under_2


def test_set_active_account(manager: FlowAccountManager) -> None:
    assert manager.get_active_account().id == 1

    acc2 = manager.set_active_account(2)
    assert acc2.id == 2
    assert acc2.status == "active"
    assert manager.get_active_account().id == 2
    assert manager.get_account(1).status == "standby"

    with pytest.raises(ValueError):
        manager.set_active_account(99)


def test_mark_exhausted(manager: FlowAccountManager) -> None:
    manager.mark_exhausted(1, reason="Test daily limit reached")
    acc1 = manager.get_account(1)
    assert acc1.status == "exhausted"
    assert acc1.exhausted_at is not None
    assert not acc1.is_eligible


def test_record_block_rendered_and_auto_exhaustion(manager: FlowAccountManager) -> None:
    manager.record_block_rendered(1, count=5)
    acc1 = manager.get_account(1)
    assert acc1.daily_credits_used == 5
    assert acc1.monthly_credits_used == 5
    assert acc1.total_blocks_rendered == 5
    assert acc1.status == "active"

    # Reaching daily quota (50) automatically marks exhausted
    manager.record_block_rendered(1, count=45)
    acc1 = manager.get_account(1)
    assert acc1.daily_credits_used == 50
    assert acc1.status == "exhausted"
    assert acc1.exhausted_at is not None


def test_rotation_pipeline(manager: FlowAccountManager) -> None:
    # Account 1 active
    assert manager.get_active_account().id == 1

    # Mark 1 exhausted and rotate
    manager.mark_exhausted(1, reason="Limit reached")
    next_acc = manager.rotate_to_next_account()
    assert next_acc is not None
    assert next_acc.id == 2
    assert next_acc.status == "active"
    assert manager.get_active_account().id == 2

    # Mark 2 exhausted and rotate -> 3
    manager.mark_exhausted(2, reason="Limit reached")
    next_acc = manager.rotate_to_next_account()
    assert next_acc is not None
    assert next_acc.id == 3
    assert next_acc.status == "active"

    # Mark 3 exhausted and rotate -> 4
    manager.mark_exhausted(3, reason="Limit reached")
    next_acc = manager.rotate_to_next_account()
    assert next_acc is not None
    assert next_acc.id == 4
    assert next_acc.status == "active"

    # Mark 4 exhausted and rotate -> All exhausted (returns None)
    manager.mark_exhausted(4, reason="Limit reached")
    next_acc = manager.rotate_to_next_account()
    assert next_acc is None


def test_rotation_24h_cooldown_recovery(manager: FlowAccountManager) -> None:
    # Mark all 4 accounts exhausted
    for i in range(1, 5):
        manager.mark_exhausted(i)

    # Set Account 1 exhausted timestamp to 25 hours ago
    past_timestamp = time.time() - (COOLDOWN_SECONDS_24H + 3600)
    acc1 = manager.get_account(1)
    acc1.exhausted_at = past_timestamp
    manager._save_state()

    # Rotate should revive Account 1
    next_acc = manager.rotate_to_next_account()
    assert next_acc is not None
    assert next_acc.id == 1
    assert next_acc.status == "active"
    assert next_acc.exhausted_at is None
    assert next_acc.daily_credits_used == 0


def test_reset_all_cooldowns(manager: FlowAccountManager) -> None:
    for i in range(1, 5):
        manager.mark_exhausted(i)
        manager.record_block_rendered(i, count=10)

    manager.reset_all_cooldowns()

    for i in range(1, 5):
        acc = manager.get_account(i)
        assert acc.exhausted_at is None
        assert acc.daily_credits_used == 0
        assert acc.status in ("active", "standby")

    assert manager.get_active_account().status == "active"


def test_date_rollover_resets() -> None:
    acc = FlowAccount(
        id=1,
        name="Account 1",
        profile_dir_name="FlowCDPProfile",
        daily_credits_used=40,
        monthly_credits_used=300,
        last_reset_date="2026-10-01",
        last_reset_month="2026-10",
    )

    changed = acc.check_and_apply_resets(today="2026-11-06")
    assert changed is True
    assert acc.daily_credits_used == 0
    assert acc.monthly_credits_used == 0
    assert acc.last_reset_date == "2026-11-06"
    assert acc.last_reset_month == "2026-11"

    # Same day check -> no change
    changed_again = acc.check_and_apply_resets(today="2026-11-06")
    assert changed_again is False


def test_windows_notification_failsafe() -> None:
    # Must not raise under any circumstances
    send_windows_notification("Test & <Title>", "Message with 'quotes' and \"double quotes\" & <xml>")


def test_singleton_get_flow_account_manager(temp_accounts_config: Path) -> None:
    FlowAccountManager.reset_instance()
    mgr1 = FlowAccountManager.get_instance(config_path=temp_accounts_config)
    mgr2 = FlowAccountManager.get_instance()
    assert mgr1 is mgr2


def test_chrome_binary_discovery() -> None:
    # On a Windows host with Chrome installed, binary should be found or raise FileNotFoundError gracefully
    try:
        bin_path = FlowAccountManager._find_chrome_binary()
        assert bin_path.exists()
    except FileNotFoundError:
        pass


def test_terminate_flow_chrome_mocked(manager: FlowAccountManager) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        manager.terminate_flow_chrome()
        assert mock_run.called


def test_launch_flow_chrome_mocked(manager: FlowAccountManager, tmp_path: Path) -> None:
    fake_chrome = tmp_path / "chrome.exe"
    fake_chrome.write_text("fake binary")

    with patch.object(FlowAccountManager, "_find_chrome_binary", return_value=fake_chrome), \
         patch.object(manager, "terminate_flow_chrome") as mock_term, \
         patch("subprocess.Popen") as mock_popen, \
         patch.object(manager, "send_windows_notification") as mock_notify:

        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        proc = manager.launch_flow_chrome(account_id=2, automation=True, cdp_port=9223)
        assert proc is mock_proc
        assert mock_term.called
        assert mock_popen.called

        args = mock_popen.call_args[0][0]
        assert str(fake_chrome) in args[0]
        assert "--remote-debugging-port=9223" in args
        assert "--start-minimized" in args
        assert any("FlowCDPProfile2" in a for a in args)
        assert "https://flow.google.com" in args
        assert not mock_notify.called


def test_update_live_credits(manager: FlowAccountManager) -> None:
    acc = manager.get_account(1)
    assert acc is not None
    assert acc.live_credits is None
    assert acc.reset_schedule is None

    manager.update_live_credits(
        1,
        42,
        reset_schedule="10 Kas günü saat 15:19 itibarıyla sıfırlanır",
        email="test@flow.google.com",
    )
    acc = manager.get_account(1)
    assert acc is not None
    assert acc.live_credits == 42
    assert acc.reset_schedule == "10 Kas günü saat 15:19 itibarıyla sıfırlanır"
    assert acc.email == "test@flow.google.com"
    assert acc.status == "active"

    # Zero credits triggers exhausted status
    manager.update_live_credits(1, 0)
    acc = manager.get_account(1)
    assert acc is not None
    assert acc.live_credits == 0
    assert acc.status == "exhausted"

    # Updating with positive credits restores status and clears exhausted_at
    manager.update_live_credits(1, 52)
    acc = manager.get_account(1)
    assert acc is not None
    assert acc.live_credits == 52
    assert acc.status == "active"
    assert acc.exhausted_at is None


@pytest.mark.asyncio
async def test_scan_account_live_credits_invalid(manager: FlowAccountManager) -> None:
    result = await manager.scan_account_live_credits(99)
    assert result is None


@pytest.mark.asyncio
async def test_scan_all_accounts_live_credits_mocked(manager: FlowAccountManager) -> None:
    with patch.object(manager, "scan_account_live_credits", side_effect=lambda aid, **kw: aid * 10):
        results = await manager.scan_all_accounts_live_credits()
        assert results == {1: 10, 2: 20, 3: 30, 4: 40}


def test_add_and_remove_account(manager: FlowAccountManager) -> None:
    initial_count = len(manager.list_accounts())
    assert initial_count == 4

    # Add Account 5
    acc5 = manager.add_account(name="Account 5", daily_quota_limit=100)
    assert acc5.id == 5
    assert acc5.name == "Account 5"
    assert acc5.profile_dir_name == "FlowCDPProfile5"
    assert acc5.daily_quota_limit == 100
    assert len(manager.list_accounts()) == 5

    # Switch to Account 5
    switched = manager.set_active_account(5)
    assert switched.id == 5
    assert manager.active_account_id == 5

    # Remove Account 5
    removed = manager.remove_account(5)
    assert removed is True
    assert len(manager.list_accounts()) == 4
    assert manager.get_account(5) is None
    # Active account falls back safely
    assert manager.active_account_id in (1, 2, 3, 4)

    # Removing non-existent account returns False
    assert manager.remove_account(999) is False


def test_dynamic_accounts_rotation_with_5_accounts(manager: FlowAccountManager) -> None:
    # Add Account 5 to pool
    acc5 = manager.add_account(name="Account 5")
    assert acc5.id == 5

    # Exhaust accounts 1 through 4
    for i in range(1, 5):
        manager.mark_exhausted(i)

    # Rotate should now pick Account 5!
    next_acc = manager.rotate_to_next_account()
    assert next_acc is not None
    assert next_acc.id == 5
    assert next_acc.status == "active"


def test_flow_account_reset_schedule_serialization() -> None:
    acc = FlowAccount(
        id=1,
        name="Account 1",
        profile_dir_name="FlowCDPProfile",
        reset_schedule="10 Kas günü saat 15:19 itibarıyla sıfırlanır",
    )
    d = acc.to_dict()
    assert d["reset_schedule"] == "10 Kas günü saat 15:19 itibarıyla sıfırlanır"

    restored = FlowAccount.from_dict(d)
    assert restored.reset_schedule == "10 Kas günü saat 15:19 itibarıyla sıfırlanır"


def _make_mock_element(text: str = "", visible: bool = True, attrs: dict[str, str] | None = None) -> MagicMock:
    el = MagicMock()
    el.is_visible = AsyncMock(return_value=visible)
    el.inner_text = AsyncMock(return_value=text)
    attrs_dict = attrs or {}
    el.get_attribute = AsyncMock(side_effect=lambda a: attrs_dict.get(a, ""))
    el.click = AsyncMock()
    el.count = AsyncMock(return_value=1 if visible else 0)
    return el


def _make_mock_locator(elements: list[MagicMock] | None = None) -> MagicMock:
    elements = elements or []
    loc = MagicMock()
    loc.count = AsyncMock(return_value=len(elements))
    if elements:
        loc.first = elements[0]
    else:
        empty = _make_mock_element(visible=False)
        loc.first = empty
    loc.nth = MagicMock(side_effect=lambda i: elements[i] if i < len(elements) else _make_mock_element(visible=False))
    return loc


@pytest.mark.asyncio
async def test_scan_account_live_credits_when_cdp_already_running(manager: FlowAccountManager) -> None:
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    mock_page = MagicMock()
    mock_page.url = "https://flow.google.com"
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.keyboard.press = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value="")

    el_credit = _make_mock_element("50 credits", visible=True)
    el_reset = _make_mock_element("Resets 10 Nov at 15:19", visible=True, attrs={"class": "refresh-daily-label"})
    el_email = _make_mock_element(visible=True, attrs={"href": "https://flow.google.com/?Email=testuser%40google.com"})

    def mock_locator(sel: str):
        if ".flow-account-panel-overlay" in sel or ".credits-count" in sel:
            return _make_mock_locator([el_credit])
        elif ".refresh-daily-label" in sel or ".credits-info" in sel:
            return _make_mock_locator([el_reset])
        elif "Email=" in sel:
            return _make_mock_locator([el_email])
        return _make_mock_locator([])

    mock_page.locator = MagicMock(side_effect=mock_locator)
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_browser = MagicMock()
    mock_browser.contexts = [mock_context]
    mock_browser.close = AsyncMock()
    mock_playwright = MagicMock()
    mock_playwright.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)

    with patch("urllib.request.urlopen", return_value=mock_resp), \
         patch.object(manager, "launch_flow_chrome") as mock_launch, \
         patch.object(manager, "terminate_flow_chrome") as mock_terminate, \
         patch("playwright.async_api.async_playwright") as mock_pw_cls:

        mock_pw_cm = MagicMock()
        mock_pw_cm.start = AsyncMock(return_value=mock_playwright)
        mock_pw_cm.stop = AsyncMock()
        mock_pw_cls.return_value = mock_pw_cm

        credits = await manager.scan_account_live_credits(1)

        assert credits == 50
        assert not mock_launch.called
        assert not mock_terminate.called

        acc = manager.get_account(1)
        assert acc is not None
        assert acc.live_credits == 50
        assert acc.reset_schedule == "Resets 10 Nov at 15:19"
        assert acc.email == "testuser@google.com"


@pytest.mark.asyncio
async def test_scan_account_live_credits_when_cdp_not_running(manager: FlowAccountManager) -> None:
    mock_page = MagicMock()
    mock_page.url = "https://flow.google.com"
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.keyboard.press = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value="")

    el_credit = _make_mock_element("100", visible=True)

    def mock_locator(sel: str):
        if ".credits-count" in sel:
            return _make_mock_locator([el_credit])
        return _make_mock_locator([])

    mock_page.locator = MagicMock(side_effect=mock_locator)
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_browser = MagicMock()
    mock_browser.contexts = [mock_context]
    mock_browser.close = AsyncMock()
    mock_playwright = MagicMock()
    mock_playwright.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)

    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")), \
         patch.object(manager, "launch_flow_chrome") as mock_launch, \
         patch.object(manager, "terminate_flow_chrome") as mock_terminate, \
         patch("playwright.async_api.async_playwright") as mock_pw_cls:

        mock_pw_cm = MagicMock()
        mock_pw_cm.start = AsyncMock(return_value=mock_playwright)
        mock_pw_cm.stop = AsyncMock()
        mock_pw_cls.return_value = mock_pw_cm

        credits = await manager.scan_account_live_credits(1)

        assert credits == 100
        assert mock_launch.called
        assert mock_terminate.called

        acc = manager.get_account(1)
        assert acc is not None
        assert acc.live_credits == 100


@pytest.mark.asyncio
async def test_scan_account_live_credits_opens_and_closes_modal(manager: FlowAccountManager) -> None:
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    mock_page = MagicMock()
    mock_page.url = "https://flow.google.com"
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.keyboard.press = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value="")

    modal_opened = False
    btn_header = _make_mock_element(visible=True)

    async def on_header_click():
        nonlocal modal_opened
        modal_opened = True

    btn_header.click.side_effect = on_header_click

    close_btn = _make_mock_element(visible=True)
    el_credit = _make_mock_element("25 Google Flow kredisi", visible=True)

    def mock_locator(sel: str):
        if ".header-user-button" in sel:
            return _make_mock_locator([btn_header])
        elif "button.panel-close" in sel:
            return _make_mock_locator([close_btn])
        elif ".flow-account-panel-overlay" in sel or ".credits-count" in sel:
            if modal_opened:
                return _make_mock_locator([el_credit])
            return _make_mock_locator([])
        return _make_mock_locator([])

    mock_page.locator = MagicMock(side_effect=mock_locator)
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_browser = MagicMock()
    mock_browser.contexts = [mock_context]
    mock_browser.close = AsyncMock()
    mock_playwright = MagicMock()
    mock_playwright.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)

    with patch("urllib.request.urlopen", return_value=mock_resp), \
         patch.object(manager, "launch_flow_chrome"), \
         patch.object(manager, "terminate_flow_chrome"), \
         patch("playwright.async_api.async_playwright") as mock_pw_cls:

        mock_pw_cm = MagicMock()
        mock_pw_cm.start = AsyncMock(return_value=mock_playwright)
        mock_pw_cm.stop = AsyncMock()
        mock_pw_cls.return_value = mock_pw_cm

        credits = await manager.scan_account_live_credits(1)

        assert credits == 25
        assert btn_header.click.called
        assert close_btn.click.called


def test_clean_credit_number() -> None:
    assert FlowAccountManager._clean_credit_number("1.050") == 1050
    assert FlowAccountManager._clean_credit_number("1,050") == 1050
    assert FlowAccountManager._clean_credit_number("52") == 52
    assert FlowAccountManager._clean_credit_number("0") == 0
    assert FlowAccountManager._clean_credit_number(" 2.500 ") == 2500
    assert FlowAccountManager._clean_credit_number("") is None
    assert FlowAccountManager._clean_credit_number(None) is None


@pytest.mark.asyncio
async def test_scan_account_live_credits_turkish_thousands_separator(manager: FlowAccountManager) -> None:
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    mock_page = MagicMock()
    mock_page.url = "https://flow.google.com"
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.keyboard.press = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value="")

    # Turkish format: "1.050 Google Flow kredisi"
    el_credit = _make_mock_element("1.050 Google Flow kredisi", visible=True)

    def mock_locator(sel: str):
        if ".credits-count" in sel or ".flow-account-panel-overlay" in sel:
            return _make_mock_locator([el_credit])
        return _make_mock_locator([])

    mock_page.locator = MagicMock(side_effect=mock_locator)
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_browser = MagicMock()
    mock_browser.contexts = [mock_context]
    mock_browser.close = AsyncMock()
    mock_playwright = MagicMock()
    mock_playwright.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)

    with patch("urllib.request.urlopen", return_value=mock_resp), \
         patch.object(manager, "launch_flow_chrome"), \
         patch.object(manager, "terminate_flow_chrome"), \
         patch("playwright.async_api.async_playwright") as mock_pw_cls:

        mock_pw_cm = MagicMock()
        mock_pw_cm.start = AsyncMock(return_value=mock_playwright)
        mock_pw_cm.stop = AsyncMock()
        mock_pw_cls.return_value = mock_pw_cm

        credits = await manager.scan_account_live_credits(1)
        assert credits == 1050

        acc = manager.get_account(1)
        assert acc is not None
        assert acc.live_credits == 1050


@pytest.mark.asyncio
async def test_scan_account_live_credits_port_isolation_when_diff_profile_active(manager: FlowAccountManager) -> None:
    """When Account 1 is active on 9223, scanning Account 2 must launch on an isolated port and NOT kill 9223."""
    assert manager.active_account_id == 1

    mock_page = MagicMock()
    mock_page.url = "https://flow.google.com"
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.keyboard.press = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value="")

    el_credit = _make_mock_element("75 credits", visible=True)

    def mock_locator(sel: str):
        if ".credits-count" in sel or ".flow-account-panel-overlay" in sel:
            return _make_mock_locator([el_credit])
        return _make_mock_locator([])

    mock_page.locator = MagicMock(side_effect=mock_locator)
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_browser = MagicMock()
    mock_browser.contexts = [mock_context]
    mock_browser.close = AsyncMock()
    mock_playwright = MagicMock()
    mock_playwright.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)

    fake_proc = MagicMock()
    fake_proc.pid = 99999
    fake_proc.terminate = MagicMock()

    with patch.object(manager, "_is_cdp_reachable", return_value=True), \
         patch.object(manager, "get_profile_name_on_port", return_value="FlowCDPProfile"), \
         patch.object(manager, "launch_flow_chrome", return_value=fake_proc) as mock_launch, \
         patch.object(manager, "terminate_flow_chrome") as mock_terminate_flow, \
         patch.object(manager, "_terminate_temp_chrome") as mock_terminate_temp, \
         patch("playwright.async_api.async_playwright") as mock_pw_cls:

        mock_pw_cm = MagicMock()
        mock_pw_cm.start = AsyncMock(return_value=mock_playwright)
        mock_pw_cm.stop = AsyncMock()
        mock_pw_cls.return_value = mock_pw_cm

        # Scan Account 2 while Account 1 is running on port 9223
        credits = await manager.scan_account_live_credits(2)

        assert credits == 75

        # Verify launch was called with isolated port and kill_existing=False
        assert mock_launch.called
        call_kwargs = mock_launch.call_args[1]
        assert call_kwargs.get("kill_existing") is False
        assert call_kwargs.get("cdp_port") != 9223

        # Verify port 9223 active daemon was NOT killed
        assert not mock_terminate_flow.called

        # Verify temporary process was terminated cleanly
        assert mock_terminate_temp.called
        assert mock_terminate_temp.call_args[0][1] == 2  # account_id 2


@pytest.mark.asyncio
async def test_scan_accounts_batch(manager: FlowAccountManager) -> None:
    mock_scan = AsyncMock(side_effect=[50, 1050, None])
    with patch.object(manager, "scan_account_live_credits", mock_scan):
        results = await manager.scan_accounts_batch([1, 2, 3])
        assert results == {1: 50, 2: 1050, 3: None}
        assert mock_scan.call_count == 3




