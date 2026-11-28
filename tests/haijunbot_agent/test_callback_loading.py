# -*- coding: utf-8 -*-
"""Tests for callback/event loading responsibility cluster

Covers methods in the Agent class for the "callback/event loading" responsibility cluster:
- _load_after_tool_callbacks
- _load_event_callbacks
- _load_all_event_callbacks
- _fire_after_tool_call

Test pattern follows tests/haijunbot_agent/test_history_compression.py:
Use Mock to construct agent, then bind real methods to avoid complex initialization.
Callback files are constructed via tmp_path with real directories and .py files, covering
scenarios like nonexistent directories, empty directories, invalid files, factory methods,
hook/modifier/event three registration targets, etc.
"""

import sys
from unittest.mock import Mock

import pytest

from haijunbot.haijunbot_agent import Agent as RealAgent
from haijunbot.haijunbot_agent.event_bus import EventBus
from haijunbot.haijunbot_agent.events import AFTER_SUMMARY
from haijunbot.haijunbot_agent.events import AFTER_TOOL_CALL
from haijunbot.haijunbot_agent.events import BEFORE_MODEL_CALL
from haijunbot.haijunbot_agent.events import BEFORE_SUMMARY
from haijunbot.haijunbot_agent.events import BEFORE_TOOL_CALL


def _bind(agent, method_name):
    """Bind real method from RealAgent to mock agent object"""
    setattr(
        agent,
        method_name,
        getattr(RealAgent, method_name).__get__(agent, Mock),
    )
    return agent


def _make_agent(**attrs):
    """Create a Mock agent with minimal attributes needed for this cluster's methods"""
    from haijunbot.haijunbot_agent.callback_loader import CallbackLoader

    ag = Mock()
    # Real EventBus: core behavior of this cluster is subscribing callbacks to it, need real implementation to verify
    ag.event_bus = EventBus()
    # Hook/Modifier lists: real lists for asserting append behavior
    ag._before_tool_call_hooks = []
    ag._before_model_call_modifiers = []
    ag._before_summary_modifiers = []
    # After refactoring, Agent-side methods delegate to self._callback_loader, need to complete before binding real methods
    ag._callback_loader = CallbackLoader(ag)
    for k, v in attrs.items():
        setattr(ag, k, v)
    return ag


def _write_cb_file(directory, name, content):
    """Write a callback .py file in the specified directory and return its path"""
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


class TestFireAfterToolCall:
    """_fire_after_tool_call fires AFTER_TOOL_CALL event"""

    @pytest.fixture
    def agent(self):
        return _bind(_make_agent(), "_fire_after_tool_call")

    def test_emits_event_with_expected_payload(self, agent):
        """Emit once, carrying agent/current_response/need_return/tool_prompt"""
        calls = []
        agent.event_bus.subscribe(AFTER_TOOL_CALL, lambda **kw: calls.append(kw))

        agent._fire_after_tool_call()

        assert len(calls) == 1
        payload = calls[0]
        assert payload["agent"] is agent
        assert payload["current_response"] == ""
        assert payload["need_return"] is False
        assert payload["tool_prompt"] == ""

    def test_subscriber_invoked_exactly_once(self, agent):
        """Subscribed callback invoked exactly once (regression: double dispatch existed before)"""
        cb = Mock()
        agent.event_bus.subscribe(AFTER_TOOL_CALL, cb)

        agent._fire_after_tool_call()

        assert cb.call_count == 1

    def test_exception_is_swallowed(self, agent):
        """Exception from event_bus.emit is caught, not propagated outward"""
        agent.event_bus = Mock()
        agent.event_bus.emit = Mock(side_effect=RuntimeError("boom"))

        # Should not raise
        agent._fire_after_tool_call()

        assert agent.event_bus.emit.call_count == 1


