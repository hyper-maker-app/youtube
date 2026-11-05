"""Register cinematic-studio web-react (TanStack SPA cockpit)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import typer

from cli.shared import console


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _web_react_dir() -> Path:
    return _repo_root() / "web_react"


def _require_npm() -> str:
    npm = shutil.which("npm")
    if not npm:
        console.print(
            "[red]npm not found on PATH.[/red]\n"
            "Install Node.js 20+ (includes npm), then retry.\n"
            "  https://nodejs.org/  ·  or  [bold]sudo apt install npm[/bold]"
        )
        raise typer.Exit(1)
    node = shutil.which("node")
    if not node:
        console.print("[red]node not found on PATH (npm alone is not enough).[/red]")
        raise typer.Exit(1)
    return npm


def _ensure_deps(npm: str, app_dir: Path, *, force_install: bool) -> None:
    modules = app_dir / "node_modules"
    if modules.is_dir() and not force_install:
        return
    console.print(
        f"[cyan]npm install[/cyan] in {app_dir}"
        + (" (--install)" if force_install else " (node_modules missing)")
    )
    result = subprocess.run(
        [npm, "install"],
        cwd=str(app_dir),
        check=False,
    )
    if result.returncode != 0:
        console.print("[red]npm install failed.[/red]")
        raise typer.Exit(result.returncode or 1)


def register(app: typer.Typer) -> None:
    @app.command("web-react")
    def web_react(
        host: str = typer.Option(
            "127.0.0.1",
            "--host",
            help="Vite bind host (use 0.0.0.0 for LAN)",
        ),
        port: int = typer.Option(
            5173,
            "--port",
            "-p",
            help="Vite port (default 5173)",
            min=1,
            max=65535,
        ),
        api_url: str = typer.Option(
            "",
            "--api-url",
            help=(
                "studio_api base URL (sets VITE_STUDIO_API_URL). "
                "Empty = same-origin; dev/preview proxy /v1 → http://127.0.0.1:8090"
            ),
        ),
        install: bool = typer.Option(
            False,
            "--install",
            help="Force npm install before start",
        ),
        preview: bool = typer.Option(
            False,
            "--preview",
            help="Serve production build (npm run build + preview) instead of dev",
        ),
        open_browser: bool = typer.Option(
            False,
            "--open",
            help="Open a browser tab on start",
        ),
    ) -> None:
        """Retired surface; use the CLI or TUI."""
        typer.secho("This surface has been retired. Use cinematic-studio ui or the CLI.", fg="yellow")
        raise typer.Exit(code=1)
