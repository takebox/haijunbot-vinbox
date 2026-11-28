# -*- coding: utf-8 -*-
"""daemon three-piece set (sessions / capabilities / call) tests.

Guarantee:
1. daemon_sessions passes through sessions returned by gateway (including system_info) -- this is the basis for
   Agent to determine "the machine environment where the daemon resides and what capabilities are available", must not be trimmed by fields.
2. daemon_capabilities reads capability list for specified session from /api/daemon/capability/list.
3. daemon_call passes capability name through to /api/daemon/capability/call, and parses result envelope.

Isolation: No real network requests; directly replaces ``_request_gateway`` returning constructed gateway responses.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from haijunbot.haijunbot_tools.daemon_sessions import DaemonSessionsTool
from haijunbot.haijunbot_tools.daemon_capabilities import DaemonCapabilitiesTool
from haijunbot.haijunbot_tools.daemon_call import DaemonCallTool


@pytest.fixture
def sessions_tool(monkeypatch):
    """Construct DaemonSessionsTool, bypass master_url validation and real network requests."""
    from haijunbot.haijunbot_tools import daemon_sessions as module

    monkeypatch.setattr(module.jglobals, "master_url", "http://127.0.0.1:1")
    return DaemonSessionsTool()


@pytest.fixture
def capabilities_tool(monkeypatch):
    """Construct DaemonCapabilitiesTool, bypass master_url validation and real network requests."""
    from haijunbot.haijunbot_tools import daemon_capabilities as module

    monkeypatch.setattr(module.jglobals, "master_url", "http://127.0.0.1:1")
    return DaemonCapabilitiesTool()


@pytest.fixture
def call_tool(monkeypatch):
    """Construct DaemonCallTool, bypass master_url validation and real network requests."""
    from haijunbot.haijunbot_tools import daemon_call as module

    monkeypatch.setattr(module.jglobals, "master_url", "http://127.0.0.1:1")
    return DaemonCallTool()


# ---------------- daemon_sessions ----------------


def test_sessions_passes_through_system_info(sessions_tool, monkeypatch):
    """daemon_sessions' stdout must include system_info returned by gateway."""
    system_info = {
        "hostname": "test-host",
        "os_name": "Ubuntu",
        "os_version": "24.04",
        "arch": "amd64",
        "cpu_count": 8,
        "mem_total_kb": 16000000,
        "user": "tester",
    }
    gateway_response = {
        "success": True,
        "data": {
            "success": True,
            "sessions": [
                {
                    "session_id": "sess-1",
                    "client_id": "daemon-test-host-1",
                    "node_id": "daemon-test-host-1",
                    "hostname": "test-host",
                    "platform": "Ubuntu",
                    "system_info": system_info,
                    "daemon_version": "0.0.1",
                    "capabilities": [],
                    "connected_at": 1.0,
                }
            ],
        },
    }
    monkeypatch.setattr(
        sessions_tool, "_request_gateway", lambda *a, **kw: gateway_response
    )

    result = sessions_tool.execute()
    assert result["success"] is True
    payload = json.loads(result["stdout"])
    assert len(payload) == 1
    assert payload[0]["system_info"] == system_info
    assert payload[0]["session_id"] == "sess-1"


def test_sessions_empty_returns_hint(sessions_tool, monkeypatch):
    """Returns hint text when no sessions, no error."""
    monkeypatch.setattr(
        sessions_tool,
        "_request_gateway",
        lambda *a, **kw: {"success": True, "data": {"success": True, "sessions": []}},
    )
    result = sessions_tool.execute()
    assert result["success"] is True
    assert "no online daemon sessions" in result["stdout"].lower()


# ---------------- daemon_capabilities ----------------


