# -*- coding: utf-8 -*-
"""
HaijunBot configuration tool Execution Line Interface (ELI)

Provides friendly command-line interaction using typer
"""

import webbrowser
from pathlib import Path
from typing import Optional

import typer
import uvicorn
from rich import print as rprint

from .schema_parser import SchemaParser
from .web_app import create_app

# Get the haijunbot_data directory path
from importlib import resources
from haijunbot.haijunbot_utils.utils import init_env

app = typer.Typer(help="HaijunBot configuration tool - dynamically generates a configuration page based on JSON Schema")


@app.command()
def web(
    schema_file: Optional[Path] = typer.Option(
        None,
        "--schema",
        "-s",
        help="JSON Schema file path (default: haijunbot's config_schema.json)",
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output configuration file path (default: ~/.haijunbot/config.yaml)",
    ),
    port: int = typer.Option(
        8080,
        "--port",
        "-p",
        help="Web service port",
    ),
    open_browser: bool = typer.Option(
        True,
        "--no-browser",
        "/nb",
        help="Automatically open the browser after startup",
    ),
) -> None:
    """Start the Web configuration interface

    Generates a configuration page based on the specified JSON Schema file,
    and automatically saves to the specified output file after the user fills it in.

    Examples:
        haijunbot-config
        haijunbot-config --schema custom.json --output custom.yaml
        haijunbot-config --port 3000 --no-browser
        haijunbot-config -s schema.json -o output.yaml -p 8080
    """

    init_env("")

    # Set default values
    if schema_file is None:
        # Use haijunbot's default config_schema.json
        try:
            haijunbot_data_dir = resources.files("haijunbot.haijunbot_data")
            schema_file = Path(str(haijunbot_data_dir / "config_schema.json"))
        except Exception:
            # If not found, try a relative path
            schema_file = (
                Path(__file__).parent.parent / "haijunbot_data" / "config_schema.json"
            )

    if output_file is None:
        # Use the default ~/.haijunbot/config.yaml
        haijunbot_dir = Path.home() / ".haijunbot"
        output_file = haijunbot_dir / "config.yaml"

    try:
        # Show startup information
        rprint("\n[bold cyan]🚀 Starting HaijunBot configuration tool[/bold cyan]\n")
        rprint(f"  [dim]Schema file:[/dim] {schema_file}")
        rprint(f"  [dim]Output file:[/dim] {output_file}")
        rprint(f"  [dim]Service port:[/dim] {port}")
        rprint()

        # Validate the schema file
        try:
            parser = SchemaParser(schema_file)
            rprint(f"[green]✓[/green] Schema loaded successfully: {parser.get_title()}")
        except Exception as e:
            rprint(f"[red]✗[/red] Failed to load schema: {e}")
            raise typer.Exit(code=1)

        # Ensure the parent directory of output_file exists
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            rprint(f"[red]✗[/red] Failed to create output directory: {e}")
            raise typer.Exit(code=1)

        # Create the FastAPI application
        try:
            fastapi_app = create_app(schema_file, output_file)
        except Exception as e:
            rprint(f"[red]✗[/red] Failed to create application: {e}")
            raise typer.Exit(code=1)

        # Startup information
        url = f"http://localhost:{port}"
        rprint("\n[bold green]✓ Service started![/bold green]")
        rprint(f"  [dim]Access URL:[/dim] [link]{url}[/link]")
        rprint("  [dim]Press Ctrl+C to stop the service[/dim]\n")

        # Automatically open the browser
        if open_browser:
            try:
                webbrowser.open(url)
                rprint("[dim]Browser opened automatically...[/dim]\n")
            except Exception:
                rprint(f"[yellow]⚠[/yellow] Failed to open the browser automatically, please visit manually: {url}\n")

        # Start the uvicorn service
        uvicorn.run(
            fastapi_app,
            host="0.0.0.0",
            port=port,
            log_level="info",
            timeout_graceful_shutdown=30,  # Graceful shutdown: allow 30 seconds to handle existing requests
        )

    except KeyboardInterrupt:
        rprint("\n[yellow]\n⚠ Service stopped[/yellow]")
        raise typer.Exit(code=0)
    except typer.Exit:
        raise  # Re-raise typer.Exit
    except Exception as e:
        rprint(f"\n[red]✗ Error occurred: {e}[/red]")
        raise typer.Exit(code=1)
