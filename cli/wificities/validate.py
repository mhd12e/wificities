"""wificities validate — check project for issues."""
import json
import re
from pathlib import Path

import click

from .themes import get_themes_dir, load_theme_json
from .project import enter_project_dir


@click.command("validate")
def validate_cmd():
    """Check the project for issues."""
    project_dir = enter_project_dir()
    errors = 0
    warnings = 0

    # Check config.json
    config_path = project_dir / "config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            if "ssid" not in config:
                click.echo("\u274c  config.json missing 'ssid' field")
                errors += 1
            elif len(config["ssid"]) > 32:
                click.echo("\u274c  SSID is longer than 32 characters")
                errors += 1
            else:
                click.echo("\u2705 config.json valid")

        except json.JSONDecodeError as e:
            click.echo(f"\u274c  config.json is not valid JSON: {e}")
            errors += 1
    else:
        click.echo("\u274c  config.json not found")
        errors += 1

    # Check wificities.json (if exists)
    wificities_path = project_dir / "wificities.json"
    manifest = None
    if wificities_path.exists():
        try:
            manifest = json.loads(wificities_path.read_text(encoding="utf-8"))
            click.echo("\u2705 wificities.json valid")
        except json.JSONDecodeError as e:
            click.echo(f"\u274c  wificities.json is not valid JSON: {e}")
            errors += 1

    # Check mode
    if manifest:
        mode = manifest.get("mode", "raw")

        if mode == "theme":
            theme_name = manifest.get("theme", "")
            themes_dir = get_themes_dir()
            theme_dir = themes_dir / theme_name

            if theme_dir.exists():
                click.echo(f"\u2705 Theme '{theme_name}' found")
            else:
                click.echo(f"\u274c  Theme '{theme_name}' not found")
                errors += 1

            # Check content files exist
            pages = manifest.get("pages", {})
            for url, page_def in pages.items():
                content = page_def.get("content")
                if content:
                    if (project_dir / content).exists():
                        click.echo(f"\u2705 Content file: {content}")
                    else:
                        click.echo(f"\u274c  Content file missing: {content}")
                        errors += 1

                # Check template exists in theme
                tmpl = page_def.get("template")
                if tmpl and theme_dir.exists():
                    tmpl_path = theme_dir / "templates" / f"{tmpl}.html"
                    if not tmpl_path.exists():
                        click.echo(f"\u274c  Template '{tmpl}' not found in theme")
                        errors += 1

        elif mode == "raw":
            public_dir = project_dir / "public"
            if public_dir.exists():
                if (public_dir / "index.html").exists():
                    click.echo("\u2705 public/index.html exists")
                else:
                    click.echo("\u274c  public/index.html not found")
                    errors += 1
            else:
                click.echo("\u274c  public/ directory not found")
                errors += 1

    else:
        # No manifest — raw mode
        public_dir = project_dir / "public"
        if public_dir.exists():
            if (public_dir / "index.html").exists():
                click.echo("\u2705 public/index.html exists")
            else:
                click.echo("\u274c  public/index.html not found")
                errors += 1
        else:
            click.echo("\u274c  public/ directory not found")
            errors += 1

    # Size estimate
    build_dir = project_dir / "build"
    if build_dir.exists():
        total = sum(f.stat().st_size for f in build_dir.rglob("*") if f.is_file())
        max_size = 2_500_000
        pct = round(total / max_size * 100)
        if pct > 100:
            click.echo(f"\u274c  Build size: {total//1024} KB / {max_size//1024} KB "
                       f"({pct}%) — TOO LARGE!")
            errors += 1
        elif pct > 90:
            click.echo(f"\u26a0\ufe0f  Build size: {total//1024} KB / {max_size//1024} KB "
                       f"({pct}%) — getting tight!")
            warnings += 1
        else:
            click.echo(f"\u2705 Build size: {total//1024} KB / {max_size//1024} KB ({pct}%)")

    # Summary
    click.echo(f"\n{errors} error(s), {warnings} warning(s)")
    if errors > 0:
        raise SystemExit(1)
