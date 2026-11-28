# -*- coding: utf-8 -*-
"""haijunbot_platform_manager.main module unit tests"""

import yaml
from unittest.mock import patch

from haijunbot.haijunbot_platform_manager.main import (
    validate_platform_model,
    load_role_config,
)


class TestValidatePlatformModel:
    """Test validate_platform_model function"""

    @patch("haijunbot.haijunbot_utils.output.PrettyOutput.auto_print")
    def test_valid_platform_and_model(self, mock_print):
        """Test valid platform and model"""
        result = validate_platform_model("openai", "gpt-4")
        assert result is True

    @patch("haijunbot.haijunbot_utils.output.PrettyOutput.auto_print")
    def test_missing_platform(self, mock_print):
        """Test missing platform"""
        result = validate_platform_model(None, "gpt-4")
        assert result is False
        mock_print.assert_called_once()

    @patch("haijunbot.haijunbot_utils.output.PrettyOutput.auto_print")
    def test_missing_model(self, mock_print):
        """Test missing model"""
        result = validate_platform_model("openai", None)
        assert result is False
        mock_print.assert_called_once()

    @patch("haijunbot.haijunbot_utils.output.PrettyOutput.auto_print")
    def test_both_missing(self, mock_print):
        """Test both platform and model missing"""
        result = validate_platform_model(None, None)
        assert result is False
        mock_print.assert_called_once()

    @patch("haijunbot.haijunbot_utils.output.PrettyOutput.auto_print")
    def test_empty_string_platform(self, mock_print):
        """Test empty string platform"""
        result = validate_platform_model("", "gpt-4")
        assert result is False

    @patch("haijunbot.haijunbot_utils.output.PrettyOutput.auto_print")
    def test_empty_string_model(self, mock_print):
        """Test empty string model"""
        result = validate_platform_model("openai", "")
        assert result is False


class TestLoadRoleConfig:
    """Test load_role_config function"""

    def test_valid_yaml_config(self, temp_dir):
        """Test valid YAML configuration"""
        config_file = temp_dir / "roles.yaml"
        config_data = {
            "roles": [
                {
                    "name": "test_role",
                    "description": "Test role",
                    "platform": "openai",
                    "model": "gpt-4",
                    "system_prompt": "You are a test assistant",
                }
            ]
        }
        config_file.write_text(yaml.dump(config_data), encoding="utf-8")

        result = load_role_config(str(config_file))
        assert result == config_data

    def test_nonexistent_file(self, temp_dir):
        """Test nonexistent file"""
        nonexistent = temp_dir / "nonexistent.yaml"
        with patch("haijunbot.haijunbot_utils.output.PrettyOutput.auto_print") as mock_print:
            result = load_role_config(str(nonexistent))
            assert result == {}
            mock_print.assert_called_once()

    def test_invalid_yaml(self, temp_dir):
        """Test invalid YAML"""
        config_file = temp_dir / "invalid.yaml"
        config_file.write_text("invalid: yaml: content: [", encoding="utf-8")

        with patch("haijunbot.haijunbot_utils.output.PrettyOutput.auto_print") as mock_print:
            result = load_role_config(str(config_file))
            assert result == {}
            mock_print.assert_called_once()

    def test_empty_file(self, temp_dir):
        """Test empty file"""
        config_file = temp_dir / "empty.yaml"
        config_file.write_text("", encoding="utf-8")

        result = load_role_config(str(config_file))
        assert result == {}

    def test_empty_config_dict(self, temp_dir):
        """Test empty configuration dictionary"""
        config_file = temp_dir / "empty_dict.yaml"
        config_file.write_text("{}", encoding="utf-8")

        result = load_role_config(str(config_file))
        assert result == {}

    def test_multiple_roles(self, temp_dir):
        """Test multiple roles"""
        config_file = temp_dir / "multiple_roles.yaml"
        config_data = {
            "roles": [
                {
                    "name": "role1",
                    "description": "Role 1",
                    "platform": "openai",
                    "model": "gpt-4",
                },
                {
                    "name": "role2",
                    "description": "Role 2",
                    "platform": "haijun",
                    "model": "haijun-3-sonnet-20240229",
                },
            ]
        }
        config_file.write_text(yaml.dump(config_data), encoding="utf-8")

        result = load_role_config(str(config_file))
        assert result == config_data
        assert len(result["roles"]) == 2
