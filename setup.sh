#!/bin/bash
# Autonomous Agent — Setup Script v2.0
# Run this to install all dependencies and prepare the system

set -e

echo ""
echo "    ◈  Autonomous Agent v2.0 — Setup"
echo "    ──────────────────────────────────"
echo ""

# Check Python
echo "Checking Python..."
if command -v python3 &> /dev/null; then
    PY=python3
elif command -v python &> /dev/null; then
    PY=python
else
    echo "✗ Python 3 is required. Install it first: https://python.org"
    exit 1
fi
PY_VERSION=$($PY --version 2>&1)
echo "✓ Found $PY_VERSION"

# Check pip
echo "Checking pip..."
if ! $PY -m pip --version &> /dev/null; then
    echo "✗ pip is required. Install it: https://pip.pypa.io"
    exit 1
fi
echo "✓ pip available"

# Check Ollama
echo ""
echo "Checking Ollama..."
if command -v ollama &> /dev/null; then
    echo "✓ Ollama found"
    if curl -s http://localhost:11434/api/tags &> /dev/null; then
        echo "✓ Ollama is running"
        MODELS=$(curl -s http://localhost:11434/api/tags | $PY -c "import sys,json; [print(m['name']) for m in json.load(sys.stdin).get('models',[])]" 2>/dev/null || echo "")
        if [ -n "$MODELS" ]; then
            echo "  Available models:"
            echo "$MODELS" | sed 's/^/    - /'
        else
            echo "  No models pulled yet. Recommended: ollama pull qwen2.5:7b"
        fi
    else
        echo "⚠ Ollama is installed but not running. Start it with: ollama serve"
    fi
else
    echo "✗ Ollama not found."
    echo "  Install: https://ollama.com/download"
    echo "  Then pull a model: ollama pull qwen2.5:7b"
fi

# Check ADB
echo ""
echo "Checking ADB (Android phone control)..."
if command -v adb &> /dev/null; then
    echo "✓ ADB found"
    DEVICES=$(adb devices 2>/dev/null | tail -n +2 | grep -v "^$")
    if [ -n "$DEVICES" ]; then
        echo "  Connected devices:"
        echo "$DEVICES" | sed 's/^/    /'
    else
        echo "  No devices connected. Enable USB debugging and plug in your phone."
    fi
else
    echo "⚠ ADB not found. Install:"
    echo "    macOS:  brew install android-platform-tools"
    echo "    Linux:  sudo apt install adb"
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
$PY -m pip install -r requirements.txt
echo "✓ Dependencies installed"

# Install Playwright browsers
echo ""
echo "Installing Playwright browser binaries..."
$PY -m playwright install chromium
echo "✓ Playwright chromium installed"

# Create directories
echo ""
echo "Creating directories..."
mkdir -p logs data .agent_screenshots plugins
echo "✓ Directories created"

# Done
echo ""
echo "    ──────────────────────────────────"
echo "    ✓ Setup complete!"
echo ""
echo "    To start the agent:"
echo "      $PY run.py"
echo ""
echo "    Then open http://localhost:8420"
echo ""
echo "    Webhooks:  POST to http://localhost:8420/webhook/<name>"
echo "    Plugins:   Drop plugins in the plugins/ directory"
echo ""
