# -*- coding: utf-8 -*-
"""Unit tests for the haijunbot_utils.tag module"""

from haijunbot.haijunbot_utils.tag import ot, ct


class TestTagFunctions:
    """Tests for tag generation functions"""

    def test_ot_basic(self):
        """Test ot function basic functionality"""
        assert ot("test") == "<test>"
        assert ot("div") == "<div>"
        assert ot("span") == "<span>"

    def test_ot_with_underscore(self):
        """Test tag names with underscores"""
        assert ot("test_tag") == "<test_tag>"
        assert ot("my_tag") == "<my_tag>"

    def test_ot_with_dash(self):
        """Test tag names with dashes"""
        assert ot("test-tag") == "<test-tag>"
        assert ot("my-tag") == "<my-tag>"

    def test_ct_basic(self):
        """Test ct function basic functionality"""
        assert ct("test") == "</test>"
        assert ct("div") == "</div>"
        assert ct("span") == "</span>"

    def test_ct_with_underscore(self):
        """Test tag names with underscores"""
        assert ct("test_tag") == "</test_tag>"
        assert ct("my_tag") == "</my_tag>"

    def test_ct_with_dash(self):
        """Test tag names with dashes"""
        assert ct("test-tag") == "</test-tag>"
        assert ct("my-tag") == "</my-tag>"

    def test_ot_ct_pair(self):
        """Test ot and ct used as a pair"""
        tag_name = "message"
        open_tag = ot(tag_name)
        close_tag = ct(tag_name)
        assert open_tag == "<message>"
        assert close_tag == "</message>"

    def test_empty_string(self):
        """Test empty string tag name"""
        assert ot("") == "<>"
        assert ct("") == "</>"

    def test_special_characters(self):
        """Test special characters"""
        assert ot("test@123") == "<test@123>"
        assert ct("test@123") == "</test@123>"
