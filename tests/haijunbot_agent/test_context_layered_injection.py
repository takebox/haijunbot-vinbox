# -*- coding: utf-8 -*-
"""Unit tests for context engineering - layered injection budget (_get_memory_retrieval_budget)"""

from unittest.mock import patch

from haijunbot.haijunbot_agent import Agent


def _make_agent():
    # Do not trigger __init__ full initialization, only for binding methods
    agent = Agent.__new__(Agent)
    return agent


class TestGetMemoryRetrievalBudget:
    """Tests for Agent._get_memory_retrieval_budget layered memory retrieval budget"""

    def test_uses_layer_ratio_budget(self):
        agent = _make_agent()
        with (
            patch(
                "haijunbot.haijunbot_utils.config.get_max_input_token_count",
                return_value=200000,
            ),
            patch(
                "haijunbot.haijunbot_utils.config.get_context_budget_usage_ratio",
                return_value=0.9,
            ),
            patch(
                "haijunbot.haijunbot_utils.config.calculate_layer_token_budget",
                return_value={"memory_retrieval": 36000, "system_prompt": 36000},
            ),
        ):
            budget = agent._get_memory_retrieval_budget()
        # 200000 x 0.9 = 180000, memory_retrieval layer at 0.20 -> 36000
        assert budget == 36000

    def test_falls_back_on_exception(self):
        """Fall back to configured fixed budget when budget calculation raises exception"""
        agent = _make_agent()
        with (
            patch(
                "haijunbot.haijunbot_utils.config.get_max_input_token_count",
                side_effect=Exception("boom"),
            ),
            patch(
                "haijunbot.haijunbot_utils.config.get_context_memory_retrieval_budget",
                return_value=3000,
            ),
        ):
            budget = agent._get_memory_retrieval_budget()
        assert budget == 3000

    def test_missing_layer_key_returns_zero(self):
        """Return 0 when memory_retrieval key is missing from layered budget"""
        agent = _make_agent()
        with (
            patch(
                "haijunbot.haijunbot_utils.config.get_max_input_token_count",
                return_value=100000,
            ),
            patch(
                "haijunbot.haijunbot_utils.config.get_context_budget_usage_ratio",
                return_value=0.9,
            ),
            patch(
                "haijunbot.haijunbot_utils.config.calculate_layer_token_budget",
                return_value={"system_prompt": 1000},
            ),
        ):
            budget = agent._get_memory_retrieval_budget()
        assert budget == 0
