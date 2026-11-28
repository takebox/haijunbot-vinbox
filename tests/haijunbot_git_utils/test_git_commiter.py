# -*- coding: utf-8 -*-
"""haijunbot_git_utils.git_commiter module unit tests"""

from unittest.mock import patch, MagicMock

from haijunbot.haijunbot_git_utils.git_commiter import GitCommitTool
from haijunbot.haijunbot_utils.tag import ot, ct


class TestGitCommitTool:
    """Test GitCommitTool class"""

    def test_init(self):
        """Test initialization"""
        tool = GitCommitTool()
        assert tool.name == "git_commit_agent"
        assert "git" in tool.labels
        assert "version_control" in tool.labels

    def test_extract_commit_message_success(self):
        """Test successful commit message extraction"""
        tool = GitCommitTool()
        message = f"{ot('COMMIT_MESSAGE')}Test commit message{ct('COMMIT_MESSAGE')}"

        result = tool._extract_commit_message(message)
        assert result == "Test commit message"

    def test_extract_commit_message_with_whitespace(self):
        """Test commit message extraction with whitespace"""
        tool = GitCommitTool()
        message = f"{ot('COMMIT_MESSAGE')}\n  Test commit\n  {ct('COMMIT_MESSAGE')}"

        result = tool._extract_commit_message(message)
        assert result == "Test commit"

    def test_extract_commit_message_case_insensitive(self):
        """Test case-insensitive matching"""
        tool = GitCommitTool()
        # The regex uses the (?i) flag, should be case-insensitive
        message = f"<commit_message>Test{ct('COMMIT_MESSAGE')}"

        result = tool._extract_commit_message(message)
        assert result == "Test"

    def test_extract_commit_message_not_found(self):
        """Test commit message not found"""
        tool = GitCommitTool()
        message = "No commit message here"

        result = tool._extract_commit_message(message)
        assert result is None

    def test_extract_commit_message_empty(self):
        """Test empty commit message"""
        tool = GitCommitTool()
        message = f"{ot('COMMIT_MESSAGE')}{ct('COMMIT_MESSAGE')}"

        result = tool._extract_commit_message(message)
        assert result == ""

    def test_extract_commit_message_special_characters(self):
        """Test commit message with special characters"""
        tool = GitCommitTool()
        message = f"{ot('COMMIT_MESSAGE')}Fix: fixed #123 and @user issue{ct('COMMIT_MESSAGE')}"

        result = tool._extract_commit_message(message)
        assert result == "Fix: fixed #123 and @user issue"

    @patch("haijunbot.haijunbot_git_utils.git_commiter.subprocess.Popen")
    def test_get_last_commit_hash(self, mock_popen):
        """Test getting last commit hash"""
        tool = GitCommitTool()
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"abc123def456\n", b"")
        mock_popen.return_value = mock_process

        result = tool._get_last_commit_hash()
        assert result == "abc123def456"

    @patch("haijunbot.haijunbot_git_utils.git_commiter.subprocess.Popen")
    def test_get_last_commit_hash_empty(self, mock_popen):
        """Test getting commit hash from empty repository"""
        tool = GitCommitTool()
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"", b"fatal: your current branch")
        mock_popen.return_value = mock_process

        result = tool._get_last_commit_hash()
        assert result == ""
