# -*- coding: utf-8 -*-
"""Regression tests for terminal name (hello frame ``name`` field).

Background: users configure a "terminal name" (defaulting to the computer name) on the
HaijunBot web settings page. This value is reported by the daemon / browser extension's
hello frame to the gateway, allowing the gateway/Agent to identify the terminal by
a readable name. Guarantees:

1. When daemon hello carries ``name``, the session should be persisted and readable from list_sessions/get_session;
2. When daemon hello does not carry ``name``, fall back to hostname (legacy daemon compatibility);
3. When daemon hello carries an empty/blank ``name``, also fall back to hostname;
4. When browser extension hello carries ``name``, it should be persisted and readable from list_sessions/get_session;
5. When browser extension hello does not carry ``name``, return an empty string (no error);
6. Browser extension reconnect hello can refresh ``name``.

Isolation: data directory is redirected to tmp_path by ``conftest.py``'s autouse fixture;
TestClient (ASGI in-memory transport) is used throughout, no ports are listened on.
"""

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


def _ext_subprotocol(token: str) -> list:
    """Construct subprotocol list for browser extension endpoint (haijunbot-ext + token)."""
    from urllib.parse import quote

    return ["haijunbot-ext", "haijunbot-token." + quote(token, safe="")]


@pytest.fixture
def client(auth_token):
    """Construct isolated application client; auth_token determines HAIJUNBOT_AUTH_TOKEN."""
    app = create_app()
    with TestClient(app) as c:
        yield c


# ----------------------------------------------------------------------
# Daemon side
# ----------------------------------------------------------------------


def test_daemon_hello_name_persisted(client, auth_token):
    """When daemon hello carries name, the session should be persisted and readable from list_sessions/get_session."""
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "daemon-name-1",
                "extension_version": "0.0.1-test",
                "name": "SF-PC",
                "system_info": {"hostname": "sf-pc-host", "os_name": "Windows"},
                "tabs": [],
            }
        )
        ack = ws.receive_json()
        assert ack.get("type") == "hello_ack"

        manager = client.app.state.daemon_capability_manager
        sessions = manager.list_sessions()
        assert len(sessions) == 1
        session = sessions[0]
        # name is persisted as-is and not overwritten by hostname
        assert session["name"] == "SF-PC"
        assert session["hostname"] == "sf-pc-host"

        # get_session also carries name
        detail = manager.get_session(session["session_id"])
        assert detail is not None
        assert detail["name"] == "SF-PC"


def test_daemon_hello_without_name_falls_back_to_hostname(client, auth_token):
    """Backward compatibility: when daemon hello has no name, the returned name falls back to hostname."""
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "daemon-noname-1",
                "extension_version": "0.0.0-legacy",
                "system_info": {"hostname": "legacy-host", "os_name": "Linux"},
                "tabs": [],
            }
        )
        ack = ws.receive_json()
        assert ack.get("type") == "hello_ack"

        manager = client.app.state.daemon_capability_manager
        sessions = manager.list_sessions()
        assert len(sessions) == 1
        # Falls back to hostname when no name field
        assert sessions[0]["name"] == "legacy-host"
        detail = manager.get_session(sessions[0]["session_id"])
        assert detail is not None
        assert detail["name"] == "legacy-host"


def test_daemon_hello_blank_name_falls_back_to_hostname(client, auth_token):
    """When daemon hello carries a blank name, also fall back to hostname; blank string must not be persisted."""
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "daemon-blankname-1",
                "extension_version": "0.0.0",
                "name": "   ",
                "system_info": {"hostname": "blank-host", "os_name": "Linux"},
                "tabs": [],
            }
        )
        ack = ws.receive_json()
        assert ack.get("type") == "hello_ack"

        manager = client.app.state.daemon_capability_manager
        sessions = manager.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["name"] == "blank-host"


def test_daemon_list_sessions_without_name_returns_hostname():
    """For legacy sessions without a persisted name, list_sessions/get_session name should fall back to hostname instead of None."""
    manager = DaemonCapabilityManager()
    manager._sessions["s1"] = {
        "websocket": None,
        "user_id": "u1",
        "client_id": "c1",
        "node_id": "c1",
        "hostname": "fallback-host",
        "platform": "",
        "capabilities": [],
        "connected_at": 0.0,
        "last_seen": 0.0,
    }
    sessions = manager.list_sessions()
    assert sessions[0]["name"] == "fallback-host"
    detail = manager.get_session("s1")
    assert detail is not None
    assert detail["name"] == "fallback-host"


# ----------------------------------------------------------------------
# Browser extension side
# ----------------------------------------------------------------------


def test_extension_hello_name_persisted(client, auth_token):
    """When extension hello carries name, the session should be persisted and readable from list_sessions/get_session."""
    with client.websocket_connect(
        "/api/browser-ext/ws", subprotocols=_ext_subprotocol(auth_token)
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "ext-name-1",
                "extension_version": "0.0.1-test",
                "name": "SF-PC",
                "browser_info": {"user_agent": "UA", "platform": "Win32"},
                "tabs": [],
            }
        )
        ack = ws.receive_json()
        assert ack.get("type") == "hello_ack"

        manager = client.app.state.browser_extension_manager
        sessions = manager.list_sessions()
        assert len(sessions) == 1
        session = sessions[0]
        assert session["name"] == "SF-PC"

        detail = manager.get_session(session["session_id"])
        assert detail is not None
        assert detail["name"] == "SF-PC"


def test_extension_hello_without_name_returns_empty(client, auth_token):
    """Backward compatibility: when extension hello has no name, return an empty string and do not raise an exception."""
    with client.websocket_connect(
        "/api/browser-ext/ws", subprotocols=_ext_subprotocol(auth_token)
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "ext-noname-1",
                "extension_version": "0.0.0-legacy",
                "browser_info": {"platform": "Win32"},
                "tabs": [],
            }
        )
        ack = ws.receive_json()
        assert ack.get("type") == "hello_ack"

        manager = client.app.state.browser_extension_manager
        sessions = manager.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["name"] == ""
        detail = manager.get_session(sessions[0]["session_id"])
        assert detail is not None
        assert detail["name"] == ""


def test_extension_reconnect_hello_refreshes_name(client, auth_token):
    """When the extension reconnects and re-handshakes, name should be refreshed to the latest value."""
    with client.websocket_connect(
        "/api/browser-ext/ws", subprotocols=_ext_subprotocol(auth_token)
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "ext-refresh-1",
                "extension_version": "0.0.1-test",
                "name": "old-name",
                "tabs": [],
            }
        )
        ack = ws.receive_json()
        assert ack.get("type") == "hello_ack"

        manager = client.app.state.browser_extension_manager
        session_id = manager.list_sessions()[0]["session_id"]
        assert manager.get_session(session_id)["name"] == "old-name"

        # Send hello again on the same connection (reconnect handshake), name should refresh
        ws.send_json(
            {
                "type": "hello",
                "client_id": "ext-refresh-1",
                "extension_version": "0.0.1-test",
                "name": "new-name",
                "tabs": [],
            }
        )
        # Trigger a ping/pong to confirm the message has been processed
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong.get("type") == "pong"

        assert manager.get_session(session_id)["name"] == "new-name"
