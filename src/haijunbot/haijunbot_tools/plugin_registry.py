# -*- coding: utf-8 -*-
"""Plugin resource registration tracker (source of truth for reversible effects).

Inspired by Cordis's reversible effects concept: a plugin explicitly records which resources
(tools, rules, etc.) it registers at load time, and precisely revokes them according to the record at unload time, making register/unregister fully symmetric.

PluginRegistry is an in-process global singleton, written by ToolRegistry / RulesManager when loading plugin
resources, and read and revoked by uninstall_plugin during uninstallation. It is the sole
source of truth for plugin reversible effects, relying on explicit registration rather than path-based inference.
"""

from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Set


class PluginRegistry:
    """Plugin resource registration tracker.

    Maintains a mapping of "plugin name -> the set of tool names/rule names registered by that plugin", providing registration, query, and
    bulk-revocation interfaces. When uninstalling a plugin, calling revoke_plugin precisely revokes all
    resources registered by that plugin.

    It also holds global revokers (registered by ToolRegistry / RulesManager instances);
    revoke_plugin uses these to actually perform the uninstallation.
    """

    _instance: Optional["PluginRegistry"] = None

    def __init__(self) -> None:
        self._plugin_tools: Dict[str, Set[str]] = {}
        self._plugin_rules: Dict[str, Set[str]] = {}
        # plugin name -> whether it applies to code_agent (declared by the plugin config's code_agent_tools field)
        self._plugin_code_agent_tools: Dict[str, bool] = {}
        self._tool_revoker: Optional[Callable[[str], int]] = None
        self._rules_revoker: Optional[Callable[[str], int]] = None

    @classmethod
    def instance(cls) -> "PluginRegistry":
        """Get the global singleton."""
        if cls._instance is None:
            cls._instance = PluginRegistry()
        return cls._instance

    # ------------------------------------------------------------------
    # Revoker registration
    # ------------------------------------------------------------------
    def set_tool_revoker(self, revoker: Optional[Callable[[str], int]]) -> None:
        """Register/clear the global tool revoker (registered by the ToolRegistry instance).

        Revoker signature: revoker(plugin_name) -> number of revoked tools.
        """
        self._tool_revoker = revoker

    def set_rules_revoker(self, revoker: Optional[Callable[[str], int]]) -> None:
        """Register/clear the global rule revoker (registered by the RulesManager instance).

        Revoker signature: revoker(plugin_name) -> number of revoked rules.
        """
        self._rules_revoker = revoker

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register_tool(self, plugin_name: str, tool_name: str) -> None:
        """Register a single tool registered by the plugin."""
        self._plugin_tools.setdefault(plugin_name, set()).add(tool_name)

    def register_tools(self, plugin_name: str, tool_names: List[str]) -> None:
        """Register a batch of tools registered by the plugin."""
        if not tool_names:
            return
        self._plugin_tools.setdefault(plugin_name, set()).update(tool_names)

    def register_rule(self, plugin_name: str, rule_name: str) -> None:
        """Register a single rule registered by the plugin."""
        self._plugin_rules.setdefault(plugin_name, set()).add(rule_name)

    def register_rules(self, plugin_name: str, rule_names: List[str]) -> None:
        """Register a batch of rules registered by the plugin."""
        if not rule_names:
            return
        self._plugin_rules.setdefault(plugin_name, set()).update(rule_names)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def get_plugin_tools(self, plugin_name: str) -> List[str]:
        """Return the list of tool names registered by the plugin."""
        return sorted(self._plugin_tools.get(plugin_name, set()))

    def get_plugin_rules(self, plugin_name: str) -> List[str]:
        """Return the list of rule names registered by the plugin."""
        return sorted(self._plugin_rules.get(plugin_name, set()))

    def registered_plugins(self) -> List[str]:
        """Return the list of plugin names that have registered resources."""
        return sorted(set(self._plugin_tools.keys()) | set(self._plugin_rules.keys()))

    # ------------------------------------------------------------------
    # code_agent applicability registration
    # ------------------------------------------------------------------
    def set_plugin_code_agent_tools(self, plugin_name: str, enabled: bool) -> None:
        """Register/clear whether the plugin applies to code_agent.

        Declared by the plugin config's code_agent_tools field (registered when loading the plugin config).
        When enabled is False, the registration is removed, indicating that the plugin does not apply to code_agent.
        """
        if enabled:
            self._plugin_code_agent_tools[plugin_name] = True
        else:
            self._plugin_code_agent_tools.pop(plugin_name, None)

    def get_code_agent_tool_plugins(self) -> List[str]:
        """Return the list of plugin names that declared applicability to code_agent."""
        return sorted(
            name for name, enabled in self._plugin_code_agent_tools.items() if enabled
        )

    # ------------------------------------------------------------------
    # Revocation
    # ------------------------------------------------------------------
    def unregister_plugin(self, plugin_name: str) -> Dict[str, List[str]]:
        """Revoke all resources registered by the specified plugin and return the revoked content.

        Returns:
            {"tools": [...], "rules": [...]}: The tool names and rule names registered by the plugin.
            The caller must use these to actually perform the uninstallation (remove from ToolRegistry / RulesManager).
        """
        tools = list(self._plugin_tools.pop(plugin_name, set()))
        rules = list(self._plugin_rules.pop(plugin_name, set()))
        return {"tools": tools, "rules": rules}

    def clear_tools(self, plugin_name: str) -> None:
        """Only clear the tool registrations of the specified plugin (does not affect rule registrations)."""
        self._plugin_tools.pop(plugin_name, None)

    def clear_rules(self, plugin_name: str) -> None:
        """Only clear the rule registrations of the specified plugin (does not affect tool registrations)."""
        self._plugin_rules.pop(plugin_name, None)

    def revoke_plugin(self, plugin_name: str) -> Dict[str, int]:
        """Revoke all resources registered by the specified plugin and actually perform the uninstallation.

        Uses the registered global revokers (ToolRegistry / RulesManager instances) to actually remove
        the tools and rules registered by the plugin, and clears the registrations.

        Returns:
            {"tools": int, "rules": int}: The number of revoked tools and rules.
        """
        tools = self.get_plugin_tools(plugin_name)
        rules = self.get_plugin_rules(plugin_name)
        revoked_tools = 0
        revoked_rules = 0
        if tools and self._tool_revoker is not None:
            try:
                revoked_tools = int(self._tool_revoker(plugin_name))
            except Exception:
                revoked_tools = 0
        if rules and self._rules_revoker is not None:
            try:
                revoked_rules = int(self._rules_revoker(plugin_name))
            except Exception:
                revoked_rules = 0
        # Clear registrations (the revoker also clears internally; this is a fallback)
        self.unregister_plugin(plugin_name)
        return {"tools": revoked_tools, "rules": revoked_rules}

    def has_plugin(self, plugin_name: str) -> bool:
        """Determine whether the plugin has registered resources."""
        return plugin_name in self._plugin_tools or plugin_name in self._plugin_rules

    def clear(self) -> None:
        """Clear all registrations and revokers (mainly for test isolation)."""
        self._plugin_tools.clear()
        self._plugin_rules.clear()
        self._plugin_code_agent_tools.clear()
        self._tool_revoker = None
        self._rules_revoker = None


__all__ = ["PluginRegistry"]
