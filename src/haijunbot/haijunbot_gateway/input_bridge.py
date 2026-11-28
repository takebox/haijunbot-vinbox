# -*- coding: utf-8 -*-
"""Input-side gateway bridge implementation.

Provides:
1. Session-level remote input buffering and waiting;
2. A WebSocket/remote input provider based on haijunbot_utils.input.InputProvider;
3. A session registry for reuse by the subsequent websocket router.
"""

from __future__ import annotations

from dataclasses import dataclass
from queue import Empty
from queue import Queue
import threading
from typing import Dict
from typing import List
from typing import Optional

from haijunbot.haijunbot_utils.input import InputProvider
from haijunbot.haijunbot_utils.input import InputProviderDisconnectedError
from haijunbot.haijunbot_utils.input import InputProviderTimeoutError
from haijunbot.haijunbot_utils.input import register_input_provider
from haijunbot.haijunbot_utils.input import unregister_input_provider


@dataclass(frozen=True)
class RemoteInputMessage:
    """Remote input message."""

    text: str


@dataclass(frozen=True)
class RemoteConfirmMessage:
    """Remote confirm message."""

    confirmed: bool


class RemoteInputSession:
    """Session-level remote input buffer, supporting waiting, delivery, and disconnection."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._queue: Queue[RemoteInputMessage] = Queue()
        self._disconnect_reason: Optional[str] = None
        self._state_lock = threading.Lock()
        self._is_waiting_for_input: bool = False

    def submit_input(self, text: str) -> None:
        print(f"[SUBMIT_INPUT] session_id={self.session_id}, text='{text}'")
        with self._state_lock:
            if self._disconnect_reason is not None:
                raise InputProviderDisconnectedError(self._disconnect_reason)
        self._queue.put(RemoteInputMessage(text=text))

    def disconnect(self, reason: str = "remote session disconnected") -> None:
        print(f"[DISCONNECT] session_id={self.session_id}, reason={reason}")
        with self._state_lock:
            if self._disconnect_reason is None:
                self._disconnect_reason = reason
        self._queue.put(RemoteInputMessage(text=""))

    def reconnect(self) -> None:
        """Clear the disconnect reason on reconnect, allowing continued waiting for input."""
        with self._state_lock:
            self._disconnect_reason = None

    def is_waiting_for_input(self) -> bool:
        """Check whether input is currently being awaited."""
        with self._state_lock:
            return self._is_waiting_for_input

    def wait_for_input(
        self, timeout: Optional[float] = None, use_global_buffer: bool = True
    ) -> str:
        print(
            f"[WAIT_INPUT_START] session_id={self.session_id}, timeout={timeout}, use_global_buffer={use_global_buffer}"
        )
        # Set the waiting-for-input state
        with self._state_lock:
            self._is_waiting_for_input = True
            initial_disconnect_reason = self._disconnect_reason
        print(
            f"[WAIT_INPUT_START] initial_disconnect_reason={initial_disconnect_reason}"
        )
        try:
            # Prefer consuming messages from the global buffer (used only for multiline input)
            if use_global_buffer:
                from haijunbot.haijunbot_utils.globals import get_input_buffer

                buffered_messages = get_input_buffer()
                print(
                    f"[WAIT_INPUT] session_id={self.session_id}, buffered_messages={buffered_messages}"
                )
                if buffered_messages:
                    # Merge all buffered messages and return them
                    result = "\n".join(buffered_messages)
                    print(f"[WAIT_INPUT] Returning buffered messages: {result}")
                    return result

            while True:
                with self._state_lock:
                    disconnect_reason = self._disconnect_reason
                print(
                    f"[WAIT_INPUT_LOOP] disconnect_reason={disconnect_reason}, queue_empty={self._queue.empty()}"
                )
                if disconnect_reason is not None and self._queue.empty():
                    print(
                        f"[WAIT_INPUT_DISCONNECTED] Raising InputProviderDisconnectedError: {disconnect_reason}"
                    )
                    raise InputProviderDisconnectedError(disconnect_reason)
                try:
                    message = self._queue.get(timeout=timeout)
                except Empty as exc:
                    raise InputProviderTimeoutError(
                        "timed out waiting for remote input"
                    ) from exc
                with self._state_lock:
                    disconnect_reason = self._disconnect_reason
                if disconnect_reason is not None and message.text == "":
                    raise InputProviderDisconnectedError(disconnect_reason)
                return message.text
        finally:
            # Clear the waiting-for-input state
            with self._state_lock:
                self._is_waiting_for_input = False


class RemoteConfirmSession:
    """Session-level remote confirm buffer, supporting waiting, delivery, and disconnection."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._queue: Queue[RemoteConfirmMessage] = Queue()
        self._disconnect_reason: Optional[str] = None
        self._state_lock = threading.Lock()

    def submit_confirm(self, confirmed: bool) -> None:
        with self._state_lock:
            if self._disconnect_reason is not None:
                raise InputProviderDisconnectedError(self._disconnect_reason)
        self._queue.put(RemoteConfirmMessage(confirmed=confirmed))

    def disconnect(self, reason: str = "remote session disconnected") -> None:
        with self._state_lock:
            if self._disconnect_reason is None:
                self._disconnect_reason = reason
        self._queue.put(RemoteConfirmMessage(confirmed=False))

    def reconnect(self) -> None:
        """Clear the disconnect reason on reconnect, allowing continued waiting for confirmation."""
        with self._state_lock:
            self._disconnect_reason = None

    def wait_for_confirm(self, timeout: Optional[float] = None) -> bool:
        while True:
            with self._state_lock:
                disconnect_reason = self._disconnect_reason
            if disconnect_reason is not None and self._queue.empty():
                raise InputProviderDisconnectedError(disconnect_reason)
            try:
                message = self._queue.get(timeout=timeout)
            except Empty as exc:
                raise InputProviderTimeoutError(
                    "timed out waiting for remote confirm"
                ) from exc
            with self._state_lock:
                disconnect_reason = self._disconnect_reason
            if disconnect_reason is not None and not message.confirmed:
                raise InputProviderDisconnectedError(disconnect_reason)
            return message.confirmed


