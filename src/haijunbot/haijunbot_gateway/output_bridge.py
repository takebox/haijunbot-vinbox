# -*- coding: utf-8 -*-
"""Bridge implementation from output events to WebSocket/gateway messages.

This module deliberately does not depend on any specific WebSocket framework, and provides:
1. OutputEvent -> structured message serialization;
2. A pluggable message publisher abstraction;
3. A WebSocketOutputSink based on OutputSink;
4. A minimal session/broadcast-oriented router implementation.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from datetime import datetime, timezone
from itertools import count
import threading
from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional

from haijunbot.haijunbot_utils.output import OUTPUT_ICONS
from haijunbot.haijunbot_utils.output import OutputEvent
from haijunbot.haijunbot_utils.output import OutputSink


class OutputMessagePublisher(ABC):
    """Structured output message publisher abstraction."""

    @abstractmethod
    def publish(
        self, message: Dict[str, Any], session_id: Optional[str] = None
    ) -> None:
        raise NotImplementedError


class SessionOutputRouter(OutputMessagePublisher):
    """Minimal session output router.

    - When session_id is None, performs a broadcast;
    - When session_id has a value, routes only to the target session's subscribers;
    - Subscribers use a callback abstraction, which can later be adapted to real WebSocket connection objects.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: Dict[str, Dict[str, Callable[[Dict[str, Any]], None]]] = {}

    def register(
        self,
        connection_id: str,
        sender: Callable[[Dict[str, Any]], None],
        session_id: Optional[str] = None,
    ) -> None:
        route_key = session_id or "*"
        with self._lock:
            subscribers = self._subscribers.setdefault(route_key, {})
            subscribers[connection_id] = sender

    def unregister(self, connection_id: str, session_id: Optional[str] = None) -> None:
        route_key = session_id or "*"
        with self._lock:
            subscribers = self._subscribers.get(route_key)
            if not subscribers:
                return
            subscribers.pop(connection_id, None)
            if not subscribers:
                self._subscribers.pop(route_key, None)

    def unregister_all_session(self, session_id: Optional[str] = None) -> None:
        """Disconnect all connections of the specified session.

        Args:
            session_id: Session ID; if None, disconnects all sessions
        """
        route_key = session_id or "*"
        with self._lock:
            if session_id is None:
                # Disconnect all connections
                self._subscribers.clear()
            else:
                # Disconnect all connections of the specified session
                self._subscribers.pop(route_key, None)

    def publish(
        self,
        message: Dict[str, Any],
        session_id: Optional[str] = None,
        connection_id: Optional[str] = None,
    ) -> None:
        callbacks: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        with self._lock:
            if connection_id is not None:
                # Connection-level targeting: exactly match this connection_id only under the target session
                for route_key in self._resolve_route_keys(session_id):
                    sender = self._subscribers.get(route_key, {}).get(connection_id)
                    if sender is not None:
                        callbacks[connection_id] = sender
                        break
            else:
                for route_key in self._resolve_route_keys(session_id):
                    callbacks.update(self._subscribers.get(route_key, {}))

        if not callbacks:
            return

        for sender in callbacks.values():
            try:
                sender(dict(message))
            except Exception:
                pass

    def _resolve_route_keys(self, session_id: Optional[str]) -> list[str]:
        if session_id is None:
            # Broadcast mode: send to all session subscribers + wildcard subscribers
            with self._lock:
                keys = list(self._subscribers.keys())
                if "*" not in keys:
                    keys.append("*")
                return keys
        if session_id:
            return [session_id, "*"]
        return ["*"]

    def has_active_subscribers(self) -> bool:
        """Check whether there are active subscriber connections."""
        with self._lock:
            return bool(self._subscribers)

    def has_connection(
        self, connection_id: str, session_id: Optional[str] = None
    ) -> bool:
        """Check whether the specified connection is online (optionally scoped to a session)."""
        with self._lock:
            for route_key in self._resolve_route_keys(session_id):
                if connection_id in self._subscribers.get(route_key, {}):
                    return True
            return False


def serialize_output_event(
    event: OutputEvent,
    *,
    sequence: Optional[int] = None,
    source: str = "haijunbot.output",
) -> Dict[str, Any]:
    """Serialize an OutputEvent into a structured message that can be sent over WebSocket."""

    payload: Dict[str, Any] = {
        "type": "output",
        "source": source,
        "emitted_at": datetime.now(timezone.utc)
        .replace(tzinfo=None)
        .isoformat(timespec="milliseconds")
        + "Z",
        "output_type": event.output_type.value,
        "icon": OUTPUT_ICONS.get(event.output_type, ""),
        "text": event.text,
        "section": event.section,
        "timestamp": event.timestamp,
        "lang": event.lang,
        "traceback": event.traceback,
        "context": dict(event.context) if event.context else {},
    }
    if sequence is not None:
        payload["sequence"] = sequence
    return payload


class WebSocketOutputSink(OutputSink):
    """WebSocket output bridge implementation based on OutputSink."""

    _global_sequence = count(1)
    _sequence_lock = threading.Lock()

    def __init__(
        self,
        publisher: OutputMessagePublisher,
        session_id: Optional[str] = None,
        source: str = "haijunbot.output",
    ) -> None:
        self.publisher = publisher
        self.session_id = session_id
        self.source = source

    def emit(self, event: OutputEvent) -> None:
        message = serialize_output_event(
            event,
            sequence=self._next_sequence(),
            source=self.source,
        )
        if self.session_id and "session_id" not in message["context"]:
            message["context"]["session_id"] = self.session_id
        self.publisher.publish(message, session_id=self.session_id)

    @classmethod
    def _next_sequence(cls) -> int:
        with cls._sequence_lock:
            return next(cls._global_sequence)
