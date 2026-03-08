"""Memory updater for reading, writing, and updating memory data."""

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from src.agents.memory.prompt import (
    MEMORY_UPDATE_PROMPT,
    format_conversation_for_update,
)
from src.config.memory_config import get_memory_config
from src.config.paths import get_paths
from src.models import create_chat_model

# Cache TTL in seconds; after expiry the next read goes to DB (or re-reads file).
_CACHE_TTL = 60.0

# Cache key: (user_id, agent_name) → (data, cached_at)
_memory_cache: dict[tuple[str | None, str | None], tuple[dict[str, Any], float]] = {}


def _cache_key(user_id: str | None, agent_name: str | None) -> tuple:
    return (user_id, agent_name)


def _get_memory_file_path(user_id: str | None = None, agent_name: str | None = None) -> Path:
    """Return the file path for the given user/agent's memory.

    Priority:
    1. Per-user file when user_id is a real (non-default) user
    2. Per-agent file when agent_name is provided
    3. Global fallback (config.storage_path or paths.memory_file)
    """
    from src.config.agents_config import _is_user_scoped

    if _is_user_scoped(user_id):
        return get_paths().user_memory_file(user_id)  # type: ignore[arg-type]

    if agent_name is not None:
        return get_paths().agent_memory_file(agent_name)

    config = get_memory_config()
    if config.storage_path:
        p = Path(config.storage_path)
        return p if p.is_absolute() else get_paths().base_dir / p
    return get_paths().memory_file


def _create_empty_memory() -> dict[str, Any]:
    """Create an empty memory structure."""
    return {
        "version": "1.0",
        "lastUpdated": datetime.utcnow().isoformat() + "Z",
        "user": {
            "workContext": {"summary": "", "updatedAt": ""},
            "personalContext": {"summary": "", "updatedAt": ""},
            "topOfMind": {"summary": "", "updatedAt": ""},
        },
        "history": {
            "recentMonths": {"summary": "", "updatedAt": ""},
            "earlierContext": {"summary": "", "updatedAt": ""},
            "longTermBackground": {"summary": "", "updatedAt": ""},
        },
        "facts": [],
    }


def _load_memory_from_file(user_id: str | None = None, agent_name: str | None = None) -> dict[str, Any]:
    file_path = _get_memory_file_path(user_id=user_id, agent_name=agent_name)
    if not file_path.exists():
        return _create_empty_memory()
    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Failed to load memory file: {e}")
        return _create_empty_memory()


def _save_memory_to_file(memory_data: dict[str, Any], user_id: str | None = None, agent_name: str | None = None) -> bool:
    file_path = _get_memory_file_path(user_id=user_id, agent_name=agent_name)
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        memory_data["lastUpdated"] = datetime.utcnow().isoformat() + "Z"
        temp_path = file_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(memory_data, f, indent=2, ensure_ascii=False)
        temp_path.replace(file_path)
        print(f"Memory saved to {file_path}")
        return True
    except OSError as e:
        print(f"Failed to save memory file: {e}")
        return False


def get_memory_data(agent_name: str | None = None, user_id: str | None = None) -> dict[str, Any]:
    """Get memory data for a user/agent pair (TTL-cached).

    When POSTGRES_URI is configured and user_id is provided, reads from DB.
    Falls back to file-based storage otherwise.

    Args:
        agent_name: Per-agent memory key; None = global memory.
        user_id: The user ID; None = global/legacy mode.

    Returns:
        Memory data dictionary.
    """
    key = _cache_key(user_id, agent_name)
    cached = _memory_cache.get(key)
    now = time.time()

    if cached is not None and (now - cached[1]) < _CACHE_TTL:
        return cached[0]

    # Cache miss or expired → load fresh
    memory_data: dict[str, Any] | None = None

    if user_id is not None:
        from src.agents.memory.db import get_memory as db_get_memory
        memory_data = db_get_memory(user_id, agent_name or "")
        # None means DB unavailable; fall through to file
        # Empty dict from DB (no row yet) → use full empty structure
        if memory_data is not None and not memory_data.get("user") and not memory_data.get("history"):
            memory_data = _create_empty_memory()

    if memory_data is None:
        memory_data = _load_memory_from_file(user_id=user_id, agent_name=agent_name)

    _memory_cache[key] = (memory_data, now)
    return memory_data


def reload_memory_data(agent_name: str | None = None, user_id: str | None = None) -> dict[str, Any]:
    """Force-reload memory data, invalidating the cache entry."""
    key = _cache_key(user_id, agent_name)
    _memory_cache.pop(key, None)
    return get_memory_data(agent_name=agent_name, user_id=user_id)


