# -*- coding: utf-8 -*-
"""JWT Token management module.

Handles issuing and validating JWT Tokens and blacklist management.
Supports a multi-user authentication system, replacing the original single-Token mode.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Optional

import jwt

# JWT signing secret: prefer reading from the environment variable; if unset, generate randomly (invalidated on restart)
_jwt_secret: str = os.environ.get("HAIJUNBOT_JWT_SECRET", "")

if not _jwt_secret:
    _jwt_secret = uuid.uuid4().hex + uuid.uuid4().hex

# Token validity period (hours): 0 means never expires (background services require long-lived connections)
# Compatible with the legacy environment variable HAIJUNBOT_JWT_EXPIRE_HOURS, defaults to 0 (never expires)
_jwt_expire_hours: int = int(os.environ.get("HAIJUNBOT_JWT_EXPIRE_HOURS", "0"))

# Token blacklist: {jti: exp_timestamp}
_revoked_tokens: dict[str, float] = {}


def generate_jwt_token(user_id: str, username: str, is_admin: bool) -> str:
    """Generate a JWT Token.

    By default no exp field is written, i.e. the Token never expires (background services require long-lived connections).
    A Token with an expiry is only issued when HAIJUNBOT_JWT_EXPIRE_HOURS > 0.

    Args:
        user_id: Unique user identifier
        username: Username
        is_admin: Whether the user is an admin

    Returns:
        JWT Token string
    """
    now = time.time()
    payload = {
        "user_id": user_id,
        "username": username,
        "is_admin": is_admin,
        "iat": int(now),
        "jti": uuid.uuid4().hex,
    }
    # Only write exp when a finite validity period (>0) is configured; otherwise the issued Token never expires
    if _jwt_expire_hours > 0:
        payload["exp"] = int(now) + _jwt_expire_hours * 3600
    return jwt.encode(payload, _jwt_secret, algorithm="HS256")


def validate_jwt_token(token: str) -> Optional[dict]:
    """Validate a JWT Token.

    Validates the signature and expiry (absence of an exp field is treated as never expiring), and checks whether the Token is blacklisted.

    Args:
        token: JWT Token string

    Returns:
        Returns the payload dict on success, or None on failure
    """
    try:
        payload = jwt.decode(token, _jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

    # Check the blacklist
    jti = payload.get("jti", "")
    if jti and jti in _revoked_tokens:
        return None

    return payload


def revoke_token(token: str) -> None:
    """Add the Token to the blacklist.

    Adds the Token's jti to the blacklist; entries are cleaned up by cleanup_revoked_tokens after expiry.

    Args:
        token: JWT Token string
    """
    try:
        # Do not verify expiry; only decode to obtain jti and exp
        payload = jwt.decode(
            token, _jwt_secret, algorithms=["HS256"], options={"verify_exp": False}
        )
        jti = payload.get("jti", "")
        exp = payload.get("exp", 0)
        if jti:
            _revoked_tokens[jti] = float(exp)
    except jwt.InvalidTokenError:
        pass


def cleanup_revoked_tokens() -> None:
    """Clean up expired entries in the blacklist."""
    now = time.time()
    expired_jtis = [jti for jti, exp in _revoked_tokens.items() if exp < now]
    for jti in expired_jtis:
        del _revoked_tokens[jti]
