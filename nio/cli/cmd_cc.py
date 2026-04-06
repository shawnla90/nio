"""NIO Claude Code CLI subcommand."""

import typer
from rich.console import Console

app = typer.Typer(invoke_without_command=True)
console = Console()


@app.callback()
def cc_callback(ctx: typer.Context):
    """Claude Code session management."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(cc_status)


@app.command("start")
def cc_start():
    """Start a new Claude Code session."""
    from nio.claude_code.session_bridge import start_cc_session

    session_id = start_cc_session()
    console.print(f"[green]Session started:[/green] {session_id}")


@app.command("turn")
def cc_turn(
    session: str = typer.Option("", "--session", "-s", help="Session ID (default: latest)"),
    user: str = typer.Option("", "--user", "-u", help="User message summary"),
    agent: str = typer.Option("", "--agent", "-a", help="Agent message summary"),
):
    """Record a turn in the active Claude Code session."""
    from nio.claude_code.session_bridge import get_cc_status, record_cc_turn

    if not session:
        status = get_cc_status()
        if not status.get("active"):
            console.print("[red]No active session.[/red] Run: nio cc start")
            raise typer.Exit(1)
        session = status["session_id"]

    result = record_cc_turn(session, user_msg=user, agent_msg=agent)
    score = result["slop_score"]
    color = "green" if score >= 92 else "yellow" if score >= 80 else "red"
    console.print(f"Turn {result['turn_index']}: slop [{color}]{score:.0f}/100[/{color}]")

    if result["violations"]:
        for v in result["violations"][:3]:
            console.print(f"  [{v['tier']}] {v['id']}: {v['description']}")


@app.command("end")
def cc_end(
    session: str = typer.Option("", "--session", "-s", help="Session ID (default: latest)"),
):
    """End the active Claude Code session."""
    from nio.claude_code.session_bridge import end_cc_session, get_cc_status

    if not session:
        status = get_cc_status()
        if not status.get("active"):
            console.print("[yellow]No active session to end.[/yellow]")
            raise typer.Exit(0)
        session = status["session_id"]

    result = end_cc_session(session)
    console.print("[green]Session ended.[/green]")
    console.print(f"  Task: {result['task_type']}")
    console.print(f"  Turns: {result['turn_count']}")
    if result["slop_avg"] is not None:
        console.print(f"  Slop avg: {result['slop_avg']}/100")


@app.command("status")
def cc_status():
    """Show current Claude Code session status."""
    from nio.claude_code.session_bridge import get_cc_status

    status = get_cc_status()
    if not status.get("session_id"):
        console.print("[dim]No Claude Code sessions found.[/dim]")
        console.print("Run: nio cc start")
        return

    state = "[green]active[/green]" if status["active"] else "[dim]ended[/dim]"
    console.print(f"Session: {state}")
    console.print(f"  ID: {status['session_id'][:8]}...")
    console.print(f"  Soul: {status.get('soul_id', 'none')}")
    console.print(f"  Turns: {status['turn_count']}")
    if status["slop_avg"] is not None:
        console.print(f"  Slop avg: {status['slop_avg']}/100")


@app.command("context")
def cc_context():
    """Show full NIO context for current session."""
    from nio.claude_code.session_bridge import get_cc_context

    ctx = get_cc_context()
    console.print(f"Mode: {ctx['mode']}")
    console.print(f"Soul: {ctx['soul']}")
    console.print(f"Voice: {ctx['voice']}")
    console.print(f"Sessions: {ctx['session_count']} | Turns: {ctx['turn_count']}")
    if ctx["last_session"]:
        console.print(f"\nLast session: {ctx['last_session']}")
    if ctx["memory_facts"]:
        console.print(f"\nMemory facts ({len(ctx['memory_facts'])}):")
        for fact in ctx["memory_facts"][:5]:
            console.print(f"  {fact[:80]}...")
