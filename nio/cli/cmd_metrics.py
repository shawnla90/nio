"""Metrics commands."""

from typing import Optional

import typer

app = typer.Typer(no_args_is_help=True)


@app.command("show")
def show_metrics(
    window: str = typer.Option("7d", help="Time window (e.g., 1d, 7d, 30d)"),
    soul: Optional[str] = typer.Option(None, help="Filter by soul ID"),
    task: Optional[str] = typer.Option(None, help="Filter by task type"),
):
    """Show performance metrics for recent sessions."""
    from rich.console import Console
    from rich.table import Table

    from nio.core.metrics import query_metrics

    console = Console()
    data = query_metrics(window=window, soul_id=soul, task_type=task)

    table = Table(title=f"Metrics ({window})")
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Sessions", str(data.get("session_count", 0)))
    table.add_row("Turns", str(data.get("turn_count", 0)))
    table.add_row("Slop avg", f"{data.get('slop_avg', 0):.1f}/100")
    table.add_row("Latency p50", f"{data.get('latency_p50', 0):.0f}ms")
    table.add_row("Latency p95", f"{data.get('latency_p95', 0):.0f}ms")
    table.add_row("User signal avg", f"{data.get('signal_avg', 0):+.2f}")
    console.print(table)


@app.command("export")
def export_metrics(
    format: str = typer.Option("json", help="Export format: json, csv"),
    window: str = typer.Option("30d", help="Time window"),
):
    """Export metrics data."""
    from nio.core.metrics import export_metrics as _export

    _export(format=format, window=window)


@app.command("team")
def team_metrics(
    team_id: str = typer.Argument(help="Team ID"),
    window: str = typer.Option("7d", help="Time window"),
):
    """Show team-wide performance metrics."""
    from rich.console import Console
    from rich.table import Table

    from nio.core.metrics import query_team_metrics

    console = Console()
    data = query_team_metrics(team_id=team_id, window=window)

    table = Table(title=f"Team: {team_id} ({window})")
    table.add_column("Member", style="bold")
    table.add_column("Sessions")
    table.add_column("Slop avg")
    table.add_column("Latency p50")
    table.add_column("Soul version")
    for member in data.get("members", []):
        table.add_row(
            member["name"],
            str(member.get("sessions", 0)),
            f"{member.get('slop_avg', 0):.1f}",
            f"{member.get('latency_p50', 0):.0f}ms",
            member.get("soul_version", ""),
        )
    console.print(table)
