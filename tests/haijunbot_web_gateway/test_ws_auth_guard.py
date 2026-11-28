# -*- coding: utf-8 -*-
"""Gateway WebSocket endpoint authentication regression tests.

Guarantees: all externally exposed WS endpoints must reject connections when
"no Token is carried", and there must be no fallback logic that "allows even
without a token" (historical defect:
``else: authorized = any(auth is not None for auth in manager._auth_store.values())``).

Covered endpoints:
- ``/api/lsp/{server_id}``           Language server bridge
- ``/api/browser-ext/ws``            Browser extension
- ``/api/daemon/ws``                 Daemon
- ``/api/agent/{agent_id}/ws``      Agent proxy
- ``/api/node/{node_id}/agent/{agent_id}/ws``  Cross-node Agent proxy

Assertion criteria: on rejection, the server first sends ``{"type":"error","payload":{"code":"AUTH_FAILED"}}``,
then closes with close code ``4401``; "with a valid token" must pass authentication,
manifesting as a business error code unrelated to authentication (4404/4000, etc.), not 4401.

**Why an authenticated connection must be established first (critical)**:
The ``auth_store`` in ``create_app()`` starts as empty ``{}``; only successfully
authenticated connections write to it (in ``app.py``'s ``WebSocketConnectionManager.handle``:
``self._auth_store[session_id] = auth_payload``). The historical defect's fallback expression
``any(a is not None for a in gateway._auth_store.values())`` is always ``False`` on an
empty store, so **if the store is not made non-empty first, the defect is unreachable and
the test is meaningless**. The ``authenticated_session`` fixture exists for this purpose:
it first makes a legal connection to make the store non-empty, so that subsequent
"no token should be rejected" assertions are truly effective.

Isolation: data directory is redirected to tmp_path by ``tests/haijunbot_web_gateway/conftest.py``'s
autouse fixture; TestClient (ASGI in-memory transport) is used throughout, no ports are listened on.
"""

import sys
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from haijunbot.haijunbot_web_gateway.app import create_app

AUTH_FAILED_CODE = "AUTH_FAILED"
WS_UNAUTHORIZED_CLOSE = 4401


def _token_subprotocol(token: str) -> list:
    """Construct WS subprotocol list carrying haijunbot-token."""
    return ["haijunbot-ws", "haijunbot-token." + quote(token, safe="")]


@pytest.fixture
def client(auth_token):
    """Construct isolated application client; auth_token determines HAIJUNBOT_AUTH_TOKEN."""
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def authenticated_session(client, auth_token):
    """First establish an authenticated connection to make ``gateway._auth_store`` non-empty.

    This is the prerequisite for making the "no token fallback allow" defect reachable:
    on an empty store, ``any(...)`` is always False, the defect cannot be triggered,
    and the test would be falsely green.

    Must use the ``/ws`` endpoint: only it goes through ``WebSocketConnectionManager.handle``,
    which executes ``self._auth_store[session_id] = auth_payload`` after authentication
    succeeds (around line 884 of app.py). The lsp / browser-ext / daemon / agent endpoints
    each have **independent** authentication and do **not** write ``_auth_store``, so
    using them to establish a connection still leaves the store empty.
    """
    with client.websocket_connect(
        "/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        yield ws


def _expect_rejected_without_token(client: TestClient, url: str) -> None:
    """Assert: connecting to this WS endpoint without a token is rejected with 4401."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(url) as ws:
            message = ws.receive_json()
            assert message["type"] == "error"
            assert message["payload"]["code"] == AUTH_FAILED_CODE
            ws.receive_text()  # Trigger server close
    assert exc_info.value.code == WS_UNAUTHORIZED_CLOSE


# --- No token: all must be rejected (store non-empty, fallback defect reachable) ------------------------


def test_lsp_ws_rejects_without_token(client, authenticated_session):
    _expect_rejected_without_token(client, "/api/lsp/pyright")


def test_browser_ext_ws_rejects_without_token(client, authenticated_session):
    _expect_rejected_without_token(client, "/api/browser-ext/ws")


def test_daemon_ws_rejects_without_token(client, authenticated_session):
    _expect_rejected_without_token(client, "/api/daemon/ws")


def test_agent_ws_rejects_without_token(client, authenticated_session):
    _expect_rejected_without_token(client, "/api/agent/ghost-agent/ws")


def test_remote_node_agent_ws_rejects_without_token(client, authenticated_session):
    _expect_rejected_without_token(
        client, "/api/node/some-remote-node/agent/ghost-agent/ws"
    )


# --- With valid token: must pass authentication ---------------------------------------------


def test_lsp_ws_with_valid_token_passes_auth(client, auth_token):
    """With a valid token, should no longer be rejected with 4401, but return 4404 due to invalid server_id."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/api/lsp/definitely-not-a-server",
            subprotocols=_token_subprotocol(auth_token),
        ) as ws:
            message = ws.receive_json()
            assert message["payload"]["code"] == "UNKNOWN_SERVER"
            ws.receive_text()
    assert exc_info.value.code == 4404


def test_agent_ws_with_valid_token_passes_auth(client, auth_token):
    """With a valid token, passes authentication and returns 4000 because the agent does not exist (not 4401)."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/api/agent/ghost-agent/ws",
            subprotocols=_token_subprotocol(auth_token),
        ) as ws:
            ws.receive_text()
    assert exc_info.value.code == 4000


def test_invalid_token_is_rejected(client, authenticated_session):
    """Forged tokens must also be rejected with 4401 (cannot be allowed just because "some token exists")."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/api/agent/ghost-agent/ws",
            subprotocols=_token_subprotocol("forged-token-not-valid"),
        ) as ws:
            message = ws.receive_json()
            assert message["payload"]["code"] == AUTH_FAILED_CODE
            ws.receive_text()
    assert exc_info.value.code == WS_UNAUTHORIZED_CLOSE


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
