"""Unit tests for Google Flow CDP multi-account CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from tools.cinematic_studio_cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolate_flow_accounts_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure all CLI tests run against an isolated temporary configuration."""
    temp_config = tmp_path / "flow_accounts_cli_test.json"
    monkeypatch.setenv("FLOW_ACCOUNTS_CONFIG_PATH", str(temp_config))
    from engine.services.flow_accounts import FlowAccountManager
    FlowAccountManager.reset_instance()
    yield
    FlowAccountManager.reset_instance()


def test_flow_accounts_status():
    result = runner.invoke(app, ["flow", "accounts", "status"], env={"COLUMNS": "140"})
    assert result.exit_code == 0
    assert "Google Flow CDP Multi-Account Pool" in result.output
    assert "Account 1" in result.output
    assert "Account 2" in result.output
    assert "Account 3" in result.output
    assert "Account 4" in result.output
    assert "Reset Schedule" in result.output
    assert "Google Flow Credit Model:" in result.output


def test_flow_accounts_status_json():
    result = runner.invoke(app, ["flow", "accounts", "status", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "active_account_id" in data
    assert "accounts" in data
    assert len(data["accounts"]) == 4
    for acc in data["accounts"]:
        assert "reset_schedule" in acc


def test_flow_accounts_switch_valid():
    result = runner.invoke(app, ["flow", "accounts", "switch", "3"])
    assert result.exit_code == 0
    assert "Successfully switched active Flow Account to Account 3" in result.output

    # Switch back to 1
    result_back = runner.invoke(app, ["flow", "accounts", "switch", "1"])
    assert result_back.exit_code == 0
    assert "Successfully switched active Flow Account to Account 1" in result_back.output


def test_flow_accounts_switch_invalid():
    result = runner.invoke(app, ["flow", "accounts", "switch", "99"])
    assert result.exit_code != 0
    assert "Invalid account ID" in result.output


def test_flow_accounts_reset():
    result = runner.invoke(app, ["flow", "accounts", "reset"])
    assert result.exit_code == 0
    assert "All 4 Google Flow accounts have been reset" in result.output


def test_flow_accounts_active_id():
    result = runner.invoke(app, ["flow", "accounts", "active-id"])
    assert result.exit_code == 0
    assert result.output.strip().isdigit()


def test_flow_accounts_notify_test():
    with patch("engine.services.flow_accounts.send_windows_notification") as mock_notify:
        result = runner.invoke(app, ["flow", "accounts", "notify-test"])
        assert result.exit_code == 0
        assert "Windows Toast notification successfully dispatched" in result.output
        mock_notify.assert_called_once()


def test_flow_shortcut_status():
    result = runner.invoke(app, ["flow", "status"])
    assert result.exit_code == 0
    assert "Google Flow CDP Multi-Account Pool" in result.output


@patch("engine.services.flow_accounts.FlowAccountManager.scan_account_live_credits", new_callable=AsyncMock)
def test_flow_accounts_check_credits_single(mock_scan):
    mock_scan.return_value = 42

    result = runner.invoke(app, ["flow", "accounts", "check-credits", "--account", "1"], env={"COLUMNS": "140"})
    assert result.exit_code == 0
    assert "Scanning live credits for 1 Google Flow account" in result.output
    assert "42 (Live)" in result.output
    assert "Reset Schedule" in result.output
    mock_scan.assert_called_once_with(1)


@patch("engine.services.flow_accounts.FlowAccountManager.scan_account_live_credits", new_callable=AsyncMock)
def test_flow_accounts_check_credits_with_reset_schedule(mock_scan):
    from engine.services.flow_accounts import get_flow_account_manager
    mgr = get_flow_account_manager()
    acc = mgr.get_account(1)
    prev_reset = acc.reset_schedule if acc else None

    # Simulate account having reset schedule discovered
    mgr.update_live_credits(1, 42, reset_schedule="Her 24 saatte bir (+50)")
    mock_scan.return_value = 42

    try:
        result = runner.invoke(app, ["flow", "accounts", "check-credits", "--account", "1"], env={"COLUMNS": "140"})
        assert result.exit_code == 0
        assert "Account 1: 42 live credits found (Reset: Her 24 saatte bir (+50))" in result.output
        assert "Her 24 saatte bir (+50)" in result.output
    finally:
        mgr.update_live_credits(1, 42, reset_schedule=prev_reset)


@patch("engine.services.flow_accounts.FlowAccountManager.scan_account_live_credits", new_callable=AsyncMock)
def test_flow_accounts_check_credits_all(mock_scan):
    mock_scan.return_value = 100

    result = runner.invoke(app, ["flow", "accounts", "check-credits", "--all"], env={"COLUMNS": "140"})
    assert result.exit_code == 0
    assert "Scanning live credits for 4 Google Flow account" in result.output
    assert "100 (Live)" in result.output
    assert mock_scan.call_count == 4


@patch("engine.services.flow_accounts.FlowAccountManager.scan_account_live_credits", new_callable=AsyncMock)
def test_flow_accounts_check_credits_undetected(mock_scan):
    mock_scan.return_value = None

    result = runner.invoke(app, ["flow", "accounts", "check-credits", "--account", "2"], env={"COLUMNS": "140"})
    assert result.exit_code == 0
    assert "Login Required" in result.output
    mock_scan.assert_called_once_with(2)


@patch("engine.services.flow_accounts.FlowAccountManager.scan_account_live_credits", new_callable=AsyncMock)
def test_flow_accounts_check_credits_json(mock_scan):
    mock_scan.return_value = 55

    result = runner.invoke(app, ["flow", "accounts", "check-credits", "--account", "1", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == 1
    assert "reset_schedule" in data[0]


@patch("engine.services.flow_accounts.FlowAccountManager.scan_account_live_credits", new_callable=AsyncMock)
def test_flow_shortcut_check_credits(mock_scan):
    mock_scan.return_value = 88

    result = runner.invoke(app, ["flow", "check-credits", "--account", "3"], env={"COLUMNS": "140"})
    assert result.exit_code == 0
    assert "88 (Live)" in result.output
    mock_scan.assert_called_once_with(3)


def test_flow_accounts_env():
    result = runner.invoke(app, ["flow", "accounts", "env"])
    assert result.exit_code == 0
    assert 'set "ACTIVE_ACCOUNT_ID=' in result.output
    assert 'set "ACC_1_NAME=' in result.output
    assert 'set "ACC_1_CREDITS=' in result.output
    assert 'set "ACC_1_RESET=' in result.output
    assert 'set "ACC_2_CREDITS=' in result.output
    assert 'set "ACC_2_RESET=' in result.output

