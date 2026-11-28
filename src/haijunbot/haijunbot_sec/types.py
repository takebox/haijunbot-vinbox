# -*- coding: utf-8 -*-
"""
Shared types for haijunbot.haijunbot_sec to avoid circular imports.
"""

from dataclasses import dataclass


@dataclass
class Issue:
    language: str
    category: str
    pattern: str
    file: str
    line: int
    evidence: str
    description: str
    suggestion: str
    confidence: float
    severity: str = "medium"
    var_name: str | None = None  # Variable name (optional, used for false-positive filtering)


__all__ = ["Issue"]
