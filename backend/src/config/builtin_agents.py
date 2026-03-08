"""Built-in agent definitions.

Built-in agents are shipped with the application and cannot be modified or
deleted by users.  They appear in the agents list alongside custom agents but
are distinguished by ``builtin=True`` in the API response.
"""

from src.config.agents_config import AgentConfig

# ---------------------------------------------------------------------------
# Built-in agent registry
# ---------------------------------------------------------------------------
# Each entry is a plain AgentConfig.  The ``soul`` field (SOUL.md content)
# can be added to the AgentResponse at the router level if needed, but is
# omitted here because built-in agents use the default lead-agent prompt.
# ---------------------------------------------------------------------------

BUILTIN_AGENTS: list[AgentConfig] = [
    AgentConfig(
        name="deep-research",
        description="Conducts deep, multi-step web research with synthesis and citations.",
        model=None,
        tool_groups=None,
    ),
    AgentConfig(
        name="data-analyst",
        description="Analyzes datasets, builds charts, and delivers data-driven insights.",
        model=None,
        tool_groups=None,
    ),
]

# Fast lookup by name
_BUILTIN_AGENT_NAMES: frozenset[str] = frozenset(a.name for a in BUILTIN_AGENTS)


def is_builtin_agent(name: str) -> bool:
    """Return True if *name* refers to a built-in agent."""
    return name.lower() in _BUILTIN_AGENT_NAMES
