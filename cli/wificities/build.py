"""wificities build — compile site into flashable output."""
import json
import shutil
from datetime import date
from pathlib import Path

import click

try:
    import mistune
except ImportError:
    mistune = None

from . import __version__
from .template_engine import render
from .themes import load_theme_json, ensure_theme, get_theme_dir
from .registry import get_installed_dir
from .project import enter_project_dir


@click.command("build")
@click.option("--size-report", is_flag=True, help="Show detailed size breakdown")
def build_cmd(size_report: bool):
    """Build the site into flashable output."""
    project_dir = enter_project_dir()
    build_dir = project_dir / "build"

    # Detect mode
    wificities_path = project_dir / "wificities.json"
    config_path = project_dir / "config.json"

    if not config_path.exists():
        click.echo("Error: config.json not found in current directory.")
        raise SystemExit(1)

    # Clean build directory
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir()
    (build_dir / "data").mkdir()

    # Copy config
    shutil.copy2(config_path, build_dir / "config.json")

    if wificities_path.exists():
        manifest = json.loads(wificities_path.read_text(encoding="utf-8"))
        mode = manifest.get("mode", "raw")
    else:
        manifest = None
        mode = "raw"

    if mode == "theme":
        _build_theme_mode(project_dir, build_dir, manifest)
    else:
        _build_raw_mode(project_dir, build_dir, manifest)

    # Process plugins
    _process_plugins(project_dir, build_dir, manifest)

    # Validate output
    public_dir = build_dir / "public"
    if not (public_dir / "index.html").exists():
        click.echo("Warning: build/public/index.html not found!")

    # Size report
    total_size = _dir_size(build_dir)
    max_size = 2_500_000  # ~2.4MB LittleFS

    click.echo(f"\n\u2705 Build complete!\n")

    page_count = len(list(public_dir.rglob("*.html"))) if public_dir.exists() else 0
    pct = round(total_size / max_size * 100)

    click.echo(f"  Pages:      {page_count}")
    click.echo(f"  Total size: {total_size // 1024} KB / {max_size // 1024} KB ({pct}%)")

    if pct > 90:
        click.echo(f"  \u26a0\ufe0f  Getting tight! Consider reducing image sizes.")
    if pct > 100:
        click.echo(f"  \u274c  TOO LARGE! Site won't fit on ESP32.")

    click.echo(f"\n  Output: build/")

    if size_report:
        click.echo(f"\n\U0001f4ca Size Breakdown:\n")
        _print_size_report(build_dir, "  ")


def _build_theme_mode(project_dir: Path, build_dir: Path,
                      manifest: dict):
    """Build a theme-mode project."""
    theme_name = manifest.get("theme", "")

    # Ensure theme is installed (clones from git if missing)
    theme_dir = ensure_theme(project_dir, theme_name)
    if theme_dir is None:
        click.echo(f"Error: Theme '{theme_name}' not found. Run: ./wificities theme add {theme_name}")
        raise SystemExit(1)

    theme_json = load_theme_json(project_dir, theme_name)
    if not theme_json:
        click.echo(f"Error: Could not load theme.json for '{theme_name}'")
        raise SystemExit(1)

    # Build variables: theme defaults → global → built-ins
    variables = {}

    # Theme defaults
    for var_name, var_def in theme_json.get("variables", {}).items():
        if isinstance(var_def, dict):
            variables[var_name] = var_def.get("default", "")
        else:
            variables[var_name] = var_def

    # Global variables from manifest
    variables.update(manifest.get("variables", {}))

    # Resolve palette: if a palette name is set, expand its colors
    # into variables (only for keys the user hasn't manually overridden)
    palette_name = variables.get("palette", "")
    if palette_name and "palettes" in theme_json:
        palette_data = theme_json["palettes"].get(palette_name, {})
        color_keys = [
            "bg_color", "bg_secondary", "text_color", "text_secondary",
            "accent_color", "accent_secondary", "link_color", "link_hover",
            "border_color", "header_bg", "header_accent",
        ]
        for key in color_keys:
            if key in palette_data and key not in manifest.get("variables", {}):
                variables[key] = palette_data[key]

    # Resolve header style flags: convert header_style="banner"
    # into header_style_banner=True, header_style_minimal=False, etc.
    header_style = variables.get("header_style", "banner")
    for style in ("banner", "minimal", "centered"):
        variables[f"header_style_{style}"] = (header_style == style)

    # Built-in variables
    variables["year"] = str(date.today().year)
    variables["build_date"] = str(date.today())
    variables["wificities_version"] = __version__

    # Load partials
    partials_dir = theme_dir / "partials"

    # Load plugin partials
    plugin_partials = _load_plugin_partials(project_dir, manifest)

    # Build each page
    public_dir = build_dir / "public"
    public_dir.mkdir(parents=True, exist_ok=True)

    pages = manifest.get("pages", {})
    for url_path, page_def in pages.items():
        click.echo(f"  Building {url_path}")

        template_name = page_def.get("template", "page")
        content_path = page_def.get("content")
        page_vars = page_def.get("variables", {})

        # Merge page variables (highest priority)
        merged_vars = {**variables, **page_vars}
        merged_vars["page_url"] = url_path

        # Load content
        content_html = ""
        if content_path:
            full_content_path = project_dir / content_path
            if full_content_path.exists():
                raw = full_content_path.read_text(encoding="utf-8")
                if full_content_path.suffix == ".md":
                    content_html = _markdown_to_html(raw)
                else:
                    content_html = raw
            else:
                click.echo(f"  Warning: Content file not found: {content_path}")

        merged_vars["content"] = content_html

        # Load template
        template_path = theme_dir / "templates" / f"{template_name}.html"
        if not template_path.exists():
            click.echo(f"  Warning: Template not found: {template_name}.html")
            template_str = "{{{content}}}"
        else:
            template_str = template_path.read_text(encoding="utf-8")

        # Render template (inserts content)
        rendered_template = render(template_str, merged_vars,
                                   partials_dir, plugin_partials)

        # Load layout
        template_def = theme_json.get("templates", {}).get(template_name, {})
        layout_name = template_def.get("layout",
                                        theme_json.get("default_layout", "base"))
        layout_path = theme_dir / "layouts" / f"{layout_name}.html"

        if layout_path.exists():
            layout_str = layout_path.read_text(encoding="utf-8")
            # Insert rendered template into layout's {{{content}}}
            merged_vars["content"] = rendered_template
            final_html = render(layout_str, merged_vars,
                                partials_dir, plugin_partials)
        else:
            final_html = rendered_template

        # Write output
        if url_path == "/":
            out_path = public_dir / "index.html"
        else:
            out_dir = public_dir / url_path.strip("/")
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / "index.html"

        out_path.write_text(final_html, encoding="utf-8")

    # Copy theme assets
    theme_assets = theme_dir / "assets"
    if theme_assets.exists():
        for f in theme_assets.rglob("*"):
            if f.is_file():
                rel = f.relative_to(theme_assets)
                dest = public_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)

    # Copy user content assets
    user_assets = project_dir / "content" / "assets"
    if user_assets.exists():
        dest_assets = public_dir / "assets"
        dest_assets.mkdir(parents=True, exist_ok=True)
        for f in user_assets.rglob("*"):
            if f.is_file():
                rel = f.relative_to(user_assets)
                dest = dest_assets / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)


