"""LSP client module

This module provides core LSP client functionality, including asynchronous
communication with the LSP server, initialization, and symbol queries.
"""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Dict

from haijunbot.haijunbot_utils.config import read_text_file

from haijunbot.haijunbot_lsp.protocol import (
    CodeActionInfo,
    DiagnosticInfo,
    FoldingRangeInfo,
    HoverInfo,
    LSPMessageCodec,
    LSPNotification,
    LSPRequest,
    LSPResponse,
)


@dataclass
class LocationInfo:
    """Location info dataclass (LLM-friendly format)

    This dataclass provides location information that is friendlier to LLM/Agent,
    including not only line and column numbers but also code content and context.

    Attributes:
        file_path: File path (absolute path)
        line: Line number (0-based)
        column: Column number (0-based)
        uri: Original LSP URI
        code_snippet: Code snippet at the target location (a few lines of context)
        symbol_name: Symbol name (function name, class name, etc., if extractable)
        context: Complete context description
    """

    file_path: str
    line: int
    column: int
    uri: str
    code_snippet: Optional[str] = None
    symbol_name: Optional[str] = None
    context: Optional[str] = None


@dataclass
class SymbolInfo:
    """Symbol info dataclass

    Attributes:
        name: Symbol name
        kind: Symbol kind (function, class, variable, etc.)
        file_path: Path of the file containing the symbol
        line: Line number (1-based)
        column: Column number (1-based)
        description: Description text
    """

    name: str
    kind: str
    line: int
    column: int
    file_path: str = ""
    description: Optional[str] = None


