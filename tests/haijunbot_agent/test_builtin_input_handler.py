# -*- coding: utf-8 -*-
"""Tests for utility functions in builtin_input_handler"""

from haijunbot.haijunbot_agent.builtin_input_handler import extract_tags_from_text


class TestExtractTagsFromText:
    """Tests for extract_tags_from_text function"""

    def test_empty_input(self):
        """Test empty input"""
        assert extract_tags_from_text("") == []
        assert extract_tags_from_text(None) == []

    def test_no_tags(self):
        """Test plain text with no tags"""
        text = "This is a normal user input with no tags"
        assert extract_tags_from_text(text) == []

    def test_single_tag(self):
        """Test single tag"""
        text = "Please help me analyze the code '<rule:python_best_practices>'"
        assert extract_tags_from_text(text) == ["rule:python_best_practices"]

    def test_multiple_tags(self):
        """Test multiple tags"""
        text = "'<rule:code_style>' and '<rule:security>' are both important"
        assert extract_tags_from_text(text) == ["rule:code_style", "rule:security"]

    def test_multimodal_list_format(self):
        """Test multimodal content (list format)"""
        content = [
            {"type": "text", "text": "Please load rule '<rule:test_rule>'"},
            {"type": "image", "url": "http://example.com/image.png"},
        ]
        assert extract_tags_from_text(content) == ["rule:test_rule"]

    def test_multimodal_multiple_text_blocks(self):
        """Test multiple text blocks in multimodal content"""
        content = [
            {"type": "text", "text": "'<rule:first>'"},
            {"type": "text", "text": "and '<rule:second>'"},
        ]
        assert extract_tags_from_text(content) == ["rule:first", "rule:second"]

    def test_multimodal_empty_list(self):
        """Test empty list input"""
        assert extract_tags_from_text([]) == []

    def test_various_tag_types(self):
        """Test different types of tags"""
        text = "'<Pin>' '<SetConfig>' '<rule:custom_rule>' '<AddDir>'"
        assert extract_tags_from_text(text) == [
            "Pin",
            "SetConfig",
            "rule:custom_rule",
            "AddDir",
        ]

    def test_tag_without_quotes(self):
        """Test tags without single quotes (should not be matched)"""
        text = "This <rule:test> will not be matched because there are no single quotes"
        assert extract_tags_from_text(text) == []

    def test_incomplete_tag(self):
        """Test incomplete tag format"""
        text = "'<rule:incomplete"  # Missing closing > and >'
        assert extract_tags_from_text(text) == []
