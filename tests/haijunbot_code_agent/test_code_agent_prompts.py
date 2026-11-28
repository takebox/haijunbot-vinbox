# -*- coding: utf-8 -*-
"""code_agent_prompts.py unit tests"""

from haijunbot.haijunbot_code_agent.code_agent_prompts import get_system_prompt
from haijunbot.haijunbot_utils.scenario_prompts import _get_scenario_types

_SCENARIO_SUBDIR = "code_agent_system"


class TestGetSystemPrompt:
    """Test get_system_prompt function"""

    def test_get_system_prompt_returns_string(self):
        """Test that the return value is a string"""
        result = get_system_prompt()

        assert isinstance(result, str)
        assert len(result) > 0



    def test_get_system_prompt_contains_core_behaviors(self):
        """Test that it contains core behavior guidelines"""
        result = get_system_prompt()

        # Check if it contains the main workflow stages (after refactoring, [MODE:] prefix is no longer enforced per turn)
        assert "understand current state" in result or "current state" in result
        assert "plan" in result
        assert "execute" in result
        assert "verify" in result or "wrap up" in result

    def test_get_system_prompt_no_forced_mode_prefix(self):
        """Test that it does not force [MODE:] stage identifiers per turn"""
        result = get_system_prompt()

        assert "[MODE:" not in result

    def test_get_system_prompt_non_empty(self):
        """Test that the prompt is not empty"""
        result = get_system_prompt()

        assert result.strip() != ""

    def test_get_system_prompt_consistent(self):
        """Test that multiple calls return consistent results"""
        result1 = get_system_prompt()
        result2 = get_system_prompt()

        assert result1 == result2

    def test_all_scenarios_load_and_use_modern_style(self):
        """All scenario files can be loaded, and [MODE:] prefix is no longer enforced nor classical Chinese style used"""
        scenarios = _get_scenario_types(_SCENARIO_SUBDIR)
        assert scenarios, "Scenario directory should contain at least one scenario"

        for scenario in scenarios.keys():
            prompt = get_system_prompt(scenario)
            assert isinstance(prompt, str) and prompt.strip(), f"{scenario} system prompt is empty"
            assert "[MODE:" not in prompt, f"{scenario} should not enforce [MODE:] prefix"
            assert "classical Chinese" not in prompt, f"{scenario} should not use classical Chinese style"

    def test_inherit_core_scenario_composes_with_default_core(self):
        """Scenarios declaring inherit_core = own key points + default shared core"""
        prompt = get_system_prompt("feature")
        assert "Feature Development" in prompt
        assert "## Main Workflow" in prompt
        assert "## Tool Usage" in prompt

    def test_detailed_design_stays_standalone(self):
        """detailed_design does not contain shared code core, maintains independent template"""
        prompt = get_system_prompt("detailed_design")
        assert "Detailed Design Document Template" in prompt
        assert "## Main Workflow" not in prompt
