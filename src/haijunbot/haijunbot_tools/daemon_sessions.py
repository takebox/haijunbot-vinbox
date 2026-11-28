# -*- coding: utf-8 -*-
"""Local daemon tool - lists the currently online haijunbot-daemon sessions.

Difference from browser_ext: browser_ext drives the user's browser extension, whereas this tool drives the
haijunbot-daemon process resident on the user's machine (capable of operating on the local filesystem, processes, system, etc.).

It relies on the user having installed and started haijunbot-daemon locally, and having pushed the gateway address and Token to it via the web page.

This tool is one of the daemon trio (sessions / capabilities / call), using a "dynamic capabilities + call"
model: capabilities are dynamically registered and reported by the daemon itself and passed through by the gateway. This tool is only responsible for listing sessions.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

import haijunbot.haijunbot_utils.globals as jglobals

logger = logging.getLogger(__name__)


class DaemonSessionsTool:
    """Local daemon tool - lists the currently online haijunbot-daemon sessions.

    Returns a list of session_ids; each session also includes system information of the machine where the backend service runs
    (system_info: hostname/os_name/os_version/arch/cpu_count/cpu_model/
    mem_total_kb/mem_available_kb/uptime_sec/user/home, etc.), which can be used to judge that
    machine's environment and callable capabilities.

    Typical flow: first use this tool to get the session_id, then use daemon_capabilities to see which capabilities
    the session supports and their parameters, and finally call daemon_call by capability name.
    """

    name = "daemon_sessions"

    @staticmethod
    def check() -> bool:
        """Check whether the tool is available; enabled only when a Gateway exists (determined by whether agent_id is set)."""
        return jglobals.agent_id is not None

    description = """List the currently online daemon (haijunbot-daemon) sessions.
Returns a list of session_ids; each session also includes system information of the machine where the backend service runs
(system_info: hostname/os_name/os_version/arch/cpu_count/cpu_model/
mem_total_kb/mem_available_kb/uptime_sec/user/home, etc.), which can be used to judge that machine's environment and callable capabilities.
**You should call this tool first to obtain the session_id**, then use daemon_capabilities to view capabilities and daemon_call to invoke.
If the user has not installed or started the daemon, this tool returns an empty list as a hint."""

    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def _get_master_url(self, action_name: str = "") -> Optional[Dict[str, Any]]:
        """Get master_url; return an error dict if it is not set."""
        if not jglobals.master_url:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"master_url is not set, cannot {action_name}. "
                "Please ensure the agent is started with --master-url option.",
            }
        return None

    def _build_auth_headers(self) -> Dict[str, str]:
        """Build request headers with authentication information."""
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
        timeout: float = 20.0,
    ) -> Dict[str, Any]:
        """Send an HTTP request to the Gateway."""
        url = f"{jglobals.master_url}{path}"
        headers = self._build_auth_headers()
        try:
            with httpx.Client(timeout=timeout) as client:
                if method.upper() == "POST":
                    response = client.post(url, json=json_data, headers=headers)
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
                "error": f"Cannot connect to gateway at {jglobals.master_url}. "
                "Please ensure the gateway is running.",
            }
        except Exception as e:
            return {
                "success": False,
                "status_code": None,
                "data": None,
                "error": f"{error_prefix}: {str(e)}",
            }

    @staticmethod
    def _format_result(data: Any) -> str:
        """Format the data returned by the gateway into readable text."""
        if data is None:
            return "list_sessions executed successfully"
        if isinstance(data, str):
            return data
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            return str(data)

    def execute(self, **kwargs) -> Dict[str, Any]:
        """List the currently online daemon sessions.

        Returns:
            Dict[str, Any]: {"success": bool, "stdout": str, "stderr": str}
        """
        err = self._get_master_url("list_sessions")
        if err is not None:
            return err

        result = self._request_gateway(
            "GET",
            "/api/daemon/sessions",
            error_prefix="Failed to list daemon sessions",
        )
        if not result.get("success"):
            return {
                "success": False,
                "stdout": "",
                "stderr": result.get("error") or "unknown error",
            }
        data = result.get("data") or {}
        sessions = data.get("sessions") or []
        if not sessions:
            return {
                "success": True,
                "stdout": "There are currently no online daemon sessions. "
                "Please confirm that the user has installed and started haijunbot-daemon on the local machine, "
                "and has completed authentication through the web page.",
                "stderr": "",
            }
        return {
            "success": True,
            "stdout": self._format_result(sessions),
            "stderr": "",
        }
