"""wificities config — easy interactive configuration."""
import json
from pathlib import Path

import click

from .themes import get_themes_dir, load_theme_json
from .project import enter_project_dir


@click.group("config", invoke_without_command=True)
@click.pass_context
def config_group(ctx):
    """Configure your wificity (interactive menu if no subcommand)."""
    if ctx.invoked_subcommand is None:
        _interactive_config()


@config_group.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str):
    """Set a config or theme variable. Example: wificities config set site_title 'My Site'"""
    project_dir = enter_project_dir()

    # Determine if it's a runtime config key or a theme variable
    runtime_keys = {
        "ssid", "password", "channel",
        "max_connections", "site_name",
        "guestbook_max_entries", "guestbook_rate_limit_seconds",
    }

    if key in runtime_keys:
        _update_json(project_dir / "config.json", key, _parse_value(value))
        click.echo(f"  config.json: {key} = {value}")
    else:
        wf = project_dir / "wificities.json"
        if wf.exists():
            data = json.loads(wf.read_text(encoding="utf-8"))
            if "variables" not in data:
                data["variables"] = {}
            data["variables"][key] = _parse_value(value)
            wf.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                          encoding="utf-8")
            click.echo(f"  wificities.json: variables.{key} = {value}")
        else:
            click.echo("Error: wificities.json not found. Are you in a wificity project?")
            raise SystemExit(1)


@config_group.command("get")
@click.argument("key")
def config_get(key: str):
    """Get a config or theme variable value."""
    project_dir = enter_project_dir()

    # Check config.json
    cfg_path = project_dir / "config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        if key in cfg:
            click.echo(cfg[key])
            return

    # Check wificities.json variables
    wf_path = project_dir / "wificities.json"
    if wf_path.exists():
        wf = json.loads(wf_path.read_text(encoding="utf-8"))
        val = wf.get("variables", {}).get(key)
        if val is not None:
            click.echo(val)
            return

    click.echo(f"Key '{key}' not found.")


@config_group.command("palette")
@click.argument("name", required=False)
def config_palette(name: str | None):
    """Apply a color palette. Run without args to see available palettes."""
    project_dir = enter_project_dir()
    wf_path = project_dir / "wificities.json"

    if not wf_path.exists():
        click.echo("Error: wificities.json not found.")
        raise SystemExit(1)

    wf = json.loads(wf_path.read_text(encoding="utf-8"))
    theme_name = wf.get("theme", "default")
    theme_json = load_theme_json(theme_name)

    if not theme_json or "palettes" not in theme_json:
        click.echo(f"Theme '{theme_name}' doesn't have palettes.")
        raise SystemExit(1)

    palettes = theme_json["palettes"]

    if name is None:
        # List palettes
        current = wf.get("variables", {}).get("palette", "midnight")
        click.echo("\nAvailable palettes:\n")
        for pid, pdata in palettes.items():
            marker = " *" if pid == current else "  "
            pname = pdata.get("name", pid) if isinstance(pdata, dict) else pid
            desc = pdata.get("description", "") if isinstance(pdata, dict) else ""
            click.echo(f"  {marker} {pid:15s} {desc}")
        click.echo(f"\n  * = current")
        click.echo(f"\n  Usage: wificities config palette <name>")
        return

    if name not in palettes:
        click.echo(f"Palette '{name}' not found. Available: {', '.join(palettes.keys())}")
        raise SystemExit(1)

    # Apply palette
    palette_data = palettes[name]
    if "variables" not in wf:
        wf["variables"] = {}

    wf["variables"]["palette"] = name

    # Copy palette colors into variables
    color_keys = [
        "bg_color", "bg_secondary", "text_color", "text_secondary",
        "accent_color", "accent_secondary", "link_color", "link_hover",
        "border_color", "header_bg", "header_accent",
    ]
    for key in color_keys:
        if key in palette_data:
            wf["variables"][key] = palette_data[key]

    wf_path.write_text(json.dumps(wf, indent=2, ensure_ascii=False),
                        encoding="utf-8")

    pname = palette_data.get("name", name)
    click.echo(f"\n  \u2705 Applied palette: {pname}")
    click.echo(f"     Run 'wificities build' to see changes.")


