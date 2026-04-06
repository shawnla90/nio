"""NIO CLI entry point."""

import typer

from nio.cli.cmd_soul import app as soul_app
from nio.cli.cmd_voice import app as voice_app
from nio.cli.cmd_antislop import app as antislop_app
from nio.cli.cmd_metrics import app as metrics_app
from nio.cli.cmd_team import app as team_app
from nio.cli.cmd_dash import app as dash_app
from nio.cli.cmd_install import app as install_app

app = typer.Typer(
    name="nio",
    help="NIO: Voice DNA, semver souls, anti-slop, live dashboard. A Hermes superset.",
    no_args_is_help=True,
)

app.add_typer(soul_app, name="soul", help="Manage agent souls (list, show, apply, release, diff, checkout)")
app.add_typer(voice_app, name="voice", help="Manage voice profiles (list, show, apply, diff, release)")
app.add_typer(antislop_app, name="antislop", help="Anti-slop registry (check, score, sync, list)")
app.add_typer(metrics_app, name="metrics", help="Performance metrics (show, export, team)")
app.add_typer(team_app, name="team", help="Team mode (init, join, sync, members, release)")
app.add_typer(dash_app, name="dash", help="Web dashboard (start, stop, open)")
app.add_typer(install_app, name="install", help="Bootstrap NIO (install hooks, seed registry, start dashboard)")


@app.command()
def status():
    """Show active soul, voice, slop average, and gateway state."""
    from nio.core.soul import get_active_soul
    from nio.core.voice import get_active_voice
    from nio.core.metrics import get_recent_slop_avg
    from rich.console import Console
    from rich.table import Table

    console = Console()
    soul = get_active_soul()
    voice = get_active_voice()
    slop_avg = get_recent_slop_avg()

    table = Table(title="NIO Status", show_header=False, border_style="dim")
    table.add_column("Key", style="bold")
    table.add_column("Value")
    table.add_row("Soul", soul or "none")
    table.add_row("Voice", voice or "none")
    table.add_row("Slop avg (24h)", f"{slop_avg:.1f}/100" if slop_avg is not None else "no data")
    console.print(table)


@app.command()
def doctor():
    """Run diagnostics: hook installed? db ok? hermes reachable?"""
    from nio.core.db import check_db
    from rich.console import Console

    console = Console()
    checks = {
        "~/.nio/ exists": _check_nio_dir(),
        "nio.db schema": check_db(),
        "Hermes hook installed": _check_hermes_hook(),
        "Dashboard reachable": _check_dash(),
    }
    for label, ok in checks.items():
        icon = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
        console.print(f"  {icon}  {label}")


def _check_nio_dir() -> bool:
    from pathlib import Path
    return Path.home().joinpath(".nio").is_dir()


def _check_hermes_hook() -> bool:
    from pathlib import Path
    return Path.home().joinpath(".hermes", "hooks", "nio", "HOOK.yaml").is_file()


def _check_dash() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:4242/health", timeout=2)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    app()
