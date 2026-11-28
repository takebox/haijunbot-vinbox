# -*- coding: utf-8 -*-
"""Web Gateway internal timer manager."""

from __future__ import annotations

import heapq
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional

from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_web_gateway.cron import CronParseError
from haijunbot.haijunbot_web_gateway.cron import parse_cron


logger = logging.getLogger(__name__)

TimerCallback = Callable[[], None]
TaskFactory = Callable[[Dict[str, Any]], TimerCallback]


@dataclass
class TimerTask:
    """Scheduled task definition."""

    task_id: str
    callback: TimerCallback
    run_at: float
    interval_seconds: Optional[float] = None
    cron_expr: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    cancelled: bool = False

    @property
    def is_recurring(self) -> bool:
        """Whether this is a recurring task (fixed interval or cron expression)."""
        return self.interval_seconds is not None or self.cron_expr is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable task information."""
        return {
            "task_id": self.task_id,
            "run_at": datetime.fromtimestamp(self.run_at).isoformat(),
            "interval_seconds": self.interval_seconds,
            "cron_expr": self.cron_expr,
            "is_recurring": self.is_recurring,
            "cancelled": self.cancelled,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(order=True)
class ScheduledTask:
    """Scheduled task used in the heap."""

    run_at: float
    sequence: int
    task_id: str


class TimerManager:
    """Timer manager.

    Supports:
    - One-shot tasks at an absolute time
    - One-shot tasks after a relative delay
    - Recurring tasks at a fixed interval
    """

    PERSISTENCE_FILE = Path(get_data_dir()) / "gateway" / ".haijunbot_timers.json"

    def __init__(self, task_factory: Optional[TaskFactory] = None) -> None:
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._tasks: Dict[str, TimerTask] = {}
        self._queue: List[ScheduledTask] = []
        self._sequence = 0
        self._shutdown = False
        self._task_factory = task_factory
        self._worker = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="web-gateway-timer",
        )
        self._worker.start()

    def schedule_at(
        self,
        run_at: datetime,
        callback: TimerCallback,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Register a one-shot task at an absolute time."""
        return self._schedule_task(
            run_at=run_at.timestamp(),
            callback=callback,
            metadata=metadata,
        )

    def schedule_after(
        self,
        delay_seconds: float,
        callback: TimerCallback,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Register a one-shot task after a relative delay."""
        if delay_seconds < 0:
            raise ValueError("delay_seconds must be >= 0")
        return self._schedule_task(
            run_at=time.time() + delay_seconds,
            callback=callback,
            metadata=metadata,
        )

    def schedule_every(
        self,
        interval_seconds: float,
        callback: TimerCallback,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Register a recurring timer task."""
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be > 0")
        return self._schedule_task(
            run_at=time.time() + interval_seconds,
            callback=callback,
            interval_seconds=interval_seconds,
            metadata=metadata,
        )

    def schedule_cron(
        self,
        cron_expr: str,
        callback: TimerCallback,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Register a recurring task with a cron expression.

        The first trigger time is the next time point matched by the cron expression; after triggering it automatically advances to the next match point.
        """
        try:
            schedule = parse_cron(cron_expr)
        except CronParseError:
            raise ValueError(f"invalid cron expression: {cron_expr!r}")
        run_at = schedule.next_match(time.time())
        return self._schedule_task(
            run_at=run_at,
            callback=callback,
            cron_expr=cron_expr,
            metadata=metadata,
        )

    def cancel(self, task_id: str) -> bool:
        """Cancel the specified task."""
        with self._condition:
            task = self._tasks.get(task_id)
            if task is None or task.cancelled:
                return False
            task.cancelled = True
            self._tasks.pop(task_id, None)
            self._persist_tasks_locked()
            self._condition.notify_all()
            return True

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get serializable information for a single task."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            return task.to_dict()

    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all non-cancelled tasks."""
        with self._lock:
            tasks = [
                task.to_dict() for task in self._tasks.values() if not task.cancelled
            ]
        tasks.sort(key=lambda task_info: task_info["run_at"])
        return tasks

    def shutdown(self) -> None:
        """Shut down the timer manager and stop further scheduling."""
        with self._condition:
            if self._shutdown:
                return
            self._shutdown = True
            self._condition.notify_all()

        if self._worker.is_alive():
            self._worker.join(timeout=1.0)

    def is_shutdown(self) -> bool:
        """Check whether the manager has been shut down."""
        with self._lock:
            return self._shutdown

    def load_persisted_tasks(self) -> None:
        """Explicitly load persisted timer tasks."""
        self._load_tasks()

    def restore_task(self, task_data: Dict[str, Any]) -> str:
        """Restore a single task from persisted data."""
        if self._task_factory is None:
            raise RuntimeError("Timer task factory is not configured")

        task_id = task_data["task_id"]
        run_at_raw = task_data["run_at"]
        interval_seconds = task_data.get("interval_seconds")
        cron_expr = task_data.get("cron_expr")
        metadata = task_data.get("metadata") or {}

        callback = self._task_factory(metadata)
        run_at_dt = datetime.fromisoformat(run_at_raw)
        run_at_ts = max(run_at_dt.timestamp(), time.time())
        return self._schedule_task(
            run_at=run_at_ts,
            callback=callback,
            interval_seconds=interval_seconds,
            cron_expr=cron_expr,
            metadata=metadata,
            task_id=task_id,
            persist=False,
        )

    def _schedule_task(
        self,
        run_at: float,
        callback: TimerCallback,
        interval_seconds: Optional[float] = None,
        cron_expr: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
        persist: bool = True,
    ) -> str:
        with self._condition:
            if self._shutdown:
                raise RuntimeError("TimerManager is shut down")

            task_id = task_id or str(uuid.uuid4())
            timer_task = TimerTask(
                task_id=task_id,
                callback=callback,
                run_at=run_at,
                interval_seconds=interval_seconds,
                cron_expr=cron_expr,
                metadata=metadata,
            )
            self._tasks[task_id] = timer_task
            heapq.heappush(
                self._queue,
                ScheduledTask(
                    run_at=run_at,
                    sequence=self._next_sequence(),
                    task_id=task_id,
                ),
            )
            if persist:
                self._persist_tasks_locked()
            self._condition.notify_all()
            return task_id

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def _run_loop(self) -> None:
        while True:
            task_to_run = self._wait_for_next_task()
            if task_to_run is None:
                return
            self._execute_task(task_to_run)

    def _wait_for_next_task(self) -> Optional[TimerTask]:
        with self._condition:
            while True:
                if self._shutdown:
                    return None

                if not self._queue:
                    self._condition.wait()
                    continue

                scheduled_task = self._queue[0]
                timer_task = self._tasks.get(scheduled_task.task_id)
                if timer_task is None or timer_task.cancelled:
                    heapq.heappop(self._queue)
                    continue

                now = time.time()
                wait_seconds = scheduled_task.run_at - now
                if wait_seconds > 0:
                    self._condition.wait(timeout=wait_seconds)
                    continue

                heapq.heappop(self._queue)
                return timer_task

    def _execute_task(self, timer_task: TimerTask) -> None:
        if timer_task.cancelled:
            return

        try:
            timer_task.callback()
        except Exception:
            logger.exception("Timer task execution failed: %s", timer_task.task_id)

        if not timer_task.is_recurring:
            with self._condition:
                self._tasks.pop(timer_task.task_id, None)
                self._persist_tasks_locked()
            return

        with self._condition:
            if self._shutdown or timer_task.cancelled:
                self._tasks.pop(timer_task.task_id, None)
                self._persist_tasks_locked()
                return

            if timer_task.cron_expr is not None:
                # cron task: advance to the next match time point
                schedule = parse_cron(timer_task.cron_expr)
                timer_task.run_at = schedule.next_match(time.time())
            else:
                assert timer_task.interval_seconds is not None
                timer_task.run_at = time.time() + timer_task.interval_seconds
            heapq.heappush(
                self._queue,
                ScheduledTask(
                    run_at=timer_task.run_at,
                    sequence=self._next_sequence(),
                    task_id=timer_task.task_id,
                ),
            )
            self._persist_tasks_locked()
            self._condition.notify_all()

    def _load_tasks(self) -> None:
        """Load saved timer tasks from a file."""
        if self._task_factory is None:
            return
        if not self.PERSISTENCE_FILE.exists():
            return

        try:
            with open(self.PERSISTENCE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                logger.warning("Invalid timer persistence file format")
                return

            restored = False
            for task_data in data:
                if not isinstance(task_data, dict):
                    continue
                try:
                    self.restore_task(task_data)
                    restored = True
                except Exception:
                    logger.exception(
                        "Failed to restore timer task: %s",
                        task_data.get("task_id"),
                    )

            if restored:
                with self._condition:
                    self._persist_tasks_locked()
        except Exception:
            logger.exception("Failed to load timer persistence file")

    def _persist_tasks_locked(self) -> None:
        """Write the current task set to the persistence file. The caller must hold the lock."""
        try:
            self.PERSISTENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = [
                task.to_dict() for task in self._tasks.values() if not task.cancelled
            ]
            with open(self.PERSISTENCE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            logger.exception("Failed to persist timer tasks")
