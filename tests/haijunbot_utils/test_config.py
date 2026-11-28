# -*- coding: utf-8 -*-
"""haijunbot_utils.config module plugin functionality unit tests"""

import yaml
import pytest

from haijunbot.haijunbot_utils.config import (
    get_plugin_dirs,
    get_plugin_config,
    get_all_plugin_configs,
    get_replace_map,
    set_global_config_data,
    GLOBAL_CONFIG_DATA,
)
from haijunbot.haijunbot_utils.utils import _load_plugin_configs


@pytest.fixture
def disable_auto_discover(monkeypatch):
    """Disable auto-discovery to avoid loading real ~/.haijunbot/plugins directory during tests"""
    monkeypatch.setenv("HAIJUNBOT_DISABLE_AUTO_DISCOVER", "1")


class TestGetPluginDirs:
    """Tests for get_plugin_dirs function"""

    def test_default_empty_list(self):
        """Test default return of empty list"""
        # When GLOBAL_CONFIG_DATA has no plugin_dirs, should return empty list
        try:
            # Clear config
            if "plugin_dirs" in GLOBAL_CONFIG_DATA:
                del GLOBAL_CONFIG_DATA["plugin_dirs"]
            result = get_plugin_dirs()
            assert result == []
        finally:
            # Restore original config (if possible)
            pass

    def test_returns_configured_dirs(self):
        """Test returning configured plugin directories"""
        # When plugin_dirs is configured, should return the configured list
        original_value = GLOBAL_CONFIG_DATA.get("plugin_dirs", None)
        try:
            GLOBAL_CONFIG_DATA["plugin_dirs"] = ["/path/to/plugin1", "/path/to/plugin2"]
            result = get_plugin_dirs()
            assert result == ["/path/to/plugin1", "/path/to/plugin2"]
        finally:
            # Restore original config
            if original_value is None:
                GLOBAL_CONFIG_DATA.pop("plugin_dirs", None)
            else:
                GLOBAL_CONFIG_DATA["plugin_dirs"] = original_value


