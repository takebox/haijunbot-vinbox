# -*- coding: utf-8 -*-
"""Tests for TimerManager timer state persistence.

Covers Bug: Scheduled tasks created via after/at/loop tool calls cannot be found by the timer tool after cross-session recovery.
Root Cause: get_state() excluded relative (after) tasks during persistence, causing delayed tasks to be unrecoverable across sessions.
"""

from datetime import datetime, timedelta

from haijunbot.haijunbot_tools.timer import TimerManager


def _make_manager():
    """Construct an independent TimerManager (does not pollute the global singleton)"""
    return TimerManager()


def test_get_state_persists_relative_after_task():
    """Scheduled tasks created with after (relative) should be persisted"""
    m = _make_manager()
    m.add_task(
        task_type="tool_call",
        time_type="relative",
        time_value=3600,
        tool_name="read_code",
        tool_args={"path": "a.py"},
    )
    state = m.get_state()
    time_types = [t["time_type"] for t in state["tasks"]]
    assert "relative" in time_types, "relative tasks created with after should be persisted"


def test_get_state_persists_interval_loop_task():
    """Scheduled tasks created with loop (interval) should be persisted"""
    m = _make_manager()
    m.add_task(
        task_type="tool_call",
        time_type="interval",
        time_value=60,
        tool_name="read_code",
        tool_args={},
        interval_seconds=60,
    )
    state = m.get_state()
    time_types = [t["time_type"] for t in state["tasks"]]
    assert "interval" in time_types


def test_get_state_excludes_cancelled_tasks():
    """Cancelled tasks should not be persisted"""
    m = _make_manager()
    task = m.add_task(
        task_type="tool_call",
        time_type="relative",
        time_value=3600,
        tool_name="read_code",
        tool_args={},
    )
    m.cancel_task(task.task_id)
    state = m.get_state()
    assert state["tasks"] == []


def test_restore_state_recovers_relative_after_task():
    """After (relative) tasks should be recoverable via list_tasks after cross-session recovery"""
    m = _make_manager()
    m.add_task(
        task_type="tool_call",
        time_type="relative",
        time_value=3600,
        tool_name="read_code",
        tool_args={"path": "a.py"},
    )
    state = m.get_state()

    # Simulate new session: fresh manager restores state
    m2 = _make_manager()
    m2.restore_state(state)
    tasks = m2.list_tasks()
    assert len(tasks) == 1
    assert tasks[0]["time_type"] == "relative"
    assert tasks[0]["tool_name"] == "read_code"


def _make_interval_state(status: str) -> dict:
    """Construct a persisted state with an interval task, next_fire_time in the future"""
    m = _make_manager()
    task = m.add_task(
        task_type="tool_call",
        time_type="interval",
        time_value=60,
        tool_name="read_code",
        tool_args={},
        interval_seconds=60,
    )
    task.status = status
    # Ensure next_fire_time is valid (future time), so restore_state goes through the scheduling branch
    task.next_fire_time = (datetime.now() + timedelta(hours=1)).isoformat()
    return m.get_state()


def test_restore_state_skips_completed_task():
    """Completed interval tasks should not continue to trigger after recovery.

    Regression guard: Before the fix, restore_state did not check status, so completed tasks would be
    forced back to pending by _schedule_task and resurrected to continue triggering.
    """
    state = _make_interval_state(status="completed")
    m = _make_manager()
    m.restore_state(state)
    assert m.list_tasks() == [], "completed tasks should not be recovered"
    assert len(m._tasks) == 0, "completed tasks should not enter the scheduling table"


def test_restore_state_recovers_pending_interval_task():
    """Pending interval tasks scheduled for future trigger should recover normally (ensures fix did not break normal tasks)"""
    state = _make_interval_state(status="pending")
    m = _make_manager()
    m.restore_state(state)
    tasks = m.list_tasks()
    assert len(tasks) == 1
    assert tasks[0]["time_type"] == "interval"
    assert tasks[0]["status"] == "pending"
