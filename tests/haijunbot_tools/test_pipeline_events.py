# -*- coding: utf-8 -*-
"""pipeline_events (pipeline progress event bus) tests.

Coverage:
1. PipelineEventBus basic read/write: emit/drain ordering, drain clears, has_events;
2. Bounded capacity: drops oldest events when exceeding maxlen;
3. Invalid input: non-dict events are ignored;
4. Thread safety: concurrent emit from multiple threads does not lose events or raise errors;
5. get_event_bus singleton semantics.
"""

import threading
from typing import Any
from typing import cast

from haijunbot.haijunbot_tools.pipeline_events import PipelineEventBus
from haijunbot.haijunbot_tools.pipeline_events import get_event_bus


class TestPipelineEventBus:
    def test_emit_drain_order(self):
        """After emit, drain returns all events in write order and clears the queue."""
        bus = PipelineEventBus()
        bus.emit({"id": 1})
        bus.emit({"id": 2})
        bus.emit({"id": 3})
        assert bus.drain() == [{"id": 1}, {"id": 2}, {"id": 3}]
        assert bus.drain() == []

    def test_has_events(self):
        """has_events reflects whether queue has unconsumed events."""
        bus = PipelineEventBus()
        assert bus.has_events() is False
        bus.emit({"id": 1})
        assert bus.has_events() is True
        bus.drain()
        assert bus.has_events() is False

    def test_bounded_drops_oldest(self):
        """When exceeding maxlen, oldest events are dropped, only newest N retained."""
        bus = PipelineEventBus(max_events=3)
        for i in range(5):
            bus.emit({"id": i})
        assert bus.drain() == [{"id": 2}, {"id": 3}, {"id": 4}]

    def test_non_dict_ignored(self):
        """Non-dict events are silently ignored, do not affect subsequent events."""
        bus = PipelineEventBus()
        bus.emit(cast(Any, "not-a-dict"))
        bus.emit(cast(Any, None))
        bus.emit({"id": 1})
        assert bus.drain() == [{"id": 1}]

    def test_thread_safety(self):
        """Concurrent emit from multiple threads does not lose events or raise exceptions."""
        bus = PipelineEventBus(max_events=10000)
        threads = []
        per_thread = 200

        def worker(tid: int) -> None:
            for i in range(per_thread):
                bus.emit({"tid": tid, "i": i})

        for t in range(8):
            th = threading.Thread(target=worker, args=(t,))
            threads.append(th)
            th.start()
        for th in threads:
            th.join()

        events = bus.drain()
        assert len(events) == 8 * per_thread
        # Each event is complete (not corrupted by concurrent writes)
        assert all(isinstance(e.get("tid"), int) for e in events)


class TestGetEventBus:
    def test_singleton(self):
        """get_event_bus returns the same instance."""
        assert get_event_bus() is get_event_bus()
