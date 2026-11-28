# -*- coding: utf-8 -*-
"""HaijunBot service ELI."""

import atexit
import os
import secrets
import shutil
import signal
import sys
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    pass

import typer

from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import init_env


def validate_node_id(node_id: str) -> None:
    """Validate whether node_id contains only URL-safe characters (whitelist approach).

    Validate with a whitelist: only letters, digits, underscores, hyphens, and dots are allowed.
    An empty string is treated as invalid input.

    Args:
        node_id: the node ID to validate

    Raises:
        ValueError: when node_id is empty or contains illegal characters
    """
    if not node_id:
        raise ValueError("node-id cannot be empty")

    # Whitelist: only letters, digits, underscores, hyphens, and dots are allowed
    import re

    if not re.match(r"^[a-zA-Z0-9_.\-]+$", node_id):
        raise ValueError(
            "node-id contains illegal characters. Only letters, digits, underscores, hyphens, and dots are allowed. Examples: node-001, worker.node_1"
        )


DEFAULT_GATEWAY_HOST = "127.0.0.1"
DEFAULT_GATEWAY_PORT = 8000
DEFAULT_FRONTEND_HOST = "127.0.0.1"
DEFAULT_FRONTEND_PORT = 5173
GATEWAY_READY_WAIT_SECONDS = 5
PROCESS_TERMINATE_TIMEOUT_SECONDS = 10
ROOT_MARKER_FILES = ("pyproject.toml",)
ROOT_MARKER_DIRECTORIES = ("src/haijunbot",)
FRONTEND_RELATIVE_PATH = Path("src/haijunbot/haijunbot_service/frontend")
MASTER_NODE_SECRET_RELATIVE_PATH = Path("node_mode/master_node_secret")
AUTO_GENERATED_SECRET_NBYTES = 24

app = typer.Typer(help="HaijunBot Service")
SINGLE_INSTANCE_LOCK_HANDLE = None  # type: Optional[TextIO]

init_env("")


class LoopAction(Enum):
    """Control actions for the service loop."""

    EXIT = "exit"
    RESTART = "restart"
    RESTART_GATEWAY_ONLY = "restart_gateway_only"


@dataclass
class ServiceConfig:
    """Service startup configuration."""

    project_root: Path
    frontend_root: Path
    gateway_host: str
    gateway_port: int
    frontend_host: str
    frontend_port: int
    node_mode: str
    node_id: Optional[str]
    master_url: Optional[str]
    node_secret: Optional[str]
    dev_mode: bool = False


@dataclass
class ServiceStatus:
    """Service status information (unified cross-platform format)."""

    is_running: bool
    is_enabled: bool  # whether auto-start is enabled
    pid: Optional[int] = None
    mode: Optional[str] = None  # "master" or "child"
    error_message: Optional[str] = None


@dataclass
class ServiceProcesses:
    """A running service process."""

    gateway_process: subprocess.Popen[bytes]
    frontend_process: Optional[subprocess.Popen[bytes]]


class ServiceBackend(ABC):
    """Abstract base class for the HaijunBot service backend.

    Defines a unified cross-platform service management interface, implemented by concrete platforms.
    """

    @abstractmethod
    def install(self, config: ServiceConfig) -> Tuple[bool, str]:
        """Install the service (create the auto-start mechanism).

        Args:
            config: service configuration

        Returns:
            (success, message): success flag and description message
        """
        pass

    @abstractmethod
    def uninstall(self, mode: Optional[str]) -> Tuple[bool, str]:
        """Uninstall the service (remove the auto-start mechanism).

        Args:
            mode: service mode ("master" or "child"); None means the current mode

        Returns:
            (success, message): success flag and description message
        """
        pass

    @abstractmethod
    def start(self, config: ServiceConfig) -> Tuple[bool, str]:
        """Start the service.

        Args:
            config: service configuration

        Returns:
            (success, message): success flag and description message
        """
        pass

    @abstractmethod
    def stop(self, mode: Optional[str]) -> Tuple[bool, str]:
        """Stop the service.

        Args:
            mode: service mode ("master" or "child"); None means the current mode

        Returns:
            (success, message): success flag and description message
        """
        pass

    @abstractmethod
    def restart(self, config: ServiceConfig) -> Tuple[bool, str]:
        """Restart the service.

        Args:
            config: service configuration

        Returns:
            (success, message): success flag and description message
        """
        pass

    @abstractmethod
    def status(self, mode: Optional[str]) -> ServiceStatus:
        """Query service status.

        Args:
            mode: service mode ("master" or "child"); None means query all modes

        Returns:
            ServiceStatus: service status information
        """
        pass

    @abstractmethod
    def switch_mode(self, target_mode: str, config: ServiceConfig) -> Tuple[bool, str]:
        """Switch the service mode.

        Args:
            target_mode: target mode ("master" or "child")
            config: service configuration

        Returns:
            (success, message): success flag and description message
        """
        pass

    @abstractmethod
    def is_current_mode(self, mode: str) -> bool:
        """Check the currently running service mode.

        Args:
            mode: the mode to check

        Returns:
            bool: whether the specified mode is currently running
        """
        pass


