# -*- coding: utf-8 -*-
"""task_list_manager tool pure logic helper unit tests"""

from haijunbot.haijunbot_tools.task_list_manager import task_list_manager


def _tool():
    return task_list_manager.__new__(task_list_manager)


def test_build_iteration_task_content_first_iteration_unchanged():
    t = _tool()
    out = t._build_iteration_task_content("Task content", 1, [])
    assert out == "Task content"


def test_build_iteration_task_content_appends_latest_feedback():
    t = _tool()
    out = t._build_iteration_task_content("Task content", 2, ["First round feedback", "Second round feedback"])
    assert "Task content" in out
    assert "Second round feedback" in out
    assert "Please fix the issues" in out
