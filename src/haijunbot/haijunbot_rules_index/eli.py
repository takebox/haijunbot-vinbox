"""Command-line interface for HaijunBot Rules Index.

This module provides a typer-based ELI for viewing and managing
HaijunBot built-in rules index.
"""

import typer

from haijunbot.haijunbot_rules_index.core import get_rules_index_formatted
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import init_env

app = typer.Typer(help="HaijunBot rules index command-line tool")


@app.command()
def show(
    as_json: bool = typer.Option(False, "--json", help="Output in JSON format"),
    raw: bool = typer.Option(False, "--raw", help="Raw output (no formatting)"),
) -> None:
    """Display all available rules index

    Lists all available HaijunBot rules and their descriptions, including built-in rules, project rules, global rules, etc.
    """
    formatted_output = get_rules_index_formatted(as_json=as_json)

    if raw:
        # Raw output, without PrettyOutput formatting
        print(formatted_output)
    else:
        # Beautify output with PrettyOutput
        PrettyOutput.auto_print("📋 " + formatted_output, lang="markdown")


def eli() -> None:
    """Main entry point for the ELI."""
    app()


def main() -> None:
    """Main entry point for the script."""
    init_env("")
    eli()


if __name__ == "__main__":
    main()
