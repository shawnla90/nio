"""Voice profile management commands."""

import typer
from typing import Optional

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_voices():
    """List all available voice profiles."""
    from nio.core.voice import list_voices as _list
    from rich.console import Console
    from rich.table import Table

    console = Console()
    voices = _list()
    if not voices:
        console.print("[dim]No voice profiles found.[/dim]")
        return

    table = Table(title="Voice Profiles")
    table.add_column("ID", style="bold")
    table.add_column("Version")
    table.add_column("Description")
    for v in voices:
        table.add_row(v["voice"], v["version"], v.get("description", ""))
    console.print(table)


@app.command("show")
def show_voice(voice_ref: str = typer.Argument(help="Voice ID, optionally @version")):
    """Show a voice profile's full content."""
    from nio.core.voice import load_voice
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console()
    voice = load_voice(voice_ref)
    if not voice:
        console.print(f"[red]Voice not found: {voice_ref}[/red]")
        raise typer.Exit(1)
    console.print(Markdown(voice["raw"]))


@app.command("apply")
def apply_voice(voice_id: str = typer.Argument(help="Voice ID to activate")):
    """Set a voice profile as active."""
    from nio.core.voice import set_active_voice

    set_active_voice(voice_id)
    typer.echo(f"Active voice: {voice_id}")


@app.command("diff")
def diff_voice(
    ref_a: str = typer.Argument(help="First voice@version"),
    ref_b: str = typer.Argument(help="Second voice@version"),
):
    """Show diff between two voice profile versions."""
    from nio.core.versioning import diff_voices

    diff_voices(ref_a, ref_b)


@app.command("release")
def release_voice(
    voice_id: str = typer.Argument(help="Voice ID to release"),
    bump: str = typer.Option("patch", help="Version bump: patch, minor, major"),
    message: str = typer.Option(..., "--message", "-m", help="Release changelog entry"),
):
    """Release a new version of a voice profile."""
    from nio.core.versioning import release_voice as _release

    new_version = _release(voice_id, bump=bump, message=message)
    typer.echo(f"Released {voice_id}@{new_version}")
