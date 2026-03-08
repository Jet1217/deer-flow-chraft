import os
from pathlib import Path

from .parser import parse_skill_file
from .types import Skill


def get_skills_root_path() -> Path:
    """
    Get the root path of the skills directory.

    Returns:
        Path to the skills directory (deer-flow/skills)
    """
    # backend directory is current file's parent's parent's parent
    backend_dir = Path(__file__).resolve().parent.parent.parent
    # skills directory is sibling to backend directory
    skills_dir = backend_dir.parent / "skills"
    return skills_dir


def _scan_skills_dir(category_path: Path, category: str) -> list[Skill]:
    """Scan a single directory for SKILL.md files."""
    skills: list[Skill] = []
    if not category_path.exists() or not category_path.is_dir():
        return skills
    for current_root, dir_names, file_names in os.walk(category_path):
        dir_names[:] = sorted(name for name in dir_names if not name.startswith("."))
        if "SKILL.md" not in file_names:
            continue
        skill_file = Path(current_root) / "SKILL.md"
        relative_path = skill_file.parent.relative_to(category_path)
        skill = parse_skill_file(skill_file, category=category, relative_path=relative_path)
        if skill:
            skills.append(skill)
    return skills


def load_skills(
    skills_path: Path | None = None,
    use_config: bool = True,
    enabled_only: bool = False,
    user_id: str | None = None,
) -> list[Skill]:
    """
    Load all skills from the skills directory.

    Scans both public and custom skill directories, parsing SKILL.md files
    to extract metadata. The enabled state is determined by the skills_state_config.json file.

    When user_id is provided (and not "default"), also scans the user's private
    skills directory and uses the user's extensions_config.json for enabled state.

    Args:
        skills_path: Optional custom path to skills directory.
                     If not provided and use_config is True, uses path from config.
                     Otherwise defaults to deer-flow/skills
        use_config: Whether to load skills path from config (default: True)
        enabled_only: If True, only return enabled skills (default: False)
        user_id: When provided and not "default", also load user-private skills and
                 use per-user extensions config for enabled state.

    Returns:
        List of Skill objects, sorted by name
    """
    is_user_scoped = bool(user_id) and user_id != "default"

    if skills_path is None:
        if use_config:
            try:
                from src.config import get_app_config

                config = get_app_config()
                skills_path = config.skills.get_skills_path()
            except Exception:
                # Fallback to default if config fails
                skills_path = get_skills_root_path()
        else:
            skills_path = get_skills_root_path()

    skills: list[Skill] = []

    if skills_path.exists():
        # Scan global public and custom directories
        for category in ["public", "custom"]:
            skills += _scan_skills_dir(skills_path / category, category)

    # Scan user-private skills (only when user is scoped)
    if is_user_scoped:
        from src.config.paths import get_paths

        user_skills_dir = get_paths().user_skills_dir(user_id)
        user_private = _scan_skills_dir(user_skills_dir, "custom")
        # Deduplicate: user private skills override global skills of the same name
        global_names = {s.name for s in skills}
        for skill in user_private:
            if skill.name not in global_names:
                skills.append(skill)

    # Load skills state configuration and update enabled status
    # NOTE: We use ExtensionsConfig.from_file() instead of get_extensions_config()
    # to always read the latest configuration from disk. This ensures that changes
    # made through the Gateway API (which runs in a separate process) are immediately
    # reflected in the LangGraph Server when loading skills.
    try:
        from src.config.extensions_config import ExtensionsConfig

        if is_user_scoped:
            from src.config.paths import get_paths

            user_cfg_file = get_paths().user_extensions_config_file(user_id)
            extensions_config = ExtensionsConfig.from_file(user_cfg_file) if user_cfg_file.exists() else ExtensionsConfig.from_file()
        else:
            extensions_config = ExtensionsConfig.from_file()

        for skill in skills:
            skill.enabled = extensions_config.is_skill_enabled(skill.name, skill.category)
    except Exception as e:
        # If config loading fails, default to all enabled
        print(f"Warning: Failed to load extensions config: {e}")

    # Filter by enabled status if requested
    if enabled_only:
        skills = [skill for skill in skills if skill.enabled]

    # Sort by name for consistent ordering
    skills.sort(key=lambda s: s.name)

    return skills
