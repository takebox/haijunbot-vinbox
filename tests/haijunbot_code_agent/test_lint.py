# -*- coding: utf-8 -*-
"""lint.py unit tests"""

from unittest.mock import patch

from haijunbot.haijunbot_utils.collections import CaseInsensitiveDict
from haijunbot.haijunbot_utils.config import get_lint_tools_config
from haijunbot.haijunbot_code_agent.lint import (
    get_lint_commands_for_files,
    LINT_COMMAND_TEMPLATES_BY_FILE,
)


class TestLintTools:
    """Tests for lint tool related functionality"""

    def test_lint_tools_default_config(self):
        """Test default lint tool configuration"""
        # Verify configuration for some common file types
        assert ".py" in LINT_COMMAND_TEMPLATES_BY_FILE
        py_templates = LINT_COMMAND_TEMPLATES_BY_FILE[".py"]
        assert any("ruff check" in t for t in py_templates)
        assert any("ty check" in t for t in py_templates)

        assert ".js" in LINT_COMMAND_TEMPLATES_BY_FILE
        js_templates = LINT_COMMAND_TEMPLATES_BY_FILE[".js"]
        assert any("eslint" in t for t in js_templates)

        assert ".go" in LINT_COMMAND_TEMPLATES_BY_FILE
        go_templates = LINT_COMMAND_TEMPLATES_BY_FILE[".go"]
        assert any("go vet" in t for t in go_templates)

        assert "dockerfile" in LINT_COMMAND_TEMPLATES_BY_FILE
        dockerfile_templates = LINT_COMMAND_TEMPLATES_BY_FILE["dockerfile"]
        assert any("hadolint" in t for t in dockerfile_templates)

    @patch("haijunbot.haijunbot_utils.config.GLOBAL_CONFIG_DATA")
    def test_get_lint_tools_config_with_config(self, mock_config):
        """Test loading configuration from GLOBAL_CONFIG_DATA"""
        mock_config.get.side_effect = lambda key, default=None: {
            "lint_tools": {
                ".custom": ["custom-linter {file_path}"],
                ".PY": ["additional-python-linter {file_path}"],  # Test uppercase to lowercase conversion
                ".new": ["new-linter1 {file_path}", "new-linter2 {file_path}"],
            }
        }.get(key, default)

        result = get_lint_tools_config()

        # Verify results
        assert result[".custom"] == ["custom-linter {file_path}"]
        assert result[".py"] == ["additional-python-linter {file_path}"]  # Should be converted to lowercase
        assert result[".new"] == ["new-linter1 {file_path}", "new-linter2 {file_path}"]
        assert ".PY" not in result  # Uppercase version should not exist

    @patch("haijunbot.haijunbot_utils.config.GLOBAL_CONFIG_DATA", CaseInsensitiveDict())
    def test_get_lint_tools_config_no_config(self):
        """Test when not configured"""
        result = get_lint_tools_config()
        assert result == {}

    @patch("haijunbot.haijunbot_utils.config.GLOBAL_CONFIG_DATA")
    def test_get_lint_tools_config_empty_config(self, mock_config):
        """Test when configuration is empty"""
        mock_config.get.return_value = None
        result = get_lint_tools_config()
        assert result == {}

    def test_get_lint_commands_by_extension(self):
        """Test getting lint commands by file extension"""
        # Python files
        cmds = get_lint_commands_for_files(["test.py"], None)
        assert len(cmds) >= 2  # ruff and ty
        cmd_strs = [cmd for _, cmd in cmds]
        assert any("ruff check" in cmd for cmd in cmd_strs)
        assert any("ty check" in cmd for cmd in cmd_strs)

        # JavaScript files
        cmds = get_lint_commands_for_files(["app.js"], None)
        assert len(cmds) >= 1
        assert any("eslint" in cmd for _, cmd in cmds)

        # Go files
        cmds = get_lint_commands_for_files(["main.go"], None)
        assert len(cmds) >= 1
        assert any("go vet" in cmd for _, cmd in cmds)

        # Unknown extension
        cmds = get_lint_commands_for_files(["unknown.xyz"], None)
        assert len(cmds) == 0

    def test_get_lint_commands_with_path(self):
        """Test filenames with paths"""
        # Should only use the base filename for matching
        cmds = get_lint_commands_for_files(["/home/user/project/test.py"], None)
        assert len(cmds) >= 2
        assert any("test.py" in file_path for file_path, _ in cmds)

        cmds = get_lint_commands_for_files(["../src/main.go"], None)
        assert len(cmds) >= 1
        assert any("go vet" in cmd for _, cmd in cmds)

        cmds = get_lint_commands_for_files(["/var/lib/docker/dockerfile"], None)
        assert len(cmds) >= 1
        assert any("hadolint" in cmd for _, cmd in cmds)

    def test_get_lint_commands_special_cases(self):
        """Test special cases"""
        # Files without extension
        cmds = get_lint_commands_for_files(["README"], None)
        assert len(cmds) == 0

        # Filenames with multiple dots
        cmds = get_lint_commands_for_files(["test.spec.js"], None)
        assert len(cmds) >= 1
        assert any("eslint" in cmd for _, cmd in cmds)

        cmds = get_lint_commands_for_files(["app.test.py"], None)
        assert len(cmds) >= 2

        # Hidden files
        cmds = get_lint_commands_for_files([".bashrc"], None)
        assert len(cmds) >= 1
        assert any("shellcheck" in cmd for _, cmd in cmds)

        cmds = get_lint_commands_for_files([".gitignore"], None)
        assert len(cmds) >= 1
        assert any("git-lint" in cmd for _, cmd in cmds)

    @patch("haijunbot.haijunbot_code_agent.lint.get_lint_tools_config")
    def test_config_merge(self, mock_get_config):
        """Test configuration merge functionality (read from config.yaml)"""
        # Mock lint_tools configured in config.yaml
        mock_get_config.return_value = {
            ".py": ["additional-linter {file_path}"],  # Override existing configuration
            ".custom": ["custom-linter {file_path}"],  # New configuration
        }

        # .py files: .py is overridden, only additional-linter is generated
        cmds = get_lint_commands_for_files(["test.py"], None)
        cmd_strs = [cmd for _, cmd in cmds]
        assert any("additional-linter" in cmd for cmd in cmd_strs)
        assert not any("ruff check" in cmd for cmd in cmd_strs)  # Overridden

        # .custom files: new configuration takes effect
        cmds = get_lint_commands_for_files(["app.custom"], None)
        cmd_strs = [cmd for _, cmd in cmds]
        assert any("custom-linter" in cmd for cmd in cmd_strs)

        # .js files: not configured, built-in defaults are preserved
        cmds = get_lint_commands_for_files(["app.js"], None)
        cmd_strs = [cmd for _, cmd in cmds]
        assert any("eslint" in cmd for cmd in cmd_strs)
