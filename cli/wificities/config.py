"""wificities config — easy interactive configuration."""
import json
from pathlib import Path

import click

from .themes import load_theme_json
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
    """Set a config or theme variable."""
    project_dir = enter_project_dir()

    runtime_keys = {
        "ssid", "password", "channel",
        "max_connections", "site_name",
        "guestbook_max_entries", "guestbook_rate_limit_seconds",
    }

    if key in runtime_keys:
        _update_json(project_dir / "config.json", key, _parse_value(value))
        click.echo(f"  {key} = {value}")
    else:
        wf = _load_manifest(project_dir)
        wf.setdefault("variables", {})[key] = _parse_value(value)
        _save_manifest(project_dir, wf)
        click.echo(f"  {key} = {value}")


@config_group.command("get")
@click.argument("key")
def config_get(key: str):
    """Get a config or theme variable value."""
    project_dir = enter_project_dir()

    cfg_path = project_dir / "config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        if key in cfg:
            click.echo(cfg[key])
            return

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
    """Apply a color palette, or list available ones."""
    project_dir = enter_project_dir()
    if name is None:
        _show_palettes(project_dir)
    else:
        _apply_palette(project_dir, name)


@config_group.command("header")
@click.argument("style", required=False)
def config_header(style: str | None):
    """Set header style (banner, minimal, centered)."""
    project_dir = enter_project_dir()
    if style is None:
        _show_header_styles(project_dir)
    else:
        _set_header_style(project_dir, style)


@config_group.command("show")
def config_show():
    """Show all current configuration."""
    project_dir = enter_project_dir()
    _print_all_settings(project_dir)


# ====================================================================
# Core logic (used by both CLI commands and interactive menu)
# ====================================================================

def _load_manifest(project_dir: Path) -> dict:
    wf_path = project_dir / "wificities.json"
    if wf_path.exists():
        return json.loads(wf_path.read_text(encoding="utf-8"))
    return {"mode": "raw", "plugins": {}}


def _save_manifest(project_dir: Path, wf: dict):
    (project_dir / "wificities.json").write_text(
        json.dumps(wf, indent=2, ensure_ascii=False), encoding="utf-8")


def _get_theme_data(project_dir: Path) -> dict | None:
    wf = _load_manifest(project_dir)
    return load_theme_json(project_dir, wf.get("theme", "default"))


def _show_palettes(project_dir: Path):
    wf = _load_manifest(project_dir)
    theme_json = _get_theme_data(project_dir)
    if not theme_json or "palettes" not in theme_json:
        click.echo("  No palettes available for this theme.")
        return

    current = wf.get("variables", {}).get("palette", "")
    click.echo("")
    for pid, pdata in theme_json["palettes"].items():
        marker = " *" if pid == current else "  "
        pname = pdata.get("name", pid)
        desc = pdata.get("description", "")
        click.echo(f"  {marker} {pid:15s} {desc}")
    click.echo(f"\n  * = current\n")


def _apply_palette(project_dir: Path, name: str):
    theme_json = _get_theme_data(project_dir)
    if not theme_json or "palettes" not in theme_json:
        click.echo("  No palettes available.")
        return
    palettes = theme_json["palettes"]
    if name not in palettes:
        click.echo(f"  Unknown palette '{name}'. Options: {', '.join(palettes.keys())}")
        return

    wf = _load_manifest(project_dir)
    wf.setdefault("variables", {})["palette"] = name
    color_keys = [
        "bg_color", "bg_secondary", "text_color", "text_secondary",
        "accent_color", "accent_secondary", "link_color", "link_hover",
        "border_color", "header_bg", "header_accent",
    ]
    for key in color_keys:
        if key in palettes[name]:
            wf["variables"][key] = palettes[name][key]
    _save_manifest(project_dir, wf)
    click.echo(f"  Applied: {palettes[name].get('name', name)}")


