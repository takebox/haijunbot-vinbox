# -*- coding: utf-8 -*-
"""Audit system tests: configurable, disabled by default, JSONL output, sensitive data redaction."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from haijunbot.haijunbot_audit.audit import AuditLogger
from haijunbot.haijunbot_audit.audit import _redact
from haijunbot.haijunbot_audit.audit import log_event
from haijunbot.haijunbot_utils.config import set_global_config_data


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset global config before each test to ensure audit is disabled by default."""
    set_global_config_data({})
    yield
    set_global_config_data({})


def _audit_dir(tmp_path: Path) -> Path:
    return tmp_path / "audit"


def _read_lines(tmp_path: Path) -> list:
    audit_dir = _audit_dir(tmp_path)
    files = list(audit_dir.glob("*.jsonl"))
    records = []
    for f in files:
        for line in f.read_text(encoding="utf-8").strip().splitlines():
            if line:
                records.append(json.loads(line))
    return records


def test_log_event_disabled_writes_nothing(tmp_path, monkeypatch):
    """When disabled by default, log_event does not write any log files."""
    # Force default disabled state and inject a logger pointing to temp directory
    monkeypatch.setattr("haijunbot.haijunbot_audit.audit.is_enable_audit", lambda: False)
    monkeypatch.setattr("haijunbot.haijunbot_audit.audit._logger", AuditLogger(str(tmp_path)))
    log_event("user_input", user_input="hello")
    assert not _audit_dir(tmp_path).exists() or not list(
        _audit_dir(tmp_path).glob("*.jsonl")
    )


def test_log_event_enabled_writes_jsonl(tmp_path, monkeypatch):
    """When enabled, log_event writes JSONL with complete fields."""
    monkeypatch.setattr("haijunbot.haijunbot_audit.audit.is_enable_audit", lambda: True)
    monkeypatch.setattr("haijunbot.haijunbot_audit.audit._logger", AuditLogger(str(tmp_path)))
    log_event("user_input", user_input="write code for me")
    records = _read_lines(tmp_path)
    assert len(records) == 1
    rec = records[0]
    assert rec["event_type"] == "user_input"
    assert "timestamp" in rec
    assert rec["data"]["user_input"] == "write code for me"


def test_redact_sensitive_fields(tmp_path, monkeypatch):
    """Sensitive field values are redacted to ***."""
    monkeypatch.setattr("haijunbot.haijunbot_audit.audit.is_enable_audit", lambda: True)
    logger = AuditLogger(str(tmp_path))
    logger.log(
        "tool_call",
        tool_name="execute_script",
        arguments={"password": "secret123", "token": "abc", "cmd": "ls"},
    )
    records = _read_lines(tmp_path)
    data = records[0]["data"]["arguments"]
    assert data["password"] == "***"
    assert data["token"] == "***"
    assert data["cmd"] == "ls"


def test_redact_nested_dict():
    """Recursive redaction: sensitive keys' entire values (including nested dicts) are redacted to ***."""
    result = _redact(
        {
            "auth": {"api_key": "k1"},
            "args": {"username": "u", "secret": "s"},
            "safe": "ok",
        }
    )
    # auth is a sensitive key, entire value (including nested api_key) is redacted
    assert result["auth"] == "***"
    assert result["args"]["secret"] == "***"
    assert result["args"]["username"] == "u"
    assert result["safe"] == "ok"


def test_event_types_all_recorded(tmp_path, monkeypatch):
    """user_input / tool_call / task_completed event types can all be recorded."""
    monkeypatch.setattr("haijunbot.haijunbot_audit.audit.is_enable_audit", lambda: True)
    logger = AuditLogger(str(tmp_path))
    logger.log("user_input", user_input="hi")
    logger.log("tool_call", tool_name="read_code")
    logger.log("task_completed", auto_completed=True, result="done")
    types = [r["event_type"] for r in _read_lines(tmp_path)]
    assert types == ["user_input", "tool_call", "task_completed"]


