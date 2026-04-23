#!/usr/bin/env bash
# WifiCities Quick Start
# Clone the repo, run this, flash your ESP32.
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$REPO_DIR/cli"

echo ""
echo "  ============================================"
echo "    WifiCities — Quick Start"
echo "  ============================================"
echo ""

# --- Check Python ---
if ! command -v python3 &> /dev/null; then
    echo "  Error: Python 3 is required."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  Install: brew install python3"
    elif [ -f /etc/debian_version ]; then
        echo "  Install: sudo apt install python3"
    elif [ -f /etc/fedora-release ] || [ -f /etc/redhat-release ]; then
        echo "  Install: sudo dnf install python3"
    elif [ -f /etc/arch-release ]; then
        echo "  Install: sudo pacman -S python"
    else
        echo "  Install from: https://python.org"
    fi
    exit 1
fi

# --- Install only essential deps (click + mistune) ---
echo "  [1/4] Checking dependencies..."

MISSING=""
python3 -c "import click" 2>/dev/null    || MISSING="$MISSING click"
python3 -c "import mistune" 2>/dev/null  || MISSING="$MISSING mistune"

if [ -n "$MISSING" ]; then
    echo "  Installing:$MISSING"

    # Ensure pip
    if ! python3 -m pip --version &> /dev/null; then
        echo "  Bootstrapping pip..."
        python3 -m ensurepip --user 2>/dev/null || {
            echo "  Trying get-pip.py..."
            curl -sS https://bootstrap.pypa.io/get-pip.py 2>/dev/null | python3 - --user 2>/dev/null || {
                echo ""
                echo "  Could not install pip. Please install manually:"
                echo "    python3 -m ensurepip --user"
                echo "  Then re-run this script."
                exit 1
            }
        }
    fi

    python3 -m pip install --user --quiet $MISSING

    # Verify
    FAIL=""
    python3 -c "import click" 2>/dev/null   || FAIL="$FAIL click"
    python3 -c "import mistune" 2>/dev/null || FAIL="$FAIL mistune"
    if [ -n "$FAIL" ]; then
        echo "  Failed to install:$FAIL"
        echo "  Try: python3 -m pip install --user$FAIL"
        exit 1
    fi
fi

echo "  Dependencies OK."
echo ""
echo "  NOTE: esptool (for flashing) and watchdog (for hot reload)"
echo "  will be installed when first needed, or install now:"
echo "    python3 -m pip install --user esptool watchdog"

# --- Create wrapper command ---
WRAPPER="$REPO_DIR/wificities"
cat > "$WRAPPER" << WRAPPER_EOF
#!/usr/bin/env bash
PYTHONPATH="$REPO_DIR/cli" exec python3 -c "from wificities.cli import main; main()" "\$@"
WRAPPER_EOF
chmod +x "$WRAPPER"

export PATH="$REPO_DIR:$PATH"

# --- Create or resume site ---
SITE_DIR="$REPO_DIR/my-wificity"
if [ -d "$SITE_DIR" ]; then
    echo ""
    echo "  Site already exists at my-wificity/"
    echo ""
    echo "  Commands:"
    echo "    cd my-wificity"
    echo "    ../wificities serve        # preview locally"
    echo "    ../wificities build        # build for ESP32"
    echo "    ../wificities flash        # flash to ESP32"
    echo ""
    echo "  Start fresh: rm -rf my-wificity && ./quickstart.sh"
    exit 0
fi

echo ""
echo "  [2/4] Creating your wificity..."
echo ""

cd "$REPO_DIR"
"$WRAPPER" init my-wificity

echo ""
echo "  [3/4] Building..."
cd "$SITE_DIR"
"$REPO_DIR/wificities" build

echo ""
echo "  [4/4] Done!"
echo ""
echo "  ============================================"
echo "    Preview locally:"
echo "      cd my-wificity"
echo "      ../wificities serve"
echo ""
echo "    Flash to ESP32:"
echo "      cd my-wificity"
echo "      ../wificities flash"
echo "  ============================================"
echo ""
echo "  Customize:"
echo "    ../wificities config               # menu"
echo "    ../wificities config palette        # colors"
echo "    ../wificities config header         # header"
echo "    ../wificities theme switch <name>   # switch theme"
echo "    ../wificities plugin add <name>     # add plugin"
echo ""
