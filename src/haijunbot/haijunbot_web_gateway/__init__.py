# -*- coding: utf-8 -*-
"""Web Gateway standalone service entry point."""

from .app import create_app
from .app import run

__all__ = ["create_app", "run"]
