# -*- coding: utf-8 -*-
"""Regression tests for daemon hello reporting system_info.

Guarantees:
1. ``system_info`` in the daemon's first hello frame must be persisted to the session;
2. ``hostname`` / ``platform`` are taken from ``system_info`` (platform takes os_name);
3. ``list_sessions()`` / ``get_session()`` responses must include ``system_info``;
4. Backward compatibility: when ``system_info`` is missing, fall back to ``browser_info``
   for hostname/platform, and do not raise an exception.

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


@pytest.fixture
def client(auth_token):
    """Construct isolated application client; auth_token determines HAIJUNBOT_AUTH_TOKEN."""
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_hello_system_info_persisted(client, auth_token):
    """When hello carries system_info, the session should be persisted and readable from list_sessions."""
    system_info = {
        "hostname": "test-host",
        "kernel": "6.8.0-test",
        "os_name": "Ubuntu",
        "os_version": "24.04",
        "arch": "amd64",
        "cpu_count": 8,
        "cpu_model": "Test CPU",
        "mem_total_kb": 16000000,
        "mem_available_kb": 8000000,
        "uptime_sec": 12345,
        "user": "tester",
        "home": "/home/tester",
    }
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "daemon-test-host-1",
                "extension_version": "0.0.1-test",
                "system_info": system_info,
                "tabs": [],
            }
        )
        ack = ws.receive_json()
        assert ack.get("type") == "hello_ack"

        sessions = client.app.state.daemon_capability_manager.list_sessions()
        assert len(sessions) == 1
        session = sessions[0]
        # system_info is persisted as-is
        assert session["system_info"] == system_info
        # hostname is taken from system_info
        assert session["hostname"] == "test-host"
        # platform is taken from system_info's os_name
        assert session["platform"] == "Ubuntu"
        # Existing fields are not affected
        assert session["client_id"] == "daemon-test-host-1"
        assert session["daemon_version"] == "0.0.1-test"

        # get_session also carries system_info
        detail = client.app.state.daemon_capability_manager.get_session(
            session["session_id"]
        )
        assert detail is not None
        assert detail["system_info"] == system_info


def test_hello_without_system_info_falls_back_to_browser_info(client, auth_token):
    """Backward compatibility: when system_info is missing, fall back to browser_info and do not raise an exception."""
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "daemon-legacy-1",
                "extension_version": "0.0.0-legacy",
                "browser_info": {"hostname": "legacy-host", "platform": "linux"},
                "tabs": [],
            }
        )
        ack = ws.receive_json()
        assert ack.get("type") == "hello_ack"

        sessions = client.app.state.daemon_capability_manager.list_sessions()
        assert len(sessions) == 1
        session = sessions[0]
        assert session["system_info"] == {}
        assert session["hostname"] == "legacy-host"
        assert session["platform"] == "linux"


def test_hello_with_invalid_system_info_type(client, auth_token):
    """When system_info has an invalid type (not a dict), it should be normalized to an empty dict and not raise an exception."""
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "daemon-badtype-1",
                "extension_version": "0.0.0",
                "system_info": "not-a-dict",
                "tabs": [],
            }
        )
        ack = ws.receive_json()
        assert ack.get("type") == "hello_ack"

        sessions = client.app.state.daemon_capability_manager.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["system_info"] == {}


def test_list_sessions_without_system_info_returns_empty_dict():
    """For sessions that did not report system_info, list_sessions should return an empty dict instead of None."""
    manager = DaemonCapabilityManager()
    manager._sessions["s1"] = {
        "websocket": None,
        "user_id": "u1",
        "client_id": "c1",
        "node_id": "c1",
        "hostname": "",
        "platform": "",
        "daemon_version": "0.0.0",
        "capabilities": [],
        "connected_at": 0.0,
        "last_seen": 0.0,
    }
    sessions = manager.list_sessions()
    assert sessions[0]["system_info"] == {}
    detail = manager.get_session("s1")
    assert detail is not None
    assert detail["system_info"] == {}


def test_hello_build_info_persisted(client, auth_token):
    """When hello carries build_info, the session should be persisted and readable from list_sessions/get_session.

    build_info is reported by the new version daemon (including build time), for the gateway to determine
    "which version is currently running and when it was built". Legacy daemons do not carry this field;
    see the next test case.
    """
    build_info = {
        "version": "v5.0.6",
        "build_time": "2026-09-26T15:00:00Z",
        "build_time_unix": 1789000000,
        "build_time_source": "exe_mtime",
        "go_version": "go1.27.1",
        "os": "windows",
        "arch": "amd64",
        "exe_path": r"D:\haijunbot-daemon.exe",
    }
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "daemon-buildinfo-1",
                "extension_version": "v5.0.6",
                "build_info": build_info,
                "tabs": [],
            }
        )
        ack = ws.receive_json()
        assert ack.get("type") == "hello_ack"
        manager = client.app.state.daemon_capability_manager
        sessions = manager.list_sessions()
        assert len(sessions) == 1
        session = sessions[0]
        # build_info is persisted as-is
        assert session["build_info"] == build_info
        # Build time is readable
        assert session["build_info"]["build_time"] == "2026-09-26T15:00:00Z"
        assert session["build_info"]["build_time_source"] == "exe_mtime"
        # get_session also carries build_info
        detail = manager.get_session(session["session_id"])
        assert detail is not None
        assert detail["build_info"] == build_info


def test_hello_without_build_info_returns_empty_dict(client, auth_token):
    """Backward compatibility: when build_info is missing, fall back to an empty dict and do not raise an exception."""
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "daemon-nobuildinfo-1",
                "extension_version": "0.0.0-legacy",
                "tabs": [],
            }
        )
        ack = ws.receive_json()
        assert ack.get("type") == "hello_ack"
        manager = client.app.state.daemon_capability_manager
        sessions = manager.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["build_info"] == {}


def test_hello_with_invalid_build_info_type(client, auth_token):
    """When build_info has an invalid type (not a dict), it should be normalized to an empty dict and not raise an exception."""
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "daemon-badbuildinfo-1",
                "extension_version": "0.0.0",
                "build_info": "not-a-dict",
                "tabs": [],
            }
        )
        ack = ws.receive_json()
        assert ack.get("type") == "hello_ack"
        manager = client.app.state.daemon_capability_manager
        sessions = manager.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["build_info"] == {}


def test_list_sessions_without_build_info_returns_empty_dict():
    """For sessions that did not report build_info, list_sessions/get_session should return an empty dict instead of None."""
    manager = DaemonCapabilityManager()
    manager._sessions["s1"] = {
        "websocket": None,
        "user_id": "u1",
        "client_id": "c1",
        "node_id": "c1",
        "hostname": "",
        "platform": "",
        "daemon_version": "0.0.0",
        "capabilities": [],
        "connected_at": 0.0,
        "last_seen": 0.0,
    }
    sessions = manager.list_sessions()
    assert sessions[0]["build_info"] == {}
    detail = manager.get_session("s1")
    assert detail is not None
    assert detail["build_info"] == {}


def test_system_info_update_merges_into_session(client, auth_token):
    """A system_info_update sent after hello should be merged into the session cache.

    Background: the hello first frame only carries "quick version" system info (to avoid handshake timeout),
    and the complete info is subsequently sent via system_info_update. The gateway needs to merge (not overwrite)
    so that derived fields hostname/platform are refreshed accordingly.
    """
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        # hello only carries zero-cost fields (quick version).
        ws.send_json(
            {
                "type": "hello",
                "client_id": "daemon-fast-1",
                "extension_version": "0.0.1-test",
                "system_info": {"hostname": "fast-host", "arch": "amd64"},
                "tabs": [],
            }
        )
        ack = ws.receive_json()
        assert ack.get("type") == "hello_ack"

        # Subsequently send complete system info.
        ws.send_json(
            {
                "type": "system_info_update",
                "system_info": {
                    "os_name": "Windows 10 Pro",
                    "os_version": "10.0.19045",
                    "mem_total_kb": 16000000,
                },
            }
        )
        # Send a ping/pong to ensure the update has been processed.
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong.get("type") == "pong"

        manager = client.app.state.daemon_capability_manager
        sessions = manager.list_sessions()
        assert len(sessions) == 1
        session = sessions[0]
        # Merged result should contain both hello's quick fields and update's complete fields.
        assert session["system_info"]["hostname"] == "fast-host"
        assert session["system_info"]["arch"] == "amd64"
        assert session["system_info"]["os_name"] == "Windows 10 Pro"
        assert session["system_info"]["mem_total_kb"] == 16000000
        # Derived field platform should refresh with os_name.
        assert session["platform"] == "Windows 10 Pro"


def test_system_info_update_ignored_when_not_dict(client, auth_token):
    """When system_info_update's system_info is not a dict, it should be safely ignored without raising an exception or polluting the session."""
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "daemon-badupd-1",
                "extension_version": "0.0.1-test",
                "system_info": {"hostname": "keep-host"},
                "tabs": [],
            }
        )
        ack = ws.receive_json()
        assert ack.get("type") == "hello_ack"

        # Invalid update: system_info is a string, not a dict.
        ws.send_json({"type": "system_info_update", "system_info": "not-a-dict"})
        # Use ping/pong to synchronize, ensuring the invalid message has been processed and the connection is not dropped.
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong.get("type") == "pong"

        manager = client.app.state.daemon_capability_manager
        sessions = manager.list_sessions()
        assert len(sessions) == 1
        # Original system_info has not been polluted.
        assert sessions[0]["system_info"] == {"hostname": "keep-host"}
