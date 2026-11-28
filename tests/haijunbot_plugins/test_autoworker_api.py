# -*- coding: utf-8 -*-
"""AutoWorker plugin (autoworker) private function api.py tests.

Covers task CRUD:
1. create_task: create task, ID increment, directory name `ID_Title`, task.json structure;
2. update_task: update details, title change does not change directory name (avoid reference path drift);
3. set_status: status change, invalid status raises error;
4. add_note: append timestamped note;
5. list_tasks: scan to discover tasks, sort by id ascending;
6. get_task: find by id;
7. Boundaries: workdir does not exist / empty title / tag normalization / concurrent multi-task independent directories.

Uses importlib to load plugin source files directly, without depending on global configuration
loading, to avoid polluting the real environment.
"""
import importlib.util
import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

PLUGIN_DIR = (
    Path(__file__).resolve().parents[2] / "builtin" / "plugins" / "autoworker"
)
API_FILE = PLUGIN_DIR / "plugin" / "api.py"


@pytest.fixture(scope="module")
def api():
    """Load autoworker/plugin/api.py module."""
    assert API_FILE.is_file(), f"api.py does not exist: {API_FILE}"
    spec = importlib.util.spec_from_file_location("autoworker_api", str(API_FILE))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["autoworker_api"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def workdir(tmp_path):
    """Temporary backend working directory."""
    wd = tmp_path / "tasks"
    wd.mkdir()
    return str(wd)


def _read_task_json(task_dir):
    """Read task.json under the task subdirectory."""
    tf = Path(task_dir) / ".haijunbot" / "autoworker" / "task.json"
    assert tf.is_file(), f"task.json does not exist: {tf}"
    with open(tf, "r", encoding="utf-8") as f:
        return json.load(f)


def test_create_task_basic(api, workdir):
    """Create task: return structure, directory naming, task.json persisted."""
    res = api.create_task(
        workdir=workdir,
        title="Implement login feature",
        description="Support username/password login",
        tags=["frontend", "auth"],
        due_date="2026-10-20",
    )
    assert res["success"] is True
    data = res["data"]
    assert data["id"] == "T001"
    assert data["title"] == "Implement login feature"
    assert data["status"] == "pending"
    assert data["tags"] == ["frontend", "auth"]
    assert data["due_date"] == "2026-10-20"
    assert data["notes"] == []
    assert data["created_at"] and data["updated_at"]
    # Directory name = ID_Title
    task_dir = data["task_dir"]
    assert Path(task_dir).name == "T001_Implement login feature"
    # task.json persisted and does not contain internal field task_dir
    on_disk = _read_task_json(task_dir)
    assert on_disk["id"] == "T001"
    assert "task_dir" not in on_disk


def test_create_task_id_increment(api, workdir):
    """ID increment: T001, T002, T003."""
    ids = []
    for title in ["Task 1", "Task 2", "Task 3"]:
        res = api.create_task(workdir=workdir, title=title)
        assert res["success"] is True
        ids.append(res["data"]["id"])
    assert ids == ["T001", "T002", "T003"]


def test_create_task_dir_name_cleans_illegal_chars(api, workdir):
    """Directory name cleans illegal characters (/ etc.), but title field preserves original title."""
    res = api.create_task(workdir=workdir, title="Task/with slash")
    assert res["success"] is True
    data = res["data"]
    assert data["title"] == "Task/with slash"  # title preserved
    assert "Task_with slash" in Path(data["task_dir"]).name  # Directory name cleaned


def test_create_task_requires_title(api, workdir):
    """Error when title is empty."""
    res = api.create_task(workdir=workdir, title="   ")
    assert res["success"] is False
    assert "title" in res["error"]


def test_create_task_requires_workdir(api):
    """Error when workdir is empty or does not exist."""
    res = api.create_task(workdir="", title="Task")
    assert res["success"] is False
    res = api.create_task(workdir="/nonexistent/path/xyz", title="Task")
    assert res["success"] is False


def test_update_task_keeps_dir_name(api, workdir):
    """Updating title only changes task.json, not the directory name (avoid reference path drift)."""
    res = api.create_task(workdir=workdir, title="Old title")
    task_id = res["data"]["id"]
    task_dir = res["data"]["task_dir"]
    assert Path(task_dir).name == "T001_Old title"

    res = api.update_task(
        workdir=workdir, task_id=task_id, title="New title", description="New description"
    )
    assert res["success"] is True
    assert res["data"]["title"] == "New title"
    assert res["data"]["description"] == "New description"
    # Directory name unchanged
    assert Path(task_dir).exists()
    assert Path(task_dir).name == "T001_Old title"
    # task.json on disk has been updated
    on_disk = _read_task_json(task_dir)
    assert on_disk["title"] == "New title"


def test_update_task_not_found(api, workdir):
    """Error when updating a nonexistent task."""
    res = api.update_task(workdir=workdir, task_id="T999", title="x")
    assert res["success"] is False
    assert "does not exist" in res["error"]


def test_set_status(api, workdir):
    """Status transitions and invalid status errors."""
    res = api.create_task(workdir=workdir, title="Task")
    task_id = res["data"]["id"]
    for status in ["running", "completed", "abandoned", "pending"]:
        res = api.set_status(workdir=workdir, task_id=task_id, status=status)
        assert res["success"] is True
        assert res["data"]["status"] == status
    # Invalid status
    res = api.set_status(workdir=workdir, task_id=task_id, status="failed")
    assert res["success"] is False
    assert "Invalid status" in res["error"]


def test_add_note(api, workdir):
    """Append timestamped note."""
    res = api.create_task(workdir=workdir, title="Task")
    task_id = res["data"]["id"]
    res = api.add_note(workdir=workdir, task_id=task_id, content="Key info A")
    assert res["success"] is True
    assert len(res["data"]["notes"]) == 1
    assert res["data"]["notes"][0]["content"] == "Key info A"
    assert res["data"]["notes"][0]["time"]
    # Append second note
    res = api.add_note(workdir=workdir, task_id=task_id, content="Key info B")
    assert len(res["data"]["notes"]) == 2
    assert [n["content"] for n in res["data"]["notes"]] == ["Key info A", "Key info B"]
    # Empty content raises error
    res = api.add_note(workdir=workdir, task_id=task_id, content="   ")
    assert res["success"] is False


def test_list_tasks_sorted(api, workdir):
    """list_tasks scans to discover tasks and sorts by id ascending."""
    for title in ["Task B", "Task A", "Task C"]:
        api.create_task(workdir=workdir, title=title)
    res = api.list_tasks(workdir=workdir)
    assert res["success"] is True
    assert res["count"] == 3
    assert [t["id"] for t in res["data"]] == ["T001", "T002", "T003"]


def test_list_tasks_empty(api, workdir):
    """Returns empty list when there are no tasks."""
    res = api.list_tasks(workdir=workdir)
    assert res["success"] is True
    assert res["count"] == 0
    assert res["data"] == []


def test_get_task(api, workdir):
    """Find task by id."""
    api.create_task(workdir=workdir, title="Task A")
    res = api.get_task(workdir=workdir, task_id="T001")
    assert res["success"] is True
    assert res["data"]["id"] == "T001"
    # Does not exist
    res = api.get_task(workdir=workdir, task_id="T999")
    assert res["success"] is False


def test_tags_normalization(api, workdir):
    """Tag normalization: string/list/deduplication."""
    res = api.create_task(workdir=workdir, title="Task", tags="a, b, a")
    assert res["data"]["tags"] == ["a", "b"]
    res = api.update_task(
        workdir=workdir, task_id="T001", tags=["x", "y", "x"]
    )
    assert res["data"]["tags"] == ["x", "y"]


def test_concurrent_tasks_independent(api, workdir):
    """Multi-task independent directories, no interference."""
    res1 = api.create_task(workdir=workdir, title="Task 1")
    res2 = api.create_task(workdir=workdir, title="Task 2")
    # Two task directories are independent
    assert res1["data"]["task_dir"] != res2["data"]["task_dir"]
    # Modifying Task 1 does not affect Task 2
    api.set_status(workdir=workdir, task_id="T001", status="completed")
    res = api.get_task(workdir=workdir, task_id="T002")
    assert res["data"]["status"] == "pending"


def test_public_functions_whitelist(api):
    """PUBLIC_FUNCTIONS whitelist contains all external functions."""
    whitelist = set(api.PUBLIC_FUNCTIONS)
    assert {
        "create_task",
        "update_task",
        "set_status",
        "add_note",
        "list_tasks",
        "get_task",
    } == whitelist
