"""wificities plugin — manage plugins via git repos."""
import json
from pathlib import Path

import click

from .project import enter_project_dir, find_project_dir
from .registry import (
    resolve_repo_url, clone_or_update, remove_package,
    get_installed_dir, list_registry,
)


def _get_firmware_dir() -> Path:
    from .registry import _repo_root
    return _repo_root() / "firmware"


@click.group("plugin")
def plugin_group():
    """Manage plugins."""
    pass


@plugin_group.command("list")
def plugin_list():
    """List available and installed plugins."""
    click.echo("\n  Available plugins:\n")

    entries = list_registry("plugins")
    if entries:
        for name, desc, verified in entries:
            v = " [verified]" if verified else ""
            click.echo(f"    {name:25s} {desc}{v}")
    else:
        click.echo("    No plugins in registry.")

    proj = find_project_dir()
    if proj:
        wf_path = proj / "wificities.json"
        if wf_path.exists():
            wf = json.loads(wf_path.read_text(encoding="utf-8"))
            installed = wf.get("plugins", {})
            if installed:
                click.echo("\n  Installed:\n")
                for name in installed:
                    exists = get_installed_dir(proj, "plugins", name).exists()
                    status = "ok" if exists else "missing"
                    click.echo(f"    {name:25s} ({status})")

    click.echo()


@plugin_group.command("add")
@click.argument("name")
def plugin_add(name: str):
    """Add a plugin. Use a name from the registry or a git URL."""
    project_dir = enter_project_dir()

    url = resolve_repo_url(name, "plugins")
    if url is None:
        click.echo(f"  '{name}' not in registry. Use a git URL:")
        click.echo(f"  ./wificities plugin add https://github.com/user/repo")
        raise SystemExit(1)

    # Derive clean name
    if name.startswith("http") or name.startswith("git@"):
        plugin_name = name.rstrip("/").split("/")[-1].replace(".git", "")
        if plugin_name.startswith("wificities-plugin-"):
            plugin_name = plugin_name[len("wificities-plugin-"):]
    else:
        plugin_name = name

    dest = get_installed_dir(project_dir, "plugins", plugin_name)

    click.echo(f"  Installing {plugin_name}...")
    if not clone_or_update(url, dest):
        click.echo(f"  Failed to clone {url}")
        raise SystemExit(1)

    # Read plugin.json if it exists
    pjson_path = dest / "plugin.json"
    ptype = "frontend"
    if pjson_path.exists():
        pdata = json.loads(pjson_path.read_text(encoding="utf-8"))
        plugin_name = pdata.get("id", plugin_name)
        ptype = pdata.get("type", "frontend")

    # Handle backend plugins
    if ptype == "backend":
        backend_dir = dest / "backend"
        if backend_dir.exists():
            import shutil
            firmware_dir = _get_firmware_dir()
            fw_dest = firmware_dir / "lib" / "plugins" / plugin_name
            fw_dest.mkdir(parents=True, exist_ok=True)
            for f in backend_dir.iterdir():
                if f.is_file() and f.suffix in (".h", ".cpp", ".c"):
                    shutil.copy2(f, fw_dest / f.name)
            _regenerate_registry(firmware_dir)
            click.echo(f"  Backend plugin — firmware recompiles on next build.")

    # Update wificities.json
    wf_path = project_dir / "wificities.json"
    wf = json.loads(wf_path.read_text(encoding="utf-8")) if wf_path.exists() else {"mode": "raw"}
    wf.setdefault("plugins", {})[plugin_name] = url
    wf_path.write_text(json.dumps(wf, indent=2, ensure_ascii=False), encoding="utf-8")

    click.echo(f"\n  Installed: {plugin_name}")
    if ptype == "frontend":
        click.echo(f"  Use in templates: {{{{> plugin:{plugin_name}}}}}")
    click.echo(f"  Run './wificities build' to apply.")


@plugin_group.command("remove")
@click.argument("name")
def plugin_remove(name: str):
    """Remove a plugin."""
    project_dir = enter_project_dir()

    wf_path = project_dir / "wificities.json"
    if wf_path.exists():
        wf = json.loads(wf_path.read_text(encoding="utf-8"))
        if name in wf.get("plugins", {}):
            del wf["plugins"][name]
            wf_path.write_text(json.dumps(wf, indent=2, ensure_ascii=False), encoding="utf-8")

    remove_package(get_installed_dir(project_dir, "plugins", name))

    firmware_dir = _get_firmware_dir()
    backend_dest = firmware_dir / "lib" / "plugins" / name
    if backend_dest.exists():
        import shutil
        shutil.rmtree(backend_dest)
        _regenerate_registry(firmware_dir)

    click.echo(f"  Removed: {name}")


@plugin_group.command("update")
@click.argument("name", required=False)
def plugin_update(name: str | None):
    """Update plugins to latest version."""
    project_dir = enter_project_dir()

    wf_path = project_dir / "wificities.json"
    if not wf_path.exists():
        click.echo("  No plugins installed.")
        return

    wf = json.loads(wf_path.read_text(encoding="utf-8"))
    plugins = wf.get("plugins", {})
    targets = {name: plugins[name]} if name and name in plugins else plugins

    for pname, url in targets.items():
        dest = get_installed_dir(project_dir, "plugins", pname)
        click.echo(f"  Updating {pname}...")
        clone_or_update(url, dest)
        click.echo(f"  {pname} updated.")


def _regenerate_registry(firmware_dir: Path):
    """Regenerate plugin_registry.h for backend plugins."""
    plugins_lib_dir = firmware_dir / "lib" / "plugins"
    registry_path = plugins_lib_dir / "plugin_registry.h"

    plugins = []
    for d in sorted(plugins_lib_dir.iterdir()):
        if d.is_dir():
            symbol = d.name.replace("-", "_") + "_plugin"
            plugins.append((d.name, symbol))

    lines = [
        "// AUTO-GENERATED — do not edit",
        "#ifndef PLUGIN_REGISTRY_H",
        "#define PLUGIN_REGISTRY_H",
        '#include "plugin_api.h"',
        "",
    ]

    if plugins:
        for _, symbol in plugins:
            lines.append(f"extern WifiCitiesPlugin {symbol};")
        lines.append("")
        lines.append("static WifiCitiesPlugin* registered_plugins[] = {")
        for _, symbol in plugins:
            lines.append(f"    &{symbol},")
        lines.append("};")
        lines.append(f"static const int PLUGIN_COUNT = {len(plugins)};")
    else:
        lines.append("static WifiCitiesPlugin* registered_plugins[] = {};")
        lines.append("static const int PLUGIN_COUNT = 0;")

    lines.extend(["", "#endif", ""])
    registry_path.write_text("\n".join(lines), encoding="utf-8")
