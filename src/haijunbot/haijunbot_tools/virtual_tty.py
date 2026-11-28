# -*- coding: utf-8 -*-
import os
import sys
import time
from typing import TYPE_CHECKING
from typing import Any
from typing import Dict

from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import decode_output
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils import vinbox_runtime

# For type checking, always import these modules
if TYPE_CHECKING:
    pass

# Platform-related imports
if sys.platform != "win32":
    pass
else:
    # Imports for the Windows platform
    pass


class VirtualTTYTool:
    name = "virtual_tty"
    description = "Manage persistent virtual terminal sessions for interactive operations (ssh/sftp/gdb, etc.); unlike one-shot execution, this tool preserves terminal state for continuous interaction across multiple commands. Windows support is limited."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Operation: launch starts a session / send_keys sends keys or inputs a command / output reads the latest output / close closes / get_screen gets the current screen / list lists sessions",
                "enum": [
                    "launch",
                    "send_keys",
                    "output",
                    "close",
                    "get_screen",
                    "list",
                ],
            },
            "keys": {
                "type": "string",
                "description": "The key sequence to send (valid only when action is send_keys)",
            },
            "add_enter": {
                "type": "boolean",
                "description": "Whether to automatically append a carriage return at the end of the command (valid only when action is send_keys, defaults to true)",
            },
            "timeout": {
                "type": "number",
                "description": "Timeout for waiting for output (seconds; valid only when action is send_keys or output, defaults to 5.0)",
            },
            "tty_id": {
                "type": "string",
                "description": "Unique identifier of the virtual terminal (defaults to 'default')",
            },
        },
        "required": ["action"],
    }

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a terminal operation

        Parameters:
            args: a dict containing the operation arguments, including the agent attribute

        Returns:
            A dict containing the following:
                - success: a boolean indicating the operation status
                - stdout: a success message or the operation result
                - stderr: an error message or an empty string
        """
        # Get the agent object
        agent = args.get("agent")
        if agent is None:
            return {"success": False, "stdout": "", "stderr": "No agent object provided"}

        # Get the TTY ID, defaulting to "default"
        tty_id = args.get("tty_id", "default")

        # Ensure the agent has a tty_sessions dict
        if not hasattr(agent, "tty_sessions"):
            agent.tty_sessions = {}
        elif agent.tty_sessions is None:
            agent.tty_sessions = {}

        # If the specified tty_id does not exist, create a new tty_data for it
        if tty_id not in agent.tty_sessions:
            # Vinbox hanya punya satu terminal: pwsh, di Windows/Linux/macOS.
            # Tidak ada cmd.exe atau bash yang dipanggil dari sini.
            shell = vinbox_runtime.shell_path()
            if sys.platform == "win32":
                import queue as _queue  # pylint: disable=import-outside-toplevel

                agent.tty_sessions[tty_id] = {
                    "process": None,
                    "output_queue": _queue.Queue(),
                    "output_thread": None,
                    "shell": shell,
                }
            else:
                agent.tty_sessions[tty_id] = {
                    "master_fd": None,
                    "pid": None,
                    "shell": shell,
                }

        action = args.get("action", "").strip().lower()

        # Validate the operation type
        valid_actions = ["launch", "send_keys", "output", "close", "get_screen", "list"]
        if action not in valid_actions:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Unsupported operation: {action}. Valid operations: {', '.join(valid_actions)}",
            }

        try:
            if action == "launch":
                if args.get("keys", "") != "":
                    PrettyOutput.auto_print("❌ The keys argument cannot be specified at the same time when launching a virtual terminal")
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": "The keys argument cannot be specified at the same time when launching a virtual terminal",
                    }

                result = self._launch_tty(agent, tty_id)
                if not result["success"]:
                    PrettyOutput.auto_print(f"❌ Failed to launch virtual terminal [{tty_id}]")
                return result
            elif action == "send_keys":
                keys = args.get("keys", "").strip()
                add_enter = args.get("add_enter", True)
                timeout = args.get("timeout", 5.0)  # Default 5 second timeout

                result = self._input_command(agent, tty_id, keys, timeout, add_enter)
                if not result["success"]:
                    PrettyOutput.auto_print(f"❌ Failed to send key sequence to terminal [{tty_id}]")
                return result
            elif action == "output":
                timeout = args.get("timeout", 5.0)  # Default 5 second timeout

                result = self._get_output(agent, tty_id, timeout)
                if not result["success"]:
                    PrettyOutput.auto_print(f"❌ Failed to get output from terminal [{tty_id}]")
                return result
            elif action == "close":
                result = self._close_tty(agent, tty_id)
                if not result["success"]:
                    PrettyOutput.auto_print(f"❌ Failed to close virtual terminal [{tty_id}]")
                return result
            elif action == "get_screen":
                result = self._get_screen(agent, tty_id)
                if not result["success"]:
                    PrettyOutput.auto_print(f"❌ Failed to get screen content of terminal [{tty_id}]")
                return result
            elif action == "list":
                result = self._list_ttys(agent)
                if not result["success"]:
                    PrettyOutput.auto_print("❌ Failed to get the virtual terminal list")
                return result
            return {"success": False, "stdout": "", "stderr": "Unsupported operation"}

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Error executing terminal operation: {str(e)}",
            }

    def _launch_tty(self, agent: Any, tty_id: str) -> Dict[str, Any]:
        """Launch a virtual terminal"""
        if sys.platform == "win32":
            return self._launch_tty_windows(agent, tty_id)
        else:
            return self._launch_tty_unix(agent, tty_id)

    def _launch_tty_unix(self, agent: Any, tty_id: str) -> Dict[str, Any]:
        """Launch a virtual terminal on the Unix/Linux platform"""
        try:
            # If the terminal with this ID is already started, close it first
            if agent.tty_sessions[tty_id]["master_fd"] is not None:
                self._close_tty(agent, tty_id)

            # Import the needed modules on the Unix platform
            import fcntl as _fcntl  # pylint: disable=import-outside-toplevel
            import pty as _pty  # pylint: disable=import-outside-toplevel
            import select as _select  # pylint: disable=import-outside-toplevel

            # Create a pseudo-terminal
            pid, master_fd = _pty.fork()

            if pid == 0:  # Child process
                # Execute the shell in the Vinbox world: its environment, its
                # File Manager as working directory, PowerShell as the shell.
                try:
                    if vinbox_runtime.is_vinbox():
                        os.environ.clear()
                        os.environ.update(vinbox_runtime.process_env())
                        os.chdir(vinbox_runtime.working_dir())
                except Exception:
                    pass
                os.execvp(
                    agent.tty_sessions[tty_id]["shell"],
                    [agent.tty_sessions[tty_id]["shell"]],
                )
            else:  # Parent process
                # Set non-blocking mode
                _fcntl.fcntl(master_fd, _fcntl.F_SETFL, os.O_NONBLOCK)

                # Save the terminal state
                agent.tty_sessions[tty_id]["master_fd"] = master_fd
                agent.tty_sessions[tty_id]["pid"] = pid

                # Read the initial output
                output = ""
                start_time = time.time()
                while time.time() - start_time < 2.0:  # Wait up to 2 seconds
                    try:
                        r, _, _ = _select.select([master_fd], [], [], 0.1)
                        if r:
                            data = os.read(master_fd, 1024)
                            if data:
                                output += decode_output(data)
                    except BlockingIOError:
                        continue

                if output:
                    PrettyOutput.auto_print(
                        f"📥 Initial output when starting the terminal [{tty_id}]:\n{output}"
                    )
                return {"success": True, "stdout": output, "stderr": ""}

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to launch virtual terminal [{tty_id}]: {str(e)}",
            }

    def _launch_tty_windows(self, agent: Any, tty_id: str) -> Dict[str, Any]:
        """Launch a virtual terminal on the Windows platform"""
        try:
            # If the terminal with this ID is already started, close it first
            if agent.tty_sessions[tty_id]["process"] is not None:
                self._close_tty(agent, tty_id)

            # Import the needed modules on the Windows platform
            import queue as _queue  # pylint: disable=import-outside-toplevel
            import subprocess as _subprocess  # pylint: disable=import-outside-toplevel
            import threading as _threading  # pylint: disable=import-outside-toplevel

            # Create the subprocess: argv list + shell=False, jadi tidak ada
            # cmd.exe yang ikut campur. Perintah tetap diketik di dalam pwsh.
            process = _subprocess.Popen(
                [agent.tty_sessions[tty_id]["shell"], "-NoLogo", "-NoProfile"],
                stdin=_subprocess.PIPE,
                stdout=_subprocess.PIPE,
                stderr=_subprocess.STDOUT,
                shell=False,
                text=True,
                bufsize=0,
                encoding="utf-8",
                errors="replace",
            )

            # Save the process object
            agent.tty_sessions[tty_id]["process"] = process

            # Create the output-reading thread
            def read_output() -> None:
                while True:
                    if process is None or process.poll() is not None:
                        break
                    try:
                        if process.stdout is None:
                            break
                        line = process.stdout.readline()
                        if line:
                            agent.tty_sessions[tty_id]["output_queue"].put(line)
                    except Exception:
                        break

            output_thread = _threading.Thread(target=read_output, daemon=True)
            output_thread.start()
            agent.tty_sessions[tty_id]["output_thread"] = output_thread

            # Read the initial output
            output = ""
            start_time = time.time()
            while time.time() - start_time < 2.0:  # Wait up to 2 seconds
                try:
                    line = agent.tty_sessions[tty_id]["output_queue"].get(timeout=0.1)
                    output += line
                except _queue.Empty:
                    continue

            if output:
                PrettyOutput.auto_print(
                    f"📥 Initial output when starting the terminal [{tty_id}]:\n{output}"
                )
            return {"success": True, "stdout": output, "stderr": ""}

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to launch virtual terminal [{tty_id}]: {str(e)}",
            }

    def _input_command(
        self,
        agent: Any,
        tty_id: str,
        command: str,
        timeout: float,
        add_enter: bool = True,
    ) -> Dict[str, Any]:
        """Input a single-line command and wait for output

        Parameters:
            command: the single-line command to input
            add_enter: whether to append a carriage return at the end of the command
        """
        if sys.platform == "win32":
            return self._input_command_windows(
                agent, tty_id, command, timeout, add_enter
            )
        else:
            return self._input_command_unix(agent, tty_id, command, timeout, add_enter)

    def _input_command_unix(
        self,
        agent: Any,
        tty_id: str,
        command: str,
        timeout: float,
        add_enter: bool = True,
    ) -> Dict[str, Any]:
        """Input a command on the Unix/Linux platform"""
        if agent.tty_sessions[tty_id]["master_fd"] is None:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Virtual terminal [{tty_id}] is not started",
            }

        # Strictly check and reject multi-line input
        if "\n" in command:
            return {"success": False, "stdout": "", "stderr": "Error: multi-line input is forbidden"}

        try:
            # Decide whether to append a carriage return based on the add_enter argument
            if add_enter:
                command = command + "\n"

            # Send the key sequence
            os.write(agent.tty_sessions[tty_id]["master_fd"], command.encode())

            # Wait for output
            output = ""
            start_time = time.time()

            while time.time() - start_time < timeout:
                try:
                    # Use select to wait until data is readable
                    import select as _select  # pylint: disable=import-outside-toplevel

                    r, _, _ = _select.select(
                        [agent.tty_sessions[tty_id]["master_fd"]], [], [], 0.1
                    )
                    if r:
                        data = os.read(agent.tty_sessions[tty_id]["master_fd"], 1024)
                        if data:
                            output += decode_output(data)
                except BlockingIOError:
                    continue
            if output:
                PrettyOutput.auto_print(
                    f"📥 Output content after command execution [{tty_id}]:\n{output}"
                )
            return {"success": True, "stdout": output, "stderr": ""}

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to execute command in terminal [{tty_id}]: {str(e)}",
            }

    def _input_command_windows(
        self,
        agent: Any,
        tty_id: str,
        command: str,
        timeout: float,
        add_enter: bool = True,
    ) -> Dict[str, Any]:
        """Input a command on the Windows platform"""
        if agent.tty_sessions[tty_id]["process"] is None:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Virtual terminal [{tty_id}] is not started",
            }

        # Strictly check and reject multi-line input
        if "\n" in command:
            return {"success": False, "stdout": "", "stderr": "Error: multi-line input is forbidden"}

        try:
            # Decide whether to append a carriage return based on the add_enter argument
            if add_enter:
                command = command + "\n"

            # Send the command
            agent.tty_sessions[tty_id]["process"].stdin.write(command)
            agent.tty_sessions[tty_id]["process"].stdin.flush()

            # Wait for output
            output = ""
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    line = agent.tty_sessions[tty_id]["output_queue"].get(timeout=0.1)
                    output += line
                except Exception:  # queue.Empty
                    continue

            if output:
                PrettyOutput.auto_print(
                    f"📥 Output content after command execution [{tty_id}]:\n{output}"
                )
            return {"success": True, "stdout": output, "stderr": ""}

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to execute command in terminal [{tty_id}]: {str(e)}",
            }

    def _get_output(
        self, agent: Any, tty_id: str, timeout: float = 5.0
    ) -> Dict[str, Any]:
        """Get terminal output"""
        if sys.platform == "win32":
            return self._get_output_windows(agent, tty_id, timeout)
        else:
            return self._get_output_unix(agent, tty_id, timeout)

    def _get_output_unix(
        self, agent: Any, tty_id: str, timeout: float = 5.0
    ) -> Dict[str, Any]:
        """Get output on the Unix/Linux platform"""
        if agent.tty_sessions[tty_id]["master_fd"] is None:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Virtual terminal [{tty_id}] is not started",
            }

        try:
            output = ""
            start_time = time.time()

            while time.time() - start_time < timeout:
                # Use select to wait until data is readable
                import select as _select  # pylint: disable=import-outside-toplevel

                r, _, _ = _select.select(
                    [agent.tty_sessions[tty_id]["master_fd"]], [], [], 0.1
                )
                if r:
                    while True:
                        try:
                            data = os.read(
                                agent.tty_sessions[tty_id]["master_fd"], 1024
                            )
                            if data:
                                output += decode_output(data)
                            else:
                                break
                        except BlockingIOError:
                            break
            if output:
                PrettyOutput.auto_print(f"📥 Output content retrieved [{tty_id}]:\n{output}")
            return {"success": True, "stdout": output, "stderr": ""}

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to get output from terminal [{tty_id}]: {str(e)}",
            }

    def _get_output_windows(
        self, agent: Any, tty_id: str, timeout: float = 5.0
    ) -> Dict[str, Any]:
        """Get output on the Windows platform"""
        if agent.tty_sessions[tty_id]["process"] is None:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Virtual terminal [{tty_id}] is not started",
            }

        try:
            output = ""
            start_time = time.time()

            while time.time() - start_time < timeout:
                try:
                    line = agent.tty_sessions[tty_id]["output_queue"].get(timeout=0.1)
                    output += line
                except Exception:  # queue.Empty
                    continue

            if output:
                PrettyOutput.auto_print(f"📥 Output content retrieved [{tty_id}]:\n{output}")
            return {"success": True, "stdout": output, "stderr": ""}

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to get output from terminal [{tty_id}]: {str(e)}",
            }

    def _close_tty(self, agent: Any, tty_id: str) -> Dict[str, Any]:
        """Close the virtual terminal"""
        if sys.platform == "win32":
            return self._close_tty_windows(agent, tty_id)
        else:
            return self._close_tty_unix(agent, tty_id)

    def _close_tty_unix(self, agent: Any, tty_id: str) -> Dict[str, Any]:
        """Close the terminal on the Unix/Linux platform"""
        if agent.tty_sessions[tty_id]["master_fd"] is None:
            return {
                "success": True,
                "stdout": f"There is no running virtual terminal [{tty_id}]",
                "stderr": "",
            }

        try:
            # Close the master file descriptor
            os.close(agent.tty_sessions[tty_id]["master_fd"])

            # Terminate the child process
            if agent.tty_sessions[tty_id]["pid"]:
                import signal as _signal  # pylint: disable=import-outside-toplevel

                os.kill(agent.tty_sessions[tty_id]["pid"], _signal.SIGTERM)

            # Reset the terminal data
            agent.tty_sessions[tty_id] = {
                "master_fd": None,
                "pid": None,
                "shell": os.getenv("SHELL", "/bin/bash"),
            }

            return {
                "success": True,
                "stdout": f"Virtual terminal [{tty_id}] closed",
                "stderr": "",
            }

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to close virtual terminal [{tty_id}]: {str(e)}",
            }

    def _close_tty_windows(self, agent: Any, tty_id: str) -> Dict[str, Any]:
        """Close the terminal on the Windows platform"""
        if agent.tty_sessions[tty_id]["process"] is None:
            return {
                "success": True,
                "stdout": f"There is no running virtual terminal [{tty_id}]",
                "stderr": "",
            }

        import subprocess as _subprocess  # pylint: disable=import-outside-toplevel

        try:
            process = agent.tty_sessions[tty_id]["process"]
            # Terminate the process
            try:
                process.terminate()
                process.wait(timeout=2)
            except _subprocess.TimeoutExpired:
                try:
                    process.kill()
                    process.wait()
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_tools.virtual_tty",
                        function="_close_tty_windows",
                    )
                    pass
            except Exception:
                try:
                    process.kill()
                    process.wait()
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_tools.virtual_tty",
                        function="_close_tty_windows",
                    )
                    pass
            finally:
                # Ensure all file descriptors are closed
                try:
                    if process.stdin:
                        process.stdin.close()
                    if process.stdout:
                        process.stdout.close()
                    if process.stderr:
                        process.stderr.close()
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_tools.virtual_tty",
                        function="_close_tty_windows",
                    )
                    pass

            # Reset the terminal data
            import queue as _queue  # pylint: disable=import-outside-toplevel

            agent.tty_sessions[tty_id] = {
                "process": None,
                "output_queue": _queue.Queue(),
                "output_thread": None,
                "shell": vinbox_runtime.shell_path(),
            }

            return {
                "success": True,
                "stdout": f"Virtual terminal [{tty_id}] closed",
                "stderr": "",
            }

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to close virtual terminal [{tty_id}]: {str(e)}",
            }

    def _get_screen(self, agent: Any, tty_id: str) -> Dict[str, Any]:
        """Get the current terminal screen content"""
        if sys.platform == "win32":
            # Getting screen content is not yet supported on the Windows platform
            return {
                "success": False,
                "stdout": "",
                "stderr": "Getting screen content is not yet supported on the Windows platform",
            }

        if agent.tty_sessions[tty_id]["master_fd"] is None:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Virtual terminal [{tty_id}] is not started",
            }

        try:
            # Send control sequences to get the screen content
            os.write(
                agent.tty_sessions[tty_id]["master_fd"],
                b"\x1b[2J\x1b[H\x1b[999;999H\x1b[6n",
            )

            # Read the response
            output = ""
            start_time = time.time()
            while time.time() - start_time < 2.0:  # Wait up to 2 seconds
                try:
                    import select as _select  # pylint: disable=import-outside-toplevel

                    r, _, _ = _select.select(
                        [agent.tty_sessions[tty_id]["master_fd"]], [], [], 0.1
                    )
                    if r:
                        data = os.read(agent.tty_sessions[tty_id]["master_fd"], 1024)
                        if data:
                            output += decode_output(data)
                except BlockingIOError:
                    continue

            # Clean up control characters
            output = (
                output.replace("\x1b[2J", "")
                .replace("\x1b[H", "")
                .replace("\x1b[999;999H", "")
                .replace("\x1b[6n", "")
            )

            return {"success": True, "stdout": output.strip(), "stderr": ""}

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to get screen content of terminal [{tty_id}]: {str(e)}",
            }

    def _list_ttys(self, agent: Any) -> Dict[str, Any]:
        """List all virtual terminals"""
        try:
            active_ttys = []

            for tty_id, tty_data in agent.tty_sessions.items():
                if sys.platform == "win32":
                    status = "active" if tty_data["process"] is not None else "closed"
                    active_ttys.append(
                        {
                            "id": tty_id,
                            "status": status,
                            "pid": (
                                tty_data["process"].pid if tty_data["process"] else None
                            ),
                            "shell": tty_data["shell"],
                        }
                    )
                else:
                    status = "active" if tty_data["master_fd"] is not None else "closed"
                    active_ttys.append(
                        {
                            "id": tty_id,
                            "status": status,
                            "pid": tty_data["pid"] if tty_data["pid"] else None,
                            "shell": tty_data["shell"],
                        }
                    )

            # Format the output
            output = "Virtual terminal list:\n"
            for tty in active_ttys:
                output += f"ID: {tty['id']}, Status: {tty['status']}, PID: {tty['pid']}, Shell: {tty['shell']}\n"

            return {
                "success": True,
                "stdout": output,
                "stderr": "",
                "tty_list": active_ttys,  # Return the raw data for easier programmatic handling
            }

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to get the virtual terminal list: {str(e)}",
            }
