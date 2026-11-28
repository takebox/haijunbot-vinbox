# -*- coding: utf-8 -*-
from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Dict
from typing import List


class McpClient(ABC):
    """MCP client abstract base class"""

    @abstractmethod
    def get_tool_list(self) -> List[Dict[str, Any]]:
        """Get the tool list

        Returns:
            List[Dict[str, Any]]: Tool list, each tool contains the following fields:
                - name: str - Tool name
                - description: str - Tool description
                - parameters: Dict - Tool parameters
        """
        pass

    @abstractmethod
    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool

        Args:
            tool_name: Tool name
            arguments: Argument dictionary containing the parameters required for tool execution

        Returns:
            Dict[str, Any]: Execution result, containing the following fields:
                - success: bool - Whether execution succeeded
                - stdout: str - Standard output
                - stderr: str - Standard error
        """
        pass

    @abstractmethod
    def get_resource_list(self) -> List[Dict[str, Any]]:
        """Get the resource list

        Returns:
            List[Dict[str, Any]]: Resource list, each resource contains the following fields:
                - uri: str - Unique identifier of the resource
                - name: str - Name of the resource
                - description: str - Description of the resource (optional)
                - mimeType: str - MIME type of the resource (optional)
        """
        pass

    @abstractmethod
    def get_resource(self, uri: str) -> Dict[str, Any]:
        """Get the content of the specified resource

        Args:
            uri: str - URI identifier of the resource

        Returns:
            Dict[str, Any]: Resource content, containing the following fields:
                - uri: str - URI of the resource
                - mimeType: str - MIME type of the resource (optional)
                - text: str - Text content (if it is a text resource)
                - blob: str - Binary content (if it is a binary resource, base64-encoded)
        """
        pass
