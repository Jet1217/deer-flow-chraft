import logging

import yaml
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from src.config.agents_config import AGENT_NAME_PATTERN, _is_user_scoped
from src.config.builtin_agents import is_builtin_agent
from src.config.paths import get_paths

logger = logging.getLogger(__name__)


def _extract_user_id(runtime: ToolRuntime) -> str | None:
    """Extract the authenticated user_id from the LangGraph run config."""
    cfg = runtime.config or {}
    meta = cfg.get("metadata", {})
    configurable = cfg.get("configurable", {})
    _auth_user = configurable.get("langgraph_auth_user") or cfg.get("configuration", {}).get("langgraph_auth_user")
    candidate = (
        meta.get("owner")
        or configurable.get("user_id")
        or configurable.get("langgraph_auth_user_id")
        or (getattr(_auth_user, "identity", None) if _auth_user is not None else None)
        or (isinstance(_auth_user, dict) and _auth_user.get("identity"))
    )
    return candidate if isinstance(candidate, str) and candidate.strip() else None


@tool
def setup_agent(
    soul: str,
    description: str,
    runtime: ToolRuntime,
    agent_name: str | None = None,
) -> Command:
    """Setup (create or update) a custom DeerFlow agent.

    Can be called from the bootstrap onboarding flow OR from a regular chat when
    the user wants to create a new agent via the agent-creator skill.

    Args:
        soul: Full SOUL.md content defining the agent's personality and behavior.
        description: One-line description of what the agent does.
        agent_name: The agent's unique identifier (hyphen-case, e.g. "aria" or "code-reviewer").
            Falls back to the agent_name injected via context (bootstrap flow).
            Required when called outside the bootstrap flow (agent-creator skill).
    """

    # Prefer explicit parameter; fall back to context injection (bootstrap flow)
    resolved_name: str | None = agent_name or runtime.context.get("agent_name")
    user_id: str | None = _extract_user_id(runtime)

    if not resolved_name:
        return Command(update={"messages": [ToolMessage(content="Error: agent_name is required.", tool_call_id=runtime.tool_call_id)]})

    if not AGENT_NAME_PATTERN.match(resolved_name):
        return Command(update={"messages": [ToolMessage(
            content=f"Error: invalid agent name '{resolved_name}'. Use only letters, digits, and hyphens (e.g. 'my-agent').",
            tool_call_id=runtime.tool_call_id,
        )]})

    if is_builtin_agent(resolved_name):
        return Command(update={"messages": [ToolMessage(
            content=f"Error: '{resolved_name}' is a built-in agent and cannot be created or modified.",
            tool_call_id=runtime.tool_call_id,
        )]})

    try:
        paths = get_paths()
        if _is_user_scoped(user_id):
            agent_dir = paths.user_agent_dir(user_id, resolved_name)
        else:
            agent_dir = paths.agent_dir(resolved_name)

        is_update = agent_dir.exists()
        agent_dir.mkdir(parents=True, exist_ok=True)

        config_data: dict = {"name": resolved_name}
        if description:
            config_data["description"] = description

        config_file = agent_dir / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

        soul_file = agent_dir / "SOUL.md"
        soul_file.write_text(soul, encoding="utf-8")

        action = "updated" if is_update else "created"
        logger.info(f"[setup_agent] Agent '{resolved_name}' {action} at {agent_dir}")
        return Command(
            update={
                "created_agent_name": resolved_name,
                "messages": [ToolMessage(
                    content=f"Agent '{resolved_name}' {action} successfully!",
                    tool_call_id=runtime.tool_call_id,
                )],
            }
        )

    except Exception as e:
        # Only clean up a newly created directory; never remove a pre-existing agent on failure.
        if not is_update:
            import shutil
            agent_dir_check = (paths.user_agent_dir(user_id, resolved_name) if _is_user_scoped(user_id) else paths.agent_dir(resolved_name))
            if agent_dir_check.exists():
                shutil.rmtree(agent_dir_check)
        logger.error(f"[setup_agent] Failed to {'update' if is_update else 'create'} agent '{resolved_name}': {e}", exc_info=True)
        return Command(update={"messages": [ToolMessage(content=f"Error: {e}", tool_call_id=runtime.tool_call_id)]})
