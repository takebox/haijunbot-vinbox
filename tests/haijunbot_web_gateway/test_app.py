# -*- coding: utf-8 -*-
"""haijunbot_web_gateway app API tests."""

import json
import os

# Must set environment variables before importing haijunbot modules to avoid triggering interactive configuration
os.environ["HAIJUNBOT_SKIP_INTERACTIVE_CONFIG"] = "1"

from datetime import datetime
from datetime import timedelta
from unittest.mock import Mock
from fastapi.testclient import TestClient

from haijunbot.haijunbot_gateway.events import GatewayOutputEvent
from haijunbot.haijunbot_gateway.output_bridge import SessionOutputRouter
from haijunbot.haijunbot_utils.output import OutputType
from haijunbot.haijunbot_web_gateway.app import MAX_FILE_SIZE_BYTES
from haijunbot.haijunbot_web_gateway.app import _fuzzy_match_score
from haijunbot.haijunbot_web_gateway.app import WebGateway
from haijunbot.haijunbot_web_gateway.app import create_app
from haijunbot.haijunbot_web_gateway.timer_manager import TimerManager


# Authentication Token for testing
TEST_AUTH_TOKEN = "test-token-for-unit-tests"
os.environ["HAIJUNBOT_AUTH_TOKEN"] = TEST_AUTH_TOKEN


def create_test_client() -> TestClient:
    app = create_app()
    return TestClient(app)


def _cleanup_timer_persistence() -> None:
    persistence_file = TimerManager.PERSISTENCE_FILE
    if persistence_file.exists():
        persistence_file.unlink()


def get_auth_headers():
    """Get authentication headers"""
    return {"Authorization": f"Bearer {TEST_AUTH_TOKEN}"}


def test_session_output_router_drops_messages_without_subscribers():
    """When there are no subscribers, the router should not cache or delay-replay messages"""
    router = SessionOutputRouter()

    session_a_message = {"type": "output", "payload": {"text": "from-a"}}
    session_b_message = {"type": "output", "payload": {"text": "from-b"}}

    sender_a = Mock()
    sender_b = Mock()

    router.publish(session_a_message, session_id="session-a")
    router.publish(session_b_message, session_id="session-b")

    router.register("conn-a", sender_a, session_id="session-a")
    router.register("conn-b", sender_b, session_id="session-b")

    sender_a.assert_not_called()
    sender_b.assert_not_called()


def test_session_output_router_routes_only_to_registered_session():
    """When subscribers are registered, messages are only sent to the sender of the corresponding session"""
    router = SessionOutputRouter()

    session_a_message = {"type": "output", "payload": {"text": "from-a"}}
    session_b_message = {"type": "output", "payload": {"text": "from-b"}}

    sender_a = Mock()
    sender_b = Mock()
    router.register("conn-a", sender_a, session_id="session-a")
    router.register("conn-b", sender_b, session_id="session-b")

    router.publish(session_a_message, session_id="session-a")
    router.publish(session_b_message, session_id="session-b")

    sender_a.assert_called_once_with(session_a_message)
    sender_b.assert_called_once_with(session_b_message)


def test_web_gateway_emit_output_promotes_agent_id_to_payload():
    """Primary connection output messages should carry agent_id at the top level of payload for accurate frontend attribution"""
    router = SessionOutputRouter()
    input_registry = Mock()
    terminal_input_registry = Mock()
    auth_store = {"default": {"token": "test-token"}}
    gateway = WebGateway(router, input_registry, auth_store, terminal_input_registry)
    gateway._check_auth = Mock(return_value=(True, None))

    sender = Mock()
    router.register("conn-1", sender, session_id="default")

    event = GatewayOutputEvent(
        output_type=OutputType.INFO,
        text="hello",
        timestamp="12:00:00",
        context={"agent_id": "agent-123", "agent_name": "Agent 123"},
    )

    gateway.emit_output(event)

    sender.assert_called_once()
    message = sender.call_args[0][0]
    assert message["type"] == "output"
    assert message["payload"]["agent_id"] == "agent-123"
    assert message["payload"]["context"]["agent_id"] == "agent-123"


def test_create_app_attaches_timer_manager_to_app_state():
    _cleanup_timer_persistence()
    app = create_app()
    timer_manager = app.state.timer_manager

    try:
        assert isinstance(timer_manager, TimerManager)
        assert timer_manager.is_shutdown() is False
    finally:
        timer_manager.shutdown()
        _cleanup_timer_persistence()


