# -*- coding: utf-8 -*-
"""Browser extension tool - lists the currently online browser extension sessions.

Difference from haijunbot-browser(hb): hb starts an independent browser with Playwright on the server side,
whereas this tool drives the real, already-logged-in tabs in the **user's own browser**.

It relies on the user having installed the HaijunBot Browser Bridge extension in their browser and connected it to the gateway.

This tool is one of the browser_ext trio (sessions / capabilities / call),
using a "dynamic capabilities + call" model: the extension side maintains a capability list (command_router.js's
routes + CAPABILITIES) and reports it dynamically, and the gateway passes it through. This tool is only responsible for listing sessions.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

import haijunbot.haijunbot_utils.globals as jglobals

logger = logging.getLogger(__name__)


class BrowserExtSessionsTool:
    """Browser extension tool - lists the currently online browser extension sessions.

    Returns a list of session_ids; each session also includes the capability list (capabilities)
    and browser information (browser_info) reported by the extension, etc.

    Typical flow: first use this tool to get the session_id, then use browser_ext_capabilities to see which capabilities
    the session supports and their parameters, and finally call browser_ext_call by capability name.
    """

    name = "browser_ext_sessions"

    @staticmethod
    def check() -> bool:
        """Check whether the tool is available; enabled only when a Gateway exists (determined by whether agent_id is set)."""
        return jglobals.agent_id is not None

    description = """List the currently online browser extension sessions (through the user's installed browser extension).
Returns a list of session_ids; each session also includes the capability list (capabilities) and browser information (browser_info) reported by the extension, etc.
**You should call this tool first to obtain the session_id**, then use browser_ext_capabilities to view capabilities and browser_ext_call to invoke.
If the user has not installed the extension or the extension is not connected, this tool returns an empty list as a hint."""

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
        """List the currently online browser extension sessions.

        Returns:
            Dict[str, Any]: {"success": bool, "stdout": str, "stderr": str}
        """
        err = self._get_master_url("list_sessions")
        if err is not None:
            return err

        result = self._request_gateway(
            "GET",
            "/api/browser-ext/sessions",
            error_prefix="Failed to list browser sessions",
        )
        if not result.get("success"):
            return {
                "success": False,
                "stdout": "",
                "stderr": result.get("error") or "unknown error",
            }
        data = result.get("data") or {}
        sessions: list = data.get("sessions") or []
        if not sessions:
            return {
                "success": True,
                "stdout": "There are currently no online browser extension sessions. "
                "Please confirm that the user has installed and connected the HaijunBot Browser Bridge extension in their browser.",
                "stderr": "",
            }
        return {
            "success": True,
            "stdout": self._format_result(sessions),
            "stderr": "",
        }