class TestLoadAfterToolCallbacks:
    """_load_after_tool_callbacks scans directories and registers after_tool_call callbacks"""

    @pytest.fixture
    def agent(self):
        return _bind(_make_agent(), "_load_after_tool_callbacks")

    @pytest.fixture
    def cb_dirs(self, monkeypatch):
        """Replace get_after_tool_call_cb_dirs with configurable mock"""
        import haijunbot.haijunbot_agent.callback_loader as mod

        holder = Mock(return_value=[])
        monkeypatch.setattr(mod, "get_after_tool_call_cb_dirs", holder)
        return holder

    def test_no_dirs_does_nothing(self, agent, cb_dirs):
        """No callbacks registered when callback directories not configured"""
        cb_dirs.return_value = []
        agent._load_after_tool_callbacks()
        assert agent.event_bus._listeners[AFTER_TOOL_CALL] == []

    def test_nonexistent_dir_is_skipped(self, agent, cb_dirs, tmp_path):
        """Skip when directory does not exist, no error"""
        cb_dirs.return_value = [str(tmp_path / "not-exist")]
        agent._load_after_tool_callbacks()
        assert agent.event_bus._listeners[AFTER_TOOL_CALL] == []

    def test_empty_dir_registers_nothing(self, agent, cb_dirs, tmp_path):
        """Empty directory registers no callbacks"""
        cb_dirs.return_value = [str(tmp_path)]
        agent._load_after_tool_callbacks()
        assert agent.event_bus._listeners[AFTER_TOOL_CALL] == []

    def test_module_level_callback_registered(self, agent, cb_dirs, tmp_path):
        """Module-level after_tool_call_cb is wrapped and registered, wrapper calls original callback with agent"""
        _write_cb_file(
            tmp_path,
            "cb_mod.py",
            "def after_tool_call_cb(agent):\n    agent.recorded = True\n",
        )
        cb_dirs.return_value = [str(tmp_path)]
        agent._load_after_tool_callbacks()

        listeners = agent.event_bus._listeners[AFTER_TOOL_CALL]
        assert len(listeners) == 1
        # emit triggers wrapper, wrapper takes agent from kwargs and passes to original callback
        agent.event_bus.emit(AFTER_TOOL_CALL, agent=agent)
        assert agent.recorded is True

    def test_factory_method_returning_single(self, agent, cb_dirs, tmp_path):
        """Factory method get_after_tool_call_cb returns single callable"""
        _write_cb_file(
            tmp_path,
            "cb_factory.py",
            "def _impl(agent):\n"
            "    agent.hit = True\n"
            "def get_after_tool_call_cb():\n"
            "    return _impl\n",
        )
        cb_dirs.return_value = [str(tmp_path)]
        agent._load_after_tool_callbacks()

        assert len(agent.event_bus._listeners[AFTER_TOOL_CALL]) == 1
        agent.event_bus.emit(AFTER_TOOL_CALL, agent=agent)
        assert agent.hit is True

    def test_factory_method_returning_list(self, agent, cb_dirs, tmp_path):
        """Factory method returns list, each registered individually"""
        _write_cb_file(
            tmp_path,
            "cb_factory_list.py",
            "def _a(agent):\n"
            "    agent.a_called = True\n"
            "def _b(agent):\n"
            "    agent.b_called = True\n"
            "def register_after_tool_call_cb():\n"
            "    return [_a, _b]\n",
        )
        cb_dirs.return_value = [str(tmp_path)]
        agent._load_after_tool_callbacks()

        assert len(agent.event_bus._listeners[AFTER_TOOL_CALL]) == 2
        agent.event_bus.emit(AFTER_TOOL_CALL, agent=agent)
        assert agent.a_called is True
        assert agent.b_called is True

    def test_init_py_is_skipped(self, agent, cb_dirs, tmp_path):
        """__init__.py is skipped"""
        _write_cb_file(
            tmp_path,
            "__init__.py",
            "def after_tool_call_cb(agent):\n    agent.should_not_run = True\n",
        )
        cb_dirs.return_value = [str(tmp_path)]
        agent._load_after_tool_callbacks()
        assert agent.event_bus._listeners[AFTER_TOOL_CALL] == []

    def test_invalid_python_file_is_tolerated(self, agent, cb_dirs, tmp_path):
        """Files with syntax errors are tolerated and skipped, do not affect overall flow"""
        _write_cb_file(tmp_path, "broken.py", "def (:\n    pass\n")
        cb_dirs.return_value = [str(tmp_path)]
        # Should not raise
        agent._load_after_tool_callbacks()
        assert agent.event_bus._listeners[AFTER_TOOL_CALL] == []

    def test_factory_exception_is_tolerated(self, agent, cb_dirs, tmp_path):
        """Factory method exception is caught, no callback registered and no error"""
        _write_cb_file(
            tmp_path,
            "cb_bad_factory.py",
            "def get_after_tool_call_cb():\n    raise RuntimeError('factory boom')\n",
        )
        cb_dirs.return_value = [str(tmp_path)]
        agent._load_after_tool_callbacks()
        assert agent.event_bus._listeners[AFTER_TOOL_CALL] == []

    def test_callback_exception_is_tolerated(self, agent, cb_dirs, tmp_path):
        """Callback execution exception caught by wrapper, does not affect other callbacks"""
        _write_cb_file(
            tmp_path,
            "cb_raise.py",
            "def after_tool_call_cb(agent):\n    raise RuntimeError('cb boom')\n",
        )
        cb_dirs.return_value = [str(tmp_path)]
        agent._load_after_tool_callbacks()

        # emit should not raise
        agent.event_bus.emit(AFTER_TOOL_CALL, agent=agent)

    def test_sys_path_restored_after_load(self, agent, cb_dirs, tmp_path):
        """sys.path is restored after loading (no callback directory residue)"""
        _write_cb_file(
            tmp_path,
            "cb_path.py",
            "def after_tool_call_cb(agent):\n    agent.ok = True\n",
        )
        cb_dirs.return_value = [str(tmp_path)]
        before = list(sys.path)
        agent._load_after_tool_callbacks()
        assert sys.path == before

    def test_config_getter_exception_is_tolerated(self, agent, cb_dirs):
        """Directory getter function exception caught by outer layer, not propagated outward"""
        cb_dirs.side_effect = RuntimeError("config boom")
        agent._load_after_tool_callbacks()
        assert agent.event_bus._listeners[AFTER_TOOL_CALL] == []


