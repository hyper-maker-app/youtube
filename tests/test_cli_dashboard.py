"""Tests for CLI studio dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from cli.dashboard import build_studio_dashboard  # noqa: E402
from cli_helpers import run_cli  # noqa: E402


def test_build_studio_dashboard_shape() -> None:
    snap = build_studio_dashboard()
    assert snap["studio_version"]
    assert "studio" in snap
    assert "quota" in snap


def test_build_studio_dashboard_renders_rich() -> None:
    from io import StringIO
    from rich.console import Console
    from cli.dashboard import render_studio_dashboard

    snap = build_studio_dashboard()
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, color_system="standard")
    render_studio_dashboard(snap, console=console)
    text = buf.getvalue()
    assert "Studio Dashboard" in text
    assert "Quota" in text


def test_render_studio_dashboard_cost_breakdown() -> None:
    from rich.console import Console
    from cli.dashboard import render_studio_dashboard

    console = Console(record=True, width=120)
    snap = build_studio_dashboard()
    snap["quota"]["reconciliation"] = {
        "cascade_source": "generation_ledger",
        "entry_count": 1,
        "estimated_total": 1.0,
        "actual_total": 1.0,
        "variance_pct": 0.0,
        "burn_rate_multiplier": 1.0,
        "burn_rate_risk": "low",
    }
    render_studio_dashboard(snap, console=console)
    text = console.export_text()
    assert "Cascade" in text
    assert "ledger" in text.lower()
    assert "Burn Rate" in text


def test_dashboard_command_runs() -> None:
    result = run_cli("dashboard", "--compact")
    assert result.returncode == 0, result.stderr
    assert "Studio Dashboard" in result.stdout
    assert "Quota" in result.stdout


def test_dashboard_json_output() -> None:
    result = run_cli("dashboard", "--json", "--compact")
    assert result.returncode == 0, result.stderr
    assert '"studio_version"' in result.stdout
    assert '"quota"' in result.stdout


if __name__ == "__main__":
    test_build_studio_dashboard_shape()
    test_dashboard_command_runs()
    test_dashboard_json_output()
    print("All CLI dashboard tests passed")
