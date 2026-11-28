# -*- coding: utf-8 -*-
"""Browser extension connection management: session registration, command routing, result delivery.

The Chrome/Edge extension in the user's browser proactively connects out to the gateway via WebSocket;
the gateway side uses this module to maintain sessions and dispatch Agent commands to the plugin for execution.

See section 4 of docs/design/browser-extension-agent-control.md for the protocol.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Session heartbeat timeout (seconds): sessions with no message received for longer than this are cleaned up
HEARTBEAT_TIMEOUT = 60.0

# Default timeout for a single command (seconds)
DEFAULT_COMMAND_TIMEOUT = 15.0

# Gateway-side latest-extension-version provider: returns the version number of the extension packaged with the gateway (returns None if unavailable).
# Injected by app.py at startup, to avoid coupling this module to the logic that locates the extension source directory.
LatestVersionProvider = Callable[[], Optional[str]]


class BrowserExtensionManager:
    """Manage browser extension connections and command dispatch.

    Session registry: session_id -> {
        websocket, user_id, client_id, tabs_meta, connected_at, last_seen
    }
    """

    def __init__(self) -> None:
        # session_id -> session information
        self._sessions: Dict[str, Dict[str, Any]] = {}
        # request_id -> Future, used to match command responses by id
        self._pending_commands: Dict[str, asyncio.Future] = {}
        # Heartbeat check task
        self._cleanup_task: Optional[asyncio.Task] = None
        # Provider for the latest version of the gateway-packaged extension (returns None when not injected; does not affect the handshake)
        self._latest_version_provider: Optional[LatestVersionProvider] = None

    def set_latest_version_provider(
        self, provider: Optional[LatestVersionProvider]
    ) -> None:
        """Inject the "latest version of the gateway-packaged extension" provider.

        During the handshake the result is sent down to the extension with hello_ack so it can decide whether an upgrade is needed.
        When not injected or on read failure this field is None and the extension side should ignore it.
        """
        self._latest_version_provider = provider

    def _get_latest_version(self) -> Optional[str]:
        """Read the latest version of the gateway-packaged extension; returns None when not injected or on error."""
        provider = self._latest_version_provider
        if provider is None:
            return None
        try:
            version = provider()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("[BROWSER-EXT] latest version provider failed: %s", exc)
            return None
        version = str(version or "").strip()
        return version or None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    def _ensure_cleanup_task(self) -> None:
        """Lazily start the heartbeat-timeout check task."""
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
                    logger.warning(
                        "[BROWSER-EXT] session heartbeat timeout: %s", session_id
                    )
                    await self.disconnect(session_id)
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("[BROWSER-EXT] cleanup loop error: %s", exc)

    async def handle_extension_websocket(
        self,
        websocket: WebSocket,
        user_id: Optional[str] = None,
    ) -> None:
        """Handle a plugin WebSocket connection: register the session, send/receive messages, clean up on disconnect.

        Note: authentication is performed at the endpoint layer in app.py; this method does not perform permission checks.
        ``user_id`` is passed in after being parsed from the token by the endpoint layer, and takes precedence over the user_id in the hello frame.
        """
        # The plugin uses a custom subprotocol; one must be echoed back or the browser disconnects
        await websocket.accept(subprotocol="haijunbot-ext")
        session_id = str(uuid.uuid4())
        self._ensure_cleanup_task()
        try:
            # The first frame must be hello
            try:
                first = await asyncio.wait_for(websocket.receive_json(), timeout=10)
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
            # The user_id parsed from the token by the endpoint layer takes precedence; the user_id in the hello frame is only a compatibility fallback
            session_user_id = user_id if user_id is not None else first.get("user_id")
            tabs_meta = first.get("tabs") or []
            now = time.time()
            # Terminal name: configured by the user on the HaijunBot web settings page; the extension caches it and reports it with hello,
            # so the gateway/Agent can identify the terminal by a user-readable name (falls back to hostname when empty).
            terminal_name = str(first.get("name") or "").strip()
            # The capability list reported by the extension ([{name, description, parameters, platform}]),
            # dynamically maintained on the extension side and reported with hello; the gateway passes it through for display in the frontend capability list.
            capabilities = first.get("capabilities")
            if not isinstance(capabilities, list):
                capabilities = []
            self._sessions[session_id] = {
                "websocket": websocket,
                "user_id": session_user_id,
                "client_id": client_id,
                "name": terminal_name,
                "tabs_meta": tabs_meta,
                "connected_at": now,
                "last_seen": now,
                "extension_version": first.get("extension_version"),
                "browser_info": first.get("browser_info") or {},
                "capabilities": capabilities,
            }
            logger.info(
                "[BROWSER-EXT] session connected: session_id=%s client_id=%s user_id=%s tabs=%d",
                session_id,
                client_id,
                user_id,
                len(tabs_meta),
            )

            await websocket.send_json(
                {
                    "type": "hello_ack",
                    "session_id": session_id,
                    "heartbeat_interval": 20,
                    # Latest version of the gateway-packaged extension: the extension uses this to decide whether an upgrade is needed
                    "latest_extension_version": self._get_latest_version(),
                }
            )

            # Message loop
            while True:
                message = await websocket.receive_json()
                if not isinstance(message, dict):
                    continue
                session = self._sessions.get(session_id)
                if session is not None:
                    session["last_seen"] = time.time()
                msg_type = message.get("type")
                if msg_type == "result":
                    self._handle_result(message)
                elif msg_type == "event":
                    self._handle_event(session_id, message)
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                elif msg_type == "hello":
                    # Re-handshake after reconnect: refresh session information
                    if session is not None:
                        session["tabs_meta"] = message.get("tabs") or []
                        session["client_id"] = (
                            str(message.get("client_id") or "").strip() or client_id
                        )
                        if message.get("name") is not None:
                            session["name"] = str(message.get("name") or "").strip()
                else:
                    logger.debug("[BROWSER-EXT] unknown message type: %s", msg_type)
        except Exception as exc:
            logger.info(
                "[BROWSER-EXT] session closed: session_id=%s reason=%s",
                session_id,
                exc,
            )
        finally:
            await self.disconnect(session_id)

    def _handle_result(self, message: Dict[str, Any]) -> None:
        """Deliver the command result to the waiting Future."""
        request_id = message.get("id")
        if not request_id:
            return
        future = self._pending_commands.get(request_id)
        if future is not None and not future.done():
            future.set_result(message)

    def _handle_event(self, session_id: str, message: Dict[str, Any]) -> None:
        """Handle events proactively reported by the plugin (e.g. tab changes)."""
        session = self._sessions.get(session_id)
        if session is None:
            return
        event = message.get("event")
        data = message.get("data") or {}
        if event in ("tab.created", "tab.removed", "tab.updated") and isinstance(
            data, dict
        ):
            raw_tabs = session.get("tabs_meta")
            if isinstance(raw_tabs, list):
                tabs: List[Dict[str, Any]] = [
                    t for t in raw_tabs if isinstance(t, dict)
                ]
                tab_id = data.get("tab_id")
                if event == "tab.removed":
                    tabs = [t for t in tabs if t.get("tab_id") != tab_id]
                elif event == "tab.created":
                    tabs.append(data)
                elif event == "tab.updated":
                    for idx, tab in enumerate(tabs):
                        if tab.get("tab_id") == tab_id:
                            tabs[idx] = {**tab, **data}
                            break
                session["tabs_meta"] = tabs
        logger.debug("[BROWSER-EXT] event from %s: %s", session_id, event)

    async def disconnect(self, session_id: str) -> None:
        """Close and remove the session, failing all pending commands."""
        session = self._sessions.pop(session_id, None)
        if session is None:
            return
        websocket = session.get("websocket")
        if websocket is not None:
            try:
                await websocket.close()
            except Exception:
                pass
        # Immediately fail all unfinished commands under this session
        for request_id, future in list(self._pending_commands.items()):
            if future.done():
                continue
            if getattr(future, "_browser_ext_session", None) == session_id:
                future.set_exception(
                    RuntimeError(f"session disconnected: {session_id}")
                )
                self._pending_commands.pop(request_id, None)
        logger.info("[BROWSER-EXT] session removed: %s", session_id)

    # ------------------------------------------------------------------
    # Session ownership checks
    # ------------------------------------------------------------------
    def check_session_access(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> tuple[bool, str]:
        """Check whether the caller has permission to access the specified browser extension session.

        Rules:
        - Session does not exist -> deny;
        - ``user_id`` empty, ``system``, or ``is_admin`` true -> allow (gateway-internal/admin);
        - Otherwise, the session's ``user_id`` must match the caller.

        Returns:
            (whether allowed, denial reason); the reason is an empty string when allowed.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return False, f"browser session not found: {session_id}"
        if not user_id or user_id == "system" or is_admin:
            return True, ""
        if session.get("user_id") != user_id:
            return False, "forbidden: browser session belongs to another user"
        return True, ""

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------
    async def send_command(
        self,
        session_id: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = DEFAULT_COMMAND_TIMEOUT,
        user_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> Dict[str, Any]:
        """Dispatch a command to the specified session and wait for the result.

        Raises:
            RuntimeError: session does not exist, no access permission, connection is no longer valid, or command timeout.
        """
        allowed, reason = self.check_session_access(session_id, user_id, is_admin)
        if not allowed:
            raise RuntimeError(reason)
        session = self._sessions.get(session_id)
        if session is None:
            raise RuntimeError(f"browser session not found: {session_id}")
        websocket = session.get("websocket")
        if websocket is None:
            raise RuntimeError(f"browser session has no connection: {session_id}")

        request_id = f"req-{uuid.uuid4()}"
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        # Record the owning session to allow bulk failure on disconnect
        setattr(future, "_browser_ext_session", session_id)
        self._pending_commands[request_id] = future
        try:
            logger.info(
                "[BROWSER-EXT] send command session_id=%s action=%s request_id=%s",
                session_id,
                action,
                request_id,
            )
            await websocket.send_json(
                {
                    "id": request_id,
                    "type": "command",
                    "action": action,
                    "params": params or {},
                    "timeout_ms": int(timeout * 1000),
                }
            )
            try:
                response = await asyncio.wait_for(future, timeout=timeout)
            except asyncio.TimeoutError as exc:
                raise RuntimeError(
                    f"browser command timed out: session_id={session_id}, "
                    f"action={action}, timeout={timeout}s"
                ) from exc
            if not isinstance(response, dict):
                raise RuntimeError(
                    f"invalid browser command response: session_id={session_id}, "
                    f"action={action}"
                )
            return response
        finally:
            self._pending_commands.pop(request_id, None)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def list_sessions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List currently online sessions; when user_id is provided, only that user's sessions are returned."""
        result: List[Dict[str, Any]] = []
        for session_id, session in self._sessions.items():
            if user_id is not None and session.get("user_id") != user_id:
                continue
            result.append(
                {
                    "session_id": session_id,
                    "client_id": session.get("client_id"),
                    "user_id": session.get("user_id"),
                    "name": session.get("name") or "",
                    "connected_at": session.get("connected_at"),
                    "extension_version": session.get("extension_version"),
                    "browser_info": session.get("browser_info") or {},
                    "tabs": session.get("tabs_meta") or [],
                    "capabilities": session.get("capabilities") or [],
                }
            )
        return result

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information for a single session (excluding the websocket object)."""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        return {
            "session_id": session_id,
            "client_id": session.get("client_id"),
            "user_id": session.get("user_id"),
            "name": session.get("name") or "",
            "connected_at": session.get("connected_at"),
            "extension_version": session.get("extension_version"),
            "browser_info": session.get("browser_info") or {},
            "tabs": session.get("tabs_meta") or [],
            "capabilities": session.get("capabilities") or [],
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
browser_extension_manager = BrowserExtensionManager()
