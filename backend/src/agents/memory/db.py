"""PostgreSQL backend for user memory and thread ownership.

Falls back gracefully (returns None / True) when POSTGRES_URI is not configured,
allowing the rest of the system to use file-based storage in development mode.
"""

import json
import logging
import os
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)


def _get_postgres_uri() -> str | None:
    return os.environ.get("POSTGRES_URI", "").strip() or None


@contextmanager
def _connection() -> Generator:
    """Open a synchronous psycopg3 connection (context manager).

    Yields None when POSTGRES_URI is not configured.
    """
    uri = _get_postgres_uri()
    if not uri:
        yield None
        return

    try:
        import psycopg  # psycopg[binary]>=3.2.0
    except ImportError:
        logger.warning("psycopg not installed; falling back to file-based storage")
        yield None
        return

    try:
        with psycopg.connect(uri) as conn:
            yield conn
    except Exception as exc:
        logger.error(f"PostgreSQL connection failed: {exc}; falling back to file-based storage")
        yield None


def ensure_schema() -> None:
    """Create required tables if they don't exist (called at startup)."""
    with _connection() as conn:
        if conn is None:
            return
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_memory (
                    user_id    TEXT        NOT NULL,
                    agent_name TEXT        NOT NULL DEFAULT '',
                    data       JSONB       NOT NULL DEFAULT '{}',
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (user_id, agent_name)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS thread_ownership (
                    thread_id  TEXT        PRIMARY KEY,
                    user_id    TEXT        NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        conn.commit()
        logger.info("PostgreSQL schema verified/created")


def get_memory(user_id: str, agent_name: str = "") -> dict | None:
    """Fetch memory data for a user from PostgreSQL.

    Returns:
        dict with memory data, empty dict if no row yet, or None if DB unavailable.
    """
    with _connection() as conn:
        if conn is None:
            return None
        with conn.cursor() as cur:
            cur.execute(
                "SELECT data FROM user_memory WHERE user_id=%s AND agent_name=%s",
                (user_id, agent_name),
            )
            row = cur.fetchone()
            return dict(row[0]) if row else {}


def save_memory(user_id: str, data: dict, agent_name: str = "") -> bool:
    """Upsert memory data for a user.

    Returns:
        True on success, False if DB unavailable.
    """
    with _connection() as conn:
        if conn is None:
            return False
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_memory (user_id, agent_name, data, updated_at)
                VALUES (%s, %s, %s::jsonb, NOW())
                ON CONFLICT (user_id, agent_name)
                DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
                """,
                (user_id, agent_name, json.dumps(data)),
            )
        conn.commit()
        return True


def claim_thread_ownership(thread_id: str, user_id: str) -> bool:
    """Record that user_id owns thread_id (no-op if already claimed).

    Returns:
        True on success, False if DB unavailable.
    """
    with _connection() as conn:
        if conn is None:
            return False
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO thread_ownership (thread_id, user_id)
                VALUES (%s, %s)
                ON CONFLICT (thread_id) DO NOTHING
                """,
                (thread_id, user_id),
            )
        conn.commit()
        return True


def verify_thread_owner(thread_id: str, user_id: str) -> bool:
    """Check whether user_id owns thread_id.

    Returns True when:
    - DB is unavailable (backward compat)
    - Thread has no owner record yet (backward compat)
    - The recorded owner matches user_id
    """
    with _connection() as conn:
        if conn is None:
            return True  # fallback: no restriction
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM thread_ownership WHERE thread_id=%s",
                (thread_id,),
            )
            row = cur.fetchone()
            if row is None:
                return True  # not yet claimed → allow (backward compat)
            return row[0] == user_id