class MemoryUpdater:
    """Updates memory using LLM based on conversation context."""

    def __init__(self, model_name: str | None = None):
        self._model_name = model_name

    def _get_model(self):
        config = get_memory_config()
        model_name = self._model_name or config.model_name
        return create_chat_model(name=model_name, thinking_enabled=False)

    def update_memory(
        self,
        messages: list[Any],
        thread_id: str | None = None,
        agent_name: str | None = None,
        user_id: str | None = None,
    ) -> bool:
        """Update memory based on conversation messages.

        Args:
            messages: List of conversation messages.
            thread_id: Optional thread ID for tracking.
            agent_name: Per-agent memory key; None = global.
            user_id: The user ID; None = global/legacy mode.

        Returns:
            True if update was successful, False otherwise.
        """
        config = get_memory_config()
        if not config.enabled:
            return False
        if not messages:
            return False

        try:
            current_memory = get_memory_data(agent_name=agent_name, user_id=user_id)
            conversation_text = format_conversation_for_update(messages)
            if not conversation_text.strip():
                return False

            prompt = MEMORY_UPDATE_PROMPT.format(
                current_memory=json.dumps(current_memory, indent=2),
                conversation=conversation_text,
            )

            model = self._get_model()
            response = model.invoke(prompt)
            response_text = str(response.content).strip()

            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            update_data = json.loads(response_text)
            updated_memory = self._apply_updates(current_memory, update_data, thread_id)

            return self._save_memory(updated_memory, agent_name=agent_name, user_id=user_id)

        except json.JSONDecodeError as e:
            print(f"Failed to parse LLM response for memory update: {e}")
            return False
        except Exception as e:
            print(f"Memory update failed: {e}")
            return False

    def _save_memory(
        self,
        memory_data: dict[str, Any],
        agent_name: str | None = None,
        user_id: str | None = None,
    ) -> bool:
        """Save memory to DB when available, otherwise fall back to file."""
        memory_data["lastUpdated"] = datetime.utcnow().isoformat() + "Z"

        saved_to_db = False
        if user_id is not None:
            from src.agents.memory.db import save_memory as db_save_memory
            saved_to_db = db_save_memory(user_id, memory_data, agent_name or "")

        if saved_to_db:
            # Update cache
            key = _cache_key(user_id, agent_name)
            _memory_cache[key] = (memory_data, time.time())
            return True

        return _save_memory_to_file(memory_data, user_id=user_id, agent_name=agent_name)

    def _apply_updates(
        self,
        current_memory: dict[str, Any],
        update_data: dict[str, Any],
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        config = get_memory_config()
        now = datetime.utcnow().isoformat() + "Z"

        user_updates = update_data.get("user", {})
        for section in ["workContext", "personalContext", "topOfMind"]:
            section_data = user_updates.get(section, {})
            if section_data.get("shouldUpdate") and section_data.get("summary"):
                current_memory["user"][section] = {
                    "summary": section_data["summary"],
                    "updatedAt": now,
                }

        history_updates = update_data.get("history", {})
        for section in ["recentMonths", "earlierContext", "longTermBackground"]:
            section_data = history_updates.get(section, {})
            if section_data.get("shouldUpdate") and section_data.get("summary"):
                current_memory["history"][section] = {
                    "summary": section_data["summary"],
                    "updatedAt": now,
                }

        facts_to_remove = set(update_data.get("factsToRemove", []))
        if facts_to_remove:
            current_memory["facts"] = [f for f in current_memory.get("facts", []) if f.get("id") not in facts_to_remove]

        new_facts = update_data.get("newFacts", [])
        for fact in new_facts:
            confidence = fact.get("confidence", 0.5)
            if confidence >= config.fact_confidence_threshold:
                fact_entry = {
                    "id": f"fact_{uuid.uuid4().hex[:8]}",
                    "content": fact.get("content", ""),
                    "category": fact.get("category", "context"),
                    "confidence": confidence,
                    "createdAt": now,
                    "source": thread_id or "unknown",
                }
                current_memory["facts"].append(fact_entry)

        if len(current_memory["facts"]) > config.max_facts:
            current_memory["facts"] = sorted(
                current_memory["facts"],
                key=lambda f: f.get("confidence", 0),
                reverse=True,
            )[: config.max_facts]

        return current_memory


def update_memory_from_conversation(
    messages: list[Any],
    thread_id: str | None = None,
    agent_name: str | None = None,
    user_id: str | None = None,
) -> bool:
    """Convenience function to update memory from a conversation."""
    updater = MemoryUpdater()
    return updater.update_memory(messages, thread_id, agent_name, user_id)
