"""Tests for child node gateway listen address restrictions.

Child nodes have no local auth data and do not perform independent permission checks,
so the gateway must only listen on the loopback address, otherwise the node would be
exposed as an unauthenticated entry point.
"""

import pytest

from haijunbot.haijunbot_service.eli import build_service_config


@pytest.mark.parametrize(
    "requested_host",
    ["0.0.0.0", "192.168.1.5", "10.0.0.1", "example.com"],
)
def test_child_gateway_host_forced_to_loopback(requested_host: str) -> None:
    """When a child node requests a non-loopback address, it should be forced to fall back to 127.0.0.1."""
    config = build_service_config(
        node_mode="child", node_id="n1", gateway_host=requested_host
    )
    assert config.gateway_host == "127.0.0.1"


@pytest.mark.parametrize("loopback_host", ["127.0.0.1", "localhost", "::1"])
def test_child_gateway_host_keeps_loopback(loopback_host: str) -> None:
    """When a child node requests a loopback address, the original value should be kept."""
    config = build_service_config(
        node_mode="child", node_id="n1", gateway_host=loopback_host
    )
    assert config.gateway_host == loopback_host


def test_master_gateway_host_not_restricted() -> None:
    """Master nodes are not restricted and still need to support external listening."""
    config = build_service_config(node_mode="master", gateway_host="0.0.0.0")
    assert config.gateway_host == "0.0.0.0"
