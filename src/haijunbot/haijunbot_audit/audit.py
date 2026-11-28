# -*- coding: utf-8 -*-
"""
Audit log module (haijunbot_audit.audit)

Provides configurable, disabled-by-default audit logging capability: records key Agent
behavior events (user input, tool calls, task completion, etc.) to JSONL audit logs
split by day, for security review and behavior tracking.

Design points:
- Disabled by default: log_event first checks is_enable_audit(), returning immediately with zero overhead when disabled;
- Split by day: writes to ~/.haijunbot/audit/YYYY-MM-DD.jsonl in JSON Lines format;
- Sensitive redaction: values of fields such as password/token/key/secret/auth/credential are masked;
- Process-safe: written in append mode, with a single record written at a time;
- Silent on failure: write exceptions only call save_exception and never affect the main flow.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_utils.config import is_enable_audit
from haijunbot.haijunbot_utils.exception_utils import save_exception

# Sensitive field names (values will be masked)
_SENSITIVE_KEYS = {"password", "token", "key", "secret", "auth", "credential"}

# Global singleton and lock (process-safe)
_logger: "AuditLogger | None" = None
_lock = threading.Lock()


def _is_sensitive_key(key: str) -> bool:
    """Determine whether a key name contains a sensitive word (substring match, covering compound keys such as api_key/access_token)."""
    lowered = str(key).lower()
    return any(s in lowered for s in _SENSITIVE_KEYS)


def _redact(value: Any) -> Any:
    """Recursively redact: replace the values of sensitive fields with ***."""
    if isinstance(value, dict):
        return {
            k: ("***" if _is_sensitive_key(k) else _redact(v)) for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


class AuditLogger:
    """Audit log writer (appends to JSONL files split by day)."""

    def __init__(self, data_dir: str | None = None) -> None:
        self.data_dir = Path(data_dir or get_data_dir()) / "audit"

    def _get_file_path(self) -> Path:
        return self.data_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"

    def log(self, event_type: str, **data: Any) -> None:
        """Write a single audit event record.

        Args:
            event_type: Event type (e.g. user_input / tool_call / task_completed)
            data: Event data (sensitive fields are redacted before writing)
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": _redact(data),
        }
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            file_path = self._get_file_path()
            with open(file_path, "a", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False)
                f.write("\n")
        except Exception as e:
            save_exception(e, module="haijunbot_audit.audit", function="AuditLogger.log")


def log_event(event_type: str, **data: Any) -> None:
    """Record a single audit event (returns immediately with zero overhead when disabled by default).

    This function is the unified external entry point of the audit system, called by each
    Agent integration point. Logs are only actually written when auditing is enabled
    (enable_audit: true).
    """
    if not is_enable_audit():
        return

    global _logger
    if _logger is None:
        with _lock:
            if _logger is None:
                _logger = AuditLogger()
    try:
        _logger.log(event_type, **data)
    except Exception as e:
        save_exception(e, module="haijunbot_audit.audit", function="log_event")
