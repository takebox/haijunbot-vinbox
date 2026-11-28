"""
LSP server manager - implements persistent LSP server management.

This module provides persistent management of LSP servers, including:
- Starting, monitoring, restarting, and stopping server processes
- Caching and reusing server instances
- Server instances separated by language and project
- Automatic shutdown on timeout

Author: HaijunBot
"""

from __future__ import annotations

import asyncio
import json
import signal
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from haijunbot.haijunbot_utils.config import read_text_file
from haijunbot.haijunbot_utils.exception_utils import save_exception

from haijunbot.haijunbot_lsp.config import LSPConfigReader
from haijunbot.haijunbot_lsp.client import LSPClient


@dataclass
class LSPServerInstance:
    """
    LSP server instance, encapsulating the process and communication of a single LSP server.

    Attributes:
        language: The language the server supports (e.g. 'python', 'rust')
        project_path: The project path, used to distinguish different projects
        process: The LSP server subprocess
        client: The LSP client instance
        status: The server status (starting/running/shutting_down/stopped)
        last_activity: The timestamp of the last activity
        initialize_timeout: The initialization timeout in seconds
    """

    language: str
    project_path: str
    process: Optional[asyncio.subprocess.Process] = field(default=None)
    client: Optional[LSPClient] = field(default=None)
    status: str = field(default="stopped")
    last_activity: float = field(default_factory=time.time)
    # First start of a language server can be slow (index building, Windows antivirus
    # scanning, CPU contention when the test suite runs sequentially), so allow 60s.
    initialize_timeout: int = field(default=60)

    async def start(self, config_reader: LSPConfigReader) -> None:
        """
        Start the LSP server instance.

        Args:
            config_reader: Configuration reader used to get the LSP server configuration

        Raises:
            RuntimeError: If the server fails to start or initialization times out
        """
        if self.status in ("starting", "running"):
            return

        self.status = "starting"

        try:
            # Get the LSP server configuration
            config = config_reader.get_language_config(self.language)
            if config is None:
                raise RuntimeError(
                    f"No LSP server configuration found for language: {self.language}"
                )

            command = [config.command] + config.args

            # In persistent mode, remove the --check-parent-process argument
            # Otherwise, when the parent process exits, the LSP server exits too
            command = [arg for arg in command if arg != "--check-parent-process"]

            # Start the LSP server process with asyncio (independent of the parent process)
            self.process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_path,  # Set the working directory to the project path
                start_new_session=True,  # Make the process independent so the parent cannot kill it
            )

            if (
                not self.process
                or not self.process.stdout
                or not self.process.stdin
                or not self.process.stderr
            ):
                raise RuntimeError("Failed to start LSP server process")

            # Wait a short while to make sure the process has started
            await asyncio.sleep(0.2)

            # Check whether the process exited immediately
            if self.process.returncode is not None:
                if self.process.stderr:
                    stderr_output = await self.process.stderr.read()
                    error_msg = stderr_output.decode("utf-8", errors="ignore")
                    raise RuntimeError(
                        f"LSP server '{' '.join(command)}' failed to start\n"
                        f"Exit code: {self.process.returncode}\n"
                        f"Error: {error_msg}"
                    )
                else:
                    raise RuntimeError(
                        f"LSP server '{config.command}' exited with code {self.process.returncode}"
                    )

            # Create the LSP client (reusing the existing process, in persistent mode)
            self.client = LSPClient(
                command=config.command,
                args=config.args,
                mode="persistent",
            )

            # Inject the existing process and reader/writer
            self.client.process = self.process
            self.client.reader = self.process.stdout
            self.client.writer = self.process.stdin

            # Initialize the LSP server
            await asyncio.wait_for(
                self.client.initialize(),
                timeout=self.initialize_timeout,
            )

            self.status = "running"
            self.last_activity = time.time()

        except asyncio.TimeoutError:
            self.status = "stopped"
            await self._cleanup()
            raise RuntimeError(
                f"LSP server initialization timeout after {self.initialize_timeout}s"
            )
        except Exception as e:
            self.status = "stopped"
            await self._cleanup()
            raise RuntimeError(f"Failed to start LSP server: {e}")

    async def shutdown(self) -> None:
        """
        Gracefully shut down the LSP server instance.

        First sends shutdown and exit notifications; if it times out, forcibly terminates the process.
        """
        if self.status in ("stopped", "shutting_down"):
            return

        self.status = "shutting_down"

        try:
            if self.client:
                try:
                    await asyncio.wait_for(self.client.shutdown(), timeout=5.0)
                except Exception:
                    pass  # Ignore shutdown errors
        except Exception as e:
            save_exception(e, module="haijunbot_lsp.server_manager", function="")
            pass
        finally:
            await self._cleanup()
            self.status = "stopped"

    async def _cleanup(self) -> None:
        """Clean up resources: stop the process and the client."""
        if self.process:
            try:
                self.process.terminate()
                # asyncio.subprocess.Process.wait() does not support timeout
                # Implement it using asyncio.wait_for
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except Exception as e:
                save_exception(e, module="haijunbot_lsp.server_manager", function="")
                pass
            finally:
                self.process = None

        self.client = None

    def update_activity(self) -> None:
        """Update the last activity time."""
        self.last_activity = time.time()

    def is_expired(self, timeout: float) -> bool:
        """
        Check whether the server instance has timed out.

        Args:
            timeout: The timeout in seconds

        Returns:
            True if timed out, otherwise False
        """
        if self.status != "running":
            return False
        return (time.time() - self.last_activity) > timeout

    def is_alive(self) -> bool:
        """Check whether the server process is alive."""
        if not self.process:
            return False
        # asyncio.subprocess.Process has no poll() method
        # Use returncode to determine this; None means the process is still running
        return self.process.returncode is None


