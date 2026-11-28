# -*- coding: utf-8 -*-
"""MemoryTool._execute_smart_search token limit unit tests"""

from unittest.mock import MagicMock, patch

from haijunbot.haijunbot_memory_organizer.smart_retrieval import Memory
from haijunbot.haijunbot_tools.memory import MemoryTool


def _make_memory(mid: str, content: str) -> Memory:
    return Memory(
        id=mid,
        memory_type="project",
        nature="long_term",
        tags=["tag"],
        content=content,
        created_at="2026-01-01",
    )


class TestSmartSearchTokenLimit:
    """Tests for _execute_smart_search token budget filtering"""

    def _make_tool(self):
        return object.__new__(MemoryTool)

    def _patch_retriever(self, memories):
        retriever = MagicMock()
        retriever.semantic_search.return_value = memories
        return patch(
            "haijunbot.haijunbot_tools.memory._get_smart_retriever",
            return_value=retriever,
        )

    def test_short_memories_all_returned(self):
        """When memory content is short, all are returned without token limit impact"""
        tool = self._make_tool()
        memories = [_make_memory("m1", "Short memory one"), _make_memory("m2", "Short memory two")]
        with (
            self._patch_retriever(memories),
            patch(
                "haijunbot.haijunbot_tools.memory.get_max_input_token_count",
                return_value=100000,
            ),
        ):
            result = tool._execute_smart_search(
                args={}, memory_types=["project"], query="test", limit=None
            )
        assert result["success"] is True
        assert "m1" in result["stdout"]
        assert "m2" in result["stdout"]

    def test_oversized_memory_truncated_by_token_budget(self):
        """Overly long memory is truncated when it exceeds token budget"""
        tool = self._make_tool()
        # First one is overly long, second is short
        memories = [
            _make_memory("m1", "x" * 10000),
            _make_memory("m2", "Short memory"),
        ]
        with (
            self._patch_retriever(memories),
            patch(
                "haijunbot.haijunbot_tools.memory.get_max_input_token_count",
                return_value=100,  # Extremely small budget triggers token limit
            ),
        ):
            result = tool._execute_smart_search(
                args={}, memory_types=["project"], query="test", limit=None
            )
        assert result["success"] is True
        # m1 is overly long and should be truncated; m2 may also not be returned because m1 already exceeded budget
        assert "m1" not in result["stdout"]

    def test_uses_agent_remaining_tokens(self):
        """Prioritize using agent remaining tokens for budget calculation"""
        tool = self._make_tool()
        memories = [_make_memory("m1", "Short memory")]
        agent = MagicMock()
        agent.model.get_remaining_token_count.return_value = 1000

        with (
            self._patch_retriever(memories),
            patch(
                "haijunbot.haijunbot_tools.memory.calculate_token_limit",
                return_value=500,
            ) as mock_calc,
        ):
            result = tool._execute_smart_search(
                args={"agent": agent},
                memory_types=["project"],
                query="test",
                limit=None,
            )
        mock_calc.assert_called_once_with(1000)
        assert result["success"] is True
        assert "m1" in result["stdout"]

    def test_fallback_to_input_window(self):
        """Fall back to 2/3 of input window when no agent"""
        tool = self._make_tool()
        memories = [_make_memory("m1", "Short memory")]
        with (
            self._patch_retriever(memories),
            patch(
                "haijunbot.haijunbot_tools.memory.get_max_input_token_count",
                return_value=3000,
            ),
        ):
            result = tool._execute_smart_search(
                args={}, memory_types=["project"], query="test", limit=None
            )
        assert result["success"] is True
        assert "m1" in result["stdout"]
