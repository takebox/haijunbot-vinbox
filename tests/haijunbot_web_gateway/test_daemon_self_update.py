# -*- coding: utf-8 -*-
"""Gateway-side daemon self-update (T5) regression tests.

Guarantees (corresponding to daemon/docs/daemon-self-update-protocol.md sections 3 and 4):
1. ``hello_ack`` carries a ``daemon_update`` field when "latest version" is configured and versions differ;
   when latest version is not configured, the key is **not** included (legacy behavior unchanged).
2. Platform/architecture resolution priority: ``build_info.os/arch`` -> ``system_info`` -> ``platform``.
3. Version comparison: same -> available=False; different -> available=True with download URL constructed.
4. Artifact naming rules: linux -> ``.tar.gz``; windows -> ``.zip``; no corresponding artifact -> available=False.
5. ``daemon.update.status`` is a one-way receipt: gateway only updates session fields and does **not** reply.

Isolation: data directory is redirected to tmp_path by ``conftest.py``'s autouse fixture;
TestClient (ASGI in-memory transport) is used throughout, no ports are listened on, no external network access.
Configuration constants are applied directly to module attributes via monkeypatch to ensure test repeatability.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from haijunbot.haijunbot_web_gateway.app import create_app
from haijunbot.haijunbot_web_gateway import daemon_capability_manager as dcm
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


# ----------------------------------------------------------------------
# Pure functions: platform/architecture resolution
# ----------------------------------------------------------------------
def test_resolve_platform_prefers_build_info():
    """build_info.os/arch takes priority over system_info / platform."""
    source = {
        "build_info": {"os": "Linux", "arch": "AMD64"},
        "system_info": {"os_name": "Ubuntu", "arch": "arm64"},
        "platform": "whatever",
    }
    assert dcm._resolve_daemon_platform(source) == ("linux", "amd64")


def test_resolve_platform_falls_back_to_system_info():
    """Fall back to system_info when build_info is missing."""
    source = {"system_info": {"os_name": "Windows", "machine": "x86_64"}}
    # x86_64 is normalized to amd64
    assert dcm._resolve_daemon_platform(source) == ("windows", "amd64")


def test_resolve_platform_falls_back_to_platform_field():
    """Fall back to top-level platform field when system_info is also missing."""
    source = {"platform": "linux"}
    os_name, arch = dcm._resolve_daemon_platform(source)
    assert os_name == "linux"
    assert arch == ""


def test_resolve_platform_missing_returns_empty():
    """Return empty strings when completely missing (caller uses this to skip update check)."""
    assert dcm._resolve_daemon_platform({}) == ("", "")
    assert dcm._resolve_daemon_platform(None) == ("", "")


def test_resolve_platform_normalizes_arch_aliases():
    """Normalize aliases like aarch64 / x64 to amd64 / arm64."""
    assert (
        dcm._resolve_daemon_platform({"build_info": {"arch": "aarch64"}})[1] == "arm64"
    )
    assert dcm._resolve_daemon_platform({"build_info": {"arch": "x64"}})[1] == "amd64"
    # ARMv7 32-bit (such as hinas ARM boxes) may report armv7l/armv7 -> normalized to arm.
    assert dcm._resolve_daemon_platform({"build_info": {"arch": "armv7l"}})[1] == "arm"
    assert dcm._resolve_daemon_platform({"build_info": {"arch": "armv7"}})[1] == "arm"
    assert dcm._resolve_daemon_platform({"build_info": {"arch": "arm"}})[1] == "arm"


# ----------------------------------------------------------------------
# Pure functions: update info construction
# ----------------------------------------------------------------------
def test_build_update_no_latest_returns_none(monkeypatch):
    """When latest version is not configured -> None (hello_ack does not carry this key)."""
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "")
    assert dcm._build_daemon_update("v1.0.0", "linux", "amd64") is None


def test_build_update_same_version_not_available(monkeypatch):
    """Same version -> available=False with note indicating already up to date."""
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "v1.2.0")
    info = dcm._build_daemon_update("v1.2.0", "linux", "amd64")
    assert info is not None
    assert info["available"] is False
    assert info["latest_version"] == "v1.2.0"
    assert info["current_version"] == "v1.2.0"
    assert info["note"]  # note is non-empty


def test_normalize_version_strips_v_prefix():
    """Normalize: strip whitespace and leading v/V."""
    assert dcm._normalize_version("v6.0.0") == "6.0.0"
    assert dcm._normalize_version("V6.0.0") == "6.0.0"
    assert dcm._normalize_version(" 6.0.0 ") == "6.0.0"
    assert dcm._normalize_version("") == ""
    assert dcm._normalize_version(None) == ""


def test_build_update_version_compare_ignores_v_prefix(monkeypatch):
    """Daemon reports with v (git tag), gateway's own version without v -> must be judged as same version.

    Otherwise it would always judge "version different" -> daemon repeatedly downloads and restarts (infinite loop).
    """
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "6.0.0")
    # Daemon reports v6.0.0 (tag injected by release build)
    info = dcm._build_daemon_update("v6.0.0", "linux", "amd64")
    assert info is not None
    assert info["available"] is False
    assert info["note"] == "already up to date"
    # Reverse: gateway has v, daemon doesn't, should also be judged as same
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "v6.0.0")
    info2 = dcm._build_daemon_update("6.0.0", "linux", "amd64")
    assert info2 is not None
    assert info2["available"] is False


def test_daemon_latest_version_comes_from_gateway_version():
    """Gateway "latest version" = gateway's own version, no longer reads environment variable."""
    from haijunbot import __version__

    assert dcm.DAEMON_LATEST_VERSION == str(__version__).strip()


