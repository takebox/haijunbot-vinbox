"""LSP daemon module

This module provides an independent background daemon that manages the lifecycle of all LSP servers.
Unix: IPC via Unix domain socket; Windows: IPC via TCP 127.0.0.1.
"""

import asyncio
import json
import os
import signal
import sys
from pathlib import Path
from typing import Any, Dict, Union

from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_lsp.config import LSPConfigReader
from haijunbot.haijunbot_lsp.server_manager import LSPServerInstance

_IS_WINDOWS = sys.platform == "win32"
LSP_DAEMON_TCP_PORT = 39282  # Windows uses a TCP port (to avoid conflicting with the browser's 39281)
LSP_DAEMON_PORT_FILE = "lsp_daemon.port"


def _get_lsp_daemon_addr() -> Union[str, tuple]:
    """Get the LSP daemon address: a socket path on Unix, (host, port) on Windows."""
    if _IS_WINDOWS:
        port_file = Path(get_data_dir()) / LSP_DAEMON_PORT_FILE
        if port_file.exists():
            try:
                port = int(port_file.read_text(encoding="utf-8").strip())
                return ("127.0.0.1", port)
            except (ValueError, OSError):
                pass
        return ("127.0.0.1", LSP_DAEMON_TCP_PORT)
    return str(Path(get_data_dir()) / "lsp_daemon.sock")


