# -*- coding: utf-8 -*-
"""Agent Manager: manages the Agent lifecycle.

Responsible for creating, stopping, and monitoring Agent subprocesses, and allocating and managing ports.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import signal
import socket
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.utils import _is_process_alive
import haijunbot.haijunbot_utils.globals as jglobals


class AgentInfo:
    """Agent information."""

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        pid: int,
        port: int,
        working_dir: str,
        process: Optional[subprocess.Popen],
        name: Optional[str] = None,
        llm_group: str = "default",
        worktree: bool = False,
        node_id: str = "master",
        quick_mode: bool = False,
        restore_session: Optional[Union[bool, str]] = None,
        no_interaction_mode: bool = False,
        proxy_node: Optional[str] = None,
        owner_id: Optional[str] = None,
        access_acl: Optional[Dict[str, List[str]]] = None,
        tool_group: str = "default",
        config_file: Optional[str] = None,
        task: Optional[str] = None,
        additional_args: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.name = name
        self.pid = pid
        self.port = port
        self.working_dir = os.path.abspath(os.path.expanduser(working_dir))
        self.process = process
        self.llm_group = llm_group
        self.worktree = worktree
        self.quick_mode = quick_mode
        self.restore_session = restore_session
        self.no_interaction_mode = no_interaction_mode
        self.proxy_node = proxy_node
        self.status = "running"
        self.node_id = node_id
        self.owner_id = owner_id
        self.access_acl = access_acl or {}
        self.tool_group = tool_group
        self.config_file = config_file
        self.task = task
        self.additional_args = additional_args
        self.created_at = datetime.now().isoformat()
        self._monitor_task: Optional[asyncio.Task] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "name": self.name,
            "pid": self.pid,
            "port": self.port,
            "status": self.status,
            "working_dir": self.working_dir,
            "llm_group": self.llm_group,
            "worktree": self.worktree,
            "quick_mode": self.quick_mode,
            "restore_session": self.restore_session,
            "no_interaction_mode": self.no_interaction_mode,
            "proxy_node": self.proxy_node,
            "node_id": self.node_id,
            "owner_id": self.owner_id,
            "access_acl": self.access_acl,
            "tool_group": self.tool_group,
            "config_file": self.config_file,
            "task": self.task,
            "additional_args": self.additional_args,
            "created_at": self.created_at,
        }


class AgentManager:
    """Agent manager: manages Agent subprocesses and ports."""

    # Agent entry point paths
    AGENT_ENTRY_POINTS = {
        "agent": "hjb",
        "code_agent": "hca",
    }

    # Random port range
    PORT_RANGE = (10000, 65535)

    # Agent list persistence file path
    PERSISTENCE_FILE = Path(get_data_dir()) / "gateway" / ".haijunbot_agents.json"

    def __init__(
        self, on_status_change: Optional[Callable[[str, str, Any], None]] = None
    ) -> None:
        """Initialize AgentManager.

        Args:
            on_status_change: Status change callback function
        """
        self._agents: Dict[str, AgentInfo] = {}
        self._on_status_change = on_status_change
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

        # Load the saved Agent list
        self._load_agents()

    def set_event_loop(self, event_loop: asyncio.AbstractEventLoop) -> None:
        """Bind the main event loop used for monitoring tasks."""
        self._event_loop = event_loop

    def create_agent(
        self,
        agent_type: str,
        working_dir: str,
        name: Optional[str] = None,
        llm_group: str = "default",
        tool_group: str = "default",
        config_file: Optional[str] = None,
        task: Optional[str] = None,
        additional_args: Optional[Dict[str, Any]] = None,
        auth_token: Optional[str] = None,
        worktree: bool = False,
        node_id: str = "master",
        quick_mode: bool = False,
        restore_session: Optional[Union[bool, str]] = None,
        no_interaction_mode: bool = False,
        proxy_node: Optional[str] = None,
        owner_id: Optional[str] = None,
        access_acl: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """Create an Agent.

        Args:
            agent_type: Agent type ("agent" or "code_agent")
            working_dir: Working directory
            name: Agent name (optional, used for identification)
            llm_group: LLM model group
            tool_group: Tool group
            config_file: Config file path
            task: Task description (only valid for code_agent)
            additional_args: Additional arguments
            auth_token: Auth token, passed to the Agent via environment variable
            worktree: Whether to enable git worktree mode for code_agent
            quick_mode: Whether to enable quick mode
            restore_session: Whether to restore the session at startup
            no_interaction_mode: Whether to enable no-interaction mode (task is required when enabled)
            owner_id: Creator user ID

        Returns:
            Agent information dictionary

        Raises:
            ValueError: Invalid argument
            RuntimeError: Failed to start
        """
        # Validate agent_type
        if agent_type not in self.AGENT_ENTRY_POINTS:
            raise ValueError(
                f"Invalid agent_type: {agent_type}, "
                f"must be one of {list(self.AGENT_ENTRY_POINTS.keys())}"
            )

        # Expand the ~ symbol in the working directory and convert to an absolute path
        working_dir = os.path.abspath(os.path.expanduser(working_dir))

        # Validate the working directory: try to create it if missing, fall back to the user home directory if creation fails
        if not os.path.isdir(working_dir):
            try:
                os.makedirs(working_dir, exist_ok=True)
                logging.getLogger(__name__).info(
                    f"Created working directory: {working_dir}"
                )
            except Exception as e:
                fallback_dir = os.path.expanduser("~")
                logging.getLogger(__name__).warning(
                    f"Failed to create working directory '{working_dir}': {e}. "
                    f"Falling back to home directory: {fallback_dir}"
                )
                working_dir = fallback_dir

        # Generate a unique ID
        agent_id = str(uuid.uuid4())

        # Allocate a port
        port = self._allocate_port()
        if port is None:
            raise RuntimeError("No available port")

        # Validate no-interaction mode: task is required
        if no_interaction_mode and not task:
            raise ValueError("no_interaction_mode is enabled but task is not provided")

        # Build the command-line arguments
        cmd = self._build_command(
            agent_type=agent_type,
            port=port,
            llm_group=llm_group,
            tool_group=tool_group,
            config_file=config_file,
            task=task,
            additional_args=additional_args,
            worktree=worktree,
            quick_mode=quick_mode,
            restore_session=restore_session,
            no_interaction_mode=no_interaction_mode,
            proxy_node=proxy_node,
            agent_id=agent_id,
        )

        # Prepare the environment variables (including the auth token)
        env = os.environ.copy()
        if auth_token:
            env["HAIJUNBOT_AUTH_TOKEN"] = auth_token

        # Start the subprocess (does not redirect stdin/stdout/stderr, allowing a TTY environment)
        try:
            process = subprocess.Popen(
                cmd,
                cwd=working_dir,
                env=env,
                start_new_session=True,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to start agent: {e}")

        # Create AgentInfo
        agent_info = AgentInfo(
            agent_id=agent_id,
            agent_type=agent_type,
            pid=process.pid,
            port=port,
            working_dir=working_dir,
            process=process,
            name=name,
            llm_group=llm_group,
            worktree=worktree,
            node_id=node_id,
            quick_mode=quick_mode,
            restore_session=restore_session,
            no_interaction_mode=no_interaction_mode,
            proxy_node=proxy_node,
            owner_id=owner_id,
            access_acl=access_acl,
            tool_group=tool_group,
            config_file=config_file,
            task=task,
            additional_args=additional_args,
        )

        # Save to memory
        self._agents[agent_id] = agent_info

        # Save to the persistence file
        self._save_agents()

        # Start the monitoring task
        monitor_loop = self._event_loop
        if monitor_loop is None:
            monitor_loop = asyncio.get_running_loop()

        if not monitor_loop.is_running():
            raise RuntimeError("AgentManager event loop is not running")

        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if monitor_loop is current_loop:
            agent_info._monitor_task = monitor_loop.create_task(
                self._monitor_agent(agent_id)
            )
        else:
            monitor_loop.call_soon_threadsafe(
                self._attach_monitor_task,
                agent_id,
            )

        # Return the information
        return agent_info.to_dict()

    def _attach_monitor_task(self, agent_id: str) -> None:
        """Attach the monitoring task in the bound event loop."""
        agent_info = self._agents.get(agent_id)
        if agent_info is None:
            return
        agent_info._monitor_task = asyncio.create_task(self._monitor_agent(agent_id))

    def create_agent_threadsafe(
        self,
        agent_type: str,
        working_dir: str,
        name: Optional[str] = None,
        llm_group: str = "default",
        tool_group: str = "default",
        config_file: Optional[str] = None,
        task: Optional[str] = None,
        additional_args: Optional[Dict[str, Any]] = None,
        auth_token: Optional[str] = None,
        worktree: bool = False,
        proxy_node: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Safely create an Agent in a threaded environment."""
        if self._event_loop is None:
            raise RuntimeError("AgentManager event loop is not set")

        future = asyncio.run_coroutine_threadsafe(
            self._create_agent_async(
                agent_type=agent_type,
                working_dir=working_dir,
                name=name,
                llm_group=llm_group,
                tool_group=tool_group,
                config_file=config_file,
                task=task,
                additional_args=additional_args,
                auth_token=auth_token,
                worktree=worktree,
                proxy_node=proxy_node,
                owner_id=owner_id,
            ),
            self._event_loop,
        )
        return future.result()

    async def _create_agent_async(
        self,
        agent_type: str,
        working_dir: str,
        name: Optional[str] = None,
        llm_group: str = "default",
        tool_group: str = "default",
        config_file: Optional[str] = None,
        task: Optional[str] = None,
        additional_args: Optional[Dict[str, Any]] = None,
        auth_token: Optional[str] = None,
        worktree: bool = False,
        proxy_node: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create an Agent in the event loop context."""
        return self.create_agent(
            agent_type=agent_type,
            working_dir=working_dir,
            name=name,
            llm_group=llm_group,
            tool_group=tool_group,
            config_file=config_file,
            task=task,
            additional_args=additional_args,
            auth_token=auth_token,
            worktree=worktree,
            proxy_node=proxy_node,
            owner_id=owner_id,
        )

    def stop_agent(self, agent_id: str) -> Dict[str, Any]:
        """Stop an Agent.

        Args:
            agent_id: Agent ID

        Returns:
            Stop result

        Raises:
            KeyError: Agent does not exist
        """
        if agent_id not in self._agents:
            raise KeyError(f"Agent not found: {agent_id}")

        agent_info = self._agents[agent_id]

        # Send SIGTERM
        if agent_info.process is not None:
            agent_info.process.terminate()

            # Wait for the process to exit (up to 10 seconds)
            try:
                agent_info.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Force kill the process
                agent_info.process.kill()
                agent_info.process.wait()
        elif agent_info.pid:
            # When the process object is None, kill the process by PID
            try:
                os.kill(agent_info.pid, signal.SIGTERM)
            except ProcessLookupError:
                # The process no longer exists
                pass

        # Cancel the monitoring task
        if agent_info._monitor_task:
            agent_info._monitor_task.cancel()

        # Update the status
        agent_info.status = "stopped"

        # Keep it in memory (do not delete) so history can be restored after a restart
        # del self._agents[agent_id]

        # Update the persistence file
        self._save_agents()

        # Notify the status change
        if self._on_status_change:
            self._on_status_change(agent_id, "stopped", agent_info.to_dict())

        return {"agent_id": agent_id, "status": "stopped"}

    def delete_agent(self, agent_id: str) -> Dict[str, Any]:
        """Delete an Agent.

        Args:
            agent_id: Agent ID

        Returns:
            Delete result

        Raises:
            KeyError: Agent does not exist
        """
        if agent_id not in self._agents:
            raise KeyError(f"Agent not found: {agent_id}")

        agent_info = self._agents[agent_id]

        # If it is running, stop it first
        if agent_info.status == "running":
            if agent_info.process is not None:
                agent_info.process.terminate()

                # Wait for the process to exit (up to 10 seconds)
                try:
                    agent_info.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # Force kill the process
                    agent_info.process.kill()
                    agent_info.process.wait()
            elif agent_info.pid:
                # When the process object is None, kill the process by PID
                try:
                    os.kill(agent_info.pid, signal.SIGTERM)
                except ProcessLookupError:
                    # The process no longer exists
                    pass

        # Cancel the monitoring task
        if agent_info._monitor_task:
            agent_info._monitor_task.cancel()

        # Delete from memory
        del self._agents[agent_id]

        # Update the persistence file
        self._save_agents()

        # Notify the status change
        if self._on_status_change:
            self._on_status_change(agent_id, "deleted", None)

        return {"agent_id": agent_id, "status": "deleted"}

    def regenerate_agent(self, agent_id: str) -> Dict[str, Any]:
        """Losslessly regenerate the specified Agent.

        Completes the entire "save session → delete → recreate" flow on the gateway side, allowing an
        Agent to losslessly regenerate itself (without the flow being interrupted by deleting itself).
        After recreation, the saved session is used to restore the scene, and the configuration remains unchanged.

        Args:
            agent_id: The Agent ID to regenerate

        Returns:
            Dict[str, Any]: Regeneration result, including the new Agent information and the saved session file

        Raises:
            KeyError: Agent does not exist
        """
        if agent_id not in self._agents:
            raise KeyError(f"Agent not found: {agent_id}")

        agent_info = self._agents[agent_id]

        # 1. Save the session (proxy to the Agent process's /sessions/save endpoint)
        session_file = None
        try:
            import urllib.request

            req = urllib.request.Request(
                f"http://127.0.0.1:{agent_info.port}/sessions/save",
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("success"):
                    session_file = data.get("session_file")
        except Exception as e:
            # A save failure does not block regeneration; just skip session restoration
            logging.getLogger(__name__).warning(
                f"Failed to save session for agent {agent_id}: {e}"
            )

        # 2. Delete the Agent
        self.delete_agent(agent_id)

        # 3. Recreate with the original configuration (including session restoration)
        new_agent = self.create_agent(
            agent_type=agent_info.agent_type,
            working_dir=agent_info.working_dir,
            name=agent_info.name,
            llm_group=agent_info.llm_group,
            tool_group=agent_info.tool_group,
            config_file=agent_info.config_file,
            task=agent_info.task,
            additional_args=agent_info.additional_args,
            worktree=agent_info.worktree,
            node_id=agent_info.node_id,
            quick_mode=agent_info.quick_mode,
            restore_session=session_file if session_file else False,
            no_interaction_mode=agent_info.no_interaction_mode,
            proxy_node=agent_info.proxy_node,
            owner_id=agent_info.owner_id,
            access_acl=agent_info.access_acl,
        )

        return {
            "success": True,
            "new_agent": new_agent,
            "session_file": session_file,
        }

    def get_agent_list(self) -> List[Dict[str, Any]]:
        """Get the Agent list.

        Returns:
            Agent information list
        """
        return [agent.to_dict() for agent in self._agents.values()]

    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get Agent information.

        Args:
            agent_id: Agent ID

        Returns:
            Agent information, or None if it does not exist
        """
        return self._agents.get(agent_id)

    def rename_agent(self, agent_id: str, name: Optional[str]) -> Dict[str, Any]:
        """Rename an Agent.

        Args:
            agent_id: Agent ID
            name: New name; None means remove the name

        Returns:
            The updated Agent information dictionary

        Raises:
            KeyError: Agent does not exist
        """
        if agent_id not in self._agents:
            raise KeyError(f"Agent {agent_id} not found")

        agent = self._agents[agent_id]
        agent.name = name

        # Save to file
        self._save_agents()
        return agent.to_dict()

    def update_agent_runtime_config(
        self,
        agent_id: str,
        llm_group: Optional[str] = None,
        proxy_node: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update the Agent runtime configuration (model group / proxy node).

        After the Agent modifies its configuration at runtime via commands (such as <SetConfig> to switch the model group or proxy node), it proactively reports
        to the gateway, which updates AgentInfo so that the configuration displayed in the list matches the real running state.

        Args:
            agent_id: Agent ID
            llm_group: New model group name (None means do not modify)
            proxy_node: New proxy node ID (None means do not modify)

        Returns:
            The updated Agent information dictionary

        Raises:
            KeyError: Agent does not exist
        """
        if agent_id not in self._agents:
            raise KeyError(f"Agent {agent_id} not found")

        agent = self._agents[agent_id]
        if llm_group is not None:
            agent.llm_group = llm_group
        if proxy_node is not None:
            agent.proxy_node = proxy_node

        # Save to file
        self._save_agents()
        return agent.to_dict()

    def update_agent_access(
        self, agent_id: str, access_acl: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """Update the Agent's access control list.

        Automatically removes the owner user and admin user (these two users have full control over the agent).

        Args:
            agent_id: Agent ID
            access_acl: Access control list, in the format {"read": [user_id, ...], "interact": [user_id, ...]}

        Returns:
            The updated Agent information dictionary

        Raises:
            KeyError: Agent does not exist
        """
        if agent_id not in self._agents:
            raise KeyError(f"Agent {agent_id} not found")

        agent = self._agents[agent_id]

        # Automatically remove the owner user and admin user
        from haijunbot.haijunbot_utils.config import get_data_dir
        from haijunbot.haijunbot_web_gateway.user_manager import UserManager

        cleaned_acl = {}
        data_dir = get_data_dir()
        for acl_type, user_ids in access_acl.items():
            if not isinstance(user_ids, list):
                continue
            # Filter out the owner user
            filtered_users = [uid for uid in user_ids if uid != agent.owner_id]
            # Filter out the admin user
            try:
                user_mgr = UserManager(data_dir)
                admin_user = user_mgr.get_user_by_username("admin")
                admin_user_id = admin_user["user_id"] if admin_user else None
                if admin_user_id:
                    filtered_users = [
                        uid for uid in filtered_users if uid != admin_user_id
                    ]
            except Exception:
                pass  # Ignore exceptions and keep the original logic
            if filtered_users:
                cleaned_acl[acl_type] = filtered_users

        # Update the agent's access_acl
        agent.access_acl = cleaned_acl

        # Save to file
        self._save_agents()

        return agent.to_dict()

    def _allocate_port(self) -> Optional[int]:
        """Allocate a random port.

        Returns:
            An available port, or None if no port is available
        """
        min_port, max_port = self.PORT_RANGE

        # Try random allocation 10 times
        for _ in range(10):
            port = int(
                min_port + (max_port - min_port) * (hash(uuid.uuid4()) % 10000) / 10000
            )

            # Check whether the port is in use
            if self._is_port_available(port):
                return port

        return None

    def _is_port_available(self, port: int) -> bool:
        """Check whether the port is available.

        Args:
            port: Port number

        Returns:
            True if available, False if in use
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return True
        except OSError:
            return False

    def _build_command(
        self,
        agent_type: str,
        port: int,
        llm_group: str,
        tool_group: str,
        config_file: Optional[str],
        task: Optional[str],
        additional_args: Optional[Dict[str, Any]],
        worktree: bool = False,
        quick_mode: bool = False,
        restore_session: Optional[Union[bool, str]] = None,
        no_interaction_mode: bool = False,
        proxy_node: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> List[str]:
        """Build the Agent startup command.

        Args:
            agent_type: Agent type
            port: Port
            llm_group: LLM model group
            tool_group: Tool group
            config_file: Config file path
            task: Task description
            additional_args: Additional arguments
            worktree: Whether to enable git worktree mode for code_agent
            quick_mode: Whether to enable quick mode
            restore_session: Whether to enable session restoration
            no_interaction_mode: Whether to enable no-interaction mode

        Returns:
            Command list
        """
        # Base command (resolve the full path to avoid PATH issues)
        entry_point = self.AGENT_ENTRY_POINTS[agent_type]
        resolved = shutil.which(entry_point)
        if resolved is None:
            # Look it up by loading the user environment with bash (overrides the user's shell PATH)
            try:
                result = subprocess.run(
                    ["bash", "-lc", f"which {entry_point}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    resolved = result.stdout.strip()
            except Exception:
                pass
        if resolved is None:
            # Fall back to common user bin directories
            for candidate in [
                Path.home() / ".local" / "bin" / entry_point,
                Path(sys.executable).parent / entry_point,
            ]:
                if candidate.exists():
                    resolved = str(candidate)
                    break
        if resolved is None:
            resolved = entry_point
        base_cmd = [resolved]

        # Add arguments
        cmd = base_cmd.copy()
        cmd.extend(["--web-gateway-port", str(port)])
        cmd.append("--web-gateway")  # Start in WebSocket Gateway mode

        # Add the LLM model group argument
        if llm_group and llm_group != "default":
            cmd.extend(["-g", llm_group])

        if config_file:
            cmd.extend(["--config-file", config_file])

        if task:
            cmd.extend(["--task", task])

        if agent_type == "code_agent" and worktree:
            cmd.append("-w")

        # Add the quick mode argument
        if quick_mode:
            cmd.append("-q")

        # Add the session restoration argument
        if restore_session is True:
            cmd.append("-r")  # Interactively choose a session to restore
        elif restore_session:
            cmd.extend(["-R", restore_session])  # Specify the session file path

        # Add the non-interactive mode argument
        if no_interaction_mode:
            cmd.append("--non-interactive")

        # Add the master URL argument (if set in the global variables)
        if jglobals.master_url:
            cmd.extend(["--master-url", jglobals.master_url])

        # Add the agent_id argument (the unique identifier allocated by AgentManager)
        if agent_id:
            cmd.extend(["--agent-id", agent_id])

        # Add the proxy node argument (if specified)
        if proxy_node:
            cmd.extend(["--proxy-node", proxy_node])

        # Add additional arguments
        if additional_args:
            for key, value in additional_args.items():
                cmd.extend([f"--{key}", str(value)])

        return cmd

    async def _monitor_agent(self, agent_id: str) -> None:
        """Monitor the Agent process.

        Args:
            agent_id: Agent ID
        """
        agent_info = self._agents.get(agent_id)
        if not agent_info:
            return

        # If the process object is None (the restored case), detect process liveness by polling the PID
        if agent_info.process is None:
            if agent_info.pid:
                try:
                    while True:
                        await asyncio.sleep(5)
                        # Check whether the process is alive
                        try:
                            os.kill(agent_info.pid, 0)
                        except ProcessLookupError:
                            # The process no longer exists
                            agent_info.status = "stopped"
                            self._save_agents()
                            if self._on_status_change:
                                self._on_status_change(
                                    agent_id,
                                    "stopped",
                                    {
                                        "agent_id": agent_id,
                                        "status": "stopped",
                                        "message": "Agent process exited (detected by PID polling)",
                                    },
                                )
                            return
                        except OSError:
                            # Insufficient permissions; unable to check
                            await asyncio.sleep(30)
                except asyncio.CancelledError:
                    pass
            return

        try:
            # Wait for the process to exit
            return_code = await asyncio.get_event_loop().run_in_executor(
                None, agent_info.process.wait
            )

            # Check whether it exited abnormally
            if return_code != 0:
                agent_info.status = "error"
                if self._on_status_change:
                    self._on_status_change(
                        agent_id,
                        "error",
                        {
                            "agent_id": agent_id,
                            "status": "error",
                            "return_code": return_code,
                            "message": f"Agent exited with code {return_code}",
                        },
                    )
            else:
                # Normal exit; update the status to stopped
                agent_info.status = "stopped"
                # Save to the persistence file
                self._save_agents()
                # Notify the status change
                if self._on_status_change:
                    self._on_status_change(
                        agent_id,
                        "stopped",
                        {
                            "agent_id": agent_id,
                            "status": "stopped",
                            "return_code": return_code,
                            "message": "Agent exited normally",
                        },
                    )
        except asyncio.CancelledError:
            # The task was cancelled; this is normal
            pass
        except Exception as e:
            # Monitoring error
            agent_info.status = "error"
            if self._on_status_change:
                self._on_status_change(
                    agent_id,
                    "error",
                    {
                        "agent_id": agent_id,
                        "status": "error",
                        "message": f"Monitor error: {e}",
                    },
                )

    async def cleanup(self) -> None:
        """Clean up all Agents (only cancel the monitoring tasks, do not kill the processes)."""
        agent_ids = list(self._agents.keys())
        for agent_id in agent_ids:
            agent_info = self._agents.get(agent_id)
            if agent_info:
                # Only cancel the monitoring task, do not kill the process
                if agent_info._monitor_task:
                    agent_info._monitor_task.cancel()
                agent_info.status = "orphaned"
            self._save_agents()

    async def start_monitoring_for_running_agents(self) -> None:
        """Start monitoring tasks for all running Agents.

        This method must be called in an async context (after the application starts).
        """
        for agent_id, agent_info in list(self._agents.items()):
            if agent_info.status == "running" and agent_info._monitor_task is None:
                agent_info._monitor_task = asyncio.create_task(
                    self._monitor_agent(agent_id)
                )

    def _load_agents(self) -> None:
        """Load the saved Agent list from the file."""
        if not self.PERSISTENCE_FILE.exists():
            return

        try:
            with open(self.PERSISTENCE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                return

            for agent_data in data:
                try:
                    # Restore AgentInfo
                    agent_info = AgentInfo(
                        agent_id=agent_data["agent_id"],
                        agent_type=agent_data["agent_type"],
                        pid=agent_data.get("pid", 0),
                        port=agent_data["port"],
                        working_dir=agent_data["working_dir"],
                        process=None,  # The process object cannot be restored, so set it to None
                        name=agent_data.get("name"),
                        llm_group=agent_data.get(
                            "llm_group", "default"
                        ),  # Backward compatible; old data uses the default value
                        worktree=agent_data.get("worktree", False),
                        node_id=agent_data.get("node_id", "master"),
                        quick_mode=agent_data.get("quick_mode", False),
                        restore_session=agent_data.get("restore_session", False),
                        no_interaction_mode=agent_data.get(
                            "no_interaction_mode", False
                        ),
                        proxy_node=agent_data.get("proxy_node"),
                        owner_id=agent_data.get("owner_id"),
                        access_acl=agent_data.get("access_acl", {}),
                        tool_group=agent_data.get("tool_group", "default"),
                        config_file=agent_data.get("config_file"),
                        task=agent_data.get("task"),
                        additional_args=agent_data.get("additional_args"),
                    )

                    # Check whether the process is still running
                    pid = agent_data.get("pid")
                    if pid and self._is_process_running(pid):
                        # The process is still running; restore to the running state
                        agent_info.status = agent_data.get("status", "running")

                        # Restart the monitoring task (requires an async context)
                        # Note: an async task cannot be created directly here; it must be created in an async context
                        agent_info._monitor_task = None  # created later in an async context
                    else:
                        # The process has stopped; restore to the stopped state
                        agent_info.status = "stopped"

                    # Restore the creation time
                    agent_info.created_at = agent_data.get(
                        "created_at", datetime.now().isoformat()
                    )

                    # Save to memory
                    self._agents[agent_info.agent_id] = agent_info
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_web_gateway.agent_manager",
                        function="_load_agents",
                    )
                    pass

        except Exception as e:
            save_exception(
                e, module="haijunbot_web_gateway.agent_manager", function="_load_agents"
            )
            pass

    def _save_agents(self) -> None:
        """Save the Agent list to the file."""
        try:
            # Ensure the directory exists
            self.PERSISTENCE_FILE.parent.mkdir(parents=True, exist_ok=True)

            data = [agent.to_dict() for agent in self._agents.values()]
            with open(self.PERSISTENCE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            save_exception(
                e, module="haijunbot_web_gateway.agent_manager", function="_save_agents"
            )
            pass

    def _is_process_running(self, pid: int) -> bool:
        """Check whether the process is running.

        Args:
            pid: Process ID

        Returns:
            True if running, False if stopped
        """
        return _is_process_alive(pid)
