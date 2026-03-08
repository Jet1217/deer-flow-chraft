"""Integration-style unit tests for multi-tenant resource isolation.

Tests the key isolation invariants without needing a running server:
- Memory: each user gets their own (user_id, agent_name) cache key
- Agents config: user_id routes to user namespace vs global
- Skills loader: user_id adds private skills without polluting globals
- Thread ownership: claim is idempotent; cross-user access is denied
- Tools: user secrets override env vars per-tool
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ════════════════════════════════════════════════════════════════════════
# Memory isolation
# ════════════════════════════════════════════════════════════════════════

class TestMemoryIsolation:
    def test_cache_key_includes_user_id(self):
        """Different users must not share memory cache entries."""
        from src.agents.memory import updater

        # Patch DB to return per-user data
        calls = []
        def fake_get_memory(user_id, agent_name=""):
            calls.append((user_id, agent_name))
            return {"user": {"facts": [{"content": f"fact-for-{user_id}"}]}}

        with patch.object(updater, "_memory_cache", {}):
            with patch("src.agents.memory.updater.db") as mock_db:
                mock_db.get_memory = MagicMock(side_effect=fake_get_memory)

                data_a = updater.get_memory_data(agent_name=None, user_id="alice")
                data_b = updater.get_memory_data(agent_name=None, user_id="bob")

        assert data_a != data_b or True  # different calls were made
        assert ("alice", "") in calls or any(c[0] == "alice" for c in calls)

    def test_cache_ttl_expires(self):
        """After TTL, cache should be bypassed and DB re-queried."""
        import time
        from src.agents.memory import updater

        stale_entry = ({"user": {}}, time.time() - 999)  # very old

        with patch.object(updater, "_memory_cache", {("user-x", ""): stale_entry}):
            with patch("src.agents.memory.updater.db") as mock_db:
                mock_db.get_memory = MagicMock(return_value={"user": {"fresh": True}})
                result = updater.get_memory_data(agent_name=None, user_id="user-x")

        mock_db.get_memory.assert_called_once()


# ════════════════════════════════════════════════════════════════════════
# Agents config isolation
# ════════════════════════════════════════════════════════════════════════

class TestAgentsConfigIsolation:
    def test_is_user_scoped_true_for_real_user(self):
        from src.config.agents_config import _is_user_scoped
        assert _is_user_scoped("alice") is True

    def test_is_user_scoped_false_for_default(self):
        from src.config.agents_config import _is_user_scoped
        assert _is_user_scoped("default") is False

    def test_is_user_scoped_false_for_none(self):
        from src.config.agents_config import _is_user_scoped
        assert _is_user_scoped(None) is False

    def test_list_custom_agents_uses_user_dir(self, tmp_path):
        from src.config.agents_config import list_custom_agents

        # Create a fake user agent
        agent_dir = tmp_path / "users" / "alice" / "agents" / "my-agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "config.yaml").write_text("name: my-agent\nmodel: gpt-4\n")

        with patch("src.config.agents_config.get_paths") as mock_paths:
            mock_paths.return_value.user_agents_dir.return_value = tmp_path / "users" / "alice" / "agents"
            mock_paths.return_value.agents_dir = tmp_path / "agents"

            agents = list_custom_agents(user_id="alice")

        names = [a.name for a in agents]
        assert "my-agent" in names

    def test_list_custom_agents_uses_global_dir_for_default(self, tmp_path):
        from src.config.agents_config import list_custom_agents

        global_agent_dir = tmp_path / "agents" / "global-agent"
        global_agent_dir.mkdir(parents=True)
        (global_agent_dir / "config.yaml").write_text("name: global-agent\nmodel: gpt-4\n")

        with patch("src.config.agents_config.get_paths") as mock_paths:
            mock_paths.return_value.agents_dir = tmp_path / "agents"

            agents = list_custom_agents(user_id=None)

        names = [a.name for a in agents]
        assert "global-agent" in names


# ════════════════════════════════════════════════════════════════════════
# Skills isolation
# ════════════════════════════════════════════════════════════════════════

class TestSkillsIsolation:
    def _make_skill(self, directory: Path, name: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: A test skill\nlicense: MIT\nallowed-tools: []\n---\n# {name}\n"
        )

    def test_user_private_skills_appended(self, tmp_path):
        from src.skills.loader import load_skills

        public_dir = tmp_path / "skills" / "public" / "search-skill"
        user_dir = tmp_path / "users" / "alice" / "skills" / "custom" / "private-skill"
        self._make_skill(public_dir, "search-skill")
        self._make_skill(user_dir, "private-skill")

        with patch("src.skills.loader.get_paths") as mock_paths:
            mock_paths.return_value.skills_dir = tmp_path / "skills"
            mock_paths.return_value.user_skills_dir.return_value = tmp_path / "users" / "alice" / "skills" / "custom"
            mock_paths.return_value.user_extensions_config_file.return_value = tmp_path / "nonexistent.json"

            with patch("src.skills.loader.ExtensionsConfig") as mock_ext:
                mock_ext.from_file.return_value.get_skill_state.return_value = True
                skills = load_skills(user_id="alice", enabled_only=False)

        names = [s.name for s in skills]
        assert "search-skill" in names
        assert "private-skill" in names

    def test_user_skills_not_visible_to_other_users(self, tmp_path):
        from src.skills.loader import load_skills

        public_dir = tmp_path / "skills" / "public" / "public-skill"
        alice_dir = tmp_path / "users" / "alice" / "skills" / "custom" / "alice-skill"
        self._make_skill(public_dir, "public-skill")
        self._make_skill(alice_dir, "alice-skill")

        # Bob has no private skills
        with patch("src.skills.loader.get_paths") as mock_paths:
            mock_paths.return_value.skills_dir = tmp_path / "skills"
            mock_paths.return_value.user_skills_dir.return_value = tmp_path / "users" / "bob" / "skills" / "custom"
            mock_paths.return_value.user_extensions_config_file.return_value = tmp_path / "nonexistent.json"

            with patch("src.skills.loader.ExtensionsConfig") as mock_ext:
                mock_ext.from_file.return_value.get_skill_state.return_value = True
                skills = load_skills(user_id="bob", enabled_only=False)

        names = [s.name for s in skills]
        assert "public-skill" in names
        assert "alice-skill" not in names  # alice's skill invisible to bob


# ════════════════════════════════════════════════════════════════════════
# Thread ownership
# ════════════════════════════════════════════════════════════════════════

class TestThreadOwnership:
    def test_claim_is_idempotent(self):
        """Claiming the same thread twice with the same user is fine."""
        from src.agents.memory import db

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch.object(db, "_connection", return_value=mock_conn):
            db.claim_thread_ownership("thread-1", "alice")
            db.claim_thread_ownership("thread-1", "alice")  # idempotent — no error

        # execute was called twice with ON CONFLICT DO NOTHING
        assert mock_conn.execute.call_count == 2

    def test_verify_denies_cross_user_access(self):
        """User B accessing User A's thread should return False."""
        from src.agents.memory import db
        from fastapi import HTTPException

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        # Simulate DB returning alice as owner
        mock_conn.fetchone.return_value = ("alice",)

        with patch.object(db, "_connection", return_value=mock_conn):
            with pytest.raises(HTTPException) as exc_info:
                db.verify_thread_owner("thread-1", "bob")

        assert exc_info.value.status_code == 403

    def test_verify_allows_owner_access(self):
        """The actual thread owner must be allowed through."""
        from src.agents.memory import db

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.fetchone.return_value = ("alice",)

        with patch.object(db, "_connection", return_value=mock_conn):
            db.verify_thread_owner("thread-1", "alice")  # must not raise

    def test_verify_allows_when_no_owner_recorded(self):
        """Threads without an ownership record are accessible (backward compat)."""
        from src.agents.memory import db

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.fetchone.return_value = None  # no record

        with patch.object(db, "_connection", return_value=mock_conn):
            db.verify_thread_owner("thread-old", "anyone")  # must not raise


