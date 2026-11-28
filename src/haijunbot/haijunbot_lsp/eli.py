"""ELI interface module

This module provides the interface for the haijunbot-lsp and hlsp command line tools.
"""

import asyncio
import json
import os
from dataclasses import asdict
from typing import Optional

import typer

from haijunbot.haijunbot_lsp import __version__
from haijunbot.haijunbot_lsp.client import LocationInfo, SymbolInfo
from haijunbot.haijunbot_lsp.protocol import (
    CodeActionInfo,
    DiagnosticInfo,
    FoldingRangeInfo,
    HoverInfo,
)
from haijunbot.haijunbot_lsp.config import LSPConfigReader
from haijunbot.haijunbot_lsp.daemon_client import LSPDaemonClient
from haijunbot.haijunbot_utils.utils import init_env


app = typer.Typer(
    help="HaijunBot LSP client tool - command line interface for communicating with language servers",
    no_args_is_help=True,
)

init_env("")


def format_symbols_json(symbols: list[SymbolInfo], file_path: str) -> str:
    """Format the symbol list as JSON

    Args:
        symbols: The list of symbols
        file_path: The file path (only used as a default; the symbol's own file_path takes precedence)

    Returns:
        The JSON string
    """
    data = {
        "file": file_path,
        "symbols": [
            {
                "name": s.name,
                "kind": s.kind,
                "file": s.file_path or file_path,
                "line": s.line,
                "column": s.column,
                "description": s.description,
            }
            for s in symbols
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def format_folding_ranges_json(ranges: list[FoldingRangeInfo], file_path: str) -> str:
    """Format folding ranges as JSON

    Args:
        ranges: The list of folding ranges
        file_path: The file path

    Returns:
        The JSON string
    """
    data = {
        "file": file_path,
        "folding_ranges": [
            {
                "start_line": r.start_line,
                "start_character": r.start_character,
                "end_line": r.end_line,
                "end_character": r.end_character,
                "kind": r.kind,
                "collapsed_text": r.collapsed_text,
            }
            for r in ranges
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def format_hover_json(hover_info: HoverInfo, file_path: str) -> str:
    """Format hover info as JSON

    Args:
        hover_info: The hover info
        file_path: The file path

    Returns:
        The JSON string
    """
    data = {
        "file": file_path,
        "hover_info": {
            "contents": hover_info.contents,
            "range": hover_info.range,
            "line": hover_info.line,
            "character": hover_info.character,
        },
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def format_diagnostic_json(diagnostics: list[DiagnosticInfo], file_path: str) -> str:
    """Format diagnostic info as JSON

    Args:
        diagnostics: The list of diagnostic info
        file_path: The file path

    Returns:
        The JSON string
    """
    data = {
        "file": file_path,
        "diagnostics": [
            {
                "range": diag.range,
                "severity": diag.severity,
                "code": diag.code,
                "source": diag.source,
                "message": diag.message,
            }
            for diag in diagnostics
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def format_code_action_json(code_actions: list[CodeActionInfo]) -> str:
    """Format code actions as JSON

    Args:
        code_actions: The list of code actions

    Returns:
        The JSON string
    """
    data = {
        "code_actions": [
            {
                "title": action.title,
                "kind": action.kind,
                "is_preferred": action.is_preferred,
            }
            for action in code_actions
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


@app.command("document_symbols")
def document_symbols_command(
    file_path: str = typer.Argument(..., help="Target file path"),
    language: str = typer.Option(
        ...,
        "--language",
        "-l",
        help="Specify the language (e.g. python, rust, javascript)",
    ),
    kind: Optional[str] = typer.Option(
        None,
        "--kind",
        "-k",
        help="Filter symbol kinds (e.g. function, class, variable)",
    ),
) -> None:
    """List the document symbols in a file

    Lists the function, class, variable, and other symbol info in the specified file.

    Note: This feature depends on the LSP daemon and the LSP server's document/symbol feature.
    If the server does not support this feature or the response times out, the command will fail.
    """
    project_path = os.getcwd()
    client = LSPDaemonClient()

    async def run() -> list[SymbolInfo]:
        symbols = await client.document_symbol(language, project_path, file_path)
        return symbols

    try:
        symbols = asyncio.run(run())
    except RuntimeError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)

    # Filter symbol kinds
    if kind:
        symbols = [s for s in symbols if s.kind.lower() == kind.lower()]

    # Output JSON format by default (for LLM use)
    symbols_data = [
        {
            "name": s.name,
            "kind": s.kind,
            "file": s.file_path,
            "line": s.line,
            "column": s.column,
            "description": s.description,
        }
        for s in symbols
    ]
    result = {"file": file_path, "symbols": symbols_data}
    print(json.dumps(result, indent=2, ensure_ascii=False))


@app.command("folding_range")
def folding_range_command(
    file_path: str = typer.Argument(..., help="Target file path"),
    language: str = typer.Option(
        ...,
        "--language",
        "-l",
        help="Specify the language (e.g. python, rust, javascript)",
    ),
) -> None:
    """Return the code folding ranges

    Returns the collapsible code block ranges in the specified file to help identify code block boundaries.

    Note: This feature depends on the LSP daemon and the LSP server's textDocument/foldingRange feature.
    If the server does not support this feature or the response times out, the command will fail.
    """


@app.command("hover")
def hover_command(
    file_path: str = typer.Argument(..., help="Target file path"),
    line: int = typer.Argument(..., help="Line number (1-based)"),
    character: int = typer.Argument(..., help="Column number (1-based)"),
    language: str = typer.Option(
        ...,
        "--language",
        "-l",
        help="Specify the language (e.g. python, rust, javascript)",
    ),
) -> None:
    """Get the hover info for a symbol

    Gets the hover info for the symbol at the specified position, including comments, types, parameter descriptions, docstrings, etc.
    This feature supplies the LLM with semantic code information, avoiding the need to parse raw code.

    Note: This feature depends on the LSP daemon and the LSP server's textDocument/hover feature.
    If the server does not support this feature or the response times out, the command will fail.
    """
    # Read the configuration
    config_reader = LSPConfigReader()

    # Get the language configuration
    lang_config = config_reader.get_language_config(language)
    if lang_config is None:
        print(f"❌ Error: no configuration found for language '{language}'")
        print("Please add a configuration under the lsp.languages section of ~/.haijunbot/config.yaml")
        raise typer.Exit(code=1)

    # Convert to 0-based indexes
    line_0based = line - 1
    character_0based = character - 1

    project_path = os.getcwd()
    client = LSPDaemonClient()

    # Run the async task (using the daemon)
    async def run() -> Optional[HoverInfo]:
        # Get the hover info through the daemon
        hover_info = await client.hover(
            language, project_path, file_path, line_0based, character_0based
        )
        return hover_info

    try:
        hover_info = asyncio.run(run())
    except RuntimeError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)

    # Output the result (JSON format by default)
    if hover_info is None:
        print(f"ℹ️  No symbol found at line {line}, column {character}")
    else:
        print(format_hover_json(hover_info, file_path))


@app.command("symbol")
def symbol_command(
    query: str = typer.Argument(..., help="The search query string"),
    language: str = typer.Option(
        ...,
        "--language",
        "-l",
        help="Specify the language (e.g. python, rust, javascript)",
    ),
    kind: Optional[str] = typer.Option(
        None,
        "--kind",
        "-k",
        help="Filter symbol kinds (e.g. function, class, variable)",
    ),
) -> None:
    """Search for symbols in the workspace

    Searches for function, class, variable, and other symbol info matching the query string in the workspace.

    Note: This feature depends on the LSP daemon and the LSP server's workspace/symbol feature.
    If the server does not support this feature or the response times out, the command will fail.
    """

    project_path = os.getcwd()
    client = LSPDaemonClient()

    async def run() -> list[SymbolInfo]:
        # Get the symbols through the daemon
        symbols = await client.workspace_symbol(language, project_path, query)
        return symbols

    try:
        symbols = asyncio.run(run())
    except RuntimeError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)

    # Filter symbol kinds
    if kind:
        symbols = [s for s in symbols if s.kind.lower() == kind.lower()]

    # Output the result (use an empty string as the file path because symbols can come from multiple files; JSON format by default)
    print(format_symbols_json(symbols, ""))


def format_location_json(locations: list[LocationInfo]) -> str:
    """Format the location list as JSON

    Args:
        locations: The list of locations

    Returns:
        The JSON string
    """
    data = {
        "count": len(locations),
        "locations": [
            {
                "file_path": loc.file_path,
                "line": loc.line,
                "column": loc.column,
                "uri": loc.uri,
                "symbol_name": loc.symbol_name,
                "context": loc.context,
                "code_snippet": loc.code_snippet,
            }
            for loc in locations
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


@app.command("def-at")
def definition_at_line_command(
    file_path: str = typer.Argument(..., help="Target file path"),
    line: int = typer.Argument(..., help="Line number (1-based)"),
    symbol_name: str = typer.Argument(..., help="Symbol name (required, for exact matching)"),
    language: str = typer.Option(
        ...,
        "--language",
        "-l",
        help="Specify the language (e.g. python, rust, javascript)",
    ),
) -> None:
    """Find the definition by line number (automatically looks up the symbol column on that line)

    Finds the definition of a symbol on the specified line of the file; an exact column is not required.
    If there are multiple symbols on the line, pass the symbol name for an exact match.

    Note: This feature depends on the LSP daemon and the LSP server's document/symbol and textDocument/definition features.
    If the server does not support this feature or the response times out, the command will fail.
    """

    project_path = os.getcwd()
    client = LSPDaemonClient()

    async def run() -> LocationInfo | None:
        location = await client.definition_at_line(
            language, project_path, file_path, line, symbol_name
        )
        return location

    try:
        location = asyncio.run(run())
    except RuntimeError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)

    # Output the result (JSON format by default)
    if location is None:
        print("[]")
    else:
        print(format_location_json([location]))


@app.command("def-name")
def definition_by_name_command(
    file_path: str = typer.Argument(..., help="Target file path"),
    symbol_name: str = typer.Argument(..., help="The symbol name"),
    language: str = typer.Option(
        ...,
        "--language",
        "-l",
        help="Specify the language (e.g. python, rust, javascript)",
    ),
) -> None:
    """Find the definition by symbol name

    Finds the definition position of the specified symbol in the file.

    Note: This feature depends on the LSP daemon and the LSP server's document/symbol and textDocument/definition features.
    If the server does not support this feature or the response times out, the command will fail.
    """

    project_path = os.getcwd()
    client = LSPDaemonClient()

    async def run() -> LocationInfo | None:
        location = await client.definition_by_name(
            language, project_path, file_path, symbol_name
        )
        return location

    try:
        location = asyncio.run(run())
    except RuntimeError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)

    # Output JSON format by default (for LLM use)
    if location is None:
        print("[]")
    else:
        print(format_location_json([location]))


@app.command("ref-name")
def references_by_name_command(
    file_path: str = typer.Argument(..., help="Target file path"),
    symbol_name: str = typer.Argument(..., help="The symbol name"),
    language: str = typer.Option(
        ...,
        "--language",
        "-l",
        help="Specify the language (e.g. python, rust, javascript)",
    ),
) -> None:
    """Find references by symbol name

    Finds all reference positions of the specified symbol in the file.

    Note: This feature depends on the LSP daemon and the LSP server's document/symbol and textDocument/references features.
    If the server does not support this feature or the response times out, the command will fail.
    """

    project_path = os.getcwd()
    client = LSPDaemonClient()

    async def run() -> list[LocationInfo]:
        locations = await client.references_by_name(
            language, project_path, file_path, symbol_name
        )
        return locations

    try:
        locations = asyncio.run(run())
    except RuntimeError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)

    # Output the result (JSON format by default)
    print(format_location_json(locations))


@app.command("impl-name")
def implementation_by_name_command(
    file_path: str = typer.Argument(..., help="Target file path"),
    symbol_name: str = typer.Argument(..., help="The symbol name"),
    language: str = typer.Option(
        ...,
        "--language",
        "-l",
        help="Specify the language (e.g. python, rust, javascript)",
    ),
) -> None:
    """Find implementations by symbol name

    Finds all implementation positions of the specified interface or abstract method in the file.

    Note: This feature depends on the LSP daemon and the LSP server's document/symbol and textDocument/implementation features.
    If the server does not support this feature or the response times out, the command will fail.
    """

    project_path = os.getcwd()
    client = LSPDaemonClient()

    async def run() -> list[LocationInfo]:
        locations = await client.implementation_by_name(
            language, project_path, file_path, symbol_name
        )
        return locations

    try:
        locations = asyncio.run(run())
    except RuntimeError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)

    # Output the result (JSON format by default)
    print(format_location_json(locations))


@app.command("type-def-name")
def type_definition_by_name_command(
    file_path: str = typer.Argument(..., help="The file path"),
    symbol_name: str = typer.Argument(..., help="The symbol name"),
    language: str = typer.Option(
        ..., "--language", "-l", help="Specify the language (e.g. python, rust, javascript)"
    ),
) -> None:
    """Find the type definition by symbol name (type definition)

    Example:
    ```
    hlsp type-def-name src/main.py MyClass
    ```

    Note:
    - First use `hlsp symbols <file>` to view the symbol list in the file
    - symbol_name must be a symbol name that exists in the file
    - pylsp may not support type definition queries and will show a friendly error
    """

    project_path = os.getcwd()
    client = LSPDaemonClient()

    async def run() -> LocationInfo | None:
        location = await client.type_definition_by_name(
            language, project_path, file_path, symbol_name
        )
        return location

    try:
        location = asyncio.run(run())
    except RuntimeError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)

    # Output JSON format by default (for LLM use)
    if location is None:
        print("[]")
    else:
        print(format_location_json([location]))


@app.command("callers-name")
def callers_by_name_command(
    file_path: str = typer.Argument(..., help="The file path"),
    symbol_name: str = typer.Argument(..., help="The symbol name"),
    language: str = typer.Option(
        ..., "--language", "-l", help="Specify the language (e.g. python, rust, javascript)"
    ),
) -> None:
    """Find callees by symbol name (all symbols called inside the function)

    Example:
    ```
    hlsp callers-name src/main.py my_function
    ```

    Note:
    - First use `hlsp symbols <file>` to view the symbol list in the file
    - symbol_name must be a function symbol name that exists in the file
    - Returns the definition positions of all symbols called inside the function
    """

    project_path = os.getcwd()
    client = LSPDaemonClient()

    async def run() -> list[dict]:
        locations = await client.callers_by_name(
            language, project_path, file_path, symbol_name
        )
        return [asdict(loc) for loc in locations]

    try:
        locations = asyncio.run(run())
    except RuntimeError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)

    # Output JSON format by default (for LLM use)
    print(json.dumps(locations, indent=2, ensure_ascii=False))


@app.command("diagnostic")
def diagnostic_command(
    file_path: str = typer.Argument(..., help="Target file path"),
    language: str = typer.Option(
        ...,
        "--language",
        "-l",
        help="Specify the language (e.g. python, rust, javascript)",
    ),
) -> None:
    """Get code diagnostic information

    Checks for syntax errors, lint warnings, type errors, code style issues, etc. in the file.
    Returns all diagnostic info; the LLM can filter them itself using the severity field.

    Example:
    ```
    hlsp diagnostic src/main.py
    ```

    Note:
    - Returns all diagnostic info (ERROR, WARNING, INFO, HINT)
    - pylsp may not support diagnostics and will show a friendly error
    """

    project_path = os.getcwd()
    client = LSPDaemonClient()

    async def run() -> list[DiagnosticInfo]:
        diagnostics = await client.diagnostic(language, project_path, file_path)
        return diagnostics

    try:
        diagnostics = asyncio.run(run())
    except RuntimeError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)

    # Output JSON format by default (for LLM use)
    print(format_diagnostic_json(diagnostics, file_path))


@app.command("codeAction")
def code_action_command(
    file_path: str = typer.Argument(..., help="Target file path"),
    line: int = typer.Argument(..., help="Line number (0-based)"),
    language: str = typer.Option(
        ...,
        "--language",
        "-l",
        help="Specify the language (e.g. python, rust, javascript)",
    ),
) -> None:
    """Get code actions (fix suggestions)

    Gets the executable actions for the specified line, such as fixing errors, refactoring, optimizing, etc.
    The column defaults to 0, which is suitable for LLM use.

    Example:
    ```
    hlsp codeAction src/main.py 10
    hlsp codeAction src/main.py 10 --json
    ```

    Note:
    - Only the line number is needed; the column defaults to 0
    - line is a 0-based index
    - pylsp may not provide code actions and will return an empty list
    """

    project_path = os.getcwd()
    client = LSPDaemonClient()

    async def run() -> list[CodeActionInfo]:
        code_actions = await client.code_action(
            language, project_path, file_path, line, 0
        )
        return code_actions

    try:
        code_actions = asyncio.run(run())
    except RuntimeError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)

    # Output the result (JSON format by default)
    print(format_code_action_json(code_actions))


