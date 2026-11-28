# -*- coding: utf-8 -*-
"""Integration terminal ACL unit tests.

Covers TerminalSessionManager's ACL logic:
1. Owner can set ACL (set_access_acl), non-owner is denied
2. set_access_acl automatically filters out the owner and admin users
3. read users can attach but cannot interact (attach returns "read")
4. interact users can attach and interact (attach returns "interact")
5. Non-ACL users are denied attach (returns None)
6. admin / system users are allowed through (treated as owner)
7. list_sessions_for_user returns owner sessions + shared sessions (with access level)

Does not depend on real PTY: directly constructs TerminalSession objects injected into manager._sessions.
"""

import os

# Must set environment variables before importing haijunbot modules to avoid triggering interactive configuration
os.environ["HAIJUNBOT_SKIP_INTERACTIVE_CONFIG"] = "1"

import pytest
from unittest.mock import patch

from haijunbot.haijunbot_web_gateway.terminal_session_manager import (
    TerminalSession,
    TerminalSessionManager,
)


def _make_session(terminal_id, owner_id, acl=None, session_id=None):
    """Construct a session object without a real PTY (for ACL logic testing only)."""
    return TerminalSession(
        terminal_id=terminal_id,
        interpreter="bash",
        working_dir=".",
        session_id=session_id or f"session_{owner_id}",
        owner_id=owner_id,
        access_acl=acl or {},
    )


@pytest.fixture
def manager():
    m = TerminalSessionManager()
    m._sessions["term-1"] = _make_session("term-1", "owner1")
    return m


def test_owner_can_set_acl(manager):
    ok = manager.set_access_acl(
        "term-1", "owner1", {"read": ["u1"], "interact": ["u2"]}
    )
    assert ok is True
    info = manager.get_session_info("term-1")
    assert info["access_acl"] == {"read": ["u1"], "interact": ["u2"]}


def test_non_owner_cannot_set_acl(manager):
    ok = manager.set_access_acl("term-1", "intruder", {"read": ["u1"]})
    assert ok is False
    info = manager.get_session_info("term-1")
    assert info["access_acl"] == {}


def test_set_acl_filters_owner_and_admin(manager):
    # admin user_id is "admin-u" (returned by _get_admin_user_id)
    with patch.object(manager, "_get_admin_user_id", return_value="admin-u"):
        ok = manager.set_access_acl(
            "term-1",
            "owner1",
            {"read": ["owner1", "admin-u", "u1", "u1"], "interact": ["u2"]},
        )
    assert ok is True
    info = manager.get_session_info("term-1")
    # Owner and admin are filtered out, duplicates are deduplicated
    assert info["access_acl"] == {"read": ["u1"], "interact": ["u2"]}


def test_read_user_can_attach_but_not_interact(manager):
    manager.set_access_acl("term-1", "owner1", {"read": ["reader"], "interact": []})
    # attach returns "read"
    assert manager.attach_session("term-1", "session_reader") == "read"
    # Interaction check (check_access need_interact=True) returns "read", not interact level
    assert manager.check_access("term-1", "reader", need_interact=True) == "read"


def test_interact_user_can_attach_and_interact(manager):
    manager.set_access_acl("term-1", "owner1", {"read": [], "interact": ["writer"]})
    assert manager.attach_session("term-1", "session_writer") == "interact"
    assert manager.check_access("term-1", "writer", need_interact=True) == "interact"


def test_non_acl_user_rejected(manager):
    manager.set_access_acl(
        "term-1", "owner1", {"read": ["reader"], "interact": ["writer"]}
    )
    assert manager.attach_session("term-1", "session_stranger") is None
    assert manager.check_access("term-1", "stranger", need_interact=False) is None


def test_admin_and_system_are_owner(manager):
    manager.set_access_acl("term-1", "owner1", {"read": [], "interact": []})
    # system user is allowed through
    assert manager.attach_session("term-1", "system") == "owner"
    # admin user is allowed through (_is_admin_user returns True)
    with patch.object(manager, "_is_admin_user", return_value=True):
        assert manager.attach_session("term-1", "session_admin") == "owner"


def test_owner_attach_returns_owner(manager):
    assert manager.attach_session("term-1", "session_owner1") == "owner"


def test_attach_nonexistent_returns_none(manager):
    assert manager.attach_session("term-999", "session_owner1") is None


