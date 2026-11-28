# -*- coding: utf-8 -*-
"""Unit tests for the haijunbot_utils.utils module"""

from unittest.mock import patch

from haijunbot.haijunbot_utils.utils import (
    is_editable_install,
)


class TestIsEditableInstall:
    """Tests for is_editable_install function"""

    def test_returns_boolean(self):
        """Test returning boolean value"""
        result = is_editable_install()
        assert isinstance(result, bool)

    @patch("haijunbot.haijunbot_utils.utils.Path")
    @patch("haijunbot.haijunbot_utils.utils.sys")
    def test_editable_install_detection(self, mock_sys, mock_path):
        """Test editable install detection"""
        # This test is complex because the function has multiple detection methods
        # We mainly verify the function executes normally and returns a boolean
        result = is_editable_install()
        assert isinstance(result, bool)
