# -*- coding: utf-8 -*-
"""
Agent factory module

Provides factory functions for creating Agent and CodeAgent, decoupling from concrete implementations.
Uses HaijunBot's Agent implementation by default, with support for switching to other implementations in the future.
"""

from typing import Any
from typing import Optional
from typing import cast

from haijunbot.haijunbot_c2rust.agent_protocol import AgentType
from haijunbot.haijunbot_c2rust.agent_protocol import CodeAgentType


# Use HaijunBot's Agent implementation by default
# Imports are placed inside functions to avoid circular dependencies during module loading


def create_agent(
    system_prompt: str,
    name: str = "HaijunBot",
    non_interactive: bool = True,
    use_methodology: bool = False,
    use_analysis: bool = False,
    need_summary: bool = False,
    rule_names: Optional[str] = None,
    model_type: str = "normal",
    quick_mode: bool = False,
    **kwargs: Any,
) -> AgentType:
    """
    Create an Agent instance

    Args:
        system_prompt: System prompt
        name: Agent name
        non_interactive: Non-interactive mode
        use_methodology: Whether to use methodology
        use_analysis: Whether to use code analysis
        need_summary: Whether a summary is needed
        rule_names: Rule names
        model_type: Model type; one of "normal", "smart", "cheap" (default "normal")
        quick_mode: Quick mode; when True, forcibly disables methodology, analysis, and rule loading
        **kwargs: Other arguments

    Returns:
        An Agent instance compatible with AgentProtocol

    Example:
        >>> agent = create_agent(
        ...     system_prompt="You are a code reviewer",
        ...     name="Reviewer",
        ...     non_interactive=True
        ... )
        >>> result = agent.run("Review this code")
    """
    # Lazy import to avoid circular dependencies
    from haijunbot.haijunbot_agent import Agent

    # quick_mode: forcibly disable methodology, analysis, and rules
    _use_methodology = False if quick_mode else use_methodology
    _use_analysis = False if quick_mode else use_analysis
    _rule_names = None if quick_mode else rule_names

    # Auto deduplication: pop enable_auto_rule_select from kwargs (if present) to avoid passing it twice
    _enable_auto_rule_select = kwargs.pop("enable_auto_rule_select", False)

    return cast(
        AgentType,
        Agent(  # type: ignore[return-value]
            system_prompt=system_prompt,
            name=name,
            non_interactive=non_interactive,
            use_methodology=_use_methodology,
            use_analysis=_use_analysis,
            need_summary=need_summary,
            rule_names=_rule_names,
            enable_auto_rule_select=_enable_auto_rule_select,
            model_type=model_type,
            **kwargs,
        ),
    )


def create_code_agent(
    name: str = "CodeAgent",
    non_interactive: bool = True,
    need_summary: bool = False,
    summary_prompt: Optional[str] = None,
    append_tools: Optional[str] = None,
    use_methodology: bool = True,
    use_analysis: bool = True,
    disable_review: bool = False,
    enable_task_list_manager: bool = False,
    force_save_memory: bool = False,
    tool_group: Optional[str] = None,
    rule_names: Optional[str] = None,
    quick_mode: bool = False,
    **kwargs: Any,
) -> CodeAgentType:
    """
    Create a CodeAgent instance

    Args:
        name: Agent name
        non_interactive: Non-interactive mode
        need_summary: Whether a summary is needed
        summary_prompt: Summary prompt
        append_tools: List of tools to append (comma-separated)
        use_methodology: Whether to use methodology
        use_analysis: Whether to use code analysis
        disable_review: Whether to disable code review
        enable_task_list_manager: Whether to enable the task list manager
        force_save_memory: Whether to force saving memory
        tool_group: Tool group configuration
        rule_names: Rule names
        quick_mode: Quick mode; when True, forcibly disables methodology, analysis, and rule loading
        **kwargs: Other arguments

    Returns:
        A CodeAgent instance compatible with CodeAgentProtocol

    Example:
        >>> agent = create_code_agent(
        ...     name="C2Rust-GenerationAgent",
        ...     non_interactive=True,
        ...     append_tools="read_symbols",
        ...     use_methodology=True
        ... )
        >>> result = agent.run("Generate Rust code for this C function")
    """
    # Lazy import to avoid circular dependencies
    from haijunbot.haijunbot_code_agent.code_agent import CodeAgent

    # quick_mode: forcibly disable methodology, analysis, and rules
    _use_methodology = False if quick_mode else use_methodology
    _use_analysis = False if quick_mode else use_analysis
    _rule_names = None if quick_mode else rule_names

    # Auto deduplication: pop enable_auto_rule_select from kwargs (if present) to avoid passing it twice
    _enable_auto_rule_select = kwargs.pop("enable_auto_rule_select", False)

    return cast(
        CodeAgentType,
        CodeAgent(  # type: ignore[return-value]
            name=name,
            non_interactive=non_interactive,
            need_summary=need_summary,
            summary_prompt=summary_prompt,
            append_tools=append_tools,
            use_methodology=_use_methodology,
            use_analysis=_use_analysis,
            disable_review=disable_review,
            enable_task_list_manager=enable_task_list_manager,
            force_save_memory=force_save_memory,
            tool_group=tool_group,
            rule_names=_rule_names,
            enable_auto_rule_select=_enable_auto_rule_select,
            **kwargs,
        ),
    )
