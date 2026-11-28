# -*- coding: utf-8 -*-
"""Unit tests for the haijunbot_utils.git_utils module"""

from unittest.mock import patch, MagicMock

from haijunbot.haijunbot_utils.git_utils import (
    detect_large_code_deletion,
    get_modified_line_ranges,
    is_file_in_git_repo,
)


class TestDetectLargeCodeDeletion:
    """Tests for detect_large_code_deletion function"""

    @patch("haijunbot.haijunbot_utils.git_utils.subprocess.run")
    def test_no_large_deletion(self, mock_run):
        """Test no large deletion scenario"""
        # Simulate git diff output: small deletion
        mock_run.return_value = MagicMock(
            returncode=0, stdout=" 5 files changed, 10 insertions(+), 5 deletions(-)"
        )

        result = detect_large_code_deletion(threshold=200)
        assert result is None

    @patch("haijunbot.haijunbot_utils.git_utils.subprocess.run")
    def test_large_deletion_detected(self, mock_run):
        """Test large deletion detected"""
        # Simulate git diff output: large deletion
        mock_run.return_value = MagicMock(
            returncode=0, stdout=" 10 files changed, 50 insertions(+), 300 deletions(-)"
        )

        result = detect_large_code_deletion(threshold=200)
        assert result is not None
        assert result["insertions"] == 50
        assert result["deletions"] == 300
        assert result["net_deletions"] == 250

    @patch("haijunbot.haijunbot_utils.git_utils.subprocess.run")
    def test_custom_threshold(self, mock_run):
        """Test custom threshold"""
        # Simulate git diff output: moderate deletion
        mock_run.return_value = MagicMock(
            returncode=0, stdout=" 5 files changed, 10 insertions(+), 150 deletions(-)"
        )

        # Use smaller threshold
        result = detect_large_code_deletion(threshold=100)
        assert result is not None
        assert result["net_deletions"] == 140

        # Use larger threshold
        result = detect_large_code_deletion(threshold=200)
        assert result is None

    @patch("haijunbot.haijunbot_utils.git_utils.subprocess.run")
    def test_no_changes(self, mock_run):
        """Test no changes scenario"""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        result = detect_large_code_deletion()
        assert result is None

    @patch("haijunbot.haijunbot_utils.git_utils.subprocess.run")
    def test_exception_handling(self, mock_run):
        """Test exception handling"""
        mock_run.side_effect = Exception("Git error")

        result = detect_large_code_deletion()
        assert result is None


class TestGetModifiedLineRanges:
    """Tests for get_modified_line_ranges function"""

    @patch("haijunbot.haijunbot_utils.git_utils.subprocess.run")
    def test_single_file_single_range(self, mock_run):
        """Test single file with single range"""
        diff_output = """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -10,5 +10,7 @@
 line 10
+new line 1
+new line 2
 line 11
"""
        mock_run.return_value = MagicMock(returncode=0, stdout=diff_output)

        result = get_modified_line_ranges()
        assert "test.py" in result
        assert len(result["test.py"]) == 1
        # @@ -10,5 +10,7 @@ means starting from line 10, 7 new lines added, so end line is 10 + 7 - 1 = 16
        assert result["test.py"][0] == (10, 16)

    @patch("haijunbot.haijunbot_utils.git_utils.subprocess.run")
    def test_multiple_files_multiple_ranges(self, mock_run):
        """Test multiple files with multiple ranges"""
        diff_output = """diff --git a/file1.py b/file1.py
+++ b/file1.py
@@ -5,3 +5,5 @@
 line 5
+new line
 line 6
diff --git a/file2.py b/file2.py
+++ b/file2.py
@@ -20,2 +20,4 @@
 line 20
+new line
"""
        mock_run.return_value = MagicMock(returncode=0, stdout=diff_output)

        result = get_modified_line_ranges()
        assert "file1.py" in result
        assert "file2.py" in result
        assert len(result["file1.py"]) >= 1
        assert len(result["file2.py"]) >= 1

    @patch("haijunbot.haijunbot_utils.git_utils.subprocess.run")
    def test_no_changes(self, mock_run):
        """Test no changes scenario"""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        result = get_modified_line_ranges()
        assert result == {}


class TestIsFileInGitRepo:
    """Tests for is_file_in_git_repo function"""

    @patch("haijunbot.haijunbot_utils.git_utils.subprocess.run")
    def test_file_in_repo(self, mock_run):
        """Test file in repository"""
        mock_run.return_value = MagicMock(returncode=0, stdout="/path/to/repo\n")

        with patch(
            "haijunbot.haijunbot_utils.git_utils.os.path.abspath",
            return_value="/path/to/repo/file.py",
        ):
            result = is_file_in_git_repo("file.py")
            assert result is True

    @patch("haijunbot.haijunbot_utils.git_utils.subprocess.run")
    def test_file_not_in_repo(self, mock_run):
        """Test file not in repository"""
        mock_run.return_value = MagicMock(returncode=0, stdout="/path/to/repo\n")

        # Simulate file path not under repository root
        with patch("haijunbot.haijunbot_utils.git_utils.os.path.abspath") as mock_abspath:

            def abspath_side_effect(path):
                if path == "file.py":
                    return "/other/path/file.py"
                elif path == "/path/to/repo":
                    return "/path/to/repo"
                return path

            mock_abspath.side_effect = abspath_side_effect

            result = is_file_in_git_repo("file.py")
            assert result is False

    @patch("haijunbot.haijunbot_utils.git_utils.subprocess.run")
    def test_exception_handling(self, mock_run):
        """Test exception handling"""
        mock_run.side_effect = Exception("Git error")

        result = is_file_in_git_repo("file.py")
        assert result is False
