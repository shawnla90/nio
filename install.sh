#!/usr/bin/env bash
# NIO installer - one-command setup
# Usage: curl -sSf https://nio.sh | bash
set -euo pipefail

NIO_HOME="$HOME/.nio"
NIO_REPO="https://github.com/shawnla90/nio"
PYTHON=""

echo ""
echo "  ╔══════════════════════════════════╗"
echo "  ║           NIO v0.1.0             ║"
echo "  ║  Voice DNA. Semver souls.        ║"
echo "  ║  Anti-slop. Live dashboard.      ║"
echo "  ╚══════════════════════════════════╝"
echo ""

# --- Detect Python ---
detect_python() {
    for cmd in python3.13 python3.12 python3.11 python3; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            local major minor
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
                PYTHON="$cmd"
                return 0
            fi
        fi
    done
    echo "Error: Python 3.11+ required. Install from https://python.org"
    exit 1
}

detect_python
echo "  Python: $PYTHON ($($PYTHON --version 2>&1))"

# --- Check for uv (preferred) or pip ---
USE_UV=false
if command -v uv &>/dev/null; then
    USE_UV=true
    echo "  Package manager: uv"
else
    echo "  Package manager: pip"
fi

# --- Create NIO home ---
echo ""
echo "  Setting up ~/.nio/..."
mkdir -p "$NIO_HOME"/{bin,lib,registry/souls,registry/voice-profiles,active,teams,logs,cache}

# --- Create venv and install ---
echo "  Installing NIO package..."
if [ "$USE_UV" = true ]; then
    uv venv "$NIO_HOME/venv" --python "$PYTHON" --quiet 2>/dev/null || true
    # Install from PyPI when published, or from local if available
    if [ -f "$(dirname "$0")/pyproject.toml" ]; then
        uv pip install --python "$NIO_HOME/venv/bin/python" -e "$(dirname "$0")" --quiet 2>/dev/null || \
        uv pip install --python "$NIO_HOME/venv/bin/python" nio-agent --quiet 2>/dev/null || \
        echo "  Note: Install from source with: cd nio && uv pip install -e ."
    else
        uv pip install --python "$NIO_HOME/venv/bin/python" nio-agent --quiet 2>/dev/null || \
        echo "  Note: Package not yet on PyPI. Clone the repo and install locally."
    fi
else
    "$PYTHON" -m venv "$NIO_HOME/venv" 2>/dev/null || true
    if [ -f "$(dirname "$0")/pyproject.toml" ]; then
        "$NIO_HOME/venv/bin/pip" install -e "$(dirname "$0")" --quiet 2>/dev/null || \
        echo "  Note: Install from source with: cd nio && pip install -e ."
    else
        "$NIO_HOME/venv/bin/pip" install nio-agent --quiet 2>/dev/null || \
        echo "  Note: Package not yet on PyPI. Clone the repo and install locally."
    fi
fi

# --- Symlink CLI ---
echo "  Linking CLI..."
ln -sf "$NIO_HOME/venv/bin/nio" "$NIO_HOME/bin/nio" 2>/dev/null || true

# Add to PATH if not already there
SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ]; then
    if ! grep -q '\.nio/bin' "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo '# NIO' >> "$SHELL_RC"
        echo 'export PATH="$HOME/.nio/bin:$PATH"' >> "$SHELL_RC"
        echo "  Added ~/.nio/bin to PATH in $(basename "$SHELL_RC")"
    fi
fi

# Also symlink to ~/.local/bin for immediate use
mkdir -p "$HOME/.local/bin"
ln -sf "$NIO_HOME/venv/bin/nio" "$HOME/.local/bin/nio" 2>/dev/null || true

# --- Install Hermes hook ---
echo "  Installing Hermes hook..."
HOOK_DIR="$HOME/.hermes/hooks/nio"
mkdir -p "$HOOK_DIR"

cat > "$HOOK_DIR/HOOK.yaml" << 'HOOKYAML'
name: nio
description: "NIO voice DNA, anti-slop, metrics, and soul pipeline"
events:
  - gateway:startup
  - session:start
  - agent:start
  - agent:end
  - command:*
HOOKYAML

cat > "$HOOK_DIR/handler.py" << 'HOOKPY'
import sys, os
sys.path.insert(0, os.path.expanduser("~/.nio/venv/lib/python3.11/site-packages"))

try:
    from nio.hermes_bridge.middleware import handle as nio_handle
except ImportError:
    async def nio_handle(event_type, context):
        return None

async def handle(event_type, context):
    return await nio_handle(event_type, context)
HOOKPY

# --- Write default config ---
if [ ! -f "$NIO_HOME/config.yaml" ]; then
    cat > "$NIO_HOME/config.yaml" << 'CONFIG'
# NIO configuration
dash:
  port: 4242
  autostart: true
telemetry:
  enabled: false
CONFIG
fi

# --- Install dashboard launchd plist (macOS only) ---
if [ "$(uname)" = "Darwin" ]; then
    echo "  Installing dashboard daemon..."
    PLIST_DIR="$HOME/Library/LaunchAgents"
    mkdir -p "$PLIST_DIR"
    PLIST="$PLIST_DIR/com.shawnos.nio-dash.plist"

    cat > "$PLIST" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.shawnos.nio-dash</string>

    <key>ProgramArguments</key>
    <array>
        <string>$NIO_HOME/venv/bin/python</string>
        <string>-m</string>
        <string>nio.dash.server</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$NIO_HOME</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$NIO_HOME/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>$HOME</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$NIO_HOME/logs/dash-stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$NIO_HOME/logs/dash-stderr.log</string>

    <key>ThrottleInterval</key>
    <integer>30</integer>
</dict>
</plist>
PLISTEOF

    launchctl load "$PLIST" 2>/dev/null || true
fi

# --- Done ---
echo ""
echo "  NIO installed."
echo ""
echo "  Dashboard:  http://localhost:4242"
echo "  CLI:        nio status"
echo "  Diagnose:   nio doctor"
echo "  Souls:      nio soul list"
echo ""
echo "  Restart your shell or run: export PATH=\"\$HOME/.nio/bin:\$PATH\""
echo ""
