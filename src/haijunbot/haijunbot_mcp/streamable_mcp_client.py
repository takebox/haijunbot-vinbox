# -*- coding: utf-8 -*-
from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
import threading
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import cast
from urllib.parse import urljoin

import requests  # Import the third-party requests library

from haijunbot.haijunbot_mcp import McpClient
from haijunbot.haijunbot_utils.output import PrettyOutput


class StreamableMcpClient(McpClient):
    """Streamable HTTP MCP client implementation

    Args:
        config: The config dict, containing the following fields:
            - base_url: str - The base URL of the MCP server
            - auth_token: str - The auth token (optional)
            - headers: Dict[str, str] - Extra HTTP headers (optional)
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_url = config.get("base_url", "")
        if not self.base_url:
            raise ValueError("No base_url specified in config")
        # Normalize base_url to ensure trailing slash for urljoin correctness
        self.base_url = self.base_url.rstrip("/") + "/"
        # Get endpoint path from config, default to "mcp"
        # If base_url already contains the endpoint, set endpoint_path to empty string
        self.endpoint_path = config.get("endpoint_path", "mcp")

        # Set up the HTTP client
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
        )

        # Add the auth token (if provided)
        auth_token = config.get("auth_token")
        if auth_token:
            self.session.headers["Authorization"] = f"Bearer {auth_token}"

        # Add extra HTTP headers
        extra_headers = config.get("headers", {})
        self.session.headers.update(extra_headers)

        # Request timeouts (connect, read) in seconds; can be overridden via config["timeout"]
        # Convert list to tuple if needed (JSON arrays become lists in Python, but requests needs tuple)
        timeout_config = config.get("timeout", [10, 300])
        if isinstance(timeout_config, list):
            self.timeout = tuple(timeout_config)
        else:
            self.timeout = timeout_config

        # Request-related attributes
        self.pending_requests: Dict[
            str, threading.Event
        ] = {}  # Requests waiting for a response {id: Event}
        self.request_results: Dict[
            str, Dict[str, Any]
        ] = {}  # Request results {id: result}
        self.notification_handlers: Dict[str, List[Callable]] = {}
        self.event_lock = threading.Lock()
        self.request_id_counter = 0
        self.mcp_session_id: str = ""  # Store the MCP session ID

        # Initialize the connection
        self._initialize()

    def _initialize(self) -> None:
        """Initialize the MCP connection"""
        try:
            # Send the initialize request
            # For HTTP MCP servers, do not send the processId field
            init_params = {
                "clientInfo": {"name": "haijunbot", "version": "1.0.0"},
                "capabilities": {},
                "protocolVersion": "2025-03-26",
            }
            response = self._send_request("initialize", init_params)

            # Validate the server response
            if "result" not in response:
                raise RuntimeError(
                    f"Initialization failed: {response.get('error', 'Unknown error')}"
                )

            # Send the initialized notification
            self._send_notification("notifications/initialized", {})

        except Exception as e:
            PrettyOutput.auto_print(f"❌ MCP initialization failed: {str(e)}")
            raise

    def register_notification_handler(self, method: str, handler: Callable) -> None:
        """Register a notification handler

        Args:
            method: The notification method name
            handler: The callback that handles the notification, receiving the params argument
        """
        with self.event_lock:
            if method not in self.notification_handlers:
                self.notification_handlers[method] = []
            self.notification_handlers[method].append(handler)

    def unregister_notification_handler(self, method: str, handler: Callable) -> None:
        """Unregister a notification handler

        Args:
            method: The notification method name
            handler: The handler function to unregister
        """
        with self.event_lock:
            if method in self.notification_handlers:
                if handler in self.notification_handlers[method]:
                    self.notification_handlers[method].remove(handler)
                if not self.notification_handlers[method]:
                    del self.notification_handlers[method]

    def _get_next_request_id(self) -> str:
        """Get the next request ID"""
        with self.event_lock:
            self.request_id_counter += 1
            return str(self.request_id_counter)

    def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the MCP server

        Args:
            method: The request method
            params: The request params

        Returns:
            Dict[str, Any]: The response result
        """
        # Generate a unique request ID
        req_id = self._get_next_request_id()

        # Create an event flag for waiting on the response
        event = threading.Event()

        with self.event_lock:
            self.pending_requests[req_id] = event

        try:
            # Build the request
            request = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": req_id,
            }

            # Send the request to the Streamable HTTP endpoint
            if self.endpoint_path:
                mcp_url = urljoin(self.base_url, self.endpoint_path)
            else:
                # If endpoint_path is empty, use base_url directly (keep trailing slash if present)
                mcp_url = self.base_url.rstrip("/") + "/"

            # Add the session header
            if self.mcp_session_id:
                self.session.headers["Mcp-Session-Id"] = self.mcp_session_id

            response = self.session.post(mcp_url, json=request, timeout=self.timeout)

            # Save the MCP session ID (if present)
            if "Mcp-Session-Id" in response.headers:
                self.mcp_session_id = response.headers["Mcp-Session-Id"]
                # If later requests need the session ID, add it to the request headers
                if self.mcp_session_id and "Mcp-Session-Id" not in self.session.headers:
                    self.session.headers["Mcp-Session-Id"] = self.mcp_session_id

            # If the request failed, print detailed error info
            if response.status_code >= 400:
                try:
                    # For error responses, try to read the response body
                    error_body = response.text
                    if error_body:
                        PrettyOutput.auto_print(
                            f"❌ HTTP error {response.status_code}, response content: {error_body[:1000]}"
                        )
                    else:
                        PrettyOutput.auto_print(
                            f"❌ HTTP error {response.status_code}, URL: {mcp_url}"
                        )
                except Exception as e:
                    PrettyOutput.auto_print(
                        f"❌ HTTP error {response.status_code}, could not read response body: {e}"
                    )
                response.raise_for_status()

            # Handle the response
            result = None
            warning_lines = []
            error_lines = []

            # Handle the response
            result = None
            warning_lines = []
            error_lines = []

            # Check whether the response is in SSE format
            content_type = response.headers.get("content-type", "")

            if "text/event-stream" in content_type.lower():
                # Handle the SSE-format response
                # Force UTF-8 decoding to avoid requests guessing the wrong encoding (default ISO-8859-1)
                response_text = response.content.decode("utf-8")
                for line in response_text.splitlines():
                    line = line.strip()
                    if line.startswith("data:"):
                        try:
                            data_str = line[5:].strip()
                            if data_str:
                                data = json.loads(data_str)
                                if "id" in data and data["id"] == req_id:
                                    result = data
                                    break
                        except json.JSONDecodeError:
                            continue
            else:
                # Parse it directly as JSON
                try:
                    result = response.json()
                except json.JSONDecodeError as e:
                    error_lines.append(f"JSON parse failed: {e}")
                    warning_lines.append(f"Response content: {response.text[:200]}...")

            if result is None:
                # Try to extract it from the response text
                response_text = response.text
                if response_text.strip():
                    # Look for the JSON object containing our request ID
                    import re

                    pattern = r'"id":\s*"' + re.escape(req_id) + r'"'
                    if re.search(pattern, response_text):
                        # Try to parse the entire response
                        try:
                            lines = response_text.split("\n")
                            for line in lines:
                                line = line.strip()
                                if line.startswith("data:"):
                                    try:
                                        data = json.loads(line[5:])
                                        if data.get("id") == req_id:
                                            result = data
                                            break
                                    except json.JSONDecodeError:
                                        continue
                        except Exception as e:
                            save_exception(
                                e,
                                module="haijunbot_mcp.streamable_mcp_client",
                                function="_send_request",
                            )
                            pass
                # Handle non-streaming responses (used for the initialize request)
                # Even for non-streaming requests, the server may return an SSE-format response
                try:
                    # Try to parse it in SSE format
                    response_text = response.text
                    for line in response_text.splitlines():
                        if line.startswith("data:"):
                            # Extract the content of the data field
                            line_data = line.split(":", 1)[1].strip()
                            try:
                                data = json.loads(line_data)
                                if "id" in data and data["id"] == req_id:
                                    result = data
                                    break
                            except json.JSONDecodeError:
                                continue
                    # If SSE parsing fails, try to parse the JSON directly
                    if result is None:
                        result = response.json()
                        if "id" in result and result["id"] != req_id:
                            # ID mismatch, this may not be our response
                            result = None
                except (json.JSONDecodeError, AttributeError) as e:
                    error_lines.append(f"Unable to parse response: {e}")
                    error_lines.append(
                        f"Response content: {response_text[:500] if 'response_text' in locals() else response.text[:500]}"
                    )

            if warning_lines:
                joined_warnings = "\n".join(warning_lines)
                PrettyOutput.auto_print(f"⚠️ {joined_warnings}")
            if error_lines:
                joined_errors = "\n".join(error_lines)
                PrettyOutput.auto_print(f"❌ {joined_errors}")
            # Ensure response is closed after streaming
            response.close()
            if result is None:
                raise RuntimeError(f"No response received: {method}")

            return cast(Dict[str, Any], result)

        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to send request: {str(e)}")
            raise
        finally:
            # Clean up the request state
            with self.event_lock:
                self.pending_requests.pop(req_id, None)
                self.request_results.pop(req_id, None)

    def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        """Send a notification to the MCP server (no response expected)

        Args:
            method: The notification method
            params: The notification params
        """
        try:
            # Build the notification
            notification = {"jsonrpc": "2.0", "method": method, "params": params}

            # Send the notification to the Streamable HTTP endpoint
            if self.endpoint_path:
                mcp_url = urljoin(self.base_url, self.endpoint_path)
            else:
                # If endpoint_path is empty, use base_url directly (keep trailing slash if present)
                mcp_url = self.base_url.rstrip("/") + "/"
            response = self.session.post(
                mcp_url, json=notification, timeout=self.timeout
            )
            response.raise_for_status()
            response.close()

        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to send notification: {str(e)}")
            raise

    def get_tool_list(self) -> List[Dict[str, Any]]:
        """Get the tool list

        Returns:
            List[Dict[str, Any]]: The tool list; each tool contains the following fields:
                - name: str - The tool name
                - description: str - The tool description
                - parameters: Dict - The tool parameters
        """
        try:
            response = self._send_request("tools/list", {})
            if "result" in response and "tools" in response["result"]:
                # Note: the response structure is response['result']['tools']
                tools = response["result"]["tools"]
                # Convert the MCP protocol fields to the internal format
                formatted_tools = []
                for tool in tools:
                    # Extract the parameter definitions from inputSchema
                    input_schema = tool.get("inputSchema", {})
                    parameters = {}
                    if "properties" in input_schema:
                        parameters = input_schema["properties"]

                    formatted_tools.append(
                        {
                            "name": tool.get("name", ""),
                            "description": tool.get("description", ""),
                            "parameters": parameters,
                        }
                    )
                return formatted_tools
            else:
                error_msg = "Failed to get the tool list"
                if "error" in response:
                    error_msg += f": {response['error']}"
                elif "result" in response:
                    error_msg += f": incorrect response format - {response['result']}"
                else:
                    error_msg += ": unknown error"

                PrettyOutput.auto_print(f"❌ {error_msg}")
                return []
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to get the tool list: {str(e)}")
            return []

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool

        Args:
            tool_name: The tool name
            arguments: The argument dict, containing the parameters required to execute the tool

        Returns:
            Dict[str, Any]: The execution result, containing the following fields:
                - success: bool - Whether the execution succeeded
                - stdout: str - The standard output
                - stderr: str - The standard error
        """
        try:
            response = self._send_request(
                "tools/call", {"name": tool_name, "arguments": arguments}
            )
            if "result" in response:
                result = response["result"]
                # Extract the output info from content
                stdout = ""
                stderr = ""
                for content in result.get("content", []):
                    if content.get("type") == "text":
                        stdout += content.get("text", "")
                    elif content.get("type") == "error":
                        stderr += content.get("text", "")

                return {"success": True, "stdout": stdout, "stderr": stderr}
            else:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": response.get("error", "Unknown error"),
                }
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to execute tool: {str(e)}")
            return {"success": False, "stdout": "", "stderr": str(e)}

    def get_resource_list(self) -> List[Dict[str, Any]]:
        """Get the resource list

        Returns:
            List[Dict[str, Any]]: The resource list; each resource contains the following fields:
                - uri: str - The unique identifier of the resource
                - name: str - The name of the resource
                - description: str - The description of the resource (optional)
                - mimeType: str - The MIME type of the resource (optional)
        """
        try:
            response = self._send_request("resources/list", {})
            if "result" in response and "resources" in response["result"]:
                return cast(List[Dict[str, Any]], response["result"]["resources"])
            else:
                error_msg = "Failed to get the resource list"
                if "error" in response:
                    error_msg += f": {response['error']}"
                else:
                    error_msg += ": unknown error"
                PrettyOutput.auto_print(f"❌ {error_msg}")
                return []
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to get the resource list: {str(e)}")
            return []

    def get_resource(self, uri: str) -> Dict[str, Any]:
        """Get the content of the specified resource

        Args:
            uri: str - The URI identifier of the resource

        Returns:
            Dict[str, Any]: The execution result, containing the following fields:
                - success: bool - Whether the execution succeeded
                - stdout: str - The resource content (text or base64-encoded binary content)
                - stderr: str - The error message
        """
        try:
            response = self._send_request("resources/read", {"uri": uri})
            if "result" in response and "contents" in response["result"]:
                contents = response["result"]["contents"]
                if contents:
                    content = contents[0]  # Get the first resource content
                    # Return the content based on the resource type
                    if "text" in content:
                        return {
                            "success": True,
                            "stdout": content["text"],
                            "stderr": "",
                        }
                    elif "blob" in content:
                        return {
                            "success": True,
                            "stdout": content["blob"],
                            "stderr": "",
                        }
                return {"success": False, "stdout": "", "stderr": "Resource content is empty"}
            else:
                error_msg = "Failed to get the resource content"
                if "error" in response:
                    error_msg += f": {response['error']}"
                else:
                    error_msg += ": unknown error"
                PrettyOutput.auto_print(f"❌ {error_msg}")
                return {"success": False, "stdout": "", "stderr": error_msg}
        except Exception as e:
            error_msg = f"Failed to get the resource content: {str(e)}"
            PrettyOutput.auto_print(f"❌ {error_msg}")
            return {"success": False, "stdout": "", "stderr": error_msg}

    def __del__(self):
        """Clean up resources"""
        # Clean up the request state
        with self.event_lock:
            for event in self.pending_requests.values():
                event.set()  # Release all waiting requests
            self.pending_requests.clear()
            self.request_results.clear()

        # Close the HTTP session
        if self.session:
            self.session.close()
