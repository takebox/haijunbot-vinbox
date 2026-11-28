# -*- coding: utf-8 -*-
"""Test that critical functions work correctly"""

import pytest


class TestCriticalFunctions:
    """Test critical functions"""

    @pytest.mark.regression
    def test_haijunbot_agent_import(self):
        """Test that Agent can be imported"""
        from haijunbot.haijunbot_agent import Agent

        assert Agent is not None

    @pytest.mark.regression
    def test_haijunbot_module_import(self):
        """Test that haijunbot module can be imported"""
        from haijunbot.haijunbot_agent import LoopAction

        assert LoopAction is not None

    @pytest.mark.regression
    def test_git_utils_module_exists(self):
        """Test that haijunbot_git_utils module exists"""
        import haijunbot.haijunbot_git_utils

        assert haijunbot.haijunbot_git_utils is not None