def test_list_sessions_for_user_includes_owner_and_shared(manager):
    # owner1 owns term-1; create another session shared with reader
    manager._sessions["term-2"] = _make_session(
        "term-2", "owner2", acl={"read": ["reader"], "interact": []}
    )
    # Session not shared with reader
    manager._sessions["term-3"] = _make_session("term-3", "owner3")

    # Set ACL on term-1 so reader can see it
    manager.set_access_acl("term-1", "owner1", {"read": ["reader"], "interact": []})

    sessions = manager.list_sessions_for_user("session_reader")
    ids = {s["terminal_id"]: s for s in sessions}
    # reader can see term-1 (read) and term-2 (read), cannot see term-3
    assert set(ids.keys()) == {"term-1", "term-2"}
    assert ids["term-1"]["access"] == "read"
    assert ids["term-2"]["access"] == "read"
    # Owner perspective: can see own term-1
    owner_sessions = manager.list_sessions_for_user("session_owner1")
    owner_ids = {s["terminal_id"]: s["access"] for s in owner_sessions}
    assert owner_ids["term-1"] == "owner"


def test_get_access_session_ids_includes_owner_and_acl_users(manager):
    """_get_access_session_ids should return session_ids of owner + shared (read/interact) users."""
    manager.set_access_acl(
        "term-1", "owner1", {"read": ["reader"], "interact": ["writer"]}
    )
    session = manager.get_session("term-1")
    ids = session._get_access_session_ids()
    assert "session_owner1" in ids
    assert "session_reader" in ids
    assert "session_writer" in ids
    # Deduplication: owner should not appear twice
    assert len(ids) == len(set(ids))


def test_get_access_session_ids_no_acl_only_owner(manager):
    """Without ACL, only the owner's session_id is returned."""
    session = manager.get_session("term-1")
    assert session._get_access_session_ids() == ["session_owner1"]


def test_publish_output_sends_to_all_access_users(manager):
    """_publish_output should push real-time output to owner and all shared users (fixing cross-device/sharing visibility issues)."""
    published = []

    class FakeRouter:
        def publish(self, message, session_id=None, connection_id=None):
            published.append((session_id, message.get("type")))

    manager.set_access_acl(
        "term-1", "owner1", {"read": ["reader"], "interact": ["writer"]}
    )
    session = manager.get_session("term-1")
    session.stream_publisher = FakeRouter()
    session._publish_output(b"hello realtime")

    target_sids = {sid for sid, _ in published}
    assert "session_owner1" in target_sids
    assert "session_reader" in target_sids
    assert "session_writer" in target_sids
    # Every session_id receives an execution message
    assert all(mtype == "execution" for _, mtype in published)


def test_attach_records_admin_user_for_realtime_output(manager):
    """After an admin user (different account) attaches, they should be recorded so they can receive real-time output.

    Root cause: admin users were allowed through _access_level (treated as owner), could see the terminal
    and type, but _get_access_session_ids previously only returned owner + ACL, not admin, causing
    real-time output not to be pushed to admin users (second device could not see output).
    """
    session = manager.get_session("term-1")
    # admin user attaches (_is_admin_user returns True, treated as owner)
    with patch.object(manager, "_is_admin_user", return_value=True):
        assert manager.attach_session("term-1", "session_admin2") == "owner"
    ids = session._get_access_session_ids()
    assert "session_admin2" in ids


def test_attach_records_acl_user_for_realtime_output(manager):
    """Attached ACL users should be recorded so real-time output can reach them (including shared users)."""
    manager.set_access_acl("term-1", "owner1", {"read": ["reader"], "interact": []})
    assert manager.attach_session("term-1", "session_reader") == "read"
    session = manager.get_session("term-1")
    ids = session._get_access_session_ids()
    assert "session_reader" in ids


def test_attach_rejected_user_not_recorded(manager):
    """Unauthorized users denied attach should not be recorded (to avoid leaking real-time output)."""
    manager.set_access_acl("term-1", "owner1", {"read": [], "interact": []})
    assert manager.attach_session("term-1", "session_stranger") is None
    session = manager.get_session("term-1")
    assert "session_stranger" not in session._get_access_session_ids()


def test_publish_output_sends_to_admin_after_attach(manager):
    """After an admin user attaches, _publish_output should push real-time output to them."""
    published = []

    class FakeRouter:
        def publish(self, message, session_id=None, connection_id=None):
            published.append(session_id)

    session = manager.get_session("term-1")
    with patch.object(manager, "_is_admin_user", return_value=True):
        assert manager.attach_session("term-1", "session_admin2") == "owner"
    session.stream_publisher = FakeRouter()
    session._publish_output(b"hello admin")
    assert "session_admin2" in published


