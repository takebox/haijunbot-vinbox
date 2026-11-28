# -*- coding: utf-8 -*-
"""TaskManager unit tests (load_tasks and select_task)"""

import os

from haijunbot.haijunbot_agent.task_manager import TaskManager


class TestTaskManagerLoadTasks:
    def test_load_tasks_merges_and_overrides(self, tmp_path, monkeypatch):
        # Simulate data_dir
        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "haijunbot.haijunbot_agent.task_manager.get_data_dir", lambda: str(data_dir)
        )

        # Write data_dir/pre-command
        (data_dir / "pre-command").write_text(
            "TaskA: descA\nTaskB: descB\n", encoding="utf-8"
        )

        # Create .haijunbot/pre-command in current directory
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / ".haijunbot").mkdir()
        (proj / ".haijunbot" / "pre-command").write_text(
            "TaskB: descB_local\nTaskC: descC\n", encoding="utf-8"
        )

        # Switch to project directory
        cwd = os.getcwd()
        os.chdir(proj)
        try:
            tasks = TaskManager.load_tasks()
        finally:
            os.chdir(cwd)

        # Merge and local overrides same-name tasks in data_dir
        assert tasks == {
            "TaskA": "descA",
            "TaskB": "descB_local",
            "TaskC": "descC",
        }

    def test_load_tasks_invalid_yaml_graceful(self, tmp_path, monkeypatch):
        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "haijunbot.haijunbot_agent.task_manager.get_data_dir", lambda: str(data_dir)
        )

        # data_dir/pre-command contains invalid YAML
        (data_dir / "pre-command").write_text(
            "This is: [invalid: yaml", encoding="utf-8"
        )

        # Local is valid
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / ".haijunbot").mkdir()
        (proj / ".haijunbot" / "pre-command").write_text(
            "TaskX: X\nTaskY: Y\n", encoding="utf-8"
        )

        cwd = os.getcwd()
        os.chdir(proj)
        try:
            tasks = TaskManager.load_tasks()
        finally:
            os.chdir(cwd)

        assert tasks == {"TaskX": "X", "TaskY": "Y"}