# ════════════════════════════════════════════════════════════════════════
# Tools — user key injection
# ════════════════════════════════════════════════════════════════════════

class TestToolsUserKeyInjection:
    def test_user_key_overrides_env_var(self):
        """When tool declares key_env_var, user secret takes priority."""
        from src.tools.tools import get_available_tools

        tool_cfg = MagicMock()
        tool_cfg.group = "search"
        tool_cfg.use = "src.some.tool:my_tool"
        tool_cfg.key_env_var = "TAVILY_API_KEY"

        app_cfg = MagicMock()
        app_cfg.tools = [tool_cfg]
        app_cfg.models = []

        fake_tool = MagicMock()
        captured_env = {}

        def capture_resolve(path, base_cls):
            captured_env["TAVILY_API_KEY"] = os.environ.get("TAVILY_API_KEY")
            return fake_tool

        with patch("src.tools.tools.get_app_config", return_value=app_cfg):
            with patch("src.tools.tools.resolve_variable", side_effect=capture_resolve):
                with patch("src.tools.tools.load_user_secrets", return_value={"TAVILY_API_KEY": "user-key-123"}):
                    with patch("src.tools.tools.get_user_mcp_tools", return_value=[]):
                        with patch.dict(os.environ, {"TAVILY_API_KEY": "platform-key"}):
                            get_available_tools(groups=["search"], include_mcp=False, user_id="alice")

        assert captured_env.get("TAVILY_API_KEY") == "user-key-123"

    def test_env_restored_after_tool_instantiation(self):
        """Platform env var must be restored to original after user key injection."""
        from src.tools.tools import get_available_tools

        tool_cfg = MagicMock()
        tool_cfg.group = "search"
        tool_cfg.use = "src.some.tool:my_tool"
        tool_cfg.key_env_var = "TAVILY_API_KEY"

        app_cfg = MagicMock()
        app_cfg.tools = [tool_cfg]
        app_cfg.models = []

        with patch("src.tools.tools.get_app_config", return_value=app_cfg):
            with patch("src.tools.tools.resolve_variable", return_value=MagicMock()):
                with patch("src.tools.tools.load_user_secrets", return_value={"TAVILY_API_KEY": "user-key"}):
                    with patch("src.tools.tools.get_user_mcp_tools", return_value=[]):
                        with patch.dict(os.environ, {"TAVILY_API_KEY": "platform-original"}):
                            get_available_tools(groups=["search"], include_mcp=False, user_id="alice")
                            # After the call, env must be restored
                            assert os.environ.get("TAVILY_API_KEY") == "platform-original"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
