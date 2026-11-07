"""Google Flow CDP Multi-Account Management CLI commands.

Provides inspection, switching, manual login, cooldown resets, and toast notification tests
for the 4-account Google Flow CDP browser pool.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import warnings
from pathlib import Path

import typer
from rich import box
from rich.panel import Panel
from rich.table import Table

from cli.shared import console
from engine.services.flow_accounts import (
    DEFAULT_ACCOUNT_PROFILES,
    FlowAccount,
    FlowAccountManager,
    get_flow_account_manager,
    send_windows_notification,
)


def flow_accounts_status(
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON format"),
) -> None:
    """Display Rich table of the 4 Google Flow accounts and their quota/cooldown status."""
    mgr = get_flow_account_manager()
    accounts = mgr.list_accounts()
    active_id = mgr.active_account_id

    if json_output:
        payload = {
            "active_account_id": active_id,
            "accounts": [acc.to_dict() for acc in accounts],
        }
        console.print_json(json.dumps(payload))
        return

    table = Table(
        title=f"Google Flow CDP Multi-Account Pool ({len(accounts)} Accounts)",
        box=box.ROUNDED,
        header_style="bold cyan",
        title_style="bold magenta",
    )
    table.add_column("ID", justify="center", style="bold", width=4)
    table.add_column("Name", style="white", width=12)
    table.add_column("Profile Directory", style="blue", width=20)
    table.add_column("Status", justify="center", width=16)
    table.add_column("Live Credits", justify="center", width=14)
    table.add_column("Reset Schedule", justify="center", width=18)
    table.add_column("Cooldown", justify="center", width=12)
    table.add_column("Blocks", justify="right", width=8)

    now = time.time()
    for acc in accounts:
        is_active = (acc.id == active_id)

        # Status badge
        if acc.status == "exhausted":
            status_str = "[bold red]✖ exhausted[/bold red]"
            if is_active:
                status_str += " [dim](curr)[/dim]"
        elif acc.status == "active" or is_active:
            status_str = "[bold green]● active[/bold green]"
            if is_active:
                status_str += " [dim](curr)[/dim]"
        elif acc.status == "standby":
            status_str = "[cyan]○ standby[/cyan]"
        else:
            status_str = f"[dim]{acc.status}[/dim]"

        # Profile directory existence check
        phys_path = mgr.resolve_profile_dir(acc.id)
        exists_mark = "✔" if phys_path.is_dir() else "○"
        profile_display = f"{phys_path.name} [dim]({exists_mark})[/dim]"

        # Credits display (live verified vs estimated)
        if acc.live_credits is not None:
            credits_str = f"[bold green]{acc.live_credits} (Live)[/bold green]"
        else:
            credits_str = f"[dim]{acc.remaining_daily_credits}/{acc.daily_quota_limit} (Est)[/dim]"

        reset_str = acc.reset_schedule or "[dim]--[/dim]"

        # Cooldown calculation
        if acc.status == "exhausted" and acc.exhausted_at:
            remaining = max(0.0, 86400.0 - (now - acc.exhausted_at))
            if remaining > 0:
                hrs = int(remaining // 3600)
                mins = int((remaining % 3600) // 60)
                secs = int(remaining % 60)
                cooldown_str = f"[bold yellow]{hrs:02d}h {mins:02d}m[/bold yellow]"
            else:
                cooldown_str = "[green]Expired[/green]"
        else:
            cooldown_str = "[dim]Ready (0s)[/dim]"

        blocks_str = str(acc.total_blocks_rendered)
        name_display = f"{acc.name}\n[dim]{acc.email}[/dim]" if acc.email else acc.name

        table.add_row(
            str(acc.id),
            name_display,
            profile_display,
            status_str,
            credits_str,
            reset_str,
            cooldown_str,
            blocks_str,
        )

    console.print(table)
    active_acc = mgr.get_account(active_id)
    active_name = active_acc.name if active_acc else f"Account {active_id}"
    console.print(
        Panel(
            f"[bold]Active Daemon Target:[/bold] Account {active_id} ({active_name})\n"
            f"[bold]CDP Server Port:[/bold] 9223\n"
            f"[yellow]Google Flow Credit Model: 1000 monthly credits pool + 50 daily renewable credits every 24 hours.[/yellow]\n"
            f"[dim]Run 'cinematic-studio flow accounts switch <id>' to switch active account.\n"
            f"Run 'cinematic-studio flow accounts login <id>' to authenticate an account in Chrome.\n"
            f"Run 'cinematic-studio flow accounts reset' to reset 24h cooldowns.[/dim]",
            border_style="cyan",
            title="Account Supervision",
        )
    )


def flow_accounts_switch(
    account_id: int = typer.Argument(..., help="Target account ID to activate"),
) -> None:
    """Manually switch active Google Flow account."""
    mgr = get_flow_account_manager()
    acc = mgr.get_account(account_id)
    if not acc:
        console.print(f"[bold red]Error: Invalid account ID {account_id}. Account not found in pool.[/bold red]")
        raise typer.Exit(1)

    try:
        acc = mgr.set_active_account(account_id)
        profile_dir = mgr.resolve_profile_dir(account_id)
        console.print(
            Panel(
                f"[bold green]✔ Successfully switched active Flow Account to {acc.name} (ID: {acc.id})[/bold green]\n"
                f"Profile Path: [cyan]{profile_dir}[/cyan]\n"
                f"Daily Quota: {acc.daily_credits_used}/{acc.daily_quota_limit} credits used\n"
                f"Status: {acc.status.upper()}",
                title="Account Switched",
                border_style="green",
            )
        )
    except Exception as exc:
        console.print(f"[bold red]Failed to switch active account: {exc}[/bold red]")
        raise typer.Exit(1)


def flow_accounts_login(
    account_id: int = typer.Argument(1, help="Account ID to launch and authenticate"),
    port: int = typer.Option(9223, "--port", "-p", help="CDP Remote Debugging Port"),
) -> None:
    """Launch visible Chrome window for the specified account so user can sign in."""
    mgr = get_flow_account_manager()
    acc = mgr.get_account(account_id)
    if not acc:
        console.print(f"[bold red]Error: Invalid account ID {account_id}. Account not found in pool.[/bold red]")
        raise typer.Exit(1)

    profile_dir = mgr.resolve_profile_dir(account_id)
    acc_name = acc.name if acc else f"Account {account_id}"

    console.print(
        f"[bold cyan]Launching Google Chrome for {acc_name} (Port {port})...[/bold cyan]"
    )
    console.print(f"[dim]Profile Directory: {profile_dir}[/dim]")

    try:
        mgr.launch_flow_chrome(account_id=account_id, automation=False, cdp_port=port)
        console.print(
            Panel(
                f"[bold green]Chrome is now running with profile '{profile_dir.name}'![/bold green]\n\n"
                f"[bold yellow]Next Steps:[/bold yellow]\n"
                f"1. In the opened Chrome browser, sign into your Google account on Google Flow.\n"
                f"2. Ensure you have access to the Google Flow video creator UI.\n"
                f"3. Do NOT close the browser window when done — keep it open or minimized.\n"
                f"4. The production engine connects via Port {port} to render cinematic scenes.",
                title=f"Authentication: {acc_name}",
                border_style="green",
            )
        )
    except Exception as exc:
        console.print(f"[bold red]Failed to launch Chrome: {exc}[/bold red]")
        raise typer.Exit(1)


def flow_accounts_reset() -> None:
    """Reset all exhaustion cooldowns and daily credit counters across all accounts in the pool."""
    mgr = get_flow_account_manager()
    try:
        mgr.reset_all_cooldowns()
        accounts_count = len(mgr.list_accounts())
        console.print(
            Panel(
                f"[bold green]✔ All {accounts_count} Google Flow accounts have been reset![/bold green]\n"
                "• All 'exhausted' statuses cleared back to standby/active\n"
                "• 24-hour cooldown timers cleared\n"
                "• Daily credit consumption counters reset to 0",
                title="Cooldowns Reset",
                border_style="green",
            )
        )
    except Exception as exc:
        console.print(f"[bold red]Failed to reset cooldowns: {exc}[/bold red]")
        raise typer.Exit(1)


def flow_accounts_notify_test() -> None:
    """Test Windows 10/11 Toast notification dispatch."""
    mgr = get_flow_account_manager()
    console.print("[cyan]Dispatching Windows Toast Notification...[/cyan]")
    try:
        mgr.send_windows_notification(
            "Grok Cinematic Studio",
            "Google Flow CDP: Windows Toast notification system is working correctly!",
        )
        console.print(
            Panel(
                "[bold green]✔ Windows Toast notification successfully dispatched![/bold green]\n"
                "[dim]Look at the bottom-right corner of your monitor or open Windows Action Center (Win + N).[/dim]",
                title="Toast Notification Test",
                border_style="green",
            )
        )
    except Exception as exc:
        console.print(f"[bold red]Failed to send notification: {exc}[/bold red]")
        raise typer.Exit(1)


def flow_accounts_active_id() -> None:
    """Print the currently active account ID (1 to 4) as a plain integer."""
    mgr = get_flow_account_manager()
    print(mgr.active_account_id)


def flow_accounts_add(
    name: str = typer.Option(None, "--name", "-n", help="Optional friendly name or email"),
    profile: str = typer.Option(None, "--profile", "-p", help="Custom profile directory name"),
    quota: int = typer.Option(50, "--quota", "-q", help="Daily credit quota limit"),
) -> None:
    """Add a new Google Flow account to the rotation pool (e.g. Account 5, 6)."""
    mgr = get_flow_account_manager()
    acc = mgr.add_account(name=name, profile_dir_name=profile, daily_quota_limit=quota)
    console.print(
        Panel(
            f"[bold green]✔ Successfully added Account {acc.id} to the pool![/bold green]\n"
            f"Profile Directory: [cyan]{acc.profile_dir_name}[/cyan]\n"
            f"Daily Quota: {acc.daily_quota_limit} credits\n\n"
            f"[dim]Run 'cinematic-studio flow accounts login {acc.id}' to open Chrome and authenticate.[/dim]",
            title="Account Added",
            border_style="green",
        )
    )


def flow_accounts_remove(
    account_id: int = typer.Argument(..., help="Account ID to remove"),
) -> None:
    """Remove a Google Flow account from the rotation pool."""
    mgr = get_flow_account_manager()
    success = mgr.remove_account(account_id)
    if success:
        console.print(f"[bold green]✔ Account {account_id} removed from the pool.[/bold green]")
    else:
        console.print(f"[bold red]Account {account_id} not found.[/bold red]")
        raise typer.Exit(1)


def _silence_windows_asyncio_pipe_errors() -> None:
    """Eliminates Windows Python 3.12+ asyncio ProactorBasePipeTransport closed pipe errors.

    When Playwright's node driver subprocess transport or CDP pipe transports are finalized
    after asyncio.run() completes, BaseSubprocessTransport.__del__ and
    _ProactorBasePipeTransport.__del__ trigger 'ValueError: I/O operation on closed pipe'
    in fileno() / sock.close(). This helper safely suppresses unraisable closed pipe exceptions.
    """
    if sys.platform != "win32":
        return

    try:
        from asyncio.base_subprocess import BaseSubprocessTransport
        from asyncio.proactor_events import _ProactorBasePipeTransport

        _orig_subproc_del = BaseSubprocessTransport.__del__

        def _safe_subproc_del(self, _warn=warnings.warn):
            try:
                _orig_subproc_del(self, _warn=_warn)
            except (ValueError, OSError, RuntimeError):
                pass

        BaseSubprocessTransport.__del__ = _safe_subproc_del

        _orig_pipe_del = _ProactorBasePipeTransport.__del__

        def _safe_pipe_del(self, _warn=warnings.warn):
            try:
                _orig_pipe_del(self, _warn=_warn)
            except (ValueError, OSError, RuntimeError):
                pass

        _ProactorBasePipeTransport.__del__ = _safe_pipe_del

        _orig_pipe_repr = _ProactorBasePipeTransport.__repr__

        def _safe_pipe_repr(self):
            try:
                return _orig_pipe_repr(self)
            except (ValueError, OSError, RuntimeError):
                return "<_ProactorBasePipeTransport closed>"

        _ProactorBasePipeTransport.__repr__ = _safe_pipe_repr
    except Exception:
        pass

    try:
        _orig_unraisablehook = sys.unraisablehook

        def _safe_unraisablehook(unraisable):
            msg = str(unraisable.exc_value).lower()
            if unraisable.exc_type in (ValueError, OSError, RuntimeError) and (
                "closed pipe" in msg or "event loop is closed" in msg
            ):
                return
            if _orig_unraisablehook:
                _orig_unraisablehook(unraisable)

        sys.unraisablehook = _safe_unraisablehook
    except Exception:
        pass

    try:
        warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed.*")
        warnings.filterwarnings("ignore", category=ResourceWarning, message=".*transport.*")
        warnings.filterwarnings("ignore", category=ResourceWarning, message=".*pipe.*")
    except Exception:
        pass


def flow_accounts_check_credits(
    all_accounts: bool = typer.Option(False, "--all", "-a", help="Scan all accounts sequentially"),
    account_id: int | None = typer.Option(None, "--account", "-i", help="Specific account ID to scan"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON format"),
) -> None:
    """Scan and synchronize live Google Flow credits directly from the browser UI."""
    _silence_windows_asyncio_pipe_errors()

    mgr = get_flow_account_manager()
    accounts = mgr.list_accounts()

    if account_id is not None:
        target_accounts = [acc for acc in accounts if acc.id == account_id]
        if not target_accounts:
            console.print(f"[bold red]Account ID {account_id} not found.[/bold red]")
            raise typer.Exit(1)
    else:
        target_accounts = accounts

    if not json_output:
        console.print(
            Panel(
                f"[bold cyan]Scanning live credits for {len(target_accounts)} Google Flow account(s)...[/bold cyan]\n"
                f"[dim]Connecting to Chrome via CDP (Port 9223) to inspect live session DOM.[/dim]",
                title="Google Flow CDP Live Credit Scanner",
                border_style="cyan",
            )
        )

    results: dict[int, int | None] = {}

    async def _run_scans() -> None:
        for acc in target_accounts:
            if not json_output:
                console.print(f"[cyan]Scanning Account {acc.id} ({acc.name})...[/cyan]")
            try:
                credits = await mgr.scan_account_live_credits(acc.id)
                results[acc.id] = credits
                if credits is not None:
                    mgr.update_live_credits(acc.id, credits)
                    refreshed_acc = mgr.get_account(acc.id)
                    current_reset = (refreshed_acc.reset_schedule if refreshed_acc else None) or acc.reset_schedule
                    if not json_output:
                        if current_reset:
                            console.print(f"  [bold green]✔ Account {acc.id}: {credits} live credits found (Reset: {current_reset})[/bold green]")
                        else:
                            console.print(f"  [bold green]✔ Account {acc.id}: {credits} live credits found[/bold green]")
                else:
                    if not json_output:
                        console.print(f"  [bold yellow]⚠ Account {acc.id}: Undetectable / Login Required[/bold yellow]")
            except Exception as exc:
                results[acc.id] = None
                if not json_output:
                    console.print(f"  [bold red]✖ Account {acc.id} error: {exc}[/bold red]")

    try:
        asyncio.run(_run_scans())
    except Exception as exc:
        if not json_output:
            console.print(f"[bold red]Live credit batch scan error: {exc}[/bold red]")

    # Refresh accounts list after scan
    accounts = mgr.list_accounts()

    if json_output:
        payload = [
            {
                "id": acc.id,
                "name": acc.name,
                "email": acc.email,
                "live_credits": acc.live_credits,
                "reset_schedule": acc.reset_schedule,
                "status": acc.status,
            }
            for acc in accounts
            if acc.id in [t.id for t in target_accounts]
        ]
        console.print_json(json.dumps(payload))
        return

    table = Table(
        title="Google Flow CDP - Live Account Credits",
        box=box.ROUNDED,
        header_style="bold cyan",
        title_style="bold magenta",
    )
    table.add_column("ID", justify="center", style="bold", width=4)
    table.add_column("Name", style="white", width=12)
    table.add_column("Email", style="blue", width=26)
    table.add_column("Live Credits", justify="center", width=16)
    table.add_column("Reset Schedule", justify="center", width=20)
    table.add_column("Status", justify="center", width=16)

    for acc in accounts:
        if acc.id not in [t.id for t in target_accounts]:
            continue

        email_str = acc.email or "[dim]Unknown / Not Logged In[/dim]"

        if acc.live_credits is not None:
            credits_str = f"[bold green]{acc.live_credits} (Live)[/bold green]"
        else:
            credits_str = "[bold yellow]Login Required[/bold yellow]"

        reset_str = acc.reset_schedule or "[dim]--[/dim]"

        if acc.status == "active":
            status_str = "[bold green]● active[/bold green]"
        elif acc.status == "exhausted":
            status_str = "[bold red]✖ exhausted[/bold red]"
        elif acc.status == "standby":
            status_str = "[cyan]○ standby[/cyan]"
        else:
            status_str = f"[dim]{acc.status}[/dim]"

        table.add_row(
            str(acc.id),
            acc.name,
            email_str,
            credits_str,
            reset_str,
            status_str,
        )

    console.print(table)


def flow_accounts_env() -> None:
    """Print CMD batch environment variable export statements for accounts.

    Designed for chrome_flow.bat to source account names, credits, reset schedules,
    and active ID without PowerShell parsing or quoting issues.
    """
    mgr = get_flow_account_manager()
    accounts = mgr.list_accounts()
    print(f'set "ACTIVE_ACCOUNT_ID={mgr.active_account_id}"')
    for acc in accounts:
        display_name = (acc.email if acc.email else acc.name).replace('"', '').replace('%', '')
        print(f'set "ACC_{acc.id}_NAME={display_name}"')
        credits_str = f"{acc.live_credits} Kredi" if acc.live_credits is not None else "Giris Yapilmali"
        credits_str = str(credits_str).replace('"', '').replace('%', '')
        print(f'set "ACC_{acc.id}_CREDITS={credits_str}"')
        reset_str = f"{acc.reset_schedule}" if acc.reset_schedule else "Aylik/Gunluk"
        reset_str = str(reset_str).replace('"', '').replace('%', '')
        print(f'set "ACC_{acc.id}_RESET={reset_str}"')


def register(app: typer.Typer, parent_flow_app: typer.Typer | None = None) -> None:
    """Registers all account management commands into the provided Typer sub-app."""
    app.command("status")(flow_accounts_status)
    app.command("switch")(flow_accounts_switch)
    app.command("login")(flow_accounts_login)
    app.command("reset")(flow_accounts_reset)
    app.command("add")(flow_accounts_add)
    app.command("remove")(flow_accounts_remove)
    app.command("notify-test")(flow_accounts_notify_test)
    app.command("active-id")(flow_accounts_active_id)
    app.command("check-credits")(flow_accounts_check_credits)
    app.command("scan-credits")(flow_accounts_check_credits)
    app.command("sync-credits")(flow_accounts_check_credits)
    app.command("env")(flow_accounts_env)
    if parent_flow_app is not None:
        parent_flow_app.command("status", help="Shortcut for 'flow accounts status'")(flow_accounts_status)
        parent_flow_app.command("switch", help="Shortcut for 'flow accounts switch'")(flow_accounts_switch)
        parent_flow_app.command("login", help="Shortcut for 'flow accounts login'")(flow_accounts_login)
        parent_flow_app.command("reset", help="Shortcut for 'flow accounts reset'")(flow_accounts_reset)
        parent_flow_app.command("add", help="Shortcut for 'flow accounts add'")(flow_accounts_add)
        parent_flow_app.command("notify-test", help="Shortcut for 'flow accounts notify-test'")(flow_accounts_notify_test)
        parent_flow_app.command("check-credits", help="Shortcut for 'flow accounts check-credits'")(flow_accounts_check_credits)
        parent_flow_app.command("scan-credits", help="Shortcut for 'flow accounts scan-credits'")(flow_accounts_check_credits)
        parent_flow_app.command("env", help="Shortcut for 'flow accounts env'")(flow_accounts_env)
