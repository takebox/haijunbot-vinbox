# -*- coding: utf-8 -*-
"""Real-time session saving daemon (daemon subprocess + pipe approach).

Background
----------
``save_session`` only persists to disk on commit/manual/task end, so when the Agent process is unexpectedly killed
(OOM/crash/manual kill), the most recent session is lost. This module provides "real-time saving + automatic recovery":

- When the main Agent starts, ``fork`` a daemon subprocess and send session snapshots to it through a pipe;
- The daemon subprocess keeps the latest snapshot in **memory** (not persisted, to avoid polluting the session directory);
- When the main Agent exits normally, it sends a "normal exit" control message; the daemon subprocess cleans up memory and exits,
  **without persisting** (the normal exit path is already handled by ``save_session``);
- When the main Agent is unexpectedly killed, the pipe write end closes; the daemon subprocess reads EOF, determines it is an
  unexpected exit, and persists the latest in-memory snapshot in the ``save_session`` format for the next recovery.

Design points
-------------
- The snapshot content is constructed by the **main process** (reusing ``SessionManager.build_session_snapshot``);
  the daemon subprocess is only responsible for "store in memory + write to disk", keeping the logic minimal.
- Persisting uses ``atomic_write_json``, fully consistent with ``save_session``, ensuring
  ``restore_session_from_file`` can restore directly.
- Enabled only for the main Agent (``allow_savesession=True``); Windows has no ``os.fork``,
  so it automatically degrades to disabled (without affecting existing functionality).
"""

import json
import os
import struct
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

# Pipe message types
_MSG_SNAPSHOT = b"S"  # Session snapshot (overwrite the latest snapshot in memory)
_MSG_QUIT = b"Q"  # Normal exit notification (clean up memory, do not persist)

# Length prefix: 8-byte unsigned big-endian integer
_LEN_FMT = ">Q"
_LEN_SIZE = struct.calcsize(_LEN_FMT)


