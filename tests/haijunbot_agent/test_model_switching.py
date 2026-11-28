# -*- coding: utf-8 -*-
"""Model/platform switching responsibility cluster tests

Covers methods in the Agent class for the "model/platform switching" responsibility cluster:
- _switch_model_by_difficulty
- _classify_and_switch_model
- _apply_task_temperature
- _create_temp_model

Test pattern follows tests/haijunbot_agent/test_history_compression.py /
test_callback_loading.py: Use Mock to construct agent, then bind real methods from RealAgent
to avoid complex initialization (no real LLM calls, no network access).

Design points:
- Assertions are on "observable behavior" (return values, side effects, called parameters),
  not implementation location, so these test cases hold true before and after cluster-3 refactoring
  (methods moving to model_switcher.py).
- Source code has lazy imports within function bodies (switch_platform_type / get_llm_config)
  and module-level imports (PlatformRegistry), patch targets chosen by actual implementation:
    * switch_platform_type -> haijunbot.haijunbot_agent.builtin_input_handler
    * get_llm_config       -> haijunbot.haijunbot_utils.config
    * PlatformRegistry     -> haijunbot.haijunbot_agent.PlatformRegistry (module global name)
- Mock() auto-generates any attribute with a truthy value; all attributes that source code
  checks via hasattr/getattr must be explicitly set in tests, otherwise assertions are invalid.
"""

from unittest.mock import Mock

import pytest

from haijunbot.haijunbot_agent import Agent as RealAgent


def _bind(agent, method_name):
    """Bind real method from RealAgent to mock agent object"""
    setattr(
        agent,
        method_name,
        getattr(RealAgent, method_name).__get__(agent, Mock),
    )
    return agent


def _make_agent(**attrs):
    """Create a Mock agent, explicitly setting minimal attributes needed for this cluster's methods

    Note: Mock() returns a truthy Mock for any attribute access, so all attributes checked
    via hasattr/getattr in source code must be explicitly assigned (including None),
    otherwise branches will go wrong.
    """
    from haijunbot.haijunbot_agent.model_switcher import ModelSwitcher

    ag = Mock()
    # After refactoring, Agent-side methods delegate to self._model_switcher, need to complete before binding real methods
    ag._model_switcher = ModelSwitcher(ag)
    # Model type flag and manual switch toggle (_switch_model_by_difficulty depends on)
    ag._model_type = "normal"
    ag._manual_model_switch = False
    # System prompt and prompt manager (prompt rebuild depends on after switch success)
    ag.system_prompt = ""
    ag.prompt_manager = None
    # Model instance
    ag.model = Mock()
    ag.model.platform_type = "normal"
    for k, v in attrs.items():
        setattr(ag, k, v)
    return ag


def _patch_switch_platform_type(monkeypatch, func):
    """Patch lazily imported switch_platform_type (located in builtin_input_handler)

    Note: The name `builtin_input_handler` is shadowed by a function of the same name in the package (re-export),
    so monkeypatch string path resolution gets the function not the module; here we explicitly get
    the module object from sys.modules and patch its attribute.
    """
    import sys

    module = sys.modules["haijunbot.haijunbot_agent.builtin_input_handler"]
    monkeypatch.setattr(module, "switch_platform_type", func)


def _patch_get_llm_config(monkeypatch, func):
    """Patch lazily imported get_llm_config (located in haijunbot_utils.config)"""
    import sys

    module = sys.modules["haijunbot.haijunbot_utils.config"]
    monkeypatch.setattr(module, "get_llm_config", func)


