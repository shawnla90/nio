"""NIO CLI entry point."""

import typer

from nio.cli.cmd_antislop import app as antislop_app
from nio.cli.cmd_cc import app as cc_app
from nio.cli.cmd_dash import app as dash_app
from nio.cli.cmd_install import app as install_app
from nio.cli.cmd_metrics import app as metrics_app
from nio.cli.cmd_setup import app as setup_app
from nio.cli.cmd_soul import app as soul_app
from nio.cli.cmd_team import app as team_app
from nio.cli.cmd_voice import app as voice_app

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
app.add_typer(setup_app, name="setup", help="Interactive setup wizard (mode, platforms, memory, verify)")
app.add_typer(cc_app, name="cc", help="Claude Code session management (start, turn, end, status, context)")


@app.command()
def status():
    """Show active soul, voice, slop average, and gateway state."""
    from pathlib import Path

    if not Path.home().joinpath(".nio").is_dir():
        from rich.console import Console
        console = Console()
        console.print("[yellow]NIO not installed.[/yellow] Run: [green]nio install[/green]")
        raise typer.Exit(0)

    from nio.cli.boot import boot_animated, boot_status
    from nio.core.metrics import get_recent_slop_avg
    from nio.core.soul import get_active_soul
    from nio.core.voice import get_active_voice

    soul = get_active_soul() or "none"
    voice = get_active_voice() or "none"
    try:
        slop_avg = get_recent_slop_avg()
        slop_str = f"{slop_avg:.1f}/100" if slop_avg is not None else "no data"
    except Exception:
        slop_str = "no data"

    hermes = "hooked" if _check_hermes_hook() else "not found"
    dash = ":4242" if _check_dash() else "stopped"

    boot_animated()
    boot_status(soul=soul, voice=voice, slop=slop_str, dash=dash, hermes=hermes)


@app.command()
def doctor():
    """Run diagnostics: hook installed? db ok? hermes reachable?"""
    from pathlib import Path

    from rich.console import Console

    from nio.core.db import check_db

    console = Console()
    # Claude Code skill
    cc_skill = Path.home().joinpath(".claude", "skills", "nio", "SKILL.md").is_file()

    checks = {
        "~/.nio/ exists": _check_nio_dir(),
        "nio.db schema": check_db(),
        "Hermes hook installed": _check_hermes_hook(),
        "Claude Code skill": cc_skill,
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
