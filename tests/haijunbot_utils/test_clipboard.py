# -*- coding: utf-8 -*-
"""Unit tests for the haijunbot_utils.clipboard module"""

import subprocess
from unittest.mock import patch, MagicMock

from haijunbot.haijunbot_utils.clipboard import copy_to_clipboard


class TestCopyToClipboard:
    """Tests for the copy_to_clipboard function"""

    @patch("haijunbot.haijunbot_utils.clipboard.platform.system")
    @patch("haijunbot.haijunbot_utils.clipboard.subprocess.Popen")
    @patch("haijunbot.haijunbot_utils.output.PrettyOutput.auto_print")
    def test_windows_clipboard(self, mock_print, mock_popen, mock_platform):
        """Test Windows clipboard"""
        mock_platform.return_value = "Windows"
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_popen.return_value = mock_process

        copy_to_clipboard("test text")

        mock_popen.assert_called_once()
        mock_process.stdin.write.assert_called_once_with(b"test text")
        mock_process.stdin.close.assert_called_once()

    @patch("haijunbot.haijunbot_utils.clipboard.platform.system")
    @patch("haijunbot.haijunbot_utils.clipboard.subprocess.Popen")
    @patch("haijunbot.haijunbot_utils.output.PrettyOutput.auto_print")
    def test_macos_clipboard(self, mock_print, mock_popen, mock_platform):
        """Test macOS clipboard"""
        mock_platform.return_value = "Darwin"
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_popen.return_value = mock_process

        copy_to_clipboard("test text")

        mock_popen.assert_called_once_with(
            ["pbcopy"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        mock_process.stdin.write.assert_called_once_with(b"test text")

    @patch("haijunbot.haijunbot_utils.clipboard.platform.system")
    @patch("haijunbot.haijunbot_utils.clipboard.subprocess.Popen")
    @patch("haijunbot.haijunbot_utils.output.PrettyOutput.auto_print")
    def test_linux_xsel_clipboard(self, mock_print, mock_popen, mock_platform):
        """Test Linux xsel clipboard"""
        mock_platform.return_value = "Linux"
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_popen.return_value = mock_process

        copy_to_clipboard("test text")

        # Should try xsel first
        calls = mock_popen.call_args_list
        assert len(calls) >= 1
        assert calls[0][0][0] == ["xsel", "-b", "-i"]

    @patch("haijunbot.haijunbot_utils.clipboard.platform.system")
    @patch("haijunbot.haijunbot_utils.clipboard.subprocess.Popen")
    @patch("haijunbot.haijunbot_utils.output.PrettyOutput.auto_print")
    def test_linux_xsel_not_found_fallback_xclip(
        self, mock_print, mock_popen, mock_platform
    ):
        """Test fallback to xclip when Linux xsel is not found"""
        mock_platform.return_value = "Linux"
        # First call (xsel) raises FileNotFoundError, second call (xclip) succeeds
        mock_popen.side_effect = [
            FileNotFoundError(),
            MagicMock(stdin=MagicMock()),
        ]
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_popen.side_effect = [FileNotFoundError(), mock_process]

        copy_to_clipboard("test text")

        # Should have tried both xsel and xclip
        assert mock_popen.call_count >= 2

    @patch("haijunbot.haijunbot_utils.clipboard.platform.system")
    @patch("haijunbot.haijunbot_utils.clipboard.subprocess.Popen")
    @patch("haijunbot.haijunbot_utils.output.PrettyOutput.auto_print")
    def test_windows_clipboard_error(self, mock_print, mock_popen, mock_platform):
        """Test Windows clipboard error handling"""
        mock_platform.return_value = "Windows"
        mock_popen.side_effect = Exception("clip error")

        copy_to_clipboard("test text")

        # Should print warning
        mock_print.assert_called()

    @patch("haijunbot.haijunbot_utils.clipboard.platform.system")
    @patch("haijunbot.haijunbot_utils.clipboard.subprocess.Popen")
    @patch("haijunbot.haijunbot_utils.output.PrettyOutput.auto_print")
    def test_linux_no_clipboard_tools(self, mock_print, mock_popen, mock_platform):
        """Test Linux with no clipboard tools available"""
        mock_platform.return_value = "Linux"
        mock_popen.side_effect = FileNotFoundError()

        copy_to_clipboard("test text")

        # Should print warning
        mock_print.assert_called()
