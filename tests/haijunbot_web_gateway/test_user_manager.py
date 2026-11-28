# -*- coding: utf-8 -*-
"""UserManager initial no-password security and forced password change on first login tests.

Covers:
1. When HAIJUNBOT_ADMIN_PASSWORD is not set, admin starts with no password, must_change_password=True,
   and logs contain no plaintext passwords
2. Passwordless admin can log in with an empty password
3. Admin with explicitly set HAIJUNBOT_ADMIN_PASSWORD has a password, no forced change, and requires password login
4. change_password skips old password verification for must_change_password=True users and clears the flag
5. change_password still requires old password verification for normal users
6. The login API returns a user that includes the must_change_password flag
7. The change-password API does not require the old password for must_change_password users
8. Auth interception: must_change users calling normal APIs are rejected with 403, the change-password API is allowed through, and normal access is restored after password change
"""

import logging
import os

# Must set environment variables before importing haijunbot modules to avoid triggering interactive configuration
os.environ["HAIJUNBOT_SKIP_INTERACTIVE_CONFIG"] = "1"

import pytest
from fastapi.testclient import TestClient

from haijunbot.haijunbot_web_gateway.user_manager import UserManager


# ---------------------------------------------------------------------------
# Unit tests: direct UserManager testing
# ---------------------------------------------------------------------------


def test_admin_no_password_not_logged(tmp_path, monkeypatch):
    """When HAIJUNBOT_ADMIN_PASSWORD is not set, admin has no password, must_change_password=True, and logs contain no plaintext passwords."""
    monkeypatch.delenv("HAIJUNBOT_ADMIN_PASSWORD", raising=False)

    records = []

    class _CapturingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    handler = _CapturingHandler()
    logger = logging.getLogger("haijunbot.haijunbot_web_gateway.user_manager")
    logger.addHandler(handler)
    try:
        um = UserManager(str(tmp_path))
    finally:
        logger.removeHandler(handler)

    admin = um.get_user_by_username("admin")
    assert admin is not None
    assert admin.get("is_admin") is True
    assert admin.get("must_change_password") is True

    # Logs contain no suspected plaintext passwords (16-character hex random strings)
    joined = "\n".join(records)
    assert "admin starts with no password" in joined
    import re

    assert not re.search(r"\b[0-9a-f]{16}\b", joined), f"Password was printed to logs: {joined}"


def test_admin_empty_password_login(tmp_path, monkeypatch):
    """Passwordless admin can log in with an empty password, and non-empty passwords are rejected."""
    monkeypatch.delenv("HAIJUNBOT_ADMIN_PASSWORD", raising=False)
    um = UserManager(str(tmp_path))
    # Empty password login succeeds
    assert um.authenticate("admin", "") is not None
    # Non-empty password login fails
    assert um.authenticate("admin", "anything") is None


def test_explicit_admin_password_no_must_change(tmp_path, monkeypatch):
    """When HAIJUNBOT_ADMIN_PASSWORD is explicitly set, admin has a password, no forced change, and requires password login."""
    monkeypatch.setenv("HAIJUNBOT_ADMIN_PASSWORD", "ExplicitStrongPass1!")
    um = UserManager(str(tmp_path))
    admin = um.get_user_by_username("admin")
    assert admin is not None
    assert admin.get("must_change_password") is False
    # Requires password login, empty password fails
    assert um.authenticate("admin", "") is None
    assert um.authenticate("admin", "ExplicitStrongPass1!") is not None


def test_change_password_skips_old_for_must_change(tmp_path, monkeypatch):
    """For users with must_change_password=True, skip old password verification on password change and clear the flag afterwards."""
    monkeypatch.delenv("HAIJUNBOT_ADMIN_PASSWORD", raising=False)
    um = UserManager(str(tmp_path))
    admin = um.get_user_by_username("admin")
    assert admin is not None
    assert admin.get("must_change_password") is True

    # Even with a wrong old password, the change should succeed (verification skipped)
    ok = um.change_password(admin["user_id"], "wrong-old-password", "NewStrongPass1!")
    assert ok is True

    # After password change, the flag is cleared, and login works with the new password but not the empty password
    updated = um.get_user(admin["user_id"])
    assert updated is not None
    assert updated.get("must_change_password") is False
    assert um.authenticate("admin", "NewStrongPass1!") is not None
    assert um.authenticate("admin", "") is None


