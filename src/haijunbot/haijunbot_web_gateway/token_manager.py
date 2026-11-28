# -*- coding: utf-8 -*-
"""Token management module.

Handles generating and validating the Gateway Token.
The Token is generated once when the Web Gateway starts and is used permanently.
Supports JWT Token validation, falling back to the legacy UUID Token.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, Optional


def generate_gateway_token() -> str:
    """Generate a Gateway Token.

    Generates a random UUID string as the Token.

    Returns:
        Token string
    """
    return str(uuid.uuid4())


def validate_gateway_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Validate the Gateway Token, preferring JWT validation and falling back to environment variable comparison.

    Args:
        token: The Token to validate

    Returns:
        Returns the user info dict on success, or None on failure
    """
    if not token:
        return None

    # Prefer JWT validation
    try:
        from .jwt_utils import validate_jwt_token

        payload = validate_jwt_token(token)
        if payload:
            return payload
    except ImportError:
        pass

    # Fallback: environment variable comparison (for CLI Gateway)
    expected_token = os.environ.get("HAIJUNBOT_AUTH_TOKEN")
    if expected_token and token == expected_token:
        return {"user_id": "system", "username": "gateway", "is_admin": True}

    return None


def validate_token_with_user(token: str) -> Optional[Dict[str, Any]]:
    """Validate the Token and return user information, for HTTP API authentication.

    Args:
        token: The Token to validate

    Returns:
        Returns the user info dict on success, or None on failure
    """
    # Prefer JWT validation
    try:
        from .jwt_utils import validate_jwt_token

        payload = validate_jwt_token(token)
        if payload:
            return payload
    except ImportError:
        pass

    # Fall back to the legacy Token
    env_token = os.environ.get("HAIJUNBOT_AUTH_TOKEN")
    if env_token and token == env_token:
        return {"user_id": "system", "username": "gateway", "is_admin": True}

    return None


def extract_token_from_authorization_header(
    authorization: Optional[str],
) -> Optional[str]:
    """Extract the Token from the Authorization Header.

    Args:
        authorization: The Authorization Header value, in the format "Bearer <token>"

    Returns:
        The Token string, or None if the format is incorrect
    """
    if not authorization:
        return None

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]
