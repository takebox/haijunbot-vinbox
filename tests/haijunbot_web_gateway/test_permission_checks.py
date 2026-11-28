# -*- coding: utf-8 -*-
"""Permission/ACL gap fix tests.

Covers:
1. Non-admin users without agent:create permission are denied when creating an Agent (PERMISSION_DENIED)
2. Non-admin users without timer:* permission are denied when creating a timer (PERMISSION_DENIED)
3. Users with the sys-operator group (containing agent:create / timer:*) can create normally
4. Admin users are not affected by permission checks (check_permission auto-passes for admin)
5. Gateway system token (HAIJUNBOT_AUTH_TOKEN) is not affected by permission checks

Depends on conftest.py's isolated_data_dir / auth_token fixtures for data directory isolation.
"""

import os

# Must set environment variables before importing haijunbot modules to avoid triggering interactive configuration
os.environ["HAIJUNBOT_SKIP_INTERACTIVE_CONFIG"] = "1"
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def perm_client_factory():
    """Return a factory: first create a user and assign permission groups, then create a TestClient.

    Users/permissions must be created before create_app(), otherwise the
    UserManager / PermissionManager in-memory state inside the app closure
    will not load the new data.
    """
    from haijunbot.haijunbot_web_gateway.user_manager import UserManager
    from haijunbot.haijunbot_web_gateway.permission_manager import PermissionManager
    from haijunbot.haijunbot_utils.config import get_data_dir
    from haijunbot.haijunbot_web_gateway.app import create_app

    def _make(setup=None):
        data_dir = get_data_dir()
        um = UserManager(data_dir)
        pm = PermissionManager(data_dir)
        pm.set_user_manager(um)
        if setup:
            setup(um, pm)
        return TestClient(create_app()), um, pm

    return _make


