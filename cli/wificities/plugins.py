"""wificities plugin — manage plugins."""
import json
import shutil
import subprocess
from pathlib import Path

import click

from .project import enter_project_dir


def _get_plugins_dir() -> Path:
    """Get the built-in plugins directory."""
    cli_dir = Path(__file__).resolve().parent.parent.parent
    return cli_dir / "plugins"


def _get_firmware_dir() -> Path:
    """Get the firmware directory."""
    cli_dir = Path(__file__).resolve().parent.parent.parent
    return cli_dir / "firmware"


@click.group("plugin")
def plugin_group():
    """Manage plugins."""
    pass


@plugin_group.command("list")
def plugin_list():
    """List available and installed plugins."""
    plugins_dir = _get_plugins_dir()

    # List available
    click.echo("\nAvailable plugins:\n")

    frontend_plugins = []
    backend_plugins = []

    if plugins_dir.exists():
        for d in sorted(plugins_dir.iterdir()):
            if d.is_dir() and (d / "plugin.json").exists():
                try:
                    data = json.loads(
                        (d / "plugin.json").read_text(encoding="utf-8"))
                    entry = (d.name, data.get("description", ""),
                             data.get("type", "frontend"))
                    if entry[2] == "backend":
                        backend_plugins.append(entry)
                    else:
                        frontend_plugins.append(entry)
                except (json.JSONDecodeError, OSError):
                    pass

    if frontend_plugins:
        click.echo("  FRONTEND")
        for name, desc, _ in frontend_plugins:
            click.echo(f"    {name:25s} {desc}")

    if backend_plugins:
        click.echo("\n  BACKEND")
        for name, desc, _ in backend_plugins:
            click.echo(f"    {name:25s} {desc}")

    if not frontend_plugins and not backend_plugins:
        click.echo("  No plugins found.")

    # List installed (if inside a project)
    from .project import find_project_dir
    proj = find_project_dir()
    wificities_json = (proj / "wificities.json") if proj else None
    if wificities_json and wificities_json.exists():
        manifest = json.loads(wificities_json.read_text(encoding="utf-8"))
        installed = manifest.get("plugins", {})
        if installed:
            click.echo("\n  INSTALLED in this project:")
            for name, version in installed.items():
                click.echo(f"    {name:25s} {version}")

    click.echo()


