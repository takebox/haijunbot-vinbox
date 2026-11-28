# -*- coding: utf-8 -*-
"""Standalone terminal session manager.

Manages standalone terminal sessions that are independent of execution, to implement tmux-like multi-tab terminal functionality.
"""

from __future__ import annotations


from haijunbot.haijunbot_utils.exception_utils import save_exception
import os
import shutil
from collections import deque
import subprocess
import threading
import uuid
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

# Platform-specific imports
if os.name == "nt":
    import queue as _queue
else:
    import fcntl
    import pty
    import select
    import struct
    import termios


@dataclass
class TerminalSession:
    """A single terminal session."""

    terminal_id: str
    interpreter: str
    working_dir: str
    master_fd: Optional[int] = None  # Unix only
    proc: Optional[subprocess.Popen] = None
    stream_publisher: Optional[Any] = None
    session_id: str = "default"
    owner_id: str = ""
    node_id: str = "master"
    access_acl: Dict[str, List[str]] = field(default_factory=dict)
    # Set of user session_ids that have attached to this session, used to push real-time output to
    # all authorized viewers (owner / ACL users / permitted admin users)
    attached_session_ids: set = field(default_factory=set)
    created_at: float = field(default_factory=lambda: __import__("time").time())
    _closed: bool = False
    _output_sequence: int = 0
    _sequence_lock: threading.Lock = field(default_factory=threading.Lock)
    # Output ring buffer (caches output during disconnects for replay after reconnect), capacity ~1MB
    _output_buffer: deque = field(default_factory=lambda: deque(maxlen=1024 * 1024))
    # Windows-specific fields
    _output_queue: Optional[Any] = field(default=None)  # queue.Queue on Windows
    _output_thread: Optional[threading.Thread] = field(default=None)

    def next_sequence(self) -> int:
        """Get the next output sequence number."""
        with self._sequence_lock:
            self._output_sequence += 1
            return self._output_sequence

    def close(self) -> None:
        """Close the terminal session."""
        with self._sequence_lock:
            if self._closed:
                return
            self._closed = True

        # Close the PTY (Unix)
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass

        # Terminate the process
        if self.proc is not None:
            try:
                if self.proc.poll() is None:
                    self.proc.terminate()
                    try:
                        self.proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self.proc.kill()
                        self.proc.wait()
            except Exception:
                try:
                    self.proc.kill()
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_web_gateway.terminal_session_manager",
                        function="close",
                    )
                    pass

    def is_closed(self) -> bool:
        """Check whether the session is closed."""
        with self._sequence_lock:
            if self._closed:
                return True
            return self.proc is not None and self.proc.poll() is not None

    def write_input(self, data: str) -> None:
        """Write input to the terminal."""
        if self.is_closed():
            return
        try:
            if os.name == "nt":
                # Windows: write to subprocess stdin
                if self.proc is not None and self.proc.stdin is not None:
                    self.proc.stdin.write(data.encode("utf-8", errors="ignore"))
                    self.proc.stdin.flush()
            else:
                # Unix: write to PTY master fd
                if self.master_fd is not None:
                    os.write(self.master_fd, data.encode("utf-8", errors="ignore"))
        except OSError:
            self.close()

    def resize(self, rows: int, cols: int) -> None:
        """Resize the terminal."""
        if self.is_closed():
            return
        if rows <= 0 or cols <= 0:
            return
        if os.name == "nt":
            # Windows: resize not supported via subprocess, no-op
            return
        try:
            if self.master_fd is not None:
                fcntl.ioctl(
                    self.master_fd,
                    termios.TIOCSWINSZ,
                    struct.pack("HHHH", rows, cols, 0, 0),
                )
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_web_gateway.terminal_session_manager",
                function="resize",
            )
            pass

    def _get_access_session_ids(self) -> List[str]:
        """Return the list of WebSocket session IDs authorized to receive this terminal's real-time output.

        Includes the owner and users shared (read/interact) with, so that real-time output can be pushed to
        all authorized users (not just the owner), fixing the issue where shared users could not see
        the terminal's real-time content.
        """
        ids: List[str] = []
        if self.owner_id:
            ids.append(f"session_{self.owner_id}")
        acl = self.access_acl or {}
        for uid in acl.get("interact", []) + acl.get("read", []):
            if uid and f"session_{uid}" not in ids:
                ids.append(f"session_{uid}")
        # Users who have attached to this session (including permitted admin users), so their real-time output is delivered too
        for sid in self.attached_session_ids:
            if sid and sid not in ids:
                ids.append(sid)
        # Compatible with child-node terminals: when owner_id is not passed at creation (empty), fall back to
        # self.session_id to avoid _get_access_session_ids being empty and leaving output unreceived
        # (manifesting as "only a tab and an empty xterm")
        if not ids and self.session_id and self.session_id != "default":
            ids.append(self.session_id)
        return ids

    def _publish_output(self, data: bytes) -> None:
        """Publish terminal output to WebSocket."""
        if self.stream_publisher is None:
            print(
                f"[TerminalSession {self.terminal_id}] No stream publisher, skipping output"
            )
            return

        # Write to the output ring buffer for replay after disconnect/reconnect
        self._output_buffer.append(data)

        try:
            # Base64-encode the data so it can be serialized to JSON
            import base64

            encoded_data = base64.b64encode(data).decode("utf-8")

            # Build the WebSocket message format expected by the frontend
            # Directly send the {type: "execution", payload: {...}} format
            payload = {
                "event_type": "stdout",  # event_type expected by the frontend
                "data": encoded_data,  # base64-encoded output data (string)
                "encoded": True,
                "sequence": self.next_sequence(),
                "execution_id": f"terminal_{self.terminal_id}",
            }
            message = {"type": "execution", "payload": payload}
            print(
                f"[TerminalSession {self.terminal_id}] Publishing output: type={message['type']}, exec_id={payload['execution_id']}, data_len={len(data)}"
            )
            # Push to the owner and users shared (read/interact) with, so that all authorized users
            # can receive real-time output (not just the owner's session_id)
            for sid in self._get_access_session_ids():
                self.stream_publisher.publish(message, session_id=sid)
        except Exception as e:
            print(f"[TerminalSession {self.terminal_id}] Failed to publish output: {e}")

    def get_output_buffer(self) -> List[bytes]:
        """Get all data in the output ring buffer (in chronological order).

        Used to replay output after a disconnect/reconnect. Returns a raw bytes list; the caller must
        base64-encode it and send it in the format expected by the frontend.
        """
        with self._sequence_lock:
            return list(self._output_buffer)


