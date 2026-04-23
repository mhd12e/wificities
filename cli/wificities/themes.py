"""wificities theme — manage themes."""
import json
from pathlib import Path

import click


def get_themes_dir() -> Path:
    """Get the built-in themes directory."""
    # Walk up from CLI package to repo root
    cli_dir = Path(__file__).resolve().parent.parent.parent
    return cli_dir / "themes"


def load_theme_json(theme_name: str) -> dict | None:
    """Load a theme's theme.json."""
    themes_dir = get_themes_dir()
    theme_path = themes_dir / theme_name / "theme.json"

    # Also check if theme_name is an absolute/relative path
    if not theme_path.exists():
        alt = Path(theme_name) / "theme.json"
        if alt.exists():
            theme_path = alt
        else:
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
    themes_dir = get_themes_dir()

    if not themes_dir.exists():
        click.echo("No themes directory found.")
        return

    click.echo("\nAvailable themes:\n")

    found = False
    for d in sorted(themes_dir.iterdir()):
        if d.is_dir() and (d / "theme.json").exists():
            try:
                data = json.loads((d / "theme.json").read_text(encoding="utf-8"))
                name = data.get("name", d.name)
                desc = data.get("description", "")
                click.echo(f"  {d.name:20s} {desc}")
                found = True
            except (json.JSONDecodeError, OSError):
                click.echo(f"  {d.name:20s} (error reading theme.json)")

    if not found:
        click.echo("  No themes found.")

    click.echo()


@theme_group.command("preview")
@click.argument("name")
@click.option("--port", default=8080, help="Port for preview server")
def theme_preview(name: str, port: int):
    """Preview a theme with demo content."""
    themes_dir = get_themes_dir()
    theme_dir = themes_dir / name

    if not theme_dir.exists():
        click.echo(f"Theme '{name}' not found.")
        raise SystemExit(1)

    click.echo(f"Preview not yet implemented. Use './wificities init' with the theme and './wificities serve'.")


@theme_group.command("switch")
@click.argument("name")
def theme_switch(name: str):
    """Switch to a different theme, keeping your content and config."""
    from .project import enter_project_dir
    project_dir = enter_project_dir()
    wf_path = project_dir / "wificities.json"

    if not wf_path.exists():
        click.echo("Error: wificities.json not found. Are you in a wificity project?")
        raise SystemExit(1)

    # Verify theme exists
    themes_dir = get_themes_dir()
    theme_dir = themes_dir / name
    if not theme_dir.exists():
        click.echo(f"Theme '{name}' not found.")
        click.echo(f"Available themes:")
        for d in sorted(themes_dir.iterdir()):
            if d.is_dir() and (d / "theme.json").exists():
                click.echo(f"  {d.name}")
        raise SystemExit(1)

    new_theme_json = load_theme_json(name)
    if not new_theme_json:
        click.echo(f"Error: Could not load theme.json for '{name}'")
        raise SystemExit(1)

    wf = json.loads(wf_path.read_text(encoding="utf-8"))
    old_theme = wf.get("theme", "")

    # Switch theme
    wf["theme"] = name

    # Reset theme-specific variables to new theme's defaults,
    # but preserve user's personal variables (site_title, owner_name, bio, etc.)
    personal_keys = {
        "site_title", "owner_name", "bio", "show_guestbook",
        "show_visitor_counter", "show_sidebar", "show_marquee",
        "show_construction", "nav_links",
    }

    old_vars = wf.get("variables", {})
    new_vars = {}

    # Keep personal variables
    for key in personal_keys:
        if key in old_vars:
            new_vars[key] = old_vars[key]

    # Apply new theme defaults for everything else
    for var_name, var_def in new_theme_json.get("variables", {}).items():
        if var_name not in new_vars:
            if isinstance(var_def, dict):
                new_vars[var_name] = var_def.get("default", "")
            else:
                new_vars[var_name] = var_def

    wf["variables"] = new_vars

    # Check if page templates exist in new theme
    available_templates = set(new_theme_json.get("templates", {}).keys())
    for url, page_def in wf.get("pages", {}).items():
        tmpl = page_def.get("template", "page")
        if tmpl not in available_templates:
            fallback = "page" if "page" in available_templates else next(iter(available_templates), "page")
            click.echo(f"  Warning: Template '{tmpl}' not in new theme. "
                       f"Falling back to '{fallback}' for {url}")
            page_def["template"] = fallback

    wf_path.write_text(json.dumps(wf, indent=2, ensure_ascii=False),
                        encoding="utf-8")

    click.echo(f"\n\u2705 Switched from '{old_theme}' to '{name}'")
    click.echo(f"   Your content and pages are preserved.")
    click.echo(f"   Run './wificities config palette' to pick colors for the new theme.")
    click.echo(f"   Run './wificities build' to see changes.")
