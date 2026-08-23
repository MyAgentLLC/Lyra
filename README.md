# Lyra — Autonomous Local Agent v2.0

A fully autonomous, locally-run AI agent that controls your computer, phone, browser, and filesystem. Uses local LLMs via Ollama. 100% free, 100% private — everything runs on your machine.

## Quick Deploy

### Docker + Tailscale (recommended for laptop deployment)

```bash
git clone https://github.com/MyAgentLLC/Lyra.git
cd Lyra
cp .env.example .env
# Add your Tailscale auth key
nano .env
docker compose up -d
```

Access the command center from any device on your Tailscale network: `http://lyra-agent:8420`

See [DEPLOY.md](DEPLOY.md) for full deployment instructions.

### Without Docker

```bash
git clone https://github.com/MyAgentLLC/Lyra.git
cd Lyra
chmod +x setup.sh && ./setup.sh
python3 run.py
```

Open `http://localhost:8420`

## What It Does

- **Computer Control**: Mouse, keyboard, screenshots, file operations, shell commands
- **Phone Control**: Android device control via ADB (screenshots, taps, swipes, app launches)
- **Browser Automation**: Full browser control via Playwright (navigate, click, type, screenshot, JS execution, tabs, downloads)
- **Webhooks**: Incoming webhook endpoints for external services to trigger agent tasks; outgoing webhooks to notify external services of events
- **Plugin System**: Drop-in plugins that add custom tools and hooks to the agent
- **Command Center**: Web-based dashboard to monitor and direct the agent
- **Local Models**: Runs entirely on local LLMs via Ollama (Llama 3.1, Qwen2.5, Mistral, etc.)
- **Tailscale VPN**: Access your agent from any device on your private network
- **Docker**: One-command deployment with docker-compose

## Architecture

```
Lyra/
├── Dockerfile                    # Docker image (Python + Playwright + Tailscale)
├── docker-compose.yml            # Ollama + Agent + Tailscale stack
├── docker/entrypoint.sh          # Container entrypoint (Tailscale + agent)
├── .env.example                  # Environment config template
├── DEPLOY.md                     # Deployment guide
├── run.py                        # Entry point
├── config/config.yaml            # Configuration
├── agent_core/
│   ├── agent.py                  # Core agent loop
│   ├── llm.py                    # Ollama model interface
│   └── memory.py                 # Persistent memory (SQLite)
├── device_control/
│   ├── computer.py               # Computer control (pyautogui)
│   ├── phone.py                  # Android control (ADB)
│   ├── browser.py                # Browser automation (Playwright)
│   └── filesystem.py             # File operations
├── command_center/
│   ├── server.py                 # FastAPI web server
│   ├── templates/index.html      # Dashboard UI
│   └── static/app.js             # Dashboard logic
├── webhooks/
│   └── webhook_manager.py        # Incoming/outgoing webhooks
├── plugins/
│   ├── plugin_manager.py         # Plugin discovery and loading
│   └── example/                  # Example plugin
│       ├── plugin.json
│       └── plugin.py
├── tools/
│   ├── tool_registry.py          # Tool definitions
│   └── register_tools.py         # Registers all built-in tools
├── utils/safety.py               # Safety checks
├── models/model_manager.py       # Model management
├── requirements.txt
└── setup.sh
```

## Docker Stack

The `docker-compose.yml` runs three services:

| Service | Purpose | Port |
|---------|---------|------|
| `ollama` | Local LLM inference server | 11434 |
| `ollama-puller` | One-shot model puller (qwen2.5:7b by default) | — |
| `agent` | The autonomous agent + command center + Tailscale | 8420 |

## Tailscale Integration

The agent container includes Tailscale for mesh VPN access. This lets you:

- Access the command center from your phone, tablet, or other laptops
- No port forwarding or public IP needed
- Everything stays private on your tailnet

Get a free Tailscale account at [tailscale.com](https://tailscale.com), then generate an auth key at [login.tailscale.com/admin/settings/keys](https://login.tailscale.com/admin/settings/keys).

## Browser Automation

The agent controls a real browser using Playwright. 18 browser tools available:
navigation, clicking, typing, form filling, screenshots, JavaScript execution,
scrolling, tab management, link extraction, file downloads, cookie management.

## Webhooks

**Incoming**: External services POST to `/webhook/<name>` to trigger agent tasks.
**Outgoing**: Agent emits events that POST to external URLs.

See [DEPLOY.md](DEPLOY.md) for the full webhook API.

## Plugin System

Create plugins by adding a directory to `plugins/` with a `plugin.json` manifest and a `plugin.py` entry point. Plugins can register custom tools, add lifecycle hooks, and access config.

See the [example plugin](plugins/example/) for a template.

## Safety

- Confirmation prompts for destructive actions
- Blocked command patterns (rm -rf /, mkfs, shutdown, etc.)
- Action logging to `logs/actions.jsonl`
- Emergency stop in the command center UI
- Max autonomous actions limit (default: 25)

## Models

Works with any Ollama-compatible model:

| Model | Size | RAM | Tool Calling | Good For |
|-------|------|-----|-------------|----------|
| qwen2.5:7b | 7B | 8GB | ✅ | Best tool calling |
| llama3.1:8b | 8B | 8GB | ✅ | General purpose |
| mistral:7b | 7B | 8GB | ✅ | Fast inference |
| llama3.2:3b | 3B | 4GB | ⚠️ | Low-end hardware |
| qwen2.5:14b | 14B | 16GB | ✅ | Higher quality |

HuggingFace models: `ollama pull hf.co/{user}/{repo}:{quantization}`

## License

MIT
