"""Per-user MCP tools cache.

Each user may have a different extensions_config.json with different MCP server
credentials, so tools are cached per user_id rather than as a global singleton.
"""

import asyncio
import logging

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

# Per-user cache: user_id (or "default") -> list of MCP tools
_mcp_tools_cache: dict[str, list[BaseTool]] = {}
_initialization_lock = asyncio.Lock()


def _get_extensions_config(user_id: str | None):
    """Load the appropriate extensions config for a user."""
    from src.config.extensions_config import ExtensionsConfig

    if user_id and user_id != "default":
        try:
            from src.config.paths import get_paths

            user_cfg_file = get_paths().user_extensions_config_file(user_id)
            if user_cfg_file.exists():
                return ExtensionsConfig.from_file(user_cfg_file)
        except Exception as e:
            logger.warning(f"Failed to load user extensions config for {user_id}: {e}")

    return ExtensionsConfig.from_file()


async def _initialize_user_mcp_tools(user_id: str | None) -> list[BaseTool]:
    """Initialize and cache MCP tools for a specific user."""
    cache_key = user_id or "default"

    async with _initialization_lock:
        # Double-check after acquiring lock
        if cache_key in _mcp_tools_cache:
            return _mcp_tools_cache[cache_key]

        from src.mcp.tools import get_mcp_tools

        extensions_config = _get_extensions_config(user_id)
        enabled_servers = extensions_config.get_enabled_mcp_servers()

        logger.info(f"Initializing MCP tools for user={cache_key}: {len(enabled_servers)} enabled server(s)")
        tools = await get_mcp_tools(mcp_servers=enabled_servers)
        _mcp_tools_cache[cache_key] = tools
        logger.info(f"MCP tools initialized for user={cache_key}: {len(tools)} tool(s)")
        return tools


def get_user_mcp_tools(user_id: str | None) -> list[BaseTool]:
    """Get MCP tools for a specific user with lazy per-user initialization.

    Each user's tools are loaded from their own extensions_config.json, which
    may contain different MCP server definitions and credentials.

    Args:
        user_id: The authenticated user ID, or None for the global/default config.

    Returns:
        List of MCP tools for this user.
    """
    cache_key = user_id or "default"

    if cache_key in _mcp_tools_cache:
        return _mcp_tools_cache[cache_key]

    # Check if there are any enabled MCP servers before initializing
    try:
        extensions_config = _get_extensions_config(user_id)
        if not extensions_config.get_enabled_mcp_servers():
            _mcp_tools_cache[cache_key] = []
            return []
    except Exception as e:
        logger.error(f"Failed to check MCP config for user={cache_key}: {e}")
        return []

    # Initialize asynchronously
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _initialize_user_mcp_tools(user_id))
                future.result()
        else:
            loop.run_until_complete(_initialize_user_mcp_tools(user_id))
    except RuntimeError:
        asyncio.run(_initialize_user_mcp_tools(user_id))
    except Exception as e:
        logger.error(f"Failed to initialize MCP tools for user={cache_key}: {e}")
        return []

    return _mcp_tools_cache.get(cache_key, [])


# Backwards-compatible alias used by existing callers (e.g. tools.py before this refactor)
def get_cached_mcp_tools() -> list[BaseTool]:
    """Get globally cached MCP tools (backwards compatible, uses default/global config)."""
    return get_user_mcp_tools(None)


async def initialize_mcp_tools() -> list[BaseTool]:
    """Initialize global (default) MCP tools. Called at application startup."""
    return await _initialize_user_mcp_tools(None)


def reset_mcp_tools_cache(user_id: str | None = None) -> None:
    """Reset the MCP tools cache for a specific user, or all users if user_id is None."""
    if user_id is None:
        _mcp_tools_cache.clear()
        logger.info("MCP tools cache reset (all users)")
    else:
        cache_key = user_id or "default"
        _mcp_tools_cache.pop(cache_key, None)
        logger.info(f"MCP tools cache reset for user={cache_key}")