def test_change_password_requires_old_for_normal_user(tmp_path, monkeypatch):
    """Normal users (must_change_password=False) still require old password verification on password change."""
    monkeypatch.setenv("HAIJUNBOT_ADMIN_PASSWORD", "ExplicitStrongPass1!")
    um = UserManager(str(tmp_path))
    um.create_user("alice", "AliceOldPass1!")

    alice = um.get_user_by_username("alice")
    assert alice is not None
    assert alice.get("must_change_password") is False

    # Wrong old password should fail
    assert um.change_password(alice["user_id"], "wrong", "NewPass1!") is False
    # Correct old password should succeed
    assert um.change_password(alice["user_id"], "AliceOldPass1!", "NewPass1!") is True
    assert um.authenticate("alice", "NewPass1!") is not None


# ---------------------------------------------------------------------------
# Integration tests: login, password change, and auth interception APIs
# ---------------------------------------------------------------------------


@pytest.fixture
def client_factory():
    """Return a factory: first create a user via UserManager, then create a TestClient.

    Users must be created before create_app(), otherwise the UserManager in-memory
    state inside the app closure will not load the new user (different UserManager
    instances each maintain their own in-memory _users).
    """

    def _make(setup=None):
        from haijunbot.haijunbot_web_gateway.user_manager import UserManager
        from haijunbot.haijunbot_utils.config import get_data_dir

        um = UserManager(get_data_dir())
        if setup:
            setup(um)
        from haijunbot.haijunbot_web_gateway.app import create_app

        return TestClient(create_app()), um

    return _make


def _login(client, username, password=""):
    """Login and return headers."""
    resp = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True, body
    token = body["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_must_change_password(client_factory):
    """The user returned by the login API should include the must_change_password flag."""

    def setup(um):
        um.create_user("bob", "", is_admin=False, must_change_password=True)

    client, _ = client_factory(setup)

    resp = client.post("/api/auth/login", json={"username": "bob", "password": ""})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["user"]["must_change_password"] is True


def test_must_change_user_blocked_until_password_set(client_factory):
    """Auth interception: must_change users calling normal APIs get 403, the change-password API is allowed through, and normal access is restored after password change."""

    def setup(um):
        um.create_user("carol", "", must_change_password=True)

    client, um = client_factory(setup)
    carol = um.get_user_by_username("carol")
    assert carol is not None

    # Login with empty password
    headers = _login(client, "carol", "")

    # Calling a normal API (get user list) should be intercepted with 403
    resp = client.get("/api/users", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "FORCE_PASSWORD_CHANGE"

    # The change-password API should be allowed through (no old password provided)
    resp = client.post(
        f"/api/users/{carol['user_id']}/change-password",
        json={"new_password": "CarolNewPass1!"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # After password change, the must_change_password flag has been cleared (reload the state from the file to verify)
    from haijunbot.haijunbot_web_gateway.user_manager import UserManager
    from haijunbot.haijunbot_utils.config import get_data_dir

    fresh = UserManager(get_data_dir())
    updated = fresh.get_user(carol["user_id"])
    assert updated is not None
    assert updated.get("must_change_password") is False

    # After password change, normal APIs are no longer intercepted by forced password change (enters normal permission check; carol is not admin so returns permission denied)
    resp = client.get("/api/users", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_change_password_api_skips_old_when_must_change(client_factory):
    """The change-password API does not require the old password for must_change_password users."""

    def setup(um):
        um.create_user("erin", "", must_change_password=True)

    client, um = client_factory(setup)
    erin = um.get_user_by_username("erin")
    assert erin is not None

    headers = _login(client, "erin", "")
    resp = client.post(
        f"/api/users/{erin['user_id']}/change-password",
        json={"new_password": "ErinNewPass1!"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_change_password_api_requires_old_for_normal(client_factory):
    """The change-password API still requires the old password for normal users."""

    def setup(um):
        um.create_user("dave", "DaveOldPass1!")

    client, um = client_factory(setup)
    dave = um.get_user_by_username("dave")
    assert dave is not None

    headers = _login(client, "dave", "DaveOldPass1!")

    # Not providing the old password should fail
    resp = client.post(
        f"/api/users/{dave['user_id']}/change-password",
        json={"new_password": "DaveNewPass1!"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is False
    assert resp.json()["error"]["code"] == "INVALID_INPUT"
