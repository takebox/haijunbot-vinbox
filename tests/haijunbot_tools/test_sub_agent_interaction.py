# -*- coding: utf-8 -*-
"""Unit tests for sub-agent interaction mode inheritance.

Verify that when SubAgentTool / SubCodeAgentTool create sub-agents, non_interactive
is conditionally inherited from the parent Agent's interaction configuration:
- Parent interactive (non_interactive not True and auto_complete not True) -> sub-agent interactive
- Parent non-interactive (non_interactive=True) -> sub-agent non-interactive
- Parent auto-complete (auto_complete=True) -> sub-agent non-interactive

Implementation note: Capture constructor parameters by patching the real Agent/CodeAgent class's __init__,
rather than replacing the class object itself -- because sub_code_agent internally uses
`isinstance(parent_agent, CodeAgent)` for type checking, replacing the class object would break that check.
"""

from unittest.mock import MagicMock, patch

import pytest

from haijunbot.haijunbot_agent import Agent
from haijunbot.haijunbot_code_agent.code_agent import CodeAgent
from haijunbot.haijunbot_tools import sub_agent as sub_agent_mod
from haijunbot.haijunbot_tools import sub_code_agent as sub_code_agent_mod


class _FakeParent:
    """Minimal usable generic parent Agent stub, only exposing inherited attributes."""

    def __init__(self, non_interactive=None, auto_complete=None):
        self.non_interactive = non_interactive
        self.auto_complete = auto_complete
        self.model = MagicMock()
        self.model.get_messages.return_value = []

    def get_tool_registry(self):
        return None

    def add_memory_tags(self, tags):
        pass


class _FakeCodeParent(CodeAgent):
    """Parent stub that actually inherits CodeAgent, bypassing __init__ to pass isinstance check."""

    def __init__(self, non_interactive=None, auto_complete=None):
        self.non_interactive = non_interactive
        self.auto_complete = auto_complete
        self.model = MagicMock()
        self.model.get_messages.return_value = []

    def get_tool_registry(self):
        return None

    def add_memory_tags(self, tags):
        pass


def _capture_non_interactive(cls, tool, parent):
    """Call tool.execute, capture the non_interactive argument at sub-agent construction.

    Patch the target class's __init__, record kwargs without executing real initialization,
    and give the instance the methods the sub-agent needs (run/get_memory_tags/get_tool_registry etc.).
    """
    captured = {}

    def fake_init(self, *args, **kwargs):
        captured.update(kwargs)
        self.run = MagicMock(return_value="done")
        self.get_memory_tags = MagicMock(return_value=[])
        self.get_tool_registry = MagicMock(return_value=None)
        self.set_user_data = MagicMock()
        self.set_use_tools = MagicMock()

    with patch.object(cls, "__init__", fake_init):
        result = tool.execute({"task": "t", "agent": parent})

    assert result["success"] is True, result
    assert captured, "Sub-agent was not constructed"
    return captured.get("non_interactive")


@pytest.mark.parametrize(
    "parent_non_interactive,parent_auto_complete,expected",
    [
        # Parent interactive: sub-agent must be interactive (core of this fix)
        (False, False, False),
        (False, None, False),
        (None, False, False),
        # Parent exists but neither attribute set -> considered interactive
        (None, None, False),
        # Parent non-interactive -> sub non-interactive
        (True, False, True),
        # Parent auto-complete -> sub non-interactive
        (False, True, True),
        (None, True, True),
    ],
)
def test_sub_agent_inherits_interaction(
    parent_non_interactive, parent_auto_complete, expected
):
    parent = _FakeParent(parent_non_interactive, parent_auto_complete)
    tool = sub_agent_mod.SubAgentTool()
    got = _capture_non_interactive(Agent, tool, parent)
    assert got is expected


@pytest.mark.parametrize(
    "parent_non_interactive,parent_auto_complete,expected",
    [
        (False, False, False),
        (False, None, False),
        (None, False, False),
        (None, None, False),
        (True, False, True),
        (False, True, True),
        (None, True, True),
    ],
)
def test_sub_code_agent_inherits_interaction(
    parent_non_interactive, parent_auto_complete, expected
):
    parent = _FakeCodeParent(parent_non_interactive, parent_auto_complete)
    tool = sub_code_agent_mod.SubCodeAgentTool()
    got = _capture_non_interactive(CodeAgent, tool, parent)
    assert got is expected


def test_sub_agent_no_parent_is_interactive():
    """When no parent Agent is provided, there is no non-interactive basis to inherit, sub-agent remains interactive."""
    tool = sub_agent_mod.SubAgentTool()
    got = _capture_non_interactive(Agent, tool, None)
    assert got is False
