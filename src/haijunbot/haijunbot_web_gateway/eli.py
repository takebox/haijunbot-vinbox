# -*- coding: utf-8 -*-
"""Web Gateway ELI entry point."""

from typing import Optional

import typer
from rich import print as rprint

from haijunbot.haijunbot_utils.utils import init_env
from .app import run
from .node_config import build_node_runtime_config

app = typer.Typer(help="HaijunBot Web Gateway service")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Listen address"),
    port: int = typer.Option(8000, "--port", "-p", help="Listen port"),
    node_mode: str = typer.Option(
        "master", "--node-mode", help="Node mode: master or child"
    ),
    node_id: Optional[str] = typer.Option(
        None, "--node-id", help="Current node ID (required in child mode)"
    ),
    master_url: Optional[str] = typer.Option(
        None, "--master-url", help="Master node URL (required in child mode)"
    ),
    node_secret: Optional[str] = typer.Option(
        None, "--node-secret", help="Node shared secret (required in child mode)"
    ),
) -> None:
    """Start the Web Gateway service."""

    rprint("\n[bold cyan]🚀 Starting HaijunBot Web Gateway[/bold cyan]\n")
    rprint(f"  [dim]Address:[/dim] {host}")
    rprint(f"  [dim]Port:[/dim] {port}")

    node_config = build_node_runtime_config(
        node_mode=node_mode,
        node_id=node_id,
        master_url=master_url,
        node_secret=node_secret,
    )
    rprint(f"  [dim]Node mode:[/dim] {node_config.node_mode}")
    rprint(f"  [dim]Node ID:[/dim] {node_config.effective_node_id}")
    if node_config.node_secret:
        rprint("  [dim]Node secret:[/dim] [green]Set[/green]")
    else:
        rprint("  [dim]Node secret:[/dim] [yellow]Not set[/yellow]")
    rprint()
    run(host=host, port=port, node_config=node_config)


def main(argv: Optional[list[str]] = None) -> None:
    init_env("")
    app(standalone_mode=True)