class TestLoadPluginConfigs:
    """Tests for _load_plugin_configs function"""

    @pytest.fixture(autouse=True)
    def setup(self, disable_auto_discover):
        """Disable auto-discovery for all tests"""
        pass

    def test_empty_plugin_dirs(self):
        """Test empty plugin directory list"""
        # When plugin_dirs is empty, config should not change
        base_config = {"model": "test-model", "plugin_dirs": []}
        result = _load_plugin_configs(base_config)
        assert result == base_config

    def test_single_plugin_loading(self, tmp_path):
        """Test single plugin loading"""
        # Create temporary plugin directory and config.yaml
        plugin_dir = tmp_path / "plugin1"
        plugin_dir.mkdir()

        plugin_config = {"model": "plugin-model", "custom_key": "custom_value"}
        config_file = plugin_dir / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(plugin_config, f)

        # Test loading (model/custom_key are plugin private fields, should be isolated to plugin_configs)
        base_config = {"plugin_dirs": [str(plugin_dir)]}
        result = _load_plugin_configs(base_config)

        # Private fields no longer pollute global config top level, isolated to plugin_configs.<plugin_name>
        assert "model" not in result
        assert "custom_key" not in result
        assert result["plugin_configs"]["plugin1"]["model"] == "plugin-model"
        assert result["plugin_configs"]["plugin1"]["custom_key"] == "custom_value"
        assert str(plugin_dir) in result["plugin_dirs"]  # plugin_dirs unchanged

    def test_multiple_plugins_loading(self, tmp_path):
        """Test multiple plugins loading"""
        # Create two temporary plugin directories
        plugin_dir1 = tmp_path / "plugin1"
        plugin_dir1.mkdir()
        plugin_config1 = {"model": "plugin1-model", "key1": "value1"}
        with open(plugin_dir1 / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(plugin_config1, f)

        plugin_dir2 = tmp_path / "plugin2"
        plugin_dir2.mkdir()
        plugin_config2 = {"model": "plugin2-model", "key2": "value2"}
        with open(plugin_dir2 / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(plugin_config2, f)

        # Test loading (model/key1/key2 are plugin private fields, should be isolated to their respective plugin_configs)
        base_config = {"plugin_dirs": [str(plugin_dir1), str(plugin_dir2)]}
        result = _load_plugin_configs(base_config)

        # Private fields isolated by plugin name, do not overwrite each other or pollute global top level
        assert "model" not in result
        assert "key1" not in result
        assert "key2" not in result
        assert result["plugin_configs"]["plugin1"]["model"] == "plugin1-model"
        assert result["plugin_configs"]["plugin2"]["model"] == "plugin2-model"
        assert result["plugin_configs"]["plugin1"]["key1"] == "value1"
        assert result["plugin_configs"]["plugin2"]["key2"] == "value2"

    def test_nonexistent_plugin_dir(self, tmp_path):
        """Test nonexistent plugin directory"""
        # When plugin directory does not exist, should warn but not error
        nonexistent_dir = tmp_path / "nonexistent"
        base_config = {"model": "base-model", "plugin_dirs": [str(nonexistent_dir)]}

        # Should not raise exception
        result = _load_plugin_configs(base_config)

        # Config should remain unchanged (except plugin_dirs)
        assert result["model"] == "base-model"

    def test_missing_config_yaml(self, tmp_path):
        """Test plugin directory missing config.yaml"""
        # Create plugin directory but not config.yaml
        plugin_dir = tmp_path / "plugin_no_config"
        plugin_dir.mkdir()

        base_config = {"model": "base-model", "plugin_dirs": [str(plugin_dir)]}
        result = _load_plugin_configs(base_config)

        # Config should remain unchanged
        assert result["model"] == "base-model"

    def test_invalid_yaml_format(self, tmp_path):
        """Test invalid YAML file"""
        # Create plugin directory and invalid config.yaml
        plugin_dir = tmp_path / "plugin_invalid"
        plugin_dir.mkdir()

        config_file = plugin_dir / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            f.write("invalid: yaml: content: [")  # Invalid YAML

        base_config = {"model": "base-model", "plugin_dirs": [str(plugin_dir)]}
        result = _load_plugin_configs(base_config)

        # Config should remain unchanged (load failed)
        assert result["model"] == "base-model"

    def test_relative_path_resolution(self, tmp_path):
        """Test relative path resolution"""
        # Create plugin directory
        plugin_dir = tmp_path / "plugin_relative"
        plugin_dir.mkdir()

        plugin_config = {"custom_key": "relative_value"}
        with open(plugin_dir / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(plugin_config, f)

        # Use relative path (relative to config file directory)
        # Config file directory is tmp_path, relative path is 'plugin_relative'
        base_config = {"plugin_dirs": ["plugin_relative"]}
        result = _load_plugin_configs(base_config, str(tmp_path))

        # Verify relative path resolved correctly (private fields isolated to plugin_configs)
        assert (
            result["plugin_configs"]["plugin_relative"]["custom_key"]
            == "relative_value"
        )


class TestConfigPriority:
    """Test configuration priority"""

    @pytest.fixture(autouse=True)
    def setup(self, disable_auto_discover):
        """Disable auto-discovery for all tests"""
        pass

    def test_project_config_priority_over_plugin(self, tmp_path):
        """Test project config is not overwritten by plugin private fields"""
        # Create plugin
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        plugin_config = {"model": "plugin-model", "plugin_only_key": "plugin_value"}
        with open(plugin_dir / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(plugin_config, f)

        # Project config (base_config)
        base_config = {"model": "project-model", "plugin_dirs": [str(plugin_dir)]}
        result = _load_plugin_configs(base_config)

        # Plugin private fields isolated to plugin_configs, do not overwrite project config
        assert result["model"] == "project-model"  # Project config preserved
        assert "plugin_only_key" not in result  # Plugin private fields do not enter global top level
        assert result["plugin_configs"]["plugin"]["model"] == "plugin-model"
        assert result["plugin_configs"]["plugin"]["plugin_only_key"] == "plugin_value"

    def test_multiple_plugins_priority(self, tmp_path):
        """Test private fields of multiple plugins are isolated by plugin name (no overwrite)"""
        # Create two plugins
        plugin_dir1 = tmp_path / "plugin1"
        plugin_dir1.mkdir()
        with open(plugin_dir1 / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"key": "value1"}, f)

        plugin_dir2 = tmp_path / "plugin2"
        plugin_dir2.mkdir()
        with open(plugin_dir2 / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"key": "value2"}, f)

        # Load in order
        base_config = {"plugin_dirs": [str(plugin_dir1), str(plugin_dir2)]}
        result = _load_plugin_configs(base_config)

        # Same-name private fields isolated by plugin name, later loaded do not overwrite earlier
        assert "key" not in result
        assert result["plugin_configs"]["plugin1"]["key"] == "value1"
        assert result["plugin_configs"]["plugin2"]["key"] == "value2"

    def test_deep_merge_nested_dict(self, tmp_path):
        """Test private field isolation for nested dictionaries (project config unaffected)"""
        # Create plugin
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        # Plugin config
        plugin_config = {
            "llm": {"model": "plugin-model", "plugin_only_key": "plugin_value"}
        }
        with open(plugin_dir / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(plugin_config, f)

        # Project config contains nested dictionary
        base_config = {
            "llm": {"model": "project-model", "temperature": 0.7, "max_tokens": 2000},
            "plugin_dirs": [str(plugin_dir)],
        }
        result = _load_plugin_configs(base_config)

        # Plugin private llm field isolated, project config llm unaffected
        assert result["llm"] == {
            "model": "project-model",
            "temperature": 0.7,
            "max_tokens": 2000,
        }
        assert result["plugin_configs"]["plugin"]["llm"]["model"] == "plugin-model"
        assert (
            result["plugin_configs"]["plugin"]["llm"]["plugin_only_key"]
            == "plugin_value"
        )

    def test_deep_merge_multiple_levels(self, tmp_path):
        """Test multi-level nested dictionary private field isolation"""
        # Create plugin
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        plugin_config = {
            "level1": {
                "level2": {"level3_key": "plugin-value", "plugin_only": "plugin_data"}
            }
        }
        with open(plugin_dir / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(plugin_config, f)

        # Project config has multi-level nesting
        base_config = {
            "level1": {
                "level1_key": "project-value",
                "level2": {
                    "level2_key": "project-value",
                    "level3_key": "project-value",
                },
            },
            "plugin_dirs": [str(plugin_dir)],
        }
        result = _load_plugin_configs(base_config)

        # Plugin private level1 isolated, project config level1 unaffected
        assert result["level1"]["level1_key"] == "project-value"
        assert result["level1"]["level2"]["level2_key"] == "project-value"
        assert result["level1"]["level2"]["level3_key"] == "project-value"
        assert "plugin_only" not in result["level1"]["level2"]
        assert (
            result["plugin_configs"]["plugin"]["level1"]["level2"]["level3_key"]
            == "plugin-value"
        )
        assert (
            result["plugin_configs"]["plugin"]["level1"]["level2"]["plugin_only"]
            == "plugin_data"
        )

    def test_deep_merge_list_append(self, tmp_path):
        """Test extension point list append merge + private list isolation"""
        # Create plugin
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        plugin_config = {
            "tool_load_dirs": ["/plugin/tools"],  # Extension point: merge into global
            "methodology_dirs": ["/plugin/methods"],  # Private: isolate
        }
        with open(plugin_dir / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(plugin_config, f)

        # Project config contains lists
        base_config = {
            "tool_load_dirs": ["/project/tools"],
            "methodology_dirs": ["/project/methods"],
            "plugin_dirs": [str(plugin_dir)],
        }
        result = _load_plugin_configs(base_config)

        # Extension point tool_load_dirs append-merged; private methodology_dirs isolated
        assert result["tool_load_dirs"] == ["/project/tools", "/plugin/tools"]
        assert result["methodology_dirs"] == ["/project/methods"]  # Project private preserved
        assert result["plugin_configs"]["plugin"]["methodology_dirs"] == [
            "/plugin/methods"
        ]

    def test_deep_mixed_types(self, tmp_path):
        """Test mixed types: extension point merge + private field isolation"""
        # Create plugin
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        plugin_config = {
            "llm": {
                "model": "plugin-model",
                "plugin_key": "plugin_val",
            },  # Private dict: isolate
            "tool_load_dirs": ["/plugin/tools"],  # Extension point: append merge
            "execute_tool_confirm": True,  # Private scalar: isolate
        }
        with open(plugin_dir / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(plugin_config, f)

        # Project config
        base_config = {
            "llm": {"model": "project-model", "temperature": 0.7},
            "tool_load_dirs": ["/project/tools"],
            "execute_tool_confirm": False,
            "plugin_dirs": [str(plugin_dir)],
        }
        result = _load_plugin_configs(base_config)

        # Project config llm/execute_tool_confirm unaffected by plugin
        assert result["llm"]["model"] == "project-model"
        assert result["llm"]["temperature"] == 0.7
        assert "plugin_key" not in result["llm"]
        # Extension point tool_load_dirs append-merged
        assert result["tool_load_dirs"] == ["/project/tools", "/plugin/tools"]
        assert result["execute_tool_confirm"] is False
        # Plugin private fields isolated
        assert result["plugin_configs"]["plugin"]["llm"]["model"] == "plugin-model"
        assert result["plugin_configs"]["plugin"]["llm"]["plugin_key"] == "plugin_val"
        assert result["plugin_configs"]["plugin"]["execute_tool_confirm"] is True

    def test_plugin_dirs_not_list(self):
        """Test plugin_dirs format error (non-list type)"""
        # plugin_dirs is string instead of list
        base_config = {"model": "test-model", "plugin_dirs": "/invalid/path"}
        result = _load_plugin_configs(base_config)

        # Should return original config and output warning
        assert result["model"] == "test-model"
        assert result["plugin_dirs"] == "/invalid/path"

    def test_plugin_dir_item_not_str(self, tmp_path):
        """Test plugin directory path format error (non-string type)"""
        # Create valid plugin
        valid_plugin_dir = tmp_path / "valid_plugin"
        valid_plugin_dir.mkdir()
        with open(valid_plugin_dir / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"valid_key": "valid_value"}, f)

        # plugin_dirs contains non-string element (number)
        base_config = {
            "model": "test-model",
            "plugin_dirs": [123, str(valid_plugin_dir)],  # First invalid, second valid
        }
        result = _load_plugin_configs(base_config)

        # Should skip invalid item, load valid item
        assert result["model"] == "test-model"
        assert result["plugin_configs"]["valid_plugin"]["valid_key"] == "valid_value"

    def test_plugin_dir_template_variable(self, tmp_path):
        """Test {{plugin_dir}} template variable in plugin config"""
        # Create temporary plugin directory
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()

        # Create config file containing {{plugin_dir}} variable
        config_content = """model: plugin-model
tool_load_dirs:
  - {{plugin_dir}}/tools
data_path: {{plugin_dir}}/data
"""
        config_file = plugin_dir / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(config_content)

        # Test loading
        base_config = {"plugin_dirs": [str(plugin_dir)]}
        result = _load_plugin_configs(base_config)

        # Verify template variables rendered correctly: extension point tool_load_dirs enters global, private fields isolated
        expected_path = str(plugin_dir)
        assert result["tool_load_dirs"] == [f"{expected_path}/tools"]
        assert "model" not in result
        assert "data_path" not in result
        assert result["plugin_configs"]["my_plugin"]["model"] == "plugin-model"
        assert (
            result["plugin_configs"]["my_plugin"]["data_path"]
            == f"{expected_path}/data"
        )

    def test_plugin_dir_template_in_nested_dict(self, tmp_path):
        """Test {{plugin_dir}} template variable in nested dictionary"""
        # Create temporary plugin directory
        plugin_dir = tmp_path / "nested_plugin"
        plugin_dir.mkdir()

        # Create config file containing nested dictionary
        config_content = """model: plugin-model
llm:
  model: nested-model
  cache_dir: {{plugin_dir}}/cache
  tools:
    path: {{plugin_dir}}/tools
"""
        config_file = plugin_dir / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(config_content)

        # Test loading
        base_config = {"plugin_dirs": [str(plugin_dir)]}
        result = _load_plugin_configs(base_config)

        # Private fields isolated to plugin_configs, template variables rendered correctly
        expected_path = str(plugin_dir)
        assert "llm" not in result
        assert "model" not in result
        assert (
            result["plugin_configs"]["nested_plugin"]["llm"]["cache_dir"]
            == f"{expected_path}/cache"
        )
        assert (
            result["plugin_configs"]["nested_plugin"]["llm"]["tools"]["path"]
            == f"{expected_path}/tools"
        )

    def test_plugin_dir_template_multiple_occurrences(self, tmp_path):
        """Test multiple uses of {{plugin_dir}} template variable in config"""
        # Create temporary plugin directory
        plugin_dir = tmp_path / "multi_plugin"
        plugin_dir.mkdir()

        # Create config file using {{plugin_dir}} multiple times
        config_content = """model: plugin-model
path1: {{plugin_dir}}/path1
path2: {{plugin_dir}}/path2
path3: {{plugin_dir}}/path3
"""
        config_file = plugin_dir / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(config_content)

        # Test loading
        base_config = {"plugin_dirs": [str(plugin_dir)]}
        result = _load_plugin_configs(base_config)

        # Private fields isolated to plugin_configs, all template variables rendered correctly
        expected_path = str(plugin_dir)
        assert "path1" not in result
        assert (
            result["plugin_configs"]["multi_plugin"]["path1"]
            == f"{expected_path}/path1"
        )
        assert (
            result["plugin_configs"]["multi_plugin"]["path2"]
            == f"{expected_path}/path2"
        )
        assert (
            result["plugin_configs"]["multi_plugin"]["path3"]
            == f"{expected_path}/path3"
        )


class TestInstallPlugin:
    """Tests for install_plugin function"""

    def test_install_from_directory(self, tmp_path, monkeypatch):
        """Test installing plugin from directory"""
        from haijunbot.haijunbot_agent.utils import install_plugin

        # Create temporary plugin directory
        plugin_source = tmp_path / "my_plugin"
        plugin_source.mkdir()

        # Create plugin config file
        config_content = """name: test-plugin
model: plugin-model
tool_load_dirs:
  - '{{plugin_dir}}/tools'
"""
        with open(plugin_source / "config.yaml", "w", encoding="utf-8") as f:
            f.write(config_content)

        # Mock data directory to temporary directory
        test_data_dir = tmp_path / ".haijunbot"
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(test_data_dir))

        # Install plugin
        result = install_plugin(str(plugin_source))

        # Verify installation successful
        assert result is True
        # Plugin name read from config.yaml name field
        assert (test_data_dir / "plugins" / "test-plugin").exists()
        assert (test_data_dir / "plugins" / "test-plugin" / "config.yaml").exists()

    def test_install_from_zip(self, tmp_path, monkeypatch):
        """Test installing plugin from zip file"""
        import zipfile
        from haijunbot.haijunbot_agent.utils import install_plugin

        # Create temporary plugin directory
        plugin_source = tmp_path / "zip_plugin"
        plugin_source.mkdir()

        config_content = "name: zip-plugin\nmodel: zip-model\n"
        with open(plugin_source / "config.yaml", "w", encoding="utf-8") as f:
            f.write(config_content)

        # Create zip file
        zip_file = tmp_path / "plugin.zip"
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.write(plugin_source / "config.yaml", "config.yaml")

        # Mock data directory
        test_data_dir = tmp_path / ".haijunbot"
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(test_data_dir))

        # Install plugin
        result = install_plugin(str(zip_file))

        # Verify installation successful
        assert result is True
        assert (test_data_dir / "plugins" / "zip-plugin").exists()

    def test_install_missing_config_yaml(self, tmp_path, monkeypatch):
        """Test installing plugin missing config.yaml"""
        from haijunbot.haijunbot_agent.utils import install_plugin

        # Create temporary plugin directory (without config.yaml)
        plugin_source = tmp_path / "invalid_plugin"
        plugin_source.mkdir()
        with open(plugin_source / "readme.txt", "w") as f:
            f.write("This is not a valid plugin")

        # Mock data directory
        test_data_dir = tmp_path / ".haijunbot"
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(test_data_dir))

        # Plugin installation should fail
        result = install_plugin(str(plugin_source))
        assert result is False

    def test_install_auto_install_plugin_dep_with_url(self, tmp_path, monkeypatch):
        """Test auto-install when dependency plugin is missing but has url"""
        from haijunbot.haijunbot_agent import utils

        # Main plugin depends on depA (with url + tag)
        plugin_source = tmp_path / "main_plugin"
        plugin_source.mkdir()
        config_content = """name: main-plugin
model: plugin-model
dependencies:
  plugins:
    depA:
      url: https://github.com/owner/repoA
      tag: v1.0
"""
        with open(plugin_source / "config.yaml", "w", encoding="utf-8") as f:
            f.write(config_content)

        test_data_dir = tmp_path / ".haijunbot"
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(test_data_dir))

        calls = {}
        orig_install = utils.install_plugin

        def fake_install(src, force=False, source_url=None, _installing_deps=None):
            calls["src"] = src
            calls["source_url"] = source_url
            # Simulate successful dependency install: create depA directory
            dep_dir = test_data_dir / "plugins" / "depA"
            dep_dir.mkdir(parents=True, exist_ok=True)
            with open(dep_dir / "config.yaml", "w", encoding="utf-8") as f:
                f.write("name: depA\nversion: 1.0\n")
            return True

        monkeypatch.setattr(utils, "install_plugin", fake_install)

        result = orig_install(str(plugin_source))

        # Auto-install triggered, and URL resolved to archive address by tag
        assert result is True
        assert calls["src"] == (
            "https://github.com/owner/repoA/archive/refs/tags/v1.0.tar.gz"
        )
        assert calls["source_url"] == calls["src"]
        assert (test_data_dir / "plugins" / "main-plugin").exists()

    def test_install_reject_plugin_dep_without_url(self, tmp_path, monkeypatch):
        """Test rejecting install when dependency plugin is missing and has no url"""
        from haijunbot.haijunbot_agent import utils

        plugin_source = tmp_path / "p2"
        plugin_source.mkdir()
        config_content = """name: p2
model: plugin-model
dependencies:
  plugins:
    depB: ">=1.0"
"""
        with open(plugin_source / "config.yaml", "w", encoding="utf-8") as f:
            f.write(config_content)

        test_data_dir = tmp_path / ".haijunbot"
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(test_data_dir))

        result = utils.install_plugin(str(plugin_source))
        assert result is False
        assert not (test_data_dir / "plugins" / "p2").exists()

    def test_install_cycle_dependency_guard(self, tmp_path, monkeypatch):
        """Test termination on circular dependency to avoid infinite loop"""
        from haijunbot.haijunbot_agent import utils

        plugin_source = tmp_path / "p3"
        plugin_source.mkdir()
        config_content = """name: p3
model: plugin-model
dependencies:
  plugins:
    depC:
      url: https://github.com/c/d
"""
        with open(plugin_source / "config.yaml", "w", encoding="utf-8") as f:
            f.write(config_content)

        test_data_dir = tmp_path / ".haijunbot"
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(test_data_dir))

        orig_install = utils.install_plugin

        def fake_install(src, force=False, source_url=None, _installing_deps=None):
            # Simulate depC depends back on p3, triggering cycle
            if _installing_deps is None:
                _installing_deps = set()
            _installing_deps.add("depC")
            return orig_install(str(plugin_source), _installing_deps=_installing_deps)

        monkeypatch.setattr(utils, "install_plugin", fake_install)

        result = orig_install(str(plugin_source))
        assert result is False

    def test_resolve_plugin_dep_url(self):
        """Test URL resolution for _resolve_plugin_dep_url"""
        from haijunbot.haijunbot_agent.utils import _resolve_plugin_dep_url

        # GitHub repo + tag
        assert (
            _resolve_plugin_dep_url("https://github.com/owner/repo", "v1.0", None)
            == "https://github.com/owner/repo/archive/refs/tags/v1.0.tar.gz"
        )
        # GitHub repo + branch
        assert (
            _resolve_plugin_dep_url("https://github.com/owner/repo", None, "main")
            == "https://github.com/owner/repo/archive/refs/heads/main.tar.gz"
        )
        # GitHub repo + .git suffix + tag
        assert (
            _resolve_plugin_dep_url("https://github.com/owner/repo.git", "v2", None)
            == "https://github.com/owner/repo/archive/refs/tags/v2.tar.gz"
        )
        # No tag/branch returns as-is
        assert (
            _resolve_plugin_dep_url("https://github.com/owner/repo", None, None)
            == "https://github.com/owner/repo"
        )
        # Non-GitHub address returns as-is
        assert (
            _resolve_plugin_dep_url("https://example.com/x.tar.gz", "v1", None)
            == "https://example.com/x.tar.gz"
        )
        # Empty url returns as-is
        assert _resolve_plugin_dep_url("", "v1", None) == ""

    def test_install_from_directory_creates_symlink(self, tmp_path, monkeypatch):
        """Local directory installation creates symlink instead of copying (Issue #95)"""
        import os
        from haijunbot.haijunbot_agent.utils import install_plugin

        plugin_source = tmp_path / "linked_plugin"
        plugin_source.mkdir()
        with open(plugin_source / "config.yaml", "w", encoding="utf-8") as f:
            f.write("name: linked-plugin\nversion: 1.0\n")

        test_data_dir = tmp_path / ".haijunbot"
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(test_data_dir))

        result = install_plugin(str(plugin_source))
        assert result is True

        target_dir = test_data_dir / "plugins" / "linked-plugin"
        assert target_dir.is_symlink()
        assert os.path.realpath(target_dir) == str(plugin_source)
        # Symlink install does not write .source (avoid following link polluting source directory)
        assert not (target_dir / ".source").exists()

    def test_install_from_directory_updates_take_effect(self, tmp_path, monkeypatch):
        """Local source updates take effect immediately via symlink (Issue #95)"""
        from haijunbot.haijunbot_agent.utils import install_plugin

        plugin_source = tmp_path / "live_plugin"
        plugin_source.mkdir()
        config_path = plugin_source / "config.yaml"
        config_path.write_text("name: live-plugin\nversion: 1.0\n", encoding="utf-8")

        test_data_dir = tmp_path / ".haijunbot"
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(test_data_dir))

        assert install_plugin(str(plugin_source)) is True
        target_dir = test_data_dir / "plugins" / "live-plugin"

        # Modify local source, symlink should read new content (no reinstall needed)
        config_path.write_text("name: live-plugin\nversion: 2.0\n", encoding="utf-8")
        content = (target_dir / "config.yaml").read_text(encoding="utf-8")
        assert "version: 2.0" in content

    def test_install_overwrite_symlink_preserves_source(self, tmp_path, monkeypatch):
        """Overwrite symlink installation does not error and does not delete local source (Issue #95)"""
        from haijunbot.haijunbot_agent.utils import install_plugin

        plugin_source = tmp_path / "ow_plugin"
        plugin_source.mkdir()
        with open(plugin_source / "config.yaml", "w", encoding="utf-8") as f:
            f.write("name: ow-plugin\nversion: 1.0\n")

        test_data_dir = tmp_path / ".haijunbot"
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(test_data_dir))

        assert install_plugin(str(plugin_source)) is True
        target_dir = test_data_dir / "plugins" / "ow-plugin"
        assert target_dir.is_symlink()

        # Force overwrite install: no error, symlink replaced, local source still present
        assert install_plugin(str(plugin_source), force=True) is True
        assert target_dir.is_symlink()
        assert plugin_source.exists()
        assert (plugin_source / "config.yaml").exists()

    def test_uninstall_symlink_preserves_source(self, tmp_path, monkeypatch):
        """Uninstalling symlink-installed plugin only deletes link not local source (Issue #95)"""
        from haijunbot.haijunbot_agent.utils import install_plugin, uninstall_plugin

        plugin_source = tmp_path / "unlink_plugin"
        plugin_source.mkdir()
        with open(plugin_source / "config.yaml", "w", encoding="utf-8") as f:
            f.write("name: unlink-plugin\nversion: 1.0\n")

        test_data_dir = tmp_path / ".haijunbot"
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(test_data_dir))

        assert install_plugin(str(plugin_source)) is True
        target_dir = test_data_dir / "plugins" / "unlink-plugin"
        assert target_dir.is_symlink()

        assert uninstall_plugin("unlink-plugin") is True
        # Symlink deleted, local source directory still intact
        assert not target_dir.exists()
        assert plugin_source.exists()
        assert (plugin_source / "config.yaml").exists()

    def test_install_from_zip_is_copy(self, tmp_path, monkeypatch):
        """Zip archive installation is still real directory copy (not symlink)"""
        import zipfile
        from haijunbot.haijunbot_agent.utils import install_plugin

        plugin_source = tmp_path / "zip_plugin_copy"
        plugin_source.mkdir()
        with open(plugin_source / "config.yaml", "w", encoding="utf-8") as f:
            f.write("name: zip-plugin-copy\nversion: 1.0\n")

        zip_file = tmp_path / "plugin_copy.zip"
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.write(plugin_source / "config.yaml", "config.yaml")

        test_data_dir = tmp_path / ".haijunbot"
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(test_data_dir))

        assert install_plugin(str(zip_file)) is True
        target_dir = test_data_dir / "plugins" / "zip-plugin-copy"
        assert target_dir.exists()
        assert not target_dir.is_symlink()
        assert (target_dir / "config.yaml").exists()


