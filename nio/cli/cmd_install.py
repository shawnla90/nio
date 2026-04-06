"""NIO install and bootstrap command."""

import typer

app = typer.Typer(invoke_without_command=True)


@app.callback()
def install(
    ctx: typer.Context,
    migrate_hermes: bool = typer.Option(False, "--migrate-hermes", help="Import existing Hermes SOUL.md as a NIO soul"),
):
    """Bootstrap NIO: create ~/.nio/, seed registry, install Hermes hook, start dashboard."""
    if ctx.invoked_subcommand is not None:
        return

    from nio.core.db import init_db
    from nio.core.soul import seed_registry
    from nio.core.voice import seed_voices
    from rich.console import Console
    from pathlib import Path
    import shutil

    console = Console()
    nio_home = Path.home() / ".nio"

    # Create directory structure
    console.print("[bold]Bootstrapping NIO...[/bold]\n")
    for subdir in ["bin", "lib", "registry/souls", "registry/voice-profiles",
                   "active", "teams", "logs", "cache"]:
        (nio_home / subdir).mkdir(parents=True, exist_ok=True)
    console.print("  [green]OK[/green]  ~/.nio/ directory tree")

    # Init database
    init_db()
    console.print("  [green]OK[/green]  nio.db initialized")

    # Seed registry from bundled souls + voices
    seed_registry()
    console.print("  [green]OK[/green]  Registry seeded (souls + voices)")

    # Seed voice profiles
    seed_voices()
    console.print("  [green]OK[/green]  Voice profiles seeded")

    # Install Hermes hook
    _install_hermes_hook(console)

    # Install Claude Code skill
    _install_claude_code_skill(console)

    # Write default config
    _write_default_config(nio_home, console)

    # Install launchd plist for dashboard
    _install_dash_plist(console)

    # Migrate hermes if requested
    if migrate_hermes:
        _migrate_hermes(console)

    console.print("\n[bold green]NIO installed.[/bold green]")
    console.print("  Dashboard: http://localhost:4242")
    console.print("  Run: nio status")
    console.print("  Run: nio doctor")


def _install_hermes_hook(console):
    """Install NIO hook into Hermes."""
    from pathlib import Path

    hook_dir = Path.home() / ".hermes" / "hooks" / "nio"
    hook_dir.mkdir(parents=True, exist_ok=True)

    # Write HOOK.yaml
    hook_yaml = hook_dir / "HOOK.yaml"
    hook_yaml.write_text(
        'name: nio\n'
        'description: "NIO voice DNA, anti-slop, metrics, and soul pipeline"\n'
        'events:\n'
        '  - gateway:startup\n'
        '  - session:start\n'
        '  - agent:start\n'
        '  - agent:end\n'
        '  - command:*\n'
    )

    # Write handler.py
    handler_py = hook_dir / "handler.py"
    handler_py.write_text(
        'import sys, os\n'
        'sys.path.insert(0, os.path.expanduser("~/.nio/lib"))\n'
        '\n'
        'from nio.hermes_bridge.middleware import handle as nio_handle\n'
        '\n'
        'async def handle(event_type, context):\n'
        '    return await nio_handle(event_type, context)\n'
    )

    console.print("  [green]OK[/green]  Hermes hook installed at ~/.hermes/hooks/nio/")


def _install_claude_code_skill(console):
    """Install NIO skill for Claude Code."""
    from pathlib import Path

    skill_dir = Path.home() / ".claude" / "skills" / "nio"
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Find the bundled skill.md
    pkg_skill = Path(__file__).parent.parent / "claude_code" / "skill.md"
    target_skill = skill_dir / "SKILL.md"

    if pkg_skill.exists():
        import shutil
        shutil.copy2(pkg_skill, target_skill)
        console.print("  [green]OK[/green]  Claude Code skill installed")
    else:
        console.print("  [yellow]SKIP[/yellow]  Claude Code skill (bundled file not found)")


def _write_default_config(nio_home, console):
    """Write default config.yaml."""
    config_path = nio_home / "config.yaml"
    if not config_path.exists():
        config_path.write_text(
            '# NIO configuration\n'
            'dash:\n'
            '  port: 4242\n'
            '  autostart: true\n'
            'telemetry:\n'
            '  enabled: false\n'
        )
    console.print("  [green]OK[/green]  config.yaml")


def _install_dash_plist(console):
    """Install launchd plist for the dashboard daemon."""
    from pathlib import Path
    import subprocess
    import sys

    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / "com.shawnos.nio-dash.plist"

    python_path = sys.executable
    nio_home = Path.home() / ".nio"

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.shawnos.nio-dash</string>

    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>-m</string>
        <string>nio.dash.server</string>
    </array>

    <key>WorkingDirectory</key>
    <string>{nio_home}</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{nio_home}/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>{Path.home()}</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>{nio_home}/logs/dash-stdout.log</string>

    <key>StandardErrorPath</key>
    <string>{nio_home}/logs/dash-stderr.log</string>

    <key>ThrottleInterval</key>
    <integer>30</integer>
</dict>
</plist>"""

    plist_path.write_text(plist_content)

    # Load the plist
    subprocess.run(["launchctl", "load", str(plist_path)], check=False, capture_output=True)
    console.print("  [green]OK[/green]  Dashboard daemon installed (com.shawnos.nio-dash)")


def _migrate_hermes(console):
    """Import existing Hermes SOUL.md into a NIO soul."""
    from pathlib import Path

    soul_path = Path.home() / ".hermes" / "memories" / "SOUL.md"
    if not soul_path.exists():
        console.print("  [yellow]SKIP[/yellow]  No Hermes SOUL.md found")
        return

    from nio.core.soul import create_soul_from_content

    content = soul_path.read_text()
    result = create_soul_from_content("hermes-migrated", content, voice="shawn-builder")
    console.print(f"  [green]OK[/green]  Migrated Hermes SOUL.md to {result}")
