# -*- coding: utf-8 -*-
"""Unit tests for agent_system common scenario prompts"""

from haijunbot.haijunbot_utils.scenario_prompts import _get_scenario_types
from haijunbot.haijunbot_utils.scenario_prompts import get_system_prompt

_SCENARIO_SUBDIR = "agent_system"


class TestAgentSystemPrompts:
    """Tests for common Agent scenario system prompts"""

    def test_all_scenarios_load_and_use_modern_style(self):
        """All scenario files can be loaded, and no longer enforce [MODE:] prefix or use classical Chinese style"""
        scenarios = _get_scenario_types(_SCENARIO_SUBDIR)
        assert scenarios, "agent_system scenario directory should contain at least one scenario"

        for scenario in scenarios.keys():
            prompt = get_system_prompt(scenario, scenario_subdir=_SCENARIO_SUBDIR)
            assert isinstance(prompt, str) and prompt.strip(), f"{scenario} system prompt is empty"
            assert "[MODE:" not in prompt, f"{scenario} should not enforce [MODE:] prefix"
            assert "文言" not in prompt, f"{scenario} should not use classical Chinese style"
            assert "Core principles" in prompt or prompt.strip(), f"{scenario} should load a non-empty prompt"

    def test_inherit_core_scenario_composes_with_default_core(self):
        """Scenarios declaring inherit_core = own key points + default shared core"""
        prompt = get_system_prompt("planning", scenario_subdir=_SCENARIO_SUBDIR)
        assert "planning and decision support" in prompt
        assert "Core principles" in prompt


def test_classify_returns_recommended_temperature(monkeypatch):
    """Classification results should include recommended temperature tier based on task nature (low/medium/high -> 0.5/0.7/1.0)"""

    from haijunbot.haijunbot_agent.agent_prompts import classify_user_request
    from haijunbot.haijunbot_platform.registry import PlatformRegistry
    from haijunbot.haijunbot_utils import decision as decision_module

    # Isolate the structured evaluation model (eval_llm): this test only verifies temperature tier parsing on the text model path.
    # If the user's real config has eval_llm enabled, classify_user_request will prefer the evaluation model path,
    # thus bypassing the monkeypatched cheap platform here, causing assertions to differ from expectations.
    monkeypatch.setattr(
        decision_module, "get_eval_platform", lambda: None
    )

    class _FakePlatform:
        def __init__(self, text):
            self._text = text

        def set_suppress_output(self, value):
            pass

        def chat_until_success(self, prompt):
            assert "temperature:" in prompt  # Classification prompt needs to request temperature tier
            return self._text

    monkeypatch.setattr(
        PlatformRegistry,
        "get_cheap_platform",
        lambda self: _FakePlatform(
            "scenario: default\ndifficulty: medium\ntemperature: low"
        ),
    )
    _, difficulty, temperature = classify_user_request("Fix a precise bug")
    assert difficulty == "medium"
    assert temperature == 0.5

    monkeypatch.setattr(
        PlatformRegistry,
        "get_cheap_platform",
        lambda self: _FakePlatform("scenario: default\ndifficulty: easy"),
    )
    _, _, temperature = classify_user_request("Casual chat")
    assert temperature == 0.7  # Default falls back to balanced

    monkeypatch.setattr(
        PlatformRegistry,
        "get_cheap_platform",
        lambda self: _FakePlatform(
            "scenario: default\ndifficulty: medium\ntemperature: high"
        ),
    )
    _, _, temperature = classify_user_request("Write a creative copy")
    assert temperature == 1.0
