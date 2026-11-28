# -*- coding: utf-8 -*-
"""registry.execute_tool call regression tests for standalone class tools (browser_ext_* / daemon_*).

Guarantee:
registry.execute_tool's v1.0 branch calls tool.execute(args_to_call) with "positional arguments",
but browser_ext_sessions / daemon_sessions' execute(self, **kwargs) only accepts keyword
arguments, which triggers ``execute() takes 1 positional argument but 2 were given``;
browser_ext_capabilities / daemon_capabilities / browser_ext_call / daemon_call's
execute(self, session_id=None, ...) would mistakenly assign the entire dict to session_id, causing parameter misalignment.

After fix, v1.0 branch prioritizes calling with keyword arguments (tool.execute(**args_to_call)),
falls back to positional arguments on TypeError (for compatibility with Tool base class execute(self, arguments) style).

This test does not make real network requests; directly replaces the tool instance's _request_gateway.
"""

import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from haijunbot.haijunbot_tools.registry import ToolRegistry
from haijunbot.haijunbot_tools.base import Tool
from haijunbot.haijunbot_tools.browser_ext_sessions import BrowserExtSessionsTool
from haijunbot.haijunbot_tools.browser_ext_capabilities import BrowserExtCapabilitiesTool
from haijunbot.haijunbot_tools.browser_ext_call import BrowserExtCallTool
from haijunbot.haijunbot_tools.daemon_sessions import DaemonSessionsTool
from haijunbot.haijunbot_tools.daemon_capabilities import DaemonCapabilitiesTool
from haijunbot.haijunbot_tools.daemon_call import DaemonCallTool


@pytest.fixture
def registry(monkeypatch):
    """Construct an empty registry, manually insert tool instances under test."""
    import haijunbot.haijunbot_utils.globals as jglobals

    monkeypatch.setattr(jglobals, "master_url", "http://127.0.0.1:1")
    reg = ToolRegistry()
    reg.tools.clear()
    reg._all_tools = {}
    return reg


def _install(reg, tool):
    """Register tool into registry following the real registration path.

    Real path (registry.register_tool_by_file) wraps standalone class tools' execute methods into
    Tool base class instances (func=tool.execute), _all_tools stores Tool instances not tool class instances.
    Same wrapping here ensures we go through base.Tool.execute compatibility branch.
    """
    wrapped = Tool(
        name=tool.name,
        description=tool.description,
        parameters=tool.parameters,
        func=tool.execute,
        protocol_version=getattr(tool, "protocol_version", "1.0"),
        interactive=getattr(tool, "interactive", False),
    )
    reg.tools[tool.name] = wrapped
    reg._all_tools[tool.name] = wrapped


def _sessions_gw_response(sessions):
    return {"success": True, "data": {"success": True, "sessions": sessions}}


def test_browser_ext_sessions_via_registry(registry, monkeypatch):
    """registry dispatch layer calling browser_ext_sessions no longer raises TypeError, and passes through sessions."""
    tool = BrowserExtSessionsTool()
    monkeypatch.setattr(
        tool,
        "_request_gateway",
        lambda *a, **kw: _sessions_gw_response(
            [{"session_id": "s1", "name": "SF-PC", "extension_version": "1.2.3"}]
        ),
    )
    _install(registry, tool)
    result = registry.execute_tool("browser_ext_sessions", {})
    assert result["success"] is True
    payload = json.loads(result["stdout"])
    assert payload[0]["session_id"] == "s1"


def test_daemon_sessions_via_registry(registry, monkeypatch):
    """registry dispatch layer calling daemon_sessions no longer raises TypeError, and passes through sessions."""
    tool = DaemonSessionsTool()
    monkeypatch.setattr(
        tool,
        "_request_gateway",
        lambda *a, **kw: _sessions_gw_response(
            [{"session_id": "d1", "hostname": "host-a", "daemon_version": "0.1.0"}]
        ),
    )
    _install(registry, tool)
    result = registry.execute_tool("daemon_sessions", {})
    assert result["success"] is True
    payload = json.loads(result["stdout"])
    assert payload[0]["session_id"] == "d1"


def test_browser_ext_capabilities_session_id_matches(registry, monkeypatch):
    """capabilities' session_id must match correctly, not be overwritten by entire dict."""
    tool = BrowserExtCapabilitiesTool()
    captured = {}

    def fake_gw(method, path, json_data=None, **kw):
        captured["json_data"] = json_data
        return {
            "success": True,
            "data": {
                "success": True,
                "sessions": [
                    {
                        "session_id": "s1",
                        "capabilities": [{"name": "tab.list", "description": "x"}],
                    }
                ],
            },
        }

    monkeypatch.setattr(tool, "_request_gateway", fake_gw)
    _install(registry, tool)
    result = registry.execute_tool("browser_ext_capabilities", {"session_id": "s1"})
    assert result["success"] is True
    payload = json.loads(result["stdout"])
    assert payload[0]["name"] == "tab.list"


def test_daemon_call_session_id_matches(registry, monkeypatch):
    """daemon_call's session_id/name must match and pass through correctly."""
    tool = DaemonCallTool()
    captured = {}

    def fake_gw(method, path, json_data=None, **kw):
        captured["json_data"] = json_data
        return {
            "success": True,
            "data": {
                "success": True,
                "result": {"success": True, "data": {"content": "hello"}},
            },
        }

    monkeypatch.setattr(tool, "_request_gateway", fake_gw)
    _install(registry, tool)
    result = registry.execute_tool(
        "daemon_call", {"session_id": "d1", "name": "fs.read"}
    )
    assert result["success"] is True
    assert captured["json_data"]["session_id"] == "d1"
    assert captured["json_data"]["name"] == "fs.read"


def test_tool_base_class_still_works(registry):
    """Tool base class (execute(self, arguments) positional argument style) still calls normally."""
    calls = []

    def tool_func(args):
        calls.append(args)
        return {"success": True, "stdout": "ok", "stderr": ""}

    base_tool = Tool(
        name="base_tool",
        description="base",
        parameters={"type": "object"},
        func=tool_func,
    )
    _install(registry, base_tool)
    result = registry.execute_tool("base_tool", {"k": "v"})
    assert result["success"] is True
    assert calls and calls[0]["k"] == "v"


def test_tool_names_match_modules():
    """Six standalone class tools' name contracts remain unchanged."""
    assert BrowserExtSessionsTool.name == "browser_ext_sessions"
    assert BrowserExtCapabilitiesTool.name == "browser_ext_capabilities"
    assert BrowserExtCallTool.name == "browser_ext_call"
    assert DaemonSessionsTool.name == "daemon_sessions"
    assert DaemonCapabilitiesTool.name == "daemon_capabilities"
    assert DaemonCallTool.name == "daemon_call"
