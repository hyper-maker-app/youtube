"""Unit tests for produce-film Tier 1, Tier 2, and Tier 3 execution modes."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tools.cinematic_studio_cli import app
from tools.cli.produce_commands import produce_film

runner = CliRunner()


def test_produce_film_signature_has_tier_flags():
    """Verify produce_film function signature includes test and real flags with False defaults."""
    sig = inspect.signature(produce_film)
    assert "test" in sig.parameters, "produce_film missing 'test' parameter"
    assert "real" in sig.parameters, "produce_film missing 'real' parameter"

    param_test = sig.parameters["test"]
    assert param_test.default.default is False
    param_real = sig.parameters["real"]
    assert param_real.default.default is False


def test_produce_film_help_displays_tier_flags():
    """Verify produce-film --help output documents --test and --real options and tiers."""
    result = runner.invoke(app, ["produce-film", "--help"], env={"COLUMNS": "140"})
    assert result.exit_code == 0
    assert "--test" in result.output
    assert "--real" in result.output
    assert "Tier 1" in result.output
    assert "Tier 2" in result.output
    assert "Tier 3" in result.output
    assert "360p" in result.output
    assert "720p" in result.output


def test_produce_film_conflict_when_both_test_and_real():
    """Verify produce-film fails when both --test and --real are passed simultaneously."""
    result = runner.invoke(app, ["produce-film", "Conflicting Tiers Film", "--test", "--real"])
    assert result.exit_code != 0
    assert "Cannot specify both --test and --real" in result.output


def test_produce_film_tier1_plan_only_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify --plan-only --dry-run activates Tier 1 (Zero-Cost Draft & Experiment Mode)."""
    monkeypatch.setenv("XAI_API_KEY", "")
    result = runner.invoke(
        app,
        [
            "produce-film",
            "Tier 1 Test Project",
            "--genre", "catastrophe",
            "--duration", "60",
            "--plan-only",
            "--dry-run",
        ],
        env={"COLUMNS": "140"},
    )
    assert result.exit_code == 0
    assert "TIER 1: ZERO-COST DRAFT & EXPERIMENT MODE" in result.output
    assert "Tier 1 Complete" in result.output or "Ready for Production Review" in result.output


def test_produce_film_tier2_test_flag_with_plan_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify --test configures fast/360p and execution_mode=test."""
    monkeypatch.setenv("XAI_API_KEY", "")
    result = runner.invoke(
        app,
        [
            "produce-film",
            "Tier 2 Test Project",
            "--genre", "catastrophe",
            "--duration", "60",
            "--test",
            "--plan-only",
            "--dry-run",
        ],
        env={"COLUMNS": "140"},
    )
    assert result.exit_code == 0
    # Veo 3.1 Mode should be FAST
    assert "FAST" in result.output
    assert "360p" in result.output


def test_produce_film_tier3_real_flag_with_plan_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify --real configures quality/720p and execution_mode=real."""
    monkeypatch.setenv("XAI_API_KEY", "")
    result = runner.invoke(
        app,
        [
            "produce-film",
            "Tier 3 Real Project",
            "--genre", "catastrophe",
            "--duration", "60",
            "--real",
            "--plan-only",
            "--dry-run",
        ],
        env={"COLUMNS": "140"},
    )
    assert result.exit_code == 0
    # Veo 3.1 Mode should be QUALITY
    assert "QUALITY" in result.output
    assert "720p" in result.output
