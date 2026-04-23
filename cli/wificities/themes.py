"""wificities theme — manage themes via git repos."""
import json
from pathlib import Path

import click

from .registry import (
    resolve_repo_url, clone_or_update, remove_package,
    get_installed_dir, list_registry,
)


def get_theme_dir(project_dir: Path, theme_name: str) -> Path | None:
    """Get the theme directory for a project."""
    dest = get_installed_dir(project_dir, "themes", theme_name)
    if dest.exists() and (dest / "theme.json").exists():
        return dest
    return None


def ensure_theme(project_dir: Path, theme_name: str) -> Path | None:
    """Make sure a theme is installed, clone if missing."""
    dest = get_installed_dir(project_dir, "themes", theme_name)
    if dest.exists() and (dest / "theme.json").exists():
        return dest

    url = resolve_repo_url(theme_name, "themes")
    if url is None:
        return None

    click.echo(f"  Downloading theme '{theme_name}'...")
    if clone_or_update(url, dest):
        return dest
    return None


def load_theme_json(project_dir: Path, theme_name: str) -> dict | None:
    """Load a theme's theme.json. Ensures theme is installed."""
    theme_dir = ensure_theme(project_dir, theme_name)
    if theme_dir is None:
        return None
    theme_path = theme_dir / "theme.json"
    if not theme_path.exists():
        return None
    try:
        return json.loads(theme_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


@click.group("theme")
def theme_group():
    """Manage themes."""
    pass


@theme_group.command("list")
def theme_list():
    """List available themes."""
    click.echo("\n  Available themes:\n")
    entries = list_registry("themes")
    if entries:
        for name, desc, verified in entries:
            v = " [verified]" if verified else ""
            click.echo(f"    {name:20s} {desc}{v}")
    else:
        click.echo("    No themes in registry.")

    from .project import find_project_dir
    proj = find_project_dir()
    if proj:
        wf_path = proj / "wificities.json"
        if wf_path.exists():
            wf = json.loads(wf_path.read_text(encoding="utf-8"))
            current = wf.get("theme", "")
            if current:
                click.echo(f"\n  Current: {current}")
    click.echo()


@theme_group.command("add")
@click.argument("name")
def theme_add(name: str):
    """Install a theme by name or git URL."""
    from .project import enter_project_dir
    project_dir = enter_project_dir()

    url = resolve_repo_url(name, "themes")
    if url is None:
        click.echo(f"  '{name}' not found. Use a git URL.")
        raise SystemExit(1)

    theme_name = name
    if name.startswith("http") or name.startswith("git@"):
        theme_name = name.rstrip("/").split("/")[-1].replace(".git", "")
        if theme_name.startswith("wificities-theme-"):
            theme_name = theme_name[len("wificities-theme-"):]

    dest = get_installed_dir(project_dir, "themes", theme_name)
    click.echo(f"  Installing theme '{theme_name}'...")
    if not clone_or_update(url, dest):
        click.echo(f"  Failed to clone.")
        raise SystemExit(1)

    click.echo(f"  Installed: {theme_name}")
    click.echo(f"  Switch: ./wificities theme switch {theme_name}")


@theme_group.command("switch")
@click.argument("name")
def theme_switch(name: str):
    """Switch to a different theme, keeping content."""
    from .project import enter_project_dir
    project_dir = enter_project_dir()

    theme_dir = ensure_theme(project_dir, name)
    if theme_dir is None:
        click.echo(f"  Theme '{name}' not found.")
        raise SystemExit(1)

    new_theme = load_theme_json(project_dir, name)
    if not new_theme:
        click.echo(f"  Could not load theme.json for '{name}'")
        raise SystemExit(1)

    wf_path = project_dir / "wificities.json"
    wf = json.loads(wf_path.read_text(encoding="utf-8")) if wf_path.exists() else {}
    old = wf.get("theme", "")
    wf["theme"] = name

    personal = {"site_title", "owner_name", "bio", "show_guestbook",
                "show_visitor_counter", "show_sidebar", "show_marquee",
                "show_construction", "nav_links"}
    old_vars = wf.get("variables", {})
    new_vars = {k: v for k, v in old_vars.items() if k in personal}

    for vname, vdef in new_theme.get("variables", {}).items():
        if vname not in new_vars:
            new_vars[vname] = vdef.get("default", "") if isinstance(vdef, dict) else vdef

    wf["variables"] = new_vars
    wf_path.write_text(json.dumps(wf, indent=2, ensure_ascii=False), encoding="utf-8")
    click.echo(f"  Switched: {old} -> {name}")
    click.echo(f"  Run './wificities build' to apply.")


@theme_group.command("update")
@click.argument("name", required=False)
def theme_update(name: str | None):
    """Update theme to latest version."""
    from .project import enter_project_dir
    project_dir = enter_project_dir()

    wf = json.loads((project_dir / "wificities.json").read_text(encoding="utf-8"))
    theme_name = name or wf.get("theme", "")
    if not theme_name:
        click.echo("  No theme set.")
        return

    url = resolve_repo_url(theme_name, "themes")
    if url:
        dest = get_installed_dir(project_dir, "themes", theme_name)
        click.echo(f"  Updating {theme_name}...")
        clone_or_update(url, dest)
        click.echo(f"  Updated.")
