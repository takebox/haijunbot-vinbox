#!/usr/bin/env python3
"""Regression tests for child node HTTP proxy passthrough of user_info.

Background: when master forwards a create agent request (POST /agents) to a child node,
it must pass user_info along; otherwise the agent created on the child node will have
owner_id of None, causing the frontend "lossless restart/permission management" buttons
to not display.

This test directly calls NodeConnectionManager._handle_node_http_proxy_request
and asserts that the dispatcher receives user_info from the payload.
"""

import asyncio
import sys
from pathlib import Path
from typing import Any, cast

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from haijunbot.haijunbot_web_gateway.node_config import NodeRuntimeConfig
from haijunbot.haijunbot_web_gateway.node_manager import NodeConnectionManager
from haijunbot.haijunbot_web_gateway.node_runtime import NodeRuntime


class _RecordingDispatcher:
    """Dispatcher stub that records called parameters."""

    def __init__(self):
        self.calls = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return {"success": True, "status_code": 200, "body": "{}"}


def _build_manager(dispatcher):
    runtime = NodeRuntime(NodeRuntimeConfig(node_mode="child", node_id="worker-x"))
    # agent_manager / agent_proxy_manager are not accessed in this test path,
    # so passing None is sufficient; cast is only for type checking.
    return NodeConnectionManager(
        node_runtime=runtime,
        agent_manager=cast(Any, None),
        agent_proxy_manager=cast(Any, None),
        node_http_dispatcher=dispatcher,
    )


def test_proxy_request_forwards_user_info():
    """Non-streaming proxy requests should pass payload.user_info through to the dispatcher."""
    dispatcher = _RecordingDispatcher()
    manager = _build_manager(dispatcher)

    user_info = {"user_id": "u-123", "username": "alice"}
    message = {
        "request_id": "req-1",
        "payload": {
            "method": "POST",
            "path": "/agents",
            "query": "",
            "headers": {"content-type": "application/json"},
            "body": '{"name": "demo"}',
            "user_info": user_info,
        },
    }

    asyncio.run(manager._handle_node_http_proxy_request(None, message))

    assert len(dispatcher.calls) == 1
    call = dispatcher.calls[0]
    assert call["user_info"] == user_info
    assert call["method"] == "POST"
    assert call["path"] == "/agents"


def test_proxy_request_without_user_info_passes_none():
    """When payload does not carry user_info, None should be passed (no error)."""
    dispatcher = _RecordingDispatcher()
    manager = _build_manager(dispatcher)

    message = {
        "request_id": "req-2",
        "payload": {"method": "GET", "path": "/agents"},
    }

    asyncio.run(manager._handle_node_http_proxy_request(None, message))

    assert len(dispatcher.calls) == 1
    assert dispatcher.calls[0]["user_info"] is None


def test_proxy_request_without_dispatcher_returns_error():
    """When dispatcher is not configured, a failure response should be returned instead of raising an exception."""
    manager = _build_manager(None)
    message = {
        "request_id": "req-3",
        "payload": {"method": "GET", "path": "/agents"},
    }

    result = asyncio.run(manager._handle_node_http_proxy_request(None, message))

    assert result is not None
    assert result["payload"]["success"] is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
