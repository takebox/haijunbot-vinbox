# -*- coding: utf-8 -*-
"""MemoryTool write-time memory value filtering (_should_store_memory) unit tests"""

from unittest.mock import patch

from haijunbot.haijunbot_tools.memory import MemoryTool


def _make_tool():
    return MemoryTool()


class TestShouldStoreMemory:
    """Tests for _should_store_memory heuristic value determination"""

    def _call(self, memory_data):
        return _make_tool()._should_store_memory(memory_data)

    def test_explicit_importance_always_kept(self):
        """Always keep when importance is explicitly annotated (respect explicit intent)"""
        assert self._call({"content": "OK", "importance": "low"}) is True
        assert self._call({"content": "", "importance": "high"}) is True
        assert self._call({"content": "Short", "importance": "medium"}) is True

    def test_empty_content_filtered(self):
        """Empty content is discarded"""
        assert self._call({"content": ""}) is False
        assert self._call({"content": "   "}) is False

    def test_too_short_content_filtered(self):
        """Too-short content (<8 characters) is discarded"""
        assert self._call({"content": "Hello"}) is False
        assert self._call({"content": "Got it"}) is False

    def test_polite_placeholder_filtered(self):
        """Purely polite/placeholder content is discarded"""
        for phrase in [
            "OK",
            "Understood",
            "Got it",
            "Alright",
            "No problem",
            "Thanks",
            "ok",
            "OK OK",
        ]:
            assert self._call({"content": phrase}) is False, f"{phrase} should be filtered"

    def test_meaningful_content_kept(self):
        """Informative content is conservatively kept"""
        assert self._call({"content": "User prefers writing tests in Python"}) is True
        assert (
            self._call(
                {"content": "Fixed the pipelineStore persistence bug, root cause is _persist not being called"}
            )
            is True
        )
        assert self._call({"content": "Decided to adopt dual-field orthogonal memory dimension design"}) is True


class TestSaveSingleMemoryFilter:
    """Tests for _save_single_memory behavior after filter integration"""

    def _call(self, memory_data):
        return _make_tool()._save_single_memory(memory_data)

    def test_filtered_returns_filtered_result(self):
        """Valueless content is filtered, returns storage=filtered and is not persisted"""
        with patch(
            "haijunbot.haijunbot_tools.memory.is_enable_memory_value_filter",
            return_value=True,
        ):
            result = self._call(
                {"memory_type": "project", "nature": "long_term", "content": "OK"}
            )
        assert result["storage"] == "filtered"
        assert result["memory_id"] is None

    def test_meaningful_saved(self):
        """Valuable content is saved normally and persisted"""
        with patch(
            "haijunbot.haijunbot_tools.memory.is_enable_memory_value_filter",
            return_value=True,
        ):
            result = self._call(
                {
                    "memory_type": "project",
                    "nature": "long_term",
                    "content": "User prefers writing tests in Python",
                }
            )
        assert result.get("storage") != "filtered"
        assert result["memory_id"] is not None

    def test_filter_disabled_saves_all(self):
        """When filter is disabled, even valueless content is saved"""
        with patch(
            "haijunbot.haijunbot_tools.memory.is_enable_memory_value_filter",
            return_value=False,
        ):
            result = self._call(
                {"memory_type": "project", "nature": "long_term", "content": "OK"}
            )
        assert result.get("storage") != "filtered"
        assert result["memory_id"] is not None
