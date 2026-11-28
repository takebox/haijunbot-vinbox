# -*- coding: utf-8 -*-
"""Gateway management tool - used to manage communication and collaboration between Agents as well as node information queries"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx

import haijunbot.haijunbot_utils.globals as jglobals

logger = logging.getLogger(__name__)


class GatewayManagerTool:
    """Gateway management tool, supporting multiple operations:

    1. **send_to_agent**: Send a message to the specified Agent (proxied via Web Gateway to the target Agent's /message endpoint)
    2. **list_agents**: Get the list of all Agents
    3. **list_nodes**: Get node list information
    4. **list_model_groups**: Get the model group list of the specified node
    5. **create_agent**: Create a new Agent
    6. **list_directory**: Get the file/directory list under the specified path, supporting cross-node queries
    7. **exec_command**: Execute a shell command on the specified node, supporting cross-node
    8. **delete_agent**: Delete the specified Agent
    9. **get_node_secret**: Get the gateway's node connection private key
    10. **update_nodes_code**: Update all node code to the main branch
    11. **restart_nodes**: Restart all node services with one click (skip the current node)
    12. **create_timer**: Create a scheduled task (supporting specified node)
    13. **list_timers**: Query the scheduled tasks of all nodes (aggregated)
    14. **get_timer**: Query a single scheduled task
    15. **delete_timer**: Delete a scheduled task
    16. **create_group**: Create a group
    17. **list_groups**: Query all groups
    18. **get_group**: Query group details
    19. **join_group**: Join a group
    20. **leave_group**: Leave a group
    21. **send_group_message**: Send a group message

    **Important notes**:
    - Only one operation can be performed per call
    - Parameters vary depending on the operation type
    """

    name = "gateway_manager"

    @staticmethod
    def check() -> bool:
        """Check whether the tool is available; enabled only when Gateway exists (determined by whether agent_id is set)."""
        return jglobals.agent_id is not None

    description = """Manage communication and collaboration between multiple Agents and the gateway, as well as orchestration operations such as nodes, scheduled tasks, groups, and chat.

Only one operation can be performed per call (see the operation parameter); the remaining parameters vary by operation. Operations fall roughly into several categories:
- Agent: send_to_agent sends a message to an Agent; list_agents lists Agents; create_agent creates an Agent; delete_agent deletes an Agent; regenerate_agent losslessly regenerates an Agent; get_node_secret retrieves the node connection key
- Node/gateway: list_nodes node information; get_master_url checks the master gateway address used by the current node; list_model_groups model group list; list_directory directory browsing; exec_command executes a shell command on the specified node (requires command, optional node_id/working_dir/timeout); update_nodes_code updates all node code; restart_nodes restarts node services with one click
- Scheduled task: create_timer / list_timers / get_timer / delete_timer
- Group: create_group / list_groups / get_group / join_group / leave_group / send_group_message
- Chat: chat_list_rooms / chat_get_online_clients / list_sessions / chat_get_room_members / chat_send_room_message / chat_send_private_message (messages automatically get an [Agent name] prefix and are sent as the owner); list_sessions returns each active connection (session) and its corresponding user
- Frontend JS: eval_js delivers a piece of JS to the frontend browser for execution and retrieves the result (requires code; optional timeout/target)

Most operations require specifying a target node/Agent; for specific fields and values, refer to the operation parameter description."""

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "send_to_agent",
                    "list_agents",
                    "list_nodes",
                    "get_master_url",
                    "list_model_groups",
                    "create_agent",
                    "list_directory",
                    "exec_command",
                    "delete_agent",
                    "get_node_secret",
                    "update_nodes_code",
                    "restart_nodes",
                    "create_timer",
                    "list_timers",
                    "get_timer",
                    "delete_timer",
                    "create_group",
                    "list_groups",
                    "get_group",
                    "join_group",
                    "leave_group",
                    "send_group_message",
                    "regenerate_agent",
                    "chat_list_rooms",
                    "chat_get_online_clients",
                    "list_sessions",
                    "chat_get_room_members",
                    "chat_send_room_message",
                    "chat_send_private_message",
                    "eval_js",
                ],
                "description": "The type of operation to perform; only one can be selected at a time; the remaining parameters depend on the operation (see each parameter description). Common ones: send_to_agent sends a message to an Agent, list_agents lists Agents, create_agent creates a new Agent, restart_nodes restarts all nodes, create_timer creates a scheduled task. The remaining operations can be understood by name; see the enum above for the full list. get_master_url returns the master gateway address used by the current node.",
            },
            # Parameters for the send_to_agent operation
            "agent_id": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                ],
                "description": "The ID of the target Agent (required for the send_to_agent operation; required for the delete_agent operation; required for the regenerate_agent operation). Supports a single ID string or an array of IDs.",
            },
            "message": {
                "type": "string",
                "description": "The content of the message to send (required for the send_to_agent operation)",
            },
            "wait": {
                "type": "boolean",
                "description": "Whether to synchronously wait for the Agent to finish processing (optional for the send_to_agent operation, defaults to false for backward-compatible asynchronous fire-and-forget). When wait=true, if status_file is provided, poll that local status file (written by the Agent after completing the task, to determine completed/failed); otherwise poll changes to the execution_status of the Agent's /status (fallback, not entirely reliable).",
            },
            "status_file": {
                "type": "string",
                "description": "Path to the phase completion status file (optional for the send_to_agent operation, used with wait=true). After the Agent completes the task it writes {\"status\": \"completed\"|\"failed\"} to this file, and send_to_agent polls it to determine completion.",
            },
            # Parameters for the list_model_groups / create_agent / list_directory operations
            "node_id": {
                "type": "string",
                "description": "Target node ID (optional for the send_to_agent operation; when unspecified, automatically queries the node where the Agent resides; optional for the list_model_groups operation, defaults to master; optional for the create_agent operation, defaults to the local node; optional for the list_directory operation, defaults to the local node; optional for the delete_agent operation, defaults to the local node; optional for the regenerate_agent operation, defaults to the local node)",
            },
            # Parameters for the list_directory operation
            "path": {
                "type": "string",
                "description": "Directory path (optional for the list_directory operation, defaults to empty meaning the user's home directory)",
            },
            # Parameters for the exec_command operation
            "command": {
                "type": "string",
                "description": "The shell command to execute (required for the exec_command operation)",
            },
            # Parameters for the create_agent operation
            "agent_type": {
                "type": "string",
                "description": "Agent type (required for the create_agent operation), such as code, chat, etc.",
            },
            "working_dir": {
                "type": "string",
                "description": "Working directory (required for the create_agent operation)",
            },
            "agent_name": {
                "type": "string",
                "description": "Agent name (optional for the create_agent operation)",
            },
            "llm_group": {
                "type": "string",
                "description": "Model group name (optional for the create_agent operation, defaults to default)",
            },
            "tool_group": {
                "type": "string",
                "description": "Tool group name (optional for the create_agent operation, defaults to default)",
            },
            "config_file": {
                "type": "string",
                "description": "Configuration file path (optional for the create_agent operation)",
            },
            "task": {
                "type": "string",
                "description": "The Agent's initial task description (optional for the create_agent operation, required in no_interaction_mode)",
            },
            "additional_args": {
                "type": "string",
                "description": "Additional parameters (optional for the create_agent operation)",
            },
            "worktree": {
                "type": "boolean",
                "description": "Whether to use a git worktree (optional for the create_agent operation, defaults to false)",
            },
            "quick_mode": {
                "type": "boolean",
                "description": "Whether to enable quick mode (optional for the create_agent operation, defaults to false)",
            },
            "restore_session": {
                "anyOf": [{"type": "boolean"}, {"type": "string"}],
                "description": "Session restore parameter (optional for the create_agent operation, defaults to null, no session restore). A boolean value true means interactively selecting a session file; a string means the specified session file path",
            },
            "no_interaction_mode": {
                "type": "boolean",
                "description": "Whether to enable no-interaction mode (optional for the create_agent operation, defaults to false; task is required when enabled)",
            },
            "owner_id": {
                "type": "string",
                "description": "Agent owner user ID (optional for the create_agent operation). When unspecified, automatically inferred as the current Agent's owner, usually no manual specification needed",
            },
            "proxy_node": {
                "type": "string",
                "description": "Proxy node ID (optional for the create_agent operation)",
            },
            "access_acl": {
                "type": "object",
                "description": 'Access control (optional for the create_agent operation), in the form {"read": ["user_id"], "interact": ["user_id"]}',
            },
            # Parameters for the timer operations
            "timer_id": {
                "type": "string",
                "description": "Scheduled task ID (required for the get_timer and delete_timer operations)",
            },
            "schedule": {
                "type": "object",
                "description": 'Scheduled task scheduling configuration (required for the create_timer operation), choose one of four: run_at (ISO time string), delay_seconds (delay seconds >= 0), interval_seconds (interval seconds > 0), cron (5-field cron expression, such as "0 9 * * 1" for every Monday at 9 o\'clock)',
            },
            "timer_action_type": {
                "type": "string",
                "enum": ["create_agent", "run_shell_command", "capability_call"],
                "description": "Scheduled task action type (required for the create_timer operation): create_agent / run_shell_command / capability_call",
            },
            "timer_action_params": {
                "type": "object",
                "description": "Scheduled task action parameters (required for the create_timer operation). The create_agent type requires: agent_type (required), working_dir (required), name, llm_group, tool_group, config_file, task, additional_args, worktree, proxy_node; the run_shell_command type requires: command (required), working_dir (required), interpreter; the capability_call type requires: session_id (required), capability (required), params (object), timeout (seconds), user_id, is_admin",
            },
            # Parameters for the group operations
            "group_id": {
                "type": "string",
                "description": "Group ID (required for the get_group, join_group, leave_group, and send_group_message operations)",
            },
            "group_name": {
                "type": "string",
                "description": "Group name (required for the create_group operation)",
            },
            "group_description": {
                "type": "string",
                "description": "Group description (optional for the create_group operation)",
            },
            # Parameters for the chat room operations
            "room_id": {
                "type": "string",
                "description": "Chat room ID (required for the chat_get_room_members and chat_send_room_message operations)",
            },
            "receiver_id": {
                "type": "string",
                "description": "Receiver ID (required for the chat_send_private_message operation, can be a client_id or user_id)",
            },
            # Parameters for the eval_js operation
            "code": {
                "type": "string",
                "description": "The JavaScript code to execute (required for the eval_js operation), supports async/await, and the return value will be sent back",
            },
            "timeout": {
                "type": "number",
                "description": "Timeout for waiting for the frontend execution result (seconds, optional for the eval_js operation, defaults to 30)",
            },
            "target": {
                "type": "string",
                "description": "Target frontend (optional for the eval_js operation, defaults to current): current means the current active frontend; a specific client_id delivers precisely to a certain frontend connection (can be obtained via list_sessions); a specific session_id delivers to all frontends under that session; all broadcasts to all frontends",
            },
        },
        "required": ["action"],
    }

    def execute(
        self,
        action: str,
        agent_id: Optional[Union[str, list]] = None,
        message: str = "",
        node_id: Optional[str] = None,
        wait: bool = False,
        status_file: Optional[str] = None,
        path: str = "",
        command: str = "",
        agent_type: Optional[str] = None,
        working_dir: Optional[str] = None,
        agent_name: Optional[str] = None,
        llm_group: Optional[str] = None,
        tool_group: Optional[str] = None,
        config_file: Optional[str] = None,
        task: Optional[str] = None,
        additional_args: Optional[str] = None,
        worktree: bool = False,
        quick_mode: bool = False,
        restore: bool = False,
        restore_session: Optional[Union[bool, str]] = None,
        no_interaction_mode: bool = False,
        owner_id: Optional[str] = None,
        proxy_node: Optional[str] = None,
        access_acl: Optional[Dict[str, Any]] = None,
        timer_id: Optional[str] = None,
        schedule: Optional[Dict[str, Any]] = None,
        timer_action_type: Optional[str] = None,
        timer_action_params: Optional[Dict[str, Any]] = None,
        group_id: Optional[str] = None,
        group_name: Optional[str] = None,
        group_description: Optional[str] = None,
        room_id: Optional[str] = None,
        receiver_id: Optional[str] = None,
        code: str = "",
        timeout: float = 30.0,
        target: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute a Gateway management operation

        Parameters:
            action: Operation type (send_to_agent, list_agents, list_nodes, list_model_groups, create_agent, list_directory, delete_agent, get_node_secret, update_nodes_code, restart_nodes, create_timer, list_timers, get_timer, delete_timer, create_group, list_groups, get_group, join_group, leave_group, send_group_message)
            agent_id: Target Agent ID
            message: Message content
            node_id: Target node ID
            path: Directory path (list_directory)
            agent_type: Agent type (create_agent)
            working_dir: Working directory (create_agent)
            agent_name: Agent name (create_agent)
            llm_group: Model group (create_agent)
            tool_group: Tool group (create_agent)
            config_file: Configuration file (create_agent)
            task: Task description (create_agent)
            additional_args: Additional parameters (create_agent)
            worktree: Whether to use a worktree (create_agent)
            quick_mode: Quick mode (create_agent)
            restore_session: Restore session (create_agent)
            no_interaction_mode: No-interaction mode (create_agent)
            owner_id: Agent owner user ID (create_agent, automatically inferred when unspecified)
            proxy_node: Proxy node ID (create_agent)
            access_acl: Access control (create_agent)
            timer_id: Scheduled task ID (get_timer, delete_timer)
            schedule: Scheduling configuration (create_timer)
            timer_action_type: Scheduled task action type (create_timer)
            timer_action_params: Scheduled task action parameters (create_timer)
            group_id: Group ID (get_group, join_group, leave_group, send_group_message)
            group_name: Group name (create_group)
            group_description: Group description (create_group)
            room_id: Chat room ID (chat_get_room_members, chat_send_room_message)
            receiver_id: Receiver ID (chat_send_private_message)
            code: The JavaScript code to execute (eval_js)
            timeout: Timeout in seconds for waiting for the frontend execution result (eval_js)
            target: Target frontend (eval_js)
            **kwargs: Other parameters

        Returns:
            Dict[str, Any]: Execution result
        """
        # Compatible with the v1.0 protocol: registry may pass the entire parameter dictionary in as action
        if isinstance(action, dict):
            args = action
            action = args.get("action", "")
            agent_id = args.get("agent_id")
            message = args.get("message", "")
            node_id = args.get("node_id")
            wait = args.get("wait", False)
            status_file = args.get("status_file")
            path = args.get("path", "")
            command = args.get("command", "")
            agent_type = args.get("agent_type")
            working_dir = args.get("working_dir")
            agent_name = args.get("agent_name")
            llm_group = args.get("llm_group")
            tool_group = args.get("tool_group")
            config_file = args.get("config_file")
            task = args.get("task")
            additional_args = args.get("additional_args")
            worktree = args.get("worktree", False)
            quick_mode = args.get("quick_mode", False)
            restore_session = args.get("restore_session")
            no_interaction_mode = args.get("no_interaction_mode", False)
            owner_id = args.get("owner_id")
            proxy_node = args.get("proxy_node")
            access_acl = args.get("access_acl")
            timer_id = args.get("timer_id")
            schedule = args.get("schedule")
            timer_action_type = args.get("timer_action_type")
            timer_action_params = args.get("timer_action_params")
            group_id = args.get("group_id")
            group_name = args.get("group_name")
            group_description = args.get("group_description")
            room_id = args.get("room_id")
            receiver_id = args.get("receiver_id")
            code = args.get("code", "")
            timeout = args.get("timeout", 30.0)
            target = args.get("target")
        try:
            if action == "send_to_agent":
                return self._send_to_agent(
                    agent_id, message, node_id=node_id, wait=wait, status_file=status_file
                )
            elif action == "list_agents":
                return self._list_agents()
            elif action == "list_nodes":
                return self._list_nodes()
            elif action == "get_master_url":
                return self._get_master_url_info()
            elif action == "list_model_groups":
                return self._list_model_groups(node_id)
            elif action == "create_agent":
                return self._create_agent(
                    agent_type=agent_type,
                    working_dir=working_dir,
                    name=agent_name,
                    llm_group=llm_group,
                    tool_group=tool_group,
                    config_file=config_file,
                    task=task,
                    additional_args=additional_args,
                    worktree=worktree,
                    quick_mode=quick_mode,
                    restore=restore,
                    restore_session=restore_session,
                    no_interaction_mode=no_interaction_mode,
                    node_id=node_id,
                    owner_id=owner_id,
                    proxy_node=proxy_node,
                    access_acl=access_acl,
                )
            elif action == "list_directory":
                return self._list_directory(path=path, node_id=node_id)
            elif action == "exec_command":
                return self._exec_command(
                    command=command,
                    node_id=node_id,
                    working_dir=working_dir,
                    timeout=timeout,
                )
            elif action == "delete_agent":
                return self._delete_agent(agent_id=agent_id, node_id=node_id)
            elif action == "get_node_secret":
                return self._get_node_secret()
            elif action == "update_nodes_code":
                return self._update_nodes_code()
            elif action == "restart_nodes":
                return self._restart_nodes()
            elif action == "create_timer":
                return self._create_timer(
                    node_id=node_id,
                    schedule=schedule,
                    timer_action_type=timer_action_type,
                    timer_action_params=timer_action_params,
                )
            elif action == "list_timers":
                return self._list_timers()
            elif action == "get_timer":
                return self._get_timer(timer_id=timer_id)
            elif action == "delete_timer":
                return self._delete_timer(timer_id=timer_id)
            elif action == "create_group":
                return self._create_group(
                    group_name=group_name, group_description=group_description
                )
            elif action == "list_groups":
                return self._list_groups()
            elif action == "get_group":
                return self._get_group(group_id=group_id)
            elif action == "join_group":
                return self._join_group(group_id=group_id)
            elif action == "leave_group":
                return self._leave_group(group_id=group_id)
            elif action == "send_group_message":
                return self._send_group_message(group_id=group_id, message=message)
            elif action == "chat_list_rooms":
                return self._chat_list_rooms()
            elif action == "chat_get_online_clients":
                return self._chat_get_online_clients()
            elif action == "list_sessions":
                return self._list_sessions()
            elif action == "chat_get_room_members":
                return self._chat_get_room_members(room_id=room_id)
            elif action == "chat_send_room_message":
                return self._chat_send_room_message(room_id=room_id, message=message)
            elif action == "chat_send_private_message":
                return self._chat_send_private_message(
                    receiver_id=receiver_id, message=message
                )
            elif action == "eval_js":
                return self._eval_js(code=code, timeout=timeout, target=target)
            elif action == "regenerate_agent":
                # Support batch regeneration
                if isinstance(agent_id, list):
                    results = []
                    for single_id in agent_id:
                        result = self._regenerate_agent(
                            agent_id=single_id, node_id=node_id
                        )
                        results.append({"agent_id": single_id, **result})

                    # Determine whether the whole is successful
                    all_success = all(r.get("success", False) for r in results)
                    return {
                        "success": all_success,
                        "stdout": json.dumps(results, ensure_ascii=False, indent=2),
                        "stderr": ""
                        if all_success
                        else "Some agents failed to regenerate",
                    }
                else:
                    return self._regenerate_agent(agent_id=agent_id, node_id=node_id)
            else:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Unknown action: {action}",
                }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
            }

    def _get_master_url(self, action_name: str = "") -> Optional[Dict[str, Any]]:
        """Get master_url; returns an error dictionary when not set.

        Parameters:
            action_name: Operation name, used for error messages

        Returns:
            None means master_url is available, otherwise returns an error dictionary
        """
        if not jglobals.master_url:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"master_url is not set, cannot {action_name}. "
                "Please ensure the agent is started with --master-url option.",
            }
        return None

    def _build_auth_headers(self) -> Dict[str, str]:
        """Build the request headers with authentication information.

        Returns:
            Dict[str, str]: Request header dictionary
        """
        headers: Dict[str, str] = {}
        auth_token = os.environ.get("HAIJUNBOT_AUTH_TOKEN")
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        return headers

    def _request_gateway(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
        error_prefix: str = "Request failed",
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """Send an HTTP request to the Gateway.

        Parameters:
            method: HTTP method (GET/POST/PATCH/DELETE)
            path: Request path (such as /api/agents)
            json_data: JSON data for POST/PATCH requests
            params: Query parameters for GET/DELETE requests
            error_prefix: Error message prefix
            timeout: HTTP request timeout (seconds)

        Returns:
            Dict[str, Any]: Request result, containing the success/status_code/data fields
        """
        url = f"{jglobals.master_url}{path}"
        headers = self._build_auth_headers()

        try:
            with httpx.Client(timeout=timeout) as client:
                if method.upper() == "POST":
                    response = client.post(url, json=json_data, headers=headers)
                elif method.upper() == "PATCH":
                    response = client.patch(url, json=json_data, headers=headers)
                elif method.upper() == "DELETE":
                    response = client.delete(url, headers=headers, params=params)
                else:
                    response = client.get(url, headers=headers, params=params)

            if response.status_code == 200:
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "data": response.json(),
                }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "data": None,
                    "error": f"{error_prefix}: HTTP {response.status_code} - {response.text}",
                }
        except httpx.ConnectError:
            return {
                "success": False,
                "status_code": None,
                "data": None,
                "error": f"Cannot connect to gateway at {jglobals.master_url}. Please ensure the gateway is running.",
            }
        except Exception as e:
            return {
                "success": False,
                "status_code": None,
                "data": None,
                "error": f"{error_prefix}: {str(e)}",
            }

    def _handle_gateway_response(
        self, result: Dict[str, Any], success_data_key: str = "data"
    ) -> Dict[str, Any]:
        """Common logic for handling Gateway responses.

        Parameters:
            result: The return result of _request_gateway
            success_data_key: The key name for extracting data on success

        Returns:
            Dict[str, Any]: Standardized execution result
        """
        if not result["success"]:
            return {"success": False, "stdout": "", "stderr": result["error"]}

        gateway_data = result["data"]
        if not gateway_data.get("success"):
            error_info = gateway_data.get("error", {})
            error_msg = (
                error_info.get("message", "unknown error")
                if isinstance(error_info, dict)
                else str(error_info)
            )
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Gateway returned error: {error_msg}",
            }

        return {
            "success": True,
            "stdout": json.dumps(
                gateway_data.get(success_data_key, {}), ensure_ascii=False
            ),
            "stderr": "",
        }

    def _send_to_agent(
        self,
        agent_id: Any,
        message: str,
        node_id: Optional[str] = None,
        wait: bool = False,
        status_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a message to the specified Agent(s).

        Send messages via the Web Gateway's /api/agent/{agent_id}/message endpoint,
        and the Gateway will proxy the request to the target Agent's /message endpoint.
        When the target Agent is on a child node, forward through the /api/node/{node_id}/agent/{agent_id}/message route.

        Parameters:
            agent_id: Target Agent ID (supports str or List[str])
            message: Message content
            node_id: Target node ID (optional; when unspecified, automatically queries the node where the Agent resides)
            wait: Whether to synchronously wait for the Agent to finish processing (default False, backward-compatible asynchronous fire-and-forget).
                  When wait=True, if status_file is provided, poll that local status file to determine completion;
                  otherwise poll changes to the execution_status of each Agent's /status (fallback, not entirely reliable).
            status_file: Path to the phase completion status file (optional, used with wait=True). After the Agent completes the task
                 it writes {"status": "completed"|"failed"} to this file, and this method polls it to determine completion.

        Returns:
            Dict[str, Any]: Send result
        """
        if not agent_id:
            return {"success": False, "stdout": "", "stderr": "agent_id is required"}

        if not message:
            return {"success": False, "stdout": "", "stderr": "message is required"}

        err = self._get_master_url("send message to agent")
        if err:
            return err

        # Normalize agent_ids into a list
        target_ids = []
        if isinstance(agent_id, str):
            # Support comma-separated strings
            target_ids = [aid.strip() for aid in agent_id.split(",") if aid.strip()]
        elif isinstance(agent_id, list):
            target_ids = [str(aid).strip() for aid in agent_id if str(aid).strip()]
        else:
            return {"success": False, "stdout": "", "stderr": "Invalid agent_id type"}

        if not target_ids:
            return {
                "success": False,
                "stdout": "",
                "stderr": "No valid agent_id provided",
            }

        sender_id = jglobals.agent_id
        # Add a reply hint at the end of the message
        enhanced_message = f"{message}\n\n---\nTo reply to this message use: gateway_manager action=send_to_agent agent_id={sender_id} message=<your reply>"

        results = []
        all_success = True

        # Build agent_id -> node_id mapping to determine the routing path
        agent_node_map: Dict[str, str] = {}
        if node_id:
            # The user specified node_id, so all target Agents use the same node_id
            for target_id in target_ids:
                agent_node_map[target_id] = node_id
        else:
            # node_id not specified, query the Agent list to get the node of each Agent
            try:
                agents_result = self._request_gateway(
                    method="GET",
                    path="/api/agents",
                    error_prefix="Failed to query agent list",
                )
                if agents_result["success"]:
                    agents_data = agents_result["data"]
                    if agents_data.get("success"):
                        for agent_info in agents_data.get("data") or []:
                            aid = str(agent_info.get("agent_id", ""))
                            if aid in target_ids:
                                agent_node_map[aid] = agent_info.get(
                                    "node_id", "master"
                                )
            except Exception:
                pass  # Fall back to the original path when the query fails

        for target_id in target_ids:
            target_node_id = agent_node_map.get(target_id)
            # Determine whether child-node routing is needed
            if target_node_id and target_node_id != "master":
                # Child-node Agent: route via /api/node/{node_id}/agent/{agent_id}/message
                path = f"/api/node/{target_node_id}/agent/{target_id}/message"
            else:
                # Local/master Agent: use the original path
                path = f"/api/agent/{target_id}/message"

            result = self._request_gateway(
                method="POST",
                path=path,
                json_data={"sender_id": sender_id, "content": enhanced_message},
                error_prefix=f"Failed to send message to agent {target_id}",
            )

            if result["success"]:
                results.append(
                    {
                        "agent_id": target_id,
                        "status": "sent",
                        "response": result["data"],
                    }
                )
            else:
                all_success = False
                results.append(
                    {
                        "agent_id": target_id,
                        "status": "failed",
                        "error": result["error"],
                    }
                )

        output = {
            "sender_id": sender_id,
            "message": message,
            "results": results,
        }

        stdout_str = json.dumps(output, ensure_ascii=False, indent=2)
        if all_success:
            stdout_str += "\n\nIf you want to wait for a response, output <Wait>."

        # wait=true: synchronously wait for the Agent to finish (Plan A: poll status_file first, otherwise poll /status as a fallback)
        if wait:
            if status_file:
                wait_ok, wait_err = self._wait_status_file(status_file)
            else:
                wait_ok, wait_err = self._wait_agent_status(
                    target_ids, agent_node_map
                )
            if not wait_ok:
                return {
                    "success": False,
                    "stdout": stdout_str,
                    "stderr": wait_err,
                }
            stdout_str += (
                "\n\n[wait] Agent processing completed"
                + (f"(status_file: {status_file})" if status_file else "")
            )

        return {
            "success": all_success,
            "stdout": stdout_str,
            "stderr": "" if all_success else "Some messages failed to send",
        }

    def _wait_status_file(
        self, status_file: str, timeout: float = 1800.0
    ) -> tuple:
        """Poll the local status_file to determine whether the Agent is done (Plan A's reliable completion signal).

        After the Agent completes the task it writes {"status": "completed"|"failed"} to this file.

        Returns:
            (ok, error): ok=True means completed, otherwise False with an error message
        """
        status_path = Path(status_file)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if status_path.exists():
                try:
                    data = json.loads(status_path.read_text(encoding="utf-8"))
                    status = str(data.get("status") or "")
                    if status == "completed":
                        return True, ""
                    if status == "failed":
                        err = data.get("error") or ""
                        return False, f"Agent task failed: {err}"
                except (json.JSONDecodeError, OSError):
                    # The file may be being written, retry later
                    pass
            time.sleep(2.0)
        return False, f"Timed out waiting for Agent completion (>{int(timeout)} seconds), status_file={status_file}"

    def _wait_agent_status(
        self, target_ids: List[str], agent_node_map: Dict[str, str], timeout: float = 1800.0
    ) -> tuple:
        """Poll each Agent's /status execution_status changes (fallback, not fully reliable).

        Since the agent state machine has no "idle/completed" state, we can only approximate
        "completion of one message" by execution_status changing from running to waiting_*. This is Plan A's fallback path;
        the reliable completion signal should prefer status_file.

        Returns:
            (ok, error): ok=True means a completion signal was observed, otherwise False with an error message
        """
        deadline = time.time() + timeout
        # Record each agent's initial execution_status and watch for changes
        while time.time() < deadline:
            all_done = True
            for target_id in target_ids:
                target_node_id = agent_node_map.get(target_id)
                if target_node_id and target_node_id != "master":
                    path = f"/api/node/{target_node_id}/agent/{target_id}/status"
                else:
                    path = f"/api/agent/{target_id}/status"
                result = self._request_gateway(
                    method="GET",
                    path=path,
                    error_prefix=f"Failed to query status of agent {target_id}",
                )
                if not result["success"]:
                    all_done = False
                    continue
                # /status returns a flat structure {"execution_status","status","non_interactive"}
                status_body = result["data"] or {}
                execution_status = (
                    status_body.get("execution_status")
                    if isinstance(status_body, dict)
                    else None
                )
                # A non-running status is treated as "current message processed" (approximate)
                if execution_status == "running":
                    all_done = False
            if all_done:
                return True, ""
            time.sleep(2.0)
        return False, f"Timed out waiting for Agent completion (>{int(timeout)} seconds)"

    def _resolve_node_id(self, agent_id: str, node_id: Optional[str] = None) -> str:
        """Resolve the node ID where the Agent resides.

        If node_id is not specified, query it from the Agent list.

        Args:
            agent_id: Agent ID
            node_id: target node ID (optional)

        Returns:
            str: node ID

        Raises:
            ValueError: if the node ID cannot be resolved
        """
        if node_id:
            return node_id

        # Get the Agent list
        list_result = self._list_agents()
        if not list_result["success"]:
            raise ValueError(
                f"Failed to list agents: {list_result.get('stderr', 'unknown error')}"
            )

        # Parse the Agent list
        try:
            agents_data = json.loads(list_result["stdout"])
            agents = agents_data.get("agents", [])
        except (json.JSONDecodeError, KeyError):
            raise ValueError("Failed to parse agents list")

        # Find the target Agent
        for agent in agents:
            if agent.get("agent_id") == agent_id:
                resolved_node_id = agent.get("node_id")
                if resolved_node_id:
                    return resolved_node_id
                else:
                    raise ValueError(f"Agent {agent_id} has no node_id information")

        raise ValueError(f"Agent {agent_id} not found")

    def _list_agents(self) -> Dict[str, Any]:
        """Get the list of all Agents.

        Get the Agent list via the Web Gateway's /api/agents interface,
        returning basic information for all Agents.

        Returns:
            Dict[str, Any]: Agent list
        """
        err = self._get_master_url("list agents")
        if err:
            return err

        result = self._request_gateway(
            method="GET",
            path="/api/agents",
            error_prefix="Failed to list agents",
        )

        if result["success"]:
            gateway_data = result["data"]
            if not gateway_data.get("success"):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Gateway returned error: {gateway_data.get('error', 'unknown error')}",
                }

            agents = gateway_data.get("data", [])
            current_agent_id = jglobals.agent_id
            result_data = {
                "current_agent_id": current_agent_id,
                "agents": agents,
            }
            return {
                "success": True,
                "stdout": json.dumps(result_data, ensure_ascii=False, indent=2),
                "stderr": "",
            }
        else:
            return {"success": False, "stdout": "", "stderr": result["error"]}

    def _list_nodes(self) -> Dict[str, Any]:
        """Get node list information.

        Get node information via the Web Gateway's /api/node/status interface,
        including this node's config, running status, registered child nodes, Agent routing, etc.

        Returns:
            Dict[str, Any]: node status information
        """
        err = self._get_master_url("list nodes")
        if err:
            return err

        result = self._request_gateway(
            method="GET",
            path="/api/node/status",
            error_prefix="Failed to list nodes",
        )

        if result["success"]:
            gateway_data = result["data"]
            if not gateway_data.get("success"):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Gateway returned error: {gateway_data.get('error', 'unknown error')}",
                }

            # Extract node-related information
            data = gateway_data.get("data", {})
            current_node_id = data.get("node", {}).get("node_id")
            current_agent_id = jglobals.agent_id
            node_info = {
                "current_node_id": current_node_id,
                "current_agent_id": current_agent_id,
                "node": data.get("node", {}),
                "runtime_status": data.get("runtime_status", "unknown"),
                "nodes": data.get("nodes", []),
                "agent_routes": data.get("agent_routes", []),
            }
            return {
                "success": True,
                "stdout": json.dumps(node_info, ensure_ascii=False, indent=2),
                "stderr": "",
            }
        else:
            return {"success": False, "stdout": "", "stderr": result["error"]}

    def _get_master_url_info(self) -> Dict[str, Any]:
        """Get the master gateway address used by the current node.

        Directly read jglobals.master_url in this process (injected by the --master-url startup argument or
        the HAIJUNBOT_MASTER_URL environment variable), without making an HTTP request.
        Child-node Agents can use it to obtain the correct master address and avoid mistakenly using 127.0.0.1.

        Returns:
            Dict[str, Any]: result containing master_url and other information
        """
        master_url = jglobals.master_url
        info = {
            "master_url": master_url,
            "env_master_url": os.environ.get("HAIJUNBOT_MASTER_URL", ""),
            "proxy_node": jglobals.proxy_node,
            "current_agent_id": jglobals.agent_id,
        }
        if not master_url:
            return {
                "success": False,
                "stdout": json.dumps(info, ensure_ascii=False, indent=2),
                "stderr": "master_url is not set. "
                "Please ensure the agent is started with --master-url option "
                "or HAIJUNBOT_MASTER_URL env var.",
            }
        return {
            "success": True,
            "stdout": json.dumps(info, ensure_ascii=False, indent=2),
            "stderr": "",
        }

    def _list_model_groups(self, node_id: Optional[str] = None) -> Dict[str, Any]:
        """Get the list of model groups for the specified node.

        Get the model group list via the Web Gateway's /api/node/{node_id}/model-groups interface,
        supporting cross-node queries; the master node proxies the request to the target node.

        Args:
            node_id: target node ID, defaults to master

        Returns:
            Dict[str, Any]: model group list
        """
        target_node = node_id or "master"

        err = self._get_master_url("list model groups")
        if err:
            return err

        result = self._request_gateway(
            method="GET",
            path=f"/api/node/{target_node}/model-groups",
            error_prefix="Failed to list model groups",
        )

        if result["success"]:
            gateway_data = result["data"]
            if not gateway_data.get("success"):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Gateway returned error: {gateway_data.get('error', 'unknown error')}",
                }

            data = gateway_data.get("data", [])
            default_llm_group = gateway_data.get("default_llm_group", "")
            output = {
                "model_groups": data,
                "default_llm_group": default_llm_group,
            }
            return {
                "success": True,
                "stdout": json.dumps(output, ensure_ascii=False, indent=2),
                "stderr": "",
            }
        else:
            return {"success": False, "stdout": "", "stderr": result["error"]}

    def _create_agent(
        self,
        agent_type: Optional[str] = None,
        working_dir: Optional[str] = None,
        name: Optional[str] = None,
        llm_group: Optional[str] = None,
        tool_group: Optional[str] = None,
        config_file: Optional[str] = None,
        task: Optional[str] = None,
        additional_args: Optional[str] = None,
        worktree: bool = False,
        quick_mode: bool = False,
        restore: bool = False,
        restore_session: Optional[Union[bool, str]] = None,
        no_interaction_mode: bool = False,
        node_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        proxy_node: Optional[str] = None,
        access_acl: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new Agent.

        Create an Agent via the Web Gateway's POST /api/agents interface,
        supporting cross-node creation (specify the target node via the node_id parameter).

        Args:
            agent_type: Agent type (required), such as code, chat, etc.
            working_dir: working directory (required)
            name: Agent name
            llm_group: model group name
            tool_group: tool group name
            config_file: config file path
            task: initial task description
            additional_args: additional arguments
            worktree: whether to use a git worktree
            quick_mode: whether to enable quick mode
            restore_session: whether to restore the previous session
            no_interaction_mode: whether to enable non-interactive mode (task is required when enabled)
            node_id: target node ID
            owner_id: Agent owner user ID (optional; when unspecified it is automatically inferred as the current Agent's owner)
            proxy_node: proxy node ID (optional)
            access_acl: access control (optional, in the form {"read": [...], "interact": [...]})

        Returns:
            Dict[str, Any]: creation result
        """
        if not agent_type:
            return {"success": False, "stdout": "", "stderr": "agent_type is required"}
        if not working_dir:
            return {"success": False, "stdout": "", "stderr": "working_dir is required"}
        if no_interaction_mode and not task:
            return {
                "success": False,
                "stdout": "",
                "stderr": "task is required when no_interaction_mode is enabled",
            }

        err = self._get_master_url("create agent")
        if err:
            return err

        # Validate worktree conflicts
        conflict = self._check_worktree_conflict(
            agent_type, worktree, working_dir, node_id
        )
        if conflict:
            return conflict

        # Build the request body and send it
        body = self._build_create_agent_body(
            agent_type=agent_type,
            working_dir=working_dir,
            name=name,
            llm_group=llm_group,
            tool_group=tool_group,
            config_file=config_file,
            task=task,
            additional_args=additional_args,
            worktree=worktree,
            quick_mode=quick_mode,
            restore_session=restore_session,
            no_interaction_mode=no_interaction_mode,
            node_id=node_id,
            owner_id=self._resolve_owner_id(owner_id),
            proxy_node=proxy_node,
            access_acl=access_acl,
        )

        result = self._request_gateway(
            method="POST",
            path="/api/agents",
            json_data=body,
            error_prefix="Failed to create agent",
        )

        if result["success"]:
            gateway_data = result["data"]
            # Fix: handle a list-type response
            if isinstance(gateway_data, list):
                if len(gateway_data) == 0:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": "Gateway returned empty list",
                    }
                elif len(gateway_data) == 1:
                    gateway_data = gateway_data[0]
                else:
                    # Multiple results; take the first and log a warning
                    import logging

                    logging.warning(
                        f"Gateway returned list with {len(gateway_data)} items, using first one"
                    )
                    gateway_data = gateway_data[0]

            if not gateway_data.get("success"):
                error_info = gateway_data.get("error", {})
                error_msg = (
                    error_info.get("message", "unknown error")
                    if isinstance(error_info, dict)
                    else str(error_info)
                )
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Gateway returned error: {error_msg}",
                }

            agent_info = gateway_data.get("data", {})
            return {
                "success": True,
                "stdout": json.dumps(agent_info, ensure_ascii=False, indent=2),
                "stderr": "",
            }
        else:
            return {"success": False, "stdout": "", "stderr": result["error"]}

    def _check_worktree_conflict(
        self,
        agent_type: Optional[str],
        worktree: bool,
        working_dir: Optional[str],
        node_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Validate that the same node and same working directory cannot have two code_agents without worktree enabled at the same time.

        Args:
            agent_type: Agent type
            worktree: whether worktree is enabled
            working_dir: working directory
            node_id: target node ID

        Returns:
            Returns an error dict on conflict, None if there is no conflict
        """
        if agent_type != "code_agent" or worktree:
            return None

        target_node_id = (node_id or "master").strip() or "master"
        normalized_dir = (working_dir or "").strip()

        agents_result = self._request_gateway(
            method="GET",
            path="/api/agents",
            error_prefix="Failed to get agents list for worktree check",
        )

        if not agents_result["success"]:
            return None

        agents_data = agents_result["data"]
        # Fix: handle a list-type response
        if isinstance(agents_data, list):
            if len(agents_data) == 0:
                return None
            elif len(agents_data) == 1:
                agents_data = agents_data[0]
            else:
                # Multiple results; take the first and log a warning
                import logging

                logging.warning(
                    f"Gateway returned list with {len(agents_data)} items in worktree check, using first one"
                )
                agents_data = agents_data[0]

        if not agents_data.get("success"):
            return None

        # Fix: correctly handle the case where the data field is a list
        data_field = agents_data.get("data", {})
        if isinstance(data_field, list):
            # data is a list, use it directly as agents_list
            agents_list = data_field
        elif isinstance(data_field, dict):
            # data is a dict, get the list from the agents key
            agents_list = data_field.get("agents", [])
        else:
            agents_list = []
        for agent in agents_list:
            # A stopped agent does not conflict
            if agent.get("status") in ("stopped", "completed", "failed", "abandoned"):
                continue
            if agent.get("agent_type") != "code_agent":
                continue
            if agent.get("worktree"):
                continue
            agent_node_id = (agent.get("node_id") or "").strip() or "master"
            if agent_node_id != target_node_id:
                continue
            if (agent.get("working_dir") or "").strip() != normalized_dir:
                continue
            conflict_name = agent.get("name") or agent.get("agent_id") or "unnamed"
            return {
                "success": False,
                "stdout": "",
                "stderr": (
                    f"Working directory conflict: node {target_node_id} already has a code Agent without worktree enabled \"{conflict_name}\"."
                    f"Only one code Agent without worktree enabled is allowed per working directory."
                    f"Please enable worktree or choose another working directory."
                ),
            }

        return None

    def _resolve_owner_id(self, owner_id: Optional[str]) -> Optional[str]:
        """Resolve the owner user ID for the Agent being created.

        If the caller explicitly specifies owner_id, use it directly;
        otherwise look up the owner_id of the current Agent (jglobals.agent_id) via GET /api/agents,
        so that Agents created via orchestration etc. belong to the initiator rather than defaulting to system.

        Args:
            owner_id: explicitly specified owner user ID (optional)

        Returns:
            Optional[str]: owner user ID, returns None when it cannot be resolved (the gateway side provides the fallback)
        """
        if owner_id:
            return owner_id

        current_agent_id = jglobals.agent_id
        if not current_agent_id:
            return None

        try:
            result = self._request_gateway(
                method="GET",
                path="/api/agents",
                error_prefix="Failed to resolve owner id",
            )
            if not result["success"]:
                return None

            gateway_data = result["data"]
            if not isinstance(gateway_data, dict) or not gateway_data.get("success"):
                return None

            # Support both forms: data as a list or {"agents": [...]}
            data_field = gateway_data.get("data", {})
            if isinstance(data_field, list):
                agents_list = data_field
            elif isinstance(data_field, dict):
                agents_list = data_field.get("agents", [])
            else:
                agents_list = []

            for agent in agents_list:
                if str(agent.get("agent_id", "")) == str(current_agent_id):
                    resolved = agent.get("owner_id")
                    return resolved or None
        except Exception:
            return None

        return None

    def _build_create_agent_body(
        self,
        agent_type: Optional[str] = None,
        working_dir: Optional[str] = None,
        name: Optional[str] = None,
        llm_group: Optional[str] = None,
        tool_group: Optional[str] = None,
        config_file: Optional[str] = None,
        task: Optional[str] = None,
        additional_args: Optional[str] = None,
        worktree: bool = False,
        quick_mode: bool = False,
        restore: bool = False,
        restore_session: Optional[Union[bool, str]] = None,
        no_interaction_mode: bool = False,
        node_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        proxy_node: Optional[str] = None,
        access_acl: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build the request body for creating an Agent, including only non-empty parameters."""
        body: Dict[str, Any] = {
            "agent_type": agent_type,
            "working_dir": working_dir,
        }
        if name:
            body["name"] = name
        if llm_group:
            body["llm_group"] = llm_group
        if tool_group:
            body["tool_group"] = tool_group
        if config_file:
            body["config_file"] = config_file
        if task:
            body["task"] = task
        if additional_args:
            body["additional_args"] = additional_args
        if worktree:
            body["worktree"] = True
        if quick_mode:
            body["quick_mode"] = True
        if restore_session:
            body["restore_session"] = restore_session
        if restore:
            body["restore"] = True
        if no_interaction_mode:
            body["no_interaction_mode"] = True
        if node_id:
            body["node_id"] = node_id
        if owner_id:
            body["owner_id"] = owner_id
        if proxy_node:
            body["proxy_node"] = proxy_node
        if access_acl:
            body["access_acl"] = access_acl
        return body

    def _list_directory(
        self, path: str = "", node_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get the list of files/directories under the specified path.

        Get the directory list via the Web Gateway's GET /api/directories interface,
        supporting cross-node queries (specify the target node via the node_id parameter).

        Args:
            path: directory path, defaults to empty (meaning the user's home directory)
            node_id: target node ID, defaults to empty (meaning this node)

        Returns:
            Dict[str, Any]: directory list
        """
        err = self._get_master_url("list directory")
        if err:
            return err

        # Build query parameters
        query_params: Dict[str, str] = {}
        if path:
            query_params["path"] = path
        if node_id:
            query_params["node_id"] = node_id

        result = self._request_gateway(
            method="GET",
            path="/api/directories",
            params=query_params if query_params else None,
            error_prefix="Failed to list directory",
        )

        if result["success"]:
            gateway_data = result["data"]
            if not gateway_data.get("success"):
                error_detail = gateway_data.get("error", "unknown error")
                if isinstance(error_detail, dict):
                    error_msg = error_detail.get("message", str(error_detail))
                else:
                    error_msg = str(error_detail)
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Gateway returned error: {error_msg}",
                }

            data = gateway_data.get("data", {})
            return {
                "success": True,
                "stdout": json.dumps(data, ensure_ascii=False, indent=2),
                "stderr": "",
            }
        else:
            return {"success": False, "stdout": "", "stderr": result["error"]}

    def _exec_command(
        self,
        command: str,
        node_id: Optional[str] = None,
        working_dir: Optional[str] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Execute a shell command on the specified node.

        Execute the command via the Web Gateway's POST /api/node/{node_id}/exec interface,
        Permission checks (terminal:create + node access rights) are handled centrally by the master gateway,
        and child nodes trust the master's decision without re-authenticating.

        Args:
            command: the shell command to execute (required)
            node_id: target node ID, defaults to master
            working_dir: working directory for command execution (optional)
            timeout: command execution timeout in seconds

        Returns:
            Dict[str, Any]: execution result, containing stdout/stderr/exit_code
        """
        if not command:
            return {"success": False, "stdout": "", "stderr": "command is required"}

        err = self._get_master_url("execute command")
        if err:
            return err

        target_node = node_id or "master"
        body: Dict[str, Any] = {"command": command, "timeout": timeout}
        if working_dir:
            body["working_dir"] = working_dir

        result = self._request_gateway(
            method="POST",
            path=f"/api/node/{target_node}/exec",
            json_data=body,
            error_prefix="Failed to execute command",
            timeout=timeout + 10.0,
        )

        if result["success"]:
            gateway_data = result["data"]
            if not gateway_data.get("success"):
                error_info = gateway_data.get("error", {})
                error_msg = (
                    error_info.get("message", "unknown error")
                    if isinstance(error_info, dict)
                    else str(error_info)
                )
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Gateway returned error: {error_msg}",
                }

            data = gateway_data.get("data", {})
            return {
                "success": True,
                "stdout": json.dumps(data, ensure_ascii=False, indent=2),
                "stderr": "",
            }
        else:
            return {"success": False, "stdout": "", "stderr": result["error"]}

    def _get_node_secret(self) -> Dict[str, Any]:
        """Get the gateway's node connection private key.

        Get the node connection private key via the Web Gateway's GET /api/node/secret interface,
        this private key is used for authentication when a child node connects to the main gateway.

        Returns:
            Dict[str, Any]: result containing node_secret
        """
        err = self._get_master_url("get node secret")
        if err:
            return err

        result = self._request_gateway(
            method="GET",
            path="/api/node/secret",
            error_prefix="Failed to get node secret",
        )

        if result["success"]:
            gateway_data = result["data"]
            if not gateway_data.get("success"):
                error_info = gateway_data.get("error", {})
                error_msg = (
                    error_info.get("message", "unknown error")
                    if isinstance(error_info, dict)
                    else str(error_info)
                )
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Gateway returned error: {error_msg}",
                }

            data = gateway_data.get("data", {})
            node_secret = data.get("node_secret", "")
            return {
                "success": True,
                "stdout": json.dumps(
                    {"node_secret": node_secret}, ensure_ascii=False, indent=2
                ),
                "stderr": "",
            }
        else:
            return {"success": False, "stdout": "", "stderr": result["error"]}

    def _update_nodes_code(self) -> Dict[str, Any]:
        """Update all nodes' code to the main branch.

        Via the Web Gateway's POST /api/nodes/{node_id}/code-update interface,
        switch all online nodes' HaijunBot code to the main branch and pull the latest code.

        Returns:
            Dict[str, Any]: information containing each node's update result
        """
        err = self._get_master_url("update nodes code")
        if err:
            return err

        # First get all online nodes (via the /api/node/status interface)
        nodes_result = self._request_gateway(
            method="GET",
            path="/api/node/status",
            error_prefix="Failed to get nodes list",
        )

        if not nodes_result["success"]:
            return {"success": False, "stdout": "", "stderr": nodes_result["error"]}

        gateway_data = nodes_result["data"]
        if not gateway_data.get("success"):
            error_info = gateway_data.get("error", {})
            error_msg = (
                error_info.get("message", "unknown error")
                if isinstance(error_info, dict)
                else str(error_info)
            )
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Gateway returned error: {error_msg}",
            }

        # /api/node/status return structure: {"success": True, "data": {"nodes": [...]}}
        nodes_data = gateway_data.get("data", {})
        nodes = nodes_data.get("nodes", [])
        if not nodes:
            return {
                "success": False,
                "stdout": "",
                "stderr": "No online nodes available for code update",
            }

        # Perform a code update on each node
        results = []
        success_count = 0
        for node in nodes:
            node_id = node.get("node_id", "")
            if not node_id:
                continue

            update_result = self._request_gateway(
                method="POST",
                path=f"/api/nodes/{node_id}/code-update",
                error_prefix=f"Failed to update code for node {node_id}",
            )

            if update_result["success"]:
                update_data = update_result["data"]
                if update_data.get("success"):
                    success_count += 1
                    data = update_data.get("data", {})
                    results.append(
                        {
                            "node_id": node_id,
                            "success": True,
                            "message": data.get("message", "Update successful"),
                        }
                    )
                else:
                    error_info = update_data.get("error", {})
                    error_msg = (
                        error_info.get("message", "unknown error")
                        if isinstance(error_info, dict)
                        else str(error_info)
                    )
                    results.append(
                        {
                            "node_id": node_id,
                            "success": False,
                            "message": error_msg,
                        }
                    )
            else:
                results.append(
                    {
                        "node_id": node_id,
                        "success": False,
                        "message": update_result["error"],
                    }
                )

        total_count = len(nodes)
        if success_count == total_count:
            message = f"Code update successful, updated {success_count}/{total_count} nodes"
        elif success_count > 0:
            message = f"Code update partially successful, succeeded on {success_count}/{total_count} nodes"
        else:
            message = "Code update failed, no node was updated successfully"

        summary: Dict[str, Any] = {
            "total": total_count,
            "success": success_count,
            "failed": total_count - success_count,
            "results": results,
            "message": message,
        }

        return {
            "success": success_count > 0,
            "stdout": json.dumps(summary, ensure_ascii=False, indent=2),
            "stderr": "" if success_count > 0 else "All nodes failed to update",
        }

    def _restart_nodes(self) -> Dict[str, Any]:
        """Restart all node services with one click (skipping the current node).

        Via the Web Gateway's POST /api/nodes/{node_id}/service/restart interface,
        restart all child nodes in sequence, and finally restart the master node.
        Skip the current node (because the current node has Agents running).

        Returns:
            Dict[str, Any]: Information containing the restart result of each node
        """
        err = self._get_master_url("restart nodes")
        if err:
            return err
        # First get all online nodes (via the /api/node/status interface)
        nodes_result = self._request_gateway(
            method="GET",
            path="/api/node/status",
            error_prefix="Failed to get nodes list",
        )

        if not nodes_result["success"]:
            return {"success": False, "stdout": "", "stderr": nodes_result["error"]}

        gateway_data = nodes_result["data"]
        if not gateway_data.get("success"):
            error_info = gateway_data.get("error", {})
            error_msg = (
                error_info.get("message", "unknown error")
                if isinstance(error_info, dict)
                else str(error_info)
            )
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Gateway returned error: {error_msg}",
            }

        # /api/node/status return structure: {"success": True, "data": {"nodes": [...]}}
        nodes_data = gateway_data.get("data", {})
        nodes = nodes_data.get("nodes", [])
        if not nodes:
            return {
                "success": False,
                "stdout": "",
                "stderr": "No online nodes available for restart",
            }

        # Get the current node ID, skip the current node
        current_node_id = os.environ.get("NODE_ID", "master")

        # Sort: child nodes first, master last
        child_nodes = [n for n in nodes if n.get("node_id", "") != "master"]
        master_node = [n for n in nodes if n.get("node_id", "") == "master"]
        sorted_nodes = child_nodes + master_node

        # Execute restart for each node
        results = []
        success_count = 0
        skipped_count = 0
        for node in sorted_nodes:
            node_id = node.get("node_id", "")
            if not node_id:
                continue

            # Skip the current node
            if node_id == current_node_id:
                skipped_count += 1
                results.append(
                    {
                        "node_id": node_id,
                        "success": True,
                        "skipped": True,
                        "message": f"Skip the current node {node_id}(an Agent is running)",
                    }
                )
                continue

            restart_result = self._request_gateway(
                method="POST",
                path=f"/api/node/{node_id}/service/restart",
                json_data={"node_id": node_id, "restart_frontend": True},
                error_prefix=f"Failed to restart node {node_id}",
            )

            if restart_result["success"]:
                restart_data = restart_result["data"]
                if restart_data.get("success"):
                    success_count += 1
                    data = restart_data.get("data", {})
                    results.append(
                        {
                            "node_id": node_id,
                            "success": True,
                            "skipped": False,
                            "message": data.get("message", "restart request has been sent"),
                        }
                    )
                else:
                    error_info = restart_data.get("error", {})
                    error_msg = (
                        error_info.get("message", "unknown error")
                        if isinstance(error_info, dict)
                        else str(error_info)
                    )
                    results.append(
                        {
                            "node_id": node_id,
                            "success": False,
                            "skipped": False,
                            "message": error_msg,
                        }
                    )
            else:
                results.append(
                    {
                        "node_id": node_id,
                        "success": False,
                        "skipped": False,
                        "message": restart_result["error"],
                    }
                )

        total_count = len(sorted_nodes)
        restarted_count = total_count - skipped_count
        if success_count == restarted_count:
            message = (
                f"Node restart commands have been sent, succeeded for {success_count}/{restarted_count} nodes"
                + (f", skipped the current node {current_node_id}" if skipped_count > 0 else "")
            )
        elif success_count > 0:
            message = (
                f"Node restart partially succeeded, succeeded for {success_count}/{restarted_count} nodes"
                + (f", skipped the current node {current_node_id}" if skipped_count > 0 else "")
            )
        else:
            message = "Node restart failed, no node was restarted successfully"

        summary: Dict[str, Any] = {
            "total": total_count,
            "success": success_count,
            "skipped": skipped_count,
            "failed": restarted_count - success_count,
            "results": results,
            "message": message,
        }

        return {
            "success": success_count > 0,
            "stdout": json.dumps(summary, ensure_ascii=False, indent=2),
            "stderr": "" if success_count > 0 else "All nodes failed to restart",
        }

    def _delete_agent(
        self, agent_id: Optional[Union[str, list]] = None, node_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete the specified Agent (supports batch deletion).

        Delete Agents via the Web Gateway's DELETE /api/agents/{agent_id} interface,
        supports cross-node deletion (specify the target node via the node_id parameter).
        Supports passing a single agent_id string or a list of agent_id strings for batch deletion.

        Parameters:
            agent_id: The Agent ID to delete (required), supports a single string or a list of strings
            node_id: Target node ID, defaults to empty (means this node)

        Returns:
            Dict[str, Any]: Deletion result
                - For a single agent_id, returns a single deletion result
                - For a list agent_id, returns a result containing a results list
        """
        if not agent_id:
            return {"success": False, "stdout": "", "stderr": "agent_id is required"}

        # Handle batch deletion
        if isinstance(agent_id, list):
            results = []
            for single_id in agent_id:
                result = self._delete_single_agent(single_id, node_id)
                results.append({"agent_id": single_id, **result})

            # Determine whether the whole operation succeeded
            all_success = all(r.get("success", False) for r in results)
            return {
                "success": all_success,
                "stdout": json.dumps(results, ensure_ascii=False, indent=2),
                "stderr": "" if all_success else "Some agents failed to delete",
            }
        else:
            # Single deletion
            return self._delete_single_agent(agent_id, node_id)

    def _delete_single_agent(
        self, agent_id: str, node_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete a single Agent (internal method).

        Parameters:
            agent_id: The Agent ID to delete
            node_id: Target node ID

        Returns:
            Dict[str, Any]: Deletion result
        """
        # Parse the node ID
        try:
            resolved_node_id = self._resolve_node_id(agent_id, node_id)
        except ValueError as e:
            return {"success": False, "stdout": "", "stderr": str(e)}

        err = self._get_master_url("delete agent")
        if err:
            return err

        # Build query parameters
        query_params: Dict[str, str] = {}
        if resolved_node_id:
            query_params["node_id"] = resolved_node_id

        result = self._request_gateway(
            method="DELETE",
            path=f"/api/agents/{agent_id}",
            params=query_params if query_params else None,
            error_prefix=f"Failed to delete agent {agent_id}",
        )

        if result["success"]:
            gateway_data = result["data"]
            if not gateway_data.get("success"):
                error_info = gateway_data.get("error", {})
                error_msg = (
                    error_info.get("message", "unknown error")
                    if isinstance(error_info, dict)
                    else str(error_info)
                )
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Gateway returned error: {error_msg}",
                }

            data = gateway_data.get("data", {})
            return {
                "success": True,
                "stdout": json.dumps(data, ensure_ascii=False, indent=2),
                "stderr": "",
            }
        else:
            return {"success": False, "stdout": "", "stderr": result["error"]}

    def _create_timer(
        self,
        node_id: Optional[str] = None,
        schedule: Optional[Dict[str, Any]] = None,
        timer_action_type: Optional[str] = None,
        timer_action_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a scheduled task.

        Parameters:
            node_id: Target node ID (optional, defaults to master)
            schedule: Schedule configuration, choose one of three
            timer_action_type: Action type (create_agent / run_shell_command / capability_call)
            timer_action_params: Action parameters

        Returns:
            Dict[str, Any]: Execution result
        """
        if not schedule:
            return {"success": False, "stdout": "", "stderr": "schedule is required"}
        if not timer_action_type:
            return {
                "success": False,
                "stdout": "",
                "stderr": "timer_action_type is required",
            }
        if not timer_action_params:
            return {
                "success": False,
                "stdout": "",
                "stderr": "timer_action_params is required",
            }

        # Build the request body
        body = {
            "schedule": schedule,
            "action": {
                "type": timer_action_type,
                "params": timer_action_params,
            },
        }

        # Determine the request path (supports cross-node)
        path = "/api/timers"
        if node_id and node_id != "master":
            path = f"/api/node/{node_id}/timers"

        result = self._request_gateway(
            method="POST",
            path=path,
            json_data=body,
            error_prefix="Failed to create timer",
        )

        if result["success"]:
            gateway_data = result["data"]
            if not gateway_data.get("success"):
                error_info = gateway_data.get("error", {})
                error_msg = (
                    error_info.get("message", "unknown error")
                    if isinstance(error_info, dict)
                    else str(error_info)
                )
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Gateway returned error: {error_msg}",
                }
            data = gateway_data.get("data", {})
            return {
                "success": True,
                "stdout": json.dumps(data, ensure_ascii=False, indent=2),
                "stderr": "",
            }
        else:
            return {"success": False, "stdout": "", "stderr": result["error"]}

    def _list_timers(self) -> Dict[str, Any]:
        """Query and aggregate the scheduled tasks of all nodes.

        Returns:
            Dict[str, Any]: Execution result
        """
        nodes_result = self._list_nodes()
        if not nodes_result.get("success"):
            return nodes_result

        try:
            nodes_data = json.loads(nodes_result["stdout"])
        except (json.JSONDecodeError, TypeError):
            return {
                "success": False,
                "stdout": "",
                "stderr": "Failed to parse nodes data",
            }

        all_timers = []
        errors = []

        # Build the node ID list: master + all child nodes
        node_ids = ["master"]
        for sub_node in nodes_data.get("nodes", []):
            sub_node_id = sub_node.get("node_id", "")
            if sub_node_id:
                node_ids.append(sub_node_id)

        # Iterate over all nodes to query scheduled tasks
        for node_id in node_ids:
            path = "/api/timers"
            if node_id != "master":
                path = f"/api/node/{node_id}/timers"

            result = self._request_gateway(
                method="GET",
                path=path,
                error_prefix=f"Failed to list timers on node {node_id}",
            )

            if result["success"]:
                gateway_data = result["data"]
                if gateway_data.get("success"):
                    timers = gateway_data.get("data", [])
                    for timer in timers:
                        timer["node_id"] = node_id
                    all_timers.extend(timers)
                else:
                    error_info = gateway_data.get("error", {})
                    error_msg = (
                        error_info.get("message", "unknown error")
                        if isinstance(error_info, dict)
                        else str(error_info)
                    )
                    errors.append(f"node {node_id}: {error_msg}")
            else:
                errors.append(f"node {node_id}: {result['error']}")

        output = {
            "timers": all_timers,
            "total": len(all_timers),
        }
        if errors:
            output["errors"] = errors

        return {
            "success": True,
            "stdout": json.dumps(output, ensure_ascii=False, indent=2),
            "stderr": "",
        }

    def _get_timer(self, timer_id: Optional[str] = None) -> Dict[str, Any]:
        """Query a single scheduled task.

        Parameters:
            timer_id: Scheduled task ID

        Returns:
            Dict[str, Any]: Execution result
        """
        if not timer_id:
            return {"success": False, "stdout": "", "stderr": "timer_id is required"}

        result = self._request_gateway(
            method="GET",
            path=f"/api/timers/{timer_id}",
            error_prefix=f"Failed to get timer {timer_id}",
        )

        if result["success"]:
            gateway_data = result["data"]
            if not gateway_data.get("success"):
                error_info = gateway_data.get("error", {})
                error_msg = (
                    error_info.get("message", "unknown error")
                    if isinstance(error_info, dict)
                    else str(error_info)
                )
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Gateway returned error: {error_msg}",
                }
            data = gateway_data.get("data", {})
            return {
                "success": True,
                "stdout": json.dumps(data, ensure_ascii=False, indent=2),
                "stderr": "",
            }
        else:
            return {"success": False, "stdout": "", "stderr": result["error"]}

    def _delete_timer(self, timer_id: Optional[str] = None) -> Dict[str, Any]:
        """Delete a scheduled task.

        Parameters:
            timer_id: Scheduled task ID

        Returns:
            Dict[str, Any]: Execution result
        """
        if not timer_id:
            return {"success": False, "stdout": "", "stderr": "timer_id is required"}

        result = self._request_gateway(
            method="DELETE",
            path=f"/api/timers/{timer_id}",
            error_prefix=f"Failed to delete timer {timer_id}",
        )

        if result["success"]:
            gateway_data = result["data"]
            if not gateway_data.get("success"):
                error_info = gateway_data.get("error", {})
                error_msg = (
                    error_info.get("message", "unknown error")
                    if isinstance(error_info, dict)
                    else str(error_info)
                )
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Gateway returned error: {error_msg}",
                }
            return {
                "success": True,
                "stdout": json.dumps({"deleted": timer_id}, ensure_ascii=False),
                "stderr": "",
            }
        else:
            return {"success": False, "stdout": "", "stderr": result["error"]}

    def _create_group(
        self, group_name: Optional[str] = None, group_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a group.

        Parameters:
            group_name: Group name
            group_description: Group description

        Returns:
            Dict[str, Any]: Execution result
        """
        if not group_name:
            return {"success": False, "stdout": "", "stderr": "group_name is required"}

        result = self._request_gateway(
            method="POST",
            path="/api/groups",
            json_data={"name": group_name, "description": group_description},
            error_prefix="Failed to create group",
        )

        return self._handle_gateway_response(result)

    def _list_groups(self) -> Dict[str, Any]:
        """Query all groups.

        Returns:
            Dict[str, Any]: Execution result
        """
        result = self._request_gateway(
            method="GET",
            path="/api/groups",
            error_prefix="Failed to list groups",
        )

        return self._handle_gateway_response(result)

    def _get_group(self, group_id: Optional[str] = None) -> Dict[str, Any]:
        """Query group details.

        Parameters:
            group_id: Group ID

        Returns:
            Dict[str, Any]: Execution result
        """
        if not group_id:
            return {"success": False, "stdout": "", "stderr": "group_id is required"}

        result = self._request_gateway(
            method="GET",
            path=f"/api/groups/{group_id}",
            error_prefix=f"Failed to get group {group_id}",
        )

        return self._handle_gateway_response(result)

    def _join_group(self, group_id: Optional[str] = None) -> Dict[str, Any]:
        """Join a group.

               Parameters:

        group_id: Group ID

               Returns:
                   Dict[str, Any]: Execution result
        """
        if not group_id:
            return {"success": False, "stdout": "", "stderr": "group_id is required"}

        # Get the current agent_id
        agent_id = jglobals.agent_id
        if not agent_id:
            return {
                "success": False,
                "stdout": "",
                "stderr": "agent_id is not available",
            }

        result = self._request_gateway(
            method="POST",
            path=f"/api/groups/{group_id}/join",
            json_data={"agent_id": agent_id},
            error_prefix=f"Failed to join group {group_id}",
        )

        return self._handle_gateway_response(result)

    def _leave_group(self, group_id: Optional[str] = None) -> Dict[str, Any]:
        """Exit the group
        .

                Parameters:
                    group_id: Group ID

                Returns:
                    Dict[str, Any]: Execution result
        """
        if not group_id:
            return {"success": False, "stdout": "", "stderr": "group_id is required"}

        # Get the current agent_id
        agent_id = jglobals.agent_id
        if not agent_id:
            return {
                "success": False,
                "stdout": "",
                "stderr": "agent_id is not available",
            }

        result = self._request_gateway(
            method="POST",
            path=f"/api/groups/{group_id}/leave",
            json_data={"agent_id": agent_id},
            error_prefix=f"Failed to leave group {group_id}",
        )

        return self._handle_gateway_response(result)

    def _send_group_message(
        self, group_id: Optional[str] = None, message: str = ""
    ) -> Dict[str, Any]:
        """Send a group message.

        Parameters:
            group_id: Group ID
            message: Message content

        Returns:
            Dict[str, Any]: Execution result
        """
        if not group_id:
            return {"success": False, "stdout": "", "stderr": "group_id is required"}
        if not message:
            return {"success": False, "stdout": "", "stderr": "message is required"}

        # Get the current Agent ID as the sender
        sender_id = jglobals.agent_id
        if not sender_id:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Current agent_id is not set",
            }

        # Append a reply hint at the end of the message
        enhanced_message = f"{message}\n\n---\nTo reply to this group message use: gateway_manager action=send_group_message group_id={group_id} message=<your reply>"

        result = self._request_gateway(
            method="POST",
            path=f"/api/groups/{group_id}/message",
            json_data={"sender_id": sender_id, "content": enhanced_message},
            error_prefix=f"Failed to send message to group {group_id}",
        )

        if result["success"]:
            gateway_data = result["data"]
            if not gateway_data.get("success"):
                error_info = gateway_data.get("error", {})
                error_msg = (
                    error_info.get("message", "unknown error")
                    if isinstance(error_info, dict)
                    else str(error_info)
                )
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Gateway returned error: {error_msg}",
                }
            stdout_str = json.dumps(gateway_data.get("data", {}), ensure_ascii=False)
            stdout_str += "\n\nIf you want to wait for a response, output <Wait>."
            return {
                "success": True,
                "stdout": stdout_str,
                "stderr": "",
            }
        else:
            return {"success": False, "stdout": "", "stderr": result["error"]}

    def _regenerate_agent(
        self, agent_id: Optional[str] = None, node_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Losslessly regenerate the specified Agent.

        This is done via the newly added POST /api/agents/{agent_id}/regenerate interface on the gateway side
        the whole process of "save session → delete → rebuild". This process runs inside the gateway process,
        and will not be interrupted by deleting the Agent process, enabling the Agent to losslessly regenerate itself.

        Parameters:
            agent_id: The Agent ID to regenerate (required)
            node_id: Target node ID, defaults to empty (means this node)

        Returns:
            Dict[str, Any]: Regeneration result
        """
        if not agent_id:
            return {"success": False, "stdout": "", "stderr": "agent_id is required"}

        err = self._get_master_url("regenerate agent")
        if err:
            return err

        # Parse the node ID (verify the target node exists; in the child-node case the gateway forwards by node_id)
        try:
            resolved_node_id = self._resolve_node_id(agent_id, node_id)
        except ValueError as e:
            return {"success": False, "stdout": "", "stderr": str(e)}

        # Call the gateway-side regenerate interface. The request is always sent to master, with node_id as a query parameter
        # passed: when the target is on a child node, master routes and forwards to the corresponding child node to perform regeneration.
        regenerate_path = f"/api/agents/{agent_id}/regenerate"
        if resolved_node_id:
            regenerate_path += f"?node_id={resolved_node_id}"

        result = self._request_gateway(
            method="POST",
            path=regenerate_path,
            error_prefix=f"Failed to regenerate agent {agent_id}",
        )

        if not result["success"]:
            return {"success": False, "stdout": "", "stderr": result["error"]}

        gateway_data = result["data"]
        if not gateway_data.get("success"):
            error_info = gateway_data.get("error", {})
            error_msg = (
                error_info.get("message", "unknown error")
                if isinstance(error_info, dict)
                else str(error_info)
            )
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Gateway returned error: {error_msg}",
            }

        # Success: return the regeneration result (new Agent info + saved session file)
        regen_result = gateway_data.get("data") or {}
        new_agent = regen_result.get("new_agent") or {}
        session_file = regen_result.get("session_file")
        return {
            "success": True,
            "stdout": json.dumps(
                {
                    "message": f"Agent {agent_id} regenerated successfully",
                    "session_file": session_file,
                    "new_agent": new_agent,
                },
                ensure_ascii=False,
                indent=2,
            ),
            "stderr": "",
        }

    # ------------------------------------------------------------------
    # Chat room operations
    # ------------------------------------------------------------------

    def _get_agent_name(self) -> str:
        """Get the current Agent name, used as the message prefix."""
        try:
            from haijunbot.haijunbot_utils.globals import get_current_agent_name

            name = get_current_agent_name()
            if name:
                return name
        except Exception:
            pass
        # fallback: use agent_id
        return jglobals.agent_id or "Agent"

    def _chat_list_rooms(self) -> Dict[str, Any]:
        """Get the chat room list."""
        err = self._get_master_url("list chat rooms")
        if err:
            return err
        result = self._request_gateway(
            method="GET",
            path="/api/chat/rooms",
            error_prefix="Failed to list chat rooms",
        )
        return self._handle_gateway_response(result, success_data_key="rooms")

    def _chat_get_online_clients(self) -> Dict[str, Any]:
        """Get the list of online users."""
        err = self._get_master_url("get online clients")
        if err:
            return err
        result = self._request_gateway(
            method="GET",
            path="/api/chat/online-clients",
            error_prefix="Failed to get online clients",
        )
        return self._handle_gateway_response(result, success_data_key="clients")

    def _list_sessions(self) -> Dict[str, Any]:
        """Get the list of all active sessions (one per connection, including the corresponding user info)."""
        err = self._get_master_url("list sessions")
        if err:
            return err
        result = self._request_gateway(
            method="GET",
            path="/api/chat/sessions",
            error_prefix="Failed to list sessions",
        )
        return self._handle_gateway_response(result, success_data_key="sessions")

    def _eval_js(
        self,
        code: str = "",
        timeout: float = 30.0,
        target: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send JS to the front-end browser and retrieve the execution result.

        Parameters:
            code: The JavaScript code to execute
            timeout: The timeout in seconds to wait for the front-end execution result
            target: The target front end; None/current selects the current active front end, all broadcasts,
                a registered client_id is delivered precisely to that front-end connection, other values are treated as session_id
        """
        if not code or not str(code).strip():
            return {"success": False, "stdout": "", "stderr": "code is required"}
        err = self._get_master_url("eval js")
        if err:
            return err
        try:
            timeout_val = float(timeout)
        except (TypeError, ValueError):
            timeout_val = 30.0
        result = self._request_gateway(
            method="POST",
            path="/api/frontend/eval-js",
            json_data={
                "code": str(code),
                "timeout": timeout_val,
                "target": target or "current",
            },
            error_prefix="Failed to eval js",
            # The HTTP timeout must be greater than the front-end execution timeout, leaving margin for network and transfer
            timeout=timeout_val + 15.0,
        )
        if not result["success"]:
            return {"success": False, "stdout": "", "stderr": result["error"]}
        gateway_data = result["data"]
        if not gateway_data.get("success"):
            error_info = gateway_data.get("error", "unknown error")
            error_msg = (
                error_info.get("message", "unknown error")
                if isinstance(error_info, dict)
                else str(error_info)
            )
            return {"success": False, "stdout": "", "stderr": error_msg}
        value = gateway_data.get("result")
        stdout = (
            value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        )
        return {"success": True, "stdout": stdout, "stderr": ""}

    def _chat_get_room_members(self, room_id: Optional[str] = None) -> Dict[str, Any]:
        """Get the chat room member list.

        Parameters:
            room_id: Chat room ID
        """
        if not room_id:
            return {"success": False, "stdout": "", "stderr": "room_id is required"}
        err = self._get_master_url("get room members")
        if err:
            return err
        result = self._request_gateway(
            method="GET",
            path="/api/chat/room-members",
            params={"room_id": room_id},
            error_prefix=f"Failed to get members of room {room_id}",
        )
        return self._handle_gateway_response(result, success_data_key="members")

    def _chat_send_room_message(
        self, room_id: Optional[str] = None, message: str = ""
    ) -> Dict[str, Any]:
        """Send a chat room message (automatically adds the [Agent name] prefix).

        Parameters:
            room_id: Chat room ID
            message: Message content
        """
        if not room_id:
            return {"success": False, "stdout": "", "stderr": "room_id is required"}
        if not message:
            return {"success": False, "stdout": "", "stderr": "message is required"}
        err = self._get_master_url("send room message")
        if err:
            return err
        # Automatically add the [Agent name] prefix
        agent_name = self._get_agent_name()
        prefixed_message = f"[{agent_name}] {message}"
        result = self._request_gateway(
            method="POST",
            path="/api/chat/send-room-message",
            json_data={
                "room_id": room_id,
                "content": prefixed_message,
                "sender_name": agent_name,
                "agent_id": jglobals.agent_id,
            },
            error_prefix=f"Failed to send message to room {room_id}",
        )
        if result["success"]:
            return {
                "success": True,
                "stdout": json.dumps(
                    {"room_id": room_id, "message": prefixed_message},
                    ensure_ascii=False,
                ),
                "stderr": "",
            }
        return {"success": False, "stdout": "", "stderr": result["error"]}

    def _chat_send_private_message(
        self, receiver_id: Optional[str] = None, message: str = ""
    ) -> Dict[str, Any]:
        """Send a private message (automatically adds the [Agent name] prefix).

        Parameters:
            receiver_id: Receiver ID
            message: Message content
        """
        if not receiver_id:
            return {"success": False, "stdout": "", "stderr": "receiver_id is required"}
        if not message:
            return {"success": False, "stdout": "", "stderr": "message is required"}
        err = self._get_master_url("send private message")
        if err:
            return err
        # Automatically add the [Agent name] prefix
        agent_name = self._get_agent_name()
        prefixed_message = f"[{agent_name}] {message}"
        result = self._request_gateway(
            method="POST",
            path="/api/chat/send-private-message",
            json_data={
                "receiver_id": receiver_id,
                "content": prefixed_message,
                "sender_name": agent_name,
                "agent_id": jglobals.agent_id,
            },
            error_prefix=f"Failed to send private message to {receiver_id}",
        )
        if result["success"]:
            return {
                "success": True,
                "stdout": json.dumps(
                    {"receiver_id": receiver_id, "message": prefixed_message},
                    ensure_ascii=False,
                ),
                "stderr": "",
            }
        return {"success": False, "stdout": "", "stderr": result["error"]}
