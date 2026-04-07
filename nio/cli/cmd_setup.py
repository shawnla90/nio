"""NIO setup wizard.

Interactive 5-stage setup: mode, access, platforms, memory, verify.
Each stage re-runnable via `nio setup <stage>`.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def setup_default(ctx: typer.Context):
    """Interactive setup wizard. Runs all stages."""
    if ctx.invoked_subcommand is None:
        import webbrowser

        # Boot animation
        try:
            from nio.cli.boot import boot_animated
            boot_animated()
        except Exception:
            pass

        # Open dashboard in browser
        console.print("\n  [dim]Opening dashboard at localhost:4242...[/dim]\n")
        try:
            webbrowser.open("http://localhost:4242")
        except Exception:
            pass

        console.print(Panel(
            "[bold green]NIO Setup[/bold green]\n\n"
            "This sets up your agent in 5 steps:\n"
            "  [green]1.[/green] How you want to use NIO (all repos or one project)\n"
            "  [green]2.[/green] Choose access mode (local or remote via phone)\n"
            "  [green]3.[/green] Connect platforms (Discord, WhatsApp, Telegram...)\n"
            "  [green]4.[/green] Import memory from previous sessions\n"
            "  [green]5.[/green] Verify everything works\n",
            border_style="green",
        ))
        console.print()

        setup_mode()
        setup_access()
        setup_platforms()
        setup_memory()
        setup_verify()

        # Build final panel with remote URL if configured
        from nio.core.tunnel import get_access_config
        access = get_access_config()
        lines = [
            "[bold green]NIO is ready.[/bold green]\n",
            "  Dashboard:  [link=http://localhost:4242]localhost:4242[/link]",
        ]
        if access.get("mode") == "remote":
            url = access.get("tunnel_url", "")
            if url and url != "quick":
                lines.append(f"  Remote:     [link=https://{url}/chat]https://{url}/chat[/link]")
            else:
                lines.append("  Remote:     Quick tunnel (URL shown on nio start)")
        lines.extend([
            "  Status:     [green]nio status[/green]",
            "  Session:    [green]nio cc start[/green]",
            "  Start:      [green]nio start[/green]",
        ])
        console.print(Panel("\n".join(lines), border_style="green"))


@app.command("mode")
def setup_mode():
    """Stage 1: Choose global or team mode."""
    from pathlib import Path

    import yaml

    console.print("\n[bold green]Step 1: How do you want to use NIO?[/bold green]\n")

    console.print("  [green]global[/green]  Use NIO everywhere. One personality, one voice, all your repos.")
    console.print("          Best for solo builders using Claude Code.\n")
    console.print("  [green]team[/green]    Use NIO for this project only. Shared with collaborators.")
    console.print("          Best when a team needs the same agent personality.\n")

    choice = Prompt.ask("  Mode", choices=["global", "team"], default="global")

    config_path = Path.home() / ".nio" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config = {}
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

    config["mode"] = choice

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    console.print(f"\n  [green]Mode set to: {choice}[/green]")

    if choice == "global":
        # Check for existing Hermes SOUL.md and offer to import
        hermes_soul = Path.home() / ".hermes" / "SOUL.md"
        if hermes_soul.exists():
            if Confirm.ask("  Import existing Hermes SOUL.md as a NIO soul?", default=True):
                from nio.core.soul import create_soul_from_content
                content = hermes_soul.read_text()
                path = create_soul_from_content("hermes-migrated", content)
                console.print(f"  [green]Imported to: {path}[/green]")

        # Set defaults
        active_soul = Path.home() / ".nio" / "active" / "soul.txt"
        if not active_soul.exists():
            active_soul.parent.mkdir(parents=True, exist_ok=True)
            active_soul.write_text("nio-core@0.1.0")
            console.print("  [green]Personality set: nio-core[/green] (direct, builder-first, no fluff)")

        active_voice = Path.home() / ".nio" / "active" / "voice.txt"
        if not active_voice.exists():
            active_voice.parent.mkdir(parents=True, exist_ok=True)
            active_voice.write_text("shawn-builder@1.0.0")
            console.print("  [green]Writing style set: shawn-builder[/green] (casual, earned authority, minimal hedging)")

    elif choice == "team":
        if Confirm.ask("  Initialize team mode in current directory?", default=True):
            team_name = Prompt.ask("  Team name", default="my-team")
            from nio.core.team import init_team
            result = init_team(team_name)
            console.print(f"  [green]Team initialized: {result.get('team_id', team_name)}[/green]")

    console.print()


@app.command("access")
def setup_access():
    """Stage 2: Configure local or remote access."""
    import subprocess

    from nio.core.tunnel import (
        check_cloudflared_installed,
        check_cloudflared_logged_in,
        create_tunnel,
        list_tunnels,
        write_access_config,
    )

    console.print("\n[bold green]Step 2: How will you access NIO?[/bold green]\n")
    console.print("  [green]local[/green]   Browser on this Mac only (localhost:4242)")
    console.print("          No tunnel needed. Simplest setup.\n")
    console.print("  [green]remote[/green]  Access from phone, tablet, or anywhere")
    console.print("          Uses a Cloudflare tunnel for secure HTTPS.\n")

    choice = Prompt.ask("  Access mode", choices=["local", "remote"], default="local")

    if choice == "local":
        write_access_config(mode="local")
        console.print("\n  [green]Access mode: local[/green]")
        console.print("  Dashboard at localhost:4242. No tunnel needed.\n")
        return

    # Remote mode: set up Cloudflare tunnel
    cf_path = check_cloudflared_installed()
    if not cf_path:
        console.print("\n  [yellow]cloudflared not found.[/yellow]")
        if Confirm.ask("  Install via Homebrew?", default=True):
            result = subprocess.run(
                ["brew", "install", "cloudflared"],
                capture_output=False,
            )
            if result.returncode != 0:
                console.print("  [red]Install failed. Set up manually: brew install cloudflared[/red]")
                write_access_config(mode="local")
                return
            console.print("  [green]cloudflared installed.[/green]\n")
        else:
            console.print("  [dim]Falling back to local mode.[/dim]")
            write_access_config(mode="local")
            return

    # Check login
    if not check_cloudflared_logged_in():
        console.print("\n  [yellow]Not logged in to Cloudflare.[/yellow]")
        console.print("  This will open your browser to authenticate.\n")
        if Confirm.ask("  Run cloudflared tunnel login?", default=True):
            subprocess.run(["cloudflared", "tunnel", "login"])
            if not check_cloudflared_logged_in():
                console.print("  [red]Login failed. Try again: cloudflared tunnel login[/red]")
                write_access_config(mode="local")
                return
            console.print("  [green]Logged in.[/green]\n")
        else:
            console.print("  [dim]Falling back to local mode.[/dim]")
            write_access_config(mode="local")
            return

    # Tunnel selection
    tunnels = list_tunnels()
    tunnel_name = ""

    if tunnels:
        table = Table(show_header=True, border_style="dim")
        table.add_column("Name", style="bold")
        table.add_column("ID")
        for t in tunnels:
            table.add_row(t["name"], t["id"][:12])
        console.print(table)
        console.print()

        use_existing = Prompt.ask(
            "  Use existing tunnel or create new?",
            choices=["existing", "new"], default="existing",
        )

        if use_existing == "existing":
            default_name = tunnels[0]["name"] if tunnels else "nio-chat"
            tunnel_name = Prompt.ask("  Tunnel name", default=default_name)
        else:
            tunnel_name = Prompt.ask("  New tunnel name", default="nio-chat")
            if not create_tunnel(tunnel_name):
                console.print(f"  [red]Failed to create tunnel '{tunnel_name}'[/red]")
                write_access_config(mode="local")
                return
            console.print(f"  [green]Tunnel '{tunnel_name}' created.[/green]\n")
    else:
        console.print("  No existing tunnels found.\n")
        tunnel_name = Prompt.ask("  Tunnel name", default="nio-chat")
        if not create_tunnel(tunnel_name):
            console.print(f"  [red]Failed to create tunnel '{tunnel_name}'[/red]")
            write_access_config(mode="local")
            return
        console.print(f"  [green]Tunnel '{tunnel_name}' created.[/green]\n")

    # Domain selection
    console.print("  [green]custom[/green]  Your own domain (e.g. nio.shawnos.ai)")
    console.print("  [green]auto[/green]    Auto-generated URL (changes on restart)\n")

    domain_choice = Prompt.ask("  Domain type", choices=["custom", "auto"], default="custom")

    if domain_choice == "custom":
        tunnel_url = Prompt.ask("  Domain", default="nio.shawnos.ai")
        console.print(f"\n  [dim]Make sure a DNS CNAME for {tunnel_url} points to your tunnel.[/dim]")
        console.print(f"  [dim]Run: cloudflared tunnel route dns {tunnel_name} {tunnel_url}[/dim]\n")
    else:
        tunnel_url = "quick"
        console.print("\n  [dim]Quick tunnel URL will be shown when you run nio start.[/dim]\n")

    write_access_config(mode="remote", tunnel_name=tunnel_name, tunnel_url=tunnel_url)
    console.print(f"  [green]Access mode: remote[/green]")
    if tunnel_url != "quick":
        console.print(f"  [green]Tunnel: {tunnel_name} -> https://{tunnel_url}[/green]\n")
    else:
        console.print(f"  [green]Tunnel: {tunnel_name} (quick mode)[/green]\n")


@app.command("platforms")
def setup_platforms():
    """Stage 3: Connect messaging platforms."""
    from nio.core.platform_probe import (
        PLATFORMS,
        check_whatsapp_bridge,
        configure_platform,
        probe_all,
    )

    console.print("\n[bold green]Step 3: Connect your agent to a platform[/bold green]\n")
    console.print("  Your agent can respond on Discord, Telegram, WhatsApp, Slack, or Signal.")
    console.print("  Skip this if you only use Claude Code.\n")

    probes = probe_all()

    # Show current status
    table = Table(show_header=True, border_style="dim")
    table.add_column("Platform", style="bold")
    table.add_column("Status")
    table.add_column("Token")

    for p in probes:
        status = "[green]configured[/green]" if p["configured"] else "[dim]not set[/dim]"
        token = p["token_preview"] or "[dim]--[/dim]"
        table.add_row(p["display"], status, token)

    console.print(table)
    console.print()

    for platform_key, info in PLATFORMS.items():
        probe = next(p for p in probes if p["platform"] == platform_key)
        if probe["configured"]:
            if not Confirm.ask(f"  [green]{info['display']}[/green] is connected. Update token?", default=False):
                continue
        elif not Confirm.ask(f"  Set up {info['display']}?", default=False):
            continue

        # Special handling for WhatsApp
        if platform_key == "whatsapp":
            bridge_path = check_whatsapp_bridge()
            if not bridge_path:
                console.print("  [yellow]WhatsApp bridge not found.[/yellow]")
                console.print("  Requires Node.js. The bridge lives at hermes-agent/scripts/whatsapp-bridge/")
                console.print("  Run: [green]hermes whatsapp[/green] for guided QR code setup.\n")
            else:
                console.print(f"  [green]Bridge found at: {bridge_path}[/green]")
                console.print("  Run: [green]hermes whatsapp[/green] to scan QR code.\n")
                configure_platform("whatsapp", "true")
                console.print("  [green]WhatsApp enabled.[/green]\n")
            continue

        # Special handling for Signal
        if platform_key == "signal":
            import shutil
            if not shutil.which("signal-cli"):
                console.print("  [yellow]signal-cli not found.[/yellow]")
                console.print("  Install: brew install signal-cli (macOS)")
                console.print("  Then: signal-cli link -n nio\n")
                continue
            phone = Prompt.ask("  Signal phone number (e.g. +1234567890)")
            configure_platform("signal", phone)
            console.print(f"  [green]Signal configured for {phone}[/green]\n")
            continue

        # Standard token-based platforms
        if info.get("setup_url"):
            console.print(f"  Get your token: [link={info['setup_url']}]{info['setup_url']}[/link]")
        console.print(f"  {info['help']}")
        console.print("  [dim](paste your token and press enter)[/dim]")
        token = Prompt.ask(f"  {info['display']} token")
        if token:
            configure_platform(platform_key, token)
            console.print(f"  [green]{info['display']} configured.[/green]\n")

    console.print()


@app.command("memory")
def setup_memory():
    """Stage 4: Import Hermes memories into NIO."""
    from pathlib import Path

    console.print("\n[bold green]Step 4: Import existing memory[/bold green]\n")
    console.print("  NIO can import context from your previous Hermes sessions and Claude Code handoffs.")
    console.print("  This gives your agent a head start on knowing your work.\n")

    hermes_mem = Path.home() / ".hermes" / "memories"
    memory_file = hermes_mem / "MEMORY.md"
    user_file = hermes_mem / "USER.md"

    found = []
    if memory_file.exists():
        content = memory_file.read_text().strip()
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        found.append(("MEMORY.md", len(paragraphs), content[:200]))

    if user_file.exists():
        content = user_file.read_text().strip()
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        found.append(("USER.md", len(paragraphs), content[:200]))

    # Check Claude Code handoffs
    handoffs_dir = Path.home() / ".claude" / "handoffs"
    handoff_count = 0
    if handoffs_dir.is_dir():
        handoff_files = [f for f in handoffs_dir.glob("*.md") if not f.name.endswith("_done.md")]
        handoff_count = len(handoff_files)
        if handoff_count:
            found.append(("Claude handoffs", handoff_count, f"{handoff_count} handoff files"))

    if not found:
        console.print("  [dim]No Hermes memories or Claude handoffs found.[/dim]")
        console.print("  Memory bridge will activate once you have session history.\n")
        return

    table = Table(show_header=True, border_style="dim")
    table.add_column("File")
    table.add_column("Paragraphs")
    table.add_column("Preview")

    for name, count, preview in found:
        table.add_row(name, str(count), preview[:80] + "...")

    console.print(table)
    console.print()

    if Confirm.ask("  Import these into NIO's eternal memory?", default=True):
        from nio.core.memory import import_claude_handoffs, import_hermes_memories
        total = 0
        count = import_hermes_memories()
        total += count
        if count:
            console.print(f"  [green]Imported {count} Hermes memory entries.[/green]")

        if handoff_count:
            hcount = import_claude_handoffs()
            total += hcount
            if hcount:
                console.print(f"  [green]Imported {hcount} Claude handoff sections.[/green]")

        console.print(f"  [green]Total: {total} entries imported.[/green]\n")
    else:
        console.print("  [dim]Skipped. Run `nio setup memory` later to import.[/dim]\n")


@app.command("verify")
def setup_verify():
    """Stage 5: Verify everything works."""
    from pathlib import Path

    from nio.core.db import check_db
    from nio.core.platform_probe import check_hermes_installed, probe_all

    console.print("\n[bold green]Step 5: Verify everything works[/bold green]\n")

    checks = []

    # Core checks
    nio_dir = Path.home() / ".nio"
    checks.append(("~/.nio/ directory", nio_dir.is_dir()))
    checks.append(("nio.db schema", check_db()))
    checks.append(("Hermes installed", check_hermes_installed()))

    hook = Path.home() / ".hermes" / "hooks" / "nio" / "HOOK.yaml"
    checks.append(("Hermes hook", hook.is_file()))

    active_soul = Path.home() / ".nio" / "active" / "soul.txt"
    checks.append(("Active soul set", active_soul.exists()))

    active_voice = Path.home() / ".nio" / "active" / "voice.txt"
    checks.append(("Active voice set", active_voice.exists()))

    # Dashboard
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:4242/health", timeout=2)
        checks.append(("Dashboard (:4242)", True))
    except Exception:
        checks.append(("Dashboard (:4242)", False))

    # Mode
    config_path = Path.home() / ".nio" / "config.yaml"
    if config_path.exists():
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        mode = config.get("mode", "global")
        checks.append((f"Mode: {mode}", True))
    else:
        checks.append(("Mode configured", False))

    # Access / tunnel
    access_cfg = config.get("access", {})
    if access_cfg.get("mode") == "remote":
        from nio.core.tunnel import is_tunnel_running
        tunnel_url = access_cfg.get("tunnel_url", "")
        tunnel_name = access_cfg.get("tunnel_name", "")
        label = f"Tunnel: {tunnel_name}" if tunnel_name else "Tunnel"
        if tunnel_url and tunnel_url != "quick":
            label += f" -> {tunnel_url}"
        checks.append((label, is_tunnel_running()))
    else:
        checks.append(("Access: local", True))

    # Platform status
    for probe in probe_all():
        checks.append((f"{probe['display']}", probe["configured"]))

    # Print results
    table = Table(show_header=True, border_style="dim")
    table.add_column("Check", style="bold")
    table.add_column("Status")

    for label, ok in checks:
        status = "[green]OK[/green]" if ok else "[dim]--[/dim]"
        table.add_row(label, status)

    console.print(table)

    ok_count = sum(1 for _, ok in checks if ok)
    total = len(checks)
    console.print(f"\n  [green]{ok_count}/{total} checks passed.[/green]")

    if ok_count == total:
        console.print("  [bold green]NIO is fully configured.[/bold green]\n")
    else:
        console.print("  Run [green]nio setup[/green] to configure missing components.\n")
