# -*- coding: utf-8 -*-
"""build_validation_config.py unit tests"""

import yaml

from haijunbot.haijunbot_code_agent.build_validation_config import (
    BuildValidationConfig,
    STATE_FILE_NAME,
)
from haijunbot.haijunbot_utils import config as config_module
from haijunbot.haijunbot_utils.config import GLOBAL_CONFIG_DATA


def _mock_update(monkeypatch):
    """Mock update_build_validation_config: only sync GLOBAL_CONFIG_DATA, do not write to disk"""

    def fake_update(project_root, updates):
        bv = dict(GLOBAL_CONFIG_DATA.get("build_validation", {}))
        bv.update(updates)
        GLOBAL_CONFIG_DATA["build_validation"] = bv
        return True

    monkeypatch.setattr(config_module, "update_build_validation_config", fake_update)


class TestBuildValidationConfig:
    """Test BuildValidationConfig class"""

    def test_init(self, tmp_path):
        """Test initialization"""
        config = BuildValidationConfig(str(tmp_path))

        assert config.project_root == str(tmp_path)
        assert config.config_dir == str(tmp_path / ".haijunbot")
        assert config.state_path == str(tmp_path / ".haijunbot" / STATE_FILE_NAME)
        assert config._state is None

    def test_is_build_validation_disabled_default(self, tmp_path, monkeypatch):
        """Test that build validation is not disabled by default"""
        monkeypatch.setitem(GLOBAL_CONFIG_DATA, "build_validation", {})
        config = BuildValidationConfig(str(tmp_path))
        result = config.is_build_validation_disabled()

        assert result is False

    def test_is_build_validation_disabled_when_disabled(self, tmp_path, monkeypatch):
        """Test when build validation is disabled"""
        _mock_update(monkeypatch)
        config = BuildValidationConfig(str(tmp_path))
        config.disable_build_validation("Test reason")
        result = config.is_build_validation_disabled()

        assert result is True

    def test_disable_build_validation(self, tmp_path, monkeypatch):
        """Test disabling build validation"""
        _mock_update(monkeypatch)
        config = BuildValidationConfig(str(tmp_path))
        result = config.disable_build_validation("Test reason")

        assert result is True
        assert config.is_build_validation_disabled() is True
        assert config.get_disable_reason() == "Test reason"

    def test_disable_build_validation_without_reason(self, tmp_path, monkeypatch):
        """Test disabling build validation without providing a reason"""
        _mock_update(monkeypatch)
        config = BuildValidationConfig(str(tmp_path))
        result = config.disable_build_validation()

        assert result is True
        assert config.is_build_validation_disabled() is True
        assert config.get_disable_reason() is None

    def test_enable_build_validation(self, tmp_path, monkeypatch):
        """Test re-enabling build validation"""
        _mock_update(monkeypatch)
        config = BuildValidationConfig(str(tmp_path))
        config.disable_build_validation("Test reason")
        result = config.enable_build_validation()

        assert result is True
        assert config.is_build_validation_disabled() is False

    def test_get_disable_reason(self, tmp_path, monkeypatch):
        """Test getting disable reason"""
        _mock_update(monkeypatch)
        config = BuildValidationConfig(str(tmp_path))
        config.disable_build_validation("Test reason")
        result = config.get_disable_reason()

        assert result == "Test reason"

    def test_get_disable_reason_not_disabled(self, tmp_path, monkeypatch):
        """Test getting disable reason when not disabled"""
        monkeypatch.setitem(GLOBAL_CONFIG_DATA, "build_validation", {})
        config = BuildValidationConfig(str(tmp_path))
        result = config.get_disable_reason()

        assert result is None

    def test_get_custom_build_command_default(self, tmp_path, monkeypatch):
        """Test that no custom build command is configured by default"""
        monkeypatch.setitem(GLOBAL_CONFIG_DATA, "build_validation", {})
        config = BuildValidationConfig(str(tmp_path))
        result = config.get_custom_build_command()

        assert result is None

    def test_set_custom_build_command(self, tmp_path, monkeypatch):
        """Test setting custom build command"""
        _mock_update(monkeypatch)
        config = BuildValidationConfig(str(tmp_path))
        result = config.set_custom_build_command("make && make test")

        assert result is True
        assert config.get_custom_build_command() == "make && make test"

    def test_has_been_asked_default(self, tmp_path):
        """Test that user has not been asked by default"""
        config = BuildValidationConfig(str(tmp_path))
        result = config.has_been_asked()

        assert result is False

    def test_mark_as_asked(self, tmp_path):
        """Test marking as asked"""
        config = BuildValidationConfig(str(tmp_path))
        result = config.mark_as_asked()

        assert result is True
        assert config.has_been_asked() is True

    def test_get_selected_build_system_default(self, tmp_path):
        """Test that no build system is selected by default"""
        config = BuildValidationConfig(str(tmp_path))
        result = config.get_selected_build_system()

        assert result is None

    def test_set_selected_build_system(self, tmp_path):
        """Test setting selected build system"""
        config = BuildValidationConfig(str(tmp_path))
        result = config.set_selected_build_system("rust")

        assert result is True
        assert config.get_selected_build_system() == "rust"

    def test_set_selected_build_system_python(self, tmp_path):
        """Test setting Python build system"""
        config = BuildValidationConfig(str(tmp_path))
        config.set_selected_build_system("python")
        result = config.get_selected_build_system()

        assert result == "python"

    def test_state_persistence(self, tmp_path, monkeypatch):
        """Test runtime state persistence (across instances)"""
        _mock_update(monkeypatch)
        config1 = BuildValidationConfig(str(tmp_path))
        config1.disable_build_validation("Test reason")
        config1.set_selected_build_system("rust")
        config1.mark_as_asked()

        # Create a new instance, should be able to read the previous runtime state
        config2 = BuildValidationConfig(str(tmp_path))

        assert config2.get_selected_build_system() == "rust"
        assert config2.has_been_asked() is True

    def test_static_config_persistence(self, tmp_path, monkeypatch):
        """Test static configuration persistence (across instances, via GLOBAL_CONFIG_DATA)"""
        _mock_update(monkeypatch)
        config1 = BuildValidationConfig(str(tmp_path))
        config1.disable_build_validation("Test reason")

        # Create a new instance, static configuration is read from GLOBAL_CONFIG_DATA
        config2 = BuildValidationConfig(str(tmp_path))

        assert config2.is_build_validation_disabled() is True
        assert config2.get_disable_reason() == "Test reason"

    def test_load_state_file_not_exists(self, tmp_path):
        """Test loading default configuration when state file does not exist"""
        config = BuildValidationConfig(str(tmp_path))
        state_data = config._load_state()

        assert state_data == {}

    def test_load_state_file_exists(self, tmp_path):
        """Test loading configuration when state file exists"""
        config_dir = tmp_path / ".haijunbot"
        config_dir.mkdir()
        state_file = config_dir / STATE_FILE_NAME
        state_data = {
            "has_been_asked": True,
            "selected_build_system": "rust",
        }
        with open(state_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(state_data, f)

        config = BuildValidationConfig(str(tmp_path))
        loaded_data = config._load_state()

        assert loaded_data["has_been_asked"] is True
        assert loaded_data["selected_build_system"] == "rust"

    def test_load_state_invalid_yaml(self, tmp_path):
        """Test using default configuration when state file format is invalid"""
        config_dir = tmp_path / ".haijunbot"
        config_dir.mkdir()
        state_file = config_dir / STATE_FILE_NAME
        state_file.write_text("invalid: yaml: content: [", encoding="utf-8")

        config = BuildValidationConfig(str(tmp_path))
        loaded_data = config._load_state()

        # Should return empty configuration instead of raising an exception
        assert isinstance(loaded_data, dict)

    def test_save_state_creates_directory(self, tmp_path):
        """Test that saving state auto-creates directory"""
        config = BuildValidationConfig(str(tmp_path))
        config.mark_as_asked()

        assert (tmp_path / ".haijunbot").exists()
        assert (tmp_path / ".haijunbot" / STATE_FILE_NAME).exists()

    def test_state_caching(self, tmp_path):
        """Test state caching mechanism"""
        config = BuildValidationConfig(str(tmp_path))
        config.mark_as_asked()

        # First call should load state
        state1 = config._load_state()
        # Second call should use cache
        state2 = config._load_state()

        assert state1 is state2

    def test_multiple_config_changes(self, tmp_path, monkeypatch):
        """Test multiple configuration changes"""
        _mock_update(monkeypatch)
        config = BuildValidationConfig(str(tmp_path))

        # Disable and set reason
        config.disable_build_validation("Reason 1")
        assert config.get_disable_reason() == "Reason 1"

        # Change reason
        config.disable_build_validation("Reason 2")
        assert config.get_disable_reason() == "Reason 2"

        # Enable
        config.enable_build_validation()
        assert config.is_build_validation_disabled() is False

        # Disable again
        config.disable_build_validation("Reason 3")
        assert config.get_disable_reason() == "Reason 3"

    def test_write_config_yaml_preserves_schema_header(self, tmp_path, monkeypatch):
        """Test that writing to project-level config.yaml preserves the schema comment header"""
        config_dir = tmp_path / ".haijunbot"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(
            "# yaml-language-server: $schema=../src/haijunbot/haijunbot_data/config_schema.json\n"
            "# enable_tmux: true\n",
            encoding="utf-8",
        )

        config = BuildValidationConfig(str(tmp_path))
        result = config.disable_build_validation("Test reason")

        assert result is True
        # Schema comment header is preserved
        content = config_file.read_text(encoding="utf-8")
        assert content.startswith("# yaml-language-server: $schema=")
        # build_validation configuration is written
        parsed = yaml.safe_load(content)
        assert parsed["build_validation"]["disable_build_validation"] is True
        assert parsed["build_validation"]["disable_reason"] == "Test reason"
        # Runtime state is written to a separate file
        assert (config_dir / STATE_FILE_NAME).exists()
        # Clean up GLOBAL_CONFIG_DATA to avoid polluting other tests
        GLOBAL_CONFIG_DATA.pop("build_validation", None)
