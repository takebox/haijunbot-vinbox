"""
AutoWorker plugin private function layer (runs in gateway, called by frontend proxy; not exposed to Agent).

Provides task CRUD pure functions:
- create_task / update_task / set_status / add_note: write operations
- list_tasks / get_task: read operations

Tasks persisted to each task subdirectory under backend working directory at `.haijunbot/autoworker/task.json`:
    <workdir>/<ID>_<title>/.haijunbot/autoworker/task.json
- Directory name fixed using `ID_title` at creation time; title modification only updates task.json, not directory name (to avoid reference path drift).
- ID auto-increments (T001, T002...).
- Status: pending / running / completed / abandoned (no failed/blocked).

Each function returns dict: {"success": bool, "data": .../ "message": .../ "error": ...}.
This module is not declared in tool_load_dirs, so not loaded by ToolRegistry, invisible to Agent;
gateway dynamically loads this module via plugin function proxy endpoint and calls it.
"""
import json
import os
import re
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

# Valid task statuses (no failed/blocked)
VALID_STATUS = {"pending", "running", "completed", "abandoned"}
# Status display names
STATUS_LABELS = {
    "pending": "Pending",
    "running": "Running",
    "completed": "Completed",
    "abandoned": "Abandoned",
}
# Task file path relative to task subdirectory
_TASK_REL_PATH = os.path.join(".haijunbot", "autoworker", "task.json")


