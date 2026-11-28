# -*- coding: utf-8 -*-
"""browser_ext three-piece set (sessions / capabilities / call) tests.

Guarantee: After the tool layer is split into three independent tools (no action parameter, tool name is the operation),
the normal and error paths of the three tools must be correct:
- browser_ext_sessions: passes through sessions returned by gateway (including capabilities)
- browser_ext_capabilities: reads capability list for specified session from sessions
- browser_ext_call: passes capability name (name) as action through to /api/browser-ext/command, and parses result envelope

Isolation: No real network requests; directly replaces ``_request_gateway`` returning constructed gateway responses.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from haijunbot.haijunbot_tools.browser_ext_sessions import BrowserExtSessionsTool
from haijunbot.haijunbot_tools.browser_ext_capabilities import BrowserExtCapabilitiesTool
from haijunbot.haijunbot_tools.browser_ext_call import BrowserExtCallTool


@pytest.fixture
def sessions_tool(monkeypatch):
    """Construct BrowserExtSessionsTool, bypass master_url validation and real network requests."""
    from haijunbot.haijunbot_tools import browser_ext_sessions as module

    monkeypatch.setattr(module.jglobals, "master_url", "http://127.0.0.1:1")
    return BrowserExtSessionsTool()


@pytest.fixture
def capabilities_tool(monkeypatch):
    """Construct BrowserExtCapabilitiesTool, bypass master_url validation and real network requests."""
    from haijunbot.haijunbot_tools import browser_ext_capabilities as module

    monkeypatch.setattr(module.jglobals, "master_url", "http://127.0.0.1:1")
    return BrowserExtCapabilitiesTool()


@pytest.fixture
def call_tool(monkeypatch):
    """Construct BrowserExtCallTool, bypass master_url validation and real network requests."""
    from haijunbot.haijunbot_tools import browser_ext_call as module

    monkeypatch.setattr(module.jglobals, "master_url", "http://127.0.0.1:1")
    return BrowserExtCallTool()


def _sessions_response(sessions):
    return {"success": True, "data": {"success": True, "sessions": sessions}}


# ---------------- browser_ext_sessions ----------------


def test_sessions_passes_through_sessions(sessions_tool, monkeypatch):
    """browser_ext_sessions' stdout must include sessions returned by gateway (including capabilities)."""
    capabilities = [
        {
            "name": "tab.list",
            "description": "List tabs",
            "parameters": {},
            "platform": "browser",
        }
    ]
    gateway_response = _sessions_response(
        [
            {
                "session_id": "sess-1",
                "name": "Chrome Extension",
                "browser_info": {"name": "Chrome", "version": "120"},
                "capabilities": capabilities,
            }
        ]
    )
    monkeypatch.setattr(
        sessions_tool, "_request_gateway", lambda *a, **kw: gateway_response
    )

    result = sessions_tool.execute()
    assert result["success"] is True
    payload = json.loads(result["stdout"])
    assert len(payload) == 1
    assert payload[0]["session_id"] == "sess-1"
    assert payload[0]["capabilities"] == capabilities


def test_sessions_empty_returns_hint(sessions_tool, monkeypatch):
    """Returns hint text when no sessions, no error."""
    monkeypatch.setattr(
        sessions_tool, "_request_gateway", lambda *a, **kw: _sessions_response([])
    )
    result = sessions_tool.execute()
    assert result["success"] is True
    assert "no online browser extension sessions" in result["stdout"].lower()


# ---------------- browser_ext_capabilities ----------------


def test_capabilities_reads_session_capabilities(capabilities_tool, monkeypatch):
    """browser_ext_capabilities reads capability list for specified session from sessions."""
    capabilities = [
        {
            "name": "dom.click",
            "description": "Click element",
            "parameters": {},
            "platform": "browser",
        },
        {
            "name": "tab.create",
            "description": "Create new tab",
            "parameters": {},
            "platform": "browser",
        },
    ]
    monkeypatch.setattr(
        capabilities_tool,
        "_request_gateway",
        lambda *a, **kw: _sessions_response(
            [
                {"session_id": "sess-1", "capabilities": capabilities},
                {"session_id": "sess-2", "capabilities": []},
            ]
        ),
    )
    result = capabilities_tool.execute(session_id="sess-1")
    assert result["success"] is True
    payload = json.loads(result["stdout"])
    assert payload == capabilities


