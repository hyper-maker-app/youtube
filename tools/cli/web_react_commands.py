"""Register cinematic-studio web-react (TanStack SPA cockpit)."""

from __future__ import annotations

import typer


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
