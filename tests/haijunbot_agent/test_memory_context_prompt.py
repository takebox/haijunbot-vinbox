# -*- coding: utf-8 -*-
"""Unit tests for MemoryManager.prepare_memory_context_prompt"""

from unittest.mock import MagicMock, patch

from haijunbot.haijunbot_agent.memory_manager import MemoryManager
from haijunbot.haijunbot_memory_organizer.smart_retrieval import Memory


def _make_memory(mid: str, content: str, tags=None, mtype="project_long_term"):
    # Support flat type names (e.g. project_long_term / global_long_term), split into dual fields
    if mtype.startswith("global"):
        memory_type, nature = "global", mtype.split("_", 1)[1]
    else:
        memory_type, nature = "project", mtype.split("_", 1)[1]
    return Memory(
        id=mid,
        memory_type=memory_type,
        nature=nature,
        tags=tags or ["tag"],
        content=content,
        created_at="2026-01-01",
    )


def _make_manager():
    agent = MagicMock()
    agent.get_tool_registry.return_value = None
    return MemoryManager(agent)


class TestPrepareMemoryContextPrompt:
    """Tests for prepare_memory_context_prompt method"""

    def test_empty_input_returns_empty(self):
        """Empty input returns empty string"""
        manager = _make_manager()
        assert manager.prepare_memory_context_prompt("") == ""
        assert manager.prepare_memory_context_prompt("   ") == ""

    def test_no_memory_dirs_returns_empty(self, monkeypatch, tmp_path):
        """Returns empty string when memory directory does not exist, no retrieval executed"""
        manager = _make_manager()
        # Simulate memory directory not existing
        monkeypatch.setattr("pathlib.Path.exists", lambda self: False)
        result = manager.prepare_memory_context_prompt("test task")
        assert result == ""

    def test_no_related_memories_returns_empty(self, monkeypatch):
        """Returns empty string when no related memories"""
        manager = _make_manager()
        # Simulate memory directory existing
        monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
        retriever = MagicMock()
        retriever.semantic_search.return_value = []
        with patch(
            "haijunbot.haijunbot_memory_organizer.smart_retrieval.SmartRetriever",
            return_value=retriever,
        ):
            result = manager.prepare_memory_context_prompt("test task")
        assert result == ""

    def test_returns_formatted_memories(self, monkeypatch):
        """Returns formatted prompt when related memories exist"""
        manager = _make_manager()
        monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
        memories = [
            _make_memory(
                "m1", "Project config: using pytest for testing", tags=["testing", "pytest"]
            ),
            _make_memory(
                "m2",
                "General experience: code review points",
                tags=["code review"],
                mtype="global_long_term",
            ),
        ]
        retriever = MagicMock()
        retriever.semantic_search.return_value = memories
        with patch(
            "haijunbot.haijunbot_memory_organizer.smart_retrieval.SmartRetriever",
            return_value=retriever,
        ):
            result = manager.prepare_memory_context_prompt("How to test code")
        assert "project/long_term" in result
        assert "global/long_term" in result
        assert "Project config: using pytest for testing" in result
        assert "General experience: code review points" in result
        assert "testing/pytest" in result

    def test_long_content_truncated(self, monkeypatch):
        """Overly long memory content is truncated to 500 characters"""
        manager = _make_manager()
        monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
        long_content = "x" * 1000
        memories = [_make_memory("m1", long_content)]
        retriever = MagicMock()
        retriever.semantic_search.return_value = memories
        with patch(
            "haijunbot.haijunbot_memory_organizer.smart_retrieval.SmartRetriever",
            return_value=retriever,
        ):
            result = manager.prepare_memory_context_prompt("test task")
        assert "..." in result
        assert "x" * 500 in result
        assert "x" * 501 not in result

    def test_calls_semantic_search_with_correct_params(self, monkeypatch):
        """Verify semantic_search is called with correct parameters"""
        manager = _make_manager()
        monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
        retriever = MagicMock()
        retriever.semantic_search.return_value = []
        with patch(
            "haijunbot.haijunbot_memory_organizer.smart_retrieval.SmartRetriever",
            return_value=retriever,
        ):
            manager.prepare_memory_context_prompt("Fix bug")
        retriever.semantic_search.assert_called_once_with(
            query="Fix bug",
            memory_types=["project", "global"],
            natures=["long_term"],
            limit=5,
        )

    def test_exception_returns_empty(self, monkeypatch):
        """Returns empty string on retrieval exception, does not affect main flow"""
        manager = _make_manager()
        monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
        with patch(
            "haijunbot.haijunbot_memory_organizer.smart_retrieval.SmartRetriever",
            side_effect=Exception("Retrieval failed"),
        ):
            result = manager.prepare_memory_context_prompt("test task")
        assert result == ""

    def test_retrieval_budget_truncation(self, monkeypatch):
        """Truncation when cumulative token count of retrieval results exceeds budget"""
        from haijunbot.haijunbot_utils.config import GLOBAL_CONFIG_DATA

        manager = _make_manager()
        monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
        # 5 memories, each estimated at ~25 tokens (including tags and numbering prefix)
        memories = [_make_memory(f"m{i}", f"Memory content {i}") for i in range(5)]
        retriever = MagicMock()
        retriever.semantic_search.return_value = memories
        key = "context_memory_retrieval_budget"
        original = GLOBAL_CONFIG_DATA.get(key)
        try:
            # Budget 60: only enough for 2 entries (25x2=50), 3rd entry cumulative 75 exceeds budget and is truncated
            GLOBAL_CONFIG_DATA[key] = 60
            with patch(
                "haijunbot.haijunbot_memory_organizer.smart_retrieval.SmartRetriever",
                return_value=retriever,
            ):
                result = manager.prepare_memory_context_prompt("test task")
        finally:
            if original is None:
                GLOBAL_CONFIG_DATA.pop(key, None)
            else:
                GLOBAL_CONFIG_DATA[key] = original
        # Should only inject first 2 entries, rest truncated
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" not in result

    def test_retrieval_budget_no_truncation_when_under(self, monkeypatch):
        """All injected when retrieval results are under budget"""
        from haijunbot.haijunbot_utils.config import GLOBAL_CONFIG_DATA

        manager = _make_manager()
        monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
        memories = [_make_memory(f"m{i}", f"Memory content {i}") for i in range(3)]
        retriever = MagicMock()
        retriever.semantic_search.return_value = memories
        key = "context_memory_retrieval_budget"
        original = GLOBAL_CONFIG_DATA.get(key)
        try:
            GLOBAL_CONFIG_DATA[key] = 10000  # Large budget, no truncation
            with patch(
                "haijunbot.haijunbot_memory_organizer.smart_retrieval.SmartRetriever",
                return_value=retriever,
            ):
                result = manager.prepare_memory_context_prompt("test task")
        finally:
            if original is None:
                GLOBAL_CONFIG_DATA.pop(key, None)
            else:
                GLOBAL_CONFIG_DATA[key] = original
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" in result