@config_group.command("header")
@click.argument("style", required=False)
def config_header(style: str | None):
    """Set the header style. Options: banner, minimal, centered."""
    styles = ["banner", "minimal", "centered"]

    if style is None:
        project_dir = enter_project_dir()
        wf_path = project_dir / "wificities.json"
        current = "banner"
        if wf_path.exists():
            wf = json.loads(wf_path.read_text(encoding="utf-8"))
            current = wf.get("variables", {}).get("header_style", "banner")

        click.echo("\nHeader styles:\n")
        click.echo(f"  {'*' if current=='banner' else ' '} banner     Full-width banner with animated accent bar")
        click.echo(f"  {'*' if current=='minimal' else ' '} minimal    Simple inline text, no decoration")
        click.echo(f"  {'*' if current=='centered' else ' '} centered   Centered block with decorative borders")
        click.echo(f"\n  * = current")
        click.echo(f"\n  Usage: wificities config header <style>")
        return

    if style not in styles:
        click.echo(f"Unknown style. Options: {', '.join(styles)}")
        raise SystemExit(1)

    project_dir = enter_project_dir()
    wf_path = project_dir / "wificities.json"
    if not wf_path.exists():
        click.echo("Error: wificities.json not found.")
        raise SystemExit(1)

    wf = json.loads(wf_path.read_text(encoding="utf-8"))
    if "variables" not in wf:
        wf["variables"] = {}
    wf["variables"]["header_style"] = style
    wf_path.write_text(json.dumps(wf, indent=2, ensure_ascii=False),
                        encoding="utf-8")

    click.echo(f"\n  \u2705 Header style set to: {style}")


@config_group.command("show")
def config_show():
    """Show all current configuration."""
    project_dir = enter_project_dir()

    click.echo("\n--- config.json (runtime) ---\n")
    cfg_path = project_dir / "config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        for k, v in cfg.items():
            if k == "plugins":
                continue
            else:
                click.echo(f"  {k}: {v}")

    click.echo("\n--- wificities.json (theme variables) ---\n")
    wf_path = project_dir / "wificities.json"
    if wf_path.exists():
        wf = json.loads(wf_path.read_text(encoding="utf-8"))
        click.echo(f"  mode: {wf.get('mode', 'raw')}")
        click.echo(f"  theme: {wf.get('theme', 'none')}")
        for k, v in wf.get("variables", {}).items():
            if isinstance(v, list):
                click.echo(f"  {k}: [{len(v)} items]")
            elif isinstance(v, bool):
                click.echo(f"  {k}: {'yes' if v else 'no'}")
            else:
                click.echo(f"  {k}: {v}")
        plugins = wf.get("plugins", {})
        if plugins:
            click.echo(f"\n  plugins: {', '.join(plugins.keys())}")

    click.echo()


def _interactive_config():
    """Interactive configuration menu."""
    project_dir = enter_project_dir()
    wf_path = project_dir / "wificities.json"

    if not wf_path.exists():
        click.echo("Error: wificities.json not found. Are you in a wificity project?")
        raise SystemExit(1)

    wf = json.loads(wf_path.read_text(encoding="utf-8"))
    cfg_path = project_dir / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}

    variables = wf.get("variables", {})

    click.echo(f"\n\U0001f3d9  WifiCity Configuration\n")

    while True:
        click.echo("  [1] Site name & bio")
        click.echo("  [2] WiFi settings (SSID, password)")
        click.echo("  [3] Color palette")
        click.echo("  [4] Header style")
        click.echo("  [5] Toggle features (guestbook, marquee, etc.)")
        click.echo("  [6] Show all settings")
        click.echo("  [0] Done")

        choice = click.prompt("\nChoice", type=int, default=0)

        if choice == 0:
            break

        elif choice == 1:
            variables["site_title"] = click.prompt(
                "Site title", default=variables.get("site_title", "My WifiCity"))
            variables["owner_name"] = click.prompt(
                "Your name", default=variables.get("owner_name", "Anonymous"))
            variables["bio"] = click.prompt(
                "Bio/welcome message", default=variables.get("bio", ""))
            cfg["site_name"] = variables["site_title"]

        elif choice == 2:
            cfg["ssid"] = click.prompt(
                "WiFi SSID", default=cfg.get("ssid", "WifiCity"))
            pw = click.prompt(
                "WiFi password (empty=open)", default=cfg.get("password", ""))
            cfg["password"] = pw

        elif choice == 3:
            config_palette.invoke(click.Context(config_palette))

        elif choice == 4:
            config_header.invoke(click.Context(config_header))

        elif choice == 5:
            toggles = [
                ("show_guestbook", "Guestbook"),
                ("show_visitor_counter", "Visitor counter"),
                ("show_sidebar", "Sidebar"),
                ("show_marquee", "Scrolling marquee"),
                ("show_construction", "Under construction banner"),
            ]
            click.echo()
            for key, label in toggles:
                current = variables.get(key, True)
                new_val = click.confirm(f"  {label}?", default=current)
                variables[key] = new_val

        elif choice == 6:
            config_show.invoke(click.Context(config_show))

        click.echo()

    # Save
    wf["variables"] = variables
    wf_path.write_text(json.dumps(wf, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    if cfg_path.exists():
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False),
                            encoding="utf-8")

    click.echo("\n\u2705 Configuration saved!")
    click.echo("   Run 'wificities build' to apply changes.\n")


def _update_json(path: Path, key: str, value):
    """Update a single key in a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data[key] = value
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                    encoding="utf-8")


def _parse_value(value: str):
    """Parse a string value into the appropriate type."""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value
