# -*- coding: utf-8 -*-
"""ELI Gateway implementation: reuses the existing output/input logic and stays backward compatible."""

from __future__ import annotations

from typing import Callable
from typing import Optional

from haijunbot.haijunbot_gateway.events import GatewayConfirmRequest
from haijunbot.haijunbot_gateway.events import GatewayConfirmResult
from haijunbot.haijunbot_gateway.events import GatewayExecutionEvent
from haijunbot.haijunbot_gateway.events import GatewayInputRequest
from haijunbot.haijunbot_gateway.events import GatewayInputResult
from haijunbot.haijunbot_gateway.events import GatewayOutputEvent
from haijunbot.haijunbot_gateway.gateway import BaseGateway
from haijunbot.haijunbot_utils.input import get_current_input_provider
from haijunbot.haijunbot_utils.output import OutputEvent
from haijunbot.haijunbot_utils.output import OutputType
from haijunbot.haijunbot_utils.output import emit_output


class ELIGateway(BaseGateway):
    """Default ELI gateway implementation, reusing the existing output/input capabilities."""

    def __init__(
        self,
        execution_event_handler: Optional[
            Callable[[GatewayExecutionEvent, Optional[str]], None]
        ] = None,
    ) -> None:
        self._execution_event_handler = execution_event_handler

    def emit_output(self, event: GatewayOutputEvent) -> None:
        auth_payload = None
        if event.context:
            auth_payload = event.context.get("auth")
        authorized, _ = self._check_auth(auth_payload)
        if not authorized:
            return
        context = dict(event.context) if event.context else {}
        context["_gateway_skip"] = True
        output_event = OutputEvent(
            text=event.text,
            output_type=_resolve_output_type(event.output_type),
            timestamp=event.timestamp,
            lang=event.lang,
            traceback=event.traceback,
            section=event.section,
            context=context,
        )
        emit_output(output_event)

    def request_input(self, request: GatewayInputRequest) -> GatewayInputResult:
        auth_payload = None
        if request.metadata:
            auth_payload = request.metadata.get("auth")
        authorized, reason = self._check_auth(auth_payload)
        if not authorized:
            return GatewayInputResult(text="", metadata={"error": reason})
        provider = get_current_input_provider()
        text = provider.get_multiline_input(
            request.tip,
            preset=request.preset,
            preset_cursor=request.preset_cursor,
        )
        return GatewayInputResult(text=text, metadata=request.metadata)

    def request_confirm(self, request: GatewayConfirmRequest) -> GatewayConfirmResult:
        auth_payload = None
        if request.metadata:
            auth_payload = request.metadata.get("auth")
        authorized, reason = self._check_auth(auth_payload)
        if not authorized:
            return GatewayConfirmResult(
                confirmed=request.default, metadata={"error": reason}
            )
        provider = get_current_input_provider()
        # Use get_multiline_input to receive user input
        suffix = "[Y/n]" if request.default else "[y/N]"
        result = provider.get_multiline_input(f"{request.message} {suffix}: ")
        # Return the confirmation result
        confirmed = request.default if result == "" else result.lower() == "y"
        return GatewayConfirmResult(confirmed=confirmed, metadata=request.metadata)

    def publish_execution_event(
        self,
        event: GatewayExecutionEvent,
        session_id: Optional[str] = None,
    ) -> None:
        auth_payload = None
        payload = event.payload if isinstance(event.payload, dict) else {}
        auth_payload = payload.get("auth")
        authorized, _ = self._check_auth(auth_payload)
        if not authorized:
            return
        if self._execution_event_handler is None:
            return
        self._execution_event_handler(event, session_id)


def _resolve_output_type(output_type: str) -> OutputType:
    try:
        return OutputType[output_type]
    except KeyError:
        pass
    try:
        return OutputType(output_type)
    except Exception:
        return OutputType.INFO
