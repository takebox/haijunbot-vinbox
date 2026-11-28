# -*- coding: utf-8 -*-
"""utils.py unit tests"""

from unittest.mock import patch, MagicMock


from haijunbot.haijunbot_code_agent.utils import (
    get_git_tracked_files_info,
    get_project_overview,
)


class TestGetGitTrackedFilesInfo:
    """Test get_git_tracked_files_info function"""

    @patch("haijunbot.haijunbot_code_agent.utils.subprocess.run")
    def test_get_git_tracked_files_info_with_few_files(self, mock_run):
        """Test returning file list when file count is below threshold"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "file1.py\nfile2.py\nfile3.js\n"
        mock_run.return_value = mock_result

        result = get_git_tracked_files_info("/tmp/test", max_files=100)

        assert result is not None
        assert "Git-tracked file list" in result
        assert "3 files in total" in result
        assert "file1.py" in result
        assert "file2.py" in result
        assert "file3.js" in result

    @patch("haijunbot.haijunbot_code_agent.utils.subprocess.run")
    def test_get_git_tracked_files_info_with_many_files(self, mock_run):
        """Test returning directory structure when file count exceeds threshold"""
        # Create file list exceeding threshold
        files = [f"src/file{i}.py" for i in range(150)]
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "\n".join(files) + "\n"
        mock_run.return_value = mock_result

        result = get_git_tracked_files_info("/tmp/test", max_files=100)

        assert result is not None
        assert "Git-tracked directory structure" in result
        assert "150 files in total" in result
        assert "src/" in result
        # Should contain directory tree structure
        assert "├──" in result or "└──" in result

    @patch("haijunbot.haijunbot_code_agent.utils.subprocess.run")
    def test_get_git_tracked_files_info_empty_output(self, mock_run):
        """Test git ls-files returning empty output"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        result = get_git_tracked_files_info("/tmp/test")

        assert result is None

    @patch("haijunbot.haijunbot_code_agent.utils.subprocess.run")
    def test_get_git_tracked_files_info_git_error(self, mock_run):
        """Test git command failure"""
        mock_run.side_effect = Exception("git not found")

        result = get_git_tracked_files_info("/tmp/test")

        assert result is None

    @patch("haijunbot.haijunbot_code_agent.utils.subprocess.run")
    def test_get_git_tracked_files_info_non_zero_returncode(self, mock_run):
        """Test git command returning non-zero exit code"""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        result = get_git_tracked_files_info("/tmp/test")

        assert result is None

    @patch("haijunbot.haijunbot_code_agent.utils.subprocess.run")
    def test_get_git_tracked_files_info_with_whitespace(self, mock_run):
        """Test handling output containing whitespace lines"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "file1.py\n\nfile2.py\n  \nfile3.js\n"
        mock_run.return_value = mock_result

        result = get_git_tracked_files_info("/tmp/test")

        assert result is not None
        assert "file1.py" in result
        assert "file2.py" in result
        assert "file3.js" in result

    @patch("haijunbot.haijunbot_code_agent.utils.subprocess.run")
    def test_get_git_tracked_files_info_directory_structure(self, mock_run):
        """Test correctness of directory structure"""
        files = [
            "src/main.py",
            "src/utils.py",
            "tests/test_main.py",
            "README.md",
        ]
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "\n".join(files) + "\n"
        mock_run.return_value = mock_result

        result = get_git_tracked_files_info("/tmp/test", max_files=100)

        assert result is not None
        # Verify directory structure contains src and tests
        assert "src/" in result or "src" in result
        assert "tests/" in result or "tests" in result


class TestGetProjectOverview:
    """Test get_project_overview function"""

    @patch("haijunbot.haijunbot_code_agent.utils.get_recent_commits_with_files")
    @patch("haijunbot.haijunbot_code_agent.utils.get_git_tracked_files_info")
    @patch("haijunbot.haijunbot_code_agent.utils.get_loc_stats")
    def test_get_project_overview_with_all_info(
        self, mock_loc_stats, mock_git_files, mock_commits
    ):
        """Test getting complete project overview"""
        mock_loc_stats.return_value = "Python: 1000 lines"
        mock_git_files.return_value = "Git-tracked file list (10 files in total):\n  - file1.py"
        mock_commits.return_value = [
            {
                "hash": "abc1234",
                "message": "Test commit",
                "files": ["file1.py", "file2.py"],
            }
        ]

        result = get_project_overview("/tmp/test")

        assert result is not None
        assert "Project overview" in result
        assert "Code statistics" in result
        assert "Git-tracked file list" in result
        assert "Recent commits" in result

    @patch("haijunbot.haijunbot_code_agent.utils.get_recent_commits_with_files")
    @patch("haijunbot.haijunbot_code_agent.utils.get_git_tracked_files_info")
    @patch("haijunbot.haijunbot_code_agent.utils.get_loc_stats")
    def test_get_project_overview_no_info(
        self, mock_loc_stats, mock_git_files, mock_commits
    ):
        """Test returning empty string when there is no information"""
        mock_loc_stats.return_value = None
        mock_git_files.return_value = None
        mock_commits.return_value = []

        result = get_project_overview("/tmp/test")

        assert result == ""

    @patch("haijunbot.haijunbot_code_agent.utils.get_recent_commits_with_files")
    @patch("haijunbot.haijunbot_code_agent.utils.get_git_tracked_files_info")
    @patch("haijunbot.haijunbot_code_agent.utils.get_loc_stats")
    def test_get_project_overview_partial_info(
        self, mock_loc_stats, mock_git_files, mock_commits
    ):
        """Test with only partial information"""
        mock_loc_stats.return_value = "Python: 1000 lines"
        mock_git_files.return_value = None
        mock_commits.return_value = []

        result = get_project_overview("/tmp/test")

        assert result is not None
        assert "Code statistics" in result
        assert "Git-tracked file list" not in result
        assert "Recent commits" not in result

    @patch("haijunbot.haijunbot_code_agent.utils.get_recent_commits_with_files")
    @patch("haijunbot.haijunbot_code_agent.utils.get_git_tracked_files_info")
    @patch("haijunbot.haijunbot_code_agent.utils.get_loc_stats")
    def test_get_project_overview_with_many_commit_files(
        self, mock_loc_stats, mock_git_files, mock_commits
    ):
        """Test truncation when commit contains multiple files"""
        mock_loc_stats.return_value = None
        mock_git_files.return_value = None
        mock_commits.return_value = [
            {
                "hash": "abc1234",
                "message": "Test commit",
                "files": [f"file{i}.py" for i in range(10)],
            }
        ]

        result = get_project_overview("/tmp/test")

        assert result is not None
        assert "Recent commits" in result
        # Should only show first 5 files
        assert "file0.py" in result
        assert "file4.py" in result
        assert "..." in result  # Should have ellipsis marker

    @patch("haijunbot.haijunbot_code_agent.utils.get_recent_commits_with_files")
    @patch("haijunbot.haijunbot_code_agent.utils.get_git_tracked_files_info")
    @patch("haijunbot.haijunbot_code_agent.utils.get_loc_stats")
    def test_get_project_overview_exception_handling(
        self, mock_loc_stats, mock_git_files, mock_commits
    ):
        """Test exception handling"""
        mock_loc_stats.side_effect = Exception("Error")
        mock_git_files.side_effect = Exception("Error")
        mock_commits.side_effect = Exception("Error")

        result = get_project_overview("/tmp/test")

        # Should return empty string instead of raising an exception
        assert result == ""

    @patch("haijunbot.haijunbot_code_agent.utils.get_recent_commits_with_files")
    @patch("haijunbot.haijunbot_code_agent.utils.get_git_tracked_files_info")
    @patch("haijunbot.haijunbot_code_agent.utils.get_loc_stats")
    def test_get_project_overview_multiple_commits(
        self, mock_loc_stats, mock_git_files, mock_commits
    ):
        """Test with multiple commits"""
        mock_loc_stats.return_value = None
        mock_git_files.return_value = None
        mock_commits.return_value = [
            {
                "hash": "abc1234",
                "message": "First commit",
                "files": ["file1.py"],
            },
            {
                "hash": "def5678",
                "message": "Second commit",
                "files": ["file2.py"],
            },
        ]

        result = get_project_overview("/tmp/test")

        assert result is not None
        assert "Commit 1" in result
        assert "Commit 2" in result
        assert "First commit" in result
        assert "Second commit" in result
