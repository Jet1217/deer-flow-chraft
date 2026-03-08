import logging
import os

from langchain.tools import BaseTool

from src.config import get_app_config
from src.reflection import resolve_variable
from src.tools.builtins import ask_clarification_tool, present_file_tool, task_tool, view_image_tool

logger = logging.getLogger(__name__)

BUILTIN_TOOLS = [
    present_file_tool,
    ask_clarification_tool,
]

SUBAGENT_TOOLS = [
    task_tool,
    # task_status_tool is no longer exposed to LLM (backend handles polling internally)
]

# Per-user tool instance cache: (user_id, frozenset(groups), include_mcp, subagent_enabled) -> tools
_user_tool_cache: dict[str, list[BaseTool]] = {}


def get_available_tools(
    groups: list[str] | None = None,
    include_mcp: bool = True,
    model_name: str | None = None,
    subagent_enabled: bool = False,
    user_id: str | None = None,
) -> list[BaseTool]:
    """Get all available tools from config.

    Note: MCP tools should be initialized at application startup using
    `initialize_mcp_tools()` from src.mcp module.

    Args:
        groups: Optional list of tool groups to filter by.
        include_mcp: Whether to include tools from MCP servers (default: True).
        model_name: Optional model name to determine if vision tools should be included.
        subagent_enabled: Whether to include subagent tools (task, task_status).
        user_id: Authenticated user ID for per-user key resolution and MCP isolation.

    Returns:
        List of available tools.
    """
    config = get_app_config()

    # Load user secrets for key resolution (user key overrides platform env var)
    user_secrets: dict[str, str] = {}
    if user_id:
        try:
            from src.auth.secrets import load_user_secrets

            user_secrets = load_user_secrets(user_id)
        except Exception as e:
            logger.warning(f"Failed to load user secrets for {user_id}: {e}")

    # Build per-tool list; inject user key into environment for tools that declare key_env_var
    loaded_tools: list[BaseTool] = []
    for tool_config in config.tools:
        if groups is not None and tool_config.group not in groups:
            continue

        # Temporarily override env var with user's key so tool picks it up at instantiation
        key_env_var = getattr(tool_config, "key_env_var", None)
        if key_env_var and key_env_var in user_secrets:
            original = os.environ.get(key_env_var)
            os.environ[key_env_var] = user_secrets[key_env_var]
            try:
                tool = resolve_variable(tool_config.use, BaseTool)
            finally:
                if original is None:
                    os.environ.pop(key_env_var, None)
                else:
                    os.environ[key_env_var] = original
        else:
            tool = resolve_variable(tool_config.use, BaseTool)

        loaded_tools.append(tool)

    # Get per-user MCP tools if enabled
    # NOTE: We pass user_id so each user gets tools loaded from their own extensions_config.json,
    # which may contain different MCP server credentials.
    mcp_tools: list[BaseTool] = []
    if include_mcp:
        try:
            from src.mcp.cache import get_user_mcp_tools

            mcp_tools = get_user_mcp_tools(user_id)
            if mcp_tools:
                logger.info(f"Using {len(mcp_tools)} MCP tool(s) for user={user_id or 'global'}")
        except ImportError:
            logger.warning("MCP module not available. Install 'langchain-mcp-adapters' package to enable MCP tools.")
        except Exception as e:
            logger.error(f"Failed to get MCP tools: {e}")

    # Conditionally add tools based on config
    builtin_tools = BUILTIN_TOOLS.copy()

    # Add subagent tools only if enabled via runtime parameter
    if subagent_enabled:
        builtin_tools.extend(SUBAGENT_TOOLS)
        logger.info("Including subagent tools (task)")

    # If no model_name specified, use the first model (default)
    if model_name is None and config.models:
        model_name = config.models[0].name

    # Add view_image_tool only if the model supports vision
    model_config = config.get_model_config(model_name) if model_name else None
    if model_config is not None and model_config.supports_vision:
        builtin_tools.append(view_image_tool)
        logger.info(f"Including view_image_tool for model '{model_name}' (supports_vision=True)")

    return loaded_tools + builtin_tools + mcp_tools
