# -*- coding: utf-8 -*-
"""Gateway interface and base implementation."""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional
from typing import Tuple

from .events import GatewayConfirmRequest
from .events import GatewayConfirmResult
from .events import GatewayExecutionEvent
from .events import GatewayInputRequest
from .events import GatewayInputResult
from .events import GatewayOutputEvent


class IGateway(ABC):
    """Unified interactive gateway interface."""

    @abstractmethod
    def emit_output(self, event: GatewayOutputEvent) -> None:
        """Send an output event."""

    @abstractmethod
    def request_input(self, request: GatewayInputRequest) -> GatewayInputResult:
        """Request user input."""

    @abstractmethod
    def request_confirm(self, request: GatewayConfirmRequest) -> GatewayConfirmResult:
        """Request user confirmation."""

    @abstractmethod
    def publish_execution_event(
        self,
        event: GatewayExecutionEvent,
        session_id: Optional[str] = None,
    ) -> None:
        """Publish an execution flow event."""

    @abstractmethod
    def get_execution_input_callback(
        self,
        execution_id: str,
    ) -> Optional[Callable[[float], Optional[str]]]:
        """Get the execution input callback (used for interactive terminals)."""

    @abstractmethod
    def get_execution_resize_callback(
        self,
        execution_id: str,
    ) -> Optional[Callable[[], Optional[Tuple[int, int]]]]:
        """Get the execution terminal resize callback."""


class BaseGateway(IGateway):
    """Base gateway implementation, making it easy to extend with custom interaction methods."""

    def _check_auth(self, auth: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
        """Check authentication information, supporting JWT Tokens and legacy UUID Tokens.

        Args:
            auth: Authentication information dictionary, should contain a token field

        Returns:
            (whether authentication succeeded, error message) tuple
        """
        # Import the token management module
        try:
            from haijunbot.haijunbot_web_gateway.token_manager import validate_gateway_token
        except ImportError:
            # If unavailable (such as CLI Gateway), reject authentication
            return False, "token validation unavailable"

        # Check the Token
        if not auth:
            return False, "token missing"

        token = auth.get("token")
        if not token:
            return False, "token missing"

        # validate_gateway_token now returns Optional[dict], None means validation failed
        user_info = validate_gateway_token(token)
        if user_info is not None:
            # Store user info in the auth dictionary for later use
            auth["user_info"] = user_info
            return True, None

        return False, "invalid token"

    def emit_output(self, event: GatewayOutputEvent) -> None:
        del event
        raise NotImplementedError

    def request_input(self, request: GatewayInputRequest) -> GatewayInputResult:
        del request
        raise NotImplementedError

    def request_confirm(self, request: GatewayConfirmRequest) -> GatewayConfirmResult:
        del request
        raise NotImplementedError

    def publish_execution_event(
        self,
        event: GatewayExecutionEvent,
        session_id: Optional[str] = None,
    ) -> None:
        del event, session_id
        raise NotImplementedError

    def get_execution_input_callback(
        self,
        execution_id: str,
    ) -> Optional[Callable[[float], Optional[str]]]:
        del execution_id
        return None

    def get_execution_resize_callback(
        self,
        execution_id: str,
    ) -> Optional[Callable[[], Optional[Tuple[int, int]]]]:
        del execution_id
        return None
