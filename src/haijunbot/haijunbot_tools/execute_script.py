# -*- coding: utf-8 -*-
import base64
import os
import re
import select
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime
from datetime import timezone
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import cast
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from haijunbot.haijunbot_utils.globals import clear_script_pid
from haijunbot.haijunbot_utils.globals import get_interrupt
from haijunbot.haijunbot_utils.globals import set_interrupt
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.globals import set_script_pid
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils import vinbox_runtime

# Match ANSI/terminal escape sequences
# CSI: ^[[?61;4;6;7;...c (terminal capability query response)
# OSC: ^[]0;253971765/49760;C:\...\powershell.EXE (window title/process info etc., which gets mixed into output)
_ANSI_ESCAPE = re.compile(
    r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)?)"
)
# Windows ConPTY sometimes outputs only the OSC payload while ESC is swallowed, causing mixing:
# Format 1: 0;pid/pid;C:\path\exe.EXE
# Format 2: 0;C:\path\exe.EXE (pid/pid part missing)
# Format 3: 0;pid/pid (only process info, no path)
_OSC_PAYLOAD_ORPHAN = re.compile(
    r"^\s*0;(?:\d+/\d+;?)?(?:[^\n\r]*\.(?:EXE|exe|ps1|bat|cmd|py)\s*)?\s*"
)


class ExecutionStreamPublisher(ABC):
    """Abstract script execution stream message publisher."""

    @abstractmethod
    def publish(
        self, message: Dict[str, Any], session_id: Optional[str] = None
    ) -> None:
        raise NotImplementedError


class NullExecutionStreamPublisher(ExecutionStreamPublisher):
    """Default null publisher, preserves original behavior."""

    def publish(
        self, message: Dict[str, Any], session_id: Optional[str] = None
    ) -> None:
        del message, session_id


class GatewayExecutionStreamPublisher(ExecutionStreamPublisher):
    """Forward execution stream events to the Gateway."""

    def __init__(self, gateway: Any) -> None:
        self._gateway = gateway

    def publish(
        self, message: Dict[str, Any], session_id: Optional[str] = None
    ) -> None:
        if self._gateway is None:
            return
        try:
            from haijunbot.haijunbot_gateway.events import GatewayExecutionEvent
        except Exception:
            return

        event_type = (
            message.get("message_type") or message.get("type") or "execution_event"
        )
        try:
            event = GatewayExecutionEvent(
                event_type=str(event_type),
                payload=dict(message),
                timestamp=message.get("timestamp"),
            )
            self._gateway.publish_execution_event(event, session_id=session_id)
        except Exception:
            return


@dataclass(frozen=True)
class ExecutionRequest:
    interpreter: str
    script_content: str
    execution_mode: str
    session_id: Optional[str] = None
    stream_publisher: Optional[ExecutionStreamPublisher] = None
    execution_id: Optional[str] = None
    input_callback: Optional[Callable[[float], Optional[str]]] = None
    resize_callback: Optional[Callable[[], Optional[Tuple[int, int]]]] = None


class ExecutionBackend(ABC):
    """Abstract script execution backend."""

    @abstractmethod
    def execute(self, tool: Any, request: ExecutionRequest) -> Dict[str, Any]:
        raise NotImplementedError


class CapturedExecutionBackend(ExecutionBackend):
    """Standard result mode backend, preserves the existing stdout/stderr return structure."""

    def execute(self, tool: Any, request: ExecutionRequest) -> Dict[str, Any]:
        return cast(Dict[str, Any], tool._execute_script_captured(request))


class VirtualTTYExecutionBackend(ExecutionBackend):
    """Interactive stream/TTY mode backend."""

    def execute(self, tool: Any, request: ExecutionRequest) -> Dict[str, Any]:
        return cast(Dict[str, Any], tool._execute_script_interactive(request))


