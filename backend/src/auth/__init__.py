"""Auth module: JWT verification, middleware, and per-user secrets."""

from fastapi import Request

from src.auth.jwt_utils import DEFAULT_USER_ID


async def get_current_user_id(request: Request) -> str:
    """FastAPI dependency: return the authenticated user_id.

    Falls back to DEFAULT_USER_ID when AUTH_ENABLED=false or
    when the middleware hasn't set request.state.user_id.
    """
    return getattr(request.state, "user_id", DEFAULT_USER_ID)
