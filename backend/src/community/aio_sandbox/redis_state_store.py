"""Redis-based sandbox state store for multi-node deployments.

Replaces FileSandboxStateStore when multiple Gateway/LangGraph instances
run on different machines sharing no common filesystem.  All sandbox
metadata is stored in Redis with a configurable TTL.

Usage (in aio_sandbox_provider.py or config):
    from src.community.aio_sandbox.redis_state_store import RedisSandboxStateStore

    store = RedisSandboxStateStore(
        redis_url=os.environ["REDIS_URI"],
        ttl=3600,   # sandbox mapping expires after 1 hour of inactivity
    )

Prerequisites:
    pip install redis  (or add redis to pyproject.toml)

The lock implementation uses the ``redis-py`` distributed lock (Redlock-style),
which is safe across multiple processes and hosts.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Generator
from contextlib import contextmanager

from .sandbox_info import SandboxInfo
from .state_store import SandboxStateStore

logger = logging.getLogger(__name__)

_DEFAULT_TTL = int(os.getenv("SANDBOX_STATE_TTL", "3600"))  # 1 hour
_LOCK_TIMEOUT = 30   # seconds to wait for lock before giving up
_LOCK_EXPIRE = 30    # seconds before lock auto-releases (dead-process safety)

_KEY_PREFIX = "sandbox:state:"
_LOCK_PREFIX = "sandbox:lock:"


class RedisSandboxStateStore(SandboxStateStore):
    """Redis-backed sandbox state store.

    Thread_id → sandbox metadata is stored as JSON strings in Redis with a TTL.
    Cross-process locking uses redis-py's built-in Lock primitive (Redlock-style).

    State key:  ``sandbox:state:{thread_id}``  TTL = self._ttl seconds
    Lock key:   ``sandbox:lock:{thread_id}``   auto-expires after _LOCK_EXPIRE s
    """

    def __init__(self, redis_url: str, ttl: int = _DEFAULT_TTL):
        """Initialize the Redis state store.

        Args:
            redis_url: Redis connection URL, e.g. ``redis://redis:6379``.
            ttl: Time-to-live for sandbox state entries in seconds.
                 The TTL is refreshed on every save().
        """
        import redis

        self._redis = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5)
        self._ttl = ttl
        logger.info(f"RedisSandboxStateStore initialized (url={redis_url}, ttl={ttl}s)")

    def save(self, thread_id: str, info: SandboxInfo) -> None:
        key = _KEY_PREFIX + thread_id
        try:
            self._redis.setex(key, self._ttl, json.dumps(info.to_dict()))
            logger.debug(f"Saved sandbox state for thread={thread_id}: {info.sandbox_id}")
        except Exception as e:
            logger.warning(f"Redis save failed for thread={thread_id}: {e}")

    def load(self, thread_id: str) -> SandboxInfo | None:
        key = _KEY_PREFIX + thread_id
        try:
            raw = self._redis.get(key)
            if raw is None:
                return None
            data = json.loads(raw)
            return SandboxInfo.from_dict(data)
        except Exception as e:
            logger.warning(f"Redis load failed for thread={thread_id}: {e}")
            return None

    def remove(self, thread_id: str) -> None:
        key = _KEY_PREFIX + thread_id
        try:
            self._redis.delete(key)
            logger.debug(f"Removed sandbox state for thread={thread_id}")
        except Exception as e:
            logger.warning(f"Redis remove failed for thread={thread_id}: {e}")

    @contextmanager
    def lock(self, thread_id: str) -> Generator[None, None, None]:
        """Acquire a distributed Redis lock for a thread's sandbox operations.

        Uses redis-py's built-in Lock (Redlock algorithm variant).
        Blocks for up to _LOCK_TIMEOUT seconds; raises RuntimeError if timeout.
        Auto-releases after _LOCK_EXPIRE seconds to prevent dead locks.
        """
        lock_key = _LOCK_PREFIX + thread_id
        lock = self._redis.lock(
            lock_key,
            timeout=_LOCK_EXPIRE,        # auto-release after this many seconds
            blocking_timeout=_LOCK_TIMEOUT,
        )
        acquired = lock.acquire()
        if not acquired:
            raise RuntimeError(
                f"Could not acquire sandbox lock for thread={thread_id} "
                f"after {_LOCK_TIMEOUT}s. Another process may be stuck."
            )
        try:
            yield
        finally:
            try:
                lock.release()
            except Exception:
                pass  # Lock may have already expired — that's acceptable