def _now() -> str:
    """Current local time, ISO 8601 format (with timezone, second precision)."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _clean_dir_name(title: str) -> str:
    """Clean illegal characters in title for directory naming (not used for task.json title field)."""
    cleaned = re.sub(r'[\\/:*?"<>|\r\n]+', "_", str(title or "").strip())
    return cleaned or "Unnamed"


def _task_file_path(task_dir: str) -> str:
    """Task subdirectory -> task.json absolute path."""
    return os.path.join(task_dir, _TASK_REL_PATH)


def _load_task(task_dir: str) -> Optional[Dict[str, Any]]:
    """Read task.json under task subdirectory; returns None if not exists or parse fails.
    Returned task dict includes internal field task_dir (task subdirectory absolute path).
    """
    tf = _task_file_path(task_dir)
    if not os.path.isfile(tf):
        return None
    try:
        with open(tf, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        data["task_dir"] = task_dir
        return data
    except Exception:
        return None


def _scan_tasks(workdir: str) -> List[Dict[str, Any]]:
    """Scan <workdir>/*/.haijunbot/autoworker/task.json, return task list (sorted by id numeric ascending)."""
    tasks: List[Dict[str, Any]] = []
    if not os.path.isdir(workdir):
        return tasks
    try:
        entries = sorted(os.listdir(workdir))
    except Exception:
        return tasks
    for name in entries:
        task_dir = os.path.join(workdir, name)
        if not os.path.isdir(task_dir):
            continue
        task = _load_task(task_dir)
        if task:
            tasks.append(task)

    def _sort_key(t: Dict[str, Any]) -> int:
        m = re.match(r"^T(\d+)$", str(t.get("id", "")))
        return int(m.group(1)) if m else 0

    tasks.sort(key=_sort_key)
    return tasks


def _next_task_id(workdir: str) -> str:
    """Generate next incremental task ID (T001, T002...)."""
    max_num = 0
    for t in _scan_tasks(workdir):
        m = re.match(r"^T(\d+)$", str(t.get("id", "")))
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"T{max_num + 1:03d}"


def _find_task(workdir: str, task_id: str) -> Optional[Dict[str, Any]]:
    """Find task by task ID; returns None if not found."""
    for t in _scan_tasks(workdir):
        if str(t.get("id", "")) == task_id:
            return t
    return None


def _require_workdir(workdir: Any) -> tuple:
    """Validate and normalize backend working directory. Returns (workdir, error); error non-empty when workdir empty/doesn't exist."""
    workdir = (workdir or "").strip()
    if not workdir:
        return "", "Backend working directory not specified"
    workdir = os.path.abspath(os.path.expanduser(workdir))
    if not os.path.isdir(workdir):
        return "", f"Backend working directory does not exist: {workdir}"
    return workdir, ""


def _require_task_id(task_id: Any) -> tuple:
    """Validate task ID. Returns (task_id, error)."""
    task_id = str(task_id or "").strip()
    if not task_id:
        return "", "Task ID not specified"
    return task_id, ""


def _write_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """Write task dict back to its task.json (excluding internal field task_dir)."""
    task_dir = task.get("task_dir")
    if not task_dir:
        return {"success": False, "error": "Task directory missing"}
    tf = _task_file_path(task_dir)
    try:
        os.makedirs(os.path.dirname(tf), exist_ok=True)
        data = {k: v for k, v in task.items() if k != "task_dir"}
        with open(tf, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": f"Failed to write task file: {e}"}


def _normalize_tags(tags: Any) -> List[str]:
    """Normalize tags: accept list or comma-separated string, return deduplicated string list."""
    if tags is None:
        return []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    elif isinstance(tags, (list, tuple)):
        tags = [str(t).strip() for t in tags if str(t).strip()]
    else:
        tags = []
    seen = set()
    result = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _normalize_due_date(due_date: Any) -> str:
    """Normalize due date: accept empty/None (return empty string) or string (trim)."""
    if due_date is None:
        return ""
    return str(due_date).strip()


def create_task(
    workdir: Optional[str] = None,
    title: Optional[str] = None,
    description: str = "",
    tags: Any = None,
    due_date: Any = None,
) -> Dict[str, Any]:
    """Create task: generate incremental ID, create <workdir>/<ID>_<title> subdirectory and task.json.
    Directory name fixed using ID_title at creation time; returns data containing id/task_dir etc.
    """
    workdir, err = _require_workdir(workdir)
    if err:
        return {"success": False, "error": err}
    title = (title or "").strip()
    if not title:
        return {"success": False, "error": "Please provide task title"}
    task_id = _next_task_id(workdir)
    dir_name = f"{task_id}_{_clean_dir_name(title)}"
    task_dir = os.path.join(workdir, dir_name)
    if os.path.exists(task_dir):
        return {"success": False, "error": f"Task directory already exists: {task_dir}"}
    now = _now()
    task: Dict[str, Any] = {
        "id": task_id,
        "title": title,
        "description": str(description or ""),
        "tags": _normalize_tags(tags),
        "due_date": _normalize_due_date(due_date),
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "notes": [],
        "task_dir": task_dir,
    }
    result = _write_task(task)
    if not result["success"]:
        return result
    # task_dir is internal field (not persisted), but added to return data: frontend uses it to set Agent working directory
    data = dict(result["data"])
    data["task_dir"] = task_dir
    return {
        "success": True,
        "data": data,
        "message": f"Task {task_id} created",
    }


def update_task(
    workdir: Optional[str] = None,
    task_id: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    tags: Any = None,
    due_date: Any = None,
) -> Dict[str, Any]:
    """Update task details (title/description/tags/due_date).
    Title modification only updates task.json, not directory name (to avoid reference path drift).
    """
    workdir, err = _require_workdir(workdir)
    if err:
        return {"success": False, "error": err}
    task_id, err = _require_task_id(task_id)
    if err:
        return {"success": False, "error": err}
    task = _find_task(workdir, task_id)
    if not task:
        return {"success": False, "error": f"Task does not exist: {task_id}"}
    if title is not None:
        title = str(title).strip()
        if not title:
            return {"success": False, "error": "Task title cannot be empty"}
        task["title"] = title
    if description is not None:
        task["description"] = str(description)
    if tags is not None:
        task["tags"] = _normalize_tags(tags)
    if due_date is not None:
        task["due_date"] = _normalize_due_date(due_date)
    task["updated_at"] = _now()
    result = _write_task(task)
    if not result["success"]:
        return result
    data = dict(result["data"])
    data["task_dir"] = task["task_dir"]
    return {
        "success": True,
        "data": data,
        "message": f"Task {task_id} updated",
    }


def set_status(
    workdir: Optional[str] = None,
    task_id: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """Mark task status (pending/running/completed/abandoned)."""
    workdir, err = _require_workdir(workdir)
    if err:
        return {"success": False, "error": err}
    task_id, err = _require_task_id(task_id)
    if err:
        return {"success": False, "error": err}
    status = str(status or "").strip()
    if status not in VALID_STATUS:
        return {
            "success": False,
            "error": f"Invalid status: {status} (options: {', '.join(sorted(VALID_STATUS))})",
        }
    task = _find_task(workdir, task_id)
    if not task:
        return {"success": False, "error": f"Task does not exist: {task_id}"}
    task["status"] = status
    task["updated_at"] = _now()
    result = _write_task(task)
    if not result["success"]:
        return result
    data = dict(result["data"])
    data["task_dir"] = task["task_dir"]
    return {
        "success": True,
        "data": data,
        "message": f"Task {task_id} status updated to {STATUS_LABELS.get(status, status)}",
    }


def add_note(
    workdir: Optional[str] = None,
    task_id: Optional[str] = None,
    content: Optional[str] = None,
) -> Dict[str, Any]:
    """Save key info (notes) with timestamp, for subsequent task report generation."""
    workdir, err = _require_workdir(workdir)
    if err:
        return {"success": False, "error": err}
    task_id, err = _require_task_id(task_id)
    if err:
        return {"success": False, "error": err}
    content = (content or "").strip()
    if not content:
        return {"success": False, "error": "Please provide note content"}
    task = _find_task(workdir, task_id)
    if not task:
        return {"success": False, "error": f"Task does not exist: {task_id}"}
    notes = task.get("notes") or []
    if not isinstance(notes, list):
        notes = []
    notes.append({"time": _now(), "content": content})
    task["notes"] = notes
    task["updated_at"] = _now()
    result = _write_task(task)
    if not result["success"]:
        return result
    data = dict(result["data"])
    data["task_dir"] = task["task_dir"]
    return {
        "success": True,
        "data": data,
        "message": f"Key info saved for task {task_id}",
    }


def list_tasks(workdir: Optional[str] = None) -> Dict[str, Any]:
    """List all tasks under backend working directory (sorted by id ascending)."""
    workdir, err = _require_workdir(workdir)
    if err:
        return {"success": False, "error": err}
    tasks = _scan_tasks(workdir)
    return {
        "success": True,
        "data": tasks,
        "workdir": workdir,
        "count": len(tasks),
    }


def get_task(
    workdir: Optional[str] = None, task_id: Optional[str] = None
) -> Dict[str, Any]:
    """View single task details."""
    workdir, err = _require_workdir(workdir)
    if err:
        return {"success": False, "error": err}
    task_id, err = _require_task_id(task_id)
    if err:
        return {"success": False, "error": err}
    task = _find_task(workdir, task_id)
    if not task:
        return {"success": False, "error": f"Task does not exist: {task_id}"}
    return {"success": True, "data": task}


# Whitelist of functions callable via gateway proxy (prevent arbitrary function calls)
PUBLIC_FUNCTIONS: List[str] = [
    "create_task",
    "update_task",
    "set_status",
    "add_note",
    "list_tasks",
    "get_task",
]