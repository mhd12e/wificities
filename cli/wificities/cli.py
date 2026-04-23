"""Main CLI entry point for wificities."""
import click

from . import __version__


@click.group()
@click.version_option(version=__version__, prog_name="wificities")
def main():
    """WifiCities — Build and flash portable personal websites to ESP32."""
    pass


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


if __name__ == "__main__":
    main()
