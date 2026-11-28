# -*- coding: utf-8 -*-
"""haijunbot_mcp module unit tests"""

import pytest

from haijunbot.haijunbot_mcp import McpClient


class TestMcpClient:
    """Test McpClient abstract base class"""

    def test_abstract_class_cannot_instantiate(self):
        """Test that abstract class cannot be instantiated directly"""
        with pytest.raises(TypeError):
            McpClient()

    def test_abstract_methods(self):
        """Test abstract methods"""

        # Create a class that does not implement all abstract methods
        class IncompleteMcpClient(McpClient):
            def get_tool_list(self):
                return []

        # Should not be instantiable because other abstract methods are missing
        with pytest.raises(TypeError):
            IncompleteMcpClient()

    def test_complete_implementation(self):
        """Test complete implementation"""

        class CompleteMcpClient(McpClient):
            def get_tool_list(self):
                return []

            def execute(self, tool_name: str, arguments: dict):
                return {"success": True, "stdout": "", "stderr": ""}

            def get_resource_list(self):
                return []

            def get_resource(self, uri: str):
                return {}

        # Complete implementation should be instantiable
        client = CompleteMcpClient()
        assert client is not None
        assert isinstance(client, McpClient)
