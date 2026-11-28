# -*- coding: utf-8 -*-
import json
import os
import subprocess
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import cast

from haijunbot.haijunbot_mcp import McpClient
from haijunbot.haijunbot_utils.output import PrettyOutput


class StdioMcpClient(McpClient):
    """Local MCP client implementation

    Args:
        config: The config dict (command, args, env)
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.protocol_version = "2025-03-26"  # MCP protocol version
        self._start_process()
        self._initialize()

    def _start_process(self) -> None:
        """Start the MCP process"""
        try:
            # Build the command and args
            command = self.config.get("command", "")
            if not command:
                raise ValueError("No command specified in config")

            # Get the args list
            args = self.config.get("args", [])
            if not isinstance(args, list):
                args = [str(args)]

            # Get the environment variables
            env = os.environ.copy()
            env.update(self.config.get("env", {}))

            # Start the process
            self.process = subprocess.Popen(
                [command] + args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
            )

        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to start MCP process: {str(e)}")
            raise

    def _initialize(self) -> None:
        """Initialize the MCP connection"""
        try:
            # Send the initialize request
            response = self._send_request(
                "initialize",
                {
                    "processId": os.getpid(),
                    "clientInfo": {"name": "haijunbot", "version": "1.0.0"},
                    "capabilities": {},
                    "protocolVersion": self.protocol_version,
                },
            )

            # Validate the server response
            if "result" not in response:
                raise RuntimeError(
                    f"Initialization failed: {response.get('error', 'Unknown error')}"
                )

            response["result"]

            # Send the initialized notification - using the correct method name format
            self._send_notification("notifications/initialized", {})

        except Exception as e:
            PrettyOutput.auto_print(f"❌ MCP initialization failed: {str(e)}")
            raise

    def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the MCP process

        Args:
            method: The request method
            params: The request params

        Returns:
            Dict[str, Any]: The response result
        """
        if not self.process:
            raise RuntimeError("MCP process not started")

        try:
            # Build the request
            request = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}

            # Send the request
            assert self.process.stdin is not None
            assert self.process.stdout is not None
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()

            # Read the response
            response = self.process.stdout.readline()
            return cast(Dict[str, Any], json.loads(response))

        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to send request: {str(e)}")
            raise

    def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        """Send a notification to the MCP process (no response expected)

        Args:
            method: The notification method
            params: The notification params
        """
        if not self.process:
            raise RuntimeError("MCP process not started")

        try:
            # Build the notification
            notification = {"jsonrpc": "2.0", "method": method, "params": params}
            # Send the notification
            assert self.process.stdin is not None
            self.process.stdin.write(json.dumps(notification) + "\n")
            self.process.stdin.flush()

        except Exception as e:
            # Silently handle pipe-broken errors (normal when the process exits)
            if isinstance(e, (BrokenPipeError, OSError)) and (
                e.errno == 32 if hasattr(e, "errno") else True
            ):
                return
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
        if self.process:
            try:
                # Send the exit notification - using a notification rather than a request
                self._send_notification("notifications/exit", {})
                # Wait for the process to exit
                self.process.wait(timeout=1)
            except Exception:
                # If the process did not exit cleanly, force a kill
                self.process.kill()
