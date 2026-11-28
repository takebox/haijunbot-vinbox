# -*- coding: utf-8 -*-
"""Tests: Auto-clearing historical task lists when creating a new task list

Requirement: When creating a task list (auto-created by add_tasks), automatically clear historical task lists,
because creating a new list usually means previous tasks have been completed.
"""

from unittest.mock import Mock

from haijunbot.haijunbot_tools.task_list_manager import task_list_manager


def _make_tool():
    """Construct tool instance without __init__ (only for testing helper logic)"""
    return task_list_manager.__new__(task_list_manager)


def _make_task_info():
    """Construct a valid tasks_info list"""
    return [
        {
            "task_name": "Task A",
            "task_desc": "Description A",
            "expected_output": "1) Output A",
            "agent_type": "main",
        }
    ]


def _make_agent(old_task_list_id="old_list_001", is_sub_agent=False):
    """Construct mock agent, default has historical task list and is main Agent"""
    agent = Mock()
    agent.name = "test_agent"

    def fake_get_user_data(key):
        if key == "__task_list_id__":
            return old_task_list_id
        if key == "__is_sub_agent__":
            return is_sub_agent
        return None

    agent.get_user_data.side_effect = fake_get_user_data
    agent.set_user_data.return_value = None
    agent.delete_user_data.return_value = None
    return agent


def _make_task_list_manager(existing=True, delete_success=True):
    """Construct mock task_list_manager"""
    tlm = Mock()
    if existing:
        tlm.get_task_list.return_value = Mock()  # Non-None, means old list still exists
    else:
        tlm.get_task_list.return_value = None
    tlm.delete_task_list.return_value = (
        delete_success,
        None if delete_success else "Delete failed",
    )
    tlm.create_task_list.return_value = ("new_list_002", True, None)
    tlm.add_tasks.return_value = (["task-1"], True, None)
    return tlm


class TestAutoClearOnCreate:
    """Auto-clearing historical task lists when creating a new task list"""

    def test_existing_task_list_auto_cleared_and_new_created(self):
        """When historical task list exists, add_tasks auto-clears old list and creates new list"""
        tool = _make_tool()
        agent = _make_agent(old_task_list_id="old_list_001")
        tlm = _make_task_list_manager(existing=True, delete_success=True)

        result = tool._handle_add_tasks(
            args={
                "tasks_info": _make_task_info(),
                "main_goal": "New goal",
            },
            task_list_manager=tlm,
            agent_id="test_agent",
            is_main_agent=True,
            agent=agent,
        )

        assert result["success"] is True
        # Old list deleted
        tlm.delete_task_list.assert_called_once_with("old_list_001", True)
        # New list created
        tlm.create_task_list.assert_called_once()
        # Tasks added
        tlm.add_tasks.assert_called_once()
        # Residual state on Agent cleared
        agent.delete_user_data.assert_any_call("__running_task_id__")

    def test_no_existing_task_list_does_not_delete(self):
        """When no historical task list exists, delete_task_list is not called"""
        tool = _make_tool()
        agent = _make_agent(old_task_list_id=None)
        tlm = _make_task_list_manager(existing=False)

        result = tool._handle_add_tasks(
            args={
                "tasks_info": _make_task_info(),
                "main_goal": "New goal",
            },
            task_list_manager=tlm,
            agent_id="test_agent",
            is_main_agent=True,
            agent=agent,
        )

        assert result["success"] is True
        tlm.delete_task_list.assert_not_called()
        tlm.create_task_list.assert_called_once()

    def test_sub_agent_cannot_auto_clear(self):
        """Sub-Agent has no authority to auto-clear historical task lists, returns failure"""
        tool = _make_tool()
        agent = _make_agent(old_task_list_id="old_list_001", is_sub_agent=True)
        tlm = _make_task_list_manager(existing=True)

        result = tool._handle_add_tasks(
            args={
                "tasks_info": _make_task_info(),
                "main_goal": "New goal",
            },
            task_list_manager=tlm,
            agent_id="test_agent",
            is_main_agent=False,
            agent=agent,
        )

        assert result["success"] is False
        assert "no right to auto-clear" in result["stderr"].lower()
        # Not deleted, no new list created
        tlm.delete_task_list.assert_not_called()
        tlm.create_task_list.assert_not_called()

    def test_delete_failure_returns_error(self):
        """Returns error when deleting historical task list fails, does not create new list"""
        tool = _make_tool()
        agent = _make_agent(old_task_list_id="old_list_001")
        tlm = _make_task_list_manager(existing=True, delete_success=False)

        result = tool._handle_add_tasks(
            args={
                "tasks_info": _make_task_info(),
                "main_goal": "New goal",
            },
            task_list_manager=tlm,
            agent_id="test_agent",
            is_main_agent=True,
            agent=agent,
        )

        assert result["success"] is False
        assert "Failed to auto-clear the historical task list" in result["stderr"]
        tlm.create_task_list.assert_not_called()
