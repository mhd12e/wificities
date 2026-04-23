#!/usr/bin/env bash
# WifiCities — One command setup.
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"

echo ""
echo "  WifiCities — Setup"
echo ""

# ---- Python check ----
if ! command -v python3 &> /dev/null; then
    echo "  Python 3 is required."
    if [[ "$OSTYPE" == "darwin"* ]]; then echo "  Run: brew install python3"
    elif [ -f /etc/debian_version ];    then echo "  Run: sudo apt install python3"
    elif [ -f /etc/fedora-release ];    then echo "  Run: sudo dnf install python3"
    elif [ -f /etc/arch-release ];      then echo "  Run: sudo pacman -S python"
    else echo "  https://python.org"; fi
    exit 1
fi

# ---- Create venv ----
if [ ! -d "$VENV_DIR" ]; then
    echo -n "  Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo " done"
fi

# Activate venv for this script
source "$VENV_DIR/bin/activate"

# ---- Install deps into venv ----
install_pkg() {
    local pkg="$1"
    local check="${2:-$1}"
    if ! python3 -c "import $check" 2>/dev/null; then
        echo -n "  Installing $pkg..."
        pip install --disable-pip-version-check -q "$pkg" > /dev/null 2>&1
        echo " done"
    fi
}

install_pkg click
install_pkg mistune
install_pkg esptool
install_pkg watchdog
install_pkg platformio
install_pkg littlefs-python littlefs

echo "  Dependencies OK."

# ---- Compile firmware ----
FIRMWARE_BIN="$REPO_DIR/firmware/.pio/build/esp32/firmware.bin"
if [ ! -f "$FIRMWARE_BIN" ]; then
    echo ""
    echo "  Compiling ESP32 firmware (first time only)..."
    cd "$REPO_DIR/firmware"
    if pio run -e esp32 > /tmp/wificities-build.log 2>&1; then
        echo "  Firmware compiled."
    else
        echo "  Firmware compilation failed. Log:"
        tail -10 /tmp/wificities-build.log
        echo ""
        echo "  Retry later: cd firmware && pio run -e esp32"
    fi
    cd "$REPO_DIR"
fi

# ---- Create 'wificities' command ----
cat > "$REPO_DIR/wificities" << EOF
#!/usr/bin/env bash
source "$VENV_DIR/bin/activate"
PYTHONPATH="$REPO_DIR/cli" exec python3 -c "from wificities.cli import main; main()" "\$@"
EOF
chmod +x "$REPO_DIR/wificities"

# Also install to ~/.local/bin for convenience
INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"
cp "$REPO_DIR/wificities" "$INSTALL_DIR/wificities"

if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
    SHELL_RC=""
    [ -f "$HOME/.bashrc" ]  && SHELL_RC="$HOME/.bashrc"
    [ -f "$HOME/.zshrc" ]   && SHELL_RC="$HOME/.zshrc"
    [ -f "$HOME/.profile" ] && SHELL_RC="$HOME/.profile"
    if [ -n "$SHELL_RC" ] && ! grep -q '.local/bin' "$SHELL_RC" 2>/dev/null; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
    fi
    export PATH="$INSTALL_DIR:$PATH"
fi

# ---- Check for existing site ----
if [ -d "$REPO_DIR/my-wificity" ]; then
    echo ""
    echo "  Site already exists. Commands:"
    echo ""
    echo "    wificities serve       # preview"
    echo "    wificities build       # build"
    echo "    wificities flash       # flash to ESP32"
    echo "    wificities config      # customize"
    echo ""
    echo "  Start fresh: rm -rf my-wificity && ./quickstart.sh"
    exit 0
fi

# ---- Create site ----
echo ""
PYTHONPATH="$REPO_DIR/cli" python3 -c "from wificities.cli import main; main()" init my-wificity

echo ""
echo "  Building..."
cd "$REPO_DIR/my-wificity"
PYTHONPATH="$REPO_DIR/cli" python3 -c "from wificities.cli import main; main()" build

echo ""
echo "  ============================================"
echo ""
echo "    wificities serve     # preview"
echo "    wificities flash     # flash to ESP32"
echo "    wificities config    # customize"
echo ""
echo "  Works from anywhere in the repo."
echo "  sudo works too: sudo ./wificities flash"
echo ""
echo "  ============================================"
echo ""