def test_build_update_linux_url(monkeypatch):
    """linux -> .tar.gz, URL is in the form base/tag/asset."""
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "v1.2.0")
    monkeypatch.setattr(
        dcm, "DAEMON_RELEASE_BASE_URL", "https://github.com/o/r/releases/download"
    )
    monkeypatch.setattr(dcm, "DAEMON_ASSETS", {})
    info = dcm._build_daemon_update("v1.1.0", "linux", "amd64")
    assert info is not None
    assert info["available"] is True
    assert info["asset"] == "haijunbot-daemon_linux_amd64.tar.gz"
    assert (
        info["url"]
        == "https://github.com/o/r/releases/download/v1.2.0/haijunbot-daemon_linux_amd64.tar.gz"
    )
    assert info["current_version"] == "v1.1.0"
    assert info["latest_version"] == "v1.2.0"


def test_build_update_windows_url(monkeypatch):
    """windows -> .zip."""
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "v2.0.0")
    monkeypatch.setattr(
        dcm, "DAEMON_RELEASE_BASE_URL", "https://github.com/o/r/releases/download"
    )
    monkeypatch.setattr(dcm, "DAEMON_ASSETS", {})
    info = dcm._build_daemon_update("v1.9.0", "windows", "arm64")
    assert info is not None
    assert info["available"] is True
    assert info["asset"] == "haijunbot-daemon_windows_arm64.zip"
    assert info["url"].endswith("/v2.0.0/haijunbot-daemon_windows_arm64.zip")


def test_build_update_linux_arm(monkeypatch):
    """linux/arm (ARMv7 32-bit, such as hinas) -> match linux_arm artifact and deliver."""
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "v6.0.10")
    monkeypatch.setattr(
        dcm, "DAEMON_RELEASE_BASE_URL", "https://github.com/o/r/releases/download"
    )
    monkeypatch.setattr(dcm, "DAEMON_ASSETS", {})
    info = dcm._build_daemon_update("v6.0.9", "linux", "arm")
    assert info is not None
    assert info["available"] is True
    assert info["asset"] == "haijunbot-daemon_linux_arm.tar.gz"
    assert info["url"].endswith("/v6.0.10/haijunbot-daemon_linux_arm.tar.gz")


def test_build_update_unsupported_platform(monkeypatch):
    """macOS (no artifact) -> available=False with non-empty note."""
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "v1.2.0")
    monkeypatch.setattr(dcm, "DAEMON_ASSETS", {})
    info = dcm._build_daemon_update("v1.1.0", "darwin", "arm64")
    assert info is not None
    assert info["available"] is False
    assert info["note"]