class WindowsTaskBackend(ServiceBackend):
    """Windows platform scheduled task service backend implementation.

    Use the schtasks command to manage auto-start (similar to systemd's enable/disable),
    Use PID files to track process state (similar to systemd's start/stop).
    """

    def __init__(self):
        """Initialize the Windows backend."""
        self._pid_dir = Path.home() / ".haijunbot" / "pids"
        self._pid_dir.mkdir(parents=True, exist_ok=True)

    def _get_task_name(self, mode: Optional[str]) -> str:
        """Get the scheduled task name.

        Args:
            mode: service mode ("master" or "child"); None means the current mode

        Returns:
            Scheduled task name (e.g. "HaijunBot-Master" or "HaijunBot-Child")
        """
        mode_lower = (mode or "master").lower()
        if mode_lower == "master":
            return "HaijunBot-Master"
        elif mode_lower == "child":
            return "HaijunBot-Child"
        else:
            return "HaijunBot-Master"

    def _get_pid_file(self, mode: str) -> Path:
        """Get the PID file path.

        Args:
            mode: service mode

        Returns:
            PID file path
        """
        return self._pid_dir / f"haijunbot-{mode.lower()}.pid"

    def _read_pid(self, mode: str) -> Optional[int]:
        """Read the PID file.

        Args:
            mode: service mode

        Returns:
            process ID, or None if the file does not exist or is invalid
        """
        pid_file = self._get_pid_file(mode)
        if not pid_file.exists():
            return None
        try:
            content = pid_file.read_text(encoding="utf-8").strip()
            pid = int(content)
            # Verify the process actually exists
            import subprocess

            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and str(pid) in result.stdout:
                return pid
            else:
                # Process does not exist; delete the PID file
                pid_file.unlink(missing_ok=True)
                return None
        except (ValueError, Exception):
            pid_file.unlink(missing_ok=True)
            return None

    def _write_pid(self, mode: str, pid: int) -> None:
        """Write the PID file.

        Args:
            mode: service mode
            pid: process ID
        """
        pid_file = self._get_pid_file(mode)
        pid_file.write_text(str(pid), encoding="utf-8")

    def _delete_pid(self, mode: str) -> None:
        """Delete the PID file.

        Args:
            mode: service mode
        """
        pid_file = self._get_pid_file(mode)
        pid_file.unlink(missing_ok=True)

    def install(self, config: ServiceConfig) -> Tuple[bool, str]:
        """Install the Windows scheduled task (to enable start on boot).

        Args:
            config: service configuration

        Returns:
            (success, message): success flag and description message
        """
        try:
            service_executable = shutil.which("haijunbot-service.exe")
            if service_executable is None:
                # Try without the .exe suffix
                service_executable = shutil.which("haijunbot-service")
            if service_executable is None:
                return False, "haijunbot-service executable not found"

            task_name = self._get_task_name(config.node_mode)

            # Build the command
            command = [
                service_executable,
                "run",
                "--gateway-host",
                config.gateway_host,
                "--gateway-port",
                str(config.gateway_port),
                "--frontend-host",
                config.frontend_host,
                "--frontend-port",
                str(config.frontend_port),
            ]
            if config.node_mode:
                command.extend(["--node-mode", config.node_mode])
            if config.node_id:
                command.extend(["--node-id", config.node_id])
            if config.master_url:
                command.extend(["--master-url", config.master_url])
            if config.node_secret:
                command.extend(["--node-secret", config.node_secret])

            # Convert to a string command (required by schtasks)
            command_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in command)

            # Create the scheduled task (start on logon)
            schtasks_cmd = [
                "schtasks",
                "/Create",
                "/TN",
                task_name,
                "/TR",
                command_str,
                "/SC",
                "ONLOGON",
                "/RL",
                "HIGHEST",
                "/F",  # overwrite an existing task
            ]

            result = subprocess.run(
                schtasks_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return True, f"Scheduled task created: {task_name}"
            else:
                return False, f"Failed to create scheduled task: {result.stderr.strip()}"
        except Exception as e:
            return False, f"Installation failed: {e}"

    def uninstall(self, mode: Optional[str]) -> Tuple[bool, str]:
        """Uninstall the Windows scheduled task.

        Args:
            mode: service mode ("master" or "child"); None means the current mode

        Returns:
            (success, message): success flag and description message
        """
        try:
            task_name = self._get_task_name(mode)

            # Stop the service first
            self.stop(mode)

            # Delete the scheduled task
            result = subprocess.run(
                ["schtasks", "/Delete", "/TN", task_name, "/F"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                # Delete the PID file
                self._delete_pid((mode or "master").lower())
                return True, f"Scheduled task deleted: {task_name}"
            else:
                return False, f"Failed to delete scheduled task: {result.stderr.strip()}"
        except Exception as e:
            return False, f"Uninstallation failed: {e}"

    def start(self, config: ServiceConfig) -> Tuple[bool, str]:
        """Start the Windows service (background process).

        Args:
            config: service configuration

        Returns:
            (success, message): success flag and description message
        """
        try:
            service_executable = shutil.which("haijunbot-service.exe")
            if service_executable is None:
                service_executable = shutil.which("haijunbot-service")
            if service_executable is None:
                return False, "haijunbot-service executable not found"

            mode_lower = (config.node_mode or "master").lower()

            # Check whether it is already running
            if self._read_pid(mode_lower) is not None:
                return False, f"{mode_lower} service is already running"

            # Build the command
            command = [
                service_executable,
                "run",
                "--gateway-host",
                config.gateway_host,
                "--gateway-port",
                str(config.gateway_port),
                "--frontend-host",
                config.frontend_host,
                "--frontend-port",
                str(config.frontend_port),
            ]
            if config.node_mode:
                command.extend(["--node-mode", config.node_mode])
            if config.node_id:
                command.extend(["--node-id", config.node_id])
            if config.master_url:
                command.extend(["--master-url", config.master_url])
            if config.node_secret:
                command.extend(["--node-secret", config.node_secret])

            # Start the process (detached mode)
            # Windows-specific constants; use getattr to avoid type-check errors
            CREATE_NEW_PROCESS_GROUP = getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200
            )
            DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            process = subprocess.Popen(
                command,
                cwd=config.project_root,
                creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
            )
            # Write the PID file
            self._write_pid(mode_lower, process.pid)
            return True, f"{mode_lower} service started (PID: {process.pid})"
        except Exception as e:
            return False, f"Failed to start: {e}"

    def stop(self, mode: Optional[str]) -> Tuple[bool, str]:
        """Stop the Windows service.

        Args:
            mode: service mode ("master" or "child"); None means the current mode

        Returns:
            (success, message): success flag and description message
        """
        try:
            mode_lower = (mode or "master").lower()
            pid = self._read_pid(mode_lower)

            if pid is None:
                # Simplification here: no PID is treated as not running
                return True, f"{mode_lower} service is not running"
            # Terminate the process
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 or "not exist" in result.stdout.lower():
                self._delete_pid(mode_lower)
                return True, f"{mode_lower} service stopped"
            else:
                return False, f"Failed to stop service: {result.stderr.strip()}"
        except Exception as e:
            return False, f"Failed to stop: {e}"

    def restart(self, config: ServiceConfig) -> Tuple[bool, str]:
        """Restart the Windows service.

        Args:
            config: service configuration

        Returns:
            (success, message): success flag and description message
        """
        mode_lower = (config.node_mode or "master").lower()

        # Stop first
        self.stop(mode_lower)
        time.sleep(2)

        # Then start
        return self.start(config)

    def status(self, mode: Optional[str]) -> ServiceStatus:
        """Query Windows service status.

        Args:
            mode: service mode ("master" or "child"); None means query all modes

        Returns:
            ServiceStatus: service status information
        """
        if mode is None:
            # Query all modes and return the first running one
            for m in ["master", "child"]:
                status = self.status(m)
                if status.is_running:
                    return status
            # None running; return the master status
            return self.status("master")

        mode_lower = mode.lower()

        # Check the PID file
        pid = self._read_pid(mode_lower)
        is_running = pid is not None

        # Check whether the scheduled task exists (equivalent to is_enabled)
        task_name = self._get_task_name(mode_lower)
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", task_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            is_enabled = result.returncode == 0
        except Exception:
            is_enabled = False

        return ServiceStatus(
            is_running=is_running,
            is_enabled=is_enabled,
            pid=pid,
            mode=mode_lower,
            error_message=None,
        )

    def switch_mode(self, target_mode: str, config: ServiceConfig) -> Tuple[bool, str]:
        """Switch the Windows service mode.

        Args:
            target_mode: target mode ("master" or "child")
            config: service configuration

        Returns:
            (success, message): success flag and description message
        """
        target_mode_lower = target_mode.lower()

        # Stop the currently running service
        for mode in ["master", "child"]:
            self.stop(mode)

        # Update the mode in the configuration
        config.node_mode = target_mode_lower

        # Start the target mode
        success, message = self.start(config)
        if not success:
            return False, message

        return True, f"Switched to {target_mode_lower} mode"

    def is_current_mode(self, mode: str) -> bool:
        """Check whether the specified mode is currently running.

        Args:
            mode: the mode to check

        Returns:
            bool: whether the specified mode is currently running
        """
        pid = self._read_pid(mode.lower())
        return pid is not None


def _detect_platform() -> str:
    """Detect the currently running platform.

    Returns:
        'windows' or 'linux'
    """
    import sys

    if sys.platform.startswith("win"):
        return "windows"
    else:
        return "linux"


def create_backend() -> ServiceBackend:
    """Create the appropriate service backend for the current platform.

    Returns:
        ServiceBackend: the backend instance for the platform
    """
    platform = _detect_platform()
    if platform == "windows":
        return WindowsTaskBackend()
    else:
        return SystemdBackend()


class SystemdBackend(ServiceBackend):
    """Linux platform systemd service backend implementation."""

    def install(self, config: ServiceConfig) -> Tuple[bool, str]:
        """Install the systemd user service.

        Args:
            config: service configuration

        Returns:
            (success, message): success flag and description message
        """
        try:
            service_executable = shutil.which("haijunbot-service")
            if service_executable is None:
                return False, "haijunbot-service executable not found"

            # Build the service file content
            current_path = os.environ.get("PATH", "")
            # Ensure PATH includes the uv tool install dir (~/.local/bin) and the haijunbot-service directory
            extra_paths = [
                os.path.expanduser("~/.local/bin"),
                os.path.dirname(service_executable),
            ]
            for p in extra_paths:
                if p and p not in current_path.split(":"):
                    current_path = f"{p}:{current_path}" if current_path else p
            proxy_env_vars = []
            for var_name in [
                "http_proxy",
                "HTTP_PROXY",
                "https_proxy",
                "HTTPS_PROXY",
                "no_proxy",
                "NO_PROXY",
                "ftp_proxy",
                "FTP_PROXY",
                "socks_proxy",
                "SOCKS_PROXY",
            ]:
                value = os.environ.get(var_name)
                if value:
                    proxy_env_vars.append(f"Environment={var_name}={value}")

            proxy_env_section = "\n".join(proxy_env_vars) if proxy_env_vars else ""
            service_name = _get_service_name(config.node_mode)
            mode_display = config.node_mode or "master"

            service_content = """[Unit]
Description=HaijunBot Service ({mode})
After=network.target

[Service]
Type=simple
Environment=PATH={path}
{proxy_env}
WorkingDirectory={project_root}
ExecStart={service_executable} run --gateway-host {gateway_host} --gateway-port {gateway_port} --frontend-host {frontend_host} --frontend-port {frontend_port}""".format(
                mode=mode_display,
                path=current_path,
                project_root=config.project_root,
                service_executable=service_executable,
                gateway_host=config.gateway_host,
                gateway_port=config.gateway_port,
                frontend_host=config.frontend_host,
                frontend_port=config.frontend_port,
                proxy_env=proxy_env_section,
            )

            # Add optional arguments
            if config.node_mode:
                service_content += " --node-mode {}".format(config.node_mode)
            if config.node_id:
                service_content += " --node-id {}".format(config.node_id)
            if config.master_url:
                service_content += " --master-url {}".format(config.master_url)
            if config.node_secret:
                service_content += " --node-secret {}".format(config.node_secret)

            service_content += """
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
"""

            # Write the service file
            systemd_user_dir = Path.home() / ".config" / "systemd" / "user"
            systemd_user_dir.mkdir(parents=True, exist_ok=True)
            service_file_path = systemd_user_dir / service_name
            service_file_path.write_text(service_content, encoding="utf-8")

            # daemon-reload
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            return True, f"systemd service installed: {service_file_path}"
        except Exception as e:
            return False, f"Installation failed: {e}"

    def uninstall(self, mode: Optional[str]) -> Tuple[bool, str]:
        """Uninstall the systemd service (delete the service file).

        Args:
            mode: service mode ("master" or "child"); None means the current mode

        Returns:
            (success, message): success flag and description message
        """
        try:
            service_name = _get_service_name(mode)
            systemd_user_dir = Path.home() / ".config" / "systemd" / "user"
            service_file_path = systemd_user_dir / service_name

            if not service_file_path.exists():
                return False, f"Service file does not exist: {service_file_path}"

            # Stop and disable the service first
            _run_systemctl_action("stop", mode)
            _run_systemctl_enable_disable("disable", mode)

            # Delete the service file
            service_file_path.unlink()

            # daemon-reload
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            return True, f"systemd service uninstalled: {service_file_path}"
        except Exception as e:
            return False, f"Uninstallation failed: {e}"

    def start(self, config: ServiceConfig) -> Tuple[bool, str]:
        """Start the systemd service.

        Args:
            config: service configuration

        Returns:
            (success, message): success flag and description message
        """
        mode_lower = (config.node_mode or "master").lower()

        if _run_systemctl_action("start", mode_lower):
            return True, f"{mode_lower} service started"
        else:
            return False, f"Failed to start {mode_lower} service"

    def stop(self, mode: Optional[str]) -> Tuple[bool, str]:
        """Stop the systemd service.

        Args:
            mode: service mode ("master" or "child"); None means the current mode

        Returns:
            (success, message): success flag and description message
        """
        mode_lower = (mode or "master").lower()

        if _run_systemctl_action("stop", mode_lower):
            return True, f"{mode_lower} service stopped"
        else:
            return False, f"Failed to stop {mode_lower} service"

    def restart(self, config: ServiceConfig) -> Tuple[bool, str]:
        """Restart the systemd service.

        Args:
            config: service configuration

        Returns:
            (success, message): success flag and description message
        """
        mode_lower = (config.node_mode or "master").lower()

        # Stop first
        _run_systemctl_action("stop", mode_lower)
        time.sleep(1)

        # Then start
        if _run_systemctl_action("start", mode_lower):
            return True, f"{mode_lower} service restarted"
        else:
            return False, f"Failed to restart {mode_lower} service"

    def status(self, mode: Optional[str]) -> ServiceStatus:
        """Query systemd service status.

        Args:
            mode: service mode ("master" or "child"); None means query all modes

        Returns:
            ServiceStatus: service status information
        """
        if mode is None:
            # Query all modes and return the first running one
            for m in ["master", "child"]:
                status = self.status(m)
                if status.is_running:
                    return status
            # None running; return the master status
            return self.status("master")

        mode_lower = mode.lower()
        service_name = _get_service_name(mode_lower)

        # Check whether it is running
        is_running = _run_systemctl_action("is-active", mode_lower)

        # Check whether it is enabled
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-enabled", service_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            is_enabled = result.returncode == 0
        except Exception:
            is_enabled = False

        # Get the PID
        pid = None
        if is_running:
            try:
                result = subprocess.run(
                    ["systemctl", "--user", "show", service_name, "--property=MainPID"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and "=" in result.stdout:
                    pid_str = result.stdout.strip().split("=")[1]
                    pid = (
                        int(pid_str) if pid_str.isdigit() and int(pid_str) > 0 else None
                    )
            except Exception as e:
                save_exception(e, module="haijunbot_service.eli", function="status")
                pass

        return ServiceStatus(
            is_running=is_running,
            is_enabled=is_enabled,
            pid=pid,
            mode=mode_lower,
            error_message=None,
        )

    def switch_mode(self, target_mode: str, config: ServiceConfig) -> Tuple[bool, str]:
        """Switch the systemd service mode.

        Args:
            target_mode: target mode ("master" or "child")
            config: service configuration

        Returns:
            (success, message): success flag and description message
        """
        target_mode_lower = target_mode.lower()
        other_mode = "child" if target_mode_lower == "master" else "master"

        # Stop the currently running service
        for mode in ["master", "child"]:
            if _run_systemctl_action("is-active", mode):
                _run_systemctl_action("stop", mode)

        # Start the target mode
        if not _run_systemctl_action("start", target_mode_lower):
            return False, f"Failed to start {target_mode_lower} service"

        # Enable the target mode and disable the other
        _run_systemctl_enable_disable("enable", target_mode_lower)
        _run_systemctl_enable_disable("disable", other_mode)

        return True, f"Switched to {target_mode_lower} mode"

    def is_current_mode(self, mode: str) -> bool:
        """Check whether the specified mode is currently running.

        Args:
            mode: the mode to check

        Returns:
            bool: whether the specified mode is currently running
        """
        return _run_systemctl_action("is-active", mode.lower())


class ServiceController:
    """Manage service start/stop and signal-driven loop control."""

    def __init__(self, config: ServiceConfig) -> None:
        self._config = config
        self._requested_action = LoopAction.EXIT
        self._signal_received = False

    def request_exit(self, _signum: int, _frame: object) -> None:
        """Exit the loop when a termination signal is received."""
        self._requested_action = LoopAction.EXIT
        self._signal_received = True

    def request_restart(self, _signum: int, _frame: object) -> None:
        """Restart the service when a restart signal is received."""
        self._requested_action = LoopAction.RESTART
        self._signal_received = True

    def request_restart_gateway_only(self, _signum: int, _frame: object) -> None:
        """On signal, restart only the gateway service, keeping the frontend running."""
        self._requested_action = LoopAction.RESTART_GATEWAY_ONLY
        self._signal_received = True

    def run_forever(self) -> None:
        """Run the service in an infinite loop until an exit signal is received."""
        frontend_process: Optional[subprocess.Popen[bytes]] = None
        while True:
            self._signal_received = False
            self._requested_action = LoopAction.EXIT
            processes = self._start_services(frontend_process)
            next_action = self._wait_for_signal_or_process_exit(processes)

            if next_action == LoopAction.RESTART_GATEWAY_ONLY:
                # Restart only the gateway, keeping the frontend running
                PrettyOutput.auto_print("🔄 Restarting only the gateway service, keeping the frontend running")
                frontend_process = processes.frontend_process
                self._stop_gateway_only(processes)
                continue

            # Fully stop all services
            frontend_process = None
            self._stop_services(processes)
            if next_action == LoopAction.EXIT:
                PrettyOutput.auto_print("🛑 Service stopped")
                return
            PrettyOutput.auto_print("🔄 Restart signal received, restarting the service")

    def _start_services(
        self, existing_frontend: Optional[subprocess.Popen[bytes]] = None
    ) -> ServiceProcesses:
        """Start the service processes according to the node mode.

        Args:
            existing_frontend: an existing frontend process (used when restarting only the gateway)
        """
        self._validate_runtime_dependencies()

        if existing_frontend is not None:
            PrettyOutput.auto_print("🚀 Restarting the gateway service (keeping the frontend running)")
        else:
            PrettyOutput.auto_print("🚀 Starting HaijunBot service")
        PrettyOutput.auto_print(f"📁 Project root: {self._config.project_root}")

        gateway_process = self._start_gateway_process()
        self._wait_for_gateway_ready()

        frontend_process = existing_frontend
        if frontend_process is None and self._config.node_mode == "master":
            self._prepare_frontend_assets()
            frontend_process = self._start_frontend_process()

        self._print_service_summary(
            gateway_pid=gateway_process.pid,
            frontend_pid=frontend_process.pid if frontend_process else None,
        )
        return ServiceProcesses(
            gateway_process=gateway_process,
            frontend_process=frontend_process,
        )

    def _wait_for_signal_or_process_exit(
        self, processes: ServiceProcesses
    ) -> LoopAction:
        """Wait for a signal or a child process exit, and return the next action."""
        while True:
            if self._signal_received:
                return self._requested_action
            if processes.gateway_process.poll() is not None:
                PrettyOutput.auto_print("⚠️ Gateway service exited, HaijunBot Service is about to stop")
                return LoopAction.EXIT
            if (
                processes.frontend_process is not None
                and processes.frontend_process.poll() is not None
            ):
                PrettyOutput.auto_print("⚠️ Frontend service exited, HaijunBot Service is about to stop")
                return LoopAction.EXIT
            time.sleep(1)

    def _validate_runtime_dependencies(self) -> None:
        """Validate the runtime dependency commands."""
        self._require_command("python", "Python environment not found")
        self._require_command("hwg", "hwg command not found; make sure HaijunBot is installed correctly")
        if self._config.node_mode == "master":
            self._require_command("npm", "npm environment not found")

    def _require_command(self, command_name: str, error_message: str) -> None:
        """Ensure the command exists."""
        if self._find_command(command_name) is None:
            PrettyOutput.auto_print(f"❌ {error_message}")
            raise typer.Exit(code=1)

    def _find_command(self, command_name: str) -> Optional[str]:
        """Find the full path of a command, preferring PATH then common user directories."""
        found = shutil.which(command_name)
        if found:
            return found
        # Look it up via bash loading the user environment (overrides the user shell PATH)
        try:
            result = subprocess.run(
                ["bash", "-lc", f"which {command_name}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        # Also check common user bin directories
        candidates = [
            Path.home() / ".local" / "bin" / command_name,
            Path(sys.executable).parent / command_name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None

    def _start_gateway_process(self) -> subprocess.Popen[bytes]:
        """Start the Web Gateway process."""
        PrettyOutput.auto_print("⏳ Starting gateway service")
        jwg_path = self._find_command("hwg")
        if jwg_path is None:
            PrettyOutput.auto_print("❌ hwg command not found; make sure HaijunBot is installed correctly")
            raise typer.Exit(code=1)
        command = [
            jwg_path,
            "--host",
            self._config.gateway_host,
            "--port",
            str(self._config.gateway_port),
        ]
        if self._config.node_mode:
            command.extend(["--node-mode", self._config.node_mode])
        if self._config.node_id:
            command.extend(["--node-id", self._config.node_id])
        if self._config.master_url:
            command.extend(["--master-url", self._config.master_url])
        if self._config.node_secret:
            command.extend(["--node-secret", self._config.node_secret])
        process = subprocess.Popen(command, cwd=self._config.project_root)
        PrettyOutput.auto_print(f"✅ Gateway started (PID: {process.pid})")
        return process

    def _wait_for_gateway_ready(self) -> None:
        """Wait for the gateway service to finish starting."""
        PrettyOutput.auto_print("⏳ Waiting for the gateway service to be ready")
        time.sleep(GATEWAY_READY_WAIT_SECONDS)

    def _prepare_frontend_assets(self) -> None:
        """Install dependencies and build the frontend artifacts."""
        PrettyOutput.auto_print("⏳ Installing frontend dependencies")
        self._run_command(["npm", "install"], self._config.frontend_root)
        PrettyOutput.auto_print("✅ Frontend dependencies installed")
        if not self._config.dev_mode:
            PrettyOutput.auto_print("⏳ Building frontend release artifacts")
            self._run_command(["npm", "run", "build"], self._config.frontend_root)
            PrettyOutput.auto_print("✅ Frontend release build completed")
        else:
            PrettyOutput.auto_print("⏩ Development mode skips the build step")

    def _start_frontend_process(self) -> subprocess.Popen[bytes]:
        """Start the frontend service."""
        if self._config.dev_mode:
            PrettyOutput.auto_print("⏳ Starting frontend dev service (hot-reload mode)")
            command = [
                "npm",
                "run",
                "dev",
                "--",
                "--host",
                self._config.frontend_host,
                "--port",
                str(self._config.frontend_port),
            ]
        else:
            PrettyOutput.auto_print("⏳ Starting frontend release service")
            command = [
                "npm",
                "run",
                "preview",
                "--",
                "--host",
                self._config.frontend_host,
                "--port",
                str(self._config.frontend_port),
            ]
        process = subprocess.Popen(command, cwd=self._config.frontend_root)
        mode_name = "development" if self._config.dev_mode else "release"
        PrettyOutput.auto_print(f"✅ Frontend {mode_name} service started (PID: {process.pid})")
        return process

    def _run_command(self, command: list[str], cwd: Path) -> None:
        """Run a foreground command and exit on failure."""
        try:
            subprocess.run(command, cwd=cwd, check=True)
        except subprocess.CalledProcessError as error:
            PrettyOutput.auto_print(
                f"❌ Command execution failed: {' '.join(command)} (exit code: {error.returncode})"
            )
            raise typer.Exit(code=error.returncode) from error

    def _stop_services(self, processes: ServiceProcesses) -> None:
        """Stop all service processes."""
        PrettyOutput.auto_print("🛑 Stopping services")
        if processes.frontend_process is not None:
            self._terminate_process(processes.frontend_process, "frontend service")
        self._terminate_process(processes.gateway_process, "gateway service")

    def _stop_gateway_only(self, processes: ServiceProcesses) -> None:
        """Stop only the gateway service, keeping the frontend running."""
        PrettyOutput.auto_print("🛑 Stopping gateway service")
        self._terminate_process(processes.gateway_process, "gateway service")

    def _terminate_process(
        self, process: subprocess.Popen[bytes], process_name: str
    ) -> None:
        """Terminate a single child process."""
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=PROCESS_TERMINATE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            PrettyOutput.auto_print(f"⚠️ Force-terminating {process_name}")
            process.kill()
            process.wait()

    def _print_service_summary(
        self, gateway_pid: int, frontend_pid: Optional[int]
    ) -> None:
        """Print a startup result summary."""
        PrettyOutput.auto_print(
            f"ℹ️ Gateway: http://{self._config.gateway_host}:{self._config.gateway_port} (PID: {gateway_pid})"
        )
        if frontend_pid is not None:
            PrettyOutput.auto_print(
                f"ℹ️ Frontend: http://{self._config.frontend_host}:{self._config.frontend_port} (PID: {frontend_pid})"
            )
        else:
            PrettyOutput.auto_print("ℹ️ Frontend: not started in child mode")
        PrettyOutput.auto_print(f"ℹ️ Node mode: {self._config.node_mode}")
        PrettyOutput.auto_print("ℹ️ Press Ctrl+C to stop the service")


def resolve_project_root() -> Path:
    """Automatically locate the HaijunBot source root from the editable install path."""
    current_path = Path(__file__).resolve()
    for candidate_root in (current_path.parent, *current_path.parents):
        if is_project_root(candidate_root):
            return candidate_root
    PrettyOutput.auto_print(
        "❌ HaijunBot source root not found; make sure it was installed with 'uv tool install -e .'"
    )
    raise typer.Exit(code=1)


def is_project_root(candidate_root: Path) -> bool:
    """Determine whether the directory is the HaijunBot project root."""
    has_marker_files = all(
        (candidate_root / marker).exists() for marker in ROOT_MARKER_FILES
    )
    has_marker_directories = all(
        (candidate_root / marker).exists() for marker in ROOT_MARKER_DIRECTORIES
    )
    return has_marker_files and has_marker_directories


def get_master_node_secret_path() -> Path:
    """Return the persistence file path for the master node key."""
    return Path(get_data_dir()) / MASTER_NODE_SECRET_RELATIVE_PATH


def load_or_create_master_node_secret() -> tuple[str, bool]:
    """Read or create the master node key."""
    secret_path = get_master_node_secret_path()
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    if secret_path.exists():
        existing_secret = secret_path.read_text(encoding="utf-8").strip()
        if existing_secret:
            return existing_secret, False
    generated_secret = secrets.token_urlsafe(AUTO_GENERATED_SECRET_NBYTES)
    secret_path.write_text(f"{generated_secret}\n", encoding="utf-8")
    try:
        os.chmod(secret_path, 0o600)
    except OSError:
        pass
    return generated_secret, True


GATEWAY_TOKEN_RELATIVE_PATH = Path("gateway_token")
JWT_SECRET_RELATIVE_PATH = Path("jwt_secret")


def load_or_create_gateway_token() -> str:
    """Read or create the Gateway Token (HAIJUNBOT_AUTH_TOKEN), persisted to the data directory.

    Inherited by the hwg subprocess to keep client tokens valid after a gateway restart.
    """
    path = Path(get_data_dir()) / GATEWAY_TOKEN_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    token = str(uuid.uuid4())
    path.write_text(f"{token}\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return token


def load_or_create_jwt_secret() -> str:
    """Read or create the JWT signing key (HAIJUNBOT_JWT_SECRET), persisted to the data directory.

    Inherited by the hwg subprocess to keep client JWT tokens verifiable after a gateway restart.
    """
    path = Path(get_data_dir()) / JWT_SECRET_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    secret = secrets.token_urlsafe(AUTO_GENERATED_SECRET_NBYTES)
    path.write_text(f"{secret}\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return secret


def ensure_service_tokens() -> None:
    """Generate/load and persist the token in the service process, writing it to the environment for the hwg subprocess to inherit.

    If the environment variable is explicitly set (e.g. manually by the user), respect the user configuration and do not overwrite it.
    """
    if not os.environ.get("HAIJUNBOT_AUTH_TOKEN"):
        os.environ["HAIJUNBOT_AUTH_TOKEN"] = load_or_create_gateway_token()
    if not os.environ.get("HAIJUNBOT_JWT_SECRET"):
        os.environ["HAIJUNBOT_JWT_SECRET"] = load_or_create_jwt_secret()


def build_service_config(
    gateway_host: Optional[str] = None,
    gateway_port: Optional[int] = None,
    frontend_host: Optional[str] = None,
    frontend_port: Optional[int] = None,
    node_mode: Optional[str] = None,
    node_id: Optional[str] = None,
    master_url: Optional[str] = None,
    node_secret: Optional[str] = None,
    dev_mode: bool = False,
) -> ServiceConfig:
    """Build the service configuration from ELI arguments and environment variables."""
    project_root = resolve_project_root()
    frontend_root = project_root / FRONTEND_RELATIVE_PATH
    resolved_gateway_host = gateway_host or os.getenv(
        "HAIJUNBOT_GATEWAY_HOST", DEFAULT_GATEWAY_HOST
    )
    resolved_gateway_port = gateway_port or int(
        os.getenv("HAIJUNBOT_GATEWAY_PORT", str(DEFAULT_GATEWAY_PORT))
    )
    resolved_frontend_host = frontend_host or os.getenv(
        "HAIJUNBOT_FRONTEND_HOST", DEFAULT_FRONTEND_HOST
    )
    resolved_frontend_port = frontend_port or int(
        os.getenv("HAIJUNBOT_FRONTEND_PORT", str(DEFAULT_FRONTEND_PORT))
    )
    resolved_node_mode = node_mode or os.getenv("HAIJUNBOT_NODE_MODE", "master")
    resolved_node_id = node_id or os.getenv("HAIJUNBOT_NODE_ID") or None
    # Validate whether node_id contains URL-unsafe characters
    if resolved_node_id:
        validate_node_id(resolved_node_id)
    resolved_master_url = master_url or os.getenv("HAIJUNBOT_MASTER_URL") or None
    resolved_node_secret = node_secret or os.getenv("HAIJUNBOT_NODE_SECRET") or None
    resolved_dev_mode = dev_mode or os.getenv("HAIJUNBOT_DEV_MODE", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    if resolved_gateway_host is None:
        resolved_gateway_host = DEFAULT_GATEWAY_HOST
    # The child node gateway may only listen on a loopback address: a child node has no local auth data and does not make permission decisions on its own,
    # binding to a non-loopback address would expose the node as an unauthenticated entry point.
    if resolved_node_mode == "child" and resolved_gateway_host not in (
        "127.0.0.1",
        "localhost",
        "::1",
    ):
        PrettyOutput.auto_print(
            f"⚠️ The child node gateway may only listen on a loopback address; ignoring gateway-host={resolved_gateway_host},"
            f"Forcing {DEFAULT_GATEWAY_HOST}"
        )
        resolved_gateway_host = DEFAULT_GATEWAY_HOST
    if resolved_frontend_host is None:
        resolved_frontend_host = DEFAULT_FRONTEND_HOST
    if resolved_node_mode is None:
        resolved_node_mode = "master"
    if resolved_node_mode == "master" and not resolved_node_secret:
        resolved_node_secret, secret_created = load_or_create_master_node_secret()
        secret_path = get_master_node_secret_path()
        if secret_created:
            PrettyOutput.auto_print(
                "🔐 No node-secret passed in master mode; generated and saved automatically"
            )
        else:
            PrettyOutput.auto_print(
                "🔐 No node-secret passed in master mode; loaded the saved key"
            )
        PrettyOutput.auto_print(f"🔑 node-secret: {resolved_node_secret}")
        PrettyOutput.auto_print(f"📄 Key file: {secret_path}")
    return ServiceConfig(
        project_root=project_root,
        frontend_root=frontend_root,
        gateway_host=resolved_gateway_host,
        gateway_port=resolved_gateway_port,
        frontend_host=resolved_frontend_host,
        frontend_port=resolved_frontend_port,
        node_mode=resolved_node_mode,
        node_id=resolved_node_id,
        master_url=resolved_master_url,
        node_secret=resolved_node_secret,
        dev_mode=resolved_dev_mode,
    )


def get_single_instance_lock_path() -> Path:
    """Return the service instance lock file path for the current user."""
    if os.name == "nt":
        # Windows: use username instead of uid
        import getpass

        user_id = getpass.getuser()
    else:
        user_id = str(os.getuid())
    return Path(get_data_dir()) / f"haijunbot-service-{user_id}.lock"


def release_single_instance_lock() -> None:
    """Release the service instance lock for the current user."""
    global SINGLE_INSTANCE_LOCK_HANDLE
    if SINGLE_INSTANCE_LOCK_HANDLE is None:
        return
    SINGLE_INSTANCE_LOCK_HANDLE.close()
    SINGLE_INSTANCE_LOCK_HANDLE = None


def acquire_single_instance_lock() -> None:
    """Acquire the service instance lock for the current user, exiting on failure."""
    global SINGLE_INSTANCE_LOCK_HANDLE
    lock_file_path = get_single_instance_lock_path()
    lock_file_path.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = open(lock_file_path, "w", encoding="utf-8")
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        lock_handle.close()
        PrettyOutput.auto_print("❌ The current user already has a haijunbot-service instance running")
        raise typer.Exit(code=1)
    service_pid = os.getpid()
    lock_handle.write(f"{service_pid}\n")
    lock_handle.flush()
    SINGLE_INSTANCE_LOCK_HANDLE = lock_handle
    atexit.register(release_single_instance_lock)


# Windows restart-command TCP port (kept consistent with app.py / node_manager.py)
_RESTART_COMMAND_TCP_PORT = 18766


def _start_restart_command_server(controller: ServiceController) -> None:
    """Windows: start the TCP command server to receive restart commands.

    Run in a daemon thread, listening on 127.0.0.1:18766 to receive the following commands:
    - RESTART_ALL: trigger a full restart (equivalent to SIGUSR1)
    - RESTART_GATEWAY_ONLY: restart only the gateway (equivalent to SIGUSR2)
    """
    import socket as _socket

    _stop_event = threading.Event()

    def _serve() -> None:
        server = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        server.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", _RESTART_COMMAND_TCP_PORT))
        server.listen(1)
        server.settimeout(1.0)  # allow graceful exit
        try:
            while not _stop_event.is_set():
                try:
                    conn, _ = server.accept()
                    try:
                        data = conn.recv(1024).decode("utf-8").strip()
                        if data == "RESTART_ALL":
                            controller.request_restart(0, None)
                        elif data == "RESTART_GATEWAY_ONLY":
                            controller.request_restart_gateway_only(0, None)
                    finally:
                        conn.close()
                except _socket.timeout:
                    continue
                except OSError:
                    break
        finally:
            server.close()

    t = threading.Thread(target=_serve, daemon=True, name="restart-cmd-server")
    t.start()


def run_service(config: ServiceConfig) -> None:
    """Start the HaijunBot service loop."""
    acquire_single_instance_lock()
    # Generate/load and persist the token in the service process, writing it to the environment for the hwg subprocess to inherit,
    # Ensure client tokens remain valid after the gateway restarts.
    ensure_service_tokens()
    controller = ServiceController(config)
    signal.signal(signal.SIGINT, controller.request_exit)
    signal.signal(signal.SIGTERM, controller.request_exit)
    if sys.platform != "win32":
        signal.signal(signal.SIGUSR1, controller.request_restart)
        signal.signal(signal.SIGUSR2, controller.request_restart_gateway_only)
    else:
        # Windows: SIGUSR1/SIGUSR2 are unavailable; trigger restarts via the TCP command channel
        _start_restart_command_server(controller)
    controller.run_forever()


@app.command(name="install")
def install_command(
    gateway_host: Optional[str] = typer.Option(
        None,
        "--gateway-host",
        help="Gateway listen address (default overridable by HAIJUNBOT_GATEWAY_HOST)",
    ),
    gateway_port: Optional[int] = typer.Option(
        None,
        "--gateway-port",
        help="Gateway listen port (default overridable by HAIJUNBOT_GATEWAY_PORT)",
    ),
    frontend_host: Optional[str] = typer.Option(
        None,
        "--frontend-host",
        help="Frontend preview service listen address (default overridable by HAIJUNBOT_FRONTEND_HOST)",
    ),
    frontend_port: Optional[int] = typer.Option(
        None,
        "--frontend-port",
        help="Frontend preview service listen port (default overridable by HAIJUNBOT_FRONTEND_PORT)",
    ),
    node_mode: Optional[str] = typer.Option(
        None,
        "--node-mode",
        help="Node mode: master or child (default overridable by HAIJUNBOT_NODE_MODE)",
    ),
    node_id: Optional[str] = typer.Option(
        None,
        "--node-id",
        help="Current node ID (default overridable by HAIJUNBOT_NODE_ID)",
    ),
    master_url: Optional[str] = typer.Option(
        None,
        "--master-url",
        help="Master node address (used in child mode; default overridable by HAIJUNBOT_MASTER_URL)",
    ),
    node_secret: Optional[str] = typer.Option(
        None,
        "--node-secret",
        help="Master/child shared secret (default overridable by HAIJUNBOT_NODE_SECRET)",
    ),
) -> None:
    """Install HaijunBot Service as a systemd user service."""
    config = build_service_config(
        gateway_host=gateway_host,
        gateway_port=gateway_port,
        frontend_host=frontend_host,
        frontend_port=frontend_port,
        node_mode=node_mode,
        node_id=node_id,
        master_url=master_url,
        node_secret=node_secret,
    )
    _install_systemd_service(config)


@app.command(name="run")
def run_command(
    gateway_host: Optional[str] = typer.Option(
        None,
        "--gateway-host",
        help="Gateway listen address (default overridable by HAIJUNBOT_GATEWAY_HOST)",
    ),
    gateway_port: Optional[int] = typer.Option(
        None,
        "--gateway-port",
        help="Gateway listen port (default overridable by HAIJUNBOT_GATEWAY_PORT)",
    ),
    frontend_host: Optional[str] = typer.Option(
        None,
        "--frontend-host",
        help="Frontend preview service listen address (default overridable by HAIJUNBOT_FRONTEND_HOST)",
    ),
    frontend_port: Optional[int] = typer.Option(
        None,
        "--frontend-port",
        help="Frontend preview service listen port (default overridable by HAIJUNBOT_FRONTEND_PORT)",
    ),
    node_mode: Optional[str] = typer.Option(
        None,
        "--node-mode",
        help="Node mode: master or child (default overridable by HAIJUNBOT_NODE_MODE)",
    ),
    node_id: Optional[str] = typer.Option(
        None,
        "--node-id",
        help="Current node ID (default overridable by HAIJUNBOT_NODE_ID)",
    ),
    master_url: Optional[str] = typer.Option(
        None,
        "--master-url",
        help="Master node address (used in child mode; default overridable by HAIJUNBOT_MASTER_URL)",
    ),
    node_secret: Optional[str] = typer.Option(
        None,
        "--node-secret",
        help="Master/child shared secret (default overridable by HAIJUNBOT_NODE_SECRET)",
    ),
    dev_mode: bool = typer.Option(
        False,
        "--dev",
        help="Development mode: start the frontend in dev mode (hot reload)",
    ),
) -> None:
    """Run HaijunBot Service directly (not managed by systemd)."""
    config = build_service_config(
        gateway_host=gateway_host,
        gateway_port=gateway_port,
        frontend_host=frontend_host,
        frontend_port=frontend_port,
        node_mode=node_mode,
        node_id=node_id,
        master_url=master_url,
        node_secret=node_secret,
        dev_mode=dev_mode,
    )
    run_service(config)


@app.command(name="start")
def start_service_command(
    mode: str = typer.Argument(
        ...,
        help="Service mode to start: master or child",
    ),
) -> None:
    """Start the systemd-managed HaijunBot service.

    Start the systemd service corresponding to the specified mode (haijunbot-master.service or haijunbot-child.service),
    and automatically enable that service while disabling the other mode's service.
    """
    mode_lower = mode.lower()
    if mode_lower not in ["master", "child"]:
        PrettyOutput.auto_print(f"❌ Invalid mode: {mode}. Please use 'master' or 'child'")
        raise typer.Exit(code=1)

    service_name = _get_service_name(mode_lower)
    PrettyOutput.auto_print(f"🚀 Starting {mode_lower} service: {service_name}")

    # Run daemon-reload first to ensure systemd recognizes newly created or modified service files
    try:
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as e:
        PrettyOutput.auto_print(f"⚠ daemon-reload failed: {e}")

    # Start the service
    if not _run_systemctl_action("start", mode_lower):
        PrettyOutput.auto_print(f"💡 Please run manually: systemctl --user start {service_name}")
        raise typer.Exit(code=1)

    PrettyOutput.auto_print(f"✅ {mode_lower} service started")

    # Enable the current service
    PrettyOutput.auto_print(f"🔧 Enabling {mode_lower} service...")
    if _run_systemctl_enable_disable("enable", mode_lower):
        PrettyOutput.auto_print(f"✅ {mode_lower} service enabled (start on boot)")
    else:
        PrettyOutput.auto_print(f"⚠ Failed to enable {mode_lower} service, but it is still running")

    # Stop the other mode's service first (to avoid port conflicts or single-instance lock)
    other_mode = "child" if mode_lower == "master" else "master"
    if _run_systemctl_action("is-active", other_mode):
        PrettyOutput.auto_print(f"🛑 Stopping {other_mode} service...")
        if _run_systemctl_action("stop", other_mode):
            PrettyOutput.auto_print(f"✅ {other_mode} service stopped")
        else:
            PrettyOutput.auto_print(f"⚠ Failed to stop {other_mode} service")

    # Disable the other mode's service
    PrettyOutput.auto_print(f"🔧 Disabling {other_mode} service...")
    if _run_systemctl_enable_disable("disable", other_mode):
        PrettyOutput.auto_print(f"✅ {other_mode} service disabled")
    else:
        PrettyOutput.auto_print(f"⚠ Failed to disable {other_mode} service")


@app.command(name="stop")
def stop_service_command(
    mode: str = typer.Argument(
        ...,
        help="Service mode to stop: master or child",
    ),
) -> None:
    """Stop the systemd-managed HaijunBot service.

    Stop the systemd service corresponding to the specified mode (haijunbot-master.service or haijunbot-child.service),
    and automatically disable that service.
    """
    mode_lower = mode.lower()
    if mode_lower not in ["master", "child"]:
        PrettyOutput.auto_print(f"❌ Invalid mode: {mode}. Please use 'master' or 'child'")
        raise typer.Exit(code=1)

    service_name = _get_service_name(mode_lower)
    PrettyOutput.auto_print(f"🛑 Stopping {mode_lower} service: {service_name}")

    # Stop the service
    if not _run_systemctl_action("stop", mode_lower):
        PrettyOutput.auto_print(f"💡 Please run manually: systemctl --user stop {service_name}")
        raise typer.Exit(code=1)

    PrettyOutput.auto_print(f"✅ {mode_lower}  service stopped")

    # Disable the service
    PrettyOutput.auto_print(f"🔧 Disabling {mode_lower} service...")
    if _run_systemctl_enable_disable("disable", mode_lower):
        PrettyOutput.auto_print(f"✅ {mode_lower} service disabled")
    else:
        PrettyOutput.auto_print(f"⚠ Failed to disable {mode_lower} service, but it has stopped")


@app.command(name="switch")
def switch_service_command(
    target_mode: str = typer.Argument(
        ...,
        help="Target mode to switch to: master or child",
    ),
) -> None:
    """Switch the HaijunBot service running mode.

    Stop the currently running service first, then start the target mode's service. Ensure master and child do not run at the same time.
    When switching, the target service is automatically enabled and the other service is disabled.
    """
    target_mode_lower = target_mode.lower()
    if target_mode_lower not in ["master", "child"]:
        PrettyOutput.auto_print(
            f"❌ Invalid target mode: {target_mode}. Please use 'master' or 'child'"
        )
        raise typer.Exit(code=1)

    # Detect the currently running service
    master_running = _run_systemctl_action("is-active", "master")
    child_running = _run_systemctl_action("is-active", "child")

    # Check whether it is already the target mode
    if (target_mode_lower == "master" and master_running) or (
        target_mode_lower == "child" and child_running
    ):
        PrettyOutput.auto_print(f"ℹ️ Already in {target_mode_lower} mode")
        return

    # Stop the currently running service
    stop_success = True
    if master_running and target_mode_lower == "child":
        PrettyOutput.auto_print("🛑 Stopping master service...")
        if not _run_systemctl_action("stop", "master"):
            PrettyOutput.auto_print("❌ Failed to stop master service; cannot continue switching")
            stop_success = False
    elif child_running and target_mode_lower == "master":
        PrettyOutput.auto_print("🛑 Stopping child service...")
        if not _run_systemctl_action("stop", "child"):
            PrettyOutput.auto_print("❌ Failed to stop child service; cannot continue switching")
            stop_success = False

    if not stop_success:
        raise typer.Exit(code=1)

    # Start the target service
    target_service_name = _get_service_name(target_mode_lower)
    PrettyOutput.auto_print(
        f"🚀 Starting {target_mode_lower} service: {target_service_name}"
    )

    if not _run_systemctl_action("start", target_mode_lower):
        PrettyOutput.auto_print(
            f"⚠ Failed to start, please run manually: systemctl --user start {target_service_name}"
        )
        raise typer.Exit(code=1)

    PrettyOutput.auto_print(f"✅ Switched to {target_mode_lower} mode")

    # Enable the target service and disable the other service
    PrettyOutput.auto_print(f"🔧 Enabling {target_mode_lower} service...")
    if _run_systemctl_enable_disable("enable", target_mode_lower):
        PrettyOutput.auto_print(f"✅ {target_mode_lower} service enabled")
    else:
        PrettyOutput.auto_print(f"⚠ Failed to enable {target_mode_lower} service")

    # Disable the other mode's service
    other_mode = "child" if target_mode_lower == "master" else "master"
    PrettyOutput.auto_print(f"🔧 Disabling {other_mode} service...")
    if _run_systemctl_enable_disable("disable", other_mode):
        PrettyOutput.auto_print(f"✅ {other_mode} service disabled")
    else:
        PrettyOutput.auto_print(f"⚠ Failed to disable {other_mode} service")


def _get_service_name(node_mode: Optional[str]) -> str:
    """Return the systemd service file name according to the node mode.

    Args:
        node_mode: node mode ("master" or "child"); defaults to "master" when None

    Returns:
        Service file name (e.g. "haijunbot-master.service" or "haijunbot-child.service")
    """
    mode = (node_mode or "master").lower()
    if mode == "master":
        return "haijunbot-master.service"
    elif mode == "child":
        return "haijunbot-child.service"
    else:
        # Unknown mode; falling back to master
        return "haijunbot-master.service"


def _run_systemctl_action(action: str, node_mode: Optional[str]) -> bool:
    """Run a systemctl command (start/stop/is-active).

    Args:
        action: systemctl action ("start", "stop", "is-active")
        node_mode: node mode ("master" or "child")

    Returns:
        For is-active: True means running, False means not running
        For start/stop: True means success, False means failure
    """
    service_name = _get_service_name(node_mode)
    try:
        result = subprocess.run(
            ["systemctl", "--user", action, service_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if action == "is-active":
            return result.returncode == 0 and result.stdout.strip() == "active"
        else:
            if result.returncode == 0:
                return True
            else:
                PrettyOutput.auto_print(
                    f"⚠ {action} {service_name} failed: {result.stderr.strip()}"
                )
                return False
    except Exception as e:
        PrettyOutput.auto_print(f"⚠ Error running systemctl {action} {service_name}: {e}")
        return False


def _run_systemctl_enable_disable(action: str, node_mode: Optional[str]) -> bool:
    """Run a systemctl enable/disable command.

    Args:
        action: systemctl action ("enable" or "disable")
        node_mode: node mode ("master" or "child")

    Returns:
        True means success, False means failure
    """
    service_name = _get_service_name(node_mode)
    try:
        result = subprocess.run(
            ["systemctl", "--user", action, service_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True
        else:
            PrettyOutput.auto_print(
                f"⚠ {action} {service_name} failed: {result.stderr.strip()}"
            )
            return False
    except Exception as e:
        PrettyOutput.auto_print(f"⚠ Error running systemctl {action} {service_name}: {e}")
        return False


def _install_systemd_service(config: ServiceConfig) -> None:
    """Install HaijunBot Service as a systemd user service."""

    service_executable = shutil.which("haijunbot-service")
    if service_executable is None:
        PrettyOutput.auto_print(
            "❌ haijunbot-service executable not found; make sure HaijunBot is installed correctly"
        )
        raise typer.Exit(code=1)

    # Build the service file content
    current_path = os.environ.get("PATH", "")

    # Collect proxy-related environment variables
    proxy_env_vars = []
    for var_name in [
        "http_proxy",
        "HTTP_PROXY",
        "https_proxy",
        "HTTPS_PROXY",
        "no_proxy",
        "NO_PROXY",
        "ftp_proxy",
        "FTP_PROXY",
        "socks_proxy",
        "SOCKS_PROXY",
    ]:
        value = os.environ.get(var_name)
        if value:
            proxy_env_vars.append(f"Environment={var_name}={value}")

    proxy_env_section = "\n".join(proxy_env_vars) if proxy_env_vars else ""

    # Determine the service file name and description from node_mode
    service_name = _get_service_name(config.node_mode)
    mode_display = config.node_mode or "master"
    PrettyOutput.auto_print(f"📦 Installing {mode_display} mode service: {service_name}")

    service_content = """[Unit]
Description=HaijunBot Service ({mode})
After=network.target

[Service]
Type=simple
Environment=PATH={path}
{proxy_env}
WorkingDirectory={project_root}
ExecStart={service_executable} run --gateway-host {gateway_host} --gateway-port {gateway_port} --frontend-host {frontend_host} --frontend-port {frontend_port}""".format(
        mode=mode_display,
        path=current_path,
        project_root=config.project_root,
        service_executable=service_executable,
        gateway_host=config.gateway_host,
        gateway_port=config.gateway_port,
        frontend_host=config.frontend_host,
        frontend_port=config.frontend_port,
        proxy_env=proxy_env_section,
    )

    # Add optional arguments
    if config.node_mode:
        service_content += " --node-mode {}".format(config.node_mode)
    if config.node_id:
        service_content += " --node-id {}".format(config.node_id)
    if config.master_url:
        service_content += " --master-url {}".format(config.master_url)
    if config.node_secret:
        service_content += " --node-secret {}".format(config.node_secret)

    service_content += """
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
"""

    # Determine the systemd user directory
    systemd_user_dir = Path.home() / ".config" / "systemd" / "user"
    systemd_user_dir.mkdir(parents=True, exist_ok=True)

    # Write the service file
    service_file_path = systemd_user_dir / service_name
    service_file_path.write_text(service_content, encoding="utf-8")

    PrettyOutput.auto_print(f"✅ systemd service file created: {service_file_path}")
    PrettyOutput.auto_print(f"💡 Use 'haijunbot-service start {mode_display}' to start the service")

    # Show systemctl command hints only on non-Windows systems
    if sys.platform != "win32":
        PrettyOutput.auto_print("📋 Service management commands:")
        PrettyOutput.auto_print("  systemctl --user daemon-reload")
        PrettyOutput.auto_print(f"  systemctl --user enable {service_name}")
        PrettyOutput.auto_print(f"  systemctl --user start {service_name}")
        PrettyOutput.auto_print(f"  systemctl --user status {service_name}")

    # Enable linger mode so the service keeps running after the user logs out
    try:
        import getpass

        username = getpass.getuser()

        # Check whether linger is already enabled
        result = subprocess.run(
            ["loginctl", "show-user", username, "--property=Linger"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        linger_enabled = False
        if result.returncode == 0:
            linger_enabled = "Linger=yes" in result.stdout

        if not linger_enabled:
            PrettyOutput.auto_print(
                "🔧 Enabling linger mode (so the service keeps running after the user logs out)..."
            )
            enable_result = subprocess.run(
                ["loginctl", "enable-linger", username],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if enable_result.returncode == 0:
                PrettyOutput.auto_print(
                    "✅ Linger mode enabled; the service will keep running after the user logs out"
                )
            else:
                PrettyOutput.auto_print(
                    f"⚠️  Failed to auto-enable linger: {enable_result.stderr}"
                )
                PrettyOutput.auto_print(
                    f"💡 Please run manually: sudo loginctl enable-linger {username}"
                )
        else:
            PrettyOutput.auto_print("✅ Linger mode enabled; the service will keep running after the user logs out")
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️  Error while checking/enabling linger: {e}")
        PrettyOutput.auto_print("💡 The service may need to run while the user is logged in, or enable linger manually")

    PrettyOutput.auto_print("📋 hservice management commands:")
    PrettyOutput.auto_print("  hservice start")
    PrettyOutput.auto_print("  hservice stop")
    PrettyOutput.auto_print("  hservice status")
    PrettyOutput.auto_print("  hservice restart")


def main() -> None:
    """Compatible with old script entry, delegate to Typer app."""
    app()


if __name__ == "__main__":
    main()