@app.command("codeAction-by-name")
def code_action_by_name_command(
    file_path: str = typer.Argument(..., help="The file path"),
    symbol_name: str = typer.Argument(..., help="Symbol name (function name, class name, etc.)"),
    language: str = typer.Option(
        ..., "--language", "-l", help="Specify the language (e.g. python, rust, javascript)"
    ),
) -> None:
    """Find code actions by symbol name (fix suggestions)

    Gets the executable actions for the specified symbol, such as fixing errors, refactoring, optimizing, etc.
    Only the symbol name is needed; no exact line/column is required, which is suitable for LLM use.

    Example:
    ```
    hlsp codeAction-by-name src/main.py MyClass
    ```

    Note:
    - First use `hlsp document_symbols <file>` to view the symbol list in the file
    - symbol_name must be a symbol name that exists in the file
    - pylsp may not provide code actions and will return an empty list
    """

    project_path = os.getcwd()
    client = LSPDaemonClient()

    async def run() -> list[CodeActionInfo]:
        code_actions = await client.code_action_by_name(
            language, project_path, file_path, symbol_name
        )
        return code_actions

    try:
        code_actions = asyncio.run(run())
    except RuntimeError as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)

    # Output JSON format by default (for LLM use)
    print(format_code_action_json(code_actions))


