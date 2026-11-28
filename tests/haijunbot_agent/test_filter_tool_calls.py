# -*- coding: utf-8 -*-
"""Tests for _filter_tool_calls_from_response method

Verify filtering of tool call JSON and surrounding ```json/``` markers.
"""

from unittest.mock import MagicMock

import pytest

from haijunbot.haijunbot_agent.run_loop import AgentRunLoop


@pytest.fixture
def run_loop():
    """Create AgentRunLoop instance (mock agent parameter)"""
    agent = MagicMock()
    return AgentRunLoop(agent)


class TestBareJsonToolCall:
    """Bare JSON tool calls (without fence wrapping)"""

    def test_bare_tool_call_removed(self, run_loop):
        """Bare tool call JSON should be removed"""
        response = 'Some text\n{"name": "execute_script", "arguments": {"interpreter": "bash"}}\nMore text'
        result = run_loop._filter_tool_calls_from_response(response)
        assert '"name"' not in result
        assert "Some text" in result
        assert "More text" in result

    def test_non_tool_json_preserved(self, run_loop):
        """Non-tool JSON (without name+arguments) should be preserved"""
        response = 'Result: {"result": "success", "count": 5}\nDone'
        result = run_loop._filter_tool_calls_from_response(response)
        assert '"result"' in result
        assert '"count"' in result


class TestJsonFence:
    """Tool calls wrapped in ```json ... ```"""

    def test_json_fence_removed(self, run_loop):
        """Tool calls wrapped in ```json should be removed entirely (including fence markers)"""
        response = (
            "Text before\n"
            "```json\n"
            '{"name": "execute_script", "arguments": {"interpreter": "bash"}}\n'
            "```\n"
            "Text after"
        )
        result = run_loop._filter_tool_calls_from_response(response)
        assert "```json" not in result
        assert "```" not in result
        assert '"name"' not in result
        assert "Text before" in result
        assert "Text after" in result

    def test_plain_fence_removed(self, run_loop):
        """Tool calls wrapped in ``` (without json keyword) should be removed entirely"""
        response = (
            "Text before\n"
            "```\n"
            '{"name": "read_code", "arguments": {"path": "test.py"}}\n'
            "```\n"
            "Text after"
        )
        result = run_loop._filter_tool_calls_from_response(response)
        assert '"name"' not in result
        assert "Text before" in result
        assert "Text after" in result

    def test_non_tool_json_fence_preserved(self, run_loop):
        """Non-tool JSON wrapped in ```json should be preserved"""
        response = 'Result:\n```json\n{"result": "success", "count": 5}\n```\nDone'
        result = run_loop._filter_tool_calls_from_response(response)
        assert '"result"' in result
        assert '"count"' in result


class TestMultipleToolCalls:
    """Multiple tool calls"""

    def test_multiple_fenced_removed(self, run_loop):
        """Multiple fenced tool calls should all be removed"""
        response = (
            "Start\n"
            "```json\n"
            '{"name": "tool1", "arguments": {"a": 1}}\n'
            "```\n"
            "Middle\n"
            "```\n"
            '{"name": "tool2", "arguments": {"b": 2}}\n'
            "```\n"
            "End"
        )
        result = run_loop._filter_tool_calls_from_response(response)
        assert '"name"' not in result
        assert "Start" in result
        assert "Middle" in result
        assert "End" in result

    def test_mixed_bare_and_fenced(self, run_loop):
        """Mix of bare JSON and fenced wrapping"""
        response = (
            "Start\n"
            '{"name": "tool1", "arguments": {"a": 1}}\n'
            "Middle\n"
            "```json\n"
            '{"name": "tool2", "arguments": {"b": 2}}\n'
            "```\n"
            "End"
        )
        result = run_loop._filter_tool_calls_from_response(response)
        assert '"name"' not in result
        assert "Start" in result
        assert "Middle" in result
        assert "End" in result


class TestEdgeCases:
    """Edge cases"""

    def test_fence_no_close(self, run_loop):
        """Only opening ```json without closing ```"""
        response = 'Text\n```json\n{"name": "tool1", "arguments": {"a": 1}}\nMore text'
        result = run_loop._filter_tool_calls_from_response(response)
        assert '"name"' not in result
        assert "Text" in result
        assert "More text" in result

    def test_fence_with_whitespace(self, run_loop):
        """Whitespace after ```json"""
        response = (
            "Text\n"
            "```json\n"
            "\n  \n"
            '{"name": "tool1", "arguments": {"a": 1}}\n'
            "```\n"
            "More text"
        )
        result = run_loop._filter_tool_calls_from_response(response)
        assert '"name"' not in result
        assert "Text" in result
        assert "More text" in result



    def test_excessive_newlines_cleaned(self, run_loop):
        """More than 2 consecutive newlines should be compressed to 2"""
        response = "Line1\n\n\n\n\nLine2"
        result = run_loop._filter_tool_calls_from_response(response)
        assert "\n\n\n" not in result

    def test_empty_response(self, run_loop):
        """Empty response"""
        result = run_loop._filter_tool_calls_from_response("")
        assert result == ""

    def test_only_tool_call(self, run_loop):
        """Response contains only one tool call"""
        response = '{"name": "tool1", "arguments": {"a": 1}}'
        result = run_loop._filter_tool_calls_from_response(response)
        assert result.strip() == ""

    def test_only_fenced_tool_call(self, run_loop):
        """Response contains only one fenced tool call"""
        response = '```json\n{"name": "tool1", "arguments": {"a": 1}}\n```'
        result = run_loop._filter_tool_calls_from_response(response)
        assert result.strip() == ""