@plugin_group.command("add")
@click.argument("name")
def plugin_add(name: str):
    """Add a plugin to the current project."""
    project_dir = enter_project_dir()
    plugins_dir = _get_plugins_dir()

    # Resolve plugin source
    plugin_source = None
    source_type = "builtin"

    # Check built-in
    builtin_path = plugins_dir / name
    if builtin_path.exists() and (builtin_path / "plugin.json").exists():
        plugin_source = builtin_path

    # Check local path
    elif Path(name).exists() and (Path(name) / "plugin.json").exists():
        plugin_source = Path(name).resolve()
        source_type = "local"

    # Check git URL
    elif name.startswith("http"):
        click.echo(f"  Cloning {name}...")
        cache_dir = project_dir / ".wificities" / "plugins"
        cache_dir.mkdir(parents=True, exist_ok=True)
        clone_name = name.split("/")[-1].replace(".git", "")
        clone_dest = cache_dir / clone_name

        if clone_dest.exists():
            shutil.rmtree(clone_dest)

        result = subprocess.run(
            ["git", "clone", "--depth", "1", name, str(clone_dest)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            click.echo(f"  Failed to clone: {result.stderr[:200]}")
            raise SystemExit(1)

        plugin_source = clone_dest
        source_type = "git"

    if plugin_source is None:
        click.echo(f"Plugin '{name}' not found.")
        raise SystemExit(1)

    # Read plugin.json
    plugin_json = json.loads(
        (plugin_source / "plugin.json").read_text(encoding="utf-8"))
    plugin_id = plugin_json.get("id", name)
    plugin_type = plugin_json.get("type", "frontend")
    plugin_version = plugin_json.get("version", "1.0.0")

    click.echo(f"  Installing {plugin_json.get('name', name)} v{plugin_version} "
               f"({plugin_type})...")

    # Cache plugin locally
    cache_dir = project_dir / ".wificities" / "plugins" / plugin_id
    if source_type != "git":  # git already cloned to cache
        cache_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(plugin_source, cache_dir, dirs_exist_ok=True)

    # Handle backend plugins
    if plugin_type == "backend":
        backend_dir = plugin_source / "backend"
        if backend_dir.exists():
            firmware_dir = _get_firmware_dir()
            dest = firmware_dir / "lib" / "plugins" / plugin_id
            dest.mkdir(parents=True, exist_ok=True)

            for f in backend_dir.iterdir():
                if f.is_file() and f.suffix in (".h", ".cpp", ".c"):
                    shutil.copy2(f, dest / f.name)

            # Regenerate plugin registry
            _regenerate_registry(firmware_dir)
            click.echo(f"  Backend source copied. Firmware will be recompiled on next build.")

    # Update wificities.json
    wificities_path = project_dir / "wificities.json"
    if wificities_path.exists():
        manifest = json.loads(wificities_path.read_text(encoding="utf-8"))
    else:
        manifest = {"mode": "raw", "plugins": {}}

    if "plugins" not in manifest:
        manifest["plugins"] = {}
    manifest["plugins"][plugin_id] = plugin_version

    wificities_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # Update config.json with plugin defaults
    config_path = project_dir / "config.json"
    if config_path.exists() and "config" in plugin_json:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if "plugins" not in config:
            config["plugins"] = {}
        if plugin_id not in config["plugins"]:
            defaults = {}
            for key, val in plugin_json["config"].items():
                if isinstance(val, dict):
                    defaults[key] = val.get("default", "")
                else:
                    defaults[key] = val
            config["plugins"][plugin_id] = defaults
            config_path.write_text(
                json.dumps(config, indent=2, ensure_ascii=False),
                encoding="utf-8")

    click.echo(f"\n\u2705 Plugin '{plugin_id}' installed!")
    if plugin_type == "frontend":
        click.echo(f"   Use in templates: {{{{> plugin:{plugin_id}}}}}")
    click.echo(f"   Run 'wificities build' to include it in your site.")


@plugin_group.command("remove")
@click.argument("name")
def plugin_remove(name: str):
    """Remove a plugin from the current project."""
    project_dir = enter_project_dir()

    # Remove from wificities.json
    wificities_path = project_dir / "wificities.json"
    if wificities_path.exists():
        manifest = json.loads(wificities_path.read_text(encoding="utf-8"))
        plugins = manifest.get("plugins", {})
        if name in plugins:
            del plugins[name]
            wificities_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8")

    # Remove cached files
    cache_dir = project_dir / ".wificities" / "plugins" / name
    if cache_dir.exists():
        shutil.rmtree(cache_dir)

    # Remove backend source
    firmware_dir = _get_firmware_dir()
    backend_dest = firmware_dir / "lib" / "plugins" / name
    if backend_dest.exists():
        shutil.rmtree(backend_dest)
        _regenerate_registry(firmware_dir)

    click.echo(f"\u2705 Plugin '{name}' removed.")


def _regenerate_registry(firmware_dir: Path):
    """Regenerate the plugin_registry.h file."""
    plugins_lib_dir = firmware_dir / "lib" / "plugins"
    registry_path = plugins_lib_dir / "plugin_registry.h"

    # Find all plugins (directories with .cpp files, exclude the registry itself)
    plugins = []
    for d in sorted(plugins_lib_dir.iterdir()):
        if d.is_dir():
            # Look for plugin.json in the cached plugin dir to get symbol name
            # or just derive it from directory name
            symbol = d.name.replace("-", "_") + "_plugin"
            plugins.append((d.name, symbol))

    # Generate registry
    lines = [
        "// AUTO-GENERATED by wificities CLI — do not edit manually",
        "#ifndef PLUGIN_REGISTRY_H",
        "#define PLUGIN_REGISTRY_H",
        "",
        '#include "plugin_api.h"',
        "",
    ]

    if plugins:
        lines.append("// Plugin extern declarations")
        for _, symbol in plugins:
            lines.append(f"extern WifiCitiesPlugin {symbol};")

        lines.append("")
        lines.append("static WifiCitiesPlugin* registered_plugins[] = {")
        for _, symbol in plugins:
            lines.append(f"    &{symbol},")
        lines.append("};")
        lines.append(f"")
        lines.append(f"static const int PLUGIN_COUNT = {len(plugins)};")
    else:
        lines.append("// No backend plugins installed.")
        lines.append("")
        lines.append("static WifiCitiesPlugin* registered_plugins[] = {};")
        lines.append("static const int PLUGIN_COUNT = 0;")

    lines.extend(["", "#endif // PLUGIN_REGISTRY_H", ""])

    registry_path.write_text("\n".join(lines), encoding="utf-8")
