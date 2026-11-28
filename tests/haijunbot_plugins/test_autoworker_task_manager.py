# -*- coding: utf-8 -*-
"""AutoWorker plugin Agent-side tool task_manager.py tests.

Covers:
1. Tool metadata (name matches filename, check usable, parameters valid);
2. Default context inference: when Agent uses task subdirectory as cwd, automatically locate current task;
3. Various actions: get_task / set_status / add_note / update_task / create_task / list_tasks;
4. Explicit workdir/task_id to operate on other tasks;
5. Boundaries: error when non-task directory and workdir not provided; error for unknown action.

Uses importlib to load plugin source directly, without depending on global configuration loading.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

PLUGIN_DIR = (
    Path(__file__).resolve().parents[2] / "builtin" / "plugins" / "autoworker"
)
TOOL_FILE = PLUGIN_DIR / "tools" / "task_manager.py"
API_FILE = PLUGIN_DIR / "plugin" / "api.py"


@pytest.fixture(scope="module")
def tool_cls():
    """Load task_manager.py, return TaskManagerTool class."""
    assert TOOL_FILE.is_file(), f"Tool file does not exist: {TOOL_FILE}"
    spec = importlib.util.spec_from_file_location("autoworker_task_manager", str(TOOL_FILE))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["autoworker_task_manager"] = mod
    spec.loader.exec_module(mod)
    return mod.TaskManagerTool


@pytest.fixture()
def api():
    """Load plugin/api.py for preparing task data."""
    spec = importlib.util.spec_from_file_location("autoworker_api_tm", str(API_FILE))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["autoworker_api_tm"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def workdir(tmp_path):
    wd = tmp_path / "tasks"
    wd.mkdir()
    return str(wd)


def _chdir(path):
    """Context manager for switching cwd (simple implementation)."""
    class _Ctx:
        def __enter__(self):
            self._old = os.getcwd()
            os.chdir(path)

        def __exit__(self, *a):
            os.chdir(self._old)

    return _Ctx()


def test_tool_metadata(tool_cls):
    """Tool metadata: name matches filename, check usable, parameters valid."""
    assert tool_cls.name == "task_manager"
    assert tool_cls.check() is True
    params = tool_cls.parameters
    assert params["type"] == "object"
    assert "action" in params["required"]
    assert set(params["properties"]["action"]["enum"]) == {
        "create_task",
        "update_task",
        "set_status",
        "add_note",
        "list_tasks",
        "get_task",
    }


def test_list_tasks(tool_cls, api, workdir):
    """list_tasks with explicit workdir lists tasks."""
    api.create_task(workdir=workdir, title="Task 1")
    api.create_task(workdir=workdir, title="Task 2")
    tool = tool_cls()
    res = tool.execute({"action": "list_tasks", "workdir": workdir})
    assert res["success"] is True
    payload = json.loads(res["stdout"])
    assert payload["count"] == 2
    assert [t["id"] for t in payload["data"]] == ["T001", "T002"]


def test_create_task(tool_cls, workdir):
    """create_task creates a task via the tool."""
    tool = tool_cls()
    res = tool.execute(
        {
            "action": "create_task",
            "workdir": workdir,
            "title": "Implement login",
            "description": "Username/password login",
            "tags": ["auth"],
            "due_date": "2026-10-20",
        }
    )
    assert res["success"] is True
    payload = json.loads(res["stdout"])
    assert payload["data"]["id"] == "T001"
    assert payload["data"]["title"] == "Implement login"
    assert payload["data"]["task_dir"]


def test_default_context_from_cwd(tool_cls, api, workdir):
    """When Agent uses task subdirectory as cwd, get_task/set_status/add_note automatically locate current task."""
    res = api.create_task(workdir=workdir, title="Current task")
    task_dir = res["data"]["task_dir"]
    tool = tool_cls()

    with _chdir(task_dir):
        # get_task defaults to current task
        r = tool.execute({"action": "get_task"})
        assert r["success"] is True
        assert json.loads(r["stdout"])["data"]["id"] == "T001"

        # set_status defaults to current task
        r = tool.execute({"action": "set_status", "status": "running"})
        assert r["success"] is True
        assert json.loads(r["stdout"])["data"]["status"] == "running"

        # add_note defaults to current task
        r = tool.execute({"action": "add_note", "content": "Key info"})
        assert r["success"] is True
        notes = json.loads(r["stdout"])["data"]["notes"]
        assert notes[0]["content"] == "Key info"

        # list_tasks infers workdir from cwd
        r = tool.execute({"action": "list_tasks"})
        assert r["success"] is True
        assert json.loads(r["stdout"])["count"] == 1


def test_update_task_via_tool(tool_cls, api, workdir):
    """update_task updates title/description, directory name unchanged."""
    res = api.create_task(workdir=workdir, title="Old title")
    task_dir = res["data"]["task_dir"]
    tool = tool_cls()
    with _chdir(task_dir):
        r = tool.execute(
            {"action": "update_task", "title": "New title", "description": "New description"}
        )
        assert r["success"] is True
        data = json.loads(r["stdout"])["data"]
        assert data["title"] == "New title"
        assert data["description"] == "New description"
        assert Path(task_dir).name == "T001_Old title"  # Directory name unchanged


def test_explicit_task_id_other_task(tool_cls, api, workdir):
    """Explicit workdir+task_id to operate on other tasks (Agent operates on Task 2 from Task 1 directory)."""
    r1 = api.create_task(workdir=workdir, title="Task 1")
    api.create_task(workdir=workdir, title="Task 2")
    tool = tool_cls()
    with _chdir(r1["data"]["task_dir"]):
        r = tool.execute(
            {"action": "set_status", "workdir": workdir, "task_id": "T002", "status": "completed"}
        )
        assert r["success"] is True
        assert json.loads(r["stdout"])["data"]["id"] == "T002"
    # Task 2 was indeed changed, Task 1 unchanged
    assert api.get_task(workdir=workdir, task_id="T002")["data"]["status"] == "completed"
    assert api.get_task(workdir=workdir, task_id="T001")["data"]["status"] == "pending"


def test_non_task_dir_without_workdir_errors(tool_cls, tmp_path):
    """Error when non-task directory and workdir not provided."""
    tool = tool_cls()
    plain = tmp_path / "plain"
    plain.mkdir()
    with _chdir(str(plain)):
        r = tool.execute({"action": "get_task"})
        assert r["success"] is False
        assert "workdir" in r["stderr"] or "working directory" in r["stderr"]


def test_unknown_action_errors(tool_cls, workdir):
    """Error for unknown action."""
    tool = tool_cls()
    r = tool.execute({"action": "no_such_action", "workdir": workdir})
    assert r["success"] is False
    assert "Unknown action" in r["stderr"]


def test_missing_action_errors(tool_cls):
    """Error when action is missing."""
    tool = tool_cls()
    r = tool.execute({})
    assert r["success"] is False
    assert "action" in r["stderr"]


def test_set_status_invalid_via_tool(tool_cls, api, workdir):
    """Invalid status returns failure via the tool."""
    res = api.create_task(workdir=workdir, title="Task")
    tool = tool_cls()
    with _chdir(res["data"]["task_dir"]):
        r = tool.execute({"action": "set_status", "status": "failed"})
        assert r["success"] is False
        assert "Invalid status" in r["stderr"]