class TestSwitchModelByDifficulty:
    """_switch_model_by_difficulty switches model type by difficulty"""

    @pytest.fixture
    def agent(self):
        return _bind(_make_agent(), "_switch_model_by_difficulty")

    def test_manual_switch_disables_auto(self, agent, monkeypatch):
        """Return directly when user has manually switched model, do not call switch_platform_type"""
        agent._manual_model_switch = True
        calls = []
        _patch_switch_platform_type(
            monkeypatch, lambda *a, **k: calls.append((a, k)) or True
        )
        agent._switch_model_by_difficulty("hard")
        assert calls == []
        # Model type remains unchanged
        assert agent._model_type == "normal"

    @pytest.mark.parametrize(
        "difficulty,expected",
        [
            ("easy", "normal"),
            ("medium", "normal"),
            ("hard", "smart"),
            ("unknown-difficulty", "normal"),
        ],
    )
    def test_difficulty_mapping(self, agent, monkeypatch, difficulty, expected):
        """Difficulty to model type mapping: easy/medium->normal, hard->smart, unknown->normal"""
        # Make current model type different from target, ensuring switch is actually triggered
        agent._model_type = "cheap" if expected != "cheap" else "smart"
        captured = {}

        def fake_switch(ag, platform_type, preserve_model_group=True):
            captured["platform_type"] = platform_type
            captured["preserve_model_group"] = preserve_model_group
            return True

        _patch_switch_platform_type(monkeypatch, fake_switch)
        agent._switch_model_by_difficulty(difficulty)
        assert captured["platform_type"] == expected
        assert captured["preserve_model_group"] is True
        assert agent._model_type == expected

    def test_same_model_type_skips_switch(self, agent, monkeypatch):
        """Return early when target model type matches current, do not call switch_platform_type"""
        agent._model_type = "normal"
        calls = []
        _patch_switch_platform_type(
            monkeypatch, lambda *a, **k: calls.append((a, k)) or True
        )
        agent._switch_model_by_difficulty("easy")
        assert calls == []

    def test_switch_success_updates_type_and_prompt_without_prompt_manager(
        self, agent, monkeypatch
    ):
        """Switch success: update _model_type, rebuild prompt directly with self.system_prompt"""
        agent._model_type = "normal"
        agent.system_prompt = "Original system prompt"
        _patch_switch_platform_type(monkeypatch, lambda *a, **k: True)
        agent._switch_model_by_difficulty("hard")
        assert agent._model_type == "smart"
        agent.model.set_system_prompt.assert_called_once_with("Original system prompt")

    def test_switch_success_uses_prompt_manager(self, agent, monkeypatch):
        """Switch success with prompt_manager: rebuild prompt via build_system_prompt"""
        agent._model_type = "normal"
        agent.system_prompt = "Original system prompt"
        agent.prompt_manager = Mock()
        agent.prompt_manager.build_system_prompt = Mock(return_value="Rebuilt prompt")
        _patch_switch_platform_type(monkeypatch, lambda *a, **k: True)
        agent._switch_model_by_difficulty("hard")
        agent.prompt_manager.build_system_prompt.assert_called_once_with(agent)
        agent.model.set_system_prompt.assert_called_once_with("Rebuilt prompt")

    def test_switch_success_without_system_prompt_skips_set(self, agent, monkeypatch):
        """Switch success but no system_prompt: do not call set_system_prompt"""
        agent._model_type = "normal"
        agent.system_prompt = ""
        _patch_switch_platform_type(monkeypatch, lambda *a, **k: True)
        agent._switch_model_by_difficulty("hard")
        assert agent._model_type == "smart"
        agent.model.set_system_prompt.assert_not_called()

    def test_switch_failure_keeps_model_type(self, agent, monkeypatch):
        """Do not update _model_type or rebuild prompt on switch failure"""
        agent._model_type = "normal"
        agent.system_prompt = "Original system prompt"
        _patch_switch_platform_type(monkeypatch, lambda *a, **k: False)
        agent._switch_model_by_difficulty("hard")
        assert agent._model_type == "normal"
        agent.model.set_system_prompt.assert_not_called()