def _build_raw_mode(project_dir: Path, build_dir: Path,
                    manifest: dict | None):
    """Build a raw-mode project."""
    public_src = project_dir / "public"
    public_dest = build_dir / "public"

    if not public_src.exists():
        click.echo("Error: public/ directory not found.")
        raise SystemExit(1)

    shutil.copytree(public_src, public_dest, dirs_exist_ok=True)


def _process_plugins(project_dir: Path, build_dir: Path,
                     manifest: dict | None):
    """Copy plugin frontend assets into the build."""
    if not manifest:
        return

    plugins = manifest.get("plugins", {})
    if not plugins:
        return

    public_dir = build_dir / "public"

    for plugin_name in plugins:
        plugin_dir = get_installed_dir(project_dir, "plugins", plugin_name)
        if not plugin_dir.exists():
            click.echo(f"  Warning: Plugin '{plugin_name}' not installed. Run: ./wificities plugin add {plugin_name}")
            continue

        # Copy frontend assets
        frontend_dir = plugin_dir / "frontend"
        assets_dir = plugin_dir / "assets"
        dest = public_dir / "plugins" / plugin_name

        if frontend_dir.exists():
            dest.mkdir(parents=True, exist_ok=True)
            for f in frontend_dir.rglob("*"):
                if f.is_file() and f.suffix in (".css", ".js"):
                    shutil.copy2(f, dest / f.name)

        if assets_dir.exists():
            dest.mkdir(parents=True, exist_ok=True)
            for f in assets_dir.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(assets_dir)
                    d = dest / rel
                    d.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, d)


def _load_plugin_partials(project_dir: Path,
                          manifest: dict) -> dict[str, str]:
    """Load HTML partials from installed plugins."""
    partials = {}
    plugins = manifest.get("plugins", {})

    for plugin_name in plugins:
        plugin_dir = get_installed_dir(project_dir, "plugins", plugin_name)
        if not plugin_dir.exists():
            continue

        pjson_path = plugin_dir / "plugin.json"
        if pjson_path.exists():
            pjson = json.loads(pjson_path.read_text(encoding="utf-8"))
            html_file = pjson.get("frontend", {}).get("html")
            if html_file:
                html_path = plugin_dir / html_file
                if html_path.exists():
                    partials[plugin_name] = html_path.read_text(encoding="utf-8")

    return partials


def _markdown_to_html(text: str) -> str:
    """Convert Markdown to HTML."""
    if mistune is not None:
        md = mistune.create_markdown()
        return md(text)
    else:
        # Fallback: wrap in <p> tags, handle basic formatting
        lines = text.strip().split("\n\n")
        parts = []
        for block in lines:
            block = block.strip()
            if block.startswith("# "):
                parts.append(f"<h1>{block[2:]}</h1>")
            elif block.startswith("## "):
                parts.append(f"<h2>{block[3:]}</h2>")
            elif block.startswith("### "):
                parts.append(f"<h3>{block[4:]}</h3>")
            elif block.startswith("- "):
                items = block.split("\n")
                li = "".join(f"<li>{l.lstrip('- ')}</li>" for l in items)
                parts.append(f"<ul>{li}</ul>")
            else:
                # Bold
                import re
                block = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', block)
                block = re.sub(r'\*(.+?)\*', r'<em>\1</em>', block)
                parts.append(f"<p>{block}</p>")
        return "\n".join(parts)


def _dir_size(path: Path) -> int:
    """Calculate total size of a directory."""
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _print_size_report(path: Path, indent: str = ""):
    """Print a size breakdown of the build directory."""
    for item in sorted(path.iterdir()):
        if item.is_file():
            size = item.stat().st_size
            click.echo(f"{indent}{item.name:40s} {size // 1024:>6d} KB")
        elif item.is_dir():
            size = _dir_size(item)
            click.echo(f"{indent}{item.name + '/':40s} {size // 1024:>6d} KB")
