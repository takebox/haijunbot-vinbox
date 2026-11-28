# -*- coding: utf-8 -*-
from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
import threading
import time
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import cast
from urllib.parse import parse_qs
from urllib.parse import urlencode
from urllib.parse import urljoin

import requests  # Import the third-party requests library

from haijunbot.haijunbot_mcp import McpClient
from haijunbot.haijunbot_utils.output import PrettyOutput


class SSEMcpClient(McpClient):
    """Remote MCP client implementation

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

        # Set up the HTTP client
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

        # Add the auth token (if provided)
        auth_token = config.get("auth_token")
        if auth_token:
            self.session.headers["Authorization"] = f"Bearer {auth_token}"

        # Add extra HTTP headers
        extra_headers = config.get("headers", {})
        self.session.headers.update(extra_headers)

        # SSE-related attributes
        self.sse_response: Optional[requests.Response] = None
        self.sse_thread: Optional[threading.Thread] = None
        self.messages_endpoint: Optional[str] = None
        self.session_id: Optional[str] = None
        self.pending_requests: Dict[
            str, threading.Event
        ] = {}  # Requests waiting for a response {id: Event}
        self.request_results: Dict[
            str, Dict[str, Any]
        ] = {}  # Request results {id: result}
        self.notification_handlers: Dict[str, List[Callable]] = {}
        self.event_lock = threading.Lock()
        self.request_id_counter = 0

        # Initialize the connection
        self._initialize()

    def _initialize(self) -> None:
        """Initialize the MCP connection"""
        try:
            # Start the SSE connection
            self._start_sse_connection()

            # Wait for the messages endpoint and session ID
            start_time = time.time()
            while (
                not self.messages_endpoint or not self.session_id
            ) and time.time() - start_time < 5:
                time.sleep(0.1)

            if not self.messages_endpoint:
                self.messages_endpoint = "/messages"  # Default endpoint
                PrettyOutput.auto_print(
                    f"⚠️ Messages endpoint not obtained; using default: {self.messages_endpoint}"
                )

            if not self.session_id:
                PrettyOutput.auto_print("⚠️ Session ID not obtained")

            # Send the initialize request
            response = self._send_request(
                "initialize",
                {
                    "processId": None,  # Remote clients do not need a process ID
                    "clientInfo": {"name": "haijunbot", "version": "1.0.0"},
                    "capabilities": {},
                    "protocolVersion": "2025-03-26",
                },
            )

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

    def _start_sse_connection(self) -> None:
        """Establish the SSE connection and start the processing thread"""
        try:
            # Set the SSE request headers
            sse_headers = dict(self.session.headers)
            sse_headers.update(
                {
                    "Accept": "text/event-stream",
                    "Cache-Control": "no-cache",
                }
            )

            # Establish the SSE connection
            sse_url = urljoin(self.base_url, "sse")
            self.sse_response = self.session.get(
                sse_url, stream=True, headers=sse_headers, timeout=30
            )
            if self.sse_response:
                self.sse_response.raise_for_status()

            # Start the event processing thread
            self.sse_thread = threading.Thread(
                target=self._process_sse_events, daemon=True
            )
            if self.sse_thread:
                self.sse_thread.start()

        except Exception as e:
            PrettyOutput.auto_print(f"❌ SSE connection failed: {str(e)}")
            raise

    def _process_sse_events(self) -> None:
        """Process the SSE event stream"""
        if not self.sse_response:
            return

        buffer = ""
        for line in self.sse_response.iter_lines(decode_unicode=True):
            if line:
                if line.startswith("data:"):
                    data = line[5:].strip()
                    # Check whether it contains messages endpoint info
                    if data.startswith("/"):
                        # This is messages endpoint info, e.g. "/messages/?session_id=xyz"
                        try:
                            # Extract the messages endpoint path and session ID
                            url_parts = data.split("?")
                            self.messages_endpoint = url_parts[0]

                            # If there are query params, try to extract session_id
                            if len(url_parts) > 1:
                                query_string = url_parts[1]
                                query_params = parse_qs(query_string)
                                if "session_id" in query_params:
                                    self.session_id = query_params["session_id"][0]
                        except Exception as e:
                            PrettyOutput.auto_print(f"⚠️ Failed to parse messages endpoint or session ID: {e}")
                    else:
                        buffer += data
                elif line.startswith(":"):  # Ignore comment lines
                    continue
                elif line.startswith("event:"):  # Event type
                    continue  # We do not use the event type
                elif line.startswith("id:"):  # Event ID
                    continue  # We do not use the event ID
                elif line.startswith("retry:"):  # Reconnect delay
                    continue  # We manage reconnection ourselves
            else:  # A blank line means the event has ended
                if buffer:
                    try:
                        self._handle_sse_event(buffer)
                    except Exception as e:
                        PrettyOutput.auto_print(f"❌ Error processing SSE event: {e}")
                    buffer = ""

        PrettyOutput.auto_print("⚠️ SSE connection closed")

    def _handle_sse_event(self, data: str) -> None:
        """Handle a single SSE event payload"""
        try:
            event_data = json.loads(data)

            # Check whether it is a request response or a notification
            if "id" in event_data:
                # This is a response to a request
                req_id = event_data["id"]
                with self.event_lock:
                    self.request_results[req_id] = event_data
                    if req_id in self.pending_requests:
                        # Notify the waiting thread that the response has arrived
                        self.pending_requests[req_id].set()
            elif "method" in event_data:
                # This is a notification
                method = event_data.get("method", "")
                params = event_data.get("params", {})

                # Call the registered handlers
                if method in self.notification_handlers:
                    error_lines: List[str] = []
                    for handler in self.notification_handlers[method]:
                        try:
                            handler(params)
                        except Exception as e:
                            error_lines.append(f"Error handling notification ({method}): {e}")
                    if error_lines:
                        joined_errors = "\n".join(error_lines)
                        PrettyOutput.auto_print(f"❌ {joined_errors}")
        except Exception:
            PrettyOutput.auto_print(f"⚠️ Failed to parse SSE event: {data}")

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

            # Try different ways of sending the request
            if self.session_id:
                # Method 1: use the session_id in the query params
                query_params = {"session_id": self.session_id}
                messages_url = urljoin(self.base_url, self.messages_endpoint)

                # Try using the original URL directly (without appending query params)
                try:
                    post_response = self.session.post(messages_url, json=request)
                    post_response.raise_for_status()
                except requests.HTTPError:
                    # If that fails, try adding the session ID to the query params
                    messages_url_with_session = (
                        f"{messages_url}?{urlencode(query_params)}"
                    )
                    post_response = self.session.post(
                        messages_url_with_session, json=request
                    )
                    post_response.raise_for_status()
            else:
                # Method 2: do not use session_id
                if not self.messages_endpoint:
                    self.messages_endpoint = "/messages"

                messages_url = urljoin(self.base_url, self.messages_endpoint)

                # Try using the messages endpoint directly without any query params
                try:
                    # Attempt 1: standard JSON-RPC format
                    post_response = self.session.post(messages_url, json=request)
                    post_response.raise_for_status()
                except requests.HTTPError:
                    # Attempt 2: JSON string as the request params
                    post_response = self.session.post(
                        messages_url, params={"request": json.dumps(request)}
                    )
                    post_response.raise_for_status()

            # Wait for the SSE channel to return a response (up to 30 seconds)
            if not event.wait(timeout=30):
                raise TimeoutError(f"Timed out waiting for response: {method}")

            # Get the response result
            with self.event_lock:
                result = self.request_results.pop(req_id, None)
                self.pending_requests.pop(req_id, None)

            if result is None:
                raise RuntimeError(f"No response received: {method}")

            return result

        except Exception as e:
            # Clean up the request state
            with self.event_lock:
                self.pending_requests.pop(req_id, None)
                self.request_results.pop(req_id, None)

            PrettyOutput.auto_print(f"❌ Failed to send request: {str(e)}")
            raise

    def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        """Send a notification to the MCP server (no response expected)

        Args:
            method: The notification method
            params: The notification params
        """
        try:
            # Build the notification
            notification = {"jsonrpc": "2.0", "method": method, "params": params}

            # Try the same sending approaches as _send_request
            if self.session_id:
                # Method 1: use the session_id in the query params
                query_params = {"session_id": self.session_id}
                messages_url = urljoin(
                    self.base_url, self.messages_endpoint or "/messages"
                )

                # Try using the original URL directly (without appending query params)
                try:
                    post_response = self.session.post(messages_url, json=notification)
                    post_response.raise_for_status()
                except requests.HTTPError:
                    # If that fails, try adding the session ID to the query params
                    messages_url_with_session = (
                        f"{messages_url}?{urlencode(query_params)}"
                    )
                    post_response = self.session.post(
                        messages_url_with_session, json=notification
                    )
                    post_response.raise_for_status()
            else:
                # Method 2: do not use session_id
                if not self.messages_endpoint:
                    self.messages_endpoint = "/messages"

                messages_url = urljoin(self.base_url, self.messages_endpoint)

                # Try using the messages endpoint directly without any query params
                try:
                    # Attempt 1: standard JSON-RPC format
                    post_response = self.session.post(messages_url, json=notification)
                    post_response.raise_for_status()
                except requests.HTTPError:
                    # Attempt 2: JSON string as the request params
                    post_response = self.session.post(
                        messages_url, params={"request": json.dumps(notification)}
                    )
                    post_response.raise_for_status()

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

        # Close the SSE response
        if self.sse_response:
            try:
                self.sse_response.close()
            except Exception as e:
                save_exception(
                    e, module="haijunbot_mcp.sse_mcp_client", function="__del__"
                )
                pass

        # Close the HTTP session
        if self.session:
            self.session.close()