@app.command("version")
def version_command() -> None:
    """Display the version info"""
    print(f"haijunbot-lsp version {__version__}")


daemon_app = typer.Typer(help="Daemon management commands")

# Register the daemon sub-application with the main application
app.add_typer(daemon_app, name="daemon", help="Daemon management commands")


@daemon_app.command("stop")
def daemon_stop() -> None:
    """Stop the LSP daemon"""
    import socket

    from haijunbot.haijunbot_lsp.daemon_client import LSPDaemonClient

    client = LSPDaemonClient()

    try:
        # Send the shutdown request (Unix: AF_UNIX, Windows: TCP)
        if client._is_unix:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(client.addr)
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((client.addr[0], client.addr[1]))

        request = {"id": 1, "method": "shutdown", "params": {}}
        message_bytes = json.dumps(request).encode("utf-8")
        # Content-Length must be the UTF-8 byte count (not the character count)
        sock.sendall(
            f"Content-Length: {len(message_bytes)}\r\n\r\n".encode("utf-8")
            + message_bytes
        )
        sock.close()

        print("✅ LSP daemon stopped")
    except (FileNotFoundError, ConnectionRefusedError, OSError):
        print("⚠️  The daemon is not running")
    except Exception as e:
        print(f"❌ Error: {e}")
        raise typer.Exit(code=1)


