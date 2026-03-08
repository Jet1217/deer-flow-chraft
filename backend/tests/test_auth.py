"""Unit tests for the multi-tenant auth module.

Covers:
- JWT verification (jwt_utils)
- AuthMiddleware request/response flow
- Secrets encryption / decryption (secrets)
- User namespace path safety (paths)
- Rate limiting (rate_limit) — no-op when Redis is absent
"""

import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Path setup ───────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))


# ════════════════════════════════════════════════════════════════════════
# jwt_utils
# ════════════════════════════════════════════════════════════════════════

class TestJwtUtils:
    def _make_token(self, payload: dict, secret: str = "test-secret", algorithm: str = "HS256") -> str:
        import jwt
        return jwt.encode(payload, secret, algorithm=algorithm)

    def test_verify_valid_token_returns_user_id(self):
        from src.auth.jwt_utils import verify_jwt

        token = self._make_token({"sub": "user-abc"})
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret", "AUTH_ENABLED": "true"}):
            user_id = verify_jwt(token)
        assert user_id == "user-abc"

    def test_verify_expired_token_raises(self):
        import jwt
        from src.auth.jwt_utils import verify_jwt

        token = self._make_token({"sub": "user-abc", "exp": int(time.time()) - 10})
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret", "AUTH_ENABLED": "true"}):
            with pytest.raises(Exception):
                verify_jwt(token)

    def test_verify_wrong_secret_raises(self):
        from src.auth.jwt_utils import verify_jwt

        token = self._make_token({"sub": "user-abc"}, secret="wrong")
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "correct-secret", "AUTH_ENABLED": "true"}):
            with pytest.raises(Exception):
                verify_jwt(token)

    def test_custom_claim_field(self):
        from src.auth.jwt_utils import verify_jwt

        token = self._make_token({"uid": "user-xyz"})
        with patch.dict(os.environ, {
            "JWT_SECRET_KEY": "test-secret",
            "AUTH_ENABLED": "true",
            "JWT_USER_ID_CLAIM": "uid",
        }):
            user_id = verify_jwt(token)
        assert user_id == "user-xyz"

    def test_unsafe_user_id_raises(self):
        """User IDs with path traversal chars must be rejected."""
        from src.auth.jwt_utils import verify_jwt

        token = self._make_token({"sub": "../../etc/passwd"})
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret", "AUTH_ENABLED": "true"}):
            with pytest.raises(Exception, match="user_id"):
                verify_jwt(token)


# ════════════════════════════════════════════════════════════════════════
# Secrets (encrypt / decrypt)
# ════════════════════════════════════════════════════════════════════════

class TestSecrets:
    def _fernet_key(self) -> str:
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode()

    def test_save_and_load_roundtrip(self, tmp_path):
        from src.auth.secrets import load_user_secrets, save_user_secrets

        master_key = self._fernet_key()
        secrets = {"TAVILY_API_KEY": "sk-test-abc", "OPENAI_API_KEY": "sk-open-xyz"}

        with patch.dict(os.environ, {"SECRETS_MASTER_KEY": master_key}):
            with patch("src.auth.secrets.get_paths") as mock_paths:
                secrets_file = tmp_path / "secrets.enc"
                mock_paths.return_value.user_secrets_file.return_value = secrets_file

                save_user_secrets("user-1", secrets)
                assert secrets_file.exists()
                assert secrets_file.read_bytes() != b""  # file is encrypted

                loaded = load_user_secrets("user-1")

        assert loaded == secrets

    def test_load_returns_empty_when_file_missing(self, tmp_path):
        from src.auth.secrets import load_user_secrets

        master_key = self._fernet_key()
        with patch.dict(os.environ, {"SECRETS_MASTER_KEY": master_key}):
            with patch("src.auth.secrets.get_paths") as mock_paths:
                mock_paths.return_value.user_secrets_file.return_value = tmp_path / "missing.enc"
                loaded = load_user_secrets("user-nope")

        assert loaded == {}

    def test_resolve_api_key_user_priority(self, tmp_path):
        """User secret takes priority over platform env var."""
        from src.auth.secrets import resolve_api_key

        master_key = self._fernet_key()
        with patch.dict(os.environ, {
            "SECRETS_MASTER_KEY": master_key,
            "TAVILY_API_KEY": "platform-key",
        }):
            with patch("src.auth.secrets.load_user_secrets", return_value={"TAVILY_API_KEY": "user-key"}):
                result = resolve_api_key("TAVILY_API_KEY", "user-1")

        assert result == "user-key"

    def test_resolve_api_key_falls_back_to_env(self):
        """Falls back to platform env var when user has no secret."""
        from src.auth.secrets import resolve_api_key

        with patch.dict(os.environ, {"TAVILY_API_KEY": "platform-fallback"}):
            with patch("src.auth.secrets.load_user_secrets", return_value={}):
                result = resolve_api_key("TAVILY_API_KEY", "user-1")

        assert result == "platform-fallback"

    def test_resolve_api_key_none_user(self):
        """No user_id → skips user secrets, returns platform key."""
        from src.auth.secrets import resolve_api_key

        with patch.dict(os.environ, {"TAVILY_API_KEY": "platform-only"}):
            result = resolve_api_key("TAVILY_API_KEY", None)

        assert result == "platform-only"


# ════════════════════════════════════════════════════════════════════════
# Paths — user namespace safety
# ════════════════════════════════════════════════════════════════════════

