"""Team mode commands."""


import typer

app = typer.Typer(no_args_is_help=True)


@app.command("init")
def init_team(
    name: str = typer.Option(..., "--name", help="Team ID (kebab-case)"),
    soul: str = typer.Option("nio-core", help="Base soul to derive team soul from"),
    voice: str = typer.Option("shawn-builder", help="Voice profile for team soul"),
):
    """Initialize team mode in the current repo."""
    from nio.core.team import init_team as _init

    result = _init(name=name, base_soul=soul, voice=voice)
    typer.echo(f"Team initialized: {result['team_id']}")
    typer.echo(f"Config: {result['config_path']}")
    typer.echo(f"Soul: {result['soul_path']}")
    typer.echo("\nShare with collaborators:")
    typer.echo(f"  nio team join {result.get('origin', '<repo-url>')}")


@app.command("join")
def join_team(
    repo_url: str = typer.Argument(help="Git repo URL with .nio/team.toml"),
):
    """Join a team by pulling its config and verifying the soul signature."""
    from nio.core.team import join_team as _join

    result = _join(repo_url)
    typer.echo(f"Joined team: {result['team_id']}")
    typer.echo(f"Soul: {result['soul_id']}@{result['soul_version']}")


@app.command("sync")
def sync_team():
    """Pull latest team soul, voice, and memory from the repo."""
    from nio.core.team import sync_team as _sync

    result = _sync()
    typer.echo(f"Synced: {result['team_id']} (soul {result['soul_version']})")


@app.command("members")
def list_members():
    """Show team members and their soul versions."""
    from rich.console import Console
    from rich.table import Table

    from nio.core.team import get_members

    console = Console()
    members = get_members()

    table = Table(title="Team Members")
    table.add_column("Member", style="bold")
    table.add_column("Soul Version")
    table.add_column("Last Sync")
    for m in members:
        table.add_row(m["name"], m.get("soul_version", ""), m.get("last_sync", ""))
    console.print(table)


@app.command("release")
def release_team_soul(
    soul_id: str = typer.Argument(help="Team soul ID to release"),
    bump: str = typer.Option("patch", help="Version bump: patch, minor, major"),
    message: str = typer.Option(..., "--message", "-m", help="Release changelog entry"),
):
    """Release a new version of the team soul (owner-only)."""
    from nio.core.team import release_team_soul as _release

    new_version = _release(soul_id, bump=bump, message=message)
    typer.echo(f"Released team soul: {soul_id}@{new_version}")