def _select_palette_interactive(project_dir: Path):
    theme_json = _get_theme_data(project_dir)
    if not theme_json or "palettes" not in theme_json:
        click.echo("  No palettes available.")
        return
    palettes = theme_json["palettes"]
    palette_ids = list(palettes.keys())
    wf = _load_manifest(project_dir)
    current = wf.get("variables", {}).get("palette", "")

    click.echo("")
    for i, pid in enumerate(palette_ids):
        pdata = palettes[pid]
        marker = "*" if pid == current else " "
        click.echo(f"  {marker} [{i+1}] {pdata.get('name', pid):15s} — {pdata.get('description', '')}")

    choice = click.prompt("\n  Palette", type=int, default=0)
    if 1 <= choice <= len(palette_ids):
        _apply_palette(project_dir, palette_ids[choice - 1])
    else:
        click.echo("  No change.")


def _show_header_styles(project_dir: Path):
    wf = _load_manifest(project_dir)
    current = wf.get("variables", {}).get("header_style", "banner")
    styles = {
        "banner": "Full-width banner with animated accent bar",
        "minimal": "Simple inline text, no decoration",
        "centered": "Centered block with decorative borders",
    }
    click.echo("")
    for sid, desc in styles.items():
        marker = "*" if sid == current else " "
        click.echo(f"  {marker} {sid:12s} {desc}")
    click.echo("")


def _set_header_style(project_dir: Path, style: str):
    valid = ["banner", "minimal", "centered"]
    if style not in valid:
        click.echo(f"  Unknown. Options: {', '.join(valid)}")
        return
    wf = _load_manifest(project_dir)
    wf.setdefault("variables", {})["header_style"] = style
    _save_manifest(project_dir, wf)
    click.echo(f"  Header: {style}")


def _select_header_interactive(project_dir: Path):
    _show_header_styles(project_dir)
    styles = ["banner", "minimal", "centered"]
    for i, s in enumerate(styles):
        click.echo(f"  [{i+1}] {s}")
    choice = click.prompt("\n  Choice", type=int, default=0)
    if 1 <= choice <= len(styles):
        _set_header_style(project_dir, styles[choice - 1])
    else:
        click.echo("  No change.")


def _edit_colors_interactive(project_dir: Path):
    wf = _load_manifest(project_dir)
    variables = wf.get("variables", {})

    color_fields = [
        ("bg_color", "Background"),
        ("bg_secondary", "Secondary background"),
        ("text_color", "Text"),
        ("text_secondary", "Secondary text"),
        ("accent_color", "Accent"),
        ("accent_secondary", "Secondary accent"),
        ("link_color", "Links"),
        ("link_hover", "Link hover"),
        ("border_color", "Borders"),
        ("header_accent", "Header accent"),
    ]

    click.echo("\n  Edit colors (press Enter to keep current):\n")
    changed = False
    for key, label in color_fields:
        current = variables.get(key, "#000000")
        new_val = click.prompt(f"  {label:20s}", default=current, show_default=True)
        if new_val != current:
            variables[key] = new_val
            changed = True

    if changed:
        wf["variables"] = variables
        _save_manifest(project_dir, wf)
        click.echo("\n  Colors updated.")
    else:
        click.echo("\n  No changes.")


