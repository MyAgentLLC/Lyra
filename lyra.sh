#!/data/data/com.termux/files/usr/bin/bash
# lyra.sh — one-command control for Lyra on Termux (or desktop bash)
# Usage: bash lyra.sh [start|stop|restart|chat|status|log]

set -u

CONFIG=""
if [ -f "config/config.mobile.yaml" ] && [ "${PREFIX:-}" != "" ] && [[ "$PREFIX" == *com.termux* ]]; then
    CONFIG="config/config.mobile.yaml"
else
    CONFIG="config/config.yaml"
fi

# Use the project virtualenv if present (Arch/Omarchy blocks system-wide pip)
PY="python"
if [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
fi

OLLAMA_URL="http://127.0.0.1:11434"
SERVER_URL="http://127.0.0.1:8420/api/status"

wakelock_on() {
    command -v termux-wake-lock > /dev/null 2>&1 && termux-wake-lock && echo "✓ Wake lock held (CPU stays awake in background)"
}

wakelock_off() {
    command -v termux-wake-unlock > /dev/null 2>&1 && termux-wake-unlock 2>/dev/null
}

ollama_up() {
    curl -s "$OLLAMA_URL/api/tags" > /dev/null 2>&1
}

server_up() {
    curl -s "$SERVER_URL" > /dev/null 2>&1
}

start_ollama() {
    if ollama_up; then
        echo "✓ Ollama already running"
    else
        nohup ollama serve > "$HOME/ollama.log" 2>&1 &
        sleep 4
        if ollama_up; then
            echo "✓ Ollama started (log: ~/ollama.log)"
        else
            echo "✗ Ollama failed to start — check ~/ollama.log"
            exit 1
        fi
    fi
}

start_server() {
    if server_up; then
        echo "✓ Lyra already running"
    else
        nohup "$PY" run.py --config "$CONFIG" > server.log 2>&1 &
        sleep 5
        if server_up; then
            echo "✓ Lyra command center started (log: server.log)"
        else
            echo "✗ Lyra failed to start — check server.log"
            exit 1
        fi
    fi
}

stop_all() {
    pkill -f "run.py" 2>/dev/null && echo "✓ Stopped command center" || echo "  (command center wasn't running)"
    pkill -f "ollama serve" 2>/dev/null && echo "✓ Stopped Ollama" || echo "  (Ollama wasn't running)"
    wakelock_off
    echo "✓ Wake lock released"
}

case "${1:-start}" in

  start)
    echo "  ◈ Starting Lyra..."
    wakelock_on
    start_ollama
    start_server
    echo ""
    echo "  Command center:  $SERVER_URL (open http://127.0.0.1:8420 in Chrome)"
    echo "  Terminal chat:    bash lyra.sh chat"
    echo ""
    echo "  ⚠ If this dies when you switch apps, do BOTH:"
    echo "    1. termux-wake-lock is already held by this script."
    echo "    2. Android Settings → Apps → Termux → Battery → Unrestricted"
    ;;

  stop)
    stop_all
    ;;

  restart)
    echo "  ◈ Restarting Lyra..."
    stop_all
    sleep 2
    wakelock_on
    start_ollama
    start_server
    echo "✓ Lyra restarted"
    ;;

  chat)
    wakelock_on
    "$PY" chat.py --config "$CONFIG"
    ;;

  status)
    echo "  ◈ Lyra status"
    if ollama_up; then
        echo "  ✓ Ollama: running"
    else
        echo "  ✗ Ollama: DOWN"
    fi
    if server_up; then
        echo "  ✓ Command center: running"
    else
        echo "  ✗ Command center: DOWN"
    fi
    ;;

  log)
    tail -f server.log 2>/dev/null || echo "No server.log yet — run 'bash lyra.sh start' first"
    ;;

  *)
    echo "Usage: bash lyra.sh [start|stop|restart|chat|status|log]"
    ;;
esac