class TestAutoDiscoverPlugins:
    """Tests for auto-discovering plugins functionality"""

    def test_auto_discover_plugins(self, tmp_path, monkeypatch):
        """Test auto-discovering plugins under plugins directory"""
        from haijunbot.haijunbot_utils.utils import _load_plugin_configs

        # Mock data directory
        test_data_dir = tmp_path / ".haijunbot"
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(test_data_dir))

        # Create plugin directory
        plugins_dir = test_data_dir / "plugins"
        plugins_dir.mkdir(parents=True)

        plugin1 = plugins_dir / "plugin1"
        plugin1.mkdir()
        with open(plugin1 / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"model": "plugin1-model", "key1": "value1"}, f)

        plugin2 = plugins_dir / "plugin2"
        plugin2.mkdir()
        with open(plugin2 / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"model": "plugin2-model", "key2": "value2"}, f)

        # Load config (without specifying plugin_dirs)
        base_config = {}
        result = _load_plugin_configs(base_config)

        # Auto-discovered plugins loaded, private fields isolated to their respective plugin_configs
        assert "model" not in result
        assert "key1" not in result
        assert "key2" not in result
        assert result["plugin_configs"]["plugin1"]["model"] == "plugin1-model"
        assert result["plugin_configs"]["plugin2"]["model"] == "plugin2-model"
        assert result["plugin_configs"]["plugin1"]["key1"] == "value1"
        assert result["plugin_configs"]["plugin2"]["key2"] == "value2"

    def test_auto_discover_with_config_dirs(self, tmp_path, monkeypatch):
        """Test merging config-specified plugin directories and auto-discovered plugin directories"""
        from haijunbot.haijunbot_utils.utils import _load_plugin_configs

        # Mock data directory
        test_data_dir = tmp_path / ".haijunbot"
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(test_data_dir))

        # Create config-specified plugin
        config_plugin = tmp_path / "config_plugin"
        config_plugin.mkdir()
        with open(config_plugin / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"model": "config-model", "config_key": "config_value"}, f)

        # Create auto-discovered plugin
        plugins_dir = test_data_dir / "plugins"
        plugins_dir.mkdir(parents=True)
        auto_plugin = plugins_dir / "auto_plugin"
        auto_plugin.mkdir()
        with open(auto_plugin / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"auto_key": "auto_value"}, f)

        # Load config (specifying plugin_dirs)
        base_config = {"plugin_dirs": [str(config_plugin)]}
        result = _load_plugin_configs(base_config)

        # Both plugins loaded, private fields isolated to their respective plugin_configs
        assert "model" not in result
        assert "config_key" not in result
        assert "auto_key" not in result
        assert result["plugin_configs"]["config_plugin"]["model"] == "config-model"
        assert result["plugin_configs"]["config_plugin"]["config_key"] == "config_value"
        assert result["plugin_configs"]["auto_plugin"]["auto_key"] == "auto_value"


