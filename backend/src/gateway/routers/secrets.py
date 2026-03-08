"""User API key management: store, list, and delete per-user encrypted secrets."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.auth import get_current_user_id
from src.auth.secrets import load_user_secrets, save_user_secrets

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/secrets", tags=["secrets"])


class SecretSetRequest(BaseModel):
    """Request body for setting a user API key."""

    key_name: str = Field(..., description="Environment variable name, e.g. TAVILY_API_KEY")
    key_value: str = Field(..., description="The secret value")


class SecretsListResponse(BaseModel):
    """List of configured secret key names (values are never returned)."""

    keys: list[str] = Field(default_factory=list, description="Names of configured API keys")


@router.get(
    "",
    response_model=SecretsListResponse,
    summary="List User API Keys",
    description="Return the names of API keys configured by the current user. Values are never returned.",
)
async def list_secrets(user_id: str = Depends(get_current_user_id)) -> SecretsListResponse:
    """List configured secret key names for the current user."""
    try:
        secrets = load_user_secrets(user_id)
        return SecretsListResponse(keys=sorted(secrets.keys()))
    except Exception as e:
        logger.error(f"Failed to list secrets for {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list secrets: {str(e)}")


@router.post(
    "",
    summary="Set User API Key",
    description="Create or update an API key in the current user's encrypted secrets store.",
)
async def set_secret(request: SecretSetRequest, user_id: str = Depends(get_current_user_id)) -> dict:
    """Set or update a secret for the current user."""
    if not request.key_name or not request.key_name.isidentifier():
        raise HTTPException(status_code=422, detail=f"Invalid key_name '{request.key_name}'")
    try:
        secrets = load_user_secrets(user_id)
        secrets[request.key_name] = request.key_value
        save_user_secrets(user_id, secrets)
        logger.info(f"Secret '{request.key_name}' set for user {user_id}")
        return {"success": True, "key_name": request.key_name}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to set secret '{request.key_name}' for {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to set secret: {str(e)}")


@router.delete(
    "/{key_name}",
    summary="Delete User API Key",
    description="Remove a specific API key from the current user's encrypted secrets store.",
)
async def delete_secret(key_name: str, user_id: str = Depends(get_current_user_id)) -> dict:
    """Delete a secret for the current user."""
    try:
        secrets = load_user_secrets(user_id)
        if key_name not in secrets:
            raise HTTPException(status_code=404, detail=f"Key '{key_name}' not found")
        del secrets[key_name]
        save_user_secrets(user_id, secrets)
        logger.info(f"Secret '{key_name}' deleted for user {user_id}")
        return {"success": True, "key_name": key_name}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete secret '{key_name}' for {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete secret: {str(e)}")
