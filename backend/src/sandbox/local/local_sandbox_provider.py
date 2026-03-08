import os
from pathlib import Path

from src.sandbox.local.local_sandbox import LocalSandbox
from src.sandbox.sandbox import Sandbox
from src.sandbox.sandbox_provider import SandboxProvider

# One sandbox instance per user (or "local" for the global/unauthenticated case).
# Key: sandbox_id string ("local" or "local:<user_id>")
_sandboxes: dict[str, LocalSandbox] = {}


class LocalSandboxProvider(SandboxProvider):
    def __init__(self):
        """Initialize the local sandbox provider."""
        self._global_path_mappings = self._build_global_path_mappings()
        self._readonly_paths = self._build_readonly_paths()

    def _build_global_path_mappings(self) -> dict[str, str]:
        """Build path mappings for the global (non-user-scoped) sandbox.

        Maps /mnt/skills → project skills directory.
        """
        mappings: dict[str, str] = {}
        try:
            from src.config import get_app_config

            config = get_app_config()
            skills_path = config.skills.get_skills_path()
            container_path = config.skills.container_path

            if skills_path.exists():
                mappings[container_path] = str(skills_path)
        except Exception as e:
            print(f"Warning: Could not setup skills path mapping: {e}")

        return mappings

    def _build_readonly_paths(self) -> list[str]:
        """Return host paths that the sandbox must never write to.

        Currently protects the skills/public directory so that neither
        write_file nor bash commands can modify built-in skills.

        Also attempts to set the directory as OS-level read-only (chmod a-w)
        so that even shell commands executed by the agent will be rejected by
        the kernel, providing a second independent layer of protection.
        """
        try:
            from src.config import get_app_config

            skills_path = get_app_config().skills.get_skills_path()
            public_dir = skills_path / "public"
            if public_dir.exists():
                self._enforce_readonly_fs(public_dir)
                return [str(public_dir)]
        except Exception as e:
            print(f"Warning: Could not determine read-only skills path: {e}")
        return []

    @staticmethod
    def _enforce_readonly_fs(directory: Path) -> None:
        """Recursively remove write permission from a directory tree.

        This is a best-effort OS-level protection.  Failures are logged but do
        not prevent the application from starting.
        """
        import stat

        try:
            for root, dirs, files in os.walk(directory):
                for name in files + dirs:
                    target = os.path.join(root, name)
                    try:
                        current = os.stat(target).st_mode
                        os.chmod(target, current & ~(stat.S_IWRITE | stat.S_IWGRP | stat.S_IWOTH))
                    except OSError:
                        pass
            # Also protect the directory itself
            current = os.stat(directory).st_mode
            os.chmod(directory, current & ~(stat.S_IWRITE | stat.S_IWGRP | stat.S_IWOTH))
        except Exception as e:
            print(f"Warning: Could not set read-only permissions on {directory}: {e}")

    def _build_user_path_mappings(self, user_id: str) -> dict[str, str]:
        """Build path mappings for a specific authenticated user.

        Inherits the global mappings but overrides /mnt/skills/custom with the
        user's private skills directory so the agent only sees its own installed
        custom skills. Public skills remain globally shared.
        """
        from src.config.agents_config import _is_user_scoped
        from src.config.paths import get_paths

        mappings = dict(self._global_path_mappings)

        if _is_user_scoped(user_id):
            try:
                from src.config import get_app_config

                container_base = get_app_config().skills.container_path  # e.g. /mnt/skills
                user_custom_dir = get_paths().user_skills_dir(user_id)
                user_custom_dir.mkdir(parents=True, exist_ok=True)
                # Override /mnt/skills/custom → user's private skills dir
                mappings[f"{container_base}/custom"] = str(user_custom_dir)
            except Exception as e:
                print(f"Warning: Could not setup user skills path mapping for {user_id}: {e}")

        return mappings

    def acquire(self, thread_id: str | None = None, user_id: str | None = None, extra_env: dict[str, str] | None = None) -> str:
        from src.config.agents_config import _is_user_scoped

        is_scoped = _is_user_scoped(user_id)
        sandbox_id = f"local:{user_id}" if is_scoped else "local"

        if sandbox_id not in _sandboxes:
            path_mappings = self._build_user_path_mappings(user_id) if is_scoped else self._global_path_mappings
            _sandboxes[sandbox_id] = LocalSandbox(sandbox_id, path_mappings=path_mappings, readonly_paths=self._readonly_paths)

        return sandbox_id

    def get(self, sandbox_id: str) -> Sandbox | None:
        if sandbox_id in _sandboxes:
            return _sandboxes[sandbox_id]
        # Legacy fallback: callers that already have "local" as sandbox_id
        if sandbox_id == "local" and "local" not in _sandboxes:
            self.acquire()
            return _sandboxes.get("local")
        return None

    def release(self, sandbox_id: str) -> None:
        # LocalSandbox uses per-user singletons - no cleanup needed on release.
        # Cleanup happens at application shutdown via shutdown() if implemented.
        pass
