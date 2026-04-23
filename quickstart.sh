#!/usr/bin/env bash
# WifiCities — One command setup.
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

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
if ! python3 -m pip --version &> /dev/null; then
    echo "  Installing pip..."
    python3 -m ensurepip --user 2>/dev/null || \
        curl -sS https://bootstrap.pypa.io/get-pip.py | python3 - --user 2>/dev/null || {
            echo "  Failed to install pip."
            echo "  Run: python3 -m ensurepip --user"
            exit 1
        }
fi

# ---- Install all Python deps ----
NEED=""
python3 -c "import click" 2>/dev/null     || NEED="$NEED click"
python3 -c "import mistune" 2>/dev/null   || NEED="$NEED mistune"
python3 -c "import esptool" 2>/dev/null   || NEED="$NEED esptool"
python3 -c "import watchdog" 2>/dev/null  || NEED="$NEED watchdog"

if [ -n "$NEED" ]; then
    echo "  Installing:$NEED"
    python3 -m pip install --user --quiet $NEED
fi

# ---- Install PlatformIO (needed to compile firmware) ----
if ! python3 -c "import platformio" 2>/dev/null && ! command -v pio &> /dev/null; then
    echo "  Installing PlatformIO (compiles ESP32 firmware)..."
    python3 -m pip install --user --quiet platformio
fi

echo "  Dependencies OK."

# ---- Compile firmware ----
FIRMWARE_BIN="$REPO_DIR/firmware/.pio/build/esp32/firmware.bin"
if [ ! -f "$FIRMWARE_BIN" ]; then
    echo "  Compiling firmware (first time only, takes a minute)..."
    cd "$REPO_DIR/firmware"
    python3 -m platformio run -e esp32 --silent 2>&1 | tail -5
    cd "$REPO_DIR"
    if [ -f "$FIRMWARE_BIN" ]; then
        echo "  Firmware compiled."
    else
        echo "  Warning: Firmware compilation failed. You can retry with:"
        echo "    cd firmware && pio run -e esp32"
    fi
fi

# ---- Install 'wificities' command globally ----
INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"

cat > "$INSTALL_DIR/wificities" << EOF
#!/usr/bin/env bash
PYTHONPATH="$REPO_DIR/cli" exec python3 -c "from wificities.cli import main; main()" "\$@"
EOF
chmod +x "$INSTALL_DIR/wificities"

# Also keep a local copy
cp "$INSTALL_DIR/wificities" "$REPO_DIR/wificities" 2>/dev/null || true

# Check PATH
if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
    # Add to shell rc
    SHELL_RC=""
    if [ -f "$HOME/.bashrc" ]; then SHELL_RC="$HOME/.bashrc"
    elif [ -f "$HOME/.zshrc" ]; then SHELL_RC="$HOME/.zshrc"
    elif [ -f "$HOME/.profile" ]; then SHELL_RC="$HOME/.profile"; fi

    if [ -n "$SHELL_RC" ]; then
        if ! grep -q '.local/bin' "$SHELL_RC" 2>/dev/null; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
        fi
    fi
    export PATH="$INSTALL_DIR:$PATH"
fi

echo ""
echo "  'wificities' command installed. Works from anywhere."

# ---- Check for existing site ----
if [ -d "$REPO_DIR/my-wificity" ]; then
    echo ""
    echo "  Site exists at: $REPO_DIR/my-wificity"
    echo ""
    echo "  Commands:"
    echo "    cd $REPO_DIR/my-wificity"
    echo "    wificities serve       # preview"
    echo "    wificities build       # build"
    echo "    wificities flash       # flash to ESP32"
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
echo "    cd my-wificity"
echo "    wificities serve     # preview"
echo "    wificities flash     # flash to ESP32"
echo ""
echo "    wificities config    # customize"
echo ""
echo "  ============================================"
echo ""