def _login(client, username, password):
    resp = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True, body
    token = body["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def _create_user(um, username, password):
    um.create_user(username, password)
    return um.get_user_by_username(username)


def _timer_payload():
    return {
        "schedule": {"delay_seconds": 3600},
        "action": {
            "type": "run_shell_command",
            "params": {
                "command": "echo hi",
                "working_dir": "/tmp",
                "interpreter": "bash",
            },
        },
    }


def _agent_payload():
    return {"agent_type": "code", "working_dir": "/tmp"}


# ---------------------------------------------------------------------------
# Users without permission are denied
# ---------------------------------------------------------------------------
def test_no_permission_user_cannot_create_agent(perm_client_factory, monkeypatch):
    """Non-admin users without agent:create permission should be denied when creating an Agent."""
    monkeypatch.setenv("HAIJUNBOT_ADMIN_PASSWORD", "AdminStrongPass1!")

    def setup(um, pm):
        _create_user(um, "noperm", "NoPermPass1!")

    client, _, _ = perm_client_factory(setup)
    headers = _login(client, "noperm", "NoPermPass1!")
    resp = client.post("/api/agents", headers=headers, json=_agent_payload())
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "PERMISSION_DENIED"
    assert "agent:create" in body["error"]["message"]


def test_no_permission_user_cannot_create_timer(perm_client_factory, monkeypatch):
    """Non-admin users without timer:* permission should be denied when creating a timer."""
    monkeypatch.setenv("HAIJUNBOT_ADMIN_PASSWORD", "AdminStrongPass1!")

    def setup(um, pm):
        _create_user(um, "noperm", "NoPermPass1!")

    client, _, _ = perm_client_factory(setup)
    headers = _login(client, "noperm", "NoPermPass1!")
    resp = client.post("/api/timers", headers=headers, json=_timer_payload())
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "PERMISSION_DENIED"
    assert "timer:create" in body["error"]["message"]


# ---------------------------------------------------------------------------
# Authorized users (sys-operator)
# ---------------------------------------------------------------------------
def test_operator_can_create_timer(perm_client_factory, monkeypatch):
    """Users in the sys-operator group (containing timer:*) can create timers normally."""
    monkeypatch.setenv("HAIJUNBOT_ADMIN_PASSWORD", "AdminStrongPass1!")

    def setup(um, pm):
        op = _create_user(um, "operator", "OpPass1!")
        pm.set_user_groups(op["user_id"], ["sys-operator"])

    client, _, _ = perm_client_factory(setup)
    headers = _login(client, "operator", "OpPass1!")
    resp = client.post("/api/timers", headers=headers, json=_timer_payload())
    body = resp.json()
    assert body["success"] is True, body
    timer_id = body["data"]["task_id"]
    # Cleanup
    resp_del = client.delete(f"/api/timers/{timer_id}", headers=headers)
    assert resp_del.json()["success"] is True


def test_operator_can_create_agent(perm_client_factory, monkeypatch):
    """Users in the sys-operator group (containing agent:create) can create Agents normally."""
    monkeypatch.setenv("HAIJUNBOT_ADMIN_PASSWORD", "AdminStrongPass1!")

    def setup(um, pm):
        op = _create_user(um, "operator", "OpPass1!")
        pm.set_user_groups(op["user_id"], ["sys-operator"])

    client, _, _ = perm_client_factory(setup)
    headers = _login(client, "operator", "OpPass1!")
    fake_agent = {
        "agent_id": "test-agent-op",
        "status": "running",
        "node_id": "local",
        "working_dir": "/tmp",
    }
    with patch.object(
        client.app.state.agent_manager, "create_agent", return_value=fake_agent
    ) as mock_create:
        resp = client.post("/api/agents", headers=headers, json=_agent_payload())
    body = resp.json()
    assert body["success"] is True, body
    assert mock_create.called


# ---------------------------------------------------------------------------
# Admin users are not affected
# ---------------------------------------------------------------------------
def test_admin_can_create_timer(perm_client_factory, monkeypatch):
    """Admin users (is_admin) are not affected by permission checks when creating timers."""
    monkeypatch.setenv("HAIJUNBOT_ADMIN_PASSWORD", "AdminStrongPass1!")

    client, _, _ = perm_client_factory()
    headers = _login(client, "admin", "AdminStrongPass1!")
    resp = client.post("/api/timers", headers=headers, json=_timer_payload())
    body = resp.json()
    assert body["success"] is True, body
    timer_id = body["data"]["task_id"]
    resp_del = client.delete(f"/api/timers/{timer_id}", headers=headers)
    assert resp_del.json()["success"] is True


def test_admin_can_create_agent(perm_client_factory, monkeypatch):
    """Admin users (is_admin) are not affected by permission checks when creating Agents."""
    monkeypatch.setenv("HAIJUNBOT_ADMIN_PASSWORD", "AdminStrongPass1!")

    client, _, _ = perm_client_factory()
    headers = _login(client, "admin", "AdminStrongPass1!")
    fake_agent = {
        "agent_id": "test-agent-admin",
        "status": "running",
        "node_id": "local",
        "working_dir": "/tmp",
    }
    with patch.object(
        client.app.state.agent_manager, "create_agent", return_value=fake_agent
    ) as mock_create:
        resp = client.post("/api/agents", headers=headers, json=_agent_payload())
    body = resp.json()
    assert body["success"] is True, body
    assert mock_create.called


# ---------------------------------------------------------------------------
# Gateway system token is not affected
# ---------------------------------------------------------------------------
def test_gateway_system_token_can_create_timer(
    perm_client_factory, monkeypatch, auth_token
):
    """Gateway system token (HAIJUNBOT_AUTH_TOKEN) is not affected by permission checks when creating timers."""
    monkeypatch.setenv("HAIJUNBOT_ADMIN_PASSWORD", "AdminStrongPass1!")

    client, _, _ = perm_client_factory()
    headers = {"Authorization": f"Bearer {auth_token}"}
    resp = client.post("/api/timers", headers=headers, json=_timer_payload())
    body = resp.json()
    assert body["success"] is True, body
    timer_id = body["data"]["task_id"]
    resp_del = client.delete(f"/api/timers/{timer_id}", headers=headers)
    assert resp_del.json()["success"] is True
