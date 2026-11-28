"""
HaijunBot frontend tool: lets the Agent issue commands to the user's frontend editor (such as opening a file / jumping to a line / selecting a region).

Purpose:
- Broadcast editor_* messages through the Web Gateway; the frontend then performs the corresponding operation in the user's Monaco workspace;
- Let the Agent, while analyzing/modifying code, guide the user's editor view to the relevant location, enabling
  visual collaboration between the Agent and the user.

Arguments:
- action (str, optional): The frontend operation to perform, currently supporting:
    - open_file: Open a file and jump to the target line/column (optionally selecting a section of code). Default value.
- path (str): Path of the file to open (relative to the Agent working_dir or an absolute path). Only needed for open_file.
- line (int, optional): Line number to jump to, defaults to 1
- column (int, optional): Column number to jump to, defaults to 1
- select_start (int, optional): Start column of the selection range (0-based), must be provided together with select_end
- select_end (int, optional): End column of the selection range (0-based), must be provided together with select_start
- reveal (bool, optional): Whether to scroll the target line to the center of the view, defaults to true

Returns:
- success (bool)
- stdout (str)
- stderr (str)
"""

from typing import Any
from typing import Dict

from haijunbot.haijunbot_gateway.manager import get_current_gateway
from haijunbot.haijunbot_utils.globals import agent_id as current_agent_id
from haijunbot.haijunbot_utils.output import PrettyOutput


class HaijunBotFrontendTool:
    # The file name must match the tool name so the registry can auto-load it
    name = "haijunbot_frontend"
    description = (
        "HaijunBot frontend tool: issues commands to the user's frontend editor (open file / jump to line / select code)."
        "Used to guide the user's editor view to the location the Agent is analyzing or modifying."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open_file"],
                "description": "The frontend operation to perform; currently supports open_file (open file); defaults to open_file",
            },
            "path": {
                "type": "string",
                "description": "Path of the file to open (relative to the current Agent working directory, or an absolute path)",
            },
            "line": {
                "type": "integer",
                "description": "Line number to jump to (starting from 1), defaults to 1",
            },
            "column": {
                "type": "integer",
                "description": "Column number to jump to (starting from 1), defaults to 1",
            },
            "select_start": {
                "type": "integer",
                "description": "Start column of the selection range (0-based), must be provided together with select_end",
            },
            "select_end": {
                "type": "integer",
                "description": "End column of the selection range (0-based), must be provided together with select_start",
            },
            "reveal": {
                "type": "boolean",
                "description": "Whether to scroll the target line to the center of the view, defaults to true",
            },
        },
        "required": [],
    }

    @staticmethod
    def check() -> bool:
        """Enabled only when there is a current Agent and the Gateway supports editor commands."""
        if not current_agent_id:
            return False
        gateway = get_current_gateway()
        return gateway is not None and hasattr(gateway, "publish_editor_command")

    def _execute_open_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """open_file: Open a file and jump to the target line/column (optionally selecting a section of code)."""
        path = args.get("path")
        if not isinstance(path, str) or not path.strip():
            return {
                "success": False,
                "stdout": "",
                "stderr": "Missing or invalid path argument",
            }

        if not current_agent_id:
            return {
                "success": False,
                "stdout": "",
                "stderr": "There is no current Agent context, unable to locate the working directory",
            }

        gateway = get_current_gateway()
        if gateway is None or not hasattr(gateway, "publish_editor_command"):
            return {
                "success": False,
                "stdout": "",
                "stderr": "The current Gateway does not support editor commands (publish_editor_command)",
            }

        payload: Dict[str, Any] = {"path": path.strip()}

        line = args.get("line")
        if line is not None:
            payload["line"] = int(line)
        column = args.get("column")
        if column is not None:
            payload["column"] = int(column)

        select_start = args.get("select_start")
        select_end = args.get("select_end")
        if select_start is not None and select_end is not None:
            payload["select_start"] = int(select_start)
            payload["select_end"] = int(select_end)
        elif select_start is not None or select_end is not None:
            return {
                "success": False,
                "stdout": "",
                "stderr": "select_start and select_end must be provided together",
            }

        reveal = args.get("reveal")
        if reveal is not None:
            payload["reveal"] = bool(reveal)

        publish = getattr(gateway, "publish_editor_command")
        publish(current_agent_id, "open_file", payload)
        PrettyOutput.auto_print(
            f"[haijunbot_frontend] Broadcast open file: {payload.get('path')}"
        )
        return {
            "success": True,
            "stdout": f"Notified the frontend editor to open the file: {payload.get('path')}",
            "stderr": "",
        }

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            action = args.get("action") or "open_file"
            if action == "open_file":
                return self._execute_open_file(args)
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Unsupported frontend operation: {action} (currently supports open_file)",
            }
        except Exception as e:
            PrettyOutput.auto_print(f"❌ {str(e)}")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to broadcast frontend command: {str(e)}",
            }
