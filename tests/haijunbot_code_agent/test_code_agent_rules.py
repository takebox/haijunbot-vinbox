# -*- coding: utf-8 -*-
"""code_agent_rules.py unit tests"""

from pathlib import Path
from unittest.mock import patch


from haijunbot.haijunbot_agent.rules_manager import RulesManager


class TestRulesManager:
    """Test RulesManager class"""

    @patch("haijunbot.haijunbot_agent.rules_manager.get_data_dir")
    def test_get_named_rule_not_found(self, mock_get_data_dir, tmp_path):
        """Test when rule does not exist"""
        mock_get_data_dir.return_value = str(tmp_path)
        manager = RulesManager("/tmp/test")
        result = manager.get_named_rule("nonexistent")

        assert result is None

    @patch("haijunbot.haijunbot_agent.rules_manager.get_data_dir")
    def test_get_named_rule_from_global_dir(self, mock_get_data_dir, tmp_path):
        """Test getting .md rule file from global rules directory"""
        data_dir = str(tmp_path)
        mock_get_data_dir.return_value = data_dir
        rules_dir = Path(data_dir) / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        rule_file = rules_dir / "test_rule.md"
        rule_file.write_text("Global test rule content", encoding="utf-8")

        manager = RulesManager("/tmp/test")
        result = manager.get_named_rule("global:test_rule")

        # Rule content includes path comment
        assert (
            f"<!-- Rule file path: {rules_dir / 'test_rule'} -->\nGlobal test rule content"
            == result
        )

    @patch("haijunbot.haijunbot_agent.rules_manager.get_data_dir")
    def test_get_named_rule_from_project_dir(self, mock_get_data_dir, tmp_path):
        """Test getting .md rule file from project .haijunbot/rules directory"""
        data_dir = str(tmp_path)
        mock_get_data_dir.return_value = data_dir
        project_root = tmp_path / "project"
        project_root.mkdir()
        project_rules_dir = project_root / ".haijunbot" / "rules"
        project_rules_dir.mkdir(parents=True, exist_ok=True)
        rule_file = project_rules_dir / "test_rule.md"
        rule_file.write_text("Project test rule content", encoding="utf-8")

        manager = RulesManager(str(project_root))
        result = manager.get_named_rule("project:test_rule")

        # Rule content includes path comment
        assert (
            f"<!-- Rule file path: {project_rules_dir / 'test_rule'} -->\nProject test rule content"
            == result
        )

    @patch("haijunbot.haijunbot_agent.rules_manager.get_data_dir")
    def test_get_named_rule_project_overrides_global(self, mock_get_data_dir, tmp_path):
        """Test that project rules override global rules (.md files)"""
        data_dir = str(tmp_path)
        mock_get_data_dir.return_value = data_dir
        global_rules_dir = Path(data_dir) / "rules"
        global_rules_dir.mkdir(parents=True, exist_ok=True)
        global_rule = global_rules_dir / "test_rule.md"
        global_rule.write_text("Global rule content", encoding="utf-8")

        project_root = tmp_path / "project"
        project_root.mkdir()
        project_rules_dir = project_root / ".haijunbot" / "rules"
        project_rules_dir.mkdir(parents=True, exist_ok=True)
        project_rule = project_rules_dir / "test_rule.md"
        project_rule.write_text("Project rule content", encoding="utf-8")

        manager = RulesManager(str(project_root))

        # Project rules should be loaded with priority
        result_project = manager.get_named_rule("project:test_rule")
        # Rule content includes path comment
        assert (
            f"<!-- Rule file path: {project_rules_dir / 'test_rule'} -->\nProject rule content"
            == result_project
        )

        # Global rules should also be accessible
        result_global = manager.get_named_rule("global:test_rule")
        # Rule content includes path comment
        assert (
            f"<!-- Rule file path: {global_rules_dir / 'test_rule'} -->\nGlobal rule content"
            == result_global
        )

    @patch("haijunbot.haijunbot_agent.rules_manager.get_data_dir")
    def test_load_all_rules_with_md_files(self, mock_get_data_dir, tmp_path):
        """Test loading .md rule files"""
        data_dir = str(tmp_path)
        mock_get_data_dir.return_value = data_dir
        rules_dir = Path(data_dir) / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        rule1 = rules_dir / "rule1.md"
        rule1.write_text("Rule 1 content", encoding="utf-8")
        rule2 = rules_dir / "rule2.md"
        rule2.write_text("Rule 2 content", encoding="utf-8")

        manager = RulesManager("/tmp/test")
        merged_rules, loaded_names = manager.load_all_rules("global:rule1,global:rule2")

        assert "Rule 1 content" in merged_rules
        assert "Rule 2 content" in merged_rules
        assert "global:rule1" in loaded_names
        assert "global:rule2" in loaded_names

    @patch("haijunbot.haijunbot_agent.rules_manager.get_data_dir")
    def test_load_all_rules_with_whitespace_in_names(self, mock_get_data_dir, tmp_path):
        """Test rule names containing whitespace"""
        data_dir = str(tmp_path)
        mock_get_data_dir.return_value = data_dir
        rules_dir = Path(data_dir) / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        rule_file = rules_dir / "rule1.md"
        rule_file.write_text("Named rule content", encoding="utf-8")

        manager = RulesManager("/tmp/test")
        merged_rules, loaded_names = manager.load_all_rules(
            " global:rule1 , global:rule2 "
        )

        assert "Named rule content" in merged_rules
        assert "global:rule1" in loaded_names
        # rule2 file does not exist, should not be loaded
        assert "global:rule2" not in loaded_names

    @patch("haijunbot.haijunbot_agent.rules_manager.get_data_dir")
    def test_rule_with_yaml_front_matter(self, mock_get_data_dir, tmp_path):
        """Test rule files with YAML Front Matter"""
        data_dir = str(tmp_path)
        mock_get_data_dir.return_value = data_dir
        rules_dir = Path(data_dir) / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        rule_file = rules_dir / "test_rule.md"
        rule_file.write_text(
            "---\ndescription: Test rule description\n---\nActual rule content here",
            encoding="utf-8",
        )

        manager = RulesManager("/tmp/test")
        result = manager.get_named_rule("global:test_rule")

        # YAML Front Matter should be removed
        assert "description: Test rule description" not in result
        assert "Actual rule content here" in result

    @patch("haijunbot.haijunbot_agent.rules_manager.get_data_dir")
    def test_load_and_unload_rule(self, mock_get_data_dir, tmp_path):
        """Test loading and unloading rules"""
        data_dir = str(tmp_path)
        mock_get_data_dir.return_value = data_dir
        rules_dir = Path(data_dir) / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        rule_file = rules_dir / "test_rule.md"
        rule_file.write_text("Test rule content", encoding="utf-8")

        manager = RulesManager("/tmp/test")

        # Load rule
        assert manager.load_rule("global:test_rule") is True
        assert manager.get_rule_status("global:test_rule") == "loaded"
        assert "Test rule content" in manager.get_loaded_rules_content()

        # Unload rule
        assert manager.unload_rule("global:test_rule") is True
        assert manager.get_rule_status("global:test_rule") == "not_loaded"
        assert manager.get_loaded_rules_content() == ""

    @patch("haijunbot.haijunbot_agent.rules_manager.get_data_dir")
    def test_get_rule_file_path(self, mock_get_data_dir, tmp_path):
        """Test getting rule file path"""
        data_dir = str(tmp_path)
        mock_get_data_dir.return_value = data_dir
        project_root = tmp_path / "project"
        project_root.mkdir()
        project_rules_dir = project_root / ".haijunbot" / "rules"
        project_rules_dir.mkdir(parents=True, exist_ok=True)
        rule_file = project_rules_dir / "test_rule.md"
        rule_file.write_text("Test content", encoding="utf-8")

        manager = RulesManager(str(project_root))
        path = manager.get_rule_file_path("project:test_rule.md")

        assert path.endswith(str(Path(".haijunbot") / "rules" / "test_rule.md"))
