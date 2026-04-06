"""Anti-slop registry commands."""

import typer
from pathlib import Path

app = typer.Typer(no_args_is_help=True)


@app.command("check")
def check_file(
    file_path: Path = typer.Argument(help="File to scan for slop patterns"),
):
    """Scan a file and print an anti-slop report."""
    from nio.core.antislop import detect, score
    from rich.console import Console

    console = Console()
    text = file_path.read_text()
    detections = detect(text)
    s = score(text)

    console.print(f"\n[bold]Slop score: {s:.1f}/100[/bold]\n")
    if not detections:
        console.print("[green]Clean. No violations detected.[/green]")
        return

    for d in detections:
        console.print(
            f"  [{d['tier']}] [bold]{d['id']}[/bold]: {d['description']}"
        )
        for match in d.get("matches", [])[:3]:
            console.print(f"    [dim]{match}[/dim]")
    console.print()


@app.command("score")
def score_text(
    text: str = typer.Argument(help="Text to score"),
):
    """Score a text string (0-100, higher = cleaner)."""
    from nio.core.antislop import score

    s = score(text)
    typer.echo(f"{s:.1f}/100")


@app.command("sync")
def sync_registry():
    """Regenerate Python + TypeScript validators from the anti-slop registry."""
    from nio.codegen.render_python import render as render_py
    from nio.codegen.render_typescript import render as render_ts
    from nio.codegen.render_markdown import render as render_md

    py_path = render_py()
    ts_path = render_ts()
    md_path = render_md()
    typer.echo(f"Python:     {py_path}")
    typer.echo(f"TypeScript: {ts_path}")
    typer.echo(f"Markdown:   {md_path}")


@app.command("list")
def list_rules():
    """Show all rules in the anti-slop registry."""
    from nio.core.antislop import load_registry
    from rich.console import Console
    from rich.table import Table

    console = Console()
    registry = load_registry()
    table = Table(title="Anti-Slop Registry")
    table.add_column("ID", style="bold")
    table.add_column("Tier")
    table.add_column("Action")
    table.add_column("Description")
    for rule in registry.get("rules", []):
        table.add_row(rule["id"], rule["tier"], rule["action"], rule["description"])
    console.print(table)


@app.command("install-ts")
def install_typescript(
    target: Path = typer.Option(..., "--target", help="Target .ts file path"),
):
    """Generate and install the TypeScript anti-slop validator to a target path."""
    from nio.codegen.render_typescript import render

    path = render(target_path=target)
    typer.echo(f"Installed: {path}")
