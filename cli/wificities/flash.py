"""wificities flash — flash firmware + filesystem to ESP32."""
import subprocess
import shutil
from pathlib import Path

import click

from .project import enter_project_dir


BOARD_CONFIGS = {
    "esp32": {
        "chip": "esp32",
        "flash_mode": "dio",
        "flash_freq": "40m",
        "flash_size": "4MB",
        "app_offset": "0x10000",
        "fs_offset": "0x190000",
        "fs_size": "0x270000",
    },
    "esp32s2": {
        "chip": "esp32s2",
        "flash_mode": "dio",
        "flash_freq": "40m",
        "flash_size": "4MB",
        "app_offset": "0x10000",
        "fs_offset": "0x190000",
        "fs_size": "0x270000",
    },
    "esp32s3": {
        "chip": "esp32s3",
        "flash_mode": "dio",
        "flash_freq": "40m",
        "flash_size": "4MB",
        "app_offset": "0x10000",
        "fs_offset": "0x190000",
        "fs_size": "0x270000",
    },
    "esp32c3": {
        "chip": "esp32c3",
        "flash_mode": "dio",
        "flash_freq": "40m",
        "flash_size": "4MB",
        "app_offset": "0x10000",
        "fs_offset": "0x190000",
        "fs_size": "0x270000",
    },
}


@click.command("flash")
@click.option("--port", default=None, help="Serial port (e.g., /dev/ttyUSB0)")
@click.option("--board", default="esp32",
              type=click.Choice(list(BOARD_CONFIGS.keys())),
              help="ESP32 board variant")
@click.option("--only", default=None,
              type=click.Choice(["firmware", "filesystem"]),
              help="Flash only firmware or only filesystem")
def flash_cmd(port: str | None, board: str, only: str | None):
    """Flash firmware and/or filesystem to ESP32."""
    project_dir = enter_project_dir()
    build_dir = project_dir / "build"

    if not build_dir.exists():
        click.echo("Error: build/ directory not found. Run 'wificities build' first.")
        raise SystemExit(1)

    config = BOARD_CONFIGS[board]

    # Auto-detect port
    if port is None:
        port = _detect_port()
        if port is None:
            click.echo("Error: No ESP32 detected. Specify --port manually.")
            raise SystemExit(1)
        click.echo(f"  Detected ESP32 on {port}")

    # Check for backend plugins (need PlatformIO)
    has_backend_plugins = _has_backend_plugins()

    if only != "filesystem":
        # Flash firmware
        firmware_bin = _get_firmware_bin(board, has_backend_plugins)
        if firmware_bin is None:
            click.echo("Error: No firmware binary. Run ./quickstart.sh to compile it.")
            raise SystemExit(1)

        click.echo(f"\nFlashing firmware to {port}...")
        _flash_binary(port, config, firmware_bin, config["app_offset"])

    if only != "firmware":
        # Create and flash LittleFS image
        click.echo(f"\nCreating LittleFS image...")
        fs_image = _create_littlefs_image(build_dir, config)

        if fs_image:
            click.echo(f"Flashing filesystem to {port}...")
            _flash_binary(port, config, fs_image, config["fs_offset"])
        else:
            click.echo("Error: Failed to create LittleFS image.")
            click.echo("  Make sure 'mklittlefs' is installed or install littlefs-python.")
            raise SystemExit(1)

    click.echo(f"\n\u2705 Done! Your wificity is broadcasting.")
    click.echo(f"   Connect to the WiFi network and enjoy!")


def _detect_port() -> str | None:
    """Try to auto-detect an ESP32 serial port."""
    import glob
    import sys

    if sys.platform == "linux":
        candidates = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
    elif sys.platform == "darwin":
        candidates = glob.glob("/dev/cu.usbserial*") + glob.glob("/dev/cu.usbmodem*")
    elif sys.platform == "win32":
        candidates = [f"COM{i}" for i in range(1, 20)]
    else:
        candidates = []

    # Return first available
    for port in sorted(candidates):
        return port
    return None


def _has_backend_plugins() -> bool:
    """Check if the project has any backend plugins installed."""
    wificities_json = Path.cwd() / "wificities.json"
    if not wificities_json.exists():
        return False

    import json
    manifest = json.loads(wificities_json.read_text(encoding="utf-8"))
    plugins_dir = Path(__file__).resolve().parent.parent.parent / "plugins"

    for plugin_name in manifest.get("plugins", {}):
        plugin_dir = plugins_dir / plugin_name
        if plugin_dir.exists():
            plugin_json = plugin_dir / "plugin.json"
            if plugin_json.exists():
                pdata = json.loads(plugin_json.read_text(encoding="utf-8"))
                if pdata.get("type") == "backend":
                    return True
    return False


