"""Per-user Redis rate limiting.

Counts requests in a sliding fixed window per user_id. When REDIS_URI is not
configured the rate limiter is a no-op, which preserves backward compatibility
for single-node development deployments.
"""

import logging
import os
import time

from fastapi import HTTPException

logger = logging.getLogger(__name__)

_redis_client = None
_redis_available: bool | None = None  # None = not yet probed


def _get_redis():
    """Return a Redis client, or None when REDIS_URI is not configured."""
    global _redis_client, _redis_available

    if _redis_available is False:
        return None
    if _redis_client is not None:
        return _redis_client

    redis_uri = os.environ.get("REDIS_URI")
    if not redis_uri:
        _redis_available = False
        return None

    try:
        import redis

        _redis_client = redis.from_url(redis_uri, decode_responses=True, socket_connect_timeout=2)
        _redis_client.ping()  # Fail fast if unreachable
        _redis_available = True
        logger.info("Redis rate limiter connected")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis unavailable, rate limiting disabled: {e}")
        _redis_available = False
        return None


async def check_rate_limit(user_id: str) -> None:
    """Enforce per-user rate limit using a fixed sliding window in Redis.

    Reads RATE_LIMIT_REQUESTS (default 100) and RATE_LIMIT_WINDOW (default 60s)
    from the environment. Raises HTTP 429 when the limit is exceeded.

    When Redis is not configured this is a no-op.

    Args:
        user_id: The authenticated user identifier.

    Raises:
        HTTPException: 429 Too Many Requests when limit exceeded.
    """
    r = _get_redis()
    if r is None:
        return  # Rate limiting disabled — development / single-node mode

    window = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    limit = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    bucket = int(time.time() // window)
    key = f"rl:{user_id}:{bucket}"

    try:
        count = r.incr(key)
        if count == 1:
            r.expire(key, window)
        if count > limit:
            logger.warning(f"Rate limit exceeded for user={user_id}: {count}/{limit} in window={window}s")
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please slow down.")
    except HTTPException:
        raise
    except Exception as e:
        # Redis errors must never block legitimate traffic
        logger.error(f"Rate limit check failed for user={user_id}: {e}")
