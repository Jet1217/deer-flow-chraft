"""JWT verification utilities for multi-tenant auth."""

import os
import re

import jwt

_AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "false").lower() == "true"
_JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
_JWT_USER_ID_CLAIM = os.environ.get("JWT_USER_ID_CLAIM", "sub")

# Prevent path traversal: only allow alphanumeric, hyphens, underscores
_SAFE_USER_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")

DEFAULT_USER_ID = "default"


def _get_secret() -> str:
    secret = os.environ.get("JWT_SECRET_KEY", "")
    if not secret:
        raise ValueError("JWT_SECRET_KEY environment variable is not set")
    return secret


def verify_jwt(token: str) -> str:
    """Verify a JWT token and return the user_id.

    Args:
        token: The JWT token string.

    Returns:
        The user_id extracted from the JWT payload.

    Raises:
        jwt.InvalidTokenError: If the token is invalid or expired.
        ValueError: If the user_id claim is missing or has an invalid format.
    """
    payload = jwt.decode(token, _get_secret(), algorithms=[_JWT_ALGORITHM])
    user_id = payload.get(_JWT_USER_ID_CLAIM)
    if not user_id or not isinstance(user_id, str):
        raise ValueError(f"JWT missing or invalid '{_JWT_USER_ID_CLAIM}' claim")
    if not _SAFE_USER_ID_RE.match(user_id):
        raise ValueError(f"user_id '{user_id}' contains invalid characters")
    return user_id


def is_auth_enabled() -> bool:
    """Check whether authentication is enabled (reads env at call time)."""
    return os.environ.get("AUTH_ENABLED", "false").lower() == "true"
