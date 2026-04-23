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

# ---- Install Python deps one by one with status ----
install_if_missing() {
    local pkg="$1"
    local import_name="${2:-$1}"
    if ! python3 -c "import $import_name" 2>/dev/null; then
        echo -n "  Installing $pkg... "
        python3 -m pip install --user "$pkg" --progress-bar on 2>&1 | tail -1
    fi
}

install_if_missing click
install_if_missing mistune
install_if_missing esptool
install_if_missing watchdog
install_if_missing platformio

echo "  All dependencies installed."

# ---- Compile firmware ----
FIRMWARE_BIN="$REPO_DIR/firmware/.pio/build/esp32/firmware.bin"
if [ ! -f "$FIRMWARE_BIN" ]; then
    echo ""
    echo "  Compiling firmware (first time only)..."
    echo "  This downloads the ESP32 toolchain and compiles. ~2 min."
    echo ""
    cd "$REPO_DIR/firmware"

    # Use pio or python -m platformio
    if command -v pio &> /dev/null; then
        PIO="pio"
    else
        PIO="python3 -m platformio"
    fi

    $PIO run -e esp32 2>&1 | while IFS= read -r line; do
        # Show only meaningful lines, skip noise
        case "$line" in
            *"Platform Manager"*|*"Installing"*|*"Downloading"*|*"Unpacking"*)
                echo "  $line" ;;
            *"Compiling"*)
                echo -ne "\r  Compiling...          " ;;
            *"Linking"*)
                echo -ne "\r  Linking...            " ;;
            *"Building"*)
                echo -ne "\r  Building filesystem..." ;;
            *"SUCCESS"*|*"success"*)
                echo -e "\r  Firmware compiled.     " ;;
            *"Error"*|*"error"*|*"FAILED"*)
                echo "  $line" ;;
        esac
    done

    cd "$REPO_DIR"

    if [ ! -f "$FIRMWARE_BIN" ]; then
        echo ""
        echo "  Warning: Firmware compilation may have failed."
        echo "  You can retry: cd firmware && pio run -e esp32"
        echo "  Continuing with site setup..."
        echo ""
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

# Ensure ~/.local/bin is in PATH
if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
    SHELL_RC=""
    if [ -f "$HOME/.bashrc" ]; then SHELL_RC="$HOME/.bashrc"
    elif [ -f "$HOME/.zshrc" ]; then SHELL_RC="$HOME/.zshrc"
    elif [ -f "$HOME/.profile" ]; then SHELL_RC="$HOME/.profile"; fi

    if [ -n "$SHELL_RC" ]; then
        if ! grep -q '.local/bin' "$SHELL_RC" 2>/dev/null; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
            echo "  Added ~/.local/bin to PATH in $SHELL_RC"
            echo "  Run 'source $SHELL_RC' or open a new terminal for it to take effect."
        fi
    fi
    export PATH="$INSTALL_DIR:$PATH"
fi

# ---- Check for existing site ----
if [ -d "$REPO_DIR/my-wificity" ]; then
    echo ""
    echo "  Site exists at: $REPO_DIR/my-wificity"
    echo ""
    echo "    cd my-wificity"
    echo "    wificities serve"
    echo "    wificities flash"
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
echo "    wificities config    # customize"
echo ""
echo "  ============================================"
echo ""
