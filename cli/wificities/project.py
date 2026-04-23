"""Project directory detection for wificities CLI."""
import os
from pathlib import Path


def find_project_dir() -> Path | None:
    """Find the wificity project directory by walking up from cwd.

    Looks for a directory containing config.json or wificities.json.
    Returns the project directory path, or None if not found.
    """
    current = Path.cwd().resolve()

    # Walk up from cwd
    for d in [current, *current.parents]:
        if _is_project_dir(d):
            return d
        # Stop at filesystem root
        if d == d.parent:
            break

    return None


def require_project_dir() -> Path:
    """Find the project directory or exit with an error."""
    project_dir = find_project_dir()
    if project_dir is None:
        import click
        click.echo("Error: Not inside a wificity project.")
        click.echo("  No config.json or wificities.json found in this directory or any parent.")
        click.echo("")
        click.echo("  Create a project first: wificities init <name>")
        raise SystemExit(1)
    return project_dir


def enter_project_dir() -> Path:
    """Find the project directory, cd into it, and return its path."""
    project_dir = require_project_dir()
    os.chdir(project_dir)
    return project_dir


def _is_project_dir(d: Path) -> bool:
    """Check if a directory looks like a wificity project."""
    # Must have config.json OR wificities.json
    if (d / "config.json").exists():
        return True
    if (d / "wificities.json").exists():
        return True
    # Also check for public/index.html (raw mode without config)
    if (d / "public" / "index.html").exists():
        return True
    return False
