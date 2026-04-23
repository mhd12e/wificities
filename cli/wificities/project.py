"""Project directory detection for wificities CLI."""
import os
from pathlib import Path


def find_project_dir() -> Path | None:
    """Find the wificity project directory.

    Search order:
    1. Current directory (if it's a project)
    2. Walk up parent directories
    3. Look one level down for a single project subdirectory
       (handles: you're in the repo root, project is in my-wificity/)
    """
    current = Path.cwd().resolve()

    # 1. Check current dir and walk up
    for d in [current, *current.parents]:
        if _is_project_dir(d):
            return d
        if d == d.parent:
            break

    # 2. Look one level down for project subdirectories
    candidates = []
    for child in current.iterdir():
        if child.is_dir() and not child.name.startswith('.') and _is_project_dir(child):
            candidates.append(child)

    if len(candidates) == 1:
        return candidates[0]

    return None


def require_project_dir() -> Path:
    """Find the project directory or exit with an error."""
    project_dir = find_project_dir()
    if project_dir is None:
        import click
        click.echo("Error: No wificity project found.")
        click.echo("  Run: wificities init <name>")
        raise SystemExit(1)
    return project_dir


def enter_project_dir() -> Path:
    """Find the project directory, cd into it, and return its path."""
    project_dir = require_project_dir()
    os.chdir(project_dir)
    return project_dir


def _is_project_dir(d: Path) -> bool:
    """Check if a directory looks like a wificity project."""
    # Must have config.json with wificities.json or public/
    if (d / "config.json").exists():
        if (d / "wificities.json").exists():
            return True
        if (d / "public").exists():
            return True
    return False