def test_capabilities_session_not_found(capabilities_tool, monkeypatch):
    """Reports error when specified session does not exist."""
    monkeypatch.setattr(
        capabilities_tool,
        "_request_gateway",
        lambda *a, **kw: _sessions_response(
            [{"session_id": "sess-1", "capabilities": []}]
        ),
    )
    result = capabilities_tool.execute(session_id="nope")
    assert result["success"] is False
    assert "session not found" in result["stderr"]


def test_capabilities_empty_returns_hint(capabilities_tool, monkeypatch):
    """Returns hint when session has no capabilities, no error."""
    monkeypatch.setattr(
        capabilities_tool,
        "_request_gateway",
        lambda *a, **kw: _sessions_response(
            [{"session_id": "sess-1", "capabilities": []}]
        ),
    )
    result = capabilities_tool.execute(session_id="sess-1")
    assert result["success"] is True
    assert "has not reported any capabilities" in result["stdout"]


def test_capabilities_requires_session_id(capabilities_tool, monkeypatch):
    """Reports error when session_id is missing."""
    result = capabilities_tool.execute()
    assert result["success"] is False
    assert "session_id is required" in result["stderr"]


# ---------------- browser_ext_call ----------------


def test_call_passes_name_and_params(call_tool, monkeypatch):
    """browser_ext_call passes capability name as action and parses result envelope."""
    captured = {}

    def fake_request_gateway(method, path, json_data=None, **kw):
        captured["method"] = method
        captured["path"] = path
        captured["json_data"] = json_data
        return {
            "success": True,
            "data": {
                "success": True,
                "result": {"success": True, "data": {"title": "Example Page"}},
            },
        }

    monkeypatch.setattr(call_tool, "_request_gateway", fake_request_gateway)
    result = call_tool.execute(
        session_id="sess-1",
        name="page.get_info",
        params={"tab_id": 3},
    )
    assert result["success"] is True
    payload = json.loads(result["stdout"])
    assert payload == {"title": "Example Page"}
    assert captured["method"] == "POST"
    assert captured["path"] == "/api/browser-ext/command"
    assert captured["json_data"] == {
        "session_id": "sess-1",
        "action": "page.get_info",
        "params": {"tab_id": 3},
        "timeout": 15.0,
    }


def test_call_requires_name(call_tool, monkeypatch):
    """Reports error when name is missing for browser_ext_call."""
    result = call_tool.execute(session_id="sess-1")
    assert result["success"] is False
    assert "name is required" in result["stderr"]


def test_call_requires_session_id(call_tool, monkeypatch):
    """Reports error when session_id is missing for browser_ext_call."""
    result = call_tool.execute(name="tab.list")
    assert result["success"] is False
    assert "session_id is required" in result["stderr"]


def test_call_params_must_be_object(call_tool, monkeypatch):
    """Reports error when browser_ext_call's params is not an object."""
    result = call_tool.execute(session_id="sess-1", name="tab.list", params="bad")
    assert result["success"] is False
    assert "params must be an object" in result["stderr"]


def test_call_extension_reports_failure(call_tool, monkeypatch):
    """Passes through error when extension side returns failure."""
    monkeypatch.setattr(
        call_tool,
        "_request_gateway",
        lambda *a, **kw: {
            "success": True,
            "data": {
                "success": True,
                "result": {"success": False, "error": "EXEC_ERROR: boom"},
            },
        },
    )
    result = call_tool.execute(session_id="sess-1", name="tab.list")
    assert result["success"] is False
    assert "boom" in result["stderr"]


# ---------------- Tool name/registration contract ----------------


def test_tool_names_match_modules():
    """Three tool classes' name must equal their respective module names (registry's item.name == module_name contract)."""
    assert BrowserExtSessionsTool.name == "browser_ext_sessions"
    assert BrowserExtCapabilitiesTool.name == "browser_ext_capabilities"
    assert BrowserExtCallTool.name == "browser_ext_call"