def test_capabilities_reads_session_capabilities(capabilities_tool, monkeypatch):
    """daemon_capabilities reads capability list for specified session from /api/daemon/capability/list."""
    capabilities = [
        {
            "name": "fs.read",
            "description": "Read file",
            "parameters": {},
            "platform": "windows",
        },
        {
            "name": "system.info",
            "description": "System information",
            "parameters": {},
            "platform": "windows",
        },
    ]
    captured = {}

    def fake_request_gateway(method, path, json_data=None, **kw):
        captured["method"] = method
        captured["path"] = path
        captured["json_data"] = json_data
        return {
            "success": True,
            "data": {
                "success": True,
                "result": {"success": True, "capabilities": capabilities},
            },
        }

    monkeypatch.setattr(capabilities_tool, "_request_gateway", fake_request_gateway)
    result = capabilities_tool.execute(session_id="sess-1")
    assert result["success"] is True
    payload = json.loads(result["stdout"])
    assert payload == capabilities
    assert captured["method"] == "POST"
    assert captured["path"] == "/api/daemon/capability/list"
    assert captured["json_data"]["session_id"] == "sess-1"


def test_capabilities_empty_returns_hint(capabilities_tool, monkeypatch):
    """Returns hint when session has no capabilities, no error."""
    monkeypatch.setattr(
        capabilities_tool,
        "_request_gateway",
        lambda *a, **kw: {
            "success": True,
            "data": {"success": True, "result": {"success": True, "capabilities": []}},
        },
    )
    result = capabilities_tool.execute(session_id="sess-1")
    assert result["success"] is True
    assert "has not registered any capabilities" in result["stdout"]


def test_capabilities_requires_session_id(capabilities_tool, monkeypatch):
    """Reports error when session_id is missing."""
    result = capabilities_tool.execute()
    assert result["success"] is False
    assert "session_id is required" in result["stderr"]


# ---------------- daemon_call ----------------


def test_call_passes_name_and_params(call_tool, monkeypatch):
    """daemon_call passes capability name through to /api/daemon/capability/call and parses result envelope."""
    captured = {}

    def fake_request_gateway(method, path, json_data=None, **kw):
        captured["method"] = method
        captured["path"] = path
        captured["json_data"] = json_data
        return {
            "success": True,
            "data": {
                "success": True,
                "result": {"success": True, "data": {"content": "hello"}},
            },
        }

    monkeypatch.setattr(call_tool, "_request_gateway", fake_request_gateway)
    result = call_tool.execute(
        session_id="sess-1",
        name="fs.read",
        params={"path": "/tmp/a.txt"},
    )
    assert result["success"] is True
    payload = json.loads(result["stdout"])
    assert payload == {"content": "hello"}
    assert captured["method"] == "POST"
    assert captured["path"] == "/api/daemon/capability/call"
    assert captured["json_data"] == {
        "session_id": "sess-1",
        "name": "fs.read",
        "params": {"path": "/tmp/a.txt"},
        "timeout": 30.0,
    }


def test_call_requires_name(call_tool, monkeypatch):
    """Reports error when daemon_call is missing name."""
    result = call_tool.execute(session_id="sess-1")
    assert result["success"] is False
    assert "name is required" in result["stderr"]


def test_call_requires_session_id(call_tool, monkeypatch):
    """Reports error when daemon_call is missing session_id."""
    result = call_tool.execute(name="fs.read")
    assert result["success"] is False
    assert "session_id is required" in result["stderr"]


def test_call_params_must_be_object(call_tool, monkeypatch):
    """Reports error when daemon_call's params is not an object."""
    result = call_tool.execute(session_id="sess-1", name="fs.read", params="bad")
    assert result["success"] is False
    assert "params must be an object" in result["stderr"]


def test_call_daemon_reports_failure(call_tool, monkeypatch):
    """Passes through error when daemon side returns failure."""
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
    result = call_tool.execute(session_id="sess-1", name="fs.read")
    assert result["success"] is False
    assert "boom" in result["stderr"]


# ---------------- Tool name/registration contract ----------------


def test_tool_names_match_modules():
    """Three tool classes' name must equal their respective module names (registry's item.name == module_name contract)."""
    assert DaemonSessionsTool.name == "daemon_sessions"
    assert DaemonCapabilitiesTool.name == "daemon_capabilities"
    assert DaemonCallTool.name == "daemon_call"
