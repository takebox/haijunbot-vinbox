# -*- coding: utf-8 -*-
"""Daemon (haijunbot-daemon) connection management: session registration, capability query and invocation, result callback.

The haijunbot-daemon on the user's machine actively connects out to the gateway's
``/api/daemon/ws`` (subprotocol ``haijunbot-daemon``) via WebSocket; the gateway side uses this module to maintain the session,
and dispatches the Agent's capability invocation requests to the daemon for execution.

This is a completely independent path from the browser extension (``browser_extension_manager``):
endpoints, subprotocols, and session tables are not shared.

Protocol (aligned with daemon/internal/wsclient/client.go):
    - First frame ``hello`` (includes client_id / node_id / hostname / platform / daemon_version)
    - The gateway replies with ``hello_ack`` (includes session_id / heartbeat_interval; optional ``daemon_update``)
    - Heartbeat ``ping`` / ``pong``
    - Capability query ``capability.list`` → ``capability.list.result``
    - Capability invocation ``capability.call`` → ``capability.call.result``
    - Self-update receipt ``daemon.update.status`` (daemon → gateway, one-way, the gateway only records and does not reply)
    - Compatible with the old envelope ``command`` → ``result``
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import WebSocket

from haijunbot import __version__ as HAIJUNBOT_VERSION

logger = logging.getLogger(__name__)

# "Latest version of the browser extension packaged by the gateway" provider: returns a version string, or None if no version.
# Semantically consistent with browser_extension_manager.LatestVersionProvider.
LatestVersionProvider = Callable[[], Optional[str]]

# Session heartbeat timeout (seconds): the session is cleaned up if no message is received within this duration
HEARTBEAT_TIMEOUT = 60.0

# Timeout (seconds) for waiting for the first hello frame after the daemon connects.
#
# Why 30s (originally 10s): on Windows the daemon needs to launch PowerShell to collect complete system information (cold start takes several seconds);
# old daemons synchronously wait for collection to finish before sending hello, and the 10s limit is easily exceeded on slow machines, causing the
# daemon to be close(4400)'d and repeatedly reconnect. Widening to 30s leaves enough margin for slow machines; the new daemon already reports only
# "quick" system information in hello (millisecond level), so this widening is only a fallback.
HELLO_FIRST_FRAME_TIMEOUT = 30.0

# Default timeout for a single capability invocation (seconds)
DEFAULT_CALL_TIMEOUT = 30.0

# Default timeout for a capability list query (seconds)
DEFAULT_LIST_TIMEOUT = 15.0

# WS subprotocol used by the daemon connection
DAEMON_SUBPROTOCOL = "haijunbot-daemon"

# ---------------------------------------------------------------------------
# daemon self-update (T5): source of the "latest version" data on the gateway side
#
# "Latest version" = **the gateway's own version** (``haijunbot.__version__``). The daemon must stay on the same version as
# the gateway, so the gateway sends its own version to the daemon during the handshake, and the daemon compares it and
# unconditionally auto-updates (no switch, no environment variable).
#
#   HAIJUNBOT_DAEMON_RELEASE_BASE_URL Release download root address, defaults to this repository.
#   HAIJUNBOT_DAEMON_ASSETS           Optional, a JSON string, an explicit mapping
#                                  "os/arch" → {"asset": "...", "sha256": "...", "size": N};
#                                  when omitted, it is assembled automatically per the asset naming rules (no sha256).
# ---------------------------------------------------------------------------

# This repository's owner/repo (source: pyproject.toml:144 Homepage / README.md:268).
DAEMON_RELEASE_OWNER_REPO = "takebox/HaijunBot"

# Default download root address: https://github.com/<owner>/<repo>/releases/download
DAEMON_RELEASE_BASE_URL = os.environ.get(
    "HAIJUNBOT_DAEMON_RELEASE_BASE_URL",
    f"https://github.com/{DAEMON_RELEASE_OWNER_REPO}/releases/download",
).rstrip("/")

# Latest version number = the gateway's own version; the daemon and the gateway always stay on the same version.
DAEMON_LATEST_VERSION = str(HAIJUNBOT_VERSION or "").strip()

# Supported platform/arch (consistent with the build matrix of .github/workflows/release-daemon.yml; no macOS).
# Note: arm = ARMv7 32-bit (e.g. the ARMv7 box of hinas); the release matrix builds linux/arm.
DAEMON_SUPPORTED_OS = ("linux", "windows")
DAEMON_SUPPORTED_ARCH = ("amd64", "arm64", "arm")


def _load_daemon_assets() -> Dict[str, Dict[str, Any]]:
    """Parse the ``HAIJUNBOT_DAEMON_ASSETS`` environment variable into an explicit asset mapping.

    Expected format (JSON string)::

        {"linux/amd64": {"asset": "haijunbot-daemon_linux_amd64.tar.gz",
                         "sha256": "…", "size": 12345678}}

    A parse failure only logs a warning and returns an empty dictionary (no exception is thrown, to avoid affecting the daemon connection).
    """
    raw = os.environ.get("HAIJUNBOT_DAEMON_ASSETS", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError) as exc:
        logger.warning("[DAEMON] failed to parse HAIJUNBOT_DAEMON_ASSETS, ignoring: %s", exc)
        return {}
    if not isinstance(parsed, dict):
        logger.warning("[DAEMON] HAIJUNBOT_DAEMON_ASSETS is not an object, ignoring")
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    for key, value in parsed.items():
        if isinstance(value, dict):
            result[str(key)] = value
    return result


# Explicit asset mapping (os/arch → {asset, sha256, size}); empty by default, assembled by naming rules.
DAEMON_ASSETS: Dict[str, Dict[str, Any]] = _load_daemon_assets()


def _daemon_asset_name(os_name: str, arch: str) -> str:
    """Assemble the asset name according to the Release asset naming rules (see release-daemon.yml:100-107).

    Linux → ``haijunbot-daemon_linux_<arch>.tar.gz``;
    Windows → ``haijunbot-daemon_windows_<arch>.zip``;
    Other platforms (including macOS) → empty string (no asset).
    """
    if os_name == "linux":
        return f"haijunbot-daemon_linux_{arch}.tar.gz"
    if os_name == "windows":
        return f"haijunbot-daemon_windows_{arch}.zip"
    return ""


def _resolve_daemon_platform(source: Any) -> Tuple[str, str]:
    """Parse (os, arch) from the session (or the hello frame), lowercased uniformly.

    Value priority:
      os:   build_info.os → system_info.os_name → system_info.platform → platform
      arch: build_info.arch → system_info.arch → system_info.machine

    When it cannot be determined, the corresponding item returns an empty string (the caller skips the update check accordingly).
    """
    if not isinstance(source, dict):
        return "", ""
    build_info = source.get("build_info") or {}
    if not isinstance(build_info, dict):
        build_info = {}
    system_info = source.get("system_info") or {}
    if not isinstance(system_info, dict):
        system_info = {}

    os_name = (
        str(
            build_info.get("os")
            or system_info.get("os_name")
            or system_info.get("platform")
            or source.get("platform")
            or ""
        )
        .strip()
        .lower()
    )
    arch = (
        str(
            build_info.get("arch")
            or system_info.get("arch")
            or system_info.get("machine")
            or ""
        )
        .strip()
        .lower()
    )

    # Normalize common aliases so that the daemon's "x86_64"/"aarch64" reports can match an asset.
    arch_alias = {
        "x86_64": "amd64",
        "x64": "amd64",
        "aarch64": "arm64",
        # ARMv7 32-bit (e.g. Raspberry Pi 2/3 32-bit systems, ARM boxes) may report armv7l/armv7; normalize to arm.
        "armv7l": "arm",
        "armv7": "arm",
        "armhf": "arm",
    }
    arch = arch_alias.get(arch, arch)
    return os_name, arch


def _normalize_version(value: Any) -> str:
    """Normalize a version string for comparison: strip whitespace and a leading ``v``/``V``.

    The daemon's version comes from a git tag (such as ``v5.0.5``), while the gateway's own version is ``6.0.0`` (without a v).
    The two formats are inconsistent, so a direct string comparison would always judge them as "different versions", causing the daemon to
    repeatedly download and restart. Therefore normalize uniformly before comparison.
    """
    text = str(value or "").strip()
    if text[:1] in ("v", "V"):
        text = text[1:].strip()
    return text


def _release_tag(version: Any) -> str:
    """Convert a version number into a GitHub Release tag.

    Why this is needed: the gateway's own version is ``6.0.1`` (without v), while the Release tag is
    injected by ``release-daemon.yml``'s ``github.ref_name``, actually of the form ``v6.0.1``.
    Directly assembling the download URL from the version number gives ``/download/6.0.1/...``, and GitHub returns 404.
    So normalize first (remove any existing v prefix to avoid assembling ``vv6.0.1``) and then add ``v``.
    """
    return f"v{_normalize_version(version)}"


def _build_daemon_update(
    daemon_version: str, os_name: str, arch: str
) -> Optional[Dict[str, Any]]:
    """Construct the ``daemon_update`` field of hello_ack.

    Returning None means "do not send" (the gateway's own version is missing, or the platform/arch cannot be determined) —
    in this case hello_ack does not carry this key, exactly matching the old behavior.
    Otherwise returns a dict with fixed fields (field names matching design doc 3.2 word for word).
    """
    latest = DAEMON_LATEST_VERSION
    if not latest:
        # The gateway's own version is missing → do not send any update information.
        return None
    if not os_name or not arch:
        # Platform/arch cannot be determined (old daemon) → skip the update check and do not disturb the connection.
        return None

    current = str(daemon_version or "").strip()
    info: Dict[str, Any] = {
        "available": False,
        "latest_version": latest,
        "current_version": current,
        "url": "",
        "sha256": "",
        "size": 0,
        "asset": "",
        "note": "",
    }

    # Versions match (after normalization) → already up to date; available=false with the reason explained.
    if _normalize_version(current) == _normalize_version(latest):
        info["note"] = "already up to date"
        return info

    # Platform/arch is not supported (e.g. macOS) → available=false with an explanation.
    if os_name not in DAEMON_SUPPORTED_OS or arch not in DAEMON_SUPPORTED_ARCH:
        info["note"] = f"no release asset for {os_name}/{arch}"
        return info

    # Explicit mapping takes priority; otherwise assemble by naming rules.
    explicit = DAEMON_ASSETS.get(f"{os_name}/{arch}") or {}
    asset = str(explicit.get("asset") or "").strip() or _daemon_asset_name(
        os_name, arch
    )
    if not asset:
        info["note"] = f"no release asset for {os_name}/{arch}"
        return info

    info["available"] = True
    info["asset"] = asset
    info["url"] = f"{DAEMON_RELEASE_BASE_URL}/{_release_tag(latest)}/{asset}"
    info["sha256"] = str(explicit.get("sha256") or "").strip()
    try:
        info["size"] = int(explicit.get("size") or 0)
    except (TypeError, ValueError):
        info["size"] = 0
    if not info["sha256"]:
        # sha256 not configured: the daemon side skips verification and logs a warning (see design doc 3.4).
        info["note"] = "sha256 not configured; daemon will skip verification"
    return info


class DaemonCapabilityManager:
    """Manage daemon connections and capability invocation.

    Session registry: session_id -> {
        websocket, user_id, client_id, node_id, hostname, platform,
        daemon_version, capabilities, connected_at, last_seen
    }

    ``user_id`` is parsed by the gateway from the token in the WS subprotocol and used for multi-user isolation: session ownership must be verified
    before a capability query/invocation to prevent any valid token from executing local capabilities across users.
    """

    def __init__(self) -> None:
        # Main event loop (bound by the gateway at lifespan startup, used for cross-thread calls)
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        # session_id -> session information
        self._sessions: Dict[str, Dict[str, Any]] = {}
        # request_id -> Future, used to match capability invocation responses by id
        self._pending_calls: Dict[str, asyncio.Future] = {}
        # session_id -> Future, used to match capability list responses that have no id
        self._pending_lists: Dict[str, asyncio.Future] = {}
        # Heartbeat inspection task
        self._cleanup_task: Optional[asyncio.Task] = None
        # Latest version provider for the extension packaged by the gateway (returns None when not injected, does not affect the handshake)
        self._latest_version_provider: Optional[LatestVersionProvider] = None

    def set_latest_version_provider(
        self, provider: Optional[LatestVersionProvider]
    ) -> None:
        """Inject the "latest version of the browser extension packaged by the gateway" provider.

        During the handshake, the result is sent to the daemon along with hello_ack's ``latest_extension_version``,
        so that it can decide whether to sync the extension when the "auto install/update browser extension" switch is on.
        When not injected or on a read failure, this field is not sent and the daemon side should ignore it (matching the old behavior).
        """
        self._latest_version_provider = provider

    def _get_latest_extension_version(self) -> Optional[str]:
        """Read the latest version of the extension packaged by the gateway; returns None when not injected or on an exception."""
        provider = self._latest_version_provider
        if provider is None:
            return None
        try:
            version = provider()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("[DAEMON] latest version provider failed: %s", exc)
            return None
        version = str(version or "").strip()
        return version or None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    def _ensure_cleanup_task(self) -> None:
        """Lazily start the heartbeat timeout inspection task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
            self._cleanup_task = loop.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """Periodically clean up sessions whose heartbeat has timed out."""
        try:
            while True:
                await asyncio.sleep(10)
                now = time.time()
                stale: List[str] = []
                for session_id, session in list(self._sessions.items()):
                    last_seen = session.get("last_seen") or session.get(
                        "connected_at", now
                    )
                    if now - last_seen > HEARTBEAT_TIMEOUT:
                        stale.append(session_id)
                for session_id in stale:
                    logger.warning("[DAEMON] session heartbeat timeout: %s", session_id)
                    await self.disconnect(session_id)
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("[DAEMON] cleanup loop error: %s", exc)

    async def handle_daemon_websocket(
        self,
        websocket: WebSocket,
        user_id: Optional[str] = None,
    ) -> None:
        """Handle the daemon WebSocket connection: register the session, send/receive messages, and clean up on disconnect.

        Note: authentication is done at the endpoint layer in app.py; this method does not perform permission checks;
        ``user_id`` is passed in by the endpoint layer after parsing it from the token, and is used for subsequent session ownership checks.
        """
        # The daemon uses a custom subprotocol; it must be echoed back or the client will disconnect
        await websocket.accept(subprotocol=DAEMON_SUBPROTOCOL)
        session_id = str(uuid.uuid4())
        self._ensure_cleanup_task()
        try:
            # The first frame must be hello
            #
            # Timeout widened to 30s (originally 10s): on Windows the daemon needs to launch PowerShell to collect complete
            # system information (cold start takes several seconds); if the first hello frame waits for collection to finish,
            # the 10s limit is easily exceeded on slow machines, causing the daemon to be close(4400)'d and repeatedly reconnect.
            # After widening, there is enough margin for slow machines; the new daemon already reports "quick" system information
            # in hello (millisecond level), and this widening is only a fallback for old daemons.
            try:
                first = await asyncio.wait_for(
                    websocket.receive_json(), timeout=HELLO_FIRST_FRAME_TIMEOUT
                )
            except Exception:
                await self._send_error(
                    websocket, "INVALID_MESSAGE", "first message must be hello"
                )
                await websocket.close(code=4400)
                return
            if not isinstance(first, dict) or first.get("type") != "hello":
                await self._send_error(
                    websocket, "INVALID_MESSAGE", "first message must be hello"
                )
                await websocket.close(code=4400)
                return

            client_id = str(first.get("client_id") or "").strip() or session_id
            # The daemon reports system information for itself (the user-side service); browser information is reported
            # separately by the browser extension and is not handled here. Backward compatible: the old version put hostname/platform in
            # browser_info, so that fallback path is still retained.
            system_info = first.get("system_info") or {}
            if not isinstance(system_info, dict):
                system_info = {}
            browser_info = first.get("browser_info") or {}
            if not isinstance(browser_info, dict):
                browser_info = {}
            hostname = str(
                system_info.get("hostname") or browser_info.get("hostname") or ""
            ).strip()
            # Terminal name: configured by the user on the HaijunBot web settings page, pushed to the daemon by the frontend,
            # and carried by the daemon in hello. Used to let the gateway/Agent identify the terminal by a user-readable name.
            # Falls back to hostname when empty (the old daemon does not carry this field).
            terminal_name = str(first.get("name") or "").strip() or hostname
            now = time.time()
            # After a daemon restart on the same machine, client_id changes (contains the PID); the old connection remains
            # in the session table until the heartbeat timeout (up to about 70s), causing ghost entries in list_sessions and
            # capability invocations possibly being routed to a dead old connection. Here (user_id, hostname) is used as a
            # stable identity, and old sessions on the same machine are proactively cleaned up before registering a new session.
            # When hostname is empty, the identity cannot be reliably determined, so no cleanup is done to avoid killing valid sessions.
            if hostname:
                await self._replace_stale_sessions(session_id, user_id, hostname)
            # The daemon may directly carry the capability list in hello (the new daemon does so).
            # This way the session has capabilities as soon as it is registered, without relying on a runtime capability.list round trip;
            # when the old daemon does not carry this field, it falls back to an empty list and can still be fetched via an active query.
            hello_capabilities = first.get("capabilities")
            if not isinstance(hello_capabilities, list):
                hello_capabilities = []
            # The daemon may carry build information in hello (version/build time/Go version/target platform).
            # The build time comes from the daemon exe's mtime (see daemon/internal/buildinfo).
            # When the old daemon does not carry this field, it falls back to an empty dictionary.
            hello_build_info = first.get("build_info")
            if not isinstance(hello_build_info, dict):
                hello_build_info = {}
            self._sessions[session_id] = {
                "websocket": websocket,
                "user_id": user_id,
                "client_id": client_id,
                "node_id": str(first.get("node_id") or "").strip() or client_id,
                "hostname": str(
                    system_info.get("hostname") or browser_info.get("hostname") or ""
                ).strip(),
                "name": terminal_name,
                "platform": str(
                    system_info.get("os_name")
                    or system_info.get("platform")
                    or browser_info.get("platform")
                    or ""
                ).strip(),
                "system_info": system_info,
                "daemon_version": first.get("extension_version"),
                "build_info": hello_build_info,
                "capabilities": hello_capabilities,
                "connected_at": now,
                "last_seen": now,
                # Self-update progress (written by the daemon.update.status receipt; None when there is no receipt).
                "update_state": None,
            }
            logger.info(
                "[DAEMON] session connected: session_id=%s client_id=%s node_id=%s user_id=%s",
                session_id,
                client_id,
                self._sessions[session_id]["node_id"],
                user_id,
            )
            # Diagnostic log: facilitates end-to-end troubleshooting of "whether system information was received".
            # If system_info is empty here, the daemon did not report it or the reported field names do not match;
            # if it has a value here but /api/daemon/sessions cannot see it, the problem is in the return layer.
            logger.info(
                "[DAEMON] hello system_info: received=%s hostname=%r platform=%r fields=%d",
                bool(system_info),
                self._sessions[session_id]["hostname"],
                self._sessions[session_id]["platform"],
                len(system_info),
            )

            # Self-update check: compare the "latest version" with the version/arch reported by the daemon,
            # and send the result with hello_ack (additive only; old daemons can just ignore it).
            # When the latest version is not configured or the platform cannot be determined, it returns None → the key is not carried,
            # ensuring the old fields and old behavior remain completely unchanged.
            daemon_os, daemon_arch = _resolve_daemon_platform(
                self._sessions[session_id]
            )
            daemon_update = _build_daemon_update(
                self._sessions[session_id].get("daemon_version") or "",
                daemon_os,
                daemon_arch,
            )
            hello_ack: Dict[str, Any] = {
                "type": "hello_ack",
                "session_id": session_id,
                "heartbeat_interval": 20,
            }
            if daemon_update is not None:
                hello_ack["daemon_update"] = daemon_update
                logger.info(
                    "[DAEMON] update check: session_id=%s current=%s latest=%s "
                    "os=%s arch=%s available=%s note=%s",
                    session_id,
                    daemon_update.get("current_version"),
                    daemon_update.get("latest_version"),
                    daemon_os,
                    daemon_arch,
                    daemon_update.get("available"),
                    daemon_update.get("note"),
                )
            await websocket.send_json(hello_ack)

            # Message loop
            while True:
                message = await websocket.receive_json()
                if not isinstance(message, dict):
                    continue
                session = self._sessions.get(session_id)
                if session is not None:
                    session["last_seen"] = time.time()
                msg_type = message.get("type")
                if msg_type == "capability.list.result":
                    self._handle_capability_list_result(session_id, message)
                elif msg_type == "capability.call.result":
                    self._handle_capability_call_result(message)
                elif msg_type == "daemon.update.status":
                    # Self-update progress receipt (one-way): only logs and updates the session field,
                    # **never replies** (the daemon does not wait; old gateways that ignore it at debug level are also compatible).
                    state = str(message.get("state") or "").strip()
                    version = str(message.get("version") or "").strip()
                    error = str(message.get("error") or "").strip()
                    if session is not None:
                        session["update_state"] = {
                            "state": state,
                            "version": version,
                            "error": error,
                            "updated_at": time.time(),
                        }
                    logger.info(
                        "[DAEMON] update status: session_id=%s state=%s version=%s error=%s",
                        session_id,
                        state or "?",
                        version or "?",
                        error or "",
                    )
                elif msg_type == "system_info_update":
                    # System information incremental resend (one-way): the daemon's first hello frame carries only "quick"
                    # system information (millisecond level, to avoid handshake timeout); the complete information (OS version/memory/uptime,
                    # etc.) is subsequently resent with this message. It is merged into the session cache here so that
                    # /api/daemon/sessions can reflect the complete information. **Never replies** (the daemon does not
                    # wait; old gateways that ignore unknown types are also compatible).
                    update = message.get("system_info")
                    if isinstance(update, dict) and session is not None:
                        merged = session.get("system_info")
                        if not isinstance(merged, dict):
                            merged = {}
                        merged.update(update)
                        session["system_info"] = merged
                        # Also refresh the derived fields used for display (kept consistent with registration in hello).
                        hostname = str(merged.get("hostname") or "").strip()
                        if hostname:
                            session["hostname"] = hostname
                        platform = str(
                            merged.get("os_name") or merged.get("platform") or ""
                        ).strip()
                        if platform:
                            session["platform"] = platform
                        logger.info(
                            "[DAEMON] system_info_update: session_id=%s fields=%d",
                            session_id,
                            len(update),
                        )
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                elif msg_type == "hello":
                    # Re-handshake after reconnect: refresh the session information
                    if session is not None:
                        session["client_id"] = (
                            str(message.get("client_id") or "").strip() or client_id
                        )
                        session["node_id"] = (
                            str(message.get("node_id") or "").strip()
                            or session["client_id"]
                        )
                else:
                    logger.debug("[DAEMON] unknown message type: %s", msg_type)
        except Exception as exc:
            logger.info(
                "[DAEMON] session closed: session_id=%s reason=%s",
                session_id,
                exc,
            )
        finally:
            await self.disconnect(session_id)

    def _handle_capability_list_result(
        self, session_id: str, message: Dict[str, Any]
    ) -> None:
        """Cache the capability list and wake up any pending query."""
        capabilities = message.get("capabilities")
        if not isinstance(capabilities, list):
            capabilities = []
        session = self._sessions.get(session_id)
        if session is not None:
            session["capabilities"] = capabilities
        future = self._pending_lists.get(session_id)
        if future is not None and not future.done():
            future.set_result(capabilities)

    def _handle_capability_call_result(self, message: Dict[str, Any]) -> None:
        """Deliver the capability invocation result to the waiting Future."""
        request_id = message.get("id")
        if not request_id:
            return
        future = self._pending_calls.get(request_id)
        if future is not None and not future.done():
            future.set_result(message)

    async def _replace_stale_sessions(
        self,
        new_session_id: str,
        user_id: Optional[str],
        hostname: str,
    ) -> None:
        """Clean up old sessions left over on the same machine (same user_id + same hostname).

        After a daemon restart, ``client_id`` changes (contains the PID), and the old connection remains
        in the session table until the heartbeat timeout. Using ``(user_id, hostname)`` as a stable identity,
        old sessions are disconnected together before registering a new session, avoiding ghost entries and misrouted invocations.
        """
        stale: List[str] = []
        for session_id, session in list(self._sessions.items()):
            if session_id == new_session_id:
                continue
            if session.get("user_id") != user_id:
                continue
            if str(session.get("hostname") or "").strip() != hostname:
                continue
            stale.append(session_id)
        for session_id in stale:
            logger.info(
                "[DAEMON] replace stale session: old=%s new=%s hostname=%s",
                session_id,
                new_session_id,
                hostname,
            )
            await self.disconnect(session_id)

    async def disconnect(self, session_id: str) -> None:
        """Close and remove the session, and fail all pending invocations."""
        session = self._sessions.pop(session_id, None)
        if session is None:
            return
        websocket = session.get("websocket")
        if websocket is not None:
            try:
                await websocket.close()
            except Exception:
                pass
        # All incomplete invocations under this session fail immediately
        for request_id, future in list(self._pending_calls.items()):
            if future.done():
                continue
            if getattr(future, "_daemon_session", None) == session_id:
                future.set_exception(
                    RuntimeError(f"daemon session disconnected: {session_id}")
                )
                self._pending_calls.pop(request_id, None)
        list_future = self._pending_lists.pop(session_id, None)
        if list_future is not None and not list_future.done():
            list_future.set_exception(
                RuntimeError(f"daemon session disconnected: {session_id}")
            )
        logger.info("[DAEMON] session removed: %s", session_id)

    # ------------------------------------------------------------------
    # Session ownership verification
    # ------------------------------------------------------------------
    def check_session_access(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> tuple[bool, str]:
        """Verify whether the caller is allowed to access the specified daemon session.

        Rules:
        - Session does not exist → deny;
        - ``user_id`` is empty, is ``system``, or ``is_admin`` is true → allow (gateway internal/administrator);
        - Otherwise, the session's ``user_id`` must match the caller.

        Returns:
            (allowed, denial reason); the reason is an empty string when allowed.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return False, f"daemon session not found: {session_id}"
        if not user_id or user_id == "system" or is_admin:
            return True, ""
        if session.get("user_id") != user_id:
            return False, "forbidden: daemon session belongs to another user"
        return True, ""

    # ------------------------------------------------------------------
    # Capability query and invocation
    # ------------------------------------------------------------------
    async def list_capabilities(
        self,
        session_id: str,
        timeout: float = DEFAULT_LIST_TIMEOUT,
        user_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> List[Dict[str, Any]]:
        """Query the capability list of the specified daemon.

        Raises:
            RuntimeError: The session does not exist, access is denied, the connection is dead, or the query timed out.
        """
        allowed, reason = self.check_session_access(session_id, user_id, is_admin)
        if not allowed:
            raise RuntimeError(reason)
        session = self._sessions.get(session_id)
        if session is None:
            raise RuntimeError(f"daemon session not found: {session_id}")
        websocket = session.get("websocket")
        if websocket is None:
            raise RuntimeError(f"daemon session has no connection: {session_id}")

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending_lists[session_id] = future
        try:
            logger.info("[DAEMON] list capabilities session_id=%s", session_id)
            await websocket.send_json({"type": "capability.list"})
            try:
                capabilities = await asyncio.wait_for(future, timeout=timeout)
            except asyncio.TimeoutError as exc:
                raise RuntimeError(
                    f"daemon capability list timed out: session_id={session_id}, "
                    f"timeout={timeout}s"
                ) from exc
            return list(capabilities or [])
        finally:
            self._pending_lists.pop(session_id, None)

    async def call_capability(
        self,
        session_id: str,
        name: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = DEFAULT_CALL_TIMEOUT,
        user_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> Dict[str, Any]:
        """Invoke one capability of the specified daemon and wait for the result.

        Returns:
            dict: {"success": bool, "data": any, "error": str}

        Raises:
            RuntimeError: The session does not exist, access is denied, the connection is dead, or the invocation timed out.
        """
        allowed, reason = self.check_session_access(session_id, user_id, is_admin)
        if not allowed:
            raise RuntimeError(reason)
        session = self._sessions.get(session_id)
        if session is None:
            raise RuntimeError(f"daemon session not found: {session_id}")
        websocket = session.get("websocket")
        if websocket is None:
            raise RuntimeError(f"daemon session has no connection: {session_id}")

        call_id = f"call-{uuid.uuid4()}"
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        # Record the owning session to facilitate batch failure on disconnect
        setattr(future, "_daemon_session", session_id)
        self._pending_calls[call_id] = future
        try:
            logger.info(
                "[DAEMON] call capability session_id=%s name=%s call_id=%s",
                session_id,
                name,
                call_id,
            )
            await websocket.send_json(
                {
                    "type": "capability.call",
                    "id": call_id,
                    "name": name,
                    "params": params or {},
                }
            )
            try:
                response = await asyncio.wait_for(future, timeout=timeout)
            except asyncio.TimeoutError as exc:
                raise RuntimeError(
                    f"daemon capability call timed out: session_id={session_id}, "
                    f"name={name}, timeout={timeout}s"
                ) from exc
            if not isinstance(response, dict):
                raise RuntimeError(
                    f"invalid daemon capability response: session_id={session_id}, "
                    f"name={name}"
                )
            return {
                "success": bool(response.get("success")),
                "data": response.get("data"),
                "error": response.get("error") or "",
            }
        finally:
            self._pending_calls.pop(call_id, None)

    def set_event_loop(self, event_loop: asyncio.AbstractEventLoop) -> None:
        """Bind the main event loop used for cross-thread capability calls (called at gateway lifespan startup)."""
        self._event_loop = event_loop

    def call_capability_threadsafe(
        self,
        session_id: str,
        name: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = DEFAULT_CALL_TIMEOUT,
        user_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> Dict[str, Any]:
        """Safely invoke a daemon capability in a threaded environment (such as a scheduled task callback).

        Using ``run_coroutine_threadsafe``, the asynchronous ``call_capability`` is submitted to
        the main event loop for execution, and the result is awaited synchronously. Suitable for invoking
        capabilities in a thread without an event loop (such as the TimerManager's worker thread).

        Raises:
            RuntimeError: The main event loop is not bound, or the capability invocation itself failed/timed out.
        """
        if self._event_loop is None:
            raise RuntimeError("DaemonCapabilityManager event loop is not set")
        future = asyncio.run_coroutine_threadsafe(
            self.call_capability(
                session_id,
                name,
                params=params,
                timeout=timeout,
                user_id=user_id,
                is_admin=is_admin,
            ),
            self._event_loop,
        )
        return future.result()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def list_sessions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List currently online daemon sessions; when user_id is passed, only that user's sessions are returned."""
        result: List[Dict[str, Any]] = []
        for session_id, session in self._sessions.items():
            if user_id is not None and session.get("user_id") != user_id:
                continue
            result.append(
                {
                    "session_id": session_id,
                    "client_id": session.get("client_id"),
                    "user_id": session.get("user_id"),
                    "node_id": session.get("node_id"),
                    "hostname": session.get("hostname"),
                    "name": session.get("name") or session.get("hostname"),
                    "platform": session.get("platform"),
                    "system_info": session.get("system_info") or {},
                    "daemon_version": session.get("daemon_version"),
                    "build_info": session.get("build_info") or {},
                    "capabilities": session.get("capabilities") or [],
                    "connected_at": session.get("connected_at"),
                    "update_state": session.get("update_state"),
                }
            )
        return result

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a single session's information (excluding the websocket object)."""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        return {
            "session_id": session_id,
            "client_id": session.get("client_id"),
            "user_id": session.get("user_id"),
            "node_id": session.get("node_id"),
            "hostname": session.get("hostname"),
            "name": session.get("name") or session.get("hostname"),
            "platform": session.get("platform"),
            "system_info": session.get("system_info") or {},
            "daemon_version": session.get("daemon_version"),
            "build_info": session.get("build_info") or {},
            "capabilities": session.get("capabilities") or [],
            "connected_at": session.get("connected_at"),
            "update_state": session.get("update_state"),
        }

    # ------------------------------------------------------------------
    # Utility functions
    # ------------------------------------------------------------------
    @staticmethod
    async def _send_error(websocket: WebSocket, code: str, message: str) -> None:
        try:
            await websocket.send_json(
                {"type": "error", "payload": {"code": code, "message": message}}
            )
        except Exception:
            pass


# Global singleton, shared by app.py and the tool layer
daemon_capability_manager = DaemonCapabilityManager()
