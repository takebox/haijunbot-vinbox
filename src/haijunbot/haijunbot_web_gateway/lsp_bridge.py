"""Generic LSP WebSocket <-> subprocess stdio bridge.

This module is **completely language-agnostic**: it is only responsible for
    1. Fetching the spec by ``server_id`` from :mod:`haijunbot.haijunbot_web_gateway.lsp_registry`,
       and starting the language server process using the ``command`` / ``args`` in the spec;
    2. Writing text messages received from the browser WebSocket into the subprocess stdin following LSP framing rules;
    3. Sending each message parsed from the subprocess stdout following LSP framing rules back to the WebSocket verbatim.

**The bridge layer does not parse JSON-RPC semantics** (it does not care about id / method / params); it forwards raw bytes,
so adding a language requires no changes to this file.

LSP framing format (base protocol)::

    Content-Length: <N>\r\n
    [Content-Type: ...]\r\n
    \r\n
    <N bytes of UTF-8 JSON>

The process pool is reused by ``(server_id, workspace_root)`` and reclaimed after an idle timeout.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from haijunbot.haijunbot_web_gateway.lsp_registry import get_lsp_server_spec

logger = logging.getLogger(__name__)

# Process idle reclaim timeout (seconds)
IDLE_TIMEOUT_SECONDS = 300.0

# Maximum size of a single LSP message body (guards against malformed/malicious Content-Length, 16 MiB)
MAX_MESSAGE_BYTES = 16 * 1024 * 1024


# ---------------------------------------------------------------------------
# LSP framing encode/decode
# ---------------------------------------------------------------------------


def encode_lsp_message(message: Dict[str, Any]) -> bytes:
    """Encode a JSON-RPC message into LSP-framed bytes.

    Args:
        message: A JSON-serializable dict

    Returns:
        ``b"Content-Length: N\\r\\n\\r\\n" + body``
    """
    body = json.dumps(message, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


class LspMessageDecoder:
    """Incremental LSP framing decoder.

    Used to handle streaming byte input: the caller continuously ``feed()``s newly arrived bytes, and the decoder handles
    **coalesced packets** (one feed containing multiple messages) and **partial packets** (one message spanning multiple feeds).

    Usage::

        decoder = LspMessageDecoder()
        for chunk in stream:
            for message in decoder.feed(chunk):
                handle(message)
    """

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> List[Dict[str, Any]]:
        """Feed new bytes and return all messages that can be fully parsed this time.

        Args:
            data: Newly arrived bytes (may be empty)

        Returns:
            The list of parsed messages (may be empty). When a message body cannot be parsed as JSON it is skipped with a warning,
            but this does not affect parsing of subsequent messages.
        """
        if data:
            self._buffer.extend(data)

        messages: List[Dict[str, Any]] = []

        while True:
            header_end = self._buffer.find(b"\r\n\r\n")
            if header_end == -1:
                # header not yet complete; wait for more data
                break

            header_bytes = bytes(self._buffer[:header_end])
            content_length = self._parse_content_length(header_bytes)

            if content_length is None:
                # Invalid header format: discard up to after the delimiter to avoid an infinite loop
                logger.warning(
                    "[lsp_bridge] Received an unparseable LSP header, discarded: %r",
                    header_bytes[:200],
                )
                del self._buffer[: header_end + 4]
                continue

            if content_length < 0 or content_length > MAX_MESSAGE_BYTES:
                logger.warning(
                    "[lsp_bridge] Invalid Content-Length=%s, discarded this message", content_length
                )
                del self._buffer[: header_end + 4]
                continue

            body_start = header_end + 4
            body_end = body_start + content_length
            if len(self._buffer) < body_end:
                # body not fully received (partial packet); wait for more data
                break

            body = bytes(self._buffer[body_start:body_end])
            del self._buffer[:body_end]

            try:
                message = json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning("[lsp_bridge] Failed to parse LSP message body JSON, skipped: %s", e)
                continue

            if isinstance(message, dict):
                messages.append(message)
            else:
                logger.warning("[lsp_bridge] LSP message body is not a JSON object, skipped")

        return messages

    @staticmethod
    def _parse_content_length(header_bytes: bytes) -> Optional[int]:
        """Parse Content-Length from the header; returns None when missing or invalid.

        Ignores extra header fields (e.g. Content-Type).
        """
        try:
            text = header_bytes.decode("ascii", errors="replace")
        except Exception:  # pragma: no cover - decode is already fault-tolerant
            return None

        for line in text.split("\r\n"):
            if ":" not in line:
                continue
            name, _, value = line.partition(":")
            if name.strip().lower() == "content-length":
                try:
                    return int(value.strip())
                except ValueError:
                    return None
        return None


# ---------------------------------------------------------------------------
# Process pool
# ---------------------------------------------------------------------------


class _LspProcess:
    """A language server subprocess and its read/write tasks."""

    def __init__(
        self,
        server_id: str,
        workspace_root: str,
        process: asyncio.subprocess.Process,
    ) -> None:
        self.server_id = server_id
        self.workspace_root = workspace_root
        self.process = process
        # The currently subscribed WebSocket send callback; None means no one is connected
        self.sender: Optional[Any] = None
        self.reader_task: Optional[asyncio.Task] = None
        self.stderr_task: Optional[asyncio.Task] = None
        self.idle_task: Optional[asyncio.Task] = None
        self.closed = False

    @property
    def key(self) -> Tuple[str, str]:
        return (self.server_id, self.workspace_root)

    def is_alive(self) -> bool:
        return not self.closed and self.process.returncode is None


class LspProcessPool:
    """Reuse language server processes by ``(server_id, workspace_root)``.

    - Multiple WS connections with the same key share the same process (the later one takes over the message subscription);
    - Starts an idle timer when there is no subscription, terminating the process after the timeout;
    - Cleans up the pool record when a process exits abnormally.
    """

    def __init__(self, idle_timeout: float = IDLE_TIMEOUT_SECONDS) -> None:
        self._idle_timeout = idle_timeout
        self._procs: Dict[Tuple[str, str], _LspProcess] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        server_id: str,
        workspace_root: str,
    ) -> _LspProcess:
        """Get (or create) the process for the specified key.

        Raises:
            RuntimeError: the spec does not exist or the process failed to start.
        """
        spec = get_lsp_server_spec(server_id)
        if spec is None:
            raise RuntimeError(f"unknown lsp server id: {server_id}")

        key = (server_id, workspace_root)

        async with self._lock:
            existing = self._procs.get(key)
            if existing is not None and existing.is_alive():
                return existing
            if existing is not None:
                # Dead process; clean up the record
                self._procs.pop(key, None)

            proc = await self._spawn(spec, workspace_root)
            self._procs[key] = proc
            return proc

    async def _spawn(self, spec: Dict[str, Any], workspace_root: str) -> _LspProcess:
        """Start the subprocess per the spec and attach the read tasks."""
        argv = list(spec.get("command") or []) + list(spec.get("args") or [])
        if not argv:
            raise RuntimeError(f"lsp server {spec.get('id')} has an empty command")

        env = dict(os.environ)
        # Let the language server know the workspace; some servers use it
        env.setdefault("PWD", workspace_root)

        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace_root if os.path.isdir(workspace_root) else None,
                env=env,
            )
        except FileNotFoundError as e:
            hint = spec.get("installHint") or ""
            raise RuntimeError(
                f"Language server not installed: {argv[0]}" + (f" ({hint})" if hint else "")
            ) from e
        except OSError as e:
            raise RuntimeError(f"Failed to start language server: {e}") from e

        logger.info(
            "[lsp_bridge] Starting language server server_id=%s pid=%s root=%s",
            spec.get("id"),
            process.pid,
            workspace_root,
        )

        proc = _LspProcess(spec.get("id", ""), workspace_root, process)
        proc.reader_task = asyncio.create_task(self._pump_stdout(proc))
        proc.stderr_task = asyncio.create_task(self._pump_stderr(proc))
        return proc

    async def _pump_stdout(self, proc: _LspProcess) -> None:
        """Continuously read the subprocess stdout and forward decoded messages to the current subscriber."""
        decoder = LspMessageDecoder()
        stream = proc.process.stdout
        assert stream is not None
        try:
            while True:
                chunk = await stream.read(65536)
                if not chunk:
                    break
                for message in decoder.feed(chunk):
                    sender = proc.sender
                    if sender is None:
                        continue
                    try:
                        result = sender(message)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.warning("[lsp_bridge] Failed to forward message to WS: %s", e)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("[lsp_bridge] Error reading language server stdout: %s", e)
        finally:
            logger.info(
                "[lsp_bridge] Language server stdout ended server_id=%s", proc.server_id
            )
            await self._on_process_gone(proc)

    async def _pump_stderr(self, proc: _LspProcess) -> None:
        """Continuously read the subprocess stderr and log it (to avoid the pipe filling up and blocking the subprocess)."""
        stream = proc.process.stderr
        assert stream is not None
        try:
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    logger.info("[lsp_bridge][%s stderr] %s", proc.server_id, text)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("[lsp_bridge] Error reading language server stderr: %s", e)

    async def _on_process_gone(self, proc: _LspProcess) -> None:
        """Remove from the pool and cancel background tasks when the process ends."""
        async with self._lock:
            if self._procs.get(proc.key) is proc:
                self._procs.pop(proc.key, None)
        proc.closed = True
        self._cancel_task(proc.stderr_task)
        self._cancel_task(proc.idle_task)

    async def send(self, proc: _LspProcess, message: Dict[str, Any]) -> None:
        """Write a message to the subprocess stdin."""
        stream = proc.process.stdin
        if stream is None or proc.process.returncode is not None:
            raise RuntimeError("Language server process has exited")
        stream.write(encode_lsp_message(message))
        try:
            await stream.drain()
        except (BrokenPipeError, ConnectionResetError) as e:
            raise RuntimeError("Language server process pipe has been closed") from e

    def subscribe(self, proc: _LspProcess, sender: Any) -> None:
        """Subscribe to process output and cancel the idle reclaim timer."""
        proc.sender = sender
        self._cancel_task(proc.idle_task)
        proc.idle_task = None

    def unsubscribe(self, proc: _LspProcess) -> None:
        """Unsubscribe and start the idle reclaim timer (the process is kept for reuse)."""
        if proc.sender is not None:
            proc.sender = None
        if proc.closed:
            return
        self._cancel_task(proc.idle_task)
        proc.idle_task = asyncio.create_task(self._idle_reaper(proc))

    async def _idle_reaper(self, proc: _LspProcess) -> None:
        """Terminate the process after the idle timeout."""
        try:
            await asyncio.sleep(self._idle_timeout)
        except asyncio.CancelledError:
            return

        if proc.sender is not None or proc.closed:
            return

        logger.info(
            "[lsp_bridge] Reclaiming idle language server server_id=%s root=%s",
            proc.server_id,
            proc.workspace_root,
        )
        await self.terminate(proc)

    async def terminate(self, proc: _LspProcess) -> None:
        """Terminate the process and clean up."""
        if proc.closed:
            return
        proc.closed = True
        async with self._lock:
            if self._procs.get(proc.key) is proc:
                self._procs.pop(proc.key, None)

        self._cancel_task(proc.idle_task)

        process = proc.process
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(
                    "[lsp_bridge] Language server did not respond to terminate, forcing kill pid=%s",
                    process.pid,
                )
                try:
                    process.kill()
                except ProcessLookupError:
                    pass

        self._cancel_task(proc.reader_task)
        self._cancel_task(proc.stderr_task)

    async def shutdown(self) -> None:
        """Shut down all processes (used on application exit)."""
        async with self._lock:
            procs = list(self._procs.values())
            self._procs.clear()
        await asyncio.gather(
            *(self.terminate(p) for p in procs), return_exceptions=True
        )

    @staticmethod
    def _cancel_task(task: Optional[asyncio.Task]) -> None:
        if task is not None and not task.done():
            task.cancel()


# ---------------------------------------------------------------------------
# workspace root resolution
# ---------------------------------------------------------------------------


def resolve_workspace_root(
    raw_root: Optional[str],
    spec: Dict[str, Any],
    fallback: Optional[str] = None,
) -> str:
    """Resolve and validate the workspace root.

    Starting from ``raw_root`` (passed by the frontend, usually the directory containing the file), **search upward** for
    the nearest ancestor directory containing ``rootMarkers`` as the project root; if no marker is found, fall back to the
    starting point itself, and finally to ``fallback`` or the current working directory.

    Why not use ``raw_root`` directly: the frontend passes the directory of the opened file; if used directly as the
    workspace root, the language server can only index that directory, and cross-file go-to-definition/reference fails (e.g.
    when ``src/haijunbot/haijunbot_sec/analysis.py`` references symbols from ``src/haijunbot/haijunbot_utils/``,
    taking ``haijunbot_sec`` as the workspace root means ``haijunbot_utils`` cannot be found). Searching upward for the project
    root lets the language server index the whole project, which is what makes cross-file semantics usable.

    Args:
        raw_root: The root passed by the frontend via query (search start point, usually the directory containing the file)
        spec: The language server spec
        fallback: A fallback start point (usually the directory containing the currently opened file)

    Returns:
        An absolute path string.
    """
    # Determine the search start point: raw_root (if it is an existing directory) takes priority, otherwise fallback
    start: Optional[Path] = None
    if raw_root:
        try:
            candidate = Path(raw_root).expanduser().resolve()
            if candidate.is_dir():
                start = candidate
        except (OSError, ValueError):
            pass

    if start is None and fallback:
        try:
            candidate = Path(fallback).expanduser().resolve()
            if candidate.is_file():
                candidate = candidate.parent
            start = candidate
        except (OSError, ValueError):
            pass

    if start is None:
        start = Path(os.getcwd())

    # Search upward from the start point for the nearest ancestor directory containing rootMarkers as the project root
    markers = spec.get("rootMarkers") or []
    if markers:
        for directory in [start, *start.parents]:
            for marker in markers:
                try:
                    if (directory / marker).exists():
                        return str(directory)
                except OSError:
                    continue

    return str(start)
