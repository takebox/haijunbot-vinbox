# -*- coding: utf-8 -*-
"""Pipeline progress event bus: a decoupling bridge between pipeline_runner and web_gateway.

At state-machine transition points, pipeline_runner writes structured events through `emit()`; web_gateway's
background thread takes them out through `drain()` and broadcasts them to the frontend. The two do not import each other directly.

Design points:
- **Thread safety**: pipeline_runner runs in a separate thread/subprocess, web_gateway runs in the asyncio
  event loop; cross-thread access is protected with `threading.Lock`.
- **Bounded**: the queue uses `deque(maxlen=N)`; when there is no consumer, overflow discards the oldest events, avoiding memory bloat.
  Progress events can tolerate dropped frames, and the final state is determined by `pipeline_done`.
- **Cross-process bridging**: pipeline_runner may run in an Agent process (e.g., a user conversation Agent calling
  this tool), while the event pump (drain and broadcast to the frontend) runs in the web_gateway process. These are
  different Python processes, and module-level singletons are not shared. Therefore, in addition to writing to the local in-process bus, `emit()`
  also reports events over HTTP to the master gateway (`jglobals.master_url`), where the gateway-side
  `/api/pipeline-events` endpoint writes them into the gateway process's event bus, so they are read by the event pump.
  Inside the gateway process (where the local pump is active), events are only written to the local bus to avoid duplicate reporting.
- **Pure memory, no IO, no external dependencies** (remote reporting failures are silent and do not affect execution semantics).
"""

import os
from collections import deque
from threading import Lock
from typing import Any
from typing import Dict
from typing import List

# Event queue upper limit: the maximum number of events retained when there is no consumer (overflow discards the oldest)
_MAX_EVENTS = 2000

# Gate manual approval actions: approve / reject / retry.
# The action values of the `pipeline_approval` event type come from this set (plus "pending" meaning
# the gate is halted waiting for approval). The frontend renders three buttons + a note input box based on this.
APPROVAL_ACTIONS = ("approve", "reject", "retry")

# Global singleton
_bus: "PipelineEventBus | None" = None
_bus_lock = Lock()

# Whether the local event pump is active: set to True when web_gateway starts the event pump thread.
# True means there is a consumer within this process (drain and broadcast to the frontend); no remote reporting is needed in this case,
# avoiding duplicate reporting to itself when the gateway process itself calls pipeline_runner.
_local_pump_active = False
_local_pump_lock = Lock()


class PipelineEventBus:
    """Thread-safe, bounded pipeline event queue."""

    def __init__(self, max_events: int = _MAX_EVENTS) -> None:
        self._events: deque = deque(maxlen=max_events)
        self._lock = Lock()

    def emit(self, event: Dict[str, Any]) -> None:
        """Producer: write one event (if full, discard the oldest)."""
        if not isinstance(event, dict):
            return
        with self._lock:
            self._events.append(event)

    def drain(self) -> List[Dict[str, Any]]:
        """Consumer: take out and clear all current events (preserving write order)."""
        with self._lock:
            events = list(self._events)
            self._events.clear()
            return events

    def has_events(self) -> bool:
        """Whether there are still unconsumed events."""
        with self._lock:
            return len(self._events) > 0


def get_event_bus() -> PipelineEventBus:
    """Get the global event bus singleton (lazy initialization, thread-safe)."""
    global _bus
    if _bus is None:
        with _bus_lock:
            if _bus is None:
                _bus = PipelineEventBus()
    return _bus


def set_local_pump_active(active: bool) -> None:
    """Set the local event pump active flag (called when web_gateway starts/stops the event pump thread).

    When True, `emit()` only writes to the local in-process bus (this process has a consumer, and the event pump
    drains and broadcasts to the frontend), and no longer reports remotely, avoiding duplication.
    """
    global _local_pump_active
    with _local_pump_lock:
        _local_pump_active = bool(active)


def is_local_pump_active() -> bool:
    """Whether the local event pump is active (whether there is an event consumer in this process)."""
    with _local_pump_lock:
        return _local_pump_active


def emit_remote(event: Dict[str, Any]) -> bool:
    """Report events over HTTP to the master gateway's /api/pipeline-events.

    Used when pipeline_runner runs in an Agent process (not the web_gateway process), to bridge events
    to the gateway process's event bus, so they are read by the event pump and broadcast to the frontend.

    Returns whether the report succeeded; any exception is swallowed (pure side effect, does not affect execution semantics).
    """
    if not isinstance(event, dict):
        return False
    try:
        import httpx

        import haijunbot.haijunbot_utils.globals as jglobals

        master_url = (jglobals.master_url or "").strip().rstrip("/")
        if not master_url:
            return False
        auth_token = os.environ.get("HAIJUNBOT_AUTH_TOKEN", "")
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        # Short reporting timeout, silent on failure: progress events can tolerate dropped frames, and the final state is determined by pipeline_done
        with httpx.Client(timeout=3.0, trust_env=False) as client:
            resp = client.post(
                f"{master_url}/api/pipeline-events",
                json={"events": [event]},
                headers=headers,
            )
            return resp.status_code in (200, 204)
    except Exception:  # pylint: disable=broad-except
        return False