def test_build_update_unknown_arch(monkeypatch):
    """Empty architecture (platform cannot be determined) -> None, i.e., no update info delivered."""
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "v1.2.0")
    monkeypatch.setattr(dcm, "DAEMON_ASSETS", {})
    assert dcm._build_daemon_update("v1.1.0", "linux", "") is None


def test_build_update_unsupported_arch_known_os(monkeypatch):
    """OS known but arch unsupported (like 386) -> available=False with non-empty note."""
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "v1.2.0")
    monkeypatch.setattr(dcm, "DAEMON_ASSETS", {})
    info = dcm._build_daemon_update("v1.1.0", "linux", "386")
    assert info is not None
    assert info["available"] is False
    assert info["note"]


def test_build_update_explicit_assets_override(monkeypatch):
    """Explicit assets mapping takes priority and includes sha256/size."""
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "v1.2.0")
    monkeypatch.setattr(
        dcm, "DAEMON_RELEASE_BASE_URL", "https://github.com/o/r/releases/download"
    )
    monkeypatch.setattr(
        dcm,
        "DAEMON_ASSETS",
        {
            "linux/amd64": {
                "asset": "custom-linux-amd64.tar.gz",
                "sha256": "a" * 64,
                "size": 12345,
            }
        },
    )
    info = dcm._build_daemon_update("v1.1.0", "linux", "amd64")
    assert info is not None
    assert info["available"] is True
    assert info["asset"] == "custom-linux-amd64.tar.gz"
    assert info["sha256"] == "a" * 64
    assert info["size"] == 12345
    assert info["url"].endswith("/v1.2.0/custom-linux-amd64.tar.gz")


def test_build_update_all_fields_present(monkeypatch):
    """Returned dict fields are fixed (consistent with design document)."""
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "v1.2.0")
    monkeypatch.setattr(dcm, "DAEMON_ASSETS", {})
    info = dcm._build_daemon_update("v1.1.0", "linux", "amd64")
    assert info is not None
    assert set(info.keys()) == {
        "available",
        "latest_version",
        "current_version",
        "url",
        "sha256",
        "size",
        "asset",
        "note",
    }


# ----------------------------------------------------------------------
# End-to-end: hello_ack carries / does not carry daemon_update
# ----------------------------------------------------------------------
def _hello_payload(**extra):
    payload = {
        "type": "hello",
        "client_id": "daemon-update-test",
        "extension_version": "v1.1.0",
        "build_info": {"os": "linux", "arch": "amd64"},
        "tabs": [],
    }
    payload.update(extra)
    return payload


def test_hello_ack_carries_daemon_update(client, auth_token, monkeypatch):
    """When latest version is configured and versions differ -> hello_ack carries daemon_update."""
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "v1.2.0")
    monkeypatch.setattr(
        dcm, "DAEMON_RELEASE_BASE_URL", "https://github.com/o/r/releases/download"
    )
    monkeypatch.setattr(dcm, "DAEMON_ASSETS", {})
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(_hello_payload())
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"
        # Existing fields are not affected
        assert ack["heartbeat_interval"] == 20
        assert ack["session_id"]
        # New field
        upd = ack["daemon_update"]
        assert upd["available"] is True
        assert upd["latest_version"] == "v1.2.0"
        assert upd["current_version"] == "v1.1.0"
        assert upd["asset"] == "haijunbot-daemon_linux_amd64.tar.gz"
        assert upd["url"].endswith("/v1.2.0/haijunbot-daemon_linux_amd64.tar.gz")


def test_hello_ack_omits_daemon_update_when_unconfigured(
    client, auth_token, monkeypatch
):
    """When latest version is not configured -> hello_ack does not contain daemon_update key (legacy behavior unchanged)."""
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "")
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(_hello_payload())
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"
        assert "daemon_update" not in ack


def test_hello_ack_omits_daemon_update_when_platform_unknown(
    client, auth_token, monkeypatch
):
    """When platform/architecture cannot be determined (legacy daemon without build_info) -> daemon_update is not carried."""
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "v1.2.0")
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(
            {
                "type": "hello",
                "client_id": "daemon-legacy",
                "extension_version": "v1.0.0",
                "tabs": [],
            }
        )
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"
        assert "daemon_update" not in ack