class TestLoadEventCallbacks:
    """_load_event_callbacks general callback loading (hook/modifier/event three targets)"""

    @pytest.fixture
    def agent(self):
        return _bind(_make_agent(), "_load_event_callbacks")

    @pytest.fixture
    def cb_dirs(self, monkeypatch):
        import haijunbot.haijunbot_agent.callback_loader as mod

        holder = Mock(return_value=[])
        monkeypatch.setattr(mod, "get_before_tool_call_cb_dirs", holder)
        return holder

    def test_no_dirs_does_nothing(self, agent, cb_dirs):
        """No callbacks registered when directories not configured"""
        cb_dirs.return_value = []
        agent._load_event_callbacks(
            event_name=BEFORE_TOOL_CALL,
            config_getter=cb_dirs,
            callback_names=["before_tool_call_cb"],
            target="hook",
        )
        assert agent._before_tool_call_hooks == []
        assert agent.event_bus._listeners[BEFORE_TOOL_CALL] == []

    def test_hook_target_registers_hook_and_event(self, agent, cb_dirs, tmp_path):
        """target=hook: both adds to hooks list and subscribes to EventBus"""
        _write_cb_file(
            tmp_path,
            "hook_cb.py",
            "def before_tool_call_cb(agent):\n    return True\n",
        )
        cb_dirs.return_value = [str(tmp_path)]
        agent._load_event_callbacks(
            event_name=BEFORE_TOOL_CALL,
            config_getter=cb_dirs,
            callback_names=["before_tool_call_cb"],
            target="hook",
        )
        assert len(agent._before_tool_call_hooks) == 1
        assert len(agent.event_bus._listeners[BEFORE_TOOL_CALL]) == 1

    def test_modifier_target_model_call(self, agent, cb_dirs, tmp_path):
        """target=modifier + BEFORE_MODEL_CALL: adds to _before_model_call_modifiers"""
        _write_cb_file(
            tmp_path,
            "mod_cb.py",
            "def before_model_call_cb(agent, message):\n    return message\n",
        )
        cb_dirs.return_value = [str(tmp_path)]
        agent._load_event_callbacks(
            event_name=BEFORE_MODEL_CALL,
            config_getter=cb_dirs,
            callback_names=["before_model_call_cb"],
            target="modifier",
        )
        assert len(agent._before_model_call_modifiers) == 1
        # modifier does not subscribe to EventBus
        assert agent.event_bus._listeners[BEFORE_MODEL_CALL] == []

    def test_modifier_target_summary(self, agent, cb_dirs, tmp_path):
        """target=modifier + BEFORE_SUMMARY: adds to _before_summary_modifiers"""
        _write_cb_file(
            tmp_path,
            "sum_cb.py",
            "def before_summary_cb(agent, prompt, auto_completed):\n"
            "    return prompt\n",
        )
        cb_dirs.return_value = [str(tmp_path)]
        agent._load_event_callbacks(
            event_name=BEFORE_SUMMARY,
            config_getter=cb_dirs,
            callback_names=["before_summary_cb"],
            target="modifier",
        )
        assert len(agent._before_summary_modifiers) == 1
        assert agent.event_bus._listeners[BEFORE_SUMMARY] == []

    def test_event_target_subscribes_only(self, agent, cb_dirs, tmp_path):
        """target=event_bus (default): only subscribes to EventBus"""
        _write_cb_file(
            tmp_path,
            "evt_cb.py",
            "def after_summary_cb(agent):\n    return None\n",
        )
        cb_dirs.return_value = [str(tmp_path)]
        agent._load_event_callbacks(
            event_name=AFTER_SUMMARY,
            config_getter=cb_dirs,
            callback_names=["after_summary_cb"],
        )
        assert len(agent.event_bus._listeners[AFTER_SUMMARY]) == 1
        assert agent._before_summary_modifiers == []

    def test_callback_priority_order(self, agent, cb_dirs, tmp_path):
        """Multiple callback names collected in callback_names order (high priority first)"""
        _write_cb_file(
            tmp_path,
            "multi_cb.py",
            "def before_tool_call_cb(agent):\n"
            "    return 'direct'\n"
            "def get_before_tool_call_cb():\n"
            "    def _factory(agent):\n"
            "        return 'factory'\n"
            "    return _factory\n",
        )
        cb_dirs.return_value = [str(tmp_path)]
        agent._load_event_callbacks(
            event_name=BEFORE_TOOL_CALL,
            config_getter=cb_dirs,
            callback_names=[
                "before_tool_call_cb",
                "get_before_tool_call_cb",
            ],
            target="hook",
        )
        # Both callbacks registered
        assert len(agent._before_tool_call_hooks) == 2
        assert len(agent.event_bus._listeners[BEFORE_TOOL_CALL]) == 2

    def test_factory_method_invoked(self, agent, cb_dirs, tmp_path):
        """Callback names with get_/register_ prefix are treated as factory methods"""
        _write_cb_file(
            tmp_path,
            "factory_cb.py",
            "def get_before_tool_call_cb():\n"
            "    def _cb(agent):\n"
            "        return True\n"
            "    return _cb\n",
        )
        cb_dirs.return_value = [str(tmp_path)]
        agent._load_event_callbacks(
            event_name=BEFORE_TOOL_CALL,
            config_getter=cb_dirs,
            callback_names=["get_before_tool_call_cb"],
            target="hook",
        )
        assert len(agent._before_tool_call_hooks) == 1

    def test_invalid_file_is_tolerated(self, agent, cb_dirs, tmp_path):
        """Syntax error files tolerated and skipped"""
        _write_cb_file(tmp_path, "broken.py", "def (:\n    pass\n")
        cb_dirs.return_value = [str(tmp_path)]
        agent._load_event_callbacks(
            event_name=BEFORE_TOOL_CALL,
            config_getter=cb_dirs,
            callback_names=["before_tool_call_cb"],
            target="hook",
        )
        assert agent._before_tool_call_hooks == []

    def test_sys_path_restored(self, agent, cb_dirs, tmp_path):
        """sys.path is restored after loading"""
        _write_cb_file(
            tmp_path,
            "path_cb.py",
            "def before_tool_call_cb(agent):\n    return True\n",
        )
        cb_dirs.return_value = [str(tmp_path)]
        before = list(sys.path)
        agent._load_event_callbacks(
            event_name=BEFORE_TOOL_CALL,
            config_getter=cb_dirs,
            callback_names=["before_tool_call_cb"],
            target="hook",
        )
        assert sys.path == before


