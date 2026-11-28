# -*- coding: utf-8 -*-
"""
HaijunBot audit system module (haijunbot_audit)

Provides configurable, disabled-by-default audit logging capability, recording key Agent
behavior events (user input, tool calls, task completion, etc.) to a JSONL audit log.
"""

from .audit import AuditLogger
from .audit import log_event

__all__ = ["AuditLogger", "log_event"]
__version__ = "1.0.0"
