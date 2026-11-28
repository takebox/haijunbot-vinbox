# -*- coding: utf-8 -*-
"""Pipeline cross-process event bridging tests.

Covers:
1. /api/pipeline-events receives events and writes them to the gateway process event bus (readable by the event pump);
2. Non-admin users without file:read permission are denied (403 / PERMISSION_DENIED);
3. Admin users can report normally;
4. Invalid body (not a list) returns an error;
5. pipeline_runner._emit does not report to remote when the local pump is active (avoid duplication);
6. emit_remote fails silently when the gateway is unreachable (does not affect execution semantics).
"""

import os

os.environ["HAIJUNBOT_SKIP_INTERACTIVE_CONFIG"] = "1"

import pytest
from fastapi.testclient import TestClient

from haijunbot.haijunbot_tools.pipeline_events import (
    emit_remote,
    get_event_bus,
    is_local_pump_active,
    set_local_pump_active,
)


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
    return {"Authorization": f"Bearer {body['data']['token']}"}


def _make_admin_client(perm_client_factory, monkeypatch):
    """Create a TestClient logged in as admin."""
    monkeypatch.setenv("HAIJUNBOT_ADMIN_PASSWORD", "AdminStrongPass1!")
    client, _, _ = perm_client_factory()
    return client, _login(client, "admin", "AdminStrongPass1!")


def _sample_event():
    return {
        "pipeline_id": "test-pipeline-123456",
        "type": "pipeline_start",
        "orchestration_file": "/tmp/simple_demo.yaml",
        "working_dir": "/tmp",
        "nodes": [
            {
                "stage": "planner",
                "agent": "planner",
                "depends_on": [],
                "input": [],
                "output": "plan.md",
            },
            {
                "stage": "worker_a",
                "agent": "worker_a",
                "depends_on": ["planner"],
                "input": [],
                "output": "a.md",
            },
            {
                "stage": "worker_b",
                "agent": "worker_b",
                "depends_on": ["planner"],
                "input": [],
                "output": "b.md",
            },
            {
                "stage": "aggregator",
                "agent": "aggregator",
                "depends_on": ["worker_a", "worker_b"],
                "input": [],
                "output": "final.md",
            },
        ],
    }


class TestPipelineEventsIngest:
    def test_admin_can_ingest_events(self, perm_client_factory, monkeypatch):
        """Admin users can report events successfully, and events are written to the gateway process event bus."""
        client, headers = _make_admin_client(perm_client_factory, monkeypatch)
        # Clear the bus to ensure no residue before testing
        get_event_bus().drain()
        resp = client.post(
            "/api/pipeline-events",
            headers=headers,
            json={"events": [_sample_event()]},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["ingested"] == 1
        # Events should be written to the gateway process event bus (readable by the event pump)
        events = get_event_bus().drain()
        assert len(events) == 1
        assert events[0]["pipeline_id"] == "test-pipeline-123456"
        assert events[0]["type"] == "pipeline_start"

    def test_invalid_body_rejected(self, perm_client_factory, monkeypatch):
        """Returns an error when events is not a list."""
        client, headers = _make_admin_client(perm_client_factory, monkeypatch)
        resp = client.post(
            "/api/pipeline-events",
            headers=headers,
            json={"events": "not-a-list"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is False

    def test_no_permission_user_rejected(self, perm_client_factory, monkeypatch):
        """Non-admin users without file:read permission are denied."""
        from tests.haijunbot_web_gateway.test_permission_checks import _create_user

        monkeypatch.setenv("HAIJUNBOT_ADMIN_PASSWORD", "AdminStrongPass1!")

        def setup(um, pm):
            _create_user(um, "noperm", "NoPermPass1!")

        client, _, _ = perm_client_factory(setup)
        headers = _login(client, "noperm", "NoPermPass1!")
        resp = client.post(
            "/api/pipeline-events",
            headers=headers,
            json={"events": [_sample_event()]},
        )
        assert resp.status_code == 403, resp.text


class TestEmitRemote:
    def test_no_master_url_returns_false(self, monkeypatch):
        """emit_remote safely returns False when there is no master_url."""
        import haijunbot.haijunbot_utils.globals as jglobals

        monkeypatch.setattr(jglobals, "master_url", None)
        assert emit_remote(_sample_event()) is False

    def test_unreachable_gateway_returns_false(self, monkeypatch):
        """emit_remote silently returns False when the gateway is unreachable (does not raise an exception)."""
        import haijunbot.haijunbot_utils.globals as jglobals

        monkeypatch.setattr(jglobals, "master_url", "http://127.0.0.1:1")
        assert emit_remote(_sample_event()) is False

    def test_local_pump_active_flag(self):
        """Local pump active flag is readable/writable."""
        set_local_pump_active(True)
        assert is_local_pump_active() is True
        set_local_pump_active(False)
        assert is_local_pump_active() is False


class TestPipelineRunnerEmit:
    def test_emit_local_when_pump_active(self):
        """When the local pump is active, _emit only writes to the local bus (does not report to remote)."""
        from haijunbot.haijunbot_tools.pipeline_runner import PipelineRunnerTool

        set_local_pump_active(True)
        bus = get_event_bus()
        bus.drain()
        tool = PipelineRunnerTool()
        tool._emit("test-pipeline-123456", "pipeline_start", orchestration_file="/tmp/x.yaml")
        events = bus.drain()
        assert len(events) == 1
        assert events[0]["type"] == "pipeline_start"
        set_local_pump_active(False)

    def test_emit_writes_local_when_pump_inactive(self):
        """When the local pump is not active, _emit still writes to the local bus (remote report failure is silent)."""
        from haijunbot.haijunbot_tools.pipeline_runner import PipelineRunnerTool

        set_local_pump_active(False)
        bus = get_event_bus()
        bus.drain()
        tool = PipelineRunnerTool()
        tool._emit("test-pipeline-123456", "stage_update", stage="planner", status="running")
        events = bus.drain()
        assert len(events) == 1
        assert events[0]["type"] == "stage_update"
