"""Register cinematic-studio web (NiceGUI shell)."""

from __future__ import annotations

import typer


def register(app: typer.Typer) -> None:
    @app.command("web")
    def web(
        host: str = typer.Option(
            "127.0.0.1",
            "--host",
            "-h",
            help="Bind host (use 0.0.0.0 for LAN)",
        ),
        port: int = typer.Option(
            8088,
            "--port",
            "-p",
            help="Bind port (default 8088; Streamlit often uses 8501)",
            min=1,
            max=65535,
        ),
        reload: bool = typer.Option(
            False,
            "--reload",
            help="Auto-reload on code changes (dev only)",
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
