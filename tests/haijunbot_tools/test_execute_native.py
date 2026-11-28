# -*- coding: utf-8 -*-
"""ToolRegistry.execute_native_tool_call unit tests"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from haijunbot.haijunbot_tools.registry import ToolRegistry


def _fake_agent():
    ag = MagicMock()
    ag.model = None
    ag.set_user_data = MagicMock()
    ag.get_user_data = MagicMock(return_value=[])
    return ag


def test_execute_native_success(monkeypatch):
    reg = ToolRegistry()

    def fake_execute(name, args, agent=None):
        assert name == "read_code"
        assert args == {"path": "a.py"}
        return {"success": True, "stdout": "file content", "stderr": ""}

    monkeypatch.setattr(reg, "execute_tool", fake_execute)
    agent = _fake_agent()
    out = reg.execute_native_tool_call("read_code", {"path": "a.py"}, agent)
    assert "file content" in out
    agent.set_user_data.assert_called()
    # Record the last executed tool
    calls = [c.args[0] for c in agent.set_user_data.call_args_list]
    assert "__last_executed_tool__" in calls


def test_execute_native_failure_returns_error(monkeypatch):
    reg = ToolRegistry()

    def fake_execute(name, args, agent=None):
        return {"success": False, "stdout": "", "stderr": "boom"}

    monkeypatch.setattr(reg, "execute_tool", fake_execute)
    agent = _fake_agent()
    out = reg.execute_native_tool_call("read_code", {"path": "a.py"}, agent)
    assert "boom" in out


def test_execute_native_strips_and_executes_want(monkeypatch):
    reg = ToolRegistry()
    captured = {}

    def fake_execute(name, args, agent=None):
        captured["args"] = args
        return {"success": True, "stdout": "ok", "stderr": ""}

    monkeypatch.setattr(reg, "execute_tool", fake_execute)
    agent = _fake_agent()
    out = reg.execute_native_tool_call(
        "read_code", {"path": "a.py", "want": "Look at file content"}, agent
    )
    assert "ok" in out
    # want is only used for prompting, should not be sent to the tool
    assert captured["args"] == {"path": "a.py"}


def test_execute_native_missing_tool_reports_error(monkeypatch):
    reg = ToolRegistry()
    monkeypatch.setattr(
        reg,
        "execute_tool",
        lambda name, args, agent=None: {
            "success": False,
            "stderr": f"Tool {name} does not exist",
            "stdout": "",
        },
    )
    agent = _fake_agent()
    out = reg.execute_native_tool_call("nope", {}, agent)
    assert "does not exist" in out


def test_register_tool_preserves_interactive():
    reg = ToolRegistry()
    reg.register_tool(
        "echo",
        "Echo",
        {"type": "object", "properties": {}},
        lambda arguments: {"success": True, "stdout": "ok", "stderr": ""},
        interactive=True,
    )
    assert reg.get_tool("echo").interactive is True


def test_execute_native_with_after_schedules_timer(monkeypatch):
    from haijunbot.haijunbot_tools import timer as timer_mod

    captured = {}

    def fake_add_task(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(task_id=7)

    monkeypatch.setattr(timer_mod, "get_timer_manager", lambda: SimpleNamespace(add_task=fake_add_task))
    reg = ToolRegistry()

    def no_run(*args, **kwargs):
        raise AssertionError("Scheduled call should not execute the tool immediately")

    monkeypatch.setattr(reg, "execute_tool", no_run)
    agent = _fake_agent()
    out = reg.execute_native_tool_call("read_code", {"path": "a.py", "after": 10}, agent)
    assert "Created scheduled task #7" in out
    assert "after 10 seconds" in out
    assert captured["tool_name"] == "read_code"
    # Scheduled parameter is stripped, should not be sent to the tool
    assert captured["tool_args"] == {"path": "a.py"}