class TestUserPaths:
    def _paths(self, tmp_path):
        from src.config.paths import Paths
        return Paths(str(tmp_path))

    def test_user_root_creates_correct_path(self, tmp_path):
        p = self._paths(tmp_path)
        assert p.user_root("alice") == tmp_path / "users" / "alice"

    def test_user_secrets_file_path(self, tmp_path):
        p = self._paths(tmp_path)
        assert p.user_secrets_file("alice") == tmp_path / "users" / "alice" / "secrets.enc"

    def test_user_skills_dir_path(self, tmp_path):
        p = self._paths(tmp_path)
        assert p.user_skills_dir("alice") == tmp_path / "users" / "alice" / "skills" / "custom"

    def test_unsafe_user_id_raises(self, tmp_path):
        p = self._paths(tmp_path)
        with pytest.raises(ValueError, match="user_id"):
            p.user_root("../../etc/passwd")

    def test_user_id_with_hyphen_allowed(self, tmp_path):
        p = self._paths(tmp_path)
        assert p.user_root("user-123") == tmp_path / "users" / "user-123"

    def test_user_id_with_underscore_allowed(self, tmp_path):
        p = self._paths(tmp_path)
        assert p.user_root("user_abc") == tmp_path / "users" / "user_abc"

    def test_user_id_with_special_chars_raises(self, tmp_path):
        p = self._paths(tmp_path)
        for bad in ["user@example.com", "user/name", "user name", "user;cmd"]:
            with pytest.raises(ValueError):
                p.user_root(bad)


# ════════════════════════════════════════════════════════════════════════
# Rate limiting — no-op when Redis absent
# ════════════════════════════════════════════════════════════════════════

class TestRateLimit:
    def test_no_op_when_redis_uri_not_set(self):
        """check_rate_limit must not raise when REDIS_URI is not configured."""
        import asyncio
        from src.auth import rate_limit

        # Reset cached client state
        rate_limit._redis_client = None
        rate_limit._redis_available = None

        env = {k: v for k, v in os.environ.items() if k != "REDIS_URI"}
        with patch.dict(os.environ, env, clear=True):
            asyncio.run(rate_limit.check_rate_limit("user-1"))  # must not raise

    def test_raises_429_when_limit_exceeded(self):
        """When Redis is available and count exceeds limit, raise 429."""
        import asyncio
        from fastapi import HTTPException
        from src.auth import rate_limit

        mock_redis = MagicMock()
        mock_redis.incr.return_value = 101  # over limit

        rate_limit._redis_client = mock_redis
        rate_limit._redis_available = True

        with patch.dict(os.environ, {"RATE_LIMIT_REQUESTS": "100", "RATE_LIMIT_WINDOW": "60"}):
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(rate_limit.check_rate_limit("user-heavy"))

        assert exc_info.value.status_code == 429

    def test_allows_request_under_limit(self):
        """Requests under the limit must pass through."""
        import asyncio
        from src.auth import rate_limit

        mock_redis = MagicMock()
        mock_redis.incr.return_value = 50

        rate_limit._redis_client = mock_redis
        rate_limit._redis_available = True

        with patch.dict(os.environ, {"RATE_LIMIT_REQUESTS": "100", "RATE_LIMIT_WINDOW": "60"}):
            asyncio.run(rate_limit.check_rate_limit("user-ok"))  # must not raise


# ════════════════════════════════════════════════════════════════════════
# AuthMiddleware (gateway_middleware) — request flow
# ════════════════════════════════════════════════════════════════════════

class TestAuthMiddleware:
    def _make_request(self, path: str = "/api/memory", auth_header: str | None = None):
        request = MagicMock()
        request.url.path = path
        headers = {}
        if auth_header:
            headers["Authorization"] = auth_header
        request.headers.get = lambda key, default="": headers.get(key, default)
        return request

    def test_skip_paths_set_default_user(self):
        """Health/docs paths bypass auth and get user_id = 'default'."""
        import asyncio
        from src.auth.gateway_middleware import AuthMiddleware

        middleware = AuthMiddleware(app=MagicMock())
        for path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            request = self._make_request(path)
            call_next = AsyncMock(return_value=MagicMock(status_code=200))

            async def run():
                return await middleware.dispatch(request, call_next)

            asyncio.run(run())
            assert request.state.user_id == "default"

    def test_missing_bearer_returns_401(self):
        import asyncio
        from src.auth.gateway_middleware import AuthMiddleware

        middleware = AuthMiddleware(app=MagicMock())
        request = self._make_request("/api/memory")  # no auth header

        async def run():
            return await middleware.dispatch(request, AsyncMock())

        response = asyncio.run(run())
        assert response.status_code == 401

    def test_valid_token_sets_user_id(self):
        import asyncio
        import jwt
        from src.auth.gateway_middleware import AuthMiddleware

        token = jwt.encode({"sub": "user-bob"}, "secret123", algorithm="HS256")
        middleware = AuthMiddleware(app=MagicMock())
        request = self._make_request("/api/memory", f"Bearer {token}")
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        with patch.dict(os.environ, {"JWT_SECRET_KEY": "secret123", "AUTH_ENABLED": "true"}):
            with patch("src.auth.gateway_middleware.check_rate_limit", AsyncMock()):
                async def run():
                    return await middleware.dispatch(request, call_next)

                asyncio.run(run())

        assert request.state.user_id == "user-bob"


# Allow running directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
