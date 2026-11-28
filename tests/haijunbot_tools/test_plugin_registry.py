# -*- coding: utf-8 -*-
"""PluginRegistry reversible effect tests.

Covers plugin resource (tool/rule) registration, querying, revocation closed loop, and ToolRegistry /
RulesManager / uninstall_plugin integration. All tests use temporary data directory isolation,
do not pollute the real environment.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from haijunbot.haijunbot_tools.plugin_registry import PluginRegistry


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Clear PluginRegistry global singleton before each test case to avoid inter-test pollution."""
    PluginRegistry.instance().clear()
    yield
    PluginRegistry.instance().clear()


class TestPluginRegistry:
    """PluginRegistry basic registration/query/revocation."""

    def test_register_and_query(self):
        pr = PluginRegistry.instance()
        pr.register_tool("p1", "tool_a")
        pr.register_tools("p1", ["tool_b", "tool_c"])
        pr.register_rule("p1", "rule_x")
        pr.register_rule("p2", "rule_y")

        assert pr.get_plugin_tools("p1") == ["tool_a", "tool_b", "tool_c"]
        assert pr.get_plugin_rules("p1") == ["rule_x"]
        assert pr.get_plugin_rules("p2") == ["rule_y"]
        assert set(pr.registered_plugins()) == {"p1", "p2"}
        assert pr.has_plugin("p1")
        assert not pr.has_plugin("nonexistent")

    def test_unregister_plugin_returns_resources(self):
        pr = PluginRegistry.instance()
        pr.register_tool("p1", "tool_a")
        pr.register_rule("p1", "rule_x")

        result = pr.unregister_plugin("p1")
        assert set(result["tools"]) == {"tool_a"}
        assert set(result["rules"]) == {"rule_x"}
        assert not pr.has_plugin("p1")

    def test_clear_tools_only_clears_tools(self):
        pr = PluginRegistry.instance()
        pr.register_tool("p1", "tool_a")
        pr.register_rule("p1", "rule_x")

        pr.clear_tools("p1")
        assert pr.get_plugin_tools("p1") == []
        assert pr.get_plugin_rules("p1") == ["rule_x"]

    def test_clear_rules_only_clears_rules(self):
        pr = PluginRegistry.instance()
        pr.register_tool("p1", "tool_a")
        pr.register_rule("p1", "rule_x")

        pr.clear_rules("p1")
        assert pr.get_plugin_rules("p1") == []
        assert pr.get_plugin_tools("p1") == ["tool_a"]

    def test_revoke_plugin_without_revoker(self):
        """Without a revoker, revoke_plugin only cleans up registration, does not raise."""
        pr = PluginRegistry.instance()
        pr.register_tool("p1", "tool_a")
        pr.register_rule("p1", "rule_x")

        result = pr.revoke_plugin("p1")
        assert result == {"tools": 0, "rules": 0}
        assert not pr.has_plugin("p1")

    def test_revoke_plugin_with_revokers(self):
        """With revokers, revoke_plugin calls revokers and cleans up registration."""
        pr = PluginRegistry.instance()
        pr.register_tool("p1", "tool_a")
        pr.register_rule("p1", "rule_x")

        revoked = {"tools": [], "rules": []}

        def tool_revoker(name):
            revoked["tools"].append(name)
            return 1

        def rules_revoker(name):
            revoked["rules"].append(name)
            return 1

        pr.set_tool_revoker(tool_revoker)
        pr.set_rules_revoker(rules_revoker)

        result = pr.revoke_plugin("p1")
        assert result == {"tools": 1, "rules": 1}
        assert revoked["tools"] == ["p1"]
        assert revoked["rules"] == ["p1"]
        assert not pr.has_plugin("p1")

    def test_singleton(self):
        assert PluginRegistry.instance() is PluginRegistry.instance()


def _make_plugin_tool(tmp_path, plugin_name, tool_name):
    """Construct a plugin tool file in temporary data directory."""
    tool_dir = tmp_path / "plugins" / plugin_name / "tools"
    tool_dir.mkdir(parents=True, exist_ok=True)
    tool_file = tool_dir / f"{tool_name}.py"
    tool_file.write_text(
        f"# -*- coding: utf-8 -*-\n"
        f"class {tool_name}:\n"
        f'    name = "{tool_name}"\n'
        f'    description = "plugin tool"\n'
        f'    parameters = {{"type": "object", "properties": {{}}, "required": []}}\n'
        f"    def execute(self, **kwargs):\n"
        f'        return {{"success": True}}\n',
        encoding="utf-8",
    )
    return str(tool_file)


