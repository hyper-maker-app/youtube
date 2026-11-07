"""Register cinematic-studio api (FastAPI control plane)."""

from __future__ import annotations

import typer


def register(app: typer.Typer) -> None:
    @app.command("api")
    def api(
        host: str = typer.Option(
            "127.0.0.1",
            "--host",
            help="Bind host (use 0.0.0.0 for LAN)",
        ),
        port: int = typer.Option(
            8090,
            "--port",
            "-p",
            help="Bind port (default 8090)",
            min=1,
            max=65535,
        ),
        reload: bool = typer.Option(
            False,
            "--reload",
            help="Auto-reload on code changes (dev only)",
        ),
    ) -> None:
        """Retired surface; use the CLI or TUI."""
        typer.secho("This surface has been retired. Use cinematic-studio ui or the CLI.", fg="yellow")
        raise typer.Exit(code=1)
