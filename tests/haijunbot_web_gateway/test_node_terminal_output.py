# -*- coding: utf-8 -*-
"""Unit tests for broadcasting child node terminal output to admin users.

Covers NodeConnectionManager._publish_terminal_output_to_admins:
1. Child node terminal output should be broadcast to all admin users (ACL decisions are unified on master)
2. Exclude the initiator session_id to avoid duplicate pushes
3. Safe return when there is no terminal_session_manager
"""

import os

# Must set environment variables before importing haijunbot modules to avoid triggering interactive configuration
os.environ["HAIJUNBOT_SKIP_INTERACTIVE_CONFIG"] = "1"

import asyncio
import base64

from unittest.mock import MagicMock

from haijunbot.haijunbot_web_gateway.node_manager import (
    ChildNodeClient,
    NodeConnectionManager,
)


def _make_manager(admin_sids, router=None):
    """Construct a NodeConnectionManager with a mock terminal_session_manager."""
    tsm = MagicMock()
    tsm.get_all_admin_session_ids.return_value = admin_sids
    return NodeConnectionManager(
        node_runtime=MagicMock(),
        agent_manager=MagicMock(),
        agent_proxy_manager=MagicMock(),
        node_http_dispatcher=None,
        router=router or MagicMock(),
        terminal_session_manager=tsm,
    )


def test_publish_terminal_output_broadcasts_to_all_admins():
    """Child node terminal output should be broadcast to all admin users."""
    published = []

    class FakeRouter:
        def publish(self, message, session_id=None, connection_id=None):
            published.append(session_id)

    m = _make_manager(["session_admin-a", "session_admin-b"], router=FakeRouter())
    m._publish_terminal_output_to_admins({"type": "execution"}, "session_owner1")

    assert "session_admin-a" in published
    assert "session_admin-b" in published


def test_publish_terminal_output_excludes_initiator():
    """The initiator session_id should be excluded during broadcast to avoid duplicate pushes."""
    published = []

    class FakeRouter:
        def publish(self, message, session_id=None, connection_id=None):
            published.append(session_id)

    # The initiator itself is also an admin
    m = _make_manager(["session_admin-a", "session_admin-b"], router=FakeRouter())
    m._publish_terminal_output_to_admins({"type": "execution"}, "session_admin-a")

    assert "session_admin-a" not in published
    assert "session_admin-b" in published


def test_publish_terminal_output_no_manager_is_safe():
    """When there is no terminal_session_manager, it should return safely without raising an exception."""
    m = NodeConnectionManager(
        node_runtime=MagicMock(),
        agent_manager=MagicMock(),
        agent_proxy_manager=MagicMock(),
        node_http_dispatcher=None,
        router=MagicMock(),
        terminal_session_manager=None,
    )
    # Should not raise an exception
    m._publish_terminal_output_to_admins({"type": "execution"}, "session_owner1")


def _make_child_client(tsm):
    """Construct a ChildNodeClient with a mock terminal_session_manager (child node side)."""
    ncm = MagicMock()
    ncm._terminal_session_manager = tsm
    return ChildNodeClient(
        node_runtime=MagicMock(),
        agent_manager=MagicMock(),
        agent_proxy_manager=MagicMock(),
        node_connection_manager=ncm,
    )


def _attach_message(terminal_id, request_id="req-1"):
    return {
        "request_id": request_id,
        "payload": {
            "action": "terminal_attach",
            "session_id": "default",
            "payload": {"terminal_id": terminal_id},
        },
    }


def test_child_terminal_attach_returns_output_buffer():
    """Child node terminal_attach should return the output buffer (base64 list)."""
    chunk1 = b"hello "
    chunk2 = b"world\n"
    session = MagicMock()
    session.interpreter = "bash"
    session.working_dir = "/home/user"
    session.get_output_buffer.return_value = [chunk1, chunk2]

    tsm = MagicMock()
    tsm.get_session.return_value = session

    client = _make_child_client(tsm)
    resp = asyncio.run(client._handle_node_terminal_request(_attach_message("term-1")))

    payload = resp["payload"]
    assert payload["success"] is True
    data = payload["data"]
    assert data["terminal_id"] == "term-1"
    assert data["interpreter"] == "bash"
    assert data["working_dir"] == "/home/user"
    assert data["output"] == [
        base64.b64encode(chunk1).decode("utf-8"),
        base64.b64encode(chunk2).decode("utf-8"),
    ]
    tsm.get_session.assert_called_once_with("term-1")


def test_child_terminal_attach_missing_session_returns_not_found():
    """Child node terminal_attach should return NOT_FOUND when the session cannot be found."""
    tsm = MagicMock()
    tsm.get_session.return_value = None

    client = _make_child_client(tsm)
    resp = asyncio.run(
        client._handle_node_terminal_request(_attach_message("missing-term"))
    )

    payload = resp["payload"]
    assert payload["success"] is False
    assert payload["error"]["code"] == "NOT_FOUND"


def test_child_terminal_attach_empty_terminal_id_returns_not_found():
    """Child node terminal_attach should return NOT_FOUND when terminal_id is empty."""
    tsm = MagicMock()

    client = _make_child_client(tsm)
    resp = asyncio.run(client._handle_node_terminal_request(_attach_message("")))

    payload = resp["payload"]
    assert payload["success"] is False
    assert payload["error"]["code"] == "NOT_FOUND"
    # Empty terminal_id should not call get_session
    tsm.get_session.assert_not_called()