def test_create_timer_with_capability_call_action(tmp_path):
    """capability_call action should be correctly built and scheduled by _build_timer_action."""
    _cleanup_timer_persistence()
    client = create_test_client()
    headers = get_auth_headers()

    # Create a capability_call timer (delay long enough to avoid triggering during test)
    resp = client.post(
        "/api/timers",
        headers=headers,
        json={
            "schedule": {"delay_seconds": 3600},
            "action": {
                "type": "capability_call",
                "params": {
                    "session_id": "session-1",
                    "capability": "fs.read",
                    "params": {"path": "/tmp"},
                    "timeout": 15,
                    "user_id": "user-1",
                    "is_admin": True,
                },
            },
        },
    )
    body = resp.json()
    assert body["success"] is True, body
    timer_info = body["data"]
    action_meta = timer_info["metadata"]["action"]
    assert action_meta["type"] == "capability_call"
    assert action_meta["params"]["capability"] == "fs.read"
    assert action_meta["params"]["session_id"] == "session-1"
    assert action_meta["params"]["timeout"] == 15.0
    assert action_meta["params"]["is_admin"] is True
    assert action_meta["params"]["params"] == {"path": "/tmp"}

    # Cleanup
    timer_id = timer_info["task_id"]
    resp_del = client.delete(f"/api/timers/{timer_id}", headers=headers)
    assert resp_del.json()["success"] is True
    _cleanup_timer_persistence()


def test_create_timer_with_capability_call_rejects_invalid_params():
    """capability_call action should return INVALID_ARGUMENT when required fields are missing or field types are wrong."""
    _cleanup_timer_persistence()
    client = create_test_client()
    headers = get_auth_headers()

    # Missing session_id
    resp = client.post(
        "/api/timers",
        headers=headers,
        json={
            "schedule": {"delay_seconds": 3600},
            "action": {
                "type": "capability_call",
                "params": {"capability": "fs.read"},
            },
        },
    )
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_ARGUMENT"
    assert "session_id" in body["error"]["message"]

    # Missing capability
    resp = client.post(
        "/api/timers",
        headers=headers,
        json={
            "schedule": {"delay_seconds": 3600},
            "action": {
                "type": "capability_call",
                "params": {"session_id": "session-1"},
            },
        },
    )
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_ARGUMENT"
    assert "capability" in body["error"]["message"]

    # params is not an object
    resp = client.post(
        "/api/timers",
        headers=headers,
        json={
            "schedule": {"delay_seconds": 3600},
            "action": {
                "type": "capability_call",
                "params": {
                    "session_id": "session-1",
                    "capability": "fs.read",
                    "params": "not-an-object",
                },
            },
        },
    )
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_ARGUMENT"

    # timeout is not a number
    resp = client.post(
        "/api/timers",
        headers=headers,
        json={
            "schedule": {"delay_seconds": 3600},
            "action": {
                "type": "capability_call",
                "params": {
                    "session_id": "session-1",
                    "capability": "fs.read",
                    "timeout": "not-a-number",
                },
            },
        },
    )
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_ARGUMENT"

    # Unknown action.type
    resp = client.post(
        "/api/timers",
        headers=headers,
        json={
            "schedule": {"delay_seconds": 3600},
            "action": {"type": "bogus_type", "params": {}},
        },
    )
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_ARGUMENT"

    _cleanup_timer_persistence()


def test_set_node_config_rejects_schema_invalid_config():
    """Configuration should be validated against config_schema.json before saving; invalid configurations must not be written."""
    client = create_test_client()
    headers = get_auth_headers()

    # Invalid config: mcp should be an array, given as string
    resp = client.post(
        "/api/nodes/nonexistent-node/config",
        headers=headers,
        json={
            "config_sections": ["mcp"],
            "config_data": {"mcp": "not-an-array"},
        },
    )
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "CONFIG_SCHEMA_VALIDATION_FAILED"
    assert any(e["path"] == "mcp" for e in body["error"]["details"])

    # Valid config should pass validation (here returns NODE_NOT_FOUND because the node doesn't exist, not a validation failure)
    resp2 = client.post(
        "/api/nodes/nonexistent-node/config",
        headers=headers,
        json={
            "config_sections": ["llm_group"],
            "config_data": {"llm_group": "qwen3"},
        },
    )
    body2 = resp2.json()
    assert body2["success"] is False
    assert body2["error"]["code"] == "NODE_NOT_FOUND"