def test_get_all_admin_session_ids_returns_admin_sessions(manager):
    """get_all_admin_session_ids should return session_ids of all admin users (for terminal event broadcasting)."""
    fake_users = [
        {"user_id": "admin-a", "is_admin": True},
        {"user_id": "admin-b", "is_admin": True},
        {"user_id": "normal-u", "is_admin": False},
    ]

    class FakeUserManager:
        def list_users(self, limit=50):
            return fake_users

    with patch(
        "haijunbot.haijunbot_web_gateway.user_manager.UserManager",
        return_value=FakeUserManager(),
    ):
        sids = manager.get_all_admin_session_ids()
    assert "session_admin-a" in sids
    assert "session_admin-b" in sids
    # Non-admin users should not be included
    assert "session_normal-u" not in sids


def test_get_access_session_ids_falls_back_to_session_id_for_child_node(manager):
    """When child node terminal owner_id is empty, fall back to session_id to avoid output being lost.

    Root cause: After the Bug 1 fix, _publish_output was changed to iterate over _get_access_session_ids,
    but child node terminals were created without owner_id (owner_id is empty), causing _get_access_session_ids
    to return an empty list and all output to be lost (manifesting as "only tabs and empty xterm").
    """
    # Simulate child node terminal: owner_id is empty, but session_id has a value (session_{user_id})
    session = TerminalSession(
        terminal_id="child-term",
        interpreter="bash",
        working_dir=".",
        session_id="session_owner1",
        owner_id="",
        access_acl={},
    )
    assert session._get_access_session_ids() == ["session_owner1"]


def test_publish_output_falls_back_to_session_id_for_child_node(manager):
    """For child node terminals (owner_id is empty), _publish_output should fall back to session_id to push output."""
    published = []

    class FakeRouter:
        def publish(self, message, session_id=None, connection_id=None):
            published.append(session_id)

    session = TerminalSession(
        terminal_id="child-term",
        interpreter="bash",
        working_dir=".",
        session_id="session_owner1",
        owner_id="",
        access_acl={},
    )
    session.stream_publisher = FakeRouter()
    session._publish_output(b"hello child node")
    assert "session_owner1" in published


def test_register_remote_session_appears_in_list_for_user():
    """After master registers a child node terminal shadow session, list_sessions_for_user should return it with node_id."""
    m = TerminalSessionManager()
    m.register_remote_session(
        terminal_id="child-term",
        node_id="node-2",
        owner_id="owner1",
        session_id="session_owner1",
    )
    sessions = m.list_sessions_for_user("session_owner1")
    assert any(s["terminal_id"] == "child-term" for s in sessions)
    child = next(s for s in sessions if s["terminal_id"] == "child-term")
    assert child["node_id"] == "node-2"
    assert child["owner_id"] == "owner1"
    assert child["access"] == "owner"


def test_register_remote_session_visible_to_admin():
    """Admin users should be able to see child node terminal shadow sessions registered by master (_access_level allows through)."""
    m = TerminalSessionManager()
    m.register_remote_session(
        terminal_id="child-term",
        node_id="node-2",
        owner_id="owner1",
        session_id="session_owner1",
    )
    with patch.object(TerminalSessionManager, "_is_admin_user", return_value=True):
        sessions = m.list_sessions_for_user("session_admin2")
    assert any(s["terminal_id"] == "child-term" for s in sessions)


def test_unregister_remote_session_removes():
    """unregister_session should remove the child node terminal shadow session registered by master."""
    m = TerminalSessionManager()
    m.register_remote_session(
        terminal_id="child-term",
        node_id="node-2",
        owner_id="owner1",
        session_id="session_owner1",
    )
    m.unregister_session("child-term")
    sessions = m.list_sessions_for_user("session_owner1")
    assert not any(s["terminal_id"] == "child-term" for s in sessions)


def test_register_remote_session_attach_returns_owner():
    """Shadow session (child node terminal) attach should return owner (for frontend to record on restore)."""
    m = TerminalSessionManager()
    m.register_remote_session(
        terminal_id="child-term",
        node_id="node-2",
        owner_id="owner1",
        session_id="session_owner1",
    )
    assert m.attach_session("child-term", "session_owner1") == "owner"