class LSPDaemon:
    """LSP daemon

    Manages all LSP server instances.
    Unix: Unix domain socket; Windows: TCP 127.0.0.1.
    """

    def __init__(self, addr: Union[str, tuple]):
        self.addr = addr
        self._is_unix = isinstance(addr, str)
        self.servers: Dict[str, LSPServerInstance] = {}
        self.config_reader = LSPConfigReader()
        self.server: asyncio.Server | None = None
        self._server_task: asyncio.Task[None] | None = None
        self.running = False

    async def start(self) -> None:
        """Start the daemon"""
        self.running = True

        if self._is_unix:
            socket_path = self.addr
            assert isinstance(socket_path, str), (
                f"Expected str for Unix socket path, got {type(socket_path)}"
            )
            if os.path.exists(socket_path):
                try:
                    os.unlink(socket_path)
                except OSError:
                    pass
            self.server = await asyncio.start_unix_server(
                self.handle_client,
                path=socket_path,
            )
            print(f"LSP daemon started, socket: {socket_path}")
        else:
            assert isinstance(self.addr, tuple), (
                f"Expected tuple for Windows address, got {type(self.addr)}"
            )
            host, port = self.addr
            port_file = Path(get_data_dir()) / LSP_DAEMON_PORT_FILE
            for try_port in range(port, port + 10):
                try:
                    self.server = await asyncio.start_server(
                        self.handle_client,
                        host=host,
                        port=try_port,
                    )
                    port_file.parent.mkdir(parents=True, exist_ok=True)
                    port_file.write_text(str(try_port), encoding="utf-8")
                    print(f"LSP daemon started, TCP: {host}:{try_port}")
                    break
                except OSError as e:
                    if "address already in use" in str(e).lower() or getattr(
                        e, "errno", 0
                    ) in (98, 10048):
                        continue
                    raise

        # Start the serving task
        assert self.server is not None, "Server should be initialized"
        self._server_task = asyncio.create_task(self.server.serve_forever())

        # Graceful exit (register signals on Unix; Windows has limited signal support, so skip)
        if not _IS_WINDOWS:
            try:
                loop = asyncio.get_running_loop()
                for sig in (signal.SIGTERM, signal.SIGINT):
                    loop.add_signal_handler(
                        sig, lambda: asyncio.create_task(self.stop())
                    )
            except NotImplementedError:
                pass

    async def _delayed_stop(self) -> None:
        """Stop the daemon with a delay"""
        # Wait a moment to make sure the client receives the response
        await asyncio.sleep(0.1)
        await self.stop()

    async def stop(self) -> None:
        """Stop the daemon"""
        if not self.running:
            return

        self.running = False

        # Stop all LSP servers
        for server in list(self.servers.values()):
            await server.shutdown()
        self.servers.clear()

        # Cancel the serving task
        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass

        # Close the socket
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Delete the socket file (Unix only)
        if self._is_unix and isinstance(self.addr, str):
            socket_path = self.addr
            if os.path.exists(socket_path):
                try:
                    os.unlink(socket_path)
                except OSError:
                    pass
        elif not self._is_unix:
            port_file = Path(get_data_dir()) / LSP_DAEMON_PORT_FILE
            if port_file.exists():
                try:
                    port_file.unlink()
                except OSError:
                    pass

        print("LSP daemon stopped")

        # Exit the process
        sys.exit(0)

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a client connection

        The client (daemon_client) uses the "one request per connection" semantics: each request opens a new connection,
        reads the response, and closes it immediately. Therefore after handling a single request, this returns, avoiding the server
        continuing to readline/write on the closed connection which would trigger Connection reset by peer.
        """
        try:
            if self.running:
                # Read the request
                line = await reader.readline()
                if not line:
                    return

                try:
                    # Parse the Content-Length header
                    header = line.decode().strip()
                    if header.startswith("Content-Length:"):
                        content_length = int(header.split(":")[1].strip())
                    else:
                        content_length = int(header)

                    # Read the blank line
                    await reader.readline()

                    # Read the content
                    content = await reader.readexactly(content_length)
                    request = json.loads(content.decode())

                    # Handle the request
                    response = await self.handle_request(request)

                    # Send the response
                    response_json = json.dumps(response, ensure_ascii=False)
                    response_bytes = response_json.encode()
                    # Content-Length must be the UTF-8 byte count (not the character count), otherwise responses containing non-ASCII characters get truncated
                    response_data = (
                        f"Content-Length: {len(response_bytes)}\r\n\r\n".encode()
                        + response_bytes
                    )
                    writer.write(response_data)
                    await writer.drain()

                except Exception as e:
                    # Send the error response
                    error_response = {
                        "success": False,
                        "error": str(e),
                    }
                    error_json = json.dumps(error_response, ensure_ascii=False)
                    error_bytes = error_json.encode()
                    error_data = (
                        f"Content-Length: {len(error_bytes)}\r\n\r\n".encode()
                        + error_bytes
                    )
                    writer.write(error_data)
                    await writer.drain()

        except Exception as e:
            save_exception(e, module="haijunbot_lsp.daemon", function="__init__")
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a request"""
        method = request.get("method")
        params = request.get("params", {})

        if method == "start_server":
            return await self.start_server(params)
        elif method == "stop_server":
            return await self.stop_server(params)
        elif method == "workspace_symbol":
            return await self.workspace_symbol(params)
        elif method == "document_symbol":
            return await self.document_symbol(params)
        elif method == "folding_range":
            return await self.folding_range(params)
        elif method == "hover":
            return await self.hover(params)
        elif method == "diagnostic":
            return await self.diagnostic(params)
        elif method == "code_action":
            return await self.code_action(params)
        elif method == "code_action_by_name":
            return await self.code_action_by_name(params)
        elif method == "definition":
            return await self.definition(params)
        elif method == "references":
            return await self.references(params)
        elif method == "implementation":
            return await self.implementation(params)
        elif method == "type_definition":
            return await self.type_definition(params)
        elif method == "definition_at_line":
            return await self.definition_at_line(params)
        elif method == "definition_by_name":
            return await self.definition_by_name(params)
        elif method == "references_by_name":
            return await self.references_by_name(params)
        elif method == "implementation_by_name":
            return await self.implementation_by_name(params)
        elif method == "type_definition_by_name":
            return await self.type_definition_by_name(params)
        elif method == "callers_by_name":
            return await self.callers_by_name(params)
        elif method == "incoming_calls_by_name":
            return await self.incoming_calls_by_name(params)
        elif method == "outgoing_calls_by_name":
            return await self.outgoing_calls_by_name(params)
        elif method == "status":
            return await self.status(params)
        elif method == "shutdown":
            # Stop the daemon with a delay; return the response first
            asyncio.create_task(self._delayed_stop())
            return {"success": True}
        else:
            return {
                "success": False,
                "error": f"Unknown method: {method}",
            }

    async def get_or_create_server(
        self, language: str, project_path: str
    ) -> LSPServerInstance:
        """Get or create an LSP server instance"""
        key = f"{language}:{project_path}"

        if key not in self.servers:
            server = LSPServerInstance(
                language=language,
                project_path=project_path,
            )
            await server.start(self.config_reader)
            self.servers[key] = server

        return self.servers[key]

    async def start_server(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Start the LSP server"""
        language = params.get("language")
        project_path = params.get("project_path")

        if not language or not project_path:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path",
            }

        server = await self.get_or_create_server(language, project_path)

        return {
            "success": True,
            "pid": server.process.pid if server.process else None,
        }

    async def stop_server(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Stop the LSP server"""
        language = params.get("language")
        project_path = params.get("project_path")

        if not language or not project_path:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path",
            }

        key = f"{language}:{project_path}"

        if key in self.servers:
            server = self.servers[key]
            await server.shutdown()
            del self.servers[key]

        return {"success": True}

    async def workspace_symbol(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search for symbols in the workspace"""
        language = params.get("language")
        project_path = params.get("project_path")
        query = params.get("query")

        if not language or not project_path or not query:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path, query",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        symbols = await server.client.workspace_symbol(query)

        return {
            "success": True,
            "symbols": [
                {
                    "name": s.name,
                    "kind": s.kind,
                    "line": s.line,
                    "column": s.column,
                    "description": s.description,
                }
                for s in symbols
            ],
        }

    async def document_symbol(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List the document symbols in a file"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")

        if not language or not project_path or not file_path:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path, file_path",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        symbols = await server.client.document_symbol(file_path)

        return {
            "success": True,
            "symbols": [
                {
                    "name": s.name,
                    "kind": s.kind,
                    "file_path": s.file_path or file_path,
                    "line": s.line,
                    "column": s.column,
                    "description": s.description,
                }
                for s in symbols
            ],
        }

    async def folding_range(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get the code folding ranges"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")

        if not language or not project_path or not file_path:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path, file_path",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        folding_ranges = await server.client.folding_range(file_path)

        return {
            "success": True,
            "folding_ranges": [
                {
                    "start_line": fr.start_line,
                    "start_character": fr.start_character,
                    "end_line": fr.end_line,
                    "end_character": fr.end_character,
                    "kind": fr.kind,
                    "collapsed_text": fr.collapsed_text,
                }
                for fr in folding_ranges
            ],
        }

    async def hover(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get symbol hover information"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        line = params.get("line")
        character = params.get("character")

        if not language or not project_path or not file_path:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path, file_path",
            }

        if line is None or character is None:
            return {
                "success": False,
                "error": "Missing required parameters: line, character",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        hover_info = await server.client.hover(file_path, line, character)

        if hover_info is None:
            return {
                "success": True,
                "hover_info": None,
            }

        return {
            "success": True,
            "hover_info": {
                "contents": hover_info.contents,
                "range": hover_info.range,
                "file_path": hover_info.file_path,
                "line": hover_info.line,
                "character": hover_info.character,
            },
        }

    async def diagnostic(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get code diagnostic information"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        severity_filter = params.get("severity_filter")

        if not language or not project_path or not file_path:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path, file_path",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        try:
            diagnostics = await server.client.diagnostic(file_path, severity_filter)
        except RuntimeError as e:
            # Check whether it is a method-not-supported error
            error_msg = str(e)
            if "Method Not Found" in error_msg or "-32601" in error_msg:
                return {
                    "success": False,
                    "error": f"LSP server does not support textDocument/diagnostic method. {language} LSP server may not provide diagnostics.",
                    "not_supported": True,
                }
            raise

        return {
            "success": True,
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

    async def code_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get code action information"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        line = params.get("line")
        character = params.get("character")

        if not language or not project_path or not file_path:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path, file_path",
            }

        if line is None or character is None:
            return {
                "success": False,
                "error": "Missing required parameters: line, character",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        try:
            code_actions = await server.client.code_action(file_path, line, character)
        except RuntimeError as e:
            # Check whether it is a method-not-supported error
            error_msg = str(e)
            if "Method Not Found" in error_msg or "-32601" in error_msg:
                return {
                    "success": False,
                    "error": f"LSP server does not support textDocument/codeAction method. {language} LSP server may not provide code actions.",
                    "not_supported": True,
                }
            raise

        return {
            "success": True,
            "code_actions": [
                {
                    "title": action.title,
                    "kind": action.kind,
                    "is_preferred": action.is_preferred,
                }
                for action in code_actions
            ],
        }

    async def code_action_by_name(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get code action information by symbol name"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        symbol_name = params.get("symbol_name")

        if not language or not project_path or not file_path:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path, file_path",
            }

        if not symbol_name:
            return {
                "success": False,
                "error": "Missing required parameter: symbol_name",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        try:
            code_actions = await server.client.code_action_by_name(
                file_path, symbol_name
            )
        except RuntimeError as e:
            # Check whether it is a method-not-supported error
            error_msg = str(e)
            if "Method Not Found" in error_msg or "-32601" in error_msg:
                return {
                    "success": False,
                    "error": f"LSP server does not support textDocument/codeAction method. {language} LSP server may not provide code actions.",
                    "not_supported": True,
                }
            raise

        return {
            "success": True,
            "code_actions": [
                {
                    "title": action.title,
                    "kind": action.kind,
                    "is_preferred": action.is_preferred,
                }
                for action in code_actions
            ],
        }

    async def status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get the daemon status"""
        servers_dict = {}

        for key, server in self.servers.items():
            servers_dict[key] = {
                "pid": server.process.pid if server.process else None,
                "start_time": str(server.last_activity) if server.last_activity else "",
                "is_alive": server.is_alive(),
            }

        return {
            "success": True,
            **servers_dict,
        }

    async def definition(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Jump to definition"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        line = params.get("line")
        column = params.get("column", 0)

        # Type checks
        if not isinstance(language, str) or not isinstance(project_path, str):
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path",
            }
        if not isinstance(file_path, str) or not isinstance(line, int):
            return {
                "success": False,
                "error": "Missing required parameters: file_path, line",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        locations = await server.client.definition(file_path, line, column)

        if not locations:
            return {"success": True, "location": None}

        # Return the first location (without code_snippet and context to avoid JSON serialization issues)
        first_location = locations[0]
        # Check the validity of the location: file_path must not be empty
        if not first_location.file_path:
            return {"success": True, "location": None}

        return {
            "success": True,
            "location": {
                "file_path": first_location.file_path,
                "line": first_location.line,
                "column": first_location.column,
                "uri": first_location.uri,
                "symbol_name": first_location.symbol_name,
                # "code_snippet": first_location.code_snippet,
                # "context": first_location.context,
            },
        }

    async def references(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find all references"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        line = params.get("line")
        column = params.get("column", 0)

        # Type checks
        if not isinstance(language, str) or not isinstance(project_path, str):
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path",
            }
        if not isinstance(file_path, str) or not isinstance(line, int):
            return {
                "success": False,
                "error": "Missing required parameters: file_path, line",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        locations = await server.client.references(file_path, line, column)

        return {
            "success": True,
            "locations": [
                {
                    "file_path": loc.file_path,
                    "line": loc.line,
                    "column": loc.column,
                }
                for loc in locations
            ],
        }

    async def implementation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find implementations"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        line = params.get("line")
        column = params.get("column", 0)

        # Type checks
        if not isinstance(language, str) or not isinstance(project_path, str):
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path",
            }
        if not isinstance(file_path, str) or not isinstance(line, int):
            return {
                "success": False,
                "error": "Missing required parameters: file_path, line",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        try:
            locations = await server.client.implementation(file_path, line, column)
        except NotImplementedError:
            return {
                "success": False,
                "error": "LSP server does not support implementation",
            }
        except RuntimeError as e:
            # Check whether it is a Method Not Found error
            if "Method Not Found" in str(e) or "-32601" in str(e):
                return {
                    "success": False,
                    "error": "LSP server does not support implementation",
                }
            raise

        return {
            "success": True,
            "locations": [
                {
                    "file_path": loc.file_path,
                    "line": loc.line,
                    "column": loc.column,
                }
                for loc in locations
            ],
        }

    async def type_definition(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find the type definition"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        line = params.get("line")
        column = params.get("column", 0)

        # Type checks
        if not isinstance(language, str) or not isinstance(project_path, str):
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path",
            }
        if not isinstance(file_path, str) or not isinstance(line, int):
            return {
                "success": False,
                "error": "Missing required parameters: file_path, line",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        try:
            locations = await server.client.type_definition(file_path, line, column)
        except NotImplementedError:
            return {
                "success": False,
                "error": "LSP server does not support type definition",
            }
        except RuntimeError as e:
            # Check whether it is a Method Not Found error
            if "Method Not Found" in str(e) or "-32601" in str(e):
                return {
                    "success": False,
                    "error": "LSP server does not support type definition",
                }
            raise

        if not locations:
            return {"success": True, "location": None}

        # Return the first location (without code_snippet and context to avoid JSON serialization issues)
        first_location = locations[0]
        # Check the validity of the location: file_path must not be empty
        if not first_location.file_path:
            return {"success": True, "location": None}

        return {
            "success": True,
            "location": {
                "file_path": first_location.file_path,
                "line": first_location.line,
                "column": first_location.column,
                "uri": first_location.uri,
                "symbol_name": first_location.symbol_name,
                # "code_snippet": first_location.code_snippet,
                # "context": first_location.context,
            },
        }

    def _find_symbol_by_name(
        self, symbols: list[Dict[str, Any]], symbol_name: str, file_path: str
    ) -> Dict[str, Any] | None:
        """Find the symbol with the specified name in the symbol list

        Args:
            symbols: The list of symbols
            symbol_name: The symbol name
            file_path: The file path (for error reporting)

        Returns:
            The matching symbol dictionary, or None if not found

        Raises:
            RuntimeError: If multiple matching symbols are found
        """
        # Exact match
        exact_matches = [s for s in symbols if s["name"] == symbol_name]

        if len(exact_matches) == 1:
            return exact_matches[0]
        elif len(exact_matches) > 1:
            # Multiple exact matches; return the first
            return exact_matches[0]

        # Fuzzy match (containing the symbol name)
        fuzzy_matches = [s for s in symbols if symbol_name.lower() in s["name"].lower()]

        if len(fuzzy_matches) == 1:
            return fuzzy_matches[0]
        elif len(fuzzy_matches) > 1:
            # Multiple fuzzy matches; choose the most similar one (the shortest)
            fuzzy_matches.sort(key=lambda s: len(s["name"]))
            return fuzzy_matches[0]

        return None

    async def definition_by_name(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find the definition by symbol name"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        symbol_name = params.get("symbol_name")

        if not language or not project_path or not file_path or not symbol_name:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path, file_path, symbol_name",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        symbols_result = await self.document_symbol(
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
            }
        )

        if not symbols_result.get("success"):
            return symbols_result

        symbols = symbols_result.get("symbols", [])
        symbol = self._find_symbol_by_name(symbols, symbol_name, file_path)

        if symbol is None:
            return {
                "success": False,
                "error": f"Symbol '{symbol_name}' not found in file '{file_path}'",
            }

        # Return the symbol's location directly (no longer calling definition, since querying the definition at the definition location returns nothing)
        result = {
            "success": True,
            "location": {
                "file_path": file_path,
                "line": symbol["line"],  # 1-based line number
                "column": symbol["column"],  # 1-based column number
                "uri": f"file://{file_path}",
                "symbol_name": symbol_name,
            },
        }
        return result

    async def callees_by_name(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Query which other functions are called inside the specified function (outgoing calls)"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        symbol_name = params.get("symbol_name")

        if not language or not project_path or not file_path or not symbol_name:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path, file_path, symbol_name",
            }

        # Get the symbol's location
        symbols_result = await self.document_symbol(
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
            }
        )

        if not symbols_result.get("success"):
            return symbols_result

        symbols = symbols_result.get("symbols", [])
        symbol = self._find_symbol_by_name(symbols, symbol_name, file_path)

        if symbol is None:
            return {
                "success": False,
                "error": f"Symbol '{symbol_name}' not found in file '{file_path}'",
            }

        # Get the symbol's start and end line numbers
        start_line = symbol["line"]
        end_line = symbol["end_line"]

        # Parse function calls
        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        callers = await server.client.callers_in_range(
            file_path, start_line, end_line, language
        )

        return {
            "success": True,
            "callers": callers,
        }

    async def definition_at_line(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find the definition by line number (automatically looks up the symbol column on that line)"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        line = params.get("line")
        symbol_name = params.get("symbol_name")  # Required, for exact matching

        if (
            not language
            or not project_path
            or not file_path
            or line is None
            or not symbol_name
        ):
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path, file_path, line, symbol_name",
            }

        # Get the list of symbols in the file
        symbols_result = await self.document_symbol(
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
            }
        )

        if not symbols_result.get("success"):
            return symbols_result

        symbols = symbols_result.get("symbols", [])

        # Find the symbols on that line (both document_symbol and the line parameter are 1-based)
        line_symbols = [s for s in symbols if s["line"] == line]

        if not line_symbols:
            return {
                "success": False,
                "error": f"No symbol found at line {line}",
            }

        # Exact match using the symbol name
        matched = [s for s in line_symbols if s["name"] == symbol_name]
        if matched:
            target_symbol = matched[0]
        else:
            return {
                "success": False,
                "error": f"Symbol '{symbol_name}' not found at line {line}",
            }

        # If the column is 0, automatically find the symbol's actual position on the line
        column = target_symbol["column"]
        if column == 0:
            try:
                # Read the file content to find the symbol's actual column on the line
                import asyncio
                from pathlib import Path

                content_text = await asyncio.to_thread(Path(file_path).read_text)
                lines = content_text.splitlines()
                if line < len(lines):
                    line_content = lines[line]
                    symbol_pos = line_content.find(target_symbol["name"])
                    if symbol_pos != -1:
                        column = symbol_pos
            except Exception:
                pass  # If lookup fails, use the original column

        # Call the definition method to find the definition
        return await self.definition(
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "line": target_symbol["line"],
                "column": column,
            }
        )

    async def references_by_name(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find references by symbol name"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        symbol_name = params.get("symbol_name")

        if not language or not project_path or not file_path or not symbol_name:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path, file_path, symbol_name",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        symbols_result = await self.document_symbol(
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
            }
        )

        if not symbols_result.get("success"):
            return symbols_result

        symbols = symbols_result.get("symbols", [])
        symbol = self._find_symbol_by_name(symbols, symbol_name, file_path)

        if symbol is None:
            return {
                "success": False,
                "error": f"Symbol '{symbol_name}' not found in file '{file_path}'",
            }

        return await self.references(
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "line": symbol["line"],
                "column": symbol["column"],
            }
        )

    async def implementation_by_name(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find implementations by symbol name"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        symbol_name = params.get("symbol_name")

        if not language or not project_path or not file_path or not symbol_name:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path, file_path, symbol_name",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        symbols_result = await self.document_symbol(
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
            }
        )

        if not symbols_result.get("success"):
            return symbols_result

        symbols = symbols_result.get("symbols", [])
        symbol = self._find_symbol_by_name(symbols, symbol_name, file_path)

        if symbol is None:
            return {
                "success": False,
                "error": f"Symbol '{symbol_name}' not found in file '{file_path}'",
            }

        return await self.definition(
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "line": symbol["line"] - 1,  # SymbolInfo is 1-based, LSP needs 0-based
                "column": symbol["column"]
                - 1,  # SymbolInfo is 1-based, LSP needs 0-based
            }
        )

    async def type_definition_by_name(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find the type definition by symbol name"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        symbol_name = params.get("symbol_name")

        if not language or not project_path or not file_path or not symbol_name:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path, file_path, symbol_name",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        symbols_result = await self.document_symbol(
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
            }
        )

        if not symbols_result.get("success"):
            return symbols_result

        symbols = symbols_result.get("symbols", [])
        symbol = self._find_symbol_by_name(symbols, symbol_name, file_path)

        if symbol is None:
            return {
                "success": False,
                "error": f"Symbol '{symbol_name}' not found in file '{file_path}'",
            }

        return await self.type_definition(
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "line": symbol["line"],
                "column": symbol["column"],
            }
        )

    async def callers_by_name(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find callees by symbol name (all symbols called inside the function)"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        symbol_name = params.get("symbol_name")

        if not language or not project_path or not file_path or not symbol_name:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path, file_path, symbol_name",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        try:
            locations = await server.client.callers_by_name(file_path, symbol_name)
        except RuntimeError as e:
            error_msg = str(e)
            if "Method Not Found" in error_msg or "-32601" in error_msg:
                return {
                    "success": False,
                    "error": f"LSP server does not support the required method. {error_msg}",
                    "not_supported": True,
                }
            raise

        return {
            "success": True,
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

    async def incoming_calls_by_name(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Query who calls this symbol by symbol name (incoming calls / callers)"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        symbol_name = params.get("symbol_name")

        if not language or not project_path or not file_path or not symbol_name:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path, file_path, symbol_name",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        try:
            locations = await server.client.incoming_calls_by_name(
                file_path, symbol_name
            )
        except RuntimeError as e:
            error_msg = str(e)
            if "Method Not Found" in error_msg or "-32601" in error_msg:
                return {
                    "success": False,
                    "error": f"LSP server does not support callHierarchy. {error_msg}",
                    "not_supported": True,
                }
            raise

        return {
            "success": True,
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

    async def outgoing_calls_by_name(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Query which symbols this symbol calls by symbol name (outgoing calls / callees)"""
        language = params.get("language")
        project_path = params.get("project_path")
        file_path = params.get("file_path")
        symbol_name = params.get("symbol_name")

        if not language or not project_path or not file_path or not symbol_name:
            return {
                "success": False,
                "error": "Missing required parameters: language, project_path, file_path, symbol_name",
            }

        server = await self.get_or_create_server(language, project_path)

        if server.client is None:
            return {
                "success": False,
                "error": "LSP server client not initialized",
            }

        try:
            locations = await server.client.outgoing_calls_by_name(
                file_path, symbol_name
            )
        except RuntimeError as e:
            error_msg = str(e)
            if "Method Not Found" in error_msg or "-32601" in error_msg:
                return {
                    "success": False,
                    "error": f"LSP server does not support callHierarchy. {error_msg}",
                    "not_supported": True,
                }
            raise

        return {
            "success": True,
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


async def main(addr: Union[str, tuple, None] = None) -> None:
    """Main function"""
    if addr is None:
        addr = _get_lsp_daemon_addr()

    daemon = LSPDaemon(addr)
    await daemon.start()

    try:
        # Wait for a stop signal
        while daemon.running:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await daemon.stop()


if __name__ == "__main__":
    addr_arg: Union[str, tuple, None] = None
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if ":" in arg and not arg.startswith("/"):
            parts = arg.split(":")
            if len(parts) == 2:
                try:
                    addr_arg = (parts[0], int(parts[1]))
                except ValueError:
                    pass
        else:
            addr_arg = arg

    asyncio.run(main(addr_arg))
