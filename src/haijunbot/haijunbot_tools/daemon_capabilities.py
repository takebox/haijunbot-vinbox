# -*- coding: utf-8 -*-
"""Local daemon tool - lists the capability list of a specified haijunbot-daemon session.

Difference from browser_ext: browser_ext drives the user's browser extension, whereas this tool drives the
haijunbot-daemon process resident on the user's machine (capable of operating on the local filesystem, processes, system, etc.).

It relies on the user having installed and started haijunbot-daemon locally, and having pushed the gateway address and Token to it via the web page.

This tool is one of the daemon trio (sessions / capabilities / call), using a "dynamic capabilities + call"
model: capabilities are dynamically registered and reported by the daemon itself and passed through by the gateway. This tool is only responsible for listing the capabilities of a specified session.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

import haijunbot.haijunbot_utils.globals as jglobals

logger = logging.getLogger(__name__)


class DaemonCapabilitiesTool:
    """Local daemon tool - lists the capability list of a specified haijunbot-daemon session.

    Returns the capabilities registered by that session (including name/description/parameters/platform).

    Typical flow: first use daemon_sessions to get the session_id, then use this tool to see which capabilities
    the session supports and their parameters, and finally call daemon_call by capability name.
    """

    name = "daemon_capabilities"

    @staticmethod
    def check() -> bool:
        """Check whether the tool is available; enabled only when a Gateway exists (determined by whether agent_id is set)."""
        return jglobals.agent_id is not None

    description = """List the capabilities available on a specified daemon (haijunbot-daemon) session (including name/description/parameters/platform).
Requires session_id (obtain it first with daemon_sessions).
The capability list is determined by the daemon's dynamic registration and may differ across machines/versions; before calling daemon_call, be sure to use this tool first to confirm the capability names and parameters, and do not call based on guesses."""

    parameters = {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Daemon session ID (required). Should be obtained by calling daemon_sessions first",
            },
        },
        "required": ["session_id"],
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
            return "list_capabilities executed successfully"
        if isinstance(data, str):
            return data
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            return str(data)

    @staticmethod
    def _format_error(error: Any) -> str:
        """Format the gateway-returned error field (which may be a dict or str) into text."""
        if error is None:
            return "unknown error"
        if isinstance(error, str):
            return error
        try:
            return json.dumps(error, ensure_ascii=False)
        except Exception:
            return str(error)

    def execute(self, session_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """List the capability list of a specified daemon session.

        Args:
            session_id: Daemon session ID (required)

        Returns:
            Dict[str, Any]: {"success": bool, "stdout": str, "stderr": str}
        """
        err = self._get_master_url("list_capabilities")
        if err is not None:
            return err

        session_id = str(session_id or "").strip()
        if not session_id:
            return {
                "success": False,
                "stdout": "",
                "stderr": "session_id is required. Please call daemon_sessions first to obtain it.",
            }

        try:
            timeout = float(kwargs.get("timeout", 30.0))
        except (TypeError, ValueError):
            timeout = 30.0

        result = self._request_gateway(
            "POST",
            "/api/daemon/capability/list",
            json_data={"session_id": session_id, "timeout": timeout},
            error_prefix="Failed to list daemon capabilities",
            timeout=timeout + 5.0,
        )
        if not result.get("success"):
            return {
                "success": False,
                "stdout": "",
                "stderr": result.get("error") or "unknown error",
            }
        data = result.get("data") or {}
        if not data.get("success"):
            return {
                "success": False,
                "stdout": "",
                "stderr": self._format_error(data.get("error")),
            }
        # Gateway envelope: {"success": true, "result": {"success":..., "capabilities":[...]}}
        payload = data.get("result") or {}
        capabilities = payload.get("capabilities") or []
        if not capabilities:
            return {
                "success": True,
                "stdout": "This daemon has not registered any capabilities currently.",
                "stderr": "",
            }
        return {
            "success": True,
            "stdout": self._format_result(capabilities),
            "stderr": "",
        }
