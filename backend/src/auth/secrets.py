"""User secrets management: Fernet-encrypted API keys per user."""

import json
import logging
import os

from cryptography.fernet import Fernet

from src.config.paths import get_paths

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet | None:
    """Return a Fernet instance using SECRETS_MASTER_KEY, or None if not configured."""
    master_key = os.environ.get("SECRETS_MASTER_KEY", "")
    if not master_key:
        return None
    return Fernet(master_key.encode() if isinstance(master_key, str) else master_key)


def load_user_secrets(user_id: str | None) -> dict[str, str]:
    """Load and decrypt a user's secrets file.

    Returns an empty dict if:
    - user_id is None
    - SECRETS_MASTER_KEY is not set
    - secrets file does not exist
    """
    if not user_id:
        return {}
    fernet = _get_fernet()
    if fernet is None:
        return {}
    secrets_file = get_paths().user_secrets_file(user_id)
    if not secrets_file.exists():
        return {}
    try:
        encrypted = secrets_file.read_bytes()
        plain = fernet.decrypt(encrypted)
        return json.loads(plain)
    except Exception as exc:
        logger.warning(f"Failed to load secrets for user {user_id}: {exc}")
        return {}


def save_user_secrets(user_id: str, secrets: dict[str, str]) -> None:
    """Encrypt and save a user's secrets file atomically."""
    fernet = _get_fernet()
    if fernet is None:
        raise RuntimeError("SECRETS_MASTER_KEY is not configured")
    secrets_file = get_paths().user_secrets_file(user_id)
    secrets_file.parent.mkdir(parents=True, exist_ok=True)
    encrypted = fernet.encrypt(json.dumps(secrets).encode())
    tmp = secrets_file.with_suffix(".tmp")
    tmp.write_bytes(encrypted)
    tmp.replace(secrets_file)


def resolve_api_key(key_name: str, user_id: str | None) -> str | None:
    """Resolve an API key: user's secrets first, platform .env fallback."""
    if user_id:
        user_secrets = load_user_secrets(user_id)
        if key_name in user_secrets:
            return user_secrets[key_name]
    return os.environ.get(key_name)
