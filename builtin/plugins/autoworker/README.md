# AutoWorker Plugin

AutoWorker organizes a batch of tasks under a backend working directory, manages them through the "Tasks" panel on the left side of the editor, and supports two execution paths: "Create an Agent to execute the task" + "the Agent calls the task management tool".

## Features

- **Frontend task panel** (sidebar_view on the left side of the editor): set the backend working directory, list grouped by task, edit task information (title/description/tags/due date), right-click menu (create an Agent to execute the task / mark as completed / mark as abandoned / edit info), create tasks, timed polling + manual refresh.
- **Task and directory structure**: the backend working directory is the root directory for all tasks; each task is assigned an auto-incrementing ID (e.g. `T001`) and a title, and its subdirectory is named `ID_title` (e.g. `T001_implement_login_feature`); the directory name is fixed to the `ID_title` at creation time, and modifying the title only updates `task.json` without changing the directory name.
- **Task state persistence**: `.haijunbot/autoworker/task.json` under each task subdirectory; the plugin discovers tasks by scanning `<working_dir>/*/.haijunbot/autoworker/task.json`. States: `pending` / `running` / `completed` / `abandoned` (no failure/blocked).
- **Dual-channel execution**:
  - Right-click "Create an Agent to execute the task": reuse the host `window.__haijunbotCreateAgentForTask`, set the new Agent's `working_dir` to the task subdirectory, and mark the task as "running" after creation.
  - The Agent calls the `task_manager` tool to view/modify the task state and save key information (notes); upon completion, it can mark it as "completed".
  - The frontend can also mark the state manually by clicking (fallback path).

## Directory Structure

```text
autoworker/
├── config.yaml          # builtin: true, tool_load_dirs, frontend.sidebar_views
├── plugin/
│   └── api.py           # Task CRUD private feature (runs in the gateway, called by the frontend proxy)
├── tools/
│   └── task_manager.py  # Agent task management tool (runs in the agent process, reuses api.py via importlib)
└── frontend/
    └── sidebar_view.js  # Task panel (self-contained single-file window.Vue)
```

## Task Data Structure

`.haijunbot/autoworker/task.json` under each task subdirectory:

```json
{
  "id": "T001",
  "title": "Implement login feature",
  "description": "…",
  "tags": ["Frontend", "Authentication"],
  "due_date": "2026-10-20",
  "status": "pending",
  "created_at": "2026-10-10T07:00:00+08:00",
  "updated_at": "2026-10-10T07:00:00+08:00",
  "notes": [{ "time": "2026-10-10T07:05:00+08:00", "content": "…" }]
}
```

## Task Management Tool (task_manager)

Any Agent can call it; actions:

- `list_tasks`: list tasks (by default scans the current directory, or a specified workdir)
- `get_task`: view a single task
- `create_task`: create a task
- `update_task`: update task details (title/description/tags/due date)
- `set_status`: mark the state (pending/running/completed/abandoned)
- `add_note`: save key information (with a timestamp)

The tool runs in the agent process, and the Agent's current working directory is its `working_dir`. When the Agent is created via "Create an Agent to execute the task", `working_dir` is the task subdirectory, and the tool by default locates `./.haijunbot/autoworker/task.json`; it also supports explicitly passing `workdir` (the backend working directory, i.e. the parent directory of the task subdirectory) + `task_id` to operate on other tasks.
