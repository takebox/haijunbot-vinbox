# -*- coding: utf-8 -*-
"""MemoryTool pre-storage compression (_compress_memory_content) unit tests"""

from unittest.mock import patch

from haijunbot.haijunbot_tools.memory import MemoryTool


def _make_tool():
    return MemoryTool()


class TestCompressMemoryContent:
    """Tests for _compress_memory_content rule-based summary compression"""

    def _call(self, content):
        return _make_tool()._compress_memory_content(content)

    def test_short_content_unchanged(self):
        """Content below threshold is returned as-is"""
        content = "This is a not-too-long memory content, used to test whether compression logic works correctly."
        with patch(
            "haijunbot.haijunbot_utils.config.get_memory_compress_threshold",
            return_value=2000,
        ):
            assert self._call(content) == content

    def test_empty_content(self):
        """Empty content is returned as-is (pure whitespace is stripped)"""
        assert self._call("") == ""
        assert self._call("   ") == ""

    def test_long_content_compressed(self):
        """Overly long content is compressed, and key signal sentences are retained"""
        # Construct long content exceeding threshold
        filler = "This is an irrelevant filler text used to extend content beyond the compression threshold, it has little information value."
        long_content = filler * 100
        # Add high-signal sentence
        signal = "Important decision: adopt dual-field orthogonal memory dimension design, incompatible with old data."
        content = long_content + signal + long_content

        with patch(
            "haijunbot.haijunbot_utils.config.get_memory_compress_threshold", return_value=10
        ):
            result = self._call(content)

        # Compressed result should contain high-signal sentence
        assert "Important decision" in result
        assert "dual-field orthogonal" in result
        # Compressed result should be shorter than original
        assert len(result) < len(content)

    def test_compress_keeps_head_and_tail(self):
        """Compression preserves beginning and ending sentences"""
        head = "Opening background: the goal of this task is to enhance the memory system."
        tail = "Closing conclusion: the solution is feasible, pending implementation."
        filler = "Middle filler content, with little information value." * 50
        content = head + filler + tail

        with patch(
            "haijunbot.haijunbot_utils.config.get_memory_compress_threshold", return_value=10
        ):
            result = self._call(content)

        assert "Opening background" in result
        assert "Closing conclusion" in result


class TestSaveSingleMemoryCompress:
    """Tests for _save_single_memory behavior after compression integration"""

    def _call(self, memory_data):
        return _make_tool()._save_single_memory(memory_data)

    def test_long_content_compressed_with_original(self):
        """Overly long content is compressed before storage, and original_content is retained"""
        filler = "This is an irrelevant filler text used to extend content beyond the compression threshold, it has little information value."
        content = filler * 100 + "Key conclusion: compression feature verified."

        with (
            patch(
                "haijunbot.haijunbot_utils.config.is_enable_memory_compress",
                return_value=True,
            ),
            patch(
                "haijunbot.haijunbot_utils.config.get_memory_compress_threshold",
                return_value=10,
            ),
        ):
            result = self._call(
                {
                    "memory_type": "project",
                    "nature": "long_term",
                    "content": content,
                }
            )

        assert result["memory_id"] is not None
        # Read back file to confirm original_content is retained
        import json
        from pathlib import Path

        file_path = Path(result["file_path"])
        saved = json.loads(file_path.read_text(encoding="utf-8"))
        assert saved["original_content"] == content
        assert len(saved["content"]) < len(content)
        assert "Key conclusion" in saved["content"]

    def test_compress_disabled_no_original(self):
        """When compression is disabled, content is stored as-is with no original_content"""
        filler = "Filler content." * 100
        content = filler

        with (
            patch(
                "haijunbot.haijunbot_utils.config.is_enable_memory_compress",
                return_value=False,
            ),
        ):
            result = self._call(
                {
                    "memory_type": "project",
                    "nature": "long_term",
                    "content": content,
                }
            )

        import json
        from pathlib import Path

        file_path = Path(result["file_path"])
        saved = json.loads(file_path.read_text(encoding="utf-8"))
        assert "original_content" not in saved
        assert saved["content"] == content
