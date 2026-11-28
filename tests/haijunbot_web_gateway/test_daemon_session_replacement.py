# -*- coding: utf-8 -*-
"""Regression tests for daemon "automatic cleanup of stale connections on the same machine".

Guarantees:
1. After daemon restarts, client_id changes (including PID). A new connection from the same
   machine (same user_id + same hostname) must replace the old connection; list_sessions
   must not show ghost entries;
2. Connections from different hostnames must coexist and not clean each other up;
3. When hostname is empty, identity cannot be determined, so no cleanup should be done (avoid accidental deletion);
4. If the replaced old session has pending calls, its Future must be set to an exception
   to avoid the caller waiting forever.

Isolation: data directory is redirected to tmp_path by ``conftest.py``'s autouse fixture;
TestClient (ASGI in-memory transport) is used throughout, no ports are listened on.
"""

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from haijunbot.haijunbot_web_gateway.app import create_app
from haijunbot.haijunbot_web_gateway.daemon_capability_manager import (
    DAEMON_SUBPROTOCOL,
    DaemonCapabilityManager,
)


def _token_subprotocol(token: str) -> list:
    """Construct WS subprotocol list carrying haijunbot-token."""
    from urllib.parse import quote

    return [DAEMON_SUBPROTOCOL, "haijunbot-token." + quote(token, safe="")]


@pytest.fixture
def client(auth_token):
    """Construct isolated application client; auth_token determines HAIJUNBOT_AUTH_TOKEN."""
    app = create_app()
    with TestClient(app) as c:
        yield c


def _hello(client_id: str, hostname: str = "", **extra) -> dict:
    """Construct a daemon hello frame; hostname is placed in system_info when non-empty."""
    frame: dict = {
        "type": "hello",
        "client_id": client_id,
        "extension_version": "0.0.1-test",
        "tabs": [],
    }
    if hostname:
        frame["system_info"] = {"hostname": hostname, "os_name": "Ubuntu"}
    frame.update(extra)
    return frame


def test_new_connection_replaces_same_host_session(client, auth_token):
    """A new connection with the same hostname should replace the old connection; list_sessions should only show the latest one."""
    manager = client.app.state.daemon_capability_manager
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws1:
        ws1.send_json(_hello("daemon-host-1001", hostname="same-host"))
        assert ws1.receive_json().get("type") == "hello_ack"
        assert len(manager.list_sessions()) == 1
        old_session_id = manager.list_sessions()[0]["session_id"]

        # Simulate daemon restart: client_id differs due to PID change, hostname unchanged
        with client.websocket_connect(
            "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
        ) as ws2:
            ws2.send_json(_hello("daemon-host-2002", hostname="same-host"))
            assert ws2.receive_json().get("type") == "hello_ack"

            sessions = manager.list_sessions()
            assert len(sessions) == 1, f"Old session was not cleaned up: {sessions}"
            assert sessions[0]["client_id"] == "daemon-host-2002"
            assert sessions[0]["session_id"] != old_session_id
            # Old session has been removed from the table
            assert manager.get_session(old_session_id) is None


def test_different_host_not_replaced(client, auth_token):
    """Connections with different hostnames should coexist and not clean each other up."""
    manager = client.app.state.daemon_capability_manager
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws1:
        ws1.send_json(_hello("daemon-hostA-1", hostname="host-a"))
        assert ws1.receive_json().get("type") == "hello_ack"

        with client.websocket_connect(
            "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
        ) as ws2:
            ws2.send_json(_hello("daemon-hostB-1", hostname="host-b"))
            assert ws2.receive_json().get("type") == "hello_ack"

            sessions = manager.list_sessions()
            assert len(sessions) == 2
            hostnames = {s["hostname"] for s in sessions}
            assert hostnames == {"host-a", "host-b"}


def test_empty_hostname_not_replaced(client, auth_token):
    """Connections with empty hostname cannot be identified, so they should coexist rather than clean each other up."""
    manager = client.app.state.daemon_capability_manager
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws1:
        ws1.send_json(_hello("daemon-nohost-1"))
        assert ws1.receive_json().get("type") == "hello_ack"

        with client.websocket_connect(
            "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
        ) as ws2:
            ws2.send_json(_hello("daemon-nohost-2"))
            assert ws2.receive_json().get("type") == "hello_ack"

            sessions = manager.list_sessions()
            assert len(sessions) == 2, f"Empty hostname should not be cleaned up: {sessions}"


def test_replacement_fails_pending_calls():
    """If the replaced old session has pending calls, its Future must be set to an exception."""
    manager = DaemonCapabilityManager()

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        # Construct an "old session" with a pending capability call
        manager._sessions["old-session"] = {
            "websocket": None,
            "user_id": "u1",
            "client_id": "daemon-host-1001",
            "node_id": "daemon-host-1001",
            "hostname": "same-host",
            "platform": "Ubuntu",
            "system_info": {"hostname": "same-host"},
            "daemon_version": "0.0.1",
            "capabilities": [],
            "connected_at": 0.0,
            "last_seen": 0.0,
        }
        pending: asyncio.Future = loop.create_future()
        setattr(pending, "_daemon_session", "old-session")
        manager._pending_calls["call-1"] = pending

        await manager._replace_stale_sessions("new-session", "u1", "same-host")

        assert "old-session" not in manager._sessions
        assert pending.done()
        with pytest.raises(RuntimeError, match="disconnected"):
            pending.result()
        assert "call-1" not in manager._pending_calls

    asyncio.run(_run())
