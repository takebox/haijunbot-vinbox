# -*- coding: utf-8 -*-
"""Web Gateway common endpoints module

Provides shared implementations of the /rules and /tools endpoints for reuse by different Agents.
"""

from typing import Any, Dict


def get_rules_info() -> Dict[str, Any]:
    """Get rules information (overall and loaded).

    Returns:
        Dict[str, Any]: A dictionary containing the rules list, in the format {"rules": [...]}
    """
    try:
        from haijunbot.haijunbot_utils.globals import (
            global_agents,
            running_agent_stack,
        )

        # Get the root agent (the first in running_agent_stack, i.e. the earliest started agent)
        if running_agent_stack:
            root_agent_name = running_agent_stack[0]
            root_agent = global_agents.get(root_agent_name)
            if root_agent and hasattr(root_agent, "rules_manager"):
                rules_manager = root_agent.rules_manager
                rules_info = rules_manager.get_all_rules_with_status()
                rules_list = [
                    {
                        "name": name,
                        "preview": preview,
                        "is_loaded": is_loaded,
                        "file_path": file_path,
                    }
                    for name, preview, is_loaded, file_path in rules_info
                ]
                # Added: return the concrete content of loaded rules
                loaded_rules_content = rules_manager.get_loaded_rules_content()
                return {
                    "rules": rules_list,
                    "loaded_rules_content": loaded_rules_content,
                }
        return {"rules": [], "loaded_rules_content": ""}
    except Exception as e:
        return {"rules": [], "loaded_rules_content": "", "error": str(e)}


def get_tools_info() -> Dict[str, Any]:
    """Get tools information (all tools and allowed tools).

    Returns:
        Dict[str, Any]: A dictionary containing tool information, in the format {"all_tools": [...], "allowed_tools": [...]}
    """
    try:
        from haijunbot.haijunbot_utils.globals import (
            global_agents,
            running_agent_stack,
        )

        # Get the root agent (the first in running_agent_stack, i.e. the earliest started agent)
        if running_agent_stack:
            root_agent_name = running_agent_stack[0]
            root_agent = global_agents.get(root_agent_name)
            if root_agent:
                tool_registry = root_agent.get_tool_registry()
                if tool_registry:
                    all_tools = tool_registry.get_all_tools()
                    allowed_tools = getattr(root_agent, "use_tools", None)
                    return {
                        "all_tools": all_tools,
                        "allowed_tools": allowed_tools,
                    }
        return {"all_tools": [], "allowed_tools": None}
    except Exception as e:
        return {"all_tools": [], "allowed_tools": None, "error": str(e)}