class WebSocketInputProvider(InputProvider):
    """Input provider used by WebSocket/remote sessions."""

    def __init__(
        self, session: RemoteInputSession, timeout: Optional[float] = None
    ) -> None:
        self.session = session
        self.timeout = timeout

    def get_multiline_input(
        self,
        tip: str,
        preset: Optional[str] = None,
        preset_cursor: Optional[int] = None,
    ) -> str:
        del tip, preset, preset_cursor
        return self.session.wait_for_input(timeout=self.timeout)


class InputSessionRegistry:
    """Minimal input session registry."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: Dict[str, RemoteInputSession] = {}
        self._provider_counts: Dict[str, int] = {}  # Connection reference count
        self._confirm_sessions: Dict[str, RemoteConfirmSession] = {}  # Confirm session
        self._pending_input_requests: Dict[
            str, List[dict]
        ] = {}  # Queue of pending input requests (FIFO)
        self._pending_confirm_requests: Dict[
            str, List[dict]
        ] = {}  # Queue of pending confirm requests (FIFO)

    def get_or_create(self, session_id: str) -> RemoteInputSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = RemoteInputSession(session_id=session_id)
                self._sessions[session_id] = session
            return session

    def register_provider(
        self, session_id: str, timeout: Optional[float] = None
    ) -> WebSocketInputProvider:
        session = self.get_or_create(session_id)
        provider = WebSocketInputProvider(session=session, timeout=timeout)
        register_input_provider(session_id, provider)
        with self._lock:
            self._provider_counts[session_id] = self._provider_counts.get(session_id, 0) + 1
        return provider

    def unregister_provider(
        self, session_id: str, disconnect_reason: str = "remote session disconnected"
    ) -> None:
        with self._lock:
            count = self._provider_counts.get(session_id, 0)
            if count > 1:
                self._provider_counts[session_id] = count - 1
                return
            self._provider_counts.pop(session_id, None)
            session = self._sessions.pop(session_id, None)
        unregister_input_provider(session_id)
        if session is not None:
            session.disconnect(reason=disconnect_reason)

    def submit_input(self, session_id: str, text: str) -> None:
        session = self.get_or_create(session_id)
        session.submit_input(text)
        # Clear the saved input request after submitting input
        self.clear_input_request(session_id)

    def save_input_request(self, session_id: str, request: dict) -> None:
        """Save the input request to the queue, for recovery after reconnect."""
        with self._lock:
            if session_id not in self._pending_input_requests:
                self._pending_input_requests[session_id] = []
            self._pending_input_requests[session_id].append(request)
            queue_len = len(self._pending_input_requests[session_id])
            tip = request.get("payload", {}).get("tip", "N/A")
            print(
                f"[INPUT_REGISTRY] Saved input_request for session={session_id}, tip='{tip[:50]}...', queue_len={queue_len}, total_sessions={len(self._pending_input_requests)}"
            )

    def get_input_request(self, session_id: str) -> Optional[dict]:
        """Get and remove an input request from the head of the queue (FIFO)."""
        with self._lock:
            queue = self._pending_input_requests.get(session_id)
            if not queue:
                print(
                    f"[INPUT_REGISTRY] Got input_request for session={session_id}, found=False, remaining=0"
                )
                return None
            request = queue.pop(0)  # FIFO: take from the head
            # If the queue is empty, clean up the dictionary entry
            if not queue:
                self._pending_input_requests.pop(session_id, None)
            remaining = len(queue)
            print(
                f"[INPUT_REGISTRY] Got input_request for session={session_id}, found=True, remaining={remaining}"
            )
            return request

    def clear_input_request(self, session_id: str) -> None:
        """Clear the saved input request."""
        with self._lock:
            self._pending_input_requests.pop(session_id, None)

    def get_or_create_confirm_session(self, session_id: str) -> RemoteConfirmSession:
        """Get or create a confirm session."""
        with self._lock:
            session = self._confirm_sessions.get(session_id)
            if session is None:
                session = RemoteConfirmSession(session_id=session_id)
                self._confirm_sessions[session_id] = session
            return session

    def submit_confirm(self, session_id: str, confirmed: bool) -> None:
        """Submit the confirmation result."""
        session = self.get_or_create_confirm_session(session_id)
        session.submit_confirm(confirmed)
        # Clear the saved confirm request after submitting confirmation
        self.clear_confirm_request(session_id)

    def save_confirm_request(self, session_id: str, request: dict) -> None:
        """Save the confirm request to the queue, for recovery after reconnect."""
        with self._lock:
            if session_id not in self._pending_confirm_requests:
                self._pending_confirm_requests[session_id] = []
            self._pending_confirm_requests[session_id].append(request)
            queue_len = len(self._pending_confirm_requests[session_id])
            print(
                f"[CONFIRM_REGISTRY] Saved confirm_request for session={session_id}, queue_len={queue_len}, total_sessions={len(self._pending_confirm_requests)}"
            )

    def get_confirm_request(self, session_id: str) -> Optional[dict]:
        """Get and remove a confirm request from the head of the queue (FIFO)."""
        with self._lock:
            queue = self._pending_confirm_requests.get(session_id)
            if not queue:
                print(
                    f"[CONFIRM_REGISTRY] Got confirm_request for session={session_id}, found=False, remaining=0"
                )
                return None
            request = queue.pop(0)  # FIFO: take from the head
            # If the queue is empty, clean up the dictionary entry
            if not queue:
                self._pending_confirm_requests.pop(session_id, None)
            remaining = len(queue)
            print(
                f"[CONFIRM_REGISTRY] Got confirm_request for session={session_id}, found=True, remaining={remaining}"
            )
            return request

    def clear_confirm_request(self, session_id: str) -> None:
        """Clear the saved confirm request."""
        with self._lock:
            self._pending_confirm_requests.pop(session_id, None)

    def disconnect_confirm_session(
        self, session_id: str, reason: str = "remote session disconnected"
    ) -> None:
        """Disconnect the confirm session."""
        with self._lock:
            session = self._confirm_sessions.pop(session_id, None)
        if session is not None:
            session.disconnect(reason=reason)
