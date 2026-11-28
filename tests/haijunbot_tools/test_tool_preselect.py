# -*- coding: utf-8 -*-
"""Unit tests for tool pre-filtering (_preselect_tools) and ToolRegistry.prompt pre-filtering logic"""

from unittest.mock import patch

from haijunbot.haijunbot_tools.registry import (
    ToolRegistry,
    _preselect_tools,
    _TOOL_PRESELECT_THRESHOLD,
)


def _mk_tool(name, desc):
    return {
        "name": name,
        "description": desc,
        "parameters": {"type": "object", "properties": {}},
    }


def _mk_tools():
    return [
        _mk_tool("read_code", "Read source code file content"),
        _mk_tool("write_file", "Write to file"),
        _mk_tool("search_web", "Search internet information"),
        _mk_tool("execute_script", "Execute script commands"),
        _mk_tool("memory", "Manage memory"),
    ]


def test_preselect_matches_relevant_tools():
    tools = _mk_tools()
    out = _preselect_tools("Read file content", tools)
    names = [t["name"] for t in out]
    # read_code matching "Read" should be selected
    assert "read_code" in names
    # Irrelevant tools (e.g. search_web) should not appear in results
    assert "search_web" not in names


def test_preselect_empty_context_returns_all():
    tools = _mk_tools()
    out = _preselect_tools("", tools)
    assert out == tools


def test_preselect_no_match_returns_all():
    tools = _mk_tools()
    # No keywords match any tool description
    out = _preselect_tools("xyzzy_nonsense_qq", tools)
    assert out == tools


def test_preselect_top_n_limits():
    tools = _mk_tools()
    out = _preselect_tools("file", tools, top_n=1)
    assert len(out) <= 1


def test_preselect_exception_returns_all():
    tools = _mk_tools()
    with patch("jieba.cut", side_effect=Exception("boom")):
        out = _preselect_tools("Read file", tools)
    assert out == tools


def test_prompt_no_task_context_keeps_all():
    """When there is no task_context, prompt injects all tools (no pre-filtering)"""
    r = ToolRegistry()
    all_tools = r.get_all_tools()
    p = r.prompt()
    # All tool names should appear in the prompt
    for t in all_tools:
        assert t["name"] in p


def test_prompt_below_threshold_no_preselect():
    """When tool count is below threshold, no pre-filtering even with task_context"""
    r = ToolRegistry()
    assert len(r.get_all_tools()) <= _TOOL_PRESELECT_THRESHOLD
    p1 = r.prompt()
    p2 = r.prompt("Read and edit file")
    assert p1 == p2


def test_prompt_above_threshold_preselects_and_keeps_required():
    """When tool count exceeds threshold, pre-filtering is enabled and required tool execute_script is always retained"""
    r = ToolRegistry()
    # Construct above-threshold scenario: mock get_all_tools returning many tools
    many_tools = _mk_tools() * 30  # 150 tools, exceeding threshold of 50
    with patch.object(r, "get_all_tools", return_value=many_tools):
        p = r.prompt("Read file")
    # Required tool execute_script should always be retained
    assert "execute_script" in p
    # read_code matching "Read" should be retained
    assert "read_code" in p
    # Irrelevant search_web should not appear in the pre-filtered prompt
    assert "search_web" not in p
