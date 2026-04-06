"""Dashboard commands."""

import typer

app = typer.Typer(invoke_without_command=True)


@app.callback()
def dash_default(ctx: typer.Context):
    """Open the NIO dashboard in the default browser."""
    if ctx.invoked_subcommand is None:
        import webbrowser
        webbrowser.open("http://localhost:4242")


@app.command("start")
def start_dash():
    """Start the dashboard daemon."""
    import subprocess
    import sys
    from pathlib import Path

    plist = Path.home() / "Library" / "LaunchAgents" / "com.shawnos.nio-dash.plist"
    if plist.exists():
        subprocess.run(["launchctl", "load", str(plist)], check=False)
        typer.echo("Dashboard daemon started via launchctl.")
    else:
        typer.echo("Starting dashboard in foreground...")
        subprocess.run(
            [sys.executable, "-m", "nio.dash.server"],
            check=False,
        )


@app.command("stop")
def stop_dash():
    """Stop the dashboard daemon."""
    import subprocess
    from pathlib import Path

    plist = Path.home() / "Library" / "LaunchAgents" / "com.shawnos.nio-dash.plist"
    if plist.exists():
        subprocess.run(["launchctl", "unload", str(plist)], check=False)
        typer.echo("Dashboard daemon stopped.")
    else:
        typer.echo("No launchd plist found. Kill the process manually if running.")