def test_fuzzy_match_score_prefers_contiguous():
    """Contiguous matches should score better than scattered matches."""
    assert _fuzzy_match_score("mod", "mod.rs") is not None
    contiguous = _fuzzy_match_score("mod", "mod.rs")
    scattered = _fuzzy_match_score("mod", "m_x_o_y_d.rs")
    assert contiguous is not None and scattered is not None
    assert contiguous < scattered


def test_fuzzy_match_score_rejects_non_subsequence():
    """Non-subsequences should return None."""
    assert _fuzzy_match_score("xyz", "sche/mod.rs") is None


def test_file_search_matches_directory_path():
    """File search should support fuzzy matching on 'directory + filename' (e.g. scmodrs -> sche/mod.rs)."""
    query = "scmodrs"

    def match_score(relative_path: str) -> int | None:
        name = relative_path.rsplit("/", 1)[-1]
        name_score = _fuzzy_match_score(query, name)
        path_score = _fuzzy_match_score(query, relative_path)
        candidates = [s for s in (name_score, path_score) if s is not None]
        return min(candidates) if candidates else None

    # Directory path match: filename alone mod.rs cannot match scmodrs, but the full path can
    assert _fuzzy_match_score(query, "mod.rs") is None
    assert match_score("sche/mod.rs") is not None
    # Filename match should not be degraded by path matching: take min to ensure it's no worse than filename-only match
    assert match_score("mod.rs") == _fuzzy_match_score(query, "mod.rs") or (
        match_score("mod.rs") is None
    )


def test_create_timer_with_cron_schedule():
    """schedule.cron should be able to create a cron recurring timer."""
    _cleanup_timer_persistence()
    client = create_test_client()
    headers = get_auth_headers()

    resp = client.post(
        "/api/timers",
        headers=headers,
        json={
            "schedule": {"cron": "0 9 * * 1"},
            "action": {
                "type": "run_shell_command",
                "params": {"command": "echo hi", "working_dir": "/tmp"},
            },
        },
    )
    body = resp.json()
    assert body["success"] is True, body
    timer_info = body["data"]
    assert timer_info["is_recurring"] is True
    assert timer_info["cron_expr"] == "0 9 * * 1"
    schedule_meta = timer_info["metadata"]["schedule"]
    assert schedule_meta["type"] == "cron"
    assert schedule_meta["cron"] == "0 9 * * 1"
    # First trigger is next Monday at 9:00
    next_run = datetime.fromisoformat(timer_info["run_at"])
    assert next_run.hour == 9 and next_run.minute == 0
    assert next_run.weekday() == 0  # Monday

    # Cleanup
    timer_id = timer_info["task_id"]
    resp_del = client.delete(f"/api/timers/{timer_id}", headers=headers)
    assert resp_del.json()["success"] is True
    _cleanup_timer_persistence()


def test_create_timer_with_invalid_cron_rejected():
    """Invalid cron expressions should return INVALID_ARGUMENT."""
    _cleanup_timer_persistence()
    client = create_test_client()
    headers = get_auth_headers()

    resp = client.post(
        "/api/timers",
        headers=headers,
        json={
            "schedule": {"cron": "not a valid cron"},
            "action": {
                "type": "run_shell_command",
                "params": {"command": "echo hi", "working_dir": "/tmp"},
            },
        },
    )
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_ARGUMENT"
    assert "cron" in body["error"]["message"]
    _cleanup_timer_persistence()


def test_create_timer_schedule_requires_exactly_one_field():
    """schedule must have exactly one of four options (run_at/delay_seconds/interval_seconds/cron); specifying multiple should raise an error."""
    _cleanup_timer_persistence()
    client = create_test_client()
    headers = get_auth_headers()

    # Both cron and delay_seconds provided -> error
    resp = client.post(
        "/api/timers",
        headers=headers,
        json={
            "schedule": {"cron": "0 9 * * 1", "delay_seconds": 10},
            "action": {
                "type": "run_shell_command",
                "params": {"command": "echo hi", "working_dir": "/tmp"},
            },
        },
    )
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_ARGUMENT"
    assert "Exactly one" in body["error"]["message"]
    _cleanup_timer_persistence()
