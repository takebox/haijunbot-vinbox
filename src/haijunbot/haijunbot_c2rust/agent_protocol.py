# -*- coding: utf-8 -*-
"""
Abstract protocol interfaces for Agent and CodeAgent

Uses typing.Protocol to define interface specifications, decoupling from concrete Agent implementations.
Supports future migration to other Agent implementations (such as Agents from other LLM platforms).
"""

from typing import Any
from typing import Callable
from typing import Optional
from typing import Protocol
from typing import runtime_checkable


@runtime_checkable
class EventBusProtocol(Protocol):
    """Event bus protocol"""

    def subscribe(self, event: str, callback: Callable[..., Any]) -> None:
        """Subscribe to an event"""
        ...

    def emit(self, event: str, **kwargs: Any) -> None:
        """Emit an event"""
        ...


@runtime_checkable
class SessionProtocol(Protocol):
    """Session management protocol"""

    prompt: str

    def clear_history(self) -> None:
        """Clear the history"""
        ...


@runtime_checkable
class AgentProtocol(Protocol):
    """
    Agent base protocol

    Defines the interfaces that an Agent must implement, including core attributes and methods.
    Any Agent that implements this protocol can be used by hc2r.

    Note: Protocol uses structural subtyping; an implementation only needs to include the required attributes and methods.
    The actual Agent/CodeAgent classes may contain more attributes; here we only define the core interfaces needed by hc2r.
    """

    # Core attributes (use looser types for compatibility with different implementations)
    event_bus: Any  # Actually EventBus, but use Any to avoid type conflicts
    session: Any  # Actually SessionManager, but use Any to avoid type conflicts
    name: str
    non_interactive: Optional[bool]  # Allow None for compatibility with actual implementations

    def run(self, user_input: str, **kwargs: Any) -> Any:
        """
        Run the Agent to process user input

        Args:
            user_input: User input text
            **kwargs: Extra arguments (such as prefix, suffix, etc.)

        Returns:
            The Agent's execution result
        """
        ...

    def clear_history(self) -> None:
        """Clear the session history"""
        ...

    def get_user_origin_input(self) -> str:
        """Get the original user input"""
        ...


@runtime_checkable
class CodeAgentProtocol(AgentProtocol, Protocol):
    """
    CodeAgent extension protocol

    Inherits AgentProtocol and adds interfaces specific to the code Agent.
    Mainly used for scenarios such as code generation, repair, and optimization.
    """

    # CodeAgent-specific attributes
    root_dir: str
    tool_group: Optional[str]
    disable_review: bool
    review_max_iterations: int
    prefix: str
    suffix: str
    start_commit: Optional[str]

    def get_user_data(self, key: str) -> Any:
        """
        Get user data

        Args:
            key: Data key

        Returns:
            The stored user data
        """
        ...


# Type aliases for type annotations
AgentType = AgentProtocol
CodeAgentType = CodeAgentProtocol