def _make_plugin_rule(tmp_path, plugin_name, rule_name):
    """Construct a plugin rule file in temporary data directory."""
    rule_dir = tmp_path / "plugins" / plugin_name / "rules"
    rule_dir.mkdir(parents=True, exist_ok=True)
    rule_file = rule_dir / f"{rule_name}.md"
    rule_file.write_text(
        f"---\nname: {rule_name}\ndescription: plugin rule\n---\n# {rule_name}\n",
        encoding="utf-8",
    )
    return str(rule_dir)


class TestToolRegistryIntegration:
    """ToolRegistry registration and revocation of plugin tools."""

    def test_register_and_unregister_plugin_tool(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(tmp_path))
        tool_file = _make_plugin_tool(tmp_path, "demo_plugin", "demo_tool")

        from haijunbot.haijunbot_tools.registry import ToolRegistry

        tr = ToolRegistry.__new__(ToolRegistry)
        tr.tools = {}
        tr._all_tools = {}
        tr._builtin_tool_names = set()
        tr._external_tool_sources = {}
        tr._required_tools = []

        assert tr.register_tool_by_file(tool_file)
        pr = PluginRegistry.instance()
        assert pr.get_plugin_tools("demo_plugin") == ["demo_tool"]
        assert "demo_tool" in tr.tools

        # Revoke
        count = tr.unregister_tools_by_plugin("demo_plugin")
        assert count == 1
        assert "demo_tool" not in tr.tools
        assert pr.get_plugin_tools("demo_plugin") == []

    def test_builtin_tool_not_affected(self, tmp_path, monkeypatch):
        """Revoking plugin tools does not affect built-in tools."""
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(tmp_path))
        tool_file = _make_plugin_tool(tmp_path, "demo_plugin", "demo_tool")

        from haijunbot.haijunbot_tools.registry import ToolRegistry

        tr = ToolRegistry.__new__(ToolRegistry)
        tr.tools = {}
        tr._all_tools = {}
        tr._builtin_tool_names = {"builtin_tool"}
        tr._external_tool_sources = {}
        tr._required_tools = []

        # Simulate built-in tool
        tr.tools["builtin_tool"] = object()
        tr._all_tools["builtin_tool"] = object()

        assert tr.register_tool_by_file(tool_file)
        tr.unregister_tools_by_plugin("demo_plugin")
        # Built-in tool still present
        assert "builtin_tool" in tr.tools


class TestRulesManagerIntegration:
    """RulesManager registration and revocation of plugin rules."""

    def test_register_and_unregister_plugin_rule(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(tmp_path))
        rule_dir = _make_plugin_rule(tmp_path, "demo_plugin", "demo_rule")

        from haijunbot.haijunbot_utils.config import set_global_config_data, set_config
        from haijunbot.haijunbot_agent.rules_manager import RulesManager

        # Construct complete rule directory structure (central + project + rules_load_dirs),
        # so config prefix index correctly maps to plugin rule directory.
        project_dir = tmp_path / "proj"
        (project_dir / ".haijunbot" / "rules").mkdir(parents=True, exist_ok=True)
        central_dir = tmp_path / "central"
        (central_dir / "rules").mkdir(parents=True, exist_ok=True)
        set_global_config_data({"rules_load_dirs": [rule_dir]})
        set_config("central_rules_repo", str(central_dir))

        rm = RulesManager(str(project_dir))
        assert rm.load_rule("config1:demo_rule.md")
        pr = PluginRegistry.instance()
        assert pr.get_plugin_rules("demo_plugin") == ["config1:demo_rule.md"]

        # Revoke
        count = rm.unregister_rules_by_plugin("demo_plugin")
        assert count == 1
        assert "config1:demo_rule.md" not in rm.loaded_rules
        assert pr.get_plugin_rules("demo_plugin") == []

    def test_non_plugin_rule_not_registered(self, tmp_path, monkeypatch):
        """Rules from non-plugin sources are not registered to PluginRegistry."""
        monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(tmp_path))
        project_dir = tmp_path / "proj"
        project_rules = project_dir / ".haijunbot" / "rules"
        project_rules.mkdir(parents=True, exist_ok=True)
        (project_rules / "proj_rule.md").write_text("# Project Rule\n", encoding="utf-8")

        from haijunbot.haijunbot_utils.config import set_global_config_data
        from haijunbot.haijunbot_agent.rules_manager import RulesManager

        set_global_config_data({})
        rm = RulesManager(str(project_dir))
        assert rm.load_rule("project:proj_rule.md")
        pr = PluginRegistry.instance()
        # Project rule path is not under plugins/, should not be registered
        assert pr.get_plugin_rules("demo_plugin") == []
        assert pr.registered_plugins() == []
