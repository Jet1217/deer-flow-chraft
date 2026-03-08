from typing import NotRequired, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.runtime import Runtime

from src.agents.thread_state import SandboxState, ThreadDataState
from src.sandbox import get_sandbox_provider


class SandboxMiddlewareState(AgentState):
    """Compatible with the `ThreadState` schema."""

    sandbox: NotRequired[SandboxState | None]
    thread_data: NotRequired[ThreadDataState | None]


class SandboxMiddleware(AgentMiddleware[SandboxMiddlewareState]):
    """Create a sandbox environment and assign it to an agent.

    Lifecycle Management:
    - With lazy_init=True (default): Sandbox is acquired on first tool call
    - With lazy_init=False: Sandbox is acquired on first agent invocation (before_agent)
    - Sandbox is reused across multiple turns within the same thread
    - Sandbox is NOT released after each agent call to avoid wasteful recreation
    - Cleanup happens at application shutdown via SandboxProvider.shutdown()
    """

    state_schema = SandboxMiddlewareState

    def __init__(self, lazy_init: bool = True, user_id: str | None = None):
        """Initialize sandbox middleware.

        Args:
            lazy_init: If True, defer sandbox acquisition until first tool call.
                      If False, acquire sandbox eagerly in before_agent().
                      Default is True for optimal performance.
            user_id: Authenticated user ID. When provided, the user's encrypted
                     secrets are injected as environment variables inside the sandbox,
                     allowing user code to access their own API keys.
        """
        super().__init__()
        self._lazy_init = lazy_init
        self._user_id = user_id

    def _acquire_sandbox(self, thread_id: str) -> str:
        # Load user secrets to inject into sandbox environment
        extra_env: dict[str, str] = {}
        if self._user_id:
            try:
                from src.auth.secrets import load_user_secrets

                extra_env = load_user_secrets(self._user_id)
            except Exception:
                pass  # Fail open: sandbox still works with platform env vars

        provider = get_sandbox_provider()
        sandbox_id = provider.acquire(thread_id, user_id=self._user_id, extra_env=extra_env)
        print(f"Acquiring sandbox {sandbox_id}")
        return sandbox_id

    @override
    def before_agent(self, state: SandboxMiddlewareState, runtime: Runtime) -> dict | None:
        # Skip acquisition if lazy_init is enabled
        if self._lazy_init:
            return super().before_agent(state, runtime)

        # Eager initialization (original behavior)
        if "sandbox" not in state or state["sandbox"] is None:
            thread_id = runtime.context["thread_id"]
            print(f"Thread ID: {thread_id}")
            sandbox_id = self._acquire_sandbox(thread_id)
            return {"sandbox": {"sandbox_id": sandbox_id}}
        return super().before_agent(state, runtime)
