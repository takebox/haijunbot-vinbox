# -*- coding: utf-8 -*-
"""haijunbot_smart_shell.main module unit tests"""

from unittest.mock import patch

from haijunbot.haijunbot_smart_shell.main import (
    _get_markers,
    _get_zsh_markers,
    _check_bash_shell,
)


class TestGetMarkers:
    """Test _get_markers function"""

    def test_returns_tuple(self):
        """Test that it returns a tuple"""
        result = _get_markers()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_markers_are_strings(self):
        """Test that markers are strings"""
        start_marker, end_marker = _get_markers()
        assert isinstance(start_marker, str)
        assert isinstance(end_marker, str)

    def test_markers_contain_fish(self):
        """Test that markers contain fish"""
        start_marker, end_marker = _get_markers()
        assert "FISH" in start_marker.upper()
        assert "FISH" in end_marker.upper()

    def test_markers_are_different(self):
        """Test that start and end markers are different"""
        start_marker, end_marker = _get_markers()
        assert start_marker != end_marker


class TestGetZshMarkers:
    """Test _get_zsh_markers function"""

    def test_returns_tuple(self):
        """Test that it returns a tuple"""
        result = _get_zsh_markers()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_markers_are_strings(self):
        """Test that markers are strings"""
        start_marker, end_marker = _get_zsh_markers()
        assert isinstance(start_marker, str)
        assert isinstance(end_marker, str)

    def test_markers_contain_zsh(self):
        """Test that markers contain zsh"""
        start_marker, end_marker = _get_zsh_markers()
        assert "ZSH" in start_marker.upper()
        assert "ZSH" in end_marker.upper()

    def test_markers_are_different(self):
        """Test that start and end markers are different"""
        start_marker, end_marker = _get_zsh_markers()
        assert start_marker != end_marker


class TestCheckBashShell:
    """Test _check_bash_shell function"""

    @patch("haijunbot.haijunbot_smart_shell.main.get_shell_name")
    def test_bash_shell(self, mock_get_shell_name):
        """Test bash shell"""
        mock_get_shell_name.return_value = "bash"
        result = _check_bash_shell()
        assert result is True

    @patch("haijunbot.haijunbot_smart_shell.main.get_shell_name")
    def test_non_bash_shell(self, mock_get_shell_name):
        """Test non-bash shell"""
        mock_get_shell_name.return_value = "fish"
        result = _check_bash_shell()
        assert result is False

    @patch("haijunbot.haijunbot_smart_shell.main.get_shell_name")
    def test_zsh_shell(self, mock_get_shell_name):
        """Test zsh shell"""
        mock_get_shell_name.return_value = "zsh"
        result = _check_bash_shell()
        assert result is False
