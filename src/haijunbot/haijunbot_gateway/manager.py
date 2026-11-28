# -*- coding: utf-8 -*-
"""Gateway manager, used to get/set the current gateway implementation."""

from __future__ import annotations

from threading import RLock
from typing import Optional

from .gateway import IGateway


_current_gateway: Optional[IGateway] = None
_gateway_lock = RLock()


def set_current_gateway(gateway: Optional[IGateway]) -> None:
    """Set the current gateway implementation (None means not enabled)."""
    global _current_gateway
    with _gateway_lock:
        _current_gateway = gateway


def get_current_gateway() -> Optional[IGateway]:
    """Get the current gateway implementation; returns None if not set."""
    with _gateway_lock:
        return _current_gateway
