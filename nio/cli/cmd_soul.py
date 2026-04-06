"""Soul management commands."""

from typing import Optional

import typer

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_souls():
    """List all available souls in the registry."""
    from rich.console import Console
    from rich.table import Table

    from nio.core.soul import list_souls as _list

    console = Console()
    souls = _list()
    if not souls:
        console.print("[dim]No souls found. Run nio install to seed the registry.[/dim]")
        return

    table = Table(title="Souls")
    table.add_column("ID", style="bold")
    table.add_column("Version")
    table.add_column("Voice")
    table.add_column("Description")
    for s in souls:
        table.add_row(s["soul"], s["version"], s.get("voice", ""), s.get("description", ""))
    console.print(table)


@app.command("show")
def show_soul(soul_ref: str = typer.Argument(help="Soul ID, optionally @version")):
    """Show a soul's full content and metadata."""
    from rich.console import Console
    from rich.markdown import Markdown

    from nio.core.soul import load_soul

    console = Console()
    soul = load_soul(soul_ref)
    if not soul:
        console.print(f"[red]Soul not found: {soul_ref}[/red]")
        raise typer.Exit(1)
    console.print(Markdown(soul["raw"]))


@app.command("apply")
def apply_soul(soul_id: str = typer.Argument(help="Soul ID to activate")):
    """Set a soul as the active soul for all sessions."""
    from nio.core.soul import set_active_soul

    set_active_soul(soul_id)
    typer.echo(f"Active soul: {soul_id}")


@app.command("active")
def active_soul():
    """Show the currently active soul and version."""
    from nio.core.soul import get_active_soul

    soul = get_active_soul()
    typer.echo(soul or "No active soul. Run: nio soul apply <id>")


@app.command("create")
def create_soul(
    soul_id: str = typer.Argument(help="New soul ID (kebab-case)"),
    from_soul: Optional[str] = typer.Option(None, "--from", help="Derive from existing soul"),
    voice: str = typer.Option("shawn-builder", help="Voice profile to bind"),
):
    """Create a new soul, optionally derived from an existing one."""
    from nio.core.soul import create_soul as _create

    path = _create(soul_id, from_soul=from_soul, voice=voice)
    typer.echo(f"Created: {path}")
    typer.echo(f"Edit with: nio soul edit {soul_id}")


@app.command("edit")
def edit_soul(soul_id: str = typer.Argument(help="Soul ID to edit")):
    """Open a soul in $EDITOR."""
    import os

    from nio.core.soul import get_soul_path

    path = get_soul_path(soul_id)
    if not path or not path.exists():
        typer.echo(f"Soul not found: {soul_id}")
        raise typer.Exit(1)
    editor = os.environ.get("EDITOR", "vim")
    os.execvp(editor, [editor, str(path)])


@app.command("release")
def release_soul(
    soul_id: str = typer.Argument(help="Soul ID to release"),
    bump: str = typer.Option("patch", help="Version bump: patch, minor, major"),
    message: str = typer.Option(..., "--message", "-m", help="Release changelog entry"),
):
    """Release a new version of a soul (bumps semver, snapshots to DB, commits to git)."""
    from nio.core.versioning import release_soul as _release

    new_version = _release(soul_id, bump=bump, message=message)
    typer.echo(f"Released {soul_id}@{new_version}")


@app.command("diff")
def diff_soul(
    ref_a: str = typer.Argument(help="First soul@version"),
    ref_b: str = typer.Argument(help="Second soul@version"),
):
    """Show diff between two soul versions with metric deltas."""
    from nio.core.versioning import diff_souls

    diff_souls(ref_a, ref_b)


@app.command("checkout")
def checkout_soul(
    soul_ref: str = typer.Argument(help="Soul ID@version to restore"),
):
    """Restore a previous soul version as the current file."""
    from nio.core.versioning import checkout_soul as _checkout

    _checkout(soul_ref)
    typer.echo(f"Checked out: {soul_ref}")
