# -*- coding: utf-8 -*-
"""
Event bus (EventBus)

Goals (phase one, minimal change):
- Provide a simple and reliable publish/subscribe mechanism
- Isolate callback exceptions so they do not affect the main flow
- Introduce no extra dependencies, to facilitate gradual integration into the Agent
- Support priority ordering; the smaller the priority number, the earlier the execution
"""

from collections import defaultdict
from typing import Any
from typing import Callable
from typing import DefaultDict


class EventBus:
    """
    A simple synchronous event bus.
    - subscribe(event, callback, priority=100): subscribe to an event, with priority support
    - emit(event, **kwargs): broadcast an event, executing callbacks in priority order
    - unsubscribe(event, callback): unsubscribe

    Priority notes:
    - The smaller the number, the higher the priority and the earlier the execution
    - The default priority is 100 (medium priority)
    - Recommended priority range: 0-200
    - For equal priorities, callbacks execute in registration order (first registered, first executed)
    """

    def __init__(self) -> None:
        # Stores a list of (priority, order, callback) tuples, sorted by priority and registration order
        # order preserves registration order when priorities are equal
        self._listeners: DefaultDict[
            str, list[tuple[int, int, Callable[..., None]]]
        ] = defaultdict(list)
        # Registration order counter (counted independently per event)
        self._order_counter: DefaultDict[str, int] = defaultdict(int)
        # Cache the sorted callback list to avoid sorting on every emit
        self._sorted_cache: DefaultDict[str, list[Callable[..., None]]] = defaultdict(
            list
        )
        # Flag indicating whether re-sorting is needed
        self._dirty: DefaultDict[str, bool] = defaultdict(lambda: False)

    def subscribe(
        self, event: str, callback: Callable[..., None], priority: int = 100
    ) -> None:
        """
        Subscribe to an event.

        Args:
            event: Event name
            callback: Callback function
            priority: Priority; the smaller the number, the higher the priority (default 100)
                      For equal priorities, callbacks execute in registration order (first registered, first executed)
        """
        if not callable(callback):
            raise TypeError("callback must be callable")
        # Get the current registration order
        order = self._order_counter[event]
        self._order_counter[event] += 1
        # Add the (priority, order, callback) tuple
        self._listeners[event].append((priority, order, callback))
        # Mark that re-sorting is needed
        self._dirty[event] = True

    def unsubscribe(self, event: str, callback: Callable[..., None]) -> None:
        """
        Unsubscribe from an event.

        Args:
            event: Event name
            callback: The callback function to unsubscribe
        """
        if event not in self._listeners:
            return
        # Find and remove the matching callback
        listeners = self._listeners[event]
        for i, (_, _, cb) in enumerate(listeners):
            if cb == callback:
                listeners.pop(i)
                self._dirty[event] = True
                break

    def _get_sorted_callbacks(self, event: str) -> list[Callable[..., None]]:
        """
        Get the sorted callback list (with caching).

        Args:
            event: Event name

        Returns:
            List of callback functions sorted by priority (registration order for equal priorities)
        """
        # If the cache is valid, return it directly
        if not self._dirty[event] and event in self._sorted_cache:
            return self._sorted_cache[event]

        # Sort by priority (the smaller the number, the higher the priority); for equal priorities, by registration order (order)
        listeners = self._listeners[event]
        sorted_listeners = sorted(listeners, key=lambda x: (x[0], x[1]))
        callbacks = [cb for _, _, cb in sorted_listeners]

        # Update the cache
        self._sorted_cache[event] = callbacks
        self._dirty[event] = False

        return callbacks

    def emit(self, event: str, **payload: Any) -> None:
        """
        Broadcast an event. Exceptions in callbacks are caught and ignored to keep the main flow stable.
        Callbacks execute in priority order (the smaller the priority number, the earlier the execution).

        Args:
            event: Event name
            **payload: Event payload data
        """
        callbacks = self._get_sorted_callbacks(event)
        for cb in callbacks:
            try:
                cb(**payload)
            except Exception:
                # Avoid a callback exception interrupting the main flow
                continue