@daemon_app.command("status")
def daemon_status() -> None:
    """View the LSP daemon status

    The daemon starts automatically the first time any LSP command is used.
    """
    import asyncio
    from haijunbot.haijunbot_lsp.daemon_client import LSPDaemonClient

    async def run() -> None:
        client = LSPDaemonClient()

        try:
            status = await client.status()

            print("📊 LSP daemon status:")
            print("\n   ✅ The daemon is running")
            addr_str = (
                client.socket_path
                if client._is_unix
                else f"{client.addr[0]}:{client.addr[1]}"
            )
            print(f"   Address: {addr_str}")

            # Remove the success field; keep only the server info
            servers = {k: v for k, v in status.items() if k != "success"}

            if not servers:
                print("\n   📌 No running LSP servers")
                return

            print("\n   📌 LSP server list:")
            for server_key, server_info in servers.items():
                print(
                    f"\n     • {server_key}"
                    f"\n       Process ID: {server_info['pid']}"
                    f"\n       Start time: {server_info['start_time']}"
                    f"\n       Alive: {'yes' if server_info['is_alive'] else 'no'}"
                )
        except (FileNotFoundError, ConnectionRefusedError, OSError):
            print("📊 LSP daemon status:")
            print("\n   ❌ The daemon is not running")
            addr_str = (
                client.socket_path
                if client._is_unix
                else f"{client.addr[0]}:{client.addr[1]}"
            )
            print(f"\n   Address: {addr_str}")
            print("\n   ℹ️  The daemon starts automatically when an LSP command is first used")
        except Exception as e:
            print(f"❌ Error: {e}")
            raise typer.Exit(code=1)

    asyncio.run(run())


def main() -> None:
    """Main entry function"""
    app()


def jlsp_main() -> None:
    """Entry function for the hlsp command"""
    app()


if __name__ == "__main__":
    main()
