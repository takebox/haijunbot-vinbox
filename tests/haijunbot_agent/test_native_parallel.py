# -*- coding: utf-8 -*-
"""Agent._execute_native_batch parallel/sequential dispatch unit tests"""

from haijunbot.haijunbot_agent import Agent
from haijunbot.haijunbot_agent.events import AFTER_TOOL_CALL


class _FakeReg:
    def __init__(self, interactive_names=()):
        self.interactive_names = set(interactive_names)

    def get_tool(self, name):
        if name in self.interactive_names:
            return type("T", (), {"interactive": True})()
        return None

    def execute_native_tool_call(self, name, arguments, agent, record=True):
        return f"res:{name}"


def _make():
    a = object.__new__(Agent)
    a.execute_tool_confirm = False
    store = {"__executed_tools__": []}
    a.get_user_data = lambda k: store.get(k)
    a.set_user_data = lambda k, v: store.__setitem__(k, v)
    a.get_tool_registry = lambda: _FakeReg()
    a.confirm_callback = lambda *x, **k: True
    return a, store


def test_parallel_read_calls_run_and_record():
    a, store = _make()
    calls = [
        {"id": "1", "name": "read_code", "arguments": {"path": "a"}},
        {"id": "2", "name": "search_web", "arguments": {"q": "x"}},
    ]
    out = a._execute_native_batch(calls)
    assert out == ["res:read_code", "res:search_web"]
    assert store["__executed_tools__"] == ["read_code", "search_web"]
    assert store["__last_executed_tool__"] == "search_web"


def test_interactive_tool_forces_sequential():
    a, store = _make()
    calls = [
        {"id": "1", "name": "read_code", "arguments": {}},
        {"id": "2", "name": "execute_script", "arguments": {}},
    ]
    out = a._execute_native_batch(calls)
    assert out == ["res:read_code", "res:execute_script"]


class _FakeBus:
    def __init__(self, listener=None):
        self._listeners = {AFTER_TOOL_CALL: [(0, 0, listener)] if listener else []}
        self.emitted = []

    def emit(self, event, **kwargs):
        # Align with real EventBus.emit semantics: call subscribed callbacks by priority (only once)
        self.emitted.append(event)
        for _, _, cb in self._listeners.get(event, []):
            if cb:
                cb(**kwargs)


def test_fire_after_tool_call_invokes_listener_and_emits():
    called = {}

    def listener(agent=None, **kwargs):
        called["agent"] = agent
        called["kwargs"] = kwargs

    bus = _FakeBus(listener)
    a = object.__new__(Agent)
    a.event_bus = bus
    # After refactoring _fire_after_tool_call delegates to self._callback_loader,
    # instances constructed via object.__new__ need this attribute completed
    from haijunbot.haijunbot_agent.callback_loader import CallbackLoader

    a._callback_loader = CallbackLoader(a)
    a._fire_after_tool_call()
    assert called["agent"] is a
    assert called["kwargs"]["current_response"] == ""
    assert AFTER_TOOL_CALL in bus.emitted


def test_confirm_deny_returns_rejection():
    a, store = _make()
    a.execute_tool_confirm = True
    a.confirm_callback = lambda *x, **k: False
    out = a._execute_native_batch([{"id": "1", "name": "read_code", "arguments": {}}])
    assert "refused" in out[0]


def test_user_tool_marked_interactive_forces_serial():
    a, store = _make()
    # User-defined tool declares interactive=True (not in built-in list), should also execute serially as a batch
    a.get_tool_registry = lambda: _FakeReg(interactive_names={"my_custom"})
    calls = [
        {"id": "1", "name": "read_code", "arguments": {}},
        {"id": "2", "name": "my_custom", "arguments": {}},
    ]
    out = a._execute_native_batch(calls)
    assert out == ["res:read_code", "res:my_custom"]
