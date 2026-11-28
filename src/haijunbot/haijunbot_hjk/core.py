# -*- coding: utf-8 -*-
"""Tool check core logic

Provides the core function implementation for tool detection.
"""

import subprocess
import shutil
from typing import Any, Dict, List, Optional

from haijunbot.haijunbot_hjk.config import (
    get_tools_config,
    get_tool_config,
    get_lint_tools_config,
    get_build_tools_config,
)


class ToolChecker:
    """Tool checker class

    Used to detect the installation status of tools in the system, including checking
    whether a tool exists and getting version information, etc.
    """

    def __init__(self) -> None:
        """Initialize the tool checker"""
        self.tools_config = get_tools_config()
        self.lint_tools_config = get_lint_tools_config()
        self.build_tools_config = get_build_tools_config()

    def check_tool_exists(self, command: str) -> bool:
        """Check whether a tool command exists

        Args:
            command: Tool command name (can be a simple command or a compound command such as 'python -m build')

        Returns:
            bool: Whether the tool exists
        """
        # Check if it is a compound command (contains a space, such as 'python -m build')
        if " " in command:
            # Compound command: extract the base command for detection
            base_command = command.split()[0]
            return shutil.which(base_command) is not None
        else:
            # Simple command: detect directly
            return shutil.which(command) is not None

    def get_tool_version(self, command: str) -> Optional[str]:
        """Get tool version information

        Args:
            command: Tool command name (can be a simple command or a compound command such as 'python -m build')

        Returns:
            Version string, or None if retrieval fails
        """
        if not self.check_tool_exists(command):
            return None

        # Check if it is a compound command
        if " " in command:
            # Compound command: execute the full command directly to get the version
            try:
                cmd_parts = command.split()
                result = subprocess.run(
                    cmd_parts + ["--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout:
                    # Only return the first line of version information
                    version = result.stdout.strip().split("\n")[0]
                    return version
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass
            return None
        else:
            # Simple command: try common version-retrieval arguments
            version_args = ["--version", "version", "-V", "-v"]

            for arg in version_args:
                try:
                    result = subprocess.run(
                        [command, arg],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0 and result.stdout:
                        # Only return the first line of version information
                        version = result.stdout.strip().split("\n")[0]
                        return version
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    continue

            return None

    def check_single_tool(self, tool_name: str) -> Dict[str, Any]:
        """Check a single tool

        Args:
            tool_name: Tool name

        Returns:
            Dictionary containing the tool check result
        """
        tool_config = get_tool_config(tool_name)

        if not tool_config:
            return {
                "name": tool_name,
                "found": False,
                "error": f"Unknown tool: {tool_name}",
                "description": "",
                "install_hint": "",
                "version": None,
            }

        command = tool_config["command"]
        exists = self.check_tool_exists(command)

        result = {
            "name": tool_name,
            "command": command,
            "found": exists,
            "description": tool_config["description"],
            "install_hint": tool_config["install_hint"],
            "version": None,
        }

        if exists:
            version = self.get_tool_version(command)
            result["version"] = version

        return result

    def check_all_tools(self) -> List[Dict[str, Any]]:
        """Check all configured tools

        Returns:
            List containing the check results of all tools
        """
        results = []

        for tool_config in self.tools_config:
            tool_name = tool_config["name"]
            result = self.check_single_tool(tool_name)
            results.append(result)

        return results

    def get_summary(self, results: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get the check result summary

        Args:
            results: List of tool check results

        Returns:
            Dictionary containing summary statistics
        """
        total = len(results)
        found = sum(1 for r in results if r["found"])
        missing = total - found

        return {
            "total": total,
            "found": found,
            "missing": missing,
        }

    def check_lint_tools(self) -> List[Dict[str, Any]]:
        """Check all lint tools

        Returns:
            List containing the check results of all lint tools
        """
        results = []

        for tool_config in self.lint_tools_config:
            tool_name = tool_config["name"]
            result = self.check_single_tool(tool_name)
            results.append(result)

        return results

    def check_build_tools(self) -> List[Dict[str, Any]]:
        """Check all build tools

        Returns:
            List containing the check results of all build tools
        """
        results = []

        for tool_config in self.build_tools_config:
            tool_name = tool_config["name"]
            result = self.check_single_tool(tool_name)
            results.append(result)

        return results
