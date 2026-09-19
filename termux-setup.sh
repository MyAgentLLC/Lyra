#!/data/data/com.termux/files/usr/bin/bash
# termux-setup.sh — One-shot installer for Lyra on Android (Termux)
# Run: bash termux-setup.sh

set -e

echo ""
echo "    ◈  Lyra — Android (Termux) Setup"
echo "    ──────────────────────────────────"
echo ""

# 1. Core packages
echo "▸ Installing core packages..."
pkg update -y
pkg install -y python git curl clang libjpeg-turbo zlib openssl
echo "✓ Core packages installed"

# 2. TUR repo + Ollama
echo "▸ Installing Ollama (TUR repo)..."
pkg install -y tur-repo
pkg install -y ollama
echo "✓ Ollama installed"

# 3. Start Ollama server in the background
echo "▸ Starting Ollama server..."
if curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "✓ Ollama already running"
else
    nohup ollama serve > ~/ollama.log 2>&1 &
    sleep 5
    if curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
        echo "✓ Ollama server started (log: ~/ollama.log)"
    else
        echo "⚠ Ollama did not start — check ~/ollama.log"
        echo "  Try manually: ollama serve &"
        exit 1
    fi
fi

# 4. Pull a small model suited to phone hardware
echo "▸ Pulling model (qwen2.5:1.5b, ~1 GB)..."
ollama pull qwen2.5:1.5b || { echo "✗ Model pull failed — check connection"; exit 1; }
echo "✓ Model ready"

# 5. Python dependencies (mobile set — no pyautogui/playwright/Pillow GUI deps)
echo "▸ Installing Python dependencies..."
pip install --upgrade pip
pip install fastapi==0.115.0 uvicorn==0.30.0 ollama==0.3.3 pyyaml==6.0.2 \
    websockets==12.0 aiohttp==3.10.0 pydantic==2.9.0 python-multipart==0.0.9 \
    --no-cache-dir
echo "✓ Python dependencies installed"

# 6. Directories
mkdir -p logs data .agent_screenshots
echo "✓ Directories created"

# 7. Optional: ADB for phone self-control
if ! command -v adb > /dev/null 2>&1; then
    echo ""
    echo "▸ (Optional) Installing ADB for phone self-control..."
    pkg install -y android-tools && echo "✓ ADB installed" || echo "⚠ ADB install skipped"
fi

echo ""
echo "    ──────────────────────────────────"
echo "    ✓ Setup complete!"
echo ""
echo "    Start the agent:"
echo "      cd $(pwd) && python run.py --config config/config.mobile.yaml"
echo ""
echo "    Then open in your phone browser:"
echo "      http://127.0.0.1:8420"
echo ""
echo "    Note: Android may kill background processes."
echo "    Run 'termux-wake-lock' to keep Lyra alive, and disable"
echo "    battery optimization for Termux in Android settings."
echo ""
