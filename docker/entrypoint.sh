#!/bin/bash
# entrypoint.sh — Starts Tailscale VPN + the Autonomous Agent
# Used by the Docker container

set -e

echo ""
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║                                                  ║"
echo "  ║      ◈  LYRA AUTONOMOUS AGENT v2.0              ║"
echo "  ║      Docker · Tailscale · Local LLM              ║"
echo "  ║                                                  ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo ""

# ── Start Tailscale (if auth key provided) ──
if [ -n "$TAILSCALE_AUTH_KEY" ]; then
    echo "▸ Starting Tailscale..."

    # Start tailscaled daemon
    tailscaled \
        --state=/var/lib/tailscale/tailscaled.state \
        --socket=/var/run/tailscale/tailscaled.sock \
        --port=41641 &

    # Wait for tailscaled to be ready
    sleep 2

    # Bring up the Tailscale connection
    tailscale up \
        --authkey="$TAILSCALE_AUTH_KEY" \
        --hostname="${TAILSCALE_HOSTNAME:-lyra-agent}" \
        --accept-dns=${TAILSCALE_ACCEPT_DNS:-true} \
        --reset=false \
        2>/dev/null || tailscale up \
        --authkey="$TAILSCALE_AUTH_KEY" \
        --hostname="${TAILSCALE_HOSTNAME:-lyra-agent}" \
        --reset=false

    sleep 1

    # Display the Tailscale IP
    TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "unknown")
    TAILSCALE_NAME=$(tailscale status --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('Self',{}).get('HostName','unknown'))" 2>/dev/null || echo "unknown")

    echo "✓ Tailscale connected!"
    echo "  Hostname:  ${TAILSCALE_HOSTNAME:-lyra-agent}"
    echo "  IP:        ${TAILSCALE_IP}"
    echo "  Access:    http://${TAILSCALE_IP}:8420"
    echo ""
else
    echo "⚠ No TAILSCALE_AUTH_KEY set — starting without VPN."
    echo "  Access the command center at http://localhost:8420"
    echo ""
fi

# ── Wait for Ollama ──
echo "▸ Checking Ollama connection..."
OLLAMA_HOST=${OLLAMA_HOST:-http://ollama:11434}
for i in $(seq 1 30); do
    if curl -sf "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
        echo "✓ Ollama is available at ${OLLAMA_HOST}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "⚠ Could not connect to Ollama at ${OLLAMA_HOST} after 30 attempts."
        echo "  The agent will start anyway — configure Ollama separately."
    fi
    sleep 2
done

# ── Start the Agent ──
echo ""
echo "▸ Starting Lyra Autonomous Agent..."
echo "  Command Center: http://0.0.0.0:${PORT:-8420}"
echo ""

cd /app
exec python3 run.py
