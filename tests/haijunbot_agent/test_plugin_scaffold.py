# -*- coding: utf-8 -*-
"""scaffold_plugin scaffold generation tests.

Verify generated plugin skeleton conforms to loading conventions:
- Directory structure complete (rules/tools/agents/orchestration/frontend/plugin)
- config.yaml contains name/version/builtin, parseable by yaml
- Tool class name matches filename stem
- plugin/api.py is syntactically valid, contains PUBLIC_FUNCTIONS whitelist, function names are valid Python identifiers
"""
import importlib.util
import os
import py_compile
import sys

import pytest
import yaml

from haijunbot.haijunbot_agent.utils import scaffold_plugin


@pytest.fixture
def plugin_dir(tmp_path):
    """Generate a test plugin scaffold, return its directory path."""
    result = scaffold_plugin("my-demo-plugin", output_dir=str(tmp_path))
    assert result is not None, "Scaffold generation failed"
    return result


def test_plugin_structure_dirs(plugin_dir):
    """Should generate all extension point directories (including plugin/ private function directory)."""
    for sub in ("rules", "tools", "agents", "orchestration", "frontend", "plugin"):
        assert os.path.isdir(os.path.join(plugin_dir, sub)), f"Missing directory {sub}"


def test_config_yaml_valid(plugin_dir):
    """config.yaml should contain name/version/builtin and be parseable by yaml."""
    config_path = os.path.join(plugin_dir, "config.yaml")
    assert os.path.isfile(config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    assert isinstance(config, dict)
    assert config["name"] == "my-demo-plugin"
    assert config["version"] == "0.1.0"
    assert config.get("builtin") is True
    # Tool/rules extension points enabled
    assert config.get("tool_load_dirs")
    assert config.get("rules_load_dirs")


def test_tool_module_matches_stem(plugin_dir):
    """Tool file name stem should equal tool class name (registry loading convention)."""
    tool_file = os.path.join(plugin_dir, "tools", "my-demo-plugin_tool.py")
    assert os.path.isfile(tool_file)
    # Class name should equal filename stem
    stem = "my-demo-plugin_tool"
    with open(tool_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert f'name = "{stem}"' in content


def test_plugin_api_py_valid(plugin_dir):
    """plugin/api.py should be syntactically valid, contain PUBLIC_FUNCTIONS whitelist, function names are valid identifiers."""
    api_file = os.path.join(plugin_dir, "plugin", "api.py")
    assert os.path.isfile(api_file)
    # Syntax validation
    py_compile.compile(api_file, doraise=True)

    # Dynamically load to verify PUBLIC_FUNCTIONS and callable functions
    spec = importlib.util.spec_from_file_location("scaffold_api_test", api_file)
    assert spec is not None and spec.loader is not None, "Cannot load api.py"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["scaffold_api_test"] = mod
    spec.loader.exec_module(mod)
    assert isinstance(mod.PUBLIC_FUNCTIONS, list) and mod.PUBLIC_FUNCTIONS
    fn_name = mod.PUBLIC_FUNCTIONS[0]
    # Function name must be a valid Python identifier (hyphens replaced with underscores)
    assert fn_name.isidentifier(), f"Invalid function name: {fn_name}"
    assert callable(getattr(mod, fn_name))


def test_frontend_files_generated(plugin_dir):
    """frontend/ should generate admin_tab.js and sidebar_view.js templates."""
    assert os.path.isfile(os.path.join(plugin_dir, "frontend", "admin_tab.js"))
    assert os.path.isfile(os.path.join(plugin_dir, "frontend", "sidebar_view.js"))


def test_readme_mentions_plugin_private(plugin_dir):
    """README should contain plugin/ private function description."""
    readme_path = os.path.join(plugin_dir, "README.md")
    assert os.path.isfile(readme_path)
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "plugin private functions" in content.lower()
    assert "PUBLIC_FUNCTIONS" in content
