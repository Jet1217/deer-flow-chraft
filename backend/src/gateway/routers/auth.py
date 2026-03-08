"""Auth API: current user and scope for frontend."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.auth import get_current_user_id
from src.config.agents_config import _is_user_scoped

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthMeResponse(BaseModel):
    """Current auth context for the request."""

    user_id: str = Field(..., description="Current user ID (from JWT or 'default' when auth disabled)")
    is_user_scoped: bool = Field(
        ...,
        description="True when data is isolated per user (authenticated with non-default user_id)",
    )


@router.get(
    "/me",
    response_model=AuthMeResponse,
    summary="Current auth context",
    description="Return current user_id and whether the session is user-scoped (per-user isolation for agents, skills, memory).",
)
async def get_me(user_id: str = Depends(get_current_user_id)) -> AuthMeResponse:
    """Return current user identity and scope.

    - user_id: from JWT claim when AUTH_ENABLED=true and token valid; otherwise 'default'.
    - is_user_scoped: True when user_id is set and not 'default'. When True, agents/skills/memory use per-user storage.
    """
    return AuthMeResponse(
        user_id=user_id,
        is_user_scoped=_is_user_scoped(user_id),
    )
