# -*- coding: utf-8 -*-
"""Native tool call path: cleanup of pending tool calls after Ctrl+C interrupt (_pending_native_tool_calls)"""

from haijunbot.haijunbot_agent import Agent
from haijunbot.haijunbot_utils.globals import set_interrupt, get_interrupt


class _FakeSession:
    addon_prompt = ""
    prompt = ""


def _make_agent(pending_calls):
    """Construct a minimal Agent instance, exposing only attributes needed for _handle_run_interrupt."""
    a = object.__new__(Agent)
    a._pending_native_tool_calls = pending_calls
    a.non_interactive = False
    a.set_non_interactive = lambda v: None
    a.run_input_handlers_next_turn = False
    a.return_control_on_auto_complete = False
    a.session = _FakeSession()
    a._last_handler_returned = False
    a.output_handler = []
    a.confirm_callback = lambda *x, **k: False
    a._process_input = lambda s: s
    # After interrupt, user input is empty -> goes to _complete_task branch
    a._multiline_input = lambda *x, **k: ""
    a._complete_task = lambda auto_completed=False: "COMPLETED"
    # event_bus.emit needs to be callable
    a.event_bus = type("Bus", (), {"emit": lambda self, *a, **k: None})()
    return a


def test_interrupt_clears_pending_native_calls():
    set_interrupt(False)
    a = _make_agent([{"id": "1", "name": "read_code", "arguments": {"path": "a"}}])
    # Simulate user Ctrl+C: set interrupt flag
    set_interrupt(True)
    assert get_interrupt() > 0
    assert a._pending_native_tool_calls is not None

    result = a._handle_run_interrupt("")

    # Pending tool calls cleared after interrupt, preventing run_loop main loop from executing them by mistake
    assert a._pending_native_tool_calls is None
    assert result == "COMPLETED"
    # Interrupt flag consumed
    assert get_interrupt() == 0


def test_no_interrupt_keeps_pending_native_calls():
    set_interrupt(False)
    a = _make_agent([{"id": "1", "name": "read_code", "arguments": {"path": "a"}}])
    # No interrupt: _handle_run_interrupt returns None directly, does not clear pending
    result = a._handle_run_interrupt("")
    assert result is None
    assert a._pending_native_tool_calls is not None
    assert len(a._pending_native_tool_calls) == 1
