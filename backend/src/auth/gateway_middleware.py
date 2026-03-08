"""Starlette middleware for JWT authentication on the Gateway API."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.auth.jwt_utils import DEFAULT_USER_ID, verify_jwt

# Paths that bypass auth
_SKIP_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


class AuthMiddleware(BaseHTTPMiddleware):
    """Extract and validate JWT from Authorization header.

    Sets ``request.state.user_id`` on success.
    Returns 401 if the token is missing or invalid.
    Returns 429 if the per-user rate limit is exceeded (when Redis is configured).
    Skips auth for health/docs paths.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _SKIP_PATHS:
            request.state.user_id = DEFAULT_USER_ID
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authorization header missing or invalid"},
            )

        token = auth_header[len("Bearer "):]
        try:
            user_id = verify_jwt(token)
        except Exception as exc:
            return JSONResponse(
                status_code=401,
                content={"detail": f"Invalid token: {exc}"},
            )

        # Per-user rate limiting (no-op when REDIS_URI is not configured)
        try:
            from src.auth.rate_limit import check_rate_limit

            await check_rate_limit(user_id)
        except Exception as exc:
            from fastapi import HTTPException

            if isinstance(exc, HTTPException) and exc.status_code == 429:
                return JSONResponse(status_code=429, content={"detail": exc.detail})
            # Any other rate-limit error must NOT block the request
            import logging

            logging.getLogger(__name__).error(f"Rate limit check error: {exc}")

        request.state.user_id = user_id
        return await call_next(request)
