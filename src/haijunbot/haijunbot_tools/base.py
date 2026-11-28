# -*- coding: utf-8 -*-
import json
from typing import Any
from typing import Callable
from typing import Dict


class Tool:
    """Tool class, used to encapsulate a tool's basic information and execution method"""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        func: Callable[[Dict[str, Any]], Dict[str, Any]],
        protocol_version: str = "1.0",
        interactive: bool = False,
    ) -> None:
        """
        Initialize the tool object.

        Args:
            name (str): Tool name
            description (str): Tool description
            parameters (Dict[str, Any]): Tool parameter definitions
            func (Callable): Tool execution function
            protocol_version (str): Tool protocol version, defaults to "1.0"; supports "1.0" or "2.0"
            interactive (bool): Whether it is interactive/exclusive. True means the tool interacts with the user/terminal
                (such as execute_script, virtual_tty); during native parallel calls the whole batch degrades to serial.
        """
        self.name = name
        self.description = description
        self.parameters = parameters
        self.func = func
        self.protocol_version = protocol_version
        self.interactive = interactive

    def to_dict(self) -> Dict[str, Any]:
        """Convert the tool object to dictionary format, mainly used for serialization"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": json.dumps(self.parameters, ensure_ascii=False),
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool function.

        Args:
            arguments (Dict): Arguments required for tool execution

        Returns:
            Dict[str, Any]: Tool execution result
        """
        try:
            # func may use one of two signature styles:
            #   1) positional-argument style func(arguments) - traditional Tool usage
            #   2) keyword-argument style func(**kwargs) - the execute method of standalone class tools
            #       (such as execute(self, **kwargs) in browser_ext_sessions / daemon_sessions)
            # Prefer calling with keyword arguments, falling back to positional arguments on TypeError.
            if isinstance(arguments, dict):
                try:
                    # func may be **kwargs style; the type annotation assumes positional arguments, which is a false positive
                    return self.func(**arguments)  # ty: ignore[missing-argument]
                except TypeError:
                    return self.func(arguments)
            return self.func(arguments)
        except Exception as e:
            return {
                "success": False,
                "stderr": f"Tool {self.name} execution failed: {str(e)}",
                "stdout": "",
            }
