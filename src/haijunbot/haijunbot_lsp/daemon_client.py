"""LSP daemon client module

This module provides the client interface for communicating with the LSP daemon.
Unix: Unix domain socket; Windows: TCP 127.0.0.1.
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from haijunbot.haijunbot_lsp.client import LocationInfo, SymbolInfo
from haijunbot.haijunbot_lsp.daemon import (
    _get_lsp_daemon_addr,
)
from haijunbot.haijunbot_lsp.protocol import (
    CodeActionInfo,
    DiagnosticInfo,
    FoldingRangeInfo,
    HoverInfo,
)

_IS_WINDOWS = sys.platform == "win32"


class LSPDaemonClient:
    """LSP daemon client

    Unix: Unix domain socket; Windows: TCP 127.0.0.1.
    """

    def __init__(self, addr: Union[str, tuple, None] = None):
        if addr is None:
            addr = _get_lsp_daemon_addr()
        self.addr = addr
        self._is_unix = isinstance(addr, str)
        # Backward compatibility for references to client.socket_path in old code (e.g. daemon_stop)
        self.socket_path = addr if self._is_unix else f"{addr[0]}:{addr[1]}"
        # Daemon readiness flag: probe/start only on the first request, to avoid
        # opening an extra probe connection on every request (a probe connection closed right away makes the server read a RST, interfering with normal requests)
        self._daemon_ready = False

    async def _ensure_daemon_running(self) -> None:
        """Ensure the daemon is running (probe/start only when readiness is not yet confirmed)"""
        if self._daemon_ready:
            return

        async def _try_connect() -> bool:
            try:
                if self._is_unix:
                    # On Unix, self.addr is a string
                    assert isinstance(self.addr, str), "The Unix socket address must be a string"
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_unix_connection(self.addr), timeout=2.0
                    )
                else:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(self.addr[0], self.addr[1]),
                        timeout=2.0,
                    )
                writer.close()
                await writer.wait_closed()
                return True
            except (
                ConnectionRefusedError,
                FileNotFoundError,
                asyncio.TimeoutError,
                OSError,
            ):
                return False

        if await _try_connect():
            self._daemon_ready = True
            return

        # Start the daemon
        daemon_script = str(Path(__file__).resolve().parent / "daemon.py")
        if not os.path.exists(daemon_script):
            raise FileNotFoundError(f"The daemon script does not exist: {daemon_script}")

        if _IS_WINDOWS:
            flags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
            if hasattr(subprocess, "DETACHED_PROCESS"):
                flags |= subprocess.DETACHED_PROCESS
            subprocess.Popen(
                [sys.executable, daemon_script],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
                cwd=os.path.expanduser("~"),
            )
        else:
            # Must use subprocess.Popen instead of asyncio.create_subprocess_exec:
            # subprocesses created by the latter are managed by the current event loop and are
            # terminated when asyncio.run ends or the process exits, causing the daemon to die with
            # the client process and Connection reset by peer during the restart window.
            subprocess.Popen(
                [sys.executable, daemon_script],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                cwd=os.path.expanduser("~"),
            )

        # Wait for the daemon to become ready (up to 5 seconds)
        for i in range(50):
            await asyncio.sleep(0.1)
            if await _try_connect():
                await asyncio.sleep(0.5)
                self._daemon_ready = True
                return

        raise RuntimeError(
            "Failed to start the daemon."
            + (
                f"socket not created: {self.addr}"
                if self._is_unix
                else f"unable to connect to TCP: {self.addr[0]}:{self.addr[1]}"
            )
        )

    async def _send_request(
        self, method: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send a request to the daemon"""

        # Automatically start the daemon (if it is not running)
        await self._ensure_daemon_running()

        if self._is_unix:
            assert isinstance(self.addr, str), "The Unix socket address must be a string"
            if not os.path.exists(self.addr):
                raise RuntimeError(f"Failed to start the daemon. The socket file does not exist: {self.addr}")

        request = {"method": method, "params": params}
        request_json = json.dumps(request, ensure_ascii=False)
        request_bytes = request_json.encode()
        # Content-Length must be the UTF-8 byte count (not the character count), otherwise requests containing non-ASCII characters get truncated
        request_data = (
            f"Content-Length: {len(request_bytes)}\r\n\r\n".encode() + request_bytes
        )

        try:
            if self._is_unix:
                # On Unix, self.addr is a string
                assert isinstance(self.addr, str), "The Unix socket address must be a string"
                reader, writer = await asyncio.open_unix_connection(self.addr)
            else:
                reader, writer = await asyncio.open_connection(
                    self.addr[0], self.addr[1]
                )

            # Send the request
            writer.write(request_data)
            await writer.drain()

            # Read the response
            line = await reader.readline()
            if not line:
                raise RuntimeError("The daemon closed the connection")

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
            response = json.loads(content.decode())

            assert isinstance(response, dict)

            writer.close()
            await writer.wait_closed()

            return response

        except ConnectionRefusedError:
            self._daemon_ready = False
            raise RuntimeError("Cannot connect to the daemon. Please run first: hlsp daemon start")
        except Exception as e:
            # Communication failure may be because the daemon exited; reset the flag so the next request probes/starts again
            self._daemon_ready = False
            raise RuntimeError(f"Daemon communication failed: {e}")

    async def start_server(self, language: str, project_path: str) -> int:
        """Start the LSP server"""
        response = await self._send_request(
            "start_server",
            {"language": language, "project_path": project_path},
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        pid = response.get("pid")
        if pid is None:
            raise RuntimeError("The daemon did not return a PID")

        assert isinstance(pid, int)
        return pid

    async def stop_server(self, language: str, project_path: str) -> None:
        """Stop the LSP server"""
        response = await self._send_request(
            "stop_server",
            {"language": language, "project_path": project_path},
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

    async def workspace_symbol(
        self, language: str, project_path: str, query: str
    ) -> List[SymbolInfo]:
        """Search for symbols in the workspace"""
        response = await self._send_request(
            "workspace_symbol",
            {"language": language, "project_path": project_path, "query": query},
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        symbols_data = response.get("symbols", [])
        return [
            SymbolInfo(
                name=s["name"],
                kind=s["kind"],
                file_path=s.get("file_path", ""),
                line=s["line"],
                column=s["column"],
                description=s["description"],
            )
            for s in symbols_data
        ]

    async def document_symbol(
        self, language: str, project_path: str, file_path: str
    ) -> List[SymbolInfo]:
        """List the document symbols in a file"""
        response = await self._send_request(
            "document_symbol",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        symbols_data = response.get("symbols", [])
        return [
            SymbolInfo(
                name=s["name"],
                kind=s["kind"],
                file_path=s.get("file_path", ""),
                line=s["line"],
                column=s["column"],
                description=s["description"],
            )
            for s in symbols_data
        ]

    async def folding_range(
        self, language: str, project_path: str, file_path: str
    ) -> List[FoldingRangeInfo]:
        """Get the code folding ranges"""
        response = await self._send_request(
            "folding_range",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        folding_ranges_data = response.get("folding_ranges", [])
        return [
            FoldingRangeInfo(
                start_line=fr["start_line"],
                start_character=fr["start_character"],
                end_line=fr["end_line"],
                end_character=fr["end_character"],
                kind=fr.get("kind"),
                collapsed_text=fr.get("collapsed_text"),
            )
            for fr in folding_ranges_data
        ]

    async def hover(
        self,
        language: str,
        project_path: str,
        file_path: str,
        line: int,
        character: int,
    ) -> Optional[HoverInfo]:
        """Get symbol hover information"""
        response = await self._send_request(
            "hover",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "line": line,
                "character": character,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        hover_data = response.get("hover_info")
        if hover_data is None:
            return None

        return HoverInfo(
            contents=hover_data["contents"],
            range=hover_data["range"],
            file_path=hover_data["file_path"],
            line=hover_data["line"],
            character=hover_data["character"],
        )

    async def diagnostic(
        self,
        language: str,
        project_path: str,
        file_path: str,
        severity_filter: Optional[int] = None,
    ) -> List[DiagnosticInfo]:
        """Get code diagnostic information"""
        response = await self._send_request(
            "diagnostic",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "severity_filter": severity_filter,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        diagnostics_data = response.get("diagnostics", [])
        return [
            DiagnosticInfo(
                range=diag["range"],
                severity=diag["severity"],
                code=diag["code"],
                source=diag["source"],
                message=diag["message"],
            )
            for diag in diagnostics_data
        ]

    async def code_action(
        self,
        language: str,
        project_path: str,
        file_path: str,
        line: int,
        character: int,
    ) -> List[CodeActionInfo]:
        """Get code action information"""
        response = await self._send_request(
            "code_action",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "line": line,
                "character": character,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        code_actions_data = response.get("code_actions", [])
        return [
            CodeActionInfo(
                title=action["title"],
                kind=action["kind"],
                is_preferred=action["is_preferred"],
            )
            for action in code_actions_data
        ]

    async def code_action_by_name(
        self,
        language: str,
        project_path: str,
        file_path: str,
        symbol_name: str,
    ) -> List[CodeActionInfo]:
        """Get code action information by symbol name"""
        response = await self._send_request(
            "code_action_by_name",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "symbol_name": symbol_name,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        code_actions_data = response.get("code_actions", [])
        return [
            CodeActionInfo(
                title=action["title"],
                kind=action["kind"],
                is_preferred=action["is_preferred"],
            )
            for action in code_actions_data
        ]

    async def status(self) -> Dict[str, Any]:
        """Get the daemon status"""
        response = await self._send_request("status", {})

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        return response

    async def definition(
        self,
        language: str,
        project_path: str,
        file_path: str,
        line: int,
        column: int = 0,
    ) -> LocationInfo | None:
        """Jump to definition"""
        response = await self._send_request(
            "definition",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "line": line,
                "column": column,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        location_data = response.get("location")
        if location_data is None:
            return None

        return LocationInfo(
            file_path=location_data["file_path"],
            line=location_data["line"],
            column=location_data["column"],
            uri=location_data.get("uri", f"file://{location_data['file_path']}"),
            code_snippet=location_data.get("code_snippet"),
            symbol_name=location_data.get("symbol_name"),
            context=location_data.get("context"),
        )

    async def references(
        self,
        language: str,
        project_path: str,
        file_path: str,
        line: int,
        column: int = 0,
    ) -> list[LocationInfo]:
        """Find all references"""
        response = await self._send_request(
            "references",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "line": line,
                "column": column,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        locations_data = response.get("locations", [])
        return [
            LocationInfo(
                file_path=loc["file_path"],
                line=loc["line"],
                column=loc["column"],
                uri=loc.get("uri", f"file://{loc['file_path']}"),
                code_snippet=loc.get("code_snippet"),
                symbol_name=loc.get("symbol_name"),
                context=loc.get("context"),
            )
            for loc in locations_data
        ]

    async def implementation(
        self,
        language: str,
        project_path: str,
        file_path: str,
        line: int,
        column: int = 0,
    ) -> list[LocationInfo]:
        """Find implementations"""
        response = await self._send_request(
            "implementation",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "line": line,
                "column": column,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        locations_data = response.get("locations", [])
        return [
            LocationInfo(
                file_path=loc["file_path"],
                line=loc["line"],
                column=loc["column"],
                uri=loc.get("uri", f"file://{loc['file_path']}"),
                code_snippet=loc.get("code_snippet"),
                symbol_name=loc.get("symbol_name"),
                context=loc.get("context"),
            )
            for loc in locations_data
        ]

    async def type_definition(
        self,
        language: str,
        project_path: str,
        file_path: str,
        line: int,
        column: int = 0,
    ) -> LocationInfo | None:
        """Find the type definition"""
        response = await self._send_request(
            "type_definition",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "line": line,
                "column": column,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        location_data = response.get("location")
        if location_data is None:
            return None

        return LocationInfo(
            file_path=location_data["file_path"],
            line=location_data["line"],
            column=location_data["column"],
            uri=f"file://{location_data['file_path']}",
            symbol_name=location_data.get("symbol_name"),
        )

    async def definition_at_line(
        self,
        language: str,
        project_path: str,
        file_path: str,
        line: int,
        symbol_name: str,
    ) -> LocationInfo | None:
        """Find the definition by line number (automatically looks up the symbol column on that line)

        Args:
            language: The language
            project_path: The project path
            file_path: The file path
            line: The line number (0-based)
            symbol_name: The symbol name (required, for exact matching)

        Returns:
            The definition location information, or None if not found
        """
        response = await self._send_request(
            "definition_at_line",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "line": line,
                "symbol_name": symbol_name,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        location_data = response.get("location")
        if location_data is None:
            return None

        return LocationInfo(
            file_path=location_data["file_path"],
            line=location_data["line"],
            column=location_data["column"],
            uri=f"file://{location_data['file_path']}",
            symbol_name=location_data.get("symbol_name"),
        )

    async def definition_by_name(
        self, language: str, project_path: str, file_path: str, symbol_name: str
    ) -> LocationInfo | None:
        """Find the definition by symbol name"""
        response = await self._send_request(
            "definition_by_name",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "symbol_name": symbol_name,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        location_data = response.get("location")
        if location_data is None:
            return None

        return LocationInfo(
            file_path=location_data["file_path"],
            line=location_data["line"],
            column=location_data["column"],
            uri=f"file://{location_data['file_path']}",
            symbol_name=location_data.get("symbol_name"),
        )

    async def references_by_name(
        self, language: str, project_path: str, file_path: str, symbol_name: str
    ) -> list[LocationInfo]:
        """Find references by symbol name"""
        response = await self._send_request(
            "references_by_name",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "symbol_name": symbol_name,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        locations_data = response.get("locations", [])
        return [
            LocationInfo(
                file_path=loc["file_path"],
                line=loc["line"],
                column=loc["column"],
                uri=loc.get("uri", f"file://{loc['file_path']}"),
                code_snippet=loc.get("code_snippet"),
                symbol_name=loc.get("symbol_name"),
                context=loc.get("context"),
            )
            for loc in locations_data
        ]

    async def callees_by_name(
        self, language: str, project_path: str, file_path: str, symbol_name: str
    ) -> list[Dict[str, Any]]:
        """Query which other functions are called inside the specified function (outgoing calls)"""
        response = await self._send_request(
            "callers_by_name",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "symbol_name": symbol_name,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        return response.get("callers", [])  # type: ignore[no-any-return]

    async def implementation_by_name(
        self, language: str, project_path: str, file_path: str, symbol_name: str
    ) -> list[LocationInfo]:
        """Find implementations by symbol name"""
        response = await self._send_request(
            "implementation_by_name",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "symbol_name": symbol_name,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        locations_data = response.get("locations", [])
        return [
            LocationInfo(
                file_path=loc["file_path"],
                line=loc["line"],
                column=loc["column"],
                uri=loc.get("uri", f"file://{loc['file_path']}"),
                code_snippet=loc.get("code_snippet"),
                symbol_name=loc.get("symbol_name"),
                context=loc.get("context"),
            )
            for loc in locations_data
        ]

    async def type_definition_by_name(
        self, language: str, project_path: str, file_path: str, symbol_name: str
    ) -> LocationInfo | None:
        """Find the type definition by symbol name"""
        response = await self._send_request(
            "type_definition_by_name",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "symbol_name": symbol_name,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        location_data = response.get("location")
        if location_data is None:
            return None

        return LocationInfo(
            file_path=location_data["file_path"],
            line=location_data["line"],
            column=location_data["column"],
            uri=f"file://{location_data['file_path']}",
            symbol_name=location_data.get("symbol_name"),
        )

    async def callers_by_name(
        self, language: str, project_path: str, file_path: str, symbol_name: str
    ) -> list[LocationInfo]:
        """Find callees by symbol name (all symbols called inside the function)

        Args:
            language: The language
            project_path: The project path
            file_path: The file path
            symbol_name: The symbol name

        Returns:
            The list of definition locations of the called symbols
        """
        response = await self._send_request(
            "callers_by_name",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "symbol_name": symbol_name,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        locations_data = response.get("locations", [])
        return [
            LocationInfo(
                file_path=loc["file_path"],
                line=loc["line"],
                column=loc["column"],
                uri=loc.get("uri", f"file://{loc['file_path']}"),
                code_snippet=loc.get("code_snippet"),
                symbol_name=loc.get("symbol_name"),
                context=loc.get("context"),
            )
            for loc in locations_data
        ]

    async def incoming_calls_by_name(
        self, language: str, project_path: str, file_path: str, symbol_name: str
    ) -> list[LocationInfo]:
        """Query who calls this symbol by symbol name (incoming calls / callers)

        Args:
            language: The language
            project_path: The project path
            file_path: The file path
            symbol_name: The symbol name

        Returns:
            The list of caller locations
        """
        response = await self._send_request(
            "incoming_calls_by_name",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "symbol_name": symbol_name,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        locations_data = response.get("locations", [])
        return [
            LocationInfo(
                file_path=loc["file_path"],
                line=loc["line"],
                column=loc["column"],
                uri=loc.get("uri", f"file://{loc['file_path']}"),
                code_snippet=loc.get("code_snippet"),
                symbol_name=loc.get("symbol_name"),
                context=loc.get("context"),
            )
            for loc in locations_data
        ]

    async def outgoing_calls_by_name(
        self, language: str, project_path: str, file_path: str, symbol_name: str
    ) -> list[LocationInfo]:
        """Query which symbols this symbol calls by symbol name (outgoing calls / callees)

        Args:
            language: The language
            project_path: The project path
            file_path: The file path
            symbol_name: The symbol name

        Returns:
            The list of callee locations
        """
        response = await self._send_request(
            "outgoing_calls_by_name",
            {
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "symbol_name": symbol_name,
            },
        )

        if not response.get("success"):
            raise RuntimeError(response.get("error", "Unknown error"))

        locations_data = response.get("locations", [])
        return [
            LocationInfo(
                file_path=loc["file_path"],
                line=loc["line"],
                column=loc["column"],
                uri=loc.get("uri", f"file://{loc['file_path']}"),
                code_snippet=loc.get("code_snippet"),
                symbol_name=loc.get("symbol_name"),
                context=loc.get("context"),
            )
            for loc in locations_data
        ]
