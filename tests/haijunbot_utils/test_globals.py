# -*- coding: utf-8 -*-
"""Unit tests for the haijunbot_utils.globals module"""

from haijunbot.haijunbot_utils.globals import make_agent_name, global_agents


class TestMakeAgentName:
    """Tests for make_agent_name function"""

    def test_unique_name(self):
        """Test unique name"""
        # Clear global agents dictionary
        global_agents.clear()

        name = make_agent_name("test_agent")
        assert name == "test_agent"
        # make_agent_name only generates name, does not automatically add to global_agents

    def test_duplicate_name(self):
        """Test duplicate name"""
        global_agents.clear()

        # Add first agent
        global_agents["test_agent"] = {}

        # Create agent with same name, should automatically add suffix
        name = make_agent_name("test_agent")
        assert name == "test_agent_1"
        # make_agent_name only generates name, does not automatically add to global_agents

    def test_multiple_duplicates(self):
        """Test multiple duplicate names"""
        global_agents.clear()

        # Add multiple agents
        global_agents["test_agent"] = {}
        global_agents["test_agent_1"] = {}
        global_agents["test_agent_2"] = {}

        # Create agent with same name, should find next available number
        name = make_agent_name("test_agent")
        assert name == "test_agent_3"
        # make_agent_name only generates name, does not automatically add to global_agents

    def test_existing_with_suffix(self):
        """Test existing names with suffix"""
        global_agents.clear()

        global_agents["test_agent"] = {}
        global_agents["test_agent_1"] = {}
        # Skip test_agent_2
        global_agents["test_agent_3"] = {}

        # Should find test_agent_2
        name = make_agent_name("test_agent")
        assert name == "test_agent_2"
        # make_agent_name only generates name, does not automatically add to global_agents
