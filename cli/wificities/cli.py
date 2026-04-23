"""Main CLI entry point for wificities."""
import shutil
from pathlib import Path

import click

from . import __version__


@click.group()
@click.version_option(version=__version__, prog_name="wificities")
def main():
    """WifiCities — Build and flash portable personal websites to ESP32."""
    pass


@click.command("uninstall")
def uninstall_cmd():
    """Remove venv, build artifacts, and cached files."""
    repo_dir = Path(__file__).resolve().parent.parent.parent

    items = [
        (repo_dir / ".venv", "Virtual environment"),
        (repo_dir / "firmware" / ".pio", "PlatformIO build cache"),
    ]

    # Find project build dirs
    for child in repo_dir.iterdir():
        if child.is_dir() and (child / "config.json").exists():
            build = child / "build"
            if build.exists():
                items.append((build, f"{child.name}/build"))

    # ~/.local/bin/wificities
    local_bin = Path.home() / ".local" / "bin" / "wificities"
    if local_bin.exists():
        items.append((local_bin, "~/.local/bin/wificities"))

    if not items:
        click.echo("  Nothing to clean.")
        return

    click.echo("\n  Will remove:\n")
    for path, desc in items:
        if path.exists():
            if path.is_dir():
                size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
                click.echo(f"    {desc:30s} ({size // 1024 // 1024}MB)")
            else:
                click.echo(f"    {desc}")

    if not click.confirm("\n  Continue?", default=False):
        click.echo("  Cancelled.")
        return

    for path, desc in items:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            click.echo(f"  Removed {desc}")

    click.echo("\n  Done. Run ./wificities to reinstall.\n")


# Import and register subcommands
from .init import init_cmd
from .build import build_cmd
from .flash import flash_cmd
from .serve import serve_cmd
from .plugins import plugin_group
from .themes import theme_group
from .validate import validate_cmd
from .config import config_group

main.add_command(init_cmd, "init")
main.add_command(build_cmd, "build")
main.add_command(flash_cmd, "flash")
main.add_command(serve_cmd, "serve")
main.add_command(plugin_group, "plugin")
main.add_command(theme_group, "theme")
main.add_command(config_group, "config")
main.add_command(validate_cmd, "validate")
main.add_command(uninstall_cmd, "uninstall")


if __name__ == "__main__":
    main()