def test_daily_file_partition(tmp_path, monkeypatch):
    """Daily file partitioning: filename is YYYY-MM-DD.jsonl."""
    monkeypatch.setattr("haijunbot.haijunbot_audit.audit.is_enable_audit", lambda: True)
    logger = AuditLogger(str(tmp_path))
    logger.log("user_input", user_input="x")
    expected = f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    files = list(_audit_dir(tmp_path).glob("*.jsonl"))
    assert [f.name for f in files] == [expected]


def test_redact_compound_sensitive_keys():
    """Substring matching: compound sensitive keys like api_key / access_token / secret_key are also redacted."""
    result = _redact(
        {
            "api_key": "k1",
            "access_token": "t1",
            "secret_key": "s1",
            "client_secret": "c1",
            "auth_token": "a1",
            "username": "u1",
            "api_base": "https://x",
        }
    )
    assert result["api_key"] == "***"
    assert result["access_token"] == "***"
    assert result["secret_key"] == "***"
    assert result["client_secret"] == "***"
    assert result["auth_token"] == "***"
    assert result["username"] == "u1"
    assert result["api_base"] == "https://x"


def test_redact_compound_nested_dict():
    """Compound sensitive keys in nested dicts are also redacted."""
    result = _redact({"args": {"api_key": "k", "model": "gpt"}})
    assert result["args"]["api_key"] == "***"
    assert result["args"]["model"] == "gpt"


def test_call_tools_audit_no_leak(tmp_path, monkeypatch):
    """Text protocol tool_call audit: does not record raw response, arguments are redacted with no sensitive plaintext."""
    from haijunbot.haijunbot_agent import Agent
    import haijunbot.haijunbot_audit.audit as audit_mod
    from haijunbot.haijunbot_audit.audit import AuditLogger

    # Control both switches: _is_audit_enabled (reads config) and log_event (reads audit)
    monkeypatch.setattr("haijunbot.haijunbot_utils.config.is_enable_audit", lambda: True)
    monkeypatch.setattr("haijunbot.haijunbot_audit.audit.is_enable_audit", lambda: True)
    monkeypatch.setattr(
        "haijunbot.haijunbot_agent.execute_tool_call", lambda *a, **k: (True, "ok")
    )
    audit_mod._logger = AuditLogger(str(tmp_path))

    agent = object.__new__(Agent)
    resp = '{"name": "execute_script", "arguments": {"api_key": "sk-123", "cmd": "ls"}}'
    agent._call_tools(resp)

    records = _read_lines(tmp_path)
    assert len(records) == 1
    data = records[0]["data"]
    # Do not record raw response string to avoid leaking sensitive plaintext
    assert "response" not in data
    assert data["tool_name"] == "execute_script"
    assert data["arguments"]["api_key"] == "***"
    assert data["arguments"]["cmd"] == "ls"
    # The entire serialized audit record must not contain sensitive plaintext
    assert "sk-123" not in json.dumps(records)


def test_call_tools_disabled_no_parse(tmp_path, monkeypatch):
    """When disabled by default, _call_tools does not parse response, maintaining zero overhead."""
    from haijunbot.haijunbot_agent import Agent

    monkeypatch.setattr("haijunbot.haijunbot_utils.config.is_enable_audit", lambda: False)
    monkeypatch.setattr("haijunbot.haijunbot_audit.audit.is_enable_audit", lambda: False)
    monkeypatch.setattr(
        "haijunbot.haijunbot_agent.execute_tool_call", lambda *a, **k: (True, "ok")
    )

    agent = object.__new__(Agent)
    # If _extract_tool_arguments were called while disabled, it would raise due to invalid JSON response; verify it is not triggered
    agent._call_tools("not valid json {{{")
    assert not _audit_dir(tmp_path).exists() or not list(
        _audit_dir(tmp_path).glob("*.jsonl")
    )