class TestPluginConfigIsolation:
    """Tests for plugin private config isolation to separate config entries"""

    @pytest.fixture(autouse=True)
    def setup(self, disable_auto_discover):
        """Disable auto-discovery for all tests"""
        pass

    def test_private_configs_isolated_by_plugin_name(self, tmp_path):
        """Test two plugins declaring same-name private fields do not overwrite each other"""
        # Plugin A and B declare same-name private dict field private_cfg
        pa = tmp_path / "pluginA"
        pa.mkdir()
        with open(pa / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"private_cfg": {"mode": "fast", "retries": 3}}, f)

        pb = tmp_path / "pluginB"
        pb.mkdir()
        with open(pb / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"private_cfg": {"mode": "slow", "level": 5}}, f)

        base_config = {"plugin_dirs": [str(pa), str(pb)]}
        result = _load_plugin_configs(base_config)

        # Same-name private fields isolated by plugin name, later loaded do not overwrite earlier
        assert "private_cfg" not in result  # Does not pollute global top level
        assert result["plugin_configs"]["pluginA"]["private_cfg"] == {
            "mode": "fast",
            "retries": 3,
        }
        assert result["plugin_configs"]["pluginB"]["private_cfg"] == {
            "mode": "slow",
            "level": 5,
        }

    def test_extension_fields_still_merged(self, tmp_path):
        """Test extension point fields still merged into global config for getter consumption"""
        pa = tmp_path / "pluginA"
        pa.mkdir()
        with open(pa / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"tool_load_dirs": ["/A/tools"], "private_key": "pv"}, f)

        pb = tmp_path / "pluginB"
        pb.mkdir()
        with open(pb / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"rules_load_dirs": ["/B/rules"]}, f)

        base_config = {"plugin_dirs": [str(pa), str(pb)]}
        result = _load_plugin_configs(base_config)

        # Extension point fields merged into global
        assert result["tool_load_dirs"] == ["/A/tools"]
        assert result["rules_load_dirs"] == ["/B/rules"]
        # Private fields isolated
        assert result["plugin_configs"]["pluginA"]["private_key"] == "pv"

    def test_get_plugin_config(self, tmp_path):
        """Test get_plugin_config / get_all_plugin_configs getter"""
        pa = tmp_path / "pluginA"
        pa.mkdir()
        with open(pa / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"name": "pluginA", "custom": {"k": "v"}}, f)

        base_config = {"plugin_dirs": [str(pa)]}
        result = _load_plugin_configs(base_config)
        set_global_config_data(result)

        # get_plugin_config returns specified plugin's private config
        assert get_plugin_config("pluginA")["custom"] == {"k": "v"}
        assert get_plugin_config("pluginA")["name"] == "pluginA"
        # Nonexistent plugin returns empty dict
        assert get_plugin_config("nonexistent") == {}
        # get_all_plugin_configs returns all
        assert "pluginA" in get_all_plugin_configs()

    def test_private_configs_not_pollute_global(self, tmp_path):
        """Test plugin private fields do not pollute global config top level"""
        pa = tmp_path / "pluginA"
        pa.mkdir()
        with open(pa / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(
                {
                    "name": "pluginA",
                    "description": "desc",
                    "version": "1.0",
                    "builtin": False,
                    "license": "MIT",
                    "custom_field": "custom",
                },
                f,
            )

        base_config = {"plugin_dirs": [str(pa)]}
        result = _load_plugin_configs(base_config)

        # Metadata fields do not pollute global top level
        for key in (
            "name",
            "description",
            "version",
            "builtin",
            "license",
            "custom_field",
        ):
            assert key not in result, f"{key} should not appear in global config top level"
        # All isolated to plugin_configs
        assert result["plugin_configs"]["pluginA"]["name"] == "pluginA"
        assert result["plugin_configs"]["pluginA"]["custom_field"] == "custom"

    def test_replace_map_merged_as_extension_field(self, tmp_path):
        """Test replace_map merged into global as extension point field, and get_replace_map can consume it"""
        pa = tmp_path / "pluginA"
        pa.mkdir()
        with open(pa / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(
                {
                    "replace_map": {
                        "MyTag": {
                            "append": False,
                            "template": "hello {{current_dir}}",
                            "description": "Custom tag",
                        }
                    },
                    "private_key": "pv",
                },
                f,
            )

        base_config = {"plugin_dirs": [str(pa)]}
        result = _load_plugin_configs(base_config)

        # replace_map merged into global top level as extension point field
        assert "replace_map" in result
        assert result["replace_map"]["MyTag"]["description"] == "Custom tag"
        # Private fields still isolated
        assert result["plugin_configs"]["pluginA"]["private_key"] == "pv"

        # get_replace_map can consume plugin-declared replace_map (takes effect after cache clear)
        set_global_config_data(result)
        get_replace_map.cache_clear()
        merged = get_replace_map()
        assert merged["MyTag"]["description"] == "Custom tag"
