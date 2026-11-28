"""Tests for _on_agent_status_change WebSocket broadcast logic.

This function is called by AgentManager when an Agent lifecycle status change occurs,
broadcasting status_update messages to all connected frontends via the global _router.
This test uses a fake router to verify the broadcast message format.
"""

from typing import Any, Dict, List

import pytest

from haijunbot.haijunbot_web_gateway import app as app_module


class FakeRouter:
    """Fake router that records publish calls."""

    def __init__(self) -> None:
        self.published: List[Dict[str, Any]] = []

    def publish(self, message: Dict[str, Any], session_id: Any = None) -> None:
        self.published.append({"message": message, "session_id": session_id})


@pytest.fixture(autouse=True)
def _patch_router(monkeypatch: pytest.MonkeyPatch) -> FakeRouter:
    """Replace the app module's global _router with a fake router."""
    fake = FakeRouter()
    monkeypatch.setattr(app_module, "_router", fake)
    return fake


def _call(agent_id: str, status: str, data: Any = None) -> None:
    app_module._on_agent_status_change(agent_id, status, data)


def test_stopped_broadcasts_stopped_execution_status(_patch_router: FakeRouter) -> None:
    """When an Agent stops normally, broadcast execution_status=stopped with agent_id."""
    _call("agent-1", "stopped", {"agent_id": "agent-1", "status": "stopped"})
    assert len(_patch_router.published) == 1
    msg = _patch_router.published[0]["message"]
    assert msg["type"] == "status_update"
    payload = msg["payload"]
    assert payload["agent_id"] == "agent-1"
    assert payload["status"] == "stopped"
    assert payload["execution_status"] == "stopped"
    # Broadcast mode: session_id is None
    assert _patch_router.published[0]["session_id"] is None


def test_error_broadcasts_stopped_execution_status(_patch_router: FakeRouter) -> None:
    """When an Agent exits with an error, also map to stopped for frontend to mark as exited."""
    _call("agent-2", "error", {"return_code": 1})
    payload = _patch_router.published[0]["message"]["payload"]
    assert payload["agent_id"] == "agent-2"
    assert payload["status"] == "error"
    assert payload["execution_status"] == "stopped"


def test_deleted_broadcasts_status_without_execution_status(
    _patch_router: FakeRouter,
) -> None:
    """When an Agent is deleted, broadcast raw status=deleted without setting execution_status."""
    _call("agent-3", "deleted", None)
    payload = _patch_router.published[0]["message"]["payload"]
    assert payload["agent_id"] == "agent-3"
    assert payload["status"] == "deleted"
    assert "execution_status" not in payload


def test_running_broadcasts_running_execution_status(
    _patch_router: FakeRouter,
) -> None:
    """When an Agent is running, broadcast execution_status=running."""
    _call("agent-4", "running", {"status": "running"})
    payload = _patch_router.published[0]["message"]["payload"]
    assert payload["execution_status"] == "running"


def test_no_router_no_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """When _router is None, return silently without raising an exception."""
    monkeypatch.setattr(app_module, "_router", None)
    # Should not raise an exception
    app_module._on_agent_status_change("agent-5", "stopped", None)
