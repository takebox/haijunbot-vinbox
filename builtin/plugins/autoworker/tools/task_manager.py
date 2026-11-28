"""
AutoWorker TODO management tool (Agent side).

Difference from built-in task_list_manager: This tool only maintains the "TODO list" itself (same source as frontend task panel, cross-session persistence), does not decompose tasks or drive sub-Agent execution; task_list_manager is responsible for decomposing complex tasks into subtasks and scheduling execution.

Purpose:
- Allow any Agent to manage TODOs: view TODO list/details, update TODO info,
  mark status (pending/running/completed/abandoned), write notes.
- Agent typically starts with task subdirectory as working_dir, so defaults to "current task"
  (i.e., .haijunbot/autoworker/task.json under working_dir); can also explicitly pass workdir/task_id
  to operate on other tasks (e.g., create subtasks).

Parameters:
- action (str): Action, one of create_task / update_task / set_status / add_note /
  list_tasks / get_task.
- workdir (str, optional): Backend working directory (parent of task subdirectories). Defaults inferred from current working directory.
- task_id (str, optional): Task ID (e.g., T001). Defaults to current task.
- title / description / tags / due_date / status / content: Fields corresponding to each action.

Returns:
- success (bool)
- stdout (str): JSON text containing operation result
- stderr (str)

Notes:
- This tool directly reuses logic from plugin private function layer plugin/api.py, ensuring consistency with frontend panel behavior.
- Task data persisted in <workdir>/<ID>_<title>/.haijunbot/autoworker/task.json.
"""

import importlib.util
import json
import os
import sys
from typing import Any
from typing import Dict
from typing import Optional

_TASK_REL_PATH = os.path.join(".haijunbot", "autoworker", "task.json")

# Supported action set (keep consistent with parameters.enum)
_KNOWN_ACTIONS = {
    "create_task",
    "update_task",
    "set_status",
    "add_note",
    "list_tasks",
    "get_task",
}


