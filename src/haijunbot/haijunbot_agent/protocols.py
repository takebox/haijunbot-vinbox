from typing import Any
from typing import Protocol
from typing import Tuple
from typing import runtime_checkable


@runtime_checkable
class OutputHandlerProtocol(Protocol):
    """
    Defines the interface for output handlers, which are responsible for processing model responses, typically used for executing tools.
    """

    def name(self) -> str:
        """Return the name of the handler."""
        ...

    def can_handle(self, response: str) -> bool:
        """Check if this handler can process the given response."""
        ...

    def prompt(self) -> str:
        """Return a prompt snippet describing the handler's functionality."""
        ...

    def handle(self, response: str, agent: Any) -> Tuple[bool, Any]:
        """
        Process the response and execute related logic.

        Returns:
            A tuple containing a boolean (whether to return) and the result.
        """
        ...