class LSPClient:
    """LSP client class

    Communicates with the LSP server, providing initialization, document opening, symbol queries, and other features.

    Supports two modes:
    - short (short connection): starts a new process each time, closed after use
    - persistent: reuses the existing process and keeps it running
    """

    def __init__(self, command: str, args: List[str], mode: str = "short") -> None:
        """Initialize the LSP client

        Args:
            command: The LSP server executable command
            args: The list of startup arguments
            mode: The client mode, "short" (short connection) or "persistent"
        """
        if mode not in ("short", "persistent"):
            raise ValueError(f"Invalid mode: {mode}, must be 'short' or 'persistent'")

        self.command = command
        self.args = args
        self.mode = mode
        self.process: Optional[asyncio.subprocess.Process] = None
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.request_id: int = 0
        self.root_uri: Optional[str] = None
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the LSP server

        Starts the LSP server process and sends the initialize request.

        In persistent mode, if the process already exists, it is reused directly.

        Raises:
            RuntimeError: If the server fails to start or initialization fails
        """
        # In persistent mode, if the process already exists, reuse it directly
        if self.mode == "persistent" and self.process is not None:
            if not self.process.stdout or not self.process.stdin:
                raise RuntimeError(
                    "Persistent mode: process exists but has no stdout/stdin"
                )
            self.reader = self.process.stdout
            self.writer = self.process.stdin
        else:
            # Start the LSP server process (short connection mode, or the first start in persistent mode)
            # Redirect stderr to a PIPE to capture error messages
            self.process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            if (
                not self.process
                or not self.process.stdout
                or not self.process.stdin
                or not self.process.stderr
            ):
                raise RuntimeError("Failed to start LSP server process")

            # Type assertion: self.process was already checked to be non-None above
            assert self.process is not None
            assert self.process.stdout is not None
            assert self.process.stdin is not None
            assert self.process.stderr is not None

            # Wait a moment to make sure the process starts
            await asyncio.sleep(0.2)

            # Check whether the process exited immediately
            if self.process.returncode is not None:
                # The process has exited; read the stderr error message
                if self.process.stderr:
                    stderr_output = await self.process.stderr.read()
                    error_msg = stderr_output.decode("utf-8", errors="ignore")
                    raise RuntimeError(
                        f"LSP server '{' '.join([self.command] + self.args)}' failed to start\n"
                        f"Exit code: {self.process.returncode}\n"
                        f"Error: {error_msg}\n\n"
                        f"To install Python LSP server: pip install python-lsp-server\n"
                        f"To install Rust LSP server: rustup component add rust-analyzer\n"
                        f"To install Go LSP server: go install golang.org/x/tools/gopls@latest\n"
                        f"For other languages, see: https://microsoft.github.io/language-server-protocol/implementors/tools/"
                    )
                else:
                    raise RuntimeError(
                        f"LSP server '{self.command}' exited with code {self.process.returncode}"
                    )

            self.reader = self.process.stdout
            self.writer = self.process.stdin

        # Send the initialize request
        request = LSPRequest(
            jsonrpc="2.0",
            id=self._next_id(),
            method="initialize",
            params={
                "processId": self.process.pid if self.process.pid else None,
                "rootUri": self.root_uri,
                "capabilities": {
                    "textDocument": {
                        "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                        "definition": {
                            "dynamicRegistration": True,
                            "linkSupport": True,
                        },
                        "references": {"dynamicRegistration": True},
                        "implementation": {
                            "dynamicRegistration": True,
                            "linkSupport": True,
                        },
                        "typeDefinition": {
                            "dynamicRegistration": True,
                            "linkSupport": True,
                        },
                    }
                },
            },
        )

        await self._send_request(request)

        try:
            response = await self._read_response(timeout=30.0)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "LSP server initialization timed out after 30 seconds. "
                "The server may be unresponsive or slow to start."
            )

        if response.error:
            raise RuntimeError(f"LSP initialization failed: {response.error}")

        # Send the initialized notification
        notification = LSPNotification(
            jsonrpc="2.0",
            method="initialized",
            params={},
        )
        await self._send_notification(notification)

        self._initialized = True

    async def open_document(self, file_path: str) -> None:
        """Open a document

        Args:
            file_path: The file path

        Raises:
            RuntimeError: If the client is not initialized
        """
        if not self._initialized:
            raise RuntimeError("LSP client not initialized")

        path = Path(file_path).resolve()
        uri = f"file://{path}"

        content = read_text_file(str(path))

        # Detect languageId from the file extension
        ext = path.suffix.lower()
        language_map = {
            ".py": "python",
            ".pyi": "python",
            ".rs": "rust",
            ".go": "go",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".c": "c",
            ".cpp": "cpp",
            ".hpp": "cpp",
            ".h": "c",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".lua": "lua",
            ".sh": "shell",
            ".bash": "shell",
            ".zsh": "shell",
            ".rb": "ruby",
            ".php": "php",
            ".html": "html",
            ".htm": "html",
            ".css": "css",
            ".scss": "css",
            ".less": "css",
        }
        language_id = language_map.get(ext, "plaintext")

        notification = LSPNotification(
            jsonrpc="2.0",
            method="textDocument/didOpen",
            params={
                "textDocument": {
                    "uri": uri,
                    "languageId": language_id,
                    "version": 1,
                    "text": content,
                }
            },
        )

        await self._send_notification(notification)

    async def folding_range(self, file_path: str) -> List[FoldingRangeInfo]:
        """Get code folding ranges

        Args:
            file_path: The file path

        Returns:
            The list of folding range info

        Raises:
            RuntimeError: If the client is not initialized or the query fails
        """
        if not self._initialized:
            raise RuntimeError("LSP client not initialized")

        # Open the document first
        await self.open_document(file_path)

        # Type assertion: open_document ensures the process has been initialized
        if self.process is None:
            raise RuntimeError("LSP server process is not initialized")

        path = Path(file_path).resolve()
        uri = f"file://{path}"

        # Send the foldingRange request
        request = LSPRequest(
            jsonrpc="2.0",
            id=self._next_id(),
            method="textDocument/foldingRange",
            params={
                "textDocument": {
                    "uri": uri,
                }
            },
        )

        await self._send_request(request)

        # Check whether the process is still running
        await asyncio.sleep(0.5)
        if self.process.returncode is not None:
            # The process has exited; read the stderr error message
            if self.process.stderr:
                stderr_output = await self.process.stderr.read()
                error_msg = stderr_output.decode("utf-8", errors="ignore")
            else:
                error_msg = "No stderr output available"
            raise RuntimeError(
                f"LSP server '{' '.join([self.command] + self.args)}' crashed after sending initialize request\n"
                f"Exit code: {self.process.returncode}\n"
                f"Error: {error_msg}"
            )

        try:
            response = await self._read_response(timeout=30.0)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "LSP server initialization timed out after 30 seconds. "
                "The server may be unresponsive or slow to start."
            )

        if response.error:
            raise RuntimeError(f"Folding range request failed: {response.error}")

        # Parse the folding ranges
        folding_ranges = self._parse_folding_ranges(response.result)
        return folding_ranges

    async def hover(
        self, file_path: str, line: int, character: int
    ) -> Optional[HoverInfo]:
        """Get symbol hover information

        Args:
            file_path: The file path
            line: Line number (0-based)
            character: Column number (0-based)

        Returns:
            The hover info, or None if there is no symbol at the position

        Raises:
            RuntimeError: If the client is not initialized or the query fails
        """
        if not self._initialized:
            raise RuntimeError("LSP client not initialized")

        # Open the document first
        await self.open_document(file_path)

        # Type assertion: open_document ensures the process has been initialized
        if self.process is None:
            raise RuntimeError("LSP server process is not initialized")

        path = Path(file_path).resolve()
        uri = f"file://{path}"

        # Send the hover request
        request = LSPRequest(
            jsonrpc="2.0",
            id=self._next_id(),
            method="textDocument/hover",
            params={
                "textDocument": {
                    "uri": uri,
                },
                "position": {
                    "line": line,
                    "character": character,
                },
            },
        )

        await self._send_request(request)

        # Check whether the process is still running
        await asyncio.sleep(0.5)
        if self.process.returncode is not None:
            # The process has exited; read the stderr error message
            if self.process.stderr:
                stderr_output = await self.process.stderr.read()
                error_msg = stderr_output.decode("utf-8", errors="ignore")
            else:
                error_msg = "No stderr output available"
            raise RuntimeError(
                f"LSP server '{' '.join([self.command] + self.args)}' crashed after sending hover request\n"
                f"Exit code: {self.process.returncode}\n"
                f"Error: {error_msg}"
            )

        try:
            response = await self._read_response(timeout=30.0)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "LSP server hover request timed out after 30 seconds. "
                "The server may be unresponsive or slow to start."
            )

        if response.error:
            raise RuntimeError(f"Hover request failed: {response.error}")

        # Parse the hover info
        hover_info = self._parse_hover(response.result, file_path, line, character)
        return hover_info

    async def document_symbol(self, file_path: str) -> List[SymbolInfo]:
        """Get document symbols

        Args:
            file_path: The file path

        Returns:
            The list of symbol info

        Raises:
            RuntimeError: If the client is not initialized or the query fails
        """
        if not self._initialized:
            raise RuntimeError("LSP client not initialized")

        # Open the document first
        await self.open_document(file_path)

        # Type assertion: open_document ensures the process has been initialized
        if self.process is None:
            raise RuntimeError("LSP server process is not initialized")

        path = Path(file_path).resolve()
        uri = f"file://{path}"

        # Send the documentSymbol request
        request = LSPRequest(
            jsonrpc="2.0",
            id=self._next_id(),
            method="textDocument/documentSymbol",
            params={
                "textDocument": {
                    "uri": uri,
                }
            },
        )

        await self._send_request(request)

        # Check whether the process is still running
        await asyncio.sleep(0.5)
        if self.process.returncode is not None:
            # The process has exited; read the stderr error message
            if self.process.stderr:
                stderr_output = await self.process.stderr.read()
                error_msg = stderr_output.decode("utf-8", errors="ignore")
            else:
                error_msg = "No stderr output available"
            raise RuntimeError(
                f"LSP server '{' '.join([self.command] + self.args)}' crashed after sending initialize request\n"
                f"Exit code: {self.process.returncode}\n"
                f"Error: {error_msg}"
            )

        try:
            response = await self._read_response(timeout=30.0)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "LSP server initialization timed out after 30 seconds. "
                "The server may be unresponsive or slow to start."
            )

        if response.error:
            raise RuntimeError(f"Document symbol request failed: {response.error}")

        # Parse the symbols
        symbols = self._parse_symbols(response.result)
        return symbols

    async def workspace_symbol(self, query: str) -> List[SymbolInfo]:
        """Search for symbols in the workspace

        Args:
            query: The search query string

        Returns:
            The list of symbol info

        Raises:
            RuntimeError: If the client is not initialized or the query fails
        """
        if not self._initialized:
            raise RuntimeError("LSP client not initialized")

        # Type assertion: initialize ensures the process has been initialized
        if self.process is None:
            raise RuntimeError("LSP server process is not initialized")

        # Send the workspace/symbol request
        request = LSPRequest(
            jsonrpc="2.0",
            id=self._next_id(),
            method="workspace/symbol",
            params={
                "query": query,
            },
        )

        await self._send_request(request)

        try:
            response = await self._read_response(timeout=30.0)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "LSP server workspace/symbol request timed out after 30 seconds. "
                "The server may be unresponsive or slow."
            )

        # Check for errors
        if response.error:
            error = response.error
            error_msg = error.get("message", "Unknown error")
            error_code = error.get("code", "unknown")

            # If pylsp does not support workspace/symbol, provide a friendly hint
            if "workspace/symbol" in error_msg and "Not Found" in error_msg:
                raise RuntimeError(
                    f"The configured LSP server does not support workspace/symbol. "
                    f"pylsp does not implement this method. "
                    f"Please use a different LSP server that supports workspace/symbol, "
                    f"such as pyright (python-lsp-server) or ruff-lsp. "
                    f"Error: {error_msg} (code: {error_code})"
                )

            raise RuntimeError(
                f"workspace/symbol request failed: {error_msg} (code: {error_code})"
            )

        # Parse the symbol list
        return self._parse_symbols(response.result or [])

    async def definition(
        self, file_path: str, line: int, column: int
    ) -> List[LocationInfo]:
        """Jump to definition

        Args:
            file_path: The file path
            line: Line number (0-based)
            column: Column number (0-based)

        Returns:
            The list of definition locations

        Raises:
            RuntimeError: If the client is not initialized or the query fails
        """
        if not self._initialized:
            raise RuntimeError("LSP client not initialized")

        # Open the document first
        await self.open_document(file_path)

        # Type assertion: open_document ensures the process has been initialized
        if self.process is None:
            raise RuntimeError("LSP server process is not initialized")

        path = Path(file_path).resolve()
        uri = f"file://{path}"

        # Send the textDocument/definition request
        request = LSPRequest(
            jsonrpc="2.0",
            id=self._next_id(),
            method="textDocument/definition",
            params={
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": column},
            },
        )

        await self._send_request(request)

        try:
            response = await self._read_response(timeout=30.0)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "textDocument/definition request timed out after 30 seconds. "
                "The server may be unresponsive or slow."
            )

        # Check for errors
        if response.error:
            error = response.error
            raise RuntimeError(
                f"definition request failed: "
                f"{error.get('message', 'Unknown error')} (code: {error.get('code', 'unknown')})"
            )

        return self._parse_locations(response.result or [])

    async def callers_in_range(
        self, file_path: str, start_line: int, end_line: int, language: str
    ) -> List[Dict[str, Any]]:
        """Parse function calls within the specified line range

        Args:
            file_path: The file path
            start_line: The start line number (1-based)
            end_line: The end line number (1-based)
            language: The language (used to select the parser; currently only python is supported)

        Returns:
            The list of function calls; each call contains name, line, column info
        """
        callers = []

        try:
            # Read the file content (detect the encoding first)
            content = read_text_file(file_path)

            # Use AST to parse the function body
            import ast

            tree = ast.parse(content)

            # Find all function calls within the specified line range
            class CallVisitor(ast.NodeVisitor):
                def __init__(self, start_line, end_line):
                    self.start_line = start_line
                    self.end_line = end_line
                    self.calls = []

                def visit_Call(self, node):
                    # Check whether the call is within the specified line range
                    if self.start_line <= node.lineno <= self.end_line:
                        # Get the function name
                        if isinstance(node.func, ast.Name):
                            func_name = node.func.id
                        elif isinstance(node.func, ast.Attribute):
                            func_name = node.func.attr
                        else:
                            func_name = "<unknown>"

                        self.calls.append(
                            {
                                "name": func_name,
                                "line": node.lineno,  # 1-based
                                "column": node.col_offset,  # 0-based
                            }
                        )

                    # Continue traversing child nodes
                    self.generic_visit(node)

            visitor = CallVisitor(start_line, end_line)
            visitor.visit(tree)
            callers = visitor.calls

        except Exception as e:
            print(f"[ERROR] Failed to parse callers: {e}")

        return callers

    async def references(
        self, file_path: str, line: int, column: int
    ) -> List[LocationInfo]:
        """Find all references

        Args:
            file_path: The file path
            line: Line number (0-based)
            column: Column number (0-based)

        Returns:
            The list of reference locations

        Raises:
            RuntimeError: If the client is not initialized or the query fails
        """
        if not self._initialized:
            raise RuntimeError("LSP client not initialized")

        # Open the document first
        await self.open_document(file_path)

        # Type assertion: open_document ensures the process has been initialized
        if self.process is None:
            raise RuntimeError("LSP server process is not initialized")

        path = Path(file_path).resolve()
        uri = f"file://{path}"

        # Send the textDocument/references request
        request = LSPRequest(
            jsonrpc="2.0",
            id=self._next_id(),
            method="textDocument/references",
            params={
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": column},
                "context": {"includeDeclaration": True},
            },
        )

        await self._send_request(request)

        try:
            response = await self._read_response(timeout=30.0)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "textDocument/references request timed out after 30 seconds. "
                "The server may be unresponsive or slow."
            )

        # Check for errors
        if response.error:
            error = response.error
            raise RuntimeError(
                f"references request failed: "
                f"{error.get('message', 'Unknown error')} (code: {error.get('code', 'unknown')})"
            )

        return self._parse_locations(response.result or [])

    async def implementation(
        self, file_path: str, line: int, column: int
    ) -> List[LocationInfo]:
        """Find implementations

        Args:
            file_path: The file path
            line: Line number (0-based)
            column: Column number (0-based)

        Returns:
            The list of implementation locations

        Raises:
            RuntimeError: If the client is not initialized or the query fails
        """
        if not self._initialized:
            raise RuntimeError("LSP client not initialized")

        # Open the document first
        await self.open_document(file_path)

        # Type assertion: open_document ensures the process has been initialized
        if self.process is None:
            raise RuntimeError("LSP server process is not initialized")

        path = Path(file_path).resolve()
        uri = f"file://{path}"

        # Send the textDocument/implementation request
        request = LSPRequest(
            jsonrpc="2.0",
            id=self._next_id(),
            method="textDocument/implementation",
            params={
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": column},
            },
        )

        await self._send_request(request)

        try:
            response = await self._read_response(timeout=30.0)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "textDocument/implementation request timed out after 30 seconds. "
                "The server may be unresponsive or slow."
            )

        # Check for errors
        if response.error:
            error = response.error
            raise RuntimeError(
                f"implementation request failed: "
                f"{error.get('message', 'Unknown error')} (code: {error.get('code', 'unknown')})"
            )

        return self._parse_locations(response.result or [])

    async def type_definition(
        self, file_path: str, line: int, column: int
    ) -> List[LocationInfo]:
        """Find the type definition

        Args:
            file_path: The file path
            line: Line number (0-based)
            column: Column number (0-based)

        Returns:
            The list of type definition locations

        Raises:
            RuntimeError: If the client is not initialized or the query fails
        """
        if not self._initialized:
            raise RuntimeError("LSP client not initialized")

        # Open the document first
        await self.open_document(file_path)

        # Type assertion: open_document ensures the process has been initialized
        if self.process is None:
            raise RuntimeError("LSP server process is not initialized")

        path = Path(file_path).resolve()
        uri = f"file://{path}"

        # Send the textDocument/typeDefinition request
        request = LSPRequest(
            jsonrpc="2.0",
            id=self._next_id(),
            method="textDocument/typeDefinition",
            params={
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": column},
            },
        )

        await self._send_request(request)

        try:
            response = await self._read_response(timeout=30.0)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "textDocument/typeDefinition request timed out after 30 seconds. "
                "The server may be unresponsive or slow."
            )

        # Check for errors
        if response.error:
            error = response.error
            raise RuntimeError(
                f"typeDefinition request failed: "
                f"{error.get('message', 'Unknown error')} (code: {error.get('code', 'unknown')})"
            )

        return self._parse_locations(response.result or [])

    async def close_document(self, file_path: str) -> None:
        """Close a document

        Args:
            file_path: The file path

        Raises:
            RuntimeError: If the client is not initialized
        """
        if not self._initialized:
            raise RuntimeError("LSP client not initialized")

        path = Path(file_path).resolve()
        uri = f"file://{path}"

        notification = LSPNotification(
            jsonrpc="2.0",
            method="textDocument/didClose",
            params={
                "textDocument": {
                    "uri": uri,
                }
            },
        )

        await self._send_notification(notification)

    async def shutdown(self) -> None:
        """Close the LSP client

        Sends the shutdown and exit requests, and closes the process.

        In persistent mode, the process is not closed; only local resources are cleaned up.
        """
        if self._initialized:
            try:
                # Send the shutdown request
                request = LSPRequest(
                    jsonrpc="2.0",
                    id=self._next_id(),
                    method="shutdown",
                    params={},
                )
                await self._send_request(request)
                try:
                    await asyncio.wait_for(self._read_response(), timeout=5.0)
                except (asyncio.TimeoutError, Exception):
                    # Ignore shutdown response timeouts or errors and continue closing
                    pass

                # Send the exit notification (short connection mode only)
                if self.mode == "short":
                    notification = LSPNotification(
                        jsonrpc="2.0",
                        method="exit",
                        params={},
                    )
                    await self._send_notification(notification)
            except Exception:  # nosec: B110
                # Ignore errors when closing
                pass

        # Close the process (short connection mode only)
        if self.mode == "short":
            if self.process:
                try:
                    self.process.terminate()
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except Exception:
                    try:
                        self.process.kill()
                        await asyncio.wait_for(self.process.wait(), timeout=5.0)
                    except Exception:  # nosec: B110
                        pass

        # Clean up the reader/writer and state (short connection mode only)
        # Persistent mode must keep the connection; do not clean up the writer and reader
        if self.mode == "short":
            if self.writer:
                try:
                    self.writer.close()
                    await self.writer.wait_closed()
                except Exception:  # nosec: B110
                    pass

        self._initialized = False

    def _next_id(self) -> int:
        """Get the next request ID"""
        self.request_id += 1
        return self.request_id

    async def _send_request(self, request: LSPRequest) -> None:
        """Send a request

        Args:
            request: The LSP request object

        Raises:
            RuntimeError: If the write fails
        """
        if not self.writer:
            raise RuntimeError("Writer not initialized")

        data = LSPMessageCodec.encode_request(request)
        self.writer.write(data)
        await self.writer.drain()

    async def _send_notification(self, notification: LSPNotification) -> None:
        """Send a notification

        Args:
            notification: The LSP notification object

        Raises:
            RuntimeError: If the write fails
        """
        if not self.writer:
            raise RuntimeError("Writer not initialized")

        data = LSPMessageCodec.encode_notification(notification)
        self.writer.write(data)
        await self.writer.drain()

    async def _read_response(self, timeout: float = 30.0) -> LSPResponse:
        """Read a response

        Args:
            timeout: The timeout in seconds

        Returns:
            The LSP response object

        Raises:
            RuntimeError: If reading fails or times out
        """
        if not self.reader:
            raise RuntimeError("Reader not initialized")

        while True:
            # Read the Content-Length header
            header_line = await asyncio.wait_for(
                self.reader.readline(), timeout=timeout
            )
            if not header_line:
                raise RuntimeError("Failed to read response header")

            content_length = int(header_line.decode("utf-8").split(":", 1)[1].strip())

            # Skip the remaining header lines until a blank line (\r\n) is reached
            while True:
                line = await asyncio.wait_for(self.reader.readline(), timeout=timeout)
                if line == b"\r\n":  # A blank line marks the end of the headers
                    break

            # Read the JSON content
            content_bytes = await asyncio.wait_for(
                self.reader.readexactly(content_length), timeout=timeout
            )

            # Parse the JSON directly
            content_str = content_bytes.decode("utf-8")
            message_dict = json.loads(content_str)

            # Check whether it is a response (has an id) rather than a notification (has no id)
            if "id" in message_dict:
                response = LSPResponse(
                    jsonrpc=message_dict.get("jsonrpc", "2.0"),
                    id=message_dict.get("id"),
                    result=message_dict.get("result"),
                    error=message_dict.get("error"),
                )
                return response

    def _uri_to_path(self, uri: str) -> str:
        """Convert an LSP URI to a file path

        Args:
            uri: The LSP URI (e.g. file:///path/to/file)

        Returns:
            The absolute file path
        """
        if uri.startswith("file://"):
            return uri[7:]  # Remove the file:// prefix
        return uri

    def _parse_location(self, location: Any) -> LocationInfo:
        """Parse an LSP Location into an LLM-friendly LocationInfo

        Args:
            location: The LSP Location object

        Returns:
            A LocationInfo object (containing the code snippet and context)
        """
        # LSP Location format: {uri: str, range: {start: {line, character}, end: {line, character}}}
        uri = location.get("uri", "")
        range_info = location.get("range", {})
        start = range_info.get("start", {})

        file_path = self._uri_to_path(uri)
        line = start.get("line", 0)
        column = start.get("character", 0)

        # Read the code snippet (including a few lines of context around the target)
        code_snippet = self._extract_code_snippet(file_path, line)

        # Build the context description (does not try to extract the symbol name, following LSP principles)
        context = f"File: {file_path}, Line: {line + 1}, Column: {column}"
        symbol_name = None  # The LSP protocol layer should not assume the target language's syntax

        return LocationInfo(
            file_path=file_path,
            line=line,
            column=column,
            uri=uri,
            code_snippet=code_snippet,
            symbol_name=symbol_name,
            context=context,
        )

    def _extract_code_snippet(self, file_path: str, target_line: int) -> Optional[str]:
        """Extract the code snippet around the target line

        Args:
            file_path: The file path
            target_line: The target line number (0-based)

        Returns:
            The code snippet string (including a few surrounding lines)
        """
        try:
            content = read_text_file(file_path)
            lines = content.splitlines()

            # Extract 3 lines before and after (7 lines in total)
            start_line = max(0, target_line - 3)
            end_line = min(len(lines), target_line + 4)

            snippet_lines = lines[start_line:end_line]

            # Add line numbers
            snippet = ""
            for i, line_text in enumerate(snippet_lines, start=start_line):
                marker = " > " if i == target_line else "   "
                snippet += f"{marker}{i + 1:4d} | {line_text}\n"

            return snippet
        except Exception:
            return None

    def _parse_hover(
        self, result: Any, file_path: str, line: int, character: int
    ) -> Optional[HoverInfo]:
        """Parse an LSP hover response

        Args:
            result: The LSP response result
            file_path: The file path
            line: Line number (0-based)
            character: Column number (0-based)

        Returns:
            A HoverInfo object, or None if the result is empty
        """
        if result is None:
            return None

        # Extract the contents
        contents = result.get("contents")
        if contents is None:
            return None

        # Handle different formats of contents
        # The LSP spec allows contents to be one of the following formats:
        # 1. MarkedString: { language: str, value: str }
        # 2. An array of MarkedString: [{ language: str, value: str }]
        # 3. MarkupContent: { kind: 'markdown'|'plaintext', value: str }
        # 4. string
        if isinstance(contents, str):
            contents_str = contents
        elif isinstance(contents, dict):
            # MarkupContent or MarkedString
            value = contents.get("value")
            if value is None:
                return None
            contents_str = value
        elif isinstance(contents, list):
            # An array of MarkedString
            contents_list = []
            for item in contents:
                if isinstance(item, str):
                    contents_list.append(item)
                elif isinstance(item, dict):
                    value = item.get("value")
                    if value:
                        contents_list.append(value)
            if not contents_list:
                return None
            contents_str = "\n\n".join(contents_list)
        else:
            return None

        # Extract the range (optional)
        range_data = result.get("range")
        if range_data:
            start = range_data.get("start", {})
            end = range_data.get("end", {})
            range_info = (
                start.get("line", 0),
                start.get("character", 0),
                end.get("line", 0),
                end.get("character", 0),
            )
        else:
            range_info = None

        return HoverInfo(
            contents=contents_str,
            range=range_info,
            file_path=file_path,
            line=line,
            character=character,
        )

    def _find_symbol_in_line(
        self, file_path: str, line: int, symbol_name: str
    ) -> Optional[int]:
        """Find the position of the symbol name on the given line (fallback mechanism)

        Note: This is an imperfect fallback mechanism that only does simple string matching.
        It does not assume the syntax of any language, so it may be inaccurate.
        The correct approach is to rely on the selectionRange returned by the LSP server.

        Args:
            file_path: The file path
            line: Line number (0-based)
            symbol_name: The symbol name

        Returns:
            The column of the symbol name (0-based), or None if not found
        """
        try:
            content = read_text_file(file_path)
            lines = content.splitlines()

            if line < 0 or line >= len(lines):
                return None

            line_text = lines[line]

            # Only do simple string matching; do not assume the syntax of any language
            # Use word boundaries to ensure an exact match
            import re

            match = re.search(rf"\b{re.escape(symbol_name)}\b", line_text)
            if match:
                return match.start()

            return None
        except Exception:
            return None

    def _parse_locations(self, result: Any) -> List[LocationInfo]:
        """Parse a list of LSP Locations

        Args:
            result: A list of LSP Locations or a single Location

        Returns:
            The list of LocationInfo
        """
        locations: List[LocationInfo] = []

        if result is None:
            return locations

        # If it is a single Location, convert it to a list
        if not isinstance(result, list):
            result = [result]

        for loc in result:
            if loc and isinstance(loc, dict):
                locations.append(self._parse_location(loc))

        return locations

    def _parse_folding_ranges(self, result: Any) -> List[FoldingRangeInfo]:
        """Parse folding ranges

        Args:
            result: The foldingRange response result

        Returns:
            The list of folding range info
        """
        folding_ranges: List[FoldingRangeInfo] = []

        if not isinstance(result, list):
            return folding_ranges

        for item in result:
            if not isinstance(item, dict):
                continue

            # LSP FoldingRange format:
            # {
            #   "startLine": int,
            #   "startCharacter": int (optional),
            #   "endLine": int,
            #   "endCharacter": int (optional),
            #   "kind": string (optional),
            #   "collapsedText": string (optional)
            # }
            start_line = item.get("startLine", 0)
            start_character = item.get("startCharacter", 0)
            end_line_raw = item.get("endLine")
            end_line = end_line_raw if end_line_raw is not None else start_line
            end_character = item.get("endCharacter", 0)
            kind = item.get("kind")
            collapsed_text = item.get("collapsedText")

            folding_ranges.append(
                FoldingRangeInfo(
                    start_line=start_line,
                    start_character=start_character,
                    end_line=end_line,
                    end_character=end_character,
                    kind=kind,
                    collapsed_text=collapsed_text,
                )
            )

        return folding_ranges

    def _parse_symbols(self, result: Any) -> List[SymbolInfo]:
        """Parse symbols

        Args:
            result: The documentSymbol response result

        Returns:
            The list of symbol info
        """
        symbols: List[SymbolInfo] = []

        if not isinstance(result, list):
            return symbols

        def _parse_symbol_item(item: Any) -> Optional[SymbolInfo]:
            if not isinstance(item, dict):
                return None

            name = item.get("name")
            kind = item.get("kind")

            # The location info may be in location.range or directly in range
            # Prefer selectionRange (the symbol name's range); fall back to range if missing
            location = item.get("location", {})
            if "range" in location:
                range_info = location["range"]
            else:
                range_info = item.get("range", {})

            # LSP DocumentSymbol has a selectionRange field that describes the symbol name's range
            # It is more precise than range (range may cover the whole definition; selectionRange covers just the name)
            selection_range = item.get("selectionRange")
            if selection_range:
                # Use selectionRange to get the precise position of the symbol name
                start = selection_range.get("start", {})
            else:
                # If there is no selectionRange, fall back to range
                start = range_info.get("start", {})

            line = start.get("line", 0)
            column = start.get("character", 0)

            # Extract the file path
            uri = location.get("uri", "")
            file_path = self._uri_to_path(uri) if uri else ""

            # If the column is 0, try to find the symbol name on the target line
            # pylsp may not return selectionRange, so the column is always 0
            if column == 0 and name:
                # Try to get the file path from range
                uri = location.get("uri", "")
                if uri:
                    file_path = self._uri_to_path(uri)
                    # Read the target line and look up the symbol name
                    found_column = self._find_symbol_in_line(file_path, line, name)
                    if found_column is not None:
                        column = found_column

            # LSP SymbolKind mapping
            kind_map: dict[int, str] = {
                1: "file",
                2: "module",
                3: "namespace",
                4: "package",
                5: "class",
                6: "method",
                7: "property",
                8: "field",
                9: "constructor",
                10: "enum",
                11: "interface",
                12: "function",
                13: "variable",
                14: "constant",
                15: "string",
                16: "number",
                17: "boolean",
                18: "array",
                19: "object",
                20: "key",
                21: "null",
                22: "enumMember",
                23: "struct",
                24: "event",
                25: "operator",
                26: "typeParameter",
            }

            if isinstance(kind, int):
                kind_name = kind_map.get(kind, "unknown")
            else:
                kind_name = "unknown"

            return SymbolInfo(
                name=name or "",
                kind=kind_name,
                file_path=file_path,
                line=line + 1,  # Convert to 1-based
                column=column + 1,  # Convert to 1-based
                description=item.get("detail"),
            )

        for item in result:
            symbol = _parse_symbol_item(item)
            if symbol:
                symbols.append(symbol)

            # Recursively process child symbols
            children = item.get("children") if isinstance(item, dict) else None
            if isinstance(children, list):
                for child in children:
                    child_symbol = _parse_symbol_item(child)
                    if child_symbol:
                        symbols.append(child_symbol)

        return symbols

    async def diagnostic(
        self, file_path: str, severity_filter: Optional[int] = None
    ) -> List[DiagnosticInfo]:
        """Get code diagnostic information

                Args:
                    file_path: The file path
                    severity_filter: Severity filter (1=Error, 2=Warning, 3=Info, 4=Hint),
                          None means no filtering, returning all diagnostics

                Returns:
                    The list of diagnostic info

                Raises:
                    RuntimeError: If the client is not initialized or the query fails
                """
        if not self._initialized:
            raise RuntimeError("LSP client not initialized")

        # Open the document first
        await self.open_document(file_path)

        # Type assertion: open_document ensures the process has been initialized
        if self.process is None:
            raise RuntimeError("LSP server process is not initialized")

        path = Path(file_path).resolve()
        uri = f"file://{path}"

        # Send the diagnostic request
        request = LSPRequest(
            jsonrpc="2.0",
            id=self._next_id(),
            method="textDocument/diagnostic",
            params={
                "textDocument": {
                    "uri": uri,
                },
            },
        )

        await self._send_request(request)

        # Check whether the process is still running
        await asyncio.sleep(0.5)
        if self.process.returncode is not None:
            # The process has exited; read the stderr error message
            if self.process.stderr:
                stderr_output = await self.process.stderr.read()
                error_msg = stderr_output.decode("utf-8", errors="ignore")
            else:
                error_msg = "No stderr output available"
            raise RuntimeError(
                f"LSP server '{' '.join([self.command] + self.args)}' crashed after sending diagnostic request\n"
                f"Exit code: {self.process.returncode}\n"
                f"Error: {error_msg}"
            )

        try:
            response = await self._read_response(timeout=30.0)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "LSP server diagnostic request timed out after 30 seconds. "
                "The server may be unresponsive or slow to start."
            )

        if response.error:
            raise RuntimeError(f"Diagnostic request failed: {response.error}")

        # Parse the diagnostic info
        diagnostics = self._parse_diagnostic(response.result, severity_filter)
        return diagnostics

    async def code_action(
        self, file_path: str, line: int, character: int
    ) -> List[CodeActionInfo]:
        """Get code action information

        Args:
            file_path: The file path
            line: Line number (0-based)
            character: Column number (0-based)

        Returns:
            The list of code actions

        Raises:
            RuntimeError: If the client is not initialized or the query fails
        """
        if not self._initialized:
            raise RuntimeError("LSP client not initialized")

        # Open the document first
        await self.open_document(file_path)

        # Type assertion: open_document ensures the process has been initialized
        if self.process is None:
            raise RuntimeError("LSP server process is not initialized")

        path = Path(file_path).resolve()
        uri = f"file://{path}"

        # Send the codeAction request
        request = LSPRequest(
            jsonrpc="2.0",
            id=self._next_id(),
            method="textDocument/codeAction",
            params={
                "textDocument": {
                    "uri": uri,
                },
                "range": {
                    "start": {
                        "line": line,
                        "character": character,
                    },
                    "end": {
                        "line": line,
                        "character": character,
                    },
                },
                "context": {
                    "diagnostics": [],
                },
            },
        )

        await self._send_request(request)

        # Check whether the process is still running
        await asyncio.sleep(0.5)
        if self.process.returncode is not None:
            # The process has exited; read the stderr error message
            if self.process.stderr:
                stderr_output = await self.process.stderr.read()
                error_msg = stderr_output.decode("utf-8", errors="ignore")
            else:
                error_msg = "No stderr output available"
            raise RuntimeError(
                f"LSP server '{' '.join([self.command] + self.args)}' crashed after sending codeAction request\n"
                f"Exit code: {self.process.returncode}\n"
                f"Error: {error_msg}"
            )

        try:
            response = await self._read_response(timeout=30.0)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "LSP server codeAction request timed out after 30 seconds. "
                "The server may be unresponsive or slow to start."
            )

        if response.error:
            raise RuntimeError(f"CodeAction request failed: {response.error}")

        # Parse the code action info
        code_actions = self._parse_code_action(response.result)
        return code_actions

    async def code_action_by_name(
        self, file_path: str, symbol_name: str
    ) -> List[CodeActionInfo]:
        """Get code action information by symbol name

        Args:
            file_path: The file path
            symbol_name: The symbol name (function name, class name, etc.)

        Returns:
            The list of code actions

        Raises:
            RuntimeError: If the client is not initialized or the query fails
        """
        if not self._initialized:
            raise RuntimeError("LSP client not initialized")

        # Open the document first
        await self.open_document(file_path)

        # Get the document symbols
        symbols = await self.document_symbol(file_path)

        # Find the matching symbol
        for symbol in symbols:
            if symbol.name == symbol_name:
                # Symbol found; get the code actions at its position
                return await self.code_action(file_path, symbol.line, 0)

        # Symbol not found; return an empty list
        return []

    def _parse_diagnostic(
        self, result: Any, severity_filter: Optional[int] = None
    ) -> List[DiagnosticInfo]:
        """Parse diagnostic info

        Args:
            result: The LSP response result
            severity_filter: The severity filter

        Returns:
            The list of diagnostic info
        """
        diagnostics: List[DiagnosticInfo] = []

        # Handle pylsp's response format
        # pylsp may return a dictionary containing a diagnostics list
        if isinstance(result, dict):
            diagnostics_list = result.get("diagnostics", [])
        elif isinstance(result, list):
            diagnostics_list = result
        else:
            return diagnostics

        for item in diagnostics_list:
            if not isinstance(item, dict):
                continue

            # Parse the range
            range_info = item.get("range", {})
            start = range_info.get("start", {})
            end = range_info.get("end", {})
            start_line = start.get("line", 0)
            start_char = start.get("character", 0)
            end_line = end.get("line", 0)
            end_char = end.get("character", 0)

            # Parse the severity
            severity = item.get("severity", 1)  # Defaults to Error

            # Apply the severity filter
            if severity_filter is not None and severity != severity_filter:
                continue

            diagnostic = DiagnosticInfo(
                range=(start_line, start_char, end_line, end_char),
                severity=severity,
                code=item.get("code"),
                source=item.get("source", "unknown"),
                message=item.get("message", ""),
            )
            diagnostics.append(diagnostic)

        return diagnostics

    def _parse_code_action(self, result: Any) -> List[CodeActionInfo]:
        """Parse code action info

        Args:
            result: The LSP response result

        Returns:
            The list of code actions
        """
        code_actions: List[CodeActionInfo] = []

        # Handle pylsp's response format
        if isinstance(result, list):
            code_actions_list = result
        elif isinstance(result, dict):
            code_actions_list = result.get("result", [])
        else:
            return code_actions

        for item in code_actions_list:
            if not isinstance(item, dict):
                continue

            code_action = CodeActionInfo(
                title=item.get("title", ""),
                kind=item.get("kind", ""),
                is_preferred=item.get("isPreferred", False),
            )
            code_actions.append(code_action)

        return code_actions

    # ==================== Call Hierarchy API ====================

    async def prepare_call_hierarchy(
        self, file_path: str, line: int, column: int
    ) -> List[dict]:
        """Prepare the call hierarchy

        Args:
            file_path: The file path
            line: Line number (0-based)
            column: Column number (0-based)

        Returns:
            The list of CallHierarchyItem, each containing:
            - uri: The file URI
            - range: The symbol range
            - selectionRange: The symbol name range
            - name: The symbol name
            - kind: The symbol kind
            - detail: The detailed info

        Raises:
            RuntimeError: If the client is not initialized or the query fails
        """
        if not self._initialized:
            raise RuntimeError("LSP client not initialized")

        await self.open_document(file_path)

        if self.process is None:
            raise RuntimeError("LSP server process is not initialized")

        path = Path(file_path).resolve()
        uri = f"file://{path}"

        request = LSPRequest(
            jsonrpc="2.0",
            id=self._next_id(),
            method="textDocument/prepareCallHierarchy",
            params={
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": column},
            },
        )

        await self._send_request(request)

        try:
            response = await self._read_response(timeout=30.0)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "textDocument/prepareCallHierarchy request timed out after 30 seconds."
            )

        if response.error:
            raise RuntimeError(f"prepareCallHierarchy request failed: {response.error}")

        result = response.result
        if not result:
            return []

        return result if isinstance(result, list) else [result]

    async def call_hierarchy_incoming_calls(self, item: dict) -> List[dict]:
        """Query the call hierarchy - who calls this symbol (incoming calls / callers)

        Args:
            item: A CallHierarchyItem obtained from prepare_call_hierarchy

        Returns:
            The list of CallHierarchyIncomingCall, each containing:
            - from: The caller's CallHierarchyItem
            - fromRanges: The list of call location ranges

        Raises:
            RuntimeError: If the client is not initialized or the query fails
        """
        if not self._initialized:
            raise RuntimeError("LSP client not initialized")

        request = LSPRequest(
            jsonrpc="2.0",
            id=self._next_id(),
            method="callHierarchy/incomingCalls",
            params={"item": item},
        )

        await self._send_request(request)

        try:
            response = await self._read_response(timeout=30.0)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "callHierarchy/incomingCalls request timed out after 30 seconds."
            )

        if response.error:
            raise RuntimeError(
                f"callHierarchy/incomingCalls request failed: {response.error}"
            )

        return response.result or []

    async def call_hierarchy_outgoing_calls(self, item: dict) -> List[dict]:
        """Query the call hierarchy - which symbols this symbol calls (outgoing calls / callees)

        Args:
            item: A CallHierarchyItem obtained from prepare_call_hierarchy

        Returns:
            The list of CallHierarchyOutgoingCall, each containing:
            - to: The callee's CallHierarchyItem
            - fromRanges: The list of call location ranges

        Raises:
            RuntimeError: If the client is not initialized or the query fails
        """
        if not self._initialized:
            raise RuntimeError("LSP client not initialized")

        request = LSPRequest(
            jsonrpc="2.0",
            id=self._next_id(),
            method="callHierarchy/outgoingCalls",
            params={"item": item},
        )

        await self._send_request(request)

        try:
            response = await self._read_response(timeout=30.0)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "callHierarchy/outgoingCalls request timed out after 30 seconds."
            )

        if response.error:
            raise RuntimeError(
                f"callHierarchy/outgoingCalls request failed: {response.error}"
            )

        return response.result or []

    # ==================== Symbol name convenience methods ====================

    async def _find_symbol_position(
        self, file_path: str, symbol_name: str
    ) -> Optional[tuple]:
        """Find the position of a symbol in a file

        Args:
            file_path: The file path
            symbol_name: The symbol name

        Returns:
            A (line, column) tuple, or None if not found
        """
        symbols = await self.document_symbol(file_path)
        for sym in symbols:
            if sym.name == symbol_name:
                return (sym.line, sym.column)
        return None

    async def incoming_calls_by_name(
        self, file_path: str, symbol_name: str
    ) -> List[LocationInfo]:
        """Query who calls this symbol by symbol name (incoming calls / callers)

        Args:
            file_path: The file path
            symbol_name: The symbol name

        Returns:
            The list of caller locations

        Raises:
            RuntimeError: If the client is not initialized or the query fails
        """
        position = await self._find_symbol_position(file_path, symbol_name)
        if position is None:
            return []

        line, column = position
        items = await self.prepare_call_hierarchy(file_path, line, column)
        if not items:
            return []

        locations: List[LocationInfo] = []
        for item in items:
            calls = await self.call_hierarchy_incoming_calls(item)
            for call in calls:
                from_item = call.get("from", {})
                uri = from_item.get("uri", "")
                if uri.startswith("file://"):
                    caller_path = uri[7:]
                else:
                    caller_path = uri

                range_info = from_item.get("range", {})
                start = range_info.get("start", {})
                caller_line = start.get("line", 0)
                caller_col = start.get("character", 0)

                # Get the code snippet
                snippet = await self._get_code_snippet(caller_path, caller_line)

                locations.append(
                    LocationInfo(
                        file_path=caller_path,
                        line=caller_line,
                        column=caller_col,
                        uri=uri,
                        code_snippet=snippet,
                        symbol_name=from_item.get("name"),
                    )
                )

        return locations

    async def outgoing_calls_by_name(
        self, file_path: str, symbol_name: str
    ) -> List[LocationInfo]:
        """Query which symbols this symbol calls by symbol name (outgoing calls / callees)

        Args:
            file_path: The file path
            symbol_name: The symbol name

        Returns:
            The list of callee locations

        Raises:
            RuntimeError: If the client is not initialized or the query fails
        """
        position = await self._find_symbol_position(file_path, symbol_name)
        if position is None:
            return []

        line, column = position
        items = await self.prepare_call_hierarchy(file_path, line, column)
        if not items:
            return []

        locations: List[LocationInfo] = []
        for item in items:
            calls = await self.call_hierarchy_outgoing_calls(item)
            for call in calls:
                to_item = call.get("to", {})
                uri = to_item.get("uri", "")
                if uri.startswith("file://"):
                    callee_path = uri[7:]
                else:
                    callee_path = uri

                range_info = to_item.get("range", {})
                start = range_info.get("start", {})
                callee_line = start.get("line", 0)
                callee_col = start.get("character", 0)

                # Get the code snippet
                snippet = await self._get_code_snippet(callee_path, callee_line)

                locations.append(
                    LocationInfo(
                        file_path=callee_path,
                        line=callee_line,
                        column=callee_col,
                        uri=uri,
                        code_snippet=snippet,
                        symbol_name=to_item.get("name"),
                    )
                )

        return locations

    async def _get_code_snippet(
        self, file_path: str, line: int, context_lines: int = 3
    ) -> Optional[str]:
        """Get the code snippet around the specified position

        Args:
            file_path: The file path
            line: Line number (0-based)
            context_lines: The number of context lines

        Returns:
            The code snippet string
        """
        try:
            content = await asyncio.to_thread(Path(file_path).read_text)
            lines = content.splitlines()
            start = max(0, line - context_lines)
            end = min(len(lines), line + context_lines + 1)
            return "\n".join(lines[start:end])
        except Exception:
            return None

    # Backward-compatible old interface name
    async def callers_by_name(
        self, file_path: str, symbol_name: str
    ) -> List[LocationInfo]:
        """Query which symbols this symbol calls by symbol name (alias for outgoing calls)

        This is an alias for outgoing_calls_by_name, kept for backward compatibility.

        Args:
            file_path: The file path
            symbol_name: The symbol name

        Returns:
            The list of callee locations
        """
        return await self.outgoing_calls_by_name(file_path, symbol_name)

    async def __aenter__(self) -> "LSPClient":
        """Async context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit"""
        await self.shutdown()