class TerminalSessionManager:
    """Standalone terminal session manager."""

    def __init__(self, max_sessions: Optional[int] = None):
        self._max_sessions = max_sessions
        self._lock = threading.RLock()
        self._sessions: Dict[str, TerminalSession] = {}
        self._closing_sessions: set[str] = set()  # IDs of sessions being closed, preventing duplicate calls

    def create_session(
        self,
        interpreter: str = "bash",
        working_dir: str = ".",
        stream_publisher: Optional[Any] = None,
        session_id: str = "default",
        owner_id: str = "",
    ) -> Tuple[Optional[str], Optional[str]]:
        """Create a new terminal session.

        Args:
            interpreter: Interpreter path (bash, python, etc.)
            working_dir: Working directory
            stream_publisher: Stream output publisher
            session_id: WebSocket session ID
            owner_id: Owner user ID of the session

        Returns:
            (terminal_id, error_message)
        """
        with self._lock:
            # Check the session count limit
            if (
                self._max_sessions is not None
                and len(self._sessions) >= self._max_sessions
            ):
                return None, f"Maximum terminal session limit reached ({self._max_sessions})"

            # Generate terminal_id
            terminal_id = str(uuid.uuid4())[:8]

            try:
                # Check whether the interpreter exists
                if not shutil.which(interpreter):
                    # Vinbox hanya memakai pwsh; tidak pernah jatuh ke cmd.exe/bash.
                    from haijunbot.haijunbot_utils.vinbox_runtime import shell_path

                    interpreter = shell_path()
                    print(
                        f"[TerminalSessionManager] Interpreter not found, using pwsh: {interpreter}"
                    )

                # Set the working directory
                if not os.path.isabs(working_dir):
                    working_dir = os.path.abspath(working_dir)

                if os.name == "nt":
                    return self._create_session_windows(
                        terminal_id,
                        interpreter,
                        working_dir,
                        stream_publisher,
                        session_id,
                        owner_id,
                    )
                else:
                    return self._create_session_unix(
                        terminal_id,
                        interpreter,
                        working_dir,
                        stream_publisher,
                        session_id,
                        owner_id,
                    )

            except Exception as e:
                return None, f"Failed to create terminal: {str(e)}"

    def _create_session_unix(
        self,
        terminal_id: str,
        interpreter: str,
        working_dir: str,
        stream_publisher: Optional[Any],
        session_id: str,
        owner_id: str = "",
    ) -> Tuple[Optional[str], Optional[str]]:
        """Unix/Linux: create a terminal session using a PTY."""
        master_fd, slave_fd = pty.openpty()

        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        if interpreter in ("python", "python2", "python3"):
            env["PYTHONIOENCODING"] = "utf-8"

        # Vinbox hanya memakai pwsh. Fish/bash/zsh bukan shell Vinbox, jadi tidak
        # ada pembungkus "bash -c exec ..." di sini.
        cmd = [interpreter]
        if os.path.basename(interpreter).lower().startswith("pwsh"):
            cmd += ["-NoLogo", "-NoProfile"]
        actual_interpreter = interpreter

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=working_dir,
                env=env,
                preexec_fn=os.setsid,
            )

            os.close(slave_fd)

            session = TerminalSession(
                terminal_id=terminal_id,
                interpreter=actual_interpreter,
                working_dir=working_dir,
                master_fd=master_fd,
                proc=proc,
                stream_publisher=stream_publisher,
                session_id=session_id,
                owner_id=owner_id,
            )

            self._sessions[terminal_id] = session

            thread = threading.Thread(
                target=self._read_output_unix,
                args=(session,),
                daemon=True,
                name=f"terminal-{terminal_id}",
            )
            thread.start()

            return terminal_id, None

        except Exception as e:
            try:
                os.close(master_fd)
            except Exception as inner_e:
                save_exception(
                    inner_e,
                    module="haijunbot_web_gateway.terminal_session_manager",
                    function="_create_session_unix",
                )
                pass
            try:
                os.close(slave_fd)
            except Exception as inner_e:
                save_exception(
                    inner_e,
                    module="haijunbot_web_gateway.terminal_session_manager",
                    function="_create_session_unix",
                )
                pass
            return None, f"Failed to create terminal: {str(e)}"

    def _create_session_windows(
        self,
        terminal_id: str,
        interpreter: str,
        working_dir: str,
        stream_publisher: Optional[Any],
        session_id: str,
        owner_id: str = "",
    ) -> Tuple[Optional[str], Optional[str]]:
        """Windows: create a terminal session using subprocess + pipe."""
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"

        try:
            proc = subprocess.Popen(
                [interpreter],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=working_dir,
                env=env,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )

            output_queue = _queue.Queue()

            session = TerminalSession(
                terminal_id=terminal_id,
                interpreter=interpreter,
                working_dir=working_dir,
                master_fd=None,
                proc=proc,
                stream_publisher=stream_publisher,
                session_id=session_id,
                owner_id=owner_id,
                _output_queue=output_queue,
            )

            self._sessions[terminal_id] = session

            # Start the output reading thread
            def read_output() -> None:
                while not session.is_closed():
                    try:
                        if proc.stdout is None:
                            break
                        data = proc.stdout.read(4096)
                        if not data:
                            break
                        output_queue.put(data)
                    except Exception:
                        break

            output_thread = threading.Thread(
                target=read_output,
                daemon=True,
                name=f"terminal-reader-{terminal_id}",
            )
            output_thread.start()
            session._output_thread = output_thread

            # Start the publishing thread
            publish_thread = threading.Thread(
                target=self._read_output_windows,
                args=(session,),
                daemon=True,
                name=f"terminal-pub-{terminal_id}",
            )
            publish_thread.start()

            return terminal_id, None

        except Exception as e:
            return None, f"Failed to create terminal: {str(e)}"

    def _read_output_unix(self, session: TerminalSession) -> None:
        """Unix/Linux: thread function that reads PTY output."""
        assert session.master_fd is not None, "master_fd must be set for Unix sessions"
        print(
            f"[TerminalSessionManager] Starting output reader for terminal {session.terminal_id}"
        )
        output_count = 0
        while not session.is_closed():
            try:
                # Use select to wait for data
                ready, _, _ = select.select([session.master_fd], [], [], 0.1)
                if not ready:
                    continue

                # Read the data
                data = os.read(session.master_fd, 4096)
                if not data:
                    print(
                        f"[TerminalSessionManager] EOF on terminal {session.terminal_id}"
                    )
                    break

                output_count += 1
                print(
                    f"[TerminalSessionManager] Read chunk {output_count} ({len(data)} bytes) from terminal {session.terminal_id}"
                )
                print(f"[TerminalSessionManager] Data preview: {data[:100]!r}")
                # Publish the output
                session._publish_output(data)

            except OSError as e:
                print(
                    f"[TerminalSessionManager] OSError on terminal {session.terminal_id}: {e}"
                )
                break
            except Exception as e:
                print(
                    f"[TerminalSessionManager] Exception on terminal {session.terminal_id}: {e}"
                )
                break
        print(
            f"[TerminalSessionManager] Output reader stopped for terminal {session.terminal_id}"
        )

        # Check the process exit status
        if session.proc is not None:
            return_code = session.proc.poll()
            print(f"[TerminalSessionManager] Process exit code: {return_code}")

        # Process finished; clean up the session
        self.close_session(session.terminal_id)

    def _read_output_windows(self, session: TerminalSession) -> None:
        """Windows: read output from the queue and publish it to WebSocket."""
        assert session._output_queue is not None, (
            "output_queue must be set for Windows sessions"
        )
        print(
            f"[TerminalSessionManager] Starting Windows output publisher for terminal {session.terminal_id}"
        )
        while not session.is_closed():
            try:
                data = session._output_queue.get(timeout=0.1)
                if data:
                    session._publish_output(data)
            except Exception:  # queue.Empty or timeout
                continue
        print(
            f"[TerminalSessionManager] Windows output publisher stopped for terminal {session.terminal_id}"
        )

        # Check the process exit status
        if session.proc is not None:
            return_code = session.proc.poll()
            print(f"[TerminalSessionManager] Process exit code: {return_code}")

        # Process finished; clean up the session
        self.close_session(session.terminal_id)

    def write_input(self, terminal_id: str, data: str) -> bool:
        """Write input to the terminal.

        Args:
            terminal_id: Terminal ID
            data: Input data

        Returns:
            Whether it succeeded
        """
        with self._lock:
            session = self._sessions.get(terminal_id)
            if session is None:
                return False
            session.write_input(data)
            return True

    def resize(self, terminal_id: str, rows: int, cols: int) -> bool:
        """Resize the terminal.

        Args:
            terminal_id: Terminal ID
            rows: Number of rows
            cols: Number of columns

        Returns:
            Whether it succeeded
        """
        with self._lock:
            session = self._sessions.get(terminal_id)
            if session is None:
                return False
            session.resize(rows, cols)
            return True

    def close_session(self, terminal_id: str) -> bool:
        """Close the terminal session.

        Args:
            terminal_id: Terminal ID

        Returns:
            Whether it succeeded
        """
        with self._lock:
            # Check whether it is already being closed (to prevent duplicate calls)
            if terminal_id in self._closing_sessions:
                return False

            session = self._sessions.pop(terminal_id, None)
            if session is None:
                # The session does not exist; remove it from the closing set
                self._closing_sessions.discard(terminal_id)
                return False

            # Mark it as closing
            self._closing_sessions.add(terminal_id)

            # Send the terminal_closed message to notify the frontend
            if session.stream_publisher is not None:
                try:
                    message = {
                        "type": "terminal_closed",
                        "payload": {
                            "terminal_id": terminal_id,
                        },
                    }
                    print(
                        f"[TerminalSessionManager] Sending terminal_closed for {terminal_id}"
                    )
                    session.stream_publisher.publish(
                        message, session_id=session.session_id
                    )
                except Exception as e:
                    print(
                        f"[TerminalSessionManager] Failed to send terminal_closed: {e}"
                    )

            session.close()

            # Remove it from the closing set
            self._closing_sessions.discard(terminal_id)
            return True

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active terminal sessions.

        Returns:
            List of session information
        """
        with self._lock:
            sessions = []
            for terminal_id, session in self._sessions.items():
                sessions.append(
                    {
                        "terminal_id": terminal_id,
                        "interpreter": session.interpreter,
                        "working_dir": session.working_dir,
                        "is_closed": session.is_closed(),
                    }
                )
            return sessions

    def list_sessions_for_user(self, session_id: str) -> List[Dict[str, Any]]:
        """List active terminal sessions accessible to the specified user (WebSocket session ID).

        Returns sessions owned by the user + sessions shared with the user (with the access level).

        Args:
            session_id: WebSocket session ID (i.e. the user identifier)

        Returns:
            List of session information, including ownership and access info such as session_id/created_at/access
        """
        with self._lock:
            sessions = []
            for terminal_id, session in self._sessions.items():
                access = self._access_level(session, session_id)
                if access is None:
                    continue
                sessions.append(
                    {
                        "terminal_id": terminal_id,
                        "interpreter": session.interpreter,
                        "working_dir": session.working_dir,
                        "is_closed": session.is_closed(),
                        "session_id": session.session_id,
                        "created_at": session.created_at,
                        "owner_id": session.owner_id,
                        "node_id": session.node_id,
                        "access": access,
                        "access_acl": session.access_acl or {},
                    }
                )
            return sessions

    def _access_level(self, session: TerminalSession, user_id: str) -> Optional[str]:
        """Compute the user's access level for the session.

        Compatible with session IDs in the ``session_{user_id}`` format, automatically extracting the real user_id for matching;
        system and admin users are treated as owner.

        Returns:
            "owner" / "interact" / "read" / None (no access permission)
        """
        # Compatible with the session_{user_id} format; extract the real user_id
        if user_id and user_id.startswith("session_"):
            user_id = user_id[len("session_") :]
        if not user_id:
            return None
        # Allow system users
        if user_id == "system":
            return "owner"
        # Allow admin users
        if self._is_admin_user(user_id):
            return "owner"
        if session.owner_id and user_id == session.owner_id:
            return "owner"
        acl = session.access_acl or {}
        if user_id in acl.get("interact", []):
            return "interact"
        if user_id in acl.get("read", []):
            return "read"
        return None

    def _is_admin_user(self, user_id: str) -> bool:
        """Check whether the user is an admin (queried via UserManager)."""
        try:
            from haijunbot.haijunbot_utils.config import get_data_dir
            from haijunbot.haijunbot_web_gateway.user_manager import UserManager

            user_mgr = UserManager(get_data_dir())
            user = user_mgr.get_user(user_id)
            return bool(user and user.get("is_admin"))
        except Exception:
            return False

    def get_all_admin_session_ids(self) -> List[str]:
        """Return the list of WebSocket session_ids of all admin users.

        Used for terminal create/close event broadcasting: admin users are allowed by _access_level (treated as
        owner) and can see all terminals, so terminal events should be pushed in real time to all online admin users,
        allowing other devices (administrators) to see new terminals appear/close in real time.
        """
        try:
            from haijunbot.haijunbot_utils.config import get_data_dir
            from haijunbot.haijunbot_web_gateway.user_manager import UserManager

            user_mgr = UserManager(get_data_dir())
            sids: List[str] = []
            for u in user_mgr.list_users(limit=100000):
                if u.get("is_admin"):
                    uid = u.get("user_id")
                    if uid:
                        sids.append(f"session_{uid}")
            return sids
        except Exception:
            return []

    def _get_admin_user_id(self) -> Optional[str]:
        """Get the admin user's user_id (used for set_access_acl filtering)."""
        try:
            from haijunbot.haijunbot_utils.config import get_data_dir
            from haijunbot.haijunbot_web_gateway.user_manager import UserManager

            user_mgr = UserManager(get_data_dir())
            admin_user = user_mgr.get_user_by_username("admin")
            return admin_user["user_id"] if admin_user else None
        except Exception:
            return None

    def attach_session(self, terminal_id: str, session_id: str) -> Optional[str]:
        """Attach/associate the terminal session to the specified user (WebSocket session ID).

        Verifies session ownership: attaching is allowed only when the session belongs to the user (owner) or is shared
        with the user (read/interact), preventing unauthorized access to other users' sessions.

        Args:
            terminal_id: Terminal ID
            session_id: WebSocket session ID (i.e. the user identifier, may be in the session_{user_id} format)

        Returns:
            Access level string ("owner"/"interact"/"read"); None when there is no permission or it does not exist
        """
        with self._lock:
            session = self._sessions.get(terminal_id)
            if session is None:
                return None
            access = self._access_level(session, session_id)
            if access is not None:
                # Record users who have attached to this session, so that _get_access_session_ids can
                # push real-time output to all authorized viewers (including permitted admin users)
                session.attached_session_ids.add(session_id)
            return access

    def check_access(
        self, terminal_id: str, user_id: str, need_interact: bool
    ) -> Optional[str]:
        """Verify the user's access level for the session.

        Args:
            terminal_id: Terminal ID
            user_id: User ID
            need_interact: Whether an interaction level is required (compatibility parameter; the return value is the actual access level)

        Returns:
            Access level string ("owner"/"interact"/"read"); None when there is no permission or it does not exist
        """
        with self._lock:
            session = self._sessions.get(terminal_id)
            if session is None:
                return None
            return self._access_level(session, user_id)

    def set_access_acl(
        self, terminal_id: str, owner_id: str, acl: Dict[str, List[str]]
    ) -> bool:
        """Set the session's access control list (only the owner can operate).

        Automatically filters out the owner and admin users (these two users have full control over the session).

        Args:
            terminal_id: Terminal ID
            owner_id: Operating user ID (must be the session owner)
            acl: Access control list {read: [...], interact: [...]}

        Returns:
            Whether it was set successfully
        """
        with self._lock:
            session = self._sessions.get(terminal_id)
            if session is None:
                return False
            if not session.owner_id or session.owner_id != owner_id:
                return False
            # Filter out the owner and admin users, and deduplicate
            admin_user_id = self._get_admin_user_id()
            normalized = {"read": [], "interact": []}
            for level in ("read", "interact"):
                users = acl.get(level, []) or []
                seen = set()
                for u in users:
                    if not u or u == session.owner_id or u in seen:
                        continue
                    if admin_user_id and u == admin_user_id:
                        continue
                    seen.add(u)
                    normalized[level].append(u)
            session.access_acl = normalized
            return True

    def register_remote_session(
        self,
        terminal_id: str,
        node_id: str,
        owner_id: str = "",
        session_id: str = "default",
        interpreter: str = "bash",
        working_dir: str = ".",
    ) -> None:
        """Register the metadata of a remote (child node) terminal session (a shadow session).

        The child node terminal's actual session lives on the child node; the master does not hold a real PTY.
        Here the master registers a PTY-less shadow session so that list_sessions_for_user
        can return child node terminals (for frontend synchronized restoration), while keeping ACL decisions on the master.

        Args:
            terminal_id: Terminal ID
            node_id: ID of the node where the terminal lives
            owner_id: Creator user ID
            session_id: The creator's WebSocket session ID
            interpreter: Interpreter
            working_dir: Working directory
        """
        with self._lock:
            if terminal_id in self._sessions:
                return
            self._sessions[terminal_id] = TerminalSession(
                terminal_id=terminal_id,
                interpreter=interpreter,
                working_dir=working_dir,
                session_id=session_id,
                owner_id=owner_id,
                node_id=node_id,
            )

    def unregister_session(self, terminal_id: str) -> None:
        """Remove a session (used to clean up shadow sessions when child node terminals close)."""
        with self._lock:
            self._sessions.pop(terminal_id, None)

    def get_session_info(self, terminal_id: str) -> Optional[Dict[str, Any]]:
        """Get session information (including owner and ACL).

        Args:
            terminal_id: Terminal ID

        Returns:
            Session information dict, or None
        """
        with self._lock:
            session = self._sessions.get(terminal_id)
            if session is None:
                return None
            return {
                "terminal_id": terminal_id,
                "interpreter": session.interpreter,
                "working_dir": session.working_dir,
                "is_closed": session.is_closed(),
                "session_id": session.session_id,
                "created_at": session.created_at,
                "owner_id": session.owner_id,
                "node_id": session.node_id,
                "access_acl": session.access_acl or {},
            }

    def get_session(self, terminal_id: str) -> Optional[TerminalSession]:
        """Get the terminal session.

        Args:
            terminal_id: Terminal ID

        Returns:
            Session object, or None
        """
        with self._lock:
            return self._sessions.get(terminal_id)

    def cleanup(self) -> None:
        """Clean up all sessions."""
        with self._lock:
            for session in self._sessions.values():
                session.close()
            self._sessions.clear()