def _get_firmware_bin(board: str, has_backend: bool) -> Path | None:
    """Get the firmware binary path. Compiles if needed."""
    import sys

    firmware_dir = Path(__file__).resolve().parent.parent.parent / "firmware"
    pio_build = firmware_dir / ".pio" / "build" / board / "firmware.bin"

    # Already compiled? Use it.
    if pio_build.exists():
        return pio_build

    # Try to compile using the current Python (venv-safe)
    click.echo("  Firmware not compiled yet. Compiling...")
    pio_cmd = [sys.executable, "-m", "platformio"]

    # Check if platformio is available
    try:
        subprocess.run([*pio_cmd, "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        click.echo("  PlatformIO not available. Run ./quickstart.sh first.")
        return None

    click.echo("  This takes ~1 min the first time (downloads ESP32 toolchain)...")
    try:
        result = subprocess.run(
            [*pio_cmd, "run", "-e", board],
            cwd=firmware_dir,
            capture_output=True, text=True,
            timeout=600
        )
        if result.returncode == 0 and pio_build.exists():
            click.echo("  Firmware compiled.")
            return pio_build
        else:
            click.echo("  Compilation failed:")
            output = (result.stderr + result.stdout).strip()
            for line in output.split('\n')[-8:]:
                click.echo(f"    {line}")
            return None
    except subprocess.TimeoutExpired:
        click.echo("  Compilation timed out.")
        return None


def _create_littlefs_image(build_dir: Path, config: dict) -> Path | None:
    """Create a LittleFS image from the build directory."""
    image_path = build_dir / "littlefs.bin"
    fs_size = int(config["fs_size"], 16)

    # Try mklittlefs first
    mklittlefs = shutil.which("mklittlefs")
    if mklittlefs:
        try:
            result = subprocess.run(
                [mklittlefs, "-c", str(build_dir), "-s", str(fs_size),
                 "-p", "256", "-b", "4096", str(image_path)],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return image_path
        except Exception:
            pass

    # Try littlefs-python
    try:
        from littlefs import LittleFS

        lfs = LittleFS(block_size=4096, block_count=fs_size // 4096)

        # Walk build dir and add all files
        for fpath in build_dir.rglob("*"):
            if fpath.is_file() and fpath != image_path:
                rel = "/" + str(fpath.relative_to(build_dir)).replace("\\", "/")
                # Create parent dirs
                parts = rel.strip("/").split("/")
                for i in range(len(parts) - 1):
                    d = "/" + "/".join(parts[:i+1])
                    try:
                        lfs.mkdir(d)
                    except Exception:
                        pass
                # Write file
                with open(fpath, "rb") as src:
                    with lfs.open(rel, "wb") as dst:
                        dst.write(src.read())

        # Write image
        with open(image_path, "wb") as f:
            f.write(lfs.context.buffer)
        return image_path

    except ImportError:
        pass

    click.echo("  No LittleFS tool found. Run ./quickstart.sh to install all dependencies.")
    return None


def _flash_binary(port: str, config: dict, binary: Path, offset: str):
    """Flash a binary to the ESP32 using esptool."""
    import sys

    args = [
        "--chip", config["chip"],
        "--port", port,
        "--baud", "460800",
        "write_flash",
        "--flash_mode", config["flash_mode"],
        "--flash_freq", config["flash_freq"],
        "--flash_size", config["flash_size"],
        offset, str(binary),
    ]

    # Always use the same Python that's running this script (venv-safe)
    cmd = [sys.executable, "-m", "esptool"] + args

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        click.echo("  OK")
    else:
        stderr = result.stderr + result.stdout
        if "Permission denied" in stderr or "Errno 13" in stderr:
            click.echo(f"  Permission denied on {port}.")
            click.echo("")
            click.echo("  Fix: sudo ./wificities flash")
            click.echo("  Or: log out and back in (if you just added yourself to dialout)")
        elif "No module named" in stderr:
            click.echo("  esptool not found. Run: ./quickstart.sh")
        else:
            click.echo(f"  Flash failed: {stderr[:400]}")
        raise SystemExit(1)
