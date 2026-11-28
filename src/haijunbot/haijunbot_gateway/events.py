# -*- coding: utf-8 -*-
"""Gateway event model definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Dict
from typing import Optional


@dataclass(frozen=True)
class GatewayOutputEvent:
    """Unified output event."""

    text: str
    output_type: str
    timestamp: Optional[str | bool] = (
        None  # ISO format time string, e.g. '2026-07-30T15:08:52'
    )
    lang: Optional[str] = None
    traceback: bool = False
    section: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class GatewayInputRequest:
    """Unified input request."""

    tip: str
    mode: Optional[str] = None  # 'single' or 'multi'
    preset: Optional[str] = None
    preset_cursor: Optional[int] = None
    is_password: bool = False
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class GatewayInputResult:
    """Unified input result."""

    text: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class GatewayConfirmRequest:
    """Confirmation request."""

    message: str
    default: bool = True
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class GatewayConfirmResult:
    """Confirmation result."""

    confirmed: bool
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class GatewayExecutionEvent:
    """Unified execution event."""

    event_type: str
    payload: Dict[str, Any]
    timestamp: Optional[str] = None
