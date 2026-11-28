# -*- coding: utf-8 -*-
"""Unit tests for the haijunbot_utils.fzf module"""

import pytest
from unittest.mock import patch, MagicMock

from haijunbot.haijunbot_utils.fzf import fzf_select


class TestFzfSelect:
    """Tests for fzf_select function"""

    def test_fzf_not_available(self):
        """Test fzf not available"""
        with patch("haijunbot.haijunbot_utils.fzf.shutil.which", return_value=None):
            result = fzf_select(["option1", "option2"])
            assert result is None

    def test_empty_options(self):
        """Test empty options list"""
        with patch("haijunbot.haijunbot_utils.fzf.shutil.which", return_value="/usr/bin/fzf"):
            result = fzf_select([])
            assert result is None

    def test_string_options_success(self):
        """Test successful selection from string options"""
        with patch("haijunbot.haijunbot_utils.fzf.shutil.which", return_value="/usr/bin/fzf"):
            with patch("haijunbot.haijunbot_utils.fzf.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout="option2\n", stderr=""
                )
                result = fzf_select(["option1", "option2", "option3"])
                assert result == "option2"
                assert mock_run.called

    def test_string_options_cancelled(self):
        """Test cancelled selection"""
        with patch("haijunbot.haijunbot_utils.fzf.shutil.which", return_value="/usr/bin/fzf"):
            with patch("haijunbot.haijunbot_utils.fzf.subprocess.run") as mock_run:
                # CalledProcessError indicates user cancelled
                import subprocess

                mock_run.side_effect = subprocess.CalledProcessError(1, "fzf")
                result = fzf_select(["option1", "option2"])
                assert result is None

    def test_dict_options_with_key(self):
        """Test dict options (with key)"""
        with patch("haijunbot.haijunbot_utils.fzf.shutil.which", return_value="/usr/bin/fzf"):
            with patch("haijunbot.haijunbot_utils.fzf.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout="value2\n", stderr=""
                )
                options = [
                    {"name": "option1", "value": "value1"},
                    {"name": "option2", "value": "value2"},
                ]
                result = fzf_select(options, key="name")
                assert result == "value2"

    def test_dict_options_without_key(self):
        """Test dict options (without key) should raise error"""
        with patch("haijunbot.haijunbot_utils.fzf.shutil.which", return_value="/usr/bin/fzf"):
            options = [{"name": "option1"}, {"name": "option2"}]
            with pytest.raises(ValueError, match="key must be provided"):
                fzf_select(options)

    def test_custom_prompt(self):
        """Test custom prompt"""
        with patch("haijunbot.haijunbot_utils.fzf.shutil.which", return_value="/usr/bin/fzf"):
            with patch("haijunbot.haijunbot_utils.fzf.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout="option1\n", stderr=""
                )
                fzf_select(["option1"], prompt="Choose> ")
                # Verify prompt parameter was passed
                call_args = mock_run.call_args[0][0]
                assert "--prompt" in call_args
                prompt_index = call_args.index("--prompt")
                assert call_args[prompt_index + 1] == "Choose> "

    def test_file_not_found_error(self):
        """Test FileNotFoundError handling"""
        with patch("haijunbot.haijunbot_utils.fzf.shutil.which", return_value="/usr/bin/fzf"):
            with patch("haijunbot.haijunbot_utils.fzf.subprocess.run") as mock_run:
                mock_run.side_effect = FileNotFoundError("fzf not found")
                result = fzf_select(["option1", "option2"])
                assert result is None
