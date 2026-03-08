"""Configuration and loaders for custom agents."""

import logging
import re
from typing import Any

import yaml
from pydantic import BaseModel

from src.config.paths import get_paths

logger = logging.getLogger(__name__)

SOUL_FILENAME = "SOUL.md"
AGENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")


class AgentConfig(BaseModel):
    """Configuration for a custom agent."""

    name: str
    description: str = ""
    model: str | None = None
    tool_groups: list[str] | None = None


def _is_user_scoped(user_id: str | None) -> bool:
    """Return True when the request should use the user-scoped agents directory.

    user_id=None or user_id="default" maps to the global agents directory
    (backward-compatible path for AUTH_ENABLED=false deployments).
    """
    return bool(user_id) and user_id != "default"


def load_agent_config(name: str | None, user_id: str | None = None) -> AgentConfig | None:
    """Load the custom or default agent's config from its directory.

    Args:
        name: The agent name.
        user_id: When provided and not "default", load from the user's private agents dir.

    Returns:
        AgentConfig instance.

    Raises:
        FileNotFoundError: If the agent directory or config.yaml does not exist.
        ValueError: If config.yaml cannot be parsed.
    """
    if name is None:
        return None

    if not AGENT_NAME_PATTERN.match(name):
        raise ValueError(f"Invalid agent name '{name}'. Must match pattern: {AGENT_NAME_PATTERN.pattern}")

    if _is_user_scoped(user_id):
        agent_dir = get_paths().user_agent_dir(user_id, name)
    else:
        agent_dir = get_paths().agent_dir(name)

    config_file = agent_dir / "config.yaml"

    if not agent_dir.exists():
        raise FileNotFoundError(f"Agent directory not found: {agent_dir}")

    if not config_file.exists():
        raise FileNotFoundError(f"Agent config not found: {config_file}")

    try:
        with open(config_file, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse agent config {config_file}: {e}") from e

    # Ensure name is set from directory name if not in file
    if "name" not in data:
        data["name"] = name

    # Strip unknown fields before passing to Pydantic (e.g. legacy prompt_file)
    known_fields = set(AgentConfig.model_fields.keys())
    data = {k: v for k, v in data.items() if k in known_fields}

    return AgentConfig(**data)


def load_agent_soul(agent_name: str | None, user_id: str | None = None) -> str | None:
    """Read the SOUL.md file for a custom agent, if it exists.

    SOUL.md defines the agent's personality, values, and behavioral guardrails.
    It is injected into the lead agent's system prompt as additional context.

    Args:
        agent_name: The name of the agent or None for the default agent.
        user_id: When provided and not "default", look in the user's private agents dir.

    Returns:
        The SOUL.md content as a string, or None if the file does not exist.
    """
    if agent_name and _is_user_scoped(user_id):
        agent_dir = get_paths().user_agent_dir(user_id, agent_name)
    elif agent_name:
        agent_dir = get_paths().agent_dir(agent_name)
    else:
        agent_dir = get_paths().base_dir

    soul_path = agent_dir / SOUL_FILENAME
    if not soul_path.exists():
        return None
    content = soul_path.read_text(encoding="utf-8").strip()
    return content or None


def list_custom_agents(user_id: str | None = None) -> list[AgentConfig]:
    """Scan the agents directory and return all valid custom agents.

    Args:
        user_id: When provided and not "default", scan the user's private agents dir.

    Returns:
        List of AgentConfig for each valid agent directory found.
    """
    if _is_user_scoped(user_id):
        agents_dir = get_paths().user_agents_dir(user_id)
    else:
        agents_dir = get_paths().agents_dir

    if not agents_dir.exists():
        return []

    agents: list[AgentConfig] = []

    for entry in sorted(agents_dir.iterdir()):
        if not entry.is_dir():
            continue

        config_file = entry / "config.yaml"
        if not config_file.exists():
            logger.debug(f"Skipping {entry.name}: no config.yaml")
            continue

        try:
            agent_cfg = load_agent_config(entry.name, user_id=user_id)
            agents.append(agent_cfg)
        except Exception as e:
            logger.warning(f"Skipping agent '{entry.name}': {e}")

    return agents