class TestClassifyAndSwitchModel:
    """_classify_and_switch_model: classify -> switch model -> adjust temperature -> update prompt"""

    @pytest.fixture
    def agent(self):
        ag = _make_agent()
        _bind(ag, "_classify_and_switch_model")
        # Two methods called within this cluster replaced with Mock for asserting call parameters
        # (after refactoring implementation is on ag._model_switcher, need to replace same-named method on that object)
        ag._model_switcher.switch_model_by_difficulty = Mock()
        ag._model_switcher.apply_task_temperature = Mock()
        return ag

    def test_normal_flow_calls_substeps(self, agent):
        """Normal flow: calls switch model and adjust temperature in order, updates system prompt"""
        agent.system_prompt = "Old prompt"
        agent.model = Mock()
        classify_fn = Mock(return_value=("coding", "hard", 0.7))
        get_prompt_fn = Mock(return_value="New prompt")

        agent._classify_and_switch_model("Write a function", classify_fn, get_prompt_fn)

        classify_fn.assert_called_once_with("Write a function")
        agent._model_switcher.switch_model_by_difficulty.assert_called_once_with("hard")
        agent._model_switcher.apply_task_temperature.assert_called_once_with(0.7)
        get_prompt_fn.assert_called_once_with("coding")
        assert agent.system_prompt == "New prompt"
        agent.model.set_system_prompt.assert_called_once_with("New prompt")

    def test_same_prompt_does_not_update(self, agent):
        """Do not update when scenario_system_prompt matches current system_prompt"""
        agent.system_prompt = "Same prompt"
        agent.model = Mock()
        classify_fn = Mock(return_value=("coding", "easy", 0.3))
        get_prompt_fn = Mock(return_value="Same prompt")

        agent._classify_and_switch_model("Input", classify_fn, get_prompt_fn)

        assert agent.system_prompt == "Same prompt"
        agent.model.set_system_prompt.assert_not_called()

    def test_uses_prompt_manager_when_available(self, agent):
        """Rebuild prompt via build_system_prompt when prompt_manager is available"""
        agent.system_prompt = "Old prompt"
        agent.model = Mock()
        agent.prompt_manager = Mock()
        agent.prompt_manager.build_system_prompt = Mock(return_value="Rebuilt prompt")
        classify_fn = Mock(return_value=("coding", "hard", 0.5))
        get_prompt_fn = Mock(return_value="New prompt")

        agent._classify_and_switch_model("Input", classify_fn, get_prompt_fn)

        agent.prompt_manager.build_system_prompt.assert_called_once_with(agent)
        agent.model.set_system_prompt.assert_called_once_with("Rebuilt prompt")

    def test_classify_fn_exception_is_swallowed(self, agent):
        """classify_fn exception is caught, not thrown outward, subsequent steps not executed"""
        agent.system_prompt = "Old prompt"

        def boom(_):
            raise RuntimeError("Classification service unavailable")

        # Should not raise
        agent._classify_and_switch_model("Input", boom, Mock())
        agent._model_switcher.switch_model_by_difficulty.assert_not_called()
        agent._model_switcher.apply_task_temperature.assert_not_called()
        assert agent.system_prompt == "Old prompt"

    def test_model_none_skips_set_system_prompt(self, agent):
        """When self.model is None, still update system_prompt but do not call set_system_prompt"""
        agent.system_prompt = "Old prompt"
        agent.model = None
        classify_fn = Mock(return_value=("coding", "easy", 0.2))
        get_prompt_fn = Mock(return_value="New prompt")

        agent._classify_and_switch_model("Input", classify_fn, get_prompt_fn)

        assert agent.system_prompt == "New prompt"


class TestApplyTaskTemperature:
    """_apply_task_temperature temperature range protection and explicit config priority"""

    @pytest.fixture
    def agent(self):
        ag = _make_agent()
        _bind(ag, "_apply_task_temperature")
        return ag

    def test_model_none_returns_early(self, agent):
        """Return directly when model is None"""
        agent.model = None
        agent._apply_task_temperature(0.7)  # Should not raise

    def test_temperature_none_returns_early(self, agent, monkeypatch):
        """Return directly when temperature is None, do not modify model temperature"""
        agent.model = Mock()
        agent.model.temperature = 0.9
        _patch_get_llm_config(monkeypatch, lambda *a, **k: {"temperature": None})
        agent._apply_task_temperature(None)
        assert agent.model.temperature == 0.9

    def test_pinned_temperature_wins(self, agent, monkeypatch):
        """No auto adjustment when llm_config explicitly locks temperature"""
        agent.model = Mock()
        agent.model.temperature = 0.9
        _patch_get_llm_config(monkeypatch, lambda *a, **k: {"temperature": 0.42})
        agent._apply_task_temperature(0.7)
        assert agent.model.temperature == 0.9

    def test_clamps_low_value(self, agent, monkeypatch):
        """Temperature below 0.1 is clamped to 0.1"""
        agent.model = Mock()
        agent.model.temperature = 0.9
        _patch_get_llm_config(monkeypatch, lambda *a, **k: {})
        agent._apply_task_temperature(0.01)
        assert agent.model.temperature == 0.1

    def test_clamps_high_value(self, agent, monkeypatch):
        """Temperature above 1.5 is clamped to 1.5"""
        agent.model = Mock()
        agent.model.temperature = 0.9
        _patch_get_llm_config(monkeypatch, lambda *a, **k: {})
        agent._apply_task_temperature(3.0)
        assert agent.model.temperature == 1.5

    def test_normal_value_applied(self, agent, monkeypatch):
        """Temperature in normal range is applied as-is"""
        agent.model = Mock()
        agent.model.temperature = 0.9
        _patch_get_llm_config(monkeypatch, lambda *a, **k: {})
        agent._apply_task_temperature(0.7)
        assert agent.model.temperature == 0.7

    def test_invalid_value_not_applied(self, agent, monkeypatch):
        """Invalid value (cannot convert to float) does not set temperature"""
        agent.model = Mock()
        agent.model.temperature = 0.9
        _patch_get_llm_config(monkeypatch, lambda *a, **k: {})
        agent._apply_task_temperature("not-a-number")
        assert agent.model.temperature == 0.9

    def test_model_without_temperature_attr(self, agent, monkeypatch):
        """When model has no temperature attribute, do not set and do not raise"""
        model = Mock(spec=["platform_type"])
        model.platform_type = "normal"
        agent.model = model
        _patch_get_llm_config(monkeypatch, lambda *a, **k: {})
        agent._apply_task_temperature(0.7)  # Should not raise

    def test_exception_is_swallowed(self, agent, monkeypatch):
        """Internal exceptions swallowed, do not affect main flow"""
        agent.model = Mock()
        agent.model.temperature = 0.9

        def boom(*a, **k):
            raise RuntimeError("Config read failed")

        _patch_get_llm_config(monkeypatch, boom)
        # When get_llm_config raises exception, pinned falls back to None, then temperature is set normally
        agent._apply_task_temperature(0.6)
        assert agent.model.temperature == 0.6