class SessionDaemon:
    """Parent process side: manages the daemon subprocess and pipe communication.

    Enabled only when ``os.fork`` is available; otherwise ``start()`` returns False, all send
    operations become no-ops, and the Agent behavior falls back to "only save_session".
    """

    def __init__(self) -> None:
        self._pid: Optional[int] = None
        self._write_fd: Optional[int] = None
        self._enabled = hasattr(os, "fork")

    @property
    def enabled(self) -> bool:
        """Whether the daemon has been enabled and started successfully."""
        return self._pid is not None and self._write_fd is not None

    def start(self) -> bool:
        """Start the daemon subprocess.

        Returns:
            bool: Whether it started successfully (False on Windows or on exception).
        """
        if not self._enabled:
            return False
        if self.enabled:
            return True
        try:
            read_fd, write_fd = os.pipe()
            pid = os.fork()
            if pid == 0:
                # Child process: only responsible for reading the pipe + persisting, never returns to the parent context
                self._daemon_loop(read_fd, write_fd)
                # In theory _daemon_loop never returns; force an exit as a fallback to avoid executing
                # cleanup logic (atexit / __del__, etc.) inherited from the parent process
                os._exit(0)
            # Parent process: close the read end, keep the write end
            os.close(read_fd)
            self._pid = pid
            self._write_fd = write_fd
            return True
        except Exception:
            # On fork/pipe failure, degrade to disabled without affecting the main flow
            try:
                if self._write_fd is not None:
                    os.close(self._write_fd)
            except Exception:
                pass
            self._pid = None
            self._write_fd = None
            return False

    def send_snapshot(self, files: List[Dict[str, Any]]) -> bool:
        """Send a session snapshot to the daemon subprocess (overwriting the latest snapshot in its memory).

        Args:
            files: Persist plan, each item being
                {"path": str, "data": Any, "indent": Optional[int],
                 "use_safe_encoder": bool}

        Returns:
            bool: Whether it was sent successfully.
        """
        if not self.enabled:
            return False
        return self._send(_MSG_SNAPSHOT, {"files": files})

    def send_quit(self) -> None:
        """Notify the daemon subprocess of "normal exit", having it clean up memory without persisting.

        After sending, close the write end and reap the child process to avoid zombie processes.
        """
        if not self.enabled:
            return
        try:
            self._send(_MSG_QUIT, None)
        except Exception:
            pass
        self._close_and_reap()

    def _send(self, msg_type: bytes, payload: Optional[Dict[str, Any]]) -> bool:
        """Write a message to the pipe following the [type][length][JSON] protocol."""
        write_fd = self._write_fd
        if write_fd is None:
            return False
        try:
            if payload is None:
                body = b""
            else:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            frame = msg_type + struct.pack(_LEN_FMT, len(body)) + body
            os.write(write_fd, frame)
            return True
        except Exception:
            # The pipe is closed (the daemon may have exited); ignore
            return False

    def _close_and_reap(self) -> None:
        """Close the write end and reap the child process."""
        if self._write_fd is not None:
            try:
                os.close(self._write_fd)
            except Exception:
                pass
            self._write_fd = None
        if self._pid is not None:
            try:
                os.waitpid(self._pid, 0)
            except Exception:
                pass
            self._pid = None

    # ------------------------------------------------------------------
    # Daemon subprocess side
    # ------------------------------------------------------------------
    def _daemon_loop(self, read_fd: int, write_fd: int) -> None:
        """Daemon subprocess main loop: block reading the pipe; persist on EOF.

        Args:
            read_fd: Pipe read end
            write_fd: Pipe write end (the child process must close it first, otherwise EOF never triggers)
        """
        # The child process must close the write end, otherwise the pipe will not EOF after the parent exits
        try:
            os.close(write_fd)
        except Exception:
            pass

        latest_files: Optional[List[Dict[str, Any]]] = None
        normal_exit = False

        try:
            while True:
                msg_type = self._read_exact(read_fd, 1)
                if msg_type is None:
                    # EOF: the parent process (write end) has disappeared
                    break
                raw_len = self._read_exact(read_fd, _LEN_SIZE)
                if raw_len is None:
                    break
                body_len = struct.unpack(_LEN_FMT, raw_len)[0]
                body = self._read_exact(read_fd, body_len) if body_len else b""
                if body is None:
                    break

                if msg_type == _MSG_QUIT:
                    normal_exit = True
                    break
                if msg_type == _MSG_SNAPSHOT:
                    try:
                        payload = json.loads(body.decode("utf-8"))
                        files = payload.get("files")
                        if isinstance(files, list):
                            latest_files = files
                    except Exception:
                        # A single snapshot parse failure does not affect subsequent ones
                        pass
        except Exception:
            pass
        finally:
            try:
                os.close(read_fd)
            except Exception:
                pass

        # Normal exit: do not persist (the normal path is already persisted by save_session)
        if normal_exit or not latest_files:
            return

        # Unexpected exit: persist the latest in-memory snapshot
        self._write_files(latest_files)

    @staticmethod
    def _read_exact(fd: int, n: int) -> Optional[bytes]:
        """Read exactly n bytes from fd; return None on EOF."""
        chunks = []
        remaining = n
        while remaining > 0:
            try:
                chunk = os.read(fd, remaining)
            except OSError:
                return None
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    @staticmethod
    def _write_files(files: List[Dict[str, Any]]) -> None:
        """Atomically write the files in the snapshot to disk (consistent with the save_session format)."""
        # Lazy import, to avoid triggering heavy dependencies very early in the child process
        from haijunbot.haijunbot_utils.utils import atomic_write_json

        try:
            from haijunbot.haijunbot_agent import SafeEncoder

            safe_default = SafeEncoder().default
        except Exception:
            safe_default = None

        for item in files:
            try:
                path = item.get("path")
                if not path:
                    continue
                data = item.get("data")
                indent = item.get("indent")
                default = safe_default if item.get("use_safe_encoder") else None
                atomic_write_json(
                    path,
                    data,
                    indent=indent,
                    ensure_ascii=False,
                    default=default,
                )
            except Exception:
                # A single file write failure does not affect other files
                continue


def build_snapshot_files(
    session_file: str, files: List[Any]
) -> List[Dict[str, Any]]:
    """Convert the return value of ``build_session_snapshot`` into a JSON-transferable persist plan.

    Args:
        session_file: Main session file path (unused, kept for extension)
        files: ``[(path, data, default_encoder), ...]``

    Returns:
        [{"path":..., "data":..., "indent":..., "use_safe_encoder":...}, ...]
    """
    # The indentation of each file is kept consistent with save_session
    plan: List[Dict[str, Any]] = []
    for path, data, default in files:
        name = os.path.basename(path)
        if name.endswith("_state.json") or name.endswith("_tasklist.json"):
            indent: Optional[int] = 2
        else:
            indent = 4
        plan.append(
            {
                "path": path,
                "data": data,
                "indent": indent,
                "use_safe_encoder": default is not None,
            }
        )
    return plan