def _load_api():
    """Load plugin private function layer plugin/api.py by path using importlib.

    plugin/ not in sys.path, so load by file path; fixed module name for cache reuse.
    """
    # tools/task_manager.py -> plugin root -> plugin/api.py
    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    api_path = os.path.join(plugin_root, "plugin", "api.py")
    if not os.path.isfile(api_path):
        raise FileNotFoundError(f"Plugin private function layer not found: {api_path}")
    mod_name = "autoworker_plugin_api"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, api_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module: {api_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _read_current_task_id(cwd: str) -> Optional[str]:
    """Read current task ID from task.json under current working directory; returns None if not exists."""
    tf = os.path.join(cwd, _TASK_REL_PATH)
    if not os.path.isfile(tf):
        return None
    try:
        with open(tf, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            tid = str(data.get("id") or "").strip()
            return tid or None
    except Exception:
        return None
    return None


def _infer_workdir(cwd: str) -> Optional[str]:
    """Infer backend working directory from current working directory.

    When Agent starts with task subdirectory as working_dir, cwd looks like <workdir>/<ID>_<title>,
    its parent directory is workdir. If cwd directly contains .haijunbot/autoworker/task.json, parent is workdir.
    """
    if os.path.isfile(os.path.join(cwd, _TASK_REL_PATH)):
        return os.path.dirname(cwd)
    return None


class TaskManagerTool:
    # Filename must match tool name for registry auto-load
    name = "task_manager"
    description = (
        "TODO management: maintains persistent TODO list under backend working directory, same source as frontend 'Tasks' "
        "panel. Can create/edit TODOs, mark status (pending/running/completed/abandoned), "
        "write notes, view list or details on demand. Suitable for recording cross-session "
        "persistent items like 'what to do, progress so far'. Defaults to current TODO "
        "(task.json of task where working_dir resides), can also operate on other TODOs via "
        "workdir/task_id."
        "Note: This tool only manages the TODO list itself, does not decompose/execute tasks; "
        "if you need to decompose complex tasks into subtasks and drive sub-Agent execution, use task_list_manager."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "create_task",
                    "update_task",
                    "set_status",
                    "add_note",
                    "list_tasks",
                    "get_task",
                ],
                "description": "Action to execute",
            },
            "workdir": {
                "type": "string",
                "description": "Backend working directory (parent of task subdirectories). Defaults inferred from current working directory.",
            },
            "task_id": {
                "type": "string",
                "description": "Task ID (e.g., T001). Defaults to current task.",
            },
            "title": {"type": "string", "description": "Task title (create_task/update_task)"},
            "description": {
                "type": "string",
                "description": "Task description (create_task/update_task)",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Task tags (create_task/update_task)",
            },
            "due_date": {
                "type": "string",
                "description": "Due date (create_task/update_task), e.g., 2026-10-20",
            },
            "status": {
                "type": "string",
                "enum": ["pending", "running", "completed", "abandoned"],
                "description": "Task status (set_status)",
            },
            "content": {
                "type": "string",
                "description": "Key info content (add_note)",
            },
        },
        "required": ["action"],
    }

    @staticmethod
    def check() -> bool:
        """Tool always available (pure file operations, no external dependencies)."""
        return True

    def _resolve_context(
        self, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve workdir and task_id: prefer explicit params, otherwise infer from current working directory.

        Returns {"workdir": str, "task_id": str, "error": str}.
        """
        cwd = os.getcwd()
        workdir = args.get("workdir")
        workdir = str(workdir).strip() if workdir else ""
        if not workdir:
            inferred = _infer_workdir(cwd)
            if not inferred:
                return {
                    "workdir": "",
                    "task_id": "",
                    "error": (
                        "Cannot infer backend working directory: current directory is not a task subdirectory, "
                        "please explicitly provide workdir parameter"
                    ),
                }
            workdir = inferred

        task_id = args.get("task_id")
        task_id = str(task_id).strip() if task_id else ""
        if not task_id:
            task_id = _read_current_task_id(cwd) or ""

        return {"workdir": workdir, "task_id": task_id, "error": ""}

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            action = str(args.get("action") or "").strip()
            if not action:
                return self._err("Parameter error: action cannot be empty")
            if action not in _KNOWN_ACTIONS:
                return self._err(f"Unknown action: {action}")

            api = _load_api()

            if action == "list_tasks":
                workdir = args.get("workdir")
                workdir = str(workdir).strip() if workdir else ""
                if not workdir:
                    ctx = self._resolve_context(args)
                    if ctx["error"]:
                        return self._err(ctx["error"])
                    workdir = ctx["workdir"]
                result = api.list_tasks(workdir=workdir)
                return self._ok(result)

            if action == "create_task":
                ctx = self._resolve_context(args)
                if ctx["error"]:
                    return self._err(ctx["error"])
                result = api.create_task(
                    workdir=ctx["workdir"],
                    title=args.get("title"),
                    description=args.get("description", ""),
                    tags=args.get("tags"),
                    due_date=args.get("due_date"),
                )
                return self._ok(result)

            # Remaining actions require task_id
            ctx = self._resolve_context(args)
            if ctx["error"]:
                return self._err(ctx["error"])
            if not ctx["task_id"]:
                return self._err(
                    "Cannot determine task ID: current directory is not a task subdirectory, please explicitly provide task_id"
                )

            if action == "get_task":
                result = api.get_task(
                    workdir=ctx["workdir"], task_id=ctx["task_id"]
                )
            elif action == "update_task":
                result = api.update_task(
                    workdir=ctx["workdir"],
                    task_id=ctx["task_id"],
                    title=args.get("title"),
                    description=args.get("description"),
                    tags=args.get("tags"),
                    due_date=args.get("due_date"),
                )
            elif action == "set_status":
                result = api.set_status(
                    workdir=ctx["workdir"],
                    task_id=ctx["task_id"],
                    status=args.get("status"),
                )
            elif action == "add_note":
                result = api.add_note(
                    workdir=ctx["workdir"],
                    task_id=ctx["task_id"],
                    content=args.get("content"),
                )
            else:
                return self._err(f"Unknown action: {action}")

            return self._ok(result)
        except Exception as e:
            return self._err(f"task_manager execution exception: {e}")

    @staticmethod
    def _ok(result: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap api return into unified tool return format."""
        success = bool(result.get("success"))
        return {
            "success": success,
            "stdout": json.dumps(result, ensure_ascii=False, indent=2),
            "stderr": "" if success else str(result.get("error") or "Operation failed"),
        }

    @staticmethod
    def _err(message: str) -> Dict[str, Any]:
        return {"success": False, "stdout": "", "stderr": message}