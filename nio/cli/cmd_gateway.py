"""NIO Gateway CLI: run the lightweight message loop."""

import typer

app = typer.Typer(invoke_without_command=True)


@app.callback()
def gateway_default(ctx: typer.Context):
    """NIO Gateway: WhatsApp/Discord via local models."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(gateway_start)


@app.command("start")
def gateway_start(
    model: str = typer.Option("gemma2", "--model", "-m", help="Ollama model name"),
    ollama_host: str = typer.Option("http://localhost:11434", "--ollama-host", help="Ollama API host"),
    bridge_url: str = typer.Option("http://localhost:3000", "--bridge", "-b", help="WhatsApp bridge URL"),
):
    """Start the NIO gateway (polls WhatsApp bridge, responds via Ollama)."""
    from nio.gateway.run import start
    start(model=model, ollama_host=ollama_host, bridge_url=bridge_url)


@app.command("status")
def gateway_status(
    ollama_host: str = typer.Option("http://localhost:11434", "--ollama-host"),
    bridge_url: str = typer.Option("http://localhost:3000", "--bridge"),
):
    """Check if Ollama and WhatsApp bridge are reachable."""
    from rich.console import Console

    from nio.gateway.ollama import check_health, list_models
    from nio.gateway.whatsapp import check_bridge

    console = Console()

    ollama_ok = check_health(ollama_host)
    bridge_ok = check_bridge(bridge_url)
    models = list_models(ollama_host) if ollama_ok else []

    console.print(f"  Ollama: {'[green]running[/green]' if ollama_ok else '[red]not reachable[/red]'} ({ollama_host})")
    if models:
        console.print(f"  Models: {', '.join(models)}")
    console.print(f"  Bridge: {'[green]running[/green]' if bridge_ok else '[dim]not reachable[/dim]'} ({bridge_url})")
