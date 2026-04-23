#!/usr/bin/env bash
# WifiCities — One command setup.
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PIP_FLAGS="--user --disable-pip-version-check"

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

# ---- Ensure pip ----
if ! python3 -m pip --version &> /dev/null 2>&1; then
    echo "  Setting up pip..."
    python3 -m ensurepip --user 2>/dev/null || \
        curl -sS https://bootstrap.pypa.io/get-pip.py | python3 - --user 2>/dev/null || {
            echo "  Failed. Run: python3 -m ensurepip --user"; exit 1;
        }
fi

# ---- Install Python deps ----
install_pkg() {
    local pkg="$1"
    local check="${2:-$1}"
    if ! python3 -c "import $check" 2>/dev/null; then
        echo -n "  Installing $pkg..."
        python3 -m pip install $PIP_FLAGS "$pkg" > /dev/null 2>&1
        echo " done"
    fi
}

install_pkg click
install_pkg mistune
install_pkg esptool
install_pkg watchdog
install_pkg platformio

echo "  Dependencies OK."

# ---- Compile firmware ----
FIRMWARE_BIN="$REPO_DIR/firmware/.pio/build/esp32/firmware.bin"
if [ ! -f "$FIRMWARE_BIN" ]; then
    echo ""
    echo "  Compiling ESP32 firmware (first time only)..."

    if command -v pio &> /dev/null; then
        PIO="pio"
    else
        PIO="python3 -m platformio"
    fi

    cd "$REPO_DIR/firmware"
    if $PIO run -e esp32 > /tmp/wificities-build.log 2>&1; then
        echo "  Firmware compiled."
    else
        echo "  Firmware compilation failed. Log:"
        tail -10 /tmp/wificities-build.log
        echo ""
        echo "  You can retry later: cd firmware && pio run -e esp32"
    fi
    cd "$REPO_DIR"
fi

# ---- Install 'wificities' command ----
INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"

cat > "$INSTALL_DIR/wificities" << EOF
#!/usr/bin/env bash
PYTHONPATH="$REPO_DIR/cli" exec python3 -c "from wificities.cli import main; main()" "\$@"
EOF
chmod +x "$INSTALL_DIR/wificities"
cp "$INSTALL_DIR/wificities" "$REPO_DIR/wificities" 2>/dev/null || true

# Ensure PATH
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
    echo "  Site already exists. Run these from anywhere in the repo:"
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
cd "$REPO_DIR"
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
echo "  Run from anywhere inside the wificities/ folder."
echo ""
echo "  ============================================"
echo ""