def _edit_fonts_interactive(project_dir: Path):
    wf = _load_manifest(project_dir)
    variables = wf.get("variables", {})

    font_presets = {
        "1": ("Comic Sans MS", "'Comic Sans MS', 'Chalkboard SE', cursive", "'Comic Sans MS', cursive"),
        "2": ("Courier / Monospace", "'Courier New', 'Lucida Console', monospace", "'Courier New', monospace"),
        "3": ("Times / Serif", "'Times New Roman', 'Georgia', serif", "'Times New Roman', serif"),
        "4": ("Arial / Sans-serif", "'Arial', 'Helvetica', sans-serif", "'Arial', sans-serif"),
        "5": ("Impact / Display", "'Impact', 'Arial Black', sans-serif", "'Arial', sans-serif"),
    }

    click.echo("\n  Font presets:\n")
    for k, (name, _, _) in font_presets.items():
        click.echo(f"  [{k}] {name}")
    click.echo(f"  [0] Custom")

    choice = click.prompt("\n  Choice", default="0")
    if choice in font_presets:
        _, heading, body = font_presets[choice]
        variables["font_heading"] = heading
        variables["font_body"] = body
        click.echo(f"  Font: {font_presets[choice][0]}")
    elif choice == "0":
        variables["font_heading"] = click.prompt("  Heading font CSS",
            default=variables.get("font_heading", "'Comic Sans MS', cursive"))
        variables["font_body"] = click.prompt("  Body font CSS",
            default=variables.get("font_body", "'Courier New', monospace"))

    wf["variables"] = variables
    _save_manifest(project_dir, wf)


def _print_all_settings(project_dir: Path):
    click.echo("\n--- config.json ---\n")
    cfg_path = project_dir / "config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        for k, v in cfg.items():
            if k == "plugins":
                continue
            click.echo(f"  {k}: {v}")

    click.echo("\n--- wificities.json ---\n")
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
    project_dir = enter_project_dir()
    wf = _load_manifest(project_dir)
    cfg_path = project_dir / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    variables = wf.get("variables", {})

    click.echo(f"\n  WifiCity Configuration\n")

    while True:
        click.echo("  [1] Site name & bio")
        click.echo("  [2] WiFi settings (SSID, password)")
        click.echo("  [3] Color palette")
        click.echo("  [4] Edit colors")
        click.echo("  [5] Header style")
        click.echo("  [6] Fonts")
        click.echo("  [7] Toggle features")
        click.echo("  [8] Show all settings")
        click.echo("  [0] Done")

        choice = click.prompt("\n  Choice", type=int, default=0)

        if choice == 0:
            break
        elif choice == 1:
            variables["site_title"] = click.prompt(
                "  Site title", default=variables.get("site_title", "My WifiCity"))
            variables["owner_name"] = click.prompt(
                "  Your name", default=variables.get("owner_name", "Anonymous"))
            variables["bio"] = click.prompt(
                "  Bio", default=variables.get("bio", ""))
            cfg["site_name"] = variables["site_title"]
        elif choice == 2:
            cfg["ssid"] = click.prompt("  WiFi SSID", default=cfg.get("ssid", "WifiCity"))
            cfg["password"] = click.prompt("  WiFi password (empty=open)",
                                            default=cfg.get("password", ""))
        elif choice == 3:
            _select_palette_interactive(project_dir)
            # Reload after palette change
            wf = _load_manifest(project_dir)
            variables = wf.get("variables", {})
        elif choice == 4:
            _edit_colors_interactive(project_dir)
            wf = _load_manifest(project_dir)
            variables = wf.get("variables", {})
        elif choice == 5:
            _select_header_interactive(project_dir)
            wf = _load_manifest(project_dir)
            variables = wf.get("variables", {})
        elif choice == 6:
            _edit_fonts_interactive(project_dir)
            wf = _load_manifest(project_dir)
            variables = wf.get("variables", {})
        elif choice == 7:
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
                variables[key] = click.confirm(f"  {label}?", default=current)
        elif choice == 8:
            _print_all_settings(project_dir)

        click.echo()

    # Save
    wf["variables"] = variables
    _save_manifest(project_dir, wf)
    if cfg_path.exists():
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False),
                            encoding="utf-8")

    click.echo("\n  Saved. Run ./wificities build to apply.\n")


# ====================================================================
# Helpers
# ====================================================================

def _update_json(path: Path, key: str, value):
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data[key] = value
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _parse_value(value: str):
    if value.lower() == "true": return True
    if value.lower() == "false": return False
    try: return int(value)
    except ValueError: pass
    try: return float(value)
    except ValueError: pass
    return value