class ScriptTool:
    """Combined script execution tool

    Executes scripts with any interpreter with a unified interface.
    """

    name = "execute_script"
    description = "Execute a script in the specified interpreter/terminal and return the result. Default interpreter: bash on Unix, powershell on Windows. Output may be long; proactively filter with grep/Select-String and limit lines with head/tail to avoid blowing up the context in one go.\n\nCommon usage (Unix):\n• Debug: script_content='grep -i \"error\" app.log'\n• View first N lines: script_content='head -n 30 large_file.txt'\n• Run Python: interpreter='python', script_content='print(1+1)'\n\nWindows debugging: interpreter='powershell', script_content='Select-String -Pattern \"error\" app.log'"
    parameters = {
        "type": "object",
        "properties": {
            "interpreter": {
                "type": "string",
                "description": "Script interpreter. On Windows, powershell or python is recommended; on Unix, bash or python3.",
            },
            "script_content": {
                "type": "string",
                "description": "Script content to execute. Mind the output volume: prefer grep/head/tail or command pipelines to limit lines and avoid long output blowing up the context.",
            },
            "execution_mode": {
                "type": "string",
                "enum": ["auto", "captured", "interactive"],
                "description": "Execution mode (optional, default auto): captured=capture output and return; interactive=keep the terminal for user interaction (suitable for programs needing stdin, e.g. debuggers); auto=automatically choose based on whether currently non-interactive. Usually the default is fine; no need to fill in.",
            },
        },
        "required": ["script_content"],
    }

    # Map of common file extensions for interpreters (can be extended as needed)
    INTERPRETER_EXTENSIONS = {
        "bash": "sh",
        "sh": "sh",
        "python": "py",
        "python2": "py",
        "python3": "py",
        "perl": "pl",
        "ruby": "rb",
        "node": "js",
        "nodejs": "js",
        "php": "php",
        "powershell": "ps1",
        "pwsh": "ps1",
        "cmd": "bat",
        "R": "r",
        "Rscript": "r",
        "julia": "jl",
        "lua": "lua",
        "go": "go",
        "awk": "awk",
        "kotlin": "kt",
        "java": "java",
        "javac": "java",
        "scala": "scala",
        "swift": "swift",
        "gcc": "c",
        "g++": "cpp",
    }

    @staticmethod
    def _is_windows() -> bool:
        """Detect whether this is a Windows system (Windows has no script command)"""
        return sys.platform == "win32"

    @staticmethod
    def _is_macos() -> bool:
        """Detect whether this is a macOS system (macOS script command syntax differs from Linux)"""
        return sys.platform == "darwin"

    def _get_windows_command(
        self, interpreter: str, script_path: str, extension: str
    ) -> List[str]:
        """Build the execution command on Windows; PowerShell needs -ExecutionPolicy Bypass"""
        if interpreter in ("powershell", "pwsh"):
            return [
                interpreter,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script_path,
            ]
        if interpreter == "cmd" and extension == "bat":
            return ["cmd", "/c", script_path]
        if interpreter in ("python", "python2", "python3"):
            return [interpreter, "-u", script_path]  # -u: unbuffered output
        return [interpreter, script_path]

    @staticmethod
    def _decode_windows_output(data: bytes) -> str:
        """Decode subprocess output on Windows. Python scripts output UTF-8 via PYTHONIOENCODING=utf-8,
        others (like PowerShell) may use the console encoding (GBK). Try UTF-8 first to display Chinese correctly."""
        if not data:
            return ""
        from haijunbot.haijunbot_utils.config import get_default_encoding

        # Prefer UTF-8: Python script stdout is UTF-8 in this mode
        for enc in ("utf-8", get_default_encoding(), "cp936"):
            try:
                return data.decode(enc)
            except (UnicodeDecodeError, LookupError, ValueError):
                continue
        return data.decode("latin-1", errors="replace")

    @staticmethod
    def _strip_ansi(text: str) -> str:
        """Remove ANSI/terminal escape sequences and Windows ConPTY OSC residue (e.g., 0;pid/pid;C:\\path\\exe.EXE)"""
        s = _ANSI_ESCAPE.sub("", text)
        s = _OSC_PAYLOAD_ORPHAN.sub("", s)
        return s

    @staticmethod
    def _get_event_timestamp() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _publish_stream_message(
        self,
        publisher: Optional[ExecutionStreamPublisher],
        chunk: Union[bytes, str],
        *,
        stream: str,
        session_id: Optional[str],
        execution_id: Optional[str] = None,
        sequence: Optional[int] = None,
    ) -> None:
        if not publisher or not chunk:
            return
        # Use base64 encoding to transmit binary data
        # Supports both bytes and str input
        if isinstance(chunk, str):
            chunk_bytes = chunk.encode("utf-8", errors="replace")
        else:
            chunk_bytes = chunk
        chunk_b64 = base64.b64encode(chunk_bytes).decode("utf-8")
        publisher.publish(
            {
                "type": "tool_stream",
                "message_type": "tool_stream",
                "tool": self.name,
                "stream": stream,
                "chunk": chunk_b64,
                "encoded": True,  # Mark data as encoded
                "execution_id": execution_id,
                "sequence": sequence,
                "timestamp": self._get_event_timestamp(),
            },
            session_id=session_id,
        )

    def _publish_execution_event(
        self,
        publisher: Optional[ExecutionStreamPublisher],
        *,
        message_type: str,
        session_id: Optional[str],
        execution_id: Optional[str],
        stream: str = "tty",
        chunk: str = "",
        sequence: Optional[int] = None,
        exit_code: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> None:
        if not publisher:
            return
        publisher.publish(
            {
                "type": message_type,
                "message_type": message_type,
                "tool": self.name,
                "stream": stream,
                "chunk": chunk,
                "execution_id": execution_id,
                "sequence": sequence,
                "exit_code": exit_code,
                "reason": reason,
                "timestamp": self._get_event_timestamp(),
            },
            session_id=session_id,
        )

    def _execute_on_windows_interactive_pty(
        self,
        argv: List[str],
        env: Dict[str, str],
        get_timeout: Any,
        stream_publisher: Optional[ExecutionStreamPublisher] = None,
        session_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        input_callback: Optional[Callable[[float], Optional[str]]] = None,
        resize_callback: Optional[Callable[[], Optional[Tuple[int, int]]]] = None,
    ) -> Dict[str, Any]:
        """Implemented with pywinpty (ConPTY): user can interact + output can be captured, similar to the Unix script command"""
        from winpty import PtyProcess

        captured: List[str] = []
        capture_lock = threading.Lock()
        read_done = threading.Event()
        exc_holder: List[BaseException] = []
        sequence_lock = threading.Lock()
        sequence = 0

        def next_sequence() -> int:
            nonlocal sequence
            with sequence_lock:
                sequence += 1
                return sequence

        def publish_input_chunk(chunk: str) -> None:
            if not chunk:
                return
            proc.write(chunk)
            self._publish_execution_event(
                stream_publisher,
                message_type="tool_input",
                session_id=session_id,
                execution_id=execution_id,
                stream="stdin",
                chunk=chunk,
                sequence=next_sequence(),
            )

        def apply_resize(rows: int, cols: int) -> None:
            if rows <= 0 or cols <= 0:
                return
            set_size = getattr(proc, "set_size", None)
            if not callable(set_size):
                return
            try:
                set_size(cols, rows)
            except TypeError:
                try:
                    set_size(rows, cols)
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_tools.execute_script", function="apply_resize"
                    )
                    pass
            except Exception as e:
                save_exception(
                    e, module="haijunbot_tools.execute_script", function="apply_resize"
                )
                pass

        def poll_resize() -> None:
            if resize_callback is None:
                return
            try:
                size = resize_callback()
            except Exception as exc:
                exc_holder.append(exc)
                return
            if not size:
                return
            rows, cols = size
            apply_resize(rows, cols)

        def reader(pty_proc: Any) -> None:
            try:
                while pty_proc.isalive():
                    # Check whether an interrupt signal was received
                    if get_interrupt() > 0:
                        break
                    poll_resize()
                    try:
                        data = pty_proc.read(4096)
                        if data:
                            raw_text = self._decode_windows_output(
                                data if isinstance(data, bytes) else data.encode()
                            )
                            if not raw_text:
                                continue
                            display_text = self._strip_ansi(raw_text)
                            if display_text:
                                with capture_lock:
                                    captured.append(display_text)
                            self._publish_stream_message(
                                stream_publisher,
                                raw_text,
                                stream="stdout",
                                session_id=session_id,
                                execution_id=execution_id,
                                sequence=next_sequence(),
                            )
                            sys.stdout.write(raw_text)
                            sys.stdout.flush()
                    except (EOFError, OSError):
                        break
                for _ in range(3):
                    try:
                        remaining_data = pty_proc.read(4096)
                        if remaining_data:
                            raw_text = self._decode_windows_output(
                                remaining_data
                                if isinstance(remaining_data, bytes)
                                else remaining_data.encode()
                            )
                            display_text = self._strip_ansi(raw_text)
                            if display_text.strip():
                                with capture_lock:
                                    captured.append(display_text)
                            if raw_text:
                                self._publish_stream_message(
                                    stream_publisher,
                                    raw_text,
                                    stream="stdout",
                                    session_id=session_id,
                                    execution_id=execution_id,
                                    sequence=next_sequence(),
                                )
                                sys.stdout.write(raw_text)
                                sys.stdout.flush()
                        else:
                            break
                    except (EOFError, OSError):
                        break
            except Exception as e:
                exc_holder.append(e)
            finally:
                read_done.set()

        try:
            proc = PtyProcess.spawn(argv, cwd=vinbox_runtime.working_dir(), env=env)
            # Set default tty size to avoid output truncation when there is no frontend
            apply_resize(100, 300)
        except Exception as e:
            PrettyOutput.auto_print(f"❌ PTY startup failed: {str(e)}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
            }

        self._publish_execution_event(
            stream_publisher,
            message_type="tool_stream_start",
            session_id=session_id,
            execution_id=execution_id,
            stream="stdout",
            sequence=next_sequence(),
        )

        reader_t = threading.Thread(target=reader, args=(proc,), daemon=True)
        reader_t.start()

        def stdin_forward() -> None:
            """Use msvcrt.kbhit polling instead of blocking readline, to ensure timely exit after the script ends without grabbing subsequent stdin"""
            try:
                if input_callback is not None:
                    while proc.isalive():
                        poll_resize()
                        try:
                            chunk = input_callback(0.1)
                        except Exception as e:
                            exc_holder.append(e)
                            break
                        if chunk:
                            publish_input_chunk(chunk)
                    return

                import msvcrt

                while proc.isalive():
                    poll_resize()
                    if msvcrt.kbhit():  # ty: ignore[unresolved-attribute]
                        try:
                            input_char = msvcrt.getwch()  # ty: ignore[unresolved-attribute]
                            publish_input_chunk(input_char)
                        except (EOFError, OSError, UnicodeEncodeError):
                            break
                    else:
                        time.sleep(0.05)
            except (EOFError, OSError, ImportError):
                pass

        stdin_t = threading.Thread(target=stdin_forward, daemon=True)
        stdin_t.start()

        try:
            timeout = get_timeout() if callable(get_timeout) else None
            if timeout is None:
                reader_t.join()
            else:
                reader_t.join(timeout=timeout)
            if timeout is not None and reader_t.is_alive():
                for method_name in ("terminate", "kill"):
                    terminate_method = getattr(proc, method_name, None)
                    if callable(terminate_method):
                        try:
                            terminate_method()
                            break
                        except Exception as e:
                            save_exception(
                                e,
                                module="haijunbot_tools.execute_script",
                                function="stdin_forward",
                            )
                            pass
                try:
                    getattr(proc, "wait", lambda: None)()
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_tools.execute_script",
                        function="stdin_forward",
                    )
                    pass
                read_done.wait(timeout=2)
                self._publish_execution_event(
                    stream_publisher,
                    message_type="tool_stream_end",
                    session_id=session_id,
                    execution_id=execution_id,
                    stream="stdout",
                    sequence=next_sequence(),
                    exit_code=getattr(proc, "exitstatus", None)
                    or getattr(proc, "returncode", None)
                    or -1,
                    reason="timeout",
                )
                return {
                    "success": False,
                    "stdout": "".join(captured),
                    "stderr": f"Execution timed out (exceeded {timeout} seconds), process terminated.",
                }
        except Exception as e:
            for method_name in ("terminate", "kill"):
                terminate_method = getattr(proc, method_name, None)
                if callable(terminate_method):
                    try:
                        terminate_method()
                        break
                    except Exception as inner_e:
                        save_exception(
                            inner_e,
                            module="haijunbot_tools.execute_script",
                            function="stdin_forward",
                        )
                        pass
            self._publish_execution_event(
                stream_publisher,
                message_type="tool_stream_end",
                session_id=session_id,
                execution_id=execution_id,
                stream="stdout",
                sequence=next_sequence(),
                exit_code=getattr(proc, "exitstatus", None)
                or getattr(proc, "returncode", None)
                or -1,
                reason="error",
            )
            return {
                "success": False,
                "stdout": "".join(captured),
                "stderr": str(e),
            }

        exit_code = (
            getattr(proc, "exitstatus", None) or getattr(proc, "returncode", None) or 0
        )
        read_done.wait(timeout=2)
        output = "".join(captured).strip()
        if exc_holder:
            self._publish_execution_event(
                stream_publisher,
                message_type="tool_stream_end",
                session_id=session_id,
                execution_id=execution_id,
                stream="stdout",
                sequence=next_sequence(),
                exit_code=exit_code,
                reason="error",
            )
            return {
                "success": False,
                "stdout": output,
                "stderr": str(exc_holder[0]),
            }
        self._publish_execution_event(
            stream_publisher,
            message_type="tool_stream_end",
            session_id=session_id,
            execution_id=execution_id,
            stream="stdout",
            sequence=next_sequence(),
            exit_code=exit_code,
            reason="completed" if exit_code == 0 else "error",
        )
        return {
            "success": exit_code == 0,
            "stdout": output,
            "stderr": "" if exit_code == 0 else f"Exit code: {exit_code}",
        }

    def _execute_on_unix_interactive_pty(
        self,
        argv: List[str],
        env: Dict[str, str],
        get_timeout: Any,
        stream_publisher: Optional[ExecutionStreamPublisher] = None,
        session_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        input_callback: Optional[Callable[[float], Optional[str]]] = None,
        resize_callback: Optional[Callable[[], Optional[Tuple[int, int]]]] = None,
    ) -> Dict[str, Any]:
        import fcntl
        import pty
        import struct
        import termios

        captured: List[str] = []
        captured_lock = threading.Lock()
        raw_captured: List[bytes] = []
        raw_captured_lock = threading.Lock()
        stop_event = threading.Event()
        exc_holder: List[BaseException] = []
        sequence_lock = threading.Lock()
        sequence = 0

        def next_sequence() -> int:
            nonlocal sequence
            with sequence_lock:
                sequence += 1
                return sequence

        master_fd, slave_fd = pty.openpty()
        old_stdin_attrs = None
        stdin_fd: Optional[int] = None
        stdin_is_tty = False
        if hasattr(sys.stdin, "fileno"):
            try:
                stdin_fd = sys.stdin.fileno()
                stdin_is_tty = os.isatty(stdin_fd)
            except Exception:
                stdin_fd = None
                stdin_is_tty = False

        def apply_resize(rows: int, cols: int) -> None:
            if rows <= 0 or cols <= 0:
                return
            try:
                fcntl.ioctl(
                    master_fd,
                    termios.TIOCSWINSZ,
                    struct.pack("HHHH", rows, cols, 0, 0),
                )
            except Exception as e:
                save_exception(
                    e, module="haijunbot_tools.execute_script", function="apply_resize"
                )
                pass

        def poll_resize() -> None:
            if resize_callback is None:
                return
            try:
                size = resize_callback()
            except Exception as exc:
                exc_holder.append(exc)
                return
            if not size:
                return
            rows, cols = size
            apply_resize(rows, cols)

        # Set default tty size to avoid output truncation when there is no frontend
        apply_resize(100, 300)

        def reader(proc: subprocess.Popen[Any]) -> None:
            try:
                while not stop_event.is_set():
                    # Check whether an interrupt signal was received
                    if get_interrupt() > 0:
                        break
                    poll_resize()
                    if proc.poll() is not None:
                        ready, _, _ = select.select([master_fd], [], [], 0.1)
                        if not ready:
                            break
                    else:
                        ready, _, _ = select.select([master_fd], [], [], 0.1)
                    if not ready:
                        continue
                    try:
                        data = os.read(master_fd, 4096)
                    except OSError:
                        break
                    if not data:
                        break
                    # Pass raw bytes data directly to _publish_stream_message
                    self._publish_stream_message(
                        stream_publisher,
                        data,
                        stream="tty",
                        session_id=session_id,
                        execution_id=execution_id,
                        sequence=next_sequence(),
                    )
                    # Save raw byte data for subsequent pyte processing
                    with raw_captured_lock:
                        raw_captured.append(data)
                    # For local output, decoding is still required
                    raw_text = data.decode("utf-8", errors="replace")
                    if not raw_text:
                        continue
                    display_text = self._strip_ansi(raw_text)
                    if display_text:
                        with captured_lock:
                            captured.append(display_text)
                    sys.stdout.write(raw_text)
                    sys.stdout.flush()
            except Exception as e:
                exc_holder.append(e)
            finally:
                stop_event.set()

        def write_input_chunk(chunk: str) -> None:
            if not chunk:
                return
            try:
                os.write(master_fd, chunk.encode("utf-8", errors="ignore"))
                self._publish_execution_event(
                    stream_publisher,
                    message_type="tool_input",
                    session_id=session_id,
                    execution_id=execution_id,
                    stream="stdin",
                    chunk=chunk,
                    sequence=next_sequence(),
                )
            except OSError:
                stop_event.set()

        def stdin_forward(proc: subprocess.Popen[Any]) -> None:
            try:
                if input_callback is not None:
                    while not stop_event.is_set() and proc.poll() is None:
                        poll_resize()
                        try:
                            chunk = input_callback(0.1)
                        except Exception as e:
                            exc_holder.append(e)
                            break
                        if chunk:
                            write_input_chunk(chunk)
                    return

                if stdin_fd is None:
                    return

                if stdin_is_tty:
                    import termios
                    import tty

                    try:
                        old_attrs = termios.tcgetattr(stdin_fd)
                        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_attrs)
                    except Exception:
                        old_attrs = None
                    if old_attrs is not None:
                        nonlocal old_stdin_attrs
                        old_stdin_attrs = old_attrs
                        tty.setraw(stdin_fd)

                while not stop_event.is_set() and proc.poll() is None:
                    poll_resize()
                    try:
                        ready, _, _ = select.select([stdin_fd], [], [], 0.1)
                    except Exception:
                        break
                    if not ready:
                        continue
                    try:
                        data = os.read(stdin_fd, 1024)
                    except OSError:
                        break
                    if not data:
                        break
                    write_input_chunk(data.decode("utf-8", errors="ignore"))
            except Exception as e:
                exc_holder.append(e)
            finally:
                if (
                    stdin_is_tty
                    and stdin_fd is not None
                    and old_stdin_attrs is not None
                ):
                    try:
                        import termios

                        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_stdin_attrs)
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_tools.execute_script",
                            function="stdin_forward",
                        )
                        pass

        try:
            proc = subprocess.Popen(
                argv,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=vinbox_runtime.working_dir(),
                env=env,
                start_new_session=True,
                close_fds=True,
            )
            set_script_pid(proc.pid)
        except Exception as e:
            os.close(master_fd)
            os.close(slave_fd)
            PrettyOutput.auto_print(f"❌ Unix PTY startup failed: {str(e)}")
            return {"success": False, "stdout": "", "stderr": str(e)}
        finally:
            try:
                os.close(slave_fd)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_tools.execute_script", function="stdin_forward"
                )
                pass

        self._publish_execution_event(
            stream_publisher,
            message_type="tool_stream_start",
            session_id=session_id,
            execution_id=execution_id,
            stream="tty",
            sequence=next_sequence(),
        )

        reader_t = threading.Thread(target=reader, args=(proc,), daemon=True)
        stdin_t = threading.Thread(target=stdin_forward, args=(proc,), daemon=True)
        reader_t.start()
        stdin_t.start()

        timeout = get_timeout() if callable(get_timeout) else None
        timed_out = False
        try:
            # Use polling to check for interrupts instead of calling wait directly
            start_time = time.time()
            if timeout is None:
                while proc.poll() is None:
                    # Check whether an interrupt signal was received
                    if get_interrupt() > 0:
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait()
                        clear_script_pid()
                        set_interrupt(False)
                        return {
                            "success": False,
                            "stdout": "",
                            "stderr": "Execution interrupted by user.",
                        }
                    time.sleep(0.1)
            else:
                while proc.poll() is None:
                    # Check whether it has timed out
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        raise subprocess.TimeoutExpired(argv, timeout)
                    # Check whether an interrupt signal was received
                    if get_interrupt() > 0:
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait()
                        clear_script_pid()
                        set_interrupt(False)
                        return {
                            "success": False,
                            "stdout": "",
                            "stderr": "Execution interrupted by user.",
                        }
                    time.sleep(0.1)
            # Process has ended; get output (already captured in the reader thread)
        except subprocess.TimeoutExpired:
            timed_out = True
            stop_event.set()
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_tools.execute_script",
                        function="stdin_forward",
                    )
                    pass
        except Exception as e:
            exc_holder.append(e)
            stop_event.set()
            try:
                proc.terminate()
            except Exception as e:
                save_exception(
                    e, module="haijunbot_tools.execute_script", function="stdin_forward"
                )
                pass

        stop_event.set()
        reader_t.join(timeout=2)
        stdin_t.join(timeout=2)
        try:
            os.close(master_fd)
        except Exception as e:
            save_exception(
                e, module="haijunbot_tools.execute_script", function="stdin_forward"
            )
            pass

        # Use pyte to process raw byte data and get the correct display output (handling control characters)
        try:
            import pyte

            raw_data = b"".join(raw_captured)
            screen = pyte.Screen(300, 100000)
            stream = pyte.ByteStream(screen)
            stream.feed(raw_data)
            # Trim trailing spaces on each line and filter out empty lines
            cleaned_lines: List[str] = []
            for y in range(screen.lines):
                line = screen.buffer[y]
                stripped = "".join(char.data for char in line.values()).rstrip()
                if stripped:
                    cleaned_lines.append(stripped)
            output = "\n".join(cleaned_lines).strip()
        except Exception:
            # If pyte processing fails, fall back to the original logic
            output = "".join(captured).strip()
        exit_code = proc.returncode if proc.returncode is not None else -1
        clear_script_pid()
        if timed_out:
            self._publish_execution_event(
                stream_publisher,
                message_type="tool_stream_end",
                session_id=session_id,
                execution_id=execution_id,
                stream="tty",
                sequence=next_sequence(),
                exit_code=exit_code,
                reason="timeout",
            )
            return {
                "success": False,
                "stdout": output,
                "stderr": f"Execution timed out (exceeded {timeout} seconds), process terminated.",
            }
        if exc_holder:
            self._publish_execution_event(
                stream_publisher,
                message_type="tool_stream_end",
                session_id=session_id,
                execution_id=execution_id,
                stream="tty",
                sequence=next_sequence(),
                exit_code=exit_code,
                reason="error",
            )
            return {
                "success": False,
                "stdout": output,
                "stderr": str(exc_holder[0]),
            }

        self._publish_execution_event(
            stream_publisher,
            message_type="tool_stream_end",
            session_id=session_id,
            execution_id=execution_id,
            stream="tty",
            sequence=next_sequence(),
            exit_code=exit_code,
            reason="completed" if exit_code == 0 else "error",
        )
        return {
            "success": exit_code == 0,
            "stdout": output,
            "stderr": "" if exit_code == 0 else f"Exit code: {exit_code}",
        }

    def _execute_on_windows(
        self,
        interpreter: str,
        script_path: str,
        extension: str,
        is_non_interactive: bool,
        get_timeout: Any,
        stream_publisher: Optional[ExecutionStreamPublisher] = None,
        session_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        input_callback: Optional[Callable[[float], Optional[str]]] = None,
        resize_callback: Optional[Callable[[], Optional[Tuple[int, int]]]] = None,
    ) -> Dict[str, Any]:
        """Execute scripts on the Windows platform (uses subprocess, no script command)

        Non-interactive mode: takes over stdin/stdout/stderr and captures output to return (user cannot interact)
        Interactive mode: inherits the parent process stdio, the user can interact with the program (e.g., input/Read-Host), but output is not captured
        """
        cmd = self._get_windows_command(interpreter, script_path, extension)
        env = vinbox_runtime.process_env()
        if interpreter in ("python", "python2", "python3"):
            env["PYTHONIOENCODING"] = "utf-8"
        try:
            if is_non_interactive:
                # Agent/automation mode: use ConPTY, which both streams output in real time and captures it
                return self._execute_on_windows_interactive_pty(
                    argv=cmd,
                    env=env,
                    get_timeout=get_timeout,
                    stream_publisher=stream_publisher,
                    session_id=session_id,
                    execution_id=execution_id,
                    input_callback=input_callback,
                    resize_callback=resize_callback,
                )
            else:
                # Interactive mode: try using pywinpty (ConPTY), which allows both user interaction and output capture (similar to script)
                return self._execute_on_windows_interactive_pty(
                    argv=cmd,
                    env=env,
                    get_timeout=None,
                    stream_publisher=stream_publisher,
                    session_id=session_id,
                    execution_id=execution_id,
                    input_callback=input_callback,
                    resize_callback=resize_callback,
                )
        except FileNotFoundError as e:
            PrettyOutput.auto_print(f"❌ {str(e)}")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Interpreter '{interpreter}' not found. Make sure it is installed and added to PATH.",
            }
        except Exception as e:
            PrettyOutput.auto_print(f"❌ {str(e)}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
            }

    def get_display_output(self, file_path: str) -> str:
        """Eliminate control characters to get the text the user actually sees, removing the first and last lines of the script command"""
        # Read the file content and try multiple encodings
        with open(file_path, "rb") as f:
            data = f.read()

        import pyte

        screen = pyte.Screen(300, 100000)
        stream = pyte.ByteStream(screen)
        stream.feed(data)

        # Trim trailing spaces on each line and filter out empty lines
        cleaned: List[str] = []
        for y in range(screen.lines):
            line = screen.buffer[y]
            stripped = "".join(char.data for char in line.values()).rstrip()
            if stripped:
                cleaned.append(stripped)
        return "\n".join(cleaned[1:-1])

    def _select_backend(self, execution_mode: str) -> ExecutionBackend:
        normalized_mode = (execution_mode or "auto").strip().lower()
        if normalized_mode == "interactive":
            return VirtualTTYExecutionBackend()
        if normalized_mode == "captured":
            return CapturedExecutionBackend()

        from haijunbot.haijunbot_utils.config import is_non_interactive

        return (
            CapturedExecutionBackend()
            if is_non_interactive()
            else VirtualTTYExecutionBackend()
        )

    def _execute_script_captured(self, request: ExecutionRequest) -> Dict[str, Any]:
        return self._execute_script_with_interpreter_internal(
            request, force_non_interactive=True
        )

    def _execute_script_interactive(self, request: ExecutionRequest) -> Dict[str, Any]:
        return self._execute_script_with_interpreter_internal(
            request, force_non_interactive=False
        )

    def _execute_script_with_interpreter_internal(
        self, request: ExecutionRequest, force_non_interactive: bool
    ) -> Dict[str, Any]:
        interpreter = request.interpreter
        script_content = request.script_content
        try:
            extension = self.INTERPRETER_EXTENSIONS.get(interpreter, "script")
            script_path = os.path.join(
                tempfile.gettempdir(),
                f"haijunbot_{interpreter.replace('/', '_')}_{os.getpid()}.{extension}",
            )
            output_file = os.path.join(
                tempfile.gettempdir(), f"haijunbot_output_{os.getpid()}.log"
            )
            try:
                enc = "utf-8-sig" if interpreter in ("powershell", "pwsh") else "utf-8"
                with open(script_path, "w", encoding=enc, errors="ignore") as f:
                    f.write(script_content)

                PrettyOutput.print_script_panel(
                    content=script_content,
                    title=f"📜 Executing script ({interpreter})",
                    lang=interpreter,
                )

                from haijunbot.haijunbot_utils.config import get_script_execution_timeout

                if self._is_windows():
                    return self._execute_on_windows(
                        interpreter=interpreter,
                        script_path=script_path,
                        extension=extension,
                        is_non_interactive=force_non_interactive,
                        get_timeout=get_script_execution_timeout,
                        stream_publisher=request.stream_publisher,
                        session_id=request.session_id,
                        execution_id=request.execution_id,
                        input_callback=request.input_callback,
                        resize_callback=request.resize_callback,
                    )

                if force_non_interactive:
                    env = vinbox_runtime.process_env()
                    # Set the TERM environment variable to avoid the "terminal is not fully functional" warning
                    env["TERM"] = "xterm-256color"
                    if interpreter in ("python", "python2", "python3"):
                        env["PYTHONIOENCODING"] = "utf-8"
                    argv = [interpreter, script_path]
                    if interpreter in ("python", "python2", "python3"):
                        argv = [interpreter, "-u", script_path]
                    return self._execute_on_unix_interactive_pty(
                        argv=argv,
                        env=env,
                        get_timeout=get_script_execution_timeout,
                        stream_publisher=request.stream_publisher,
                        session_id=request.session_id,
                        execution_id=request.execution_id,
                        input_callback=request.input_callback,
                        resize_callback=request.resize_callback,
                    )

                env = vinbox_runtime.process_env()
                # Set the TERM environment variable to avoid the "terminal is not fully functional" warning
                env["TERM"] = "xterm-256color"
                if interpreter in ("python", "python2", "python3"):
                    env["PYTHONIOENCODING"] = "utf-8"
                argv = [interpreter, script_path]
                if interpreter in ("python", "python2", "python3"):
                    argv = [interpreter, "-u", script_path]
                return self._execute_on_unix_interactive_pty(
                    argv=argv,
                    env=env,
                    get_timeout=None,
                    stream_publisher=request.stream_publisher,
                    session_id=request.session_id,
                    execution_id=request.execution_id,
                    input_callback=request.input_callback,
                    resize_callback=request.resize_callback,
                )
            finally:
                Path(script_path).unlink(missing_ok=True)
                Path(output_file).unlink(missing_ok=True)
        except Exception as e:
            PrettyOutput.auto_print(f"❌ {str(e)}")
            return {"success": False, "stdout": "", "stderr": str(e)}

    def _execute_script_with_interpreter(
        self,
        interpreter: str,
        script_content: str,
        execution_mode: str = "auto",
        session_id: Optional[str] = None,
        stream_publisher: Optional[ExecutionStreamPublisher] = None,
        execution_id: Optional[str] = None,
        input_callback: Optional[Callable[[float], Optional[str]]] = None,
        resize_callback: Optional[Callable[[], Optional[Tuple[int, int]]]] = None,
    ) -> Dict[str, Any]:
        request = ExecutionRequest(
            interpreter=interpreter,
            script_content=script_content,
            execution_mode=execution_mode,
            session_id=session_id,
            stream_publisher=stream_publisher,
            execution_id=execution_id,
            input_callback=input_callback,
            resize_callback=resize_callback,
        )
        backend = self._select_backend(execution_mode)
        return backend.execute(self, request)

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute script based on interpreter and content

        Args:
            args: Dictionary containing interpreter (or script_type) and script_content

        Returns:
            Dictionary with execution results
        """
        try:
            # Compatible with different callers' key names (script_content/code/command/script)
            raw_script = (
                args.get("script_content")
                or args.get("script")
                or args.get("command")
                or args.get("code")
                or ""
            )
            script_content = str(raw_script).strip()
            if not script_content:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Missing or empty: script_content (script content)",
                }

            # Get interpreter: Windows defaults to powershell, Unix defaults to bash; compatible with the legacy key script_type
            interpreter = (
                args.get("interpreter")
                or args.get("script_type")
                or ("powershell" if self._is_windows() else "bash")
            )
            execution_mode = str(args.get("execution_mode", "auto"))
            session_id = args.get("session_id")
            stream_publisher = args.get("stream_publisher")
            execution_id = args.get("execution_id")
            input_callback = args.get("input_callback")
            resize_callback = args.get("resize_callback")
            gateway = None

            if stream_publisher is None:
                try:
                    from haijunbot.haijunbot_gateway.manager import get_current_gateway

                    gateway = get_current_gateway()
                except Exception:
                    gateway = None
                if gateway is not None:
                    stream_publisher = GatewayExecutionStreamPublisher(gateway)
            if stream_publisher is not None and not isinstance(
                stream_publisher, ExecutionStreamPublisher
            ):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "stream_publisher must implement ExecutionStreamPublisher",
                }
            if input_callback is not None and not callable(input_callback):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "input_callback must be callable",
                }
            if resize_callback is not None and not callable(resize_callback):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "resize_callback must be callable",
                }

            execution_id_value = (
                execution_id if isinstance(execution_id, str) else uuid.uuid4().hex
            )
            if input_callback is None or resize_callback is None:
                if gateway is None:
                    try:
                        from haijunbot.haijunbot_gateway.manager import get_current_gateway

                        gateway = get_current_gateway()
                    except Exception:
                        gateway = None
                if gateway is not None:
                    if input_callback is None:
                        input_callback = gateway.get_execution_input_callback(
                            execution_id_value
                        )
                    if resize_callback is None:
                        resize_callback = gateway.get_execution_resize_callback(
                            execution_id_value
                        )

            # Execute the script with the specified interpreter
            return self._execute_script_with_interpreter(
                interpreter,
                script_content,
                execution_mode=execution_mode,
                session_id=session_id if isinstance(session_id, str) else None,
                stream_publisher=stream_publisher,
                execution_id=execution_id_value,
                input_callback=input_callback,
                resize_callback=resize_callback,
            )

        except Exception as e:
            PrettyOutput.auto_print(f"❌ {str(e)}")
            return {"success": False, "stdout": "", "stderr": str(e)}
