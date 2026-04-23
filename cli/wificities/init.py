"""wificities init — scaffold a new wificity project."""
import json
import shutil
from pathlib import Path

import click

from .themes import get_themes_dir, load_theme_json


@click.command("init")
@click.argument("name")
@click.option("--theme", default=None, help="Theme to use (e.g., geocities-flame)")
@click.option("--raw", is_flag=True, help="Raw HTML mode, no theme")
def init_cmd(name: str, theme: str | None, raw: bool):
    """Create a new wificity project."""
    project_dir = Path.cwd() / name

    if project_dir.exists():
        click.echo(f"Error: Directory '{name}' already exists.")
        raise SystemExit(1)

    click.echo(f"\n\U0001f3d9  Welcome to WifiCities!\n")

    # Interactive prompts
    site_name = click.prompt("What's your wificity called?", default=name)
    ssid = click.prompt("What SSID should it broadcast?", default=site_name)
    # Theme selection
    if raw:
        theme = None
    elif theme is None:
        themes_dir = get_themes_dir()
        available = _list_available_themes(themes_dir)

        if available:
            click.echo("\nPick a theme:")
            for i, (tid, tdesc) in enumerate(available):
                click.echo(f"  [{i+1}] {tid:20s} — {tdesc}")
            click.echo(f"  [0] {'(none)':20s} — Raw HTML, I'll build my own")

            choice = click.prompt("\nChoice", type=int, default=1)
            if choice == 0:
                theme = None
            elif 1 <= choice <= len(available):
                theme = available[choice - 1][0]
            else:
                theme = None

    # Collect theme variables
    theme_vars = {}
    selected_palette = None
    if theme:
        theme_json = load_theme_json(theme)
        if theme_json:
            # Palette selection (if theme has palettes)
            if "palettes" in theme_json:
                palettes = theme_json["palettes"]
                palette_ids = list(palettes.keys())
                click.echo("\nPick a color palette:")
                for i, pid in enumerate(palette_ids):
                    pdata = palettes[pid]
                    pname = pdata.get("name", pid) if isinstance(pdata, dict) else pid
                    pdesc = pdata.get("description", "") if isinstance(pdata, dict) else ""
                    click.echo(f"  [{i+1}] {pname:15s} — {pdesc}")

                pchoice = click.prompt("\nPalette", type=int, default=1)
                if 1 <= pchoice <= len(palette_ids):
                    selected_palette = palette_ids[pchoice - 1]
                else:
                    selected_palette = palette_ids[0]

                theme_vars["palette"] = selected_palette

                # Apply palette colors
                pdata = palettes[selected_palette]
                color_keys = [
                    "bg_color", "bg_secondary", "text_color", "text_secondary",
                    "accent_color", "accent_secondary", "link_color", "link_hover",
                    "border_color", "header_bg", "header_accent",
                ]
                for key in color_keys:
                    if key in pdata:
                        theme_vars[key] = pdata[key]

            # Only ask for key personal variables, not all of them
            if "variables" in theme_json:
                personal_vars = ["owner_name", "bio"]
                click.echo(f"\nPersonalize:")
                for var_name in personal_vars:
                    var_def = theme_json["variables"].get(var_name, {})
                    if isinstance(var_def, dict):
                        desc = var_def.get("description", var_name)
                        default = var_def.get("default", "")
                    else:
                        desc = var_name
                        default = var_def
                    theme_vars[var_name] = click.prompt(f"  {desc}",
                                                        default=default)

    # Create project
    project_dir.mkdir(parents=True)

    # Write config.json
    config = {
        "ssid": ssid,
        "password": "",
        "channel": 1,
        "max_connections": 8,
        "site_name": site_name,
        "guestbook_max_entries": 100,
        "guestbook_max_name_length": 32,
        "guestbook_max_message_length": 256,
        "guestbook_rate_limit_seconds": 60,
        "plugins": {},
    }
    (project_dir / "config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if theme:
        # Theme mode
        wificities_json = {
            "mode": "theme",
            "theme": theme,
            "pages": {
                "/": {
                    "template": "home",
                    "content": "content/index.md",
                },
                "/about": {
                    "template": "page",
                    "content": "content/about.md",
                },
            },
            "variables": {
                "site_title": site_name,
                "owner_name": theme_vars.get("owner_name", site_name),
                **theme_vars,
            },
            "plugins": {},
        }
        (project_dir / "wificities.json").write_text(
            json.dumps(wificities_json, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Create content files
        content_dir = project_dir / "content"
        content_dir.mkdir()
        (content_dir / "index.md").write_text(
            f"Welcome to **{site_name}**!\n\n"
            "This is my portable website, broadcasting from my pocket.\n\n"
            "If you're reading this, we're probably nearby. Say hi!\n",
            encoding="utf-8",
        )
        (content_dir / "about.md").write_text(
            f"# About Me\n\nThis is {theme_vars.get('owner_name', site_name)}'s wificity.\n\n"
            "Edit this file at `content/about.md` to tell visitors about yourself.\n",
            encoding="utf-8",
        )

        click.echo(f"\n\u2705 Created {name}/")
        click.echo(f"   config.json")
        click.echo(f"   wificities.json")
        click.echo(f"   content/index.md")
        click.echo(f"   content/about.md")
    else:
        # Raw mode
        public_dir = project_dir / "public"
        public_dir.mkdir()
        (public_dir / "index.html").write_text(
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<head>\n"
            f'  <meta charset="UTF-8">\n'
            f'  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f"  <title>{site_name}</title>\n"
            "  <style>\n"
            "    body { font-family: 'Comic Sans MS', cursive; background: #000033;\n"
            "           color: #00ff00; text-align: center; padding: 50px; }\n"
            "    a { color: #ff00ff; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            f"  <h1>{site_name}</h1>\n"
            "  <p>Welcome to my wificity!</p>\n"
            "  <p><small>Edit public/index.html to make it yours.</small></p>\n"
            "</body>\n"
            "</html>\n",
            encoding="utf-8",
        )

        click.echo(f"\n\u2705 Created {name}/")
        click.echo(f"   config.json")
        click.echo(f"   public/index.html")

    click.echo(f"\nNext steps:")
    click.echo(f"  wificities serve        # preview locally")
    click.echo(f"  wificities build        # build for ESP32")
    click.echo(f"  wificities flash        # flash to ESP32")


def _list_available_themes(themes_dir: Path) -> list[tuple[str, str]]:
    """Return list of (theme_id, description) pairs. 'default' theme is always first."""
    result = []
    if not themes_dir.exists():
        return result
    for d in sorted(themes_dir.iterdir()):
        if d.is_dir() and (d / "theme.json").exists():
            try:
                data = json.loads((d / "theme.json").read_text(encoding="utf-8"))
                result.append((d.name, data.get("description", "")))
            except (json.JSONDecodeError, OSError):
                result.append((d.name, ""))

    # Put 'default' first
    result.sort(key=lambda x: (0 if x[0] == "default" else 1, x[0]))
    return result