class LSPServerManager:
    """
    LSP server manager (singleton pattern).

    Manages multiple LSP server instances, providing server retrieval, start, stop, and monitoring functionality.

    Attributes:
        _instance: The singleton instance
        _servers: Dictionary of server instances, keyed by {language}:{project_path}
        _lock: Concurrency access lock
        _config_reader: The configuration reader
        _default_timeout: The default timeout in seconds
        _monitor_task: The monitor task
        _initialized: Initialization flag
    """

    _instance: Optional[LSPServerManager] = None
    _servers: Dict[str, LSPServerInstance]
    _lock: asyncio.Lock
    _config_reader: LSPConfigReader
    _default_timeout: float
    _monitor_task: Optional[asyncio.Task[None]]
    _initialized: bool
    _state_file: Path  # Process state file

    def __new__(cls) -> LSPServerManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Initialize the class attributes
            cls._instance._servers = {}
            cls._instance._lock = asyncio.Lock()
            cls._instance._config_reader = LSPConfigReader()
            cls._instance._default_timeout = 1800.0  # Default 30 minutes
            cls._instance._monitor_task = None
            cls._instance._initialized = True
            cls._instance._state_file = Path.home() / ".haijunbot" / "lsp_servers.json"
        return cls._instance

    def __init__(self) -> None:
        # Singleton pattern; __init__ is only called once
        pass

    def _get_server_key(self, language: str, project_path: str) -> str:
        """Generate the cache key for a server instance."""
        return f"{language}:{project_path}"

    def _save_server_state(self, key: str, pid: int) -> None:
        """Save the server process information to a file.

        Args:
            key: The server key
            pid: The process ID
        """
        try:
            # Make sure the directory exists
            self._state_file.parent.mkdir(parents=True, exist_ok=True)

            # Read the existing state
            state: Dict[str, Dict[str, Any]] = {}
            if self._state_file.exists():
                content = read_text_file(str(self._state_file))
                state = json.loads(content)

            # Update the state
            state[key] = {
                "pid": pid,
                "language": key.split(":")[0],
                "project_path": key.split(":", 1)[1] if ":" in key else ".",
                "start_time": time.time(),
            }

            # Save the state
            with open(self._state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass  # Ignore save errors

    def _remove_server_state(self, key: str) -> None:
        """Remove the server process information.

        Args:
            key: The server key
        """
        try:
            if self._state_file.exists():
                content = read_text_file(str(self._state_file))
                state = json.loads(content)

                if key in state:
                    del state[key]

                    with open(self._state_file, "w") as f:
                        json.dump(state, f, indent=2)
        except Exception:
            pass  # Ignore removal errors

    async def get_server(self, language: str, project_path: str) -> LSPServerInstance:
        """
        Get or create an LSP server instance.

        If the server instance already exists and is running normally, returns it directly; otherwise creates a new instance.

        Args:
            language: The language the LSP server supports
            project_path: The project path

        Returns:
            The LSP server instance

        Raises:
            RuntimeError: If the server fails to start
        """
        async with self._lock:
            key = self._get_server_key(language, project_path)

            # Check whether a running server already exists
            if key in self._servers:
                server = self._servers[key]
                if server.is_alive() and server.status == "running":
                    server.update_activity()
                    return server
                else:
                    # The server is no longer valid; clean up and recreate it
                    await server.shutdown()
                    del self._servers[key]

            # Create a new server instance
            server = LSPServerInstance(language=language, project_path=project_path)
            await server.start(self._config_reader)
            self._servers[key] = server

            # Save the process information
            if server.process:
                self._save_server_state(key, server.process.pid)

            return server

    async def start_server(self, language: str, project_path: str) -> LSPServerInstance:
        """
        Start an LSP server instance.

        Args:
            language: The language the LSP server supports
            project_path: The project path

        Returns:
            The LSP server instance

        Raises:
            RuntimeError: If the server fails to start
        """
        return await self.get_server(language, project_path)

    async def stop_server(self, language: str, project_path: str) -> None:
        """
        Stop the LSP server instance for the specified language and project.

        Also stops the background daemon process.

        Args:
            language: The language the LSP server supports
            project_path: The project path
        """
        async with self._lock:
            key = self._get_server_key(language, project_path)

            # Stop the server
            if key in self._servers:
                server = self._servers[key]
                await server.shutdown()
                del self._servers[key]

            # Remove the process information
            self._remove_server_state(key)

            # Find and stop the daemon process (Unix only; Windows has no pgrep)
            if sys.platform != "win32":
                try:
                    result = subprocess.run(
                        [
                            "pgrep",
                            "-f",
                            f'keep_server_alive.*"{language}".*"{project_path}"',
                        ],
                        capture_output=True,
                        text=True,
                    )

                    if result.returncode == 0:
                        for pid in result.stdout.strip().split("\n"):
                            if pid:
                                try:
                                    if sys.platform == "win32":
                                        os.kill(int(pid), signal.SIGTERM)
                                    else:
                                        os.kill(int(pid), signal.SIGKILL)
                                except (ProcessLookupError, ValueError):
                                    pass
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_lsp.server_manager",
                        function="_remove_server_state",
                    )
                    pass

    async def stop_all(self) -> None:
        """Stop all LSP server instances."""
        async with self._lock:
            tasks = [server.shutdown() for server in self._servers.values()]
            await asyncio.gather(*tasks, return_exceptions=True)
            self._servers.clear()
            # Clear the process information
            try:
                if self._state_file.exists():
                    self._state_file.unlink()
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_lsp.server_manager",
                    function="_remove_server_state",
                )
                pass

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the status of all server instances.

        Returns:
            A status dictionary keyed by {language}:{project_path}, with server status information as values
        """
        status = {}

        # Read the server status from memory
        for key, server in self._servers.items():
            status[key] = {
                "language": server.language,
                "project_path": server.project_path,
                "status": server.status,
                "is_alive": server.is_alive(),
                "last_activity": server.last_activity,
                "idle_time": time.time() - server.last_activity,
            }

        # Read the persisted server status
        try:
            if self._state_file.exists():
                content = read_text_file(str(self._state_file))
                saved_state = json.loads(content)

                # Check whether the persisted process is still running
                for key, info in saved_state.items():
                    # If it is already in memory, skip it
                    if key in status:
                        continue

                    # Check whether the process is still running
                    try:
                        if sys.platform == "win32":
                            # Windows: os.kill(pid, 0) is not available
                            from haijunbot.haijunbot_utils.utils import _is_process_alive

                            if not _is_process_alive(info["pid"]):
                                raise ProcessLookupError
                        else:
                            os.kill(info["pid"], 0)
                    except ProcessLookupError:
                        # The process does not exist; remove it from the persisted file
                        self._remove_server_state(key)
                    except PermissionError:
                        # The process exists but is not accessible; add it to the status
                        status[key] = {
                            "language": info["language"],
                            "project_path": info["project_path"],
                            "status": "running",
                            "is_alive": True,
                            "last_activity": info.get("start_time", time.time()),
                            "idle_time": time.time()
                            - info.get("start_time", time.time()),
                            "pid": info["pid"],
                        }
                    else:
                        # The process is still running; add it to the status
                        status[key] = {
                            "language": info["language"],
                            "project_path": info["project_path"],
                            "status": "running",
                            "is_alive": True,
                            "last_activity": info.get("start_time", time.time()),
                            "idle_time": time.time()
                            - info.get("start_time", time.time()),
                            "pid": info["pid"],
                        }
        except Exception:
            pass  # Ignore read errors

        return status

    async def start_monitor(self, check_interval: float = 30.0) -> None:
        """
        Start the server monitoring task.

        Periodically checks server status, cleans up invalid server instances, and shuts down expired ones.

        Args:
            check_interval: The check interval in seconds, default 30 seconds
        """
        if self._monitor_task and not self._monitor_task.done():
            return  # The monitoring task is already running

        async def _monitor() -> None:
            while True:
                try:
                    await asyncio.sleep(check_interval)
                    await self._cleanup_expired_servers()
                except asyncio.CancelledError:
                    break
                except Exception:
                    pass  # Ignore monitor errors and continue running

        self._monitor_task = asyncio.create_task(_monitor())

    async def stop_monitor(self) -> None:
        """Stop the server monitoring task."""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

    async def _cleanup_expired_servers(self) -> None:
        """Clean up expired server instances."""
        async with self._lock:
            expired_keys = []
            for key, server in self._servers.items():
                if not server.is_alive():
                    expired_keys.append(key)
                elif server.is_expired(self._default_timeout):
                    await server.shutdown()
                    expired_keys.append(key)

            for key in expired_keys:
                if key in self._servers:
                    del self._servers[key]

    async def __aenter__(self) -> LSPServerManager:
        await self.start_monitor()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.stop_monitor()
        await self.stop_all()
