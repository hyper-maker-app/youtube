#!/usr/bin/env python3
"""Smoke-check studio_core + optional surfaces (no long-running servers)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))


def main() -> int:
    errors: list[str] = []

    try:
        from studio_core.services.dashboard import build_studio_dashboard

        snap = build_studio_dashboard()
        assert "studio_version" in snap
        print("OK  studio_core.dashboard", snap.get("studio_version"))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"dashboard: {exc}")
        print("FAIL studio_core.dashboard", exc)

    try:
        from studio_core.services.execute import execute_action

        r = execute_action("status", mode="inprocess", timeout=60.0)
        assert r.ok, r.stderr
        print("OK  studio_core.execute status")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"execute: {exc}")
        print("FAIL studio_core.execute", exc)

    try:
        from studio_core.services.actions import ACTIONS

        assert len(ACTIONS) >= 10
        print("OK  studio_core.actions", len(ACTIONS))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"actions: {exc}")
        print("FAIL studio_core.actions", exc)

    from typer.testing import CliRunner
    from cinematic_studio_cli import app

    runner = CliRunner()
    for command in ("web", "api", "web-react"):
        result = runner.invoke(app, [command])
        if result.exit_code != 1 or "retired" not in result.stdout.lower():
            errors.append(f"{command}: unexpected retirement response")
        else:
            print(f"OK  {command} retirement")

    if errors:
        print("SMOKE FAILED:", "; ".join(errors))
        return 1
    print("SMOKE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
