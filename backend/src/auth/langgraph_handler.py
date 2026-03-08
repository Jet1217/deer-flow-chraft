"""LangGraph Platform auth handler for multi-tenant JWT verification."""

from langgraph_sdk import Auth

from src.auth.jwt_utils import DEFAULT_USER_ID, is_auth_enabled, verify_jwt

auth = Auth()


@auth.authenticate
async def authenticate(authorization: str | None) -> dict:
    """Verify JWT and return user identity for LangGraph.

    LangGraph requires the returned dict to have an ``identity`` key (str).
    Optional keys: ``is_authenticated`` (bool), ``display_name`` (str).

    When AUTH_ENABLED=false, always returns the default user.
    """
    if not is_auth_enabled():
        return {"identity": DEFAULT_USER_ID, "is_authenticated": True}

    if not authorization or not authorization.startswith("Bearer "):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Authorization header missing")

    token = authorization[len("Bearer "):]
    try:
        user_id = verify_jwt(token)
    except Exception as exc:
        raise Auth.exceptions.HTTPException(status_code=401, detail=f"Invalid token: {exc}")

    return {"identity": user_id, "is_authenticated": True}


@auth.on
async def add_owner(ctx, value):
    """Inject owner into thread metadata so LangGraph can filter threads by user."""
    # ctx.user is the dict returned by authenticate; access via .identity or ["identity"]
    user_id = ctx.user.identity if hasattr(ctx.user, "identity") else ctx.user["identity"]
    filters = {"owner": user_id}
    metadata = value.setdefault("metadata", {})
    metadata.update(filters)
    return filters