class TestCreateTempModel:
    """_create_temp_model creates temporary model instance"""

    @pytest.fixture
    def agent(self):
        ag = _make_agent()
        _bind(ag, "_create_temp_model")
        # Default model (uses its platform_type when not forced)
        ag.model = Mock()
        ag.model.platform_type = "normal"
        return ag

    def _patch_registry(self, monkeypatch, registry):
        """Patch module-level PlatformRegistry name as factory returning specified registry

        After refactoring, implementation is in model_switcher.py, need to patch that module's global name.
        """
        monkeypatch.setattr(
            "haijunbot.haijunbot_agent.model_switcher.PlatformRegistry",
            lambda *a, **k: registry,
        )

    def test_create_platform_uses_current_platform_type(self, agent, monkeypatch):
        """Uses current model's platform_type to create platform when no force_model_type"""
        temp_model = Mock()
        registry = Mock()
        registry.create_platform = Mock(return_value=temp_model)
        self._patch_registry(monkeypatch, registry)

        result = agent._create_temp_model()

        registry.create_platform.assert_called_once_with("normal")
        assert result is temp_model
        temp_model.set_suppress_output.assert_called_once_with(False)
        temp_model.set_system_prompt.assert_not_called()

    @pytest.mark.parametrize(
        "force_type,getter",
        [
            ("smart", "get_smart_platform"),
            ("cheap", "get_cheap_platform"),
            ("normal", "get_normal_platform"),
        ],
    )
    def test_force_model_type_dispatches(self, agent, monkeypatch, force_type, getter):
        """force_model_type dispatches to corresponding get_*_platform branch"""
        temp_model = Mock()
        registry = Mock()
        setattr(registry, getter, Mock(return_value=temp_model))
        self._patch_registry(monkeypatch, registry)

        result = agent._create_temp_model(force_model_type=force_type)

        getattr(registry, getter).assert_called_once()
        assert result is temp_model

    def test_system_prompt_applied_when_non_empty(self, agent, monkeypatch):
        """Call set_system_prompt when system_prompt is non-empty"""
        temp_model = Mock()
        registry = Mock()
        registry.create_platform = Mock(return_value=temp_model)
        self._patch_registry(monkeypatch, registry)

        agent._create_temp_model(system_prompt="You are an assistant")

        temp_model.set_system_prompt.assert_called_once_with("You are an assistant")

    def test_creation_failure_raises_runtime_error(self, agent, monkeypatch):
        """Raise RuntimeError on creation failure (returns None)"""
        registry = Mock()
        registry.create_platform = Mock(return_value=None)
        self._patch_registry(monkeypatch, registry)

        with pytest.raises(RuntimeError):
            agent._create_temp_model()

    def test_always_disables_output_suppression(self, agent, monkeypatch):
        """Always call set_suppress_output(False) regardless of system_prompt"""
        temp_model = Mock()
        registry = Mock()
        registry.create_platform = Mock(return_value=temp_model)
        self._patch_registry(monkeypatch, registry)

        agent._create_temp_model(system_prompt="Prompt")

        temp_model.set_suppress_output.assert_called_once_with(False)
