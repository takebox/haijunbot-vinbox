"""haijunbot_lsp - LSP client tools

This module provides command-line LSP (Language Server Protocol) client capabilities,
supporting communication with various language servers to obtain code analysis results.

Main features:
    - Configuration management: reads LSP server configuration from ~/.haijunbot/config.yaml
    - LSP client: implements basic LSP protocol communication
    - Symbol queries: list definitions, references, symbols, etc. in a file
    - CLI interface: provides the command-line tools haijunbot-lsp and hlsp

Usage example:
    >>> from haijunbot.haijunbot_lsp import LSPClient
    >>> client = LSPClient(command="python", args=["-m", "pylsp"])
    >>> symbols = await client.document_symbol("test.py")

Command line usage:
    $ haijunbot-lsp symbols test.py
    $ hlsp symbols test.py --json
"""

__version__ = "0.1.0"

from haijunbot.haijunbot_lsp.config import LSPConfigReader
from haijunbot.haijunbot_lsp.client import LSPClient, LocationInfo, SymbolInfo
from haijunbot.haijunbot_lsp.server_manager import LSPServerInstance, LSPServerManager

__all__ = [
    "LSPConfigReader",
    "LSPClient",
    "LocationInfo",
    "SymbolInfo",
    "LSPServerInstance",
    "LSPServerManager",
    "__version__",
]