class TestLoadAllEventCallbacks:
    """_load_all_event_callbacks orchestrates loading of four types of event callbacks"""

    @pytest.fixture
    def agent(self):
        return _bind(_make_agent(), "_load_all_event_callbacks")

    def test_invokes_load_event_callbacks_four_times(self, agent):
        """Calls _load_event_callbacks once for each of the four event types"""
        agent._load_event_callbacks = Mock()
        agent._load_all_event_callbacks()

        assert agent._load_event_callbacks.call_count == 4
        kwargs_list = [c.kwargs for c in agent._load_event_callbacks.call_args_list]
        events = [kw["event_name"] for kw in kwargs_list]
        assert events == [
            BEFORE_TOOL_CALL,
            BEFORE_MODEL_CALL,
            BEFORE_SUMMARY,
            AFTER_SUMMARY,
        ]

    def test_target_kinds_are_correct(self, agent):
        """hook/modifier/modifier/event four target types are correct"""
        agent._load_event_callbacks = Mock()
        agent._load_all_event_callbacks()

        kwargs_list = [c.kwargs for c in agent._load_event_callbacks.call_args_list]
        targets = [kw.get("target", "event_bus") for kw in kwargs_list]
        assert targets == ["hook", "modifier", "modifier", "event_bus"]

    def test_config_getters_are_wired(self, agent):
        """Each event uses corresponding directory getter function"""
        import haijunbot.haijunbot_agent.callback_loader as mod

        agent._load_event_callbacks = Mock()
        agent._load_all_event_callbacks()

        kwargs_list = [c.kwargs for c in agent._load_event_callbacks.call_args_list]
        getters = [kw["config_getter"] for kw in kwargs_list]
        assert getters[0] is mod.get_before_tool_call_cb_dirs
        assert getters[1] is mod.get_before_model_call_cb_dirs
        assert getters[2] is mod.get_summary_cb_dirs
        assert getters[3] is mod.get_summary_cb_dirs

    def test_callback_names_are_wired(self, agent):
        """Each event uses corresponding callback name list"""
        agent._load_event_callbacks = Mock()
        agent._load_all_event_callbacks()

        kwargs_list = [c.kwargs for c in agent._load_event_callbacks.call_args_list]
        names = [kw["callback_names"] for kw in kwargs_list]
        assert names[0] == [
            "before_tool_call_cb",
            "get_before_tool_call_cb",
            "register_before_tool_call_cb",
        ]
        assert names[1] == [
            "before_model_call_cb",
            "get_before_model_call_cb",
            "register_before_model_call_cb",
        ]
        assert names[2] == [
            "before_summary_cb",
            "get_before_summary_cb",
            "register_before_summary_cb",
        ]
        assert names[3] == [
            "after_summary_cb",
            "get_after_summary_cb",
            "register_after_summary_cb",
        ]
