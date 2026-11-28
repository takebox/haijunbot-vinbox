# -*- coding: utf-8 -*-
"""End-to-end regression tests for browser extension hello reporting capabilities.

Guarantees:
1. When the extension's first hello frame carries a ``capabilities`` array, it must be persisted to the session;
2. ``list_sessions()`` / ``get_session()`` responses must include ``capabilities``;
3. Backward compatibility: when hello does not carry capabilities (or is not a list), fall back to ``[]`` without raising an exception;
4. GET /api/browser-ext/sessions returns capabilities matching what was reported.

Isolation: data directory is redirected to tmp_path by conftest.py's autouse fixture;
TestClient (ASGI in-memory transport) is used throughout, no ports are listened on.
"""

import sys
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from haijunbot.haijunbot_web_gateway.app import create_app

EXT_SUBPROTOCOL = "haijunbot-ext"


def _token_subprotocol(token: str) -> list:
    """Construct WS subprotocol list carrying haijunbot-token (extension uses haijunbot-ext subprotocol)."""
    return [EXT_SUBPROTOCOL, "haijunbot-token." + quote(token, safe="")]


@pytest.fixture
def client(auth_token):
    """Construct isolated application client; auth_token determines HAIJUNBOT_AUTH_TOKEN."""
    app = create_app()
    with TestClient(app) as c:
        yield c


CAPS = [
    {
        "name": "tab.list",
        "description": "List currently open browser tabs",
        "parameters": {},
        "platform": "browser",
    },
    {
        "name": "dom.click",
        "description": "Click page elements",
        "parameters": {"selector": "string"},
        "platform": "browser",
    },
]


def test_hello_capabilities_persisted(client, auth_token):
    """When hello carries capabilities, the session should be persisted and readable from list_sessions."""
    with client.websocket_connect(
        "/api/browser-ext/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "ext-client-1",
                "extension_version": "6.0.7",
                "browser_info": {"name": "Edge", "version": "120"},
                "capabilities": CAPS,
                "tabs": [],
            }
        )
        # Read hello_ack
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"

        # Read session via HTTP interface
        resp = client.get(
            "/api/browser-ext/sessions",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        sessions = resp.json()["sessions"]
        assert len(sessions) >= 1
        session = next(s for s in sessions if s["client_id"] == "ext-client-1")
        assert session["capabilities"] == CAPS


def test_hello_without_capabilities_falls_back_to_empty(client, auth_token):
    """When a legacy extension's hello does not carry capabilities, fall back to [] without raising an exception."""
    with client.websocket_connect(
        "/api/browser-ext/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "ext-client-legacy",
                "extension_version": "6.0.0",
                "browser_info": {"name": "Chrome"},
                "tabs": [],
            }
        )
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"

        resp = client.get(
            "/api/browser-ext/sessions",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        sessions = resp.json()["sessions"]
        assert len(sessions) >= 1
        session = next(s for s in sessions if s["client_id"] == "ext-client-legacy")
        assert session["capabilities"] == []