# ----------------------------------------------------------------------
# daemon.update.status one-way receipt
# ----------------------------------------------------------------------
def test_update_status_updates_session_and_no_reply(client, auth_token, monkeypatch):
    """daemon.update.status only updates session fields and does not reply."""
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "")
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(_hello_payload())
        ack = ws.receive_json()
        session_id = ack["session_id"]
        # Receipt: should not receive any reply
        ws.send_json(
            {
                "type": "daemon.update.status",
                "state": "downloading",
                "version": "v1.2.0",
                "error": "",
            }
        )
        # Use a ping/pong as a synchronization barrier: if the gateway incorrectly replied with status,
        # the message received here would be something else (assert type == pong).
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"

        manager = client.app.state.daemon_capability_manager
        session = manager.get_session(session_id)
        assert session is not None
        assert session["update_state"] is not None
        assert session["update_state"]["state"] == "downloading"
        assert session["update_state"]["version"] == "v1.2.0"
        assert session["update_state"]["error"] == ""
        assert session["update_state"]["updated_at"] > 0


def test_update_status_failed_records_error(client, auth_token, monkeypatch):
    """When state=failed, error is recorded; unknown states also do not raise errors."""
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "")
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(_hello_payload())
        ack = ws.receive_json()
        session_id = ack["session_id"]
        ws.send_json(
            {
                "type": "daemon.update.status",
                "state": "failed",
                "version": "v1.2.0",
                "error": "sha256 mismatch",
            }
        )
        ws.send_json({"type": "daemon.update.status", "state": "weird-state"})
        ws.send_json({"type": "ping"})
        assert ws.receive_json()["type"] == "pong"

        manager = client.app.state.daemon_capability_manager
        session = manager.get_session(session_id)
        # Last receipt (unknown state) is recorded, no exception raised
        assert session["update_state"]["state"] == "weird-state"
        # Session still exists (not disconnected by exception)
        assert manager.get_session(session_id) is not None


def test_update_state_default_none(client, auth_token, monkeypatch):
    """New sessions have update_state defaulting to None (no receipt received)."""
    monkeypatch.setattr(dcm, "DAEMON_LATEST_VERSION", "")
    with client.websocket_connect(
        "/api/daemon/ws", subprotocols=_token_subprotocol(auth_token)
    ) as ws:
        ws.send_json(_hello_payload())
        ack = ws.receive_json()
        manager = client.app.state.daemon_capability_manager
        session = manager.get_session(ack["session_id"])
        assert session["update_state"] is None
        # list_sessions also carries this field
        listed = manager.list_sessions()
        assert listed[0]["update_state"] is None


# ----------------------------------------------------------------------
# Configuration parsing: HAIJUNBOT_DAEMON_ASSETS
# ----------------------------------------------------------------------
def test_load_daemon_assets_parses_json(monkeypatch):
    monkeypatch.setenv(
        "HAIJUNBOT_DAEMON_ASSETS",
        '{"linux/amd64": {"asset": "a.tar.gz", "sha256": "b"}}',
    )
    assert dcm._load_daemon_assets() == {
        "linux/amd64": {"asset": "a.tar.gz", "sha256": "b"}
    }


def test_load_daemon_assets_bad_json_returns_empty(monkeypatch):
    """Invalid JSON only logs a warning, returns empty dict (does not raise an exception)."""
    monkeypatch.setenv("HAIJUNBOT_DAEMON_ASSETS", "{not json")
    assert dcm._load_daemon_assets() == {}


def test_load_daemon_assets_empty(monkeypatch):
    monkeypatch.delenv("HAIJUNBOT_DAEMON_ASSETS", raising=False)
    assert dcm._load_daemon_assets() == {}


def test_manager_isolation_no_global_state():
    """Registry/Manager has no global state: two instances do not interfere with each other (aligned with daemon-side design)."""
    m1 = DaemonCapabilityManager()
    m2 = DaemonCapabilityManager()
    assert m1 is not m2
    assert m1._sessions == {}
    assert m2._sessions == {}
