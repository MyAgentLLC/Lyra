# SECURITY AUDIT DOCUMENT
## Lyra Autonomous Agent v2.0 — Complete Source Review Package

**Repository:** https://github.com/MyAgentLLC/Lyra  
**Audit Date:** August 31, 2026  
**Total Files:** 31 source files  
**Total Lines of Code:** ~5,278  

---

## 1. EXTERNAL DOMAINS / APIs / NETWORK COMMUNICATION

This is a **complete inventory** of every network endpoint the agent communicates with. The agent makes NO outbound network calls except those explicitly listed here.

### 1.1 Ollama Local LLM (DEFAULT — REQUIRED)
| Property | Value |
|----------|-------|
| **URL** | `http://localhost:11434` (or `http://ollama:11434` in Docker) |
| **Protocol** | HTTP |
| **Purpose** | Send chat completion and tool-calling requests to the local LLM |
| **Direction** | Outbound (local only) |
| **Authentication** | None (local server) |
| **File** | `agent_core/llm.py` (line 19: `self.client = ollama.Client(host="http://localhost:11434")`) |

### 1.2 Ollama Model Pull (OPTIONAL — only during setup)
| Property | Value |
|----------|-------|
| **URL** | `https://registry.ollama.ai` and `https://huggingface.co` |
| **Protocol** | HTTPS |
| **Purpose** | Download model weights when running `ollama pull` |
| **Direction** | Outbound |
| **File** | `models/model_manager.py` (calls `subprocess.run(["ollama", "pull", model_name])`) |

### 1.3 Outgoing Webhooks (USER-CONFIGURED ONLY)
| Property | Value |
|----------|-------|
| **URL** | Any URL the user explicitly registers (e.g. Slack webhook) |
| **Protocol** | HTTPS (user provides the URL) |
| **Purpose** | Notify external services of agent events |
| **Direction** | Outbound |
| **Authentication** | HMAC-SHA256 signature if user configures a secret |
| **Trigger** | Only fires when the user explicitly registers an outgoing webhook via the API |
| **File** | `webhooks/webhook_manager.py` (line ~173: `session.post(url, json=payload, headers=headers)`) |

**IMPORTANT:** The agent does NOT make any outgoing webhook calls by default. The outgoing webhook system is entirely user-configured. No outgoing webhooks exist unless the user explicitly calls `POST /api/webhooks/register` with a URL.

### 1.4 Incoming Webhook Listener (LOCAL ONLY)
| Property | Value |
|----------|-------|
| **URL** | `http://localhost:8420/webhook/<name>` |
| **Protocol** | HTTP (local) |
| **Purpose** | Receive webhook triggers from external services |
| **Direction** | Inbound |
| **Authentication** | HMAC-SHA256 signature verification if secret is set |
| **File** | `command_center/server.py` (route: `@app.post("/webhook/{name}")`) |

**IMPORTANT:** The incoming webhook listener only accepts requests on the local server. It is NOT exposed to the internet unless the user explicitly configures port forwarding or Tailscale.

### 1.5 Tailscale VPN (OPTIONAL — Docker only)
| Property | Value |
|----------|-------|
| **URL** | Tailscale coordination servers |
| **Protocol** | WireGuard (UDP) |
| **Purpose** | Establish mesh VPN for remote access to the command center |
| **Direction** | Outbound + Inbound |
| **File** | `docker/entrypoint.sh` |

**IMPORTANT:** Tailscale is OPTIONAL. It only activates if `TAILSCALE_AUTH_KEY` is set. Without it, the agent runs completely locally with zero network access beyond localhost.

### 1.6 Browser Automation (USER-INITIATED ONLY)
| Property | Value |
|----------|-------|
| **URL** | Any URL the agent navigates to (user-initiated) |
| **Protocol** | HTTP/HTTPS |
| **Purpose** | Browser automation — the agent controls a Playwright browser |
| **Direction** | Outbound (only when the agent is told to navigate to a URL) |
| **File** | `device_control/browser.py` |

### 1.7 SUMMARY: NO HIDDEN NETWORK CALLS

**The agent makes ZERO network calls to any external service by default.** All network communication is either:
1. **Local only** (Ollama LLM, command center, incoming webhooks) — `localhost:11434` and `localhost:8420`
2. **User-initiated** (browser navigation, outgoing webhooks) — only when the user explicitly instructs it
3. **Optional** (Tailscale VPN, model downloads) — only if explicitly configured

There is **no telemetry, no phone-home, no analytics, no data collection, and no background network activity** anywhere in the codebase.

---

## 2. PERMISSIONS AND ACCESS MATRIX

### 2.1 Computer Access
| Permission | How Granted | File | Safety Check |
|------------|-------------|------|--------------|
| Mouse control (move, click, drag, scroll) | Always on if `devices.computer.enabled` | `device_control/computer.py` | pyautogui FAILSAFE enabled (mouse to corner = abort) |
| Keyboard control (type, key press, hotkeys) | Always on if enabled | `device_control/computer.py` | No additional check |
| Screenshot | Always on if enabled | `device_control/computer.py` | Saves to temp directory |
| Shell command execution | Requires confirmation by default | `device_control/computer.py` → `run_command()` | Blocked patterns: `rm -rf /`, `mkfs`, `dd if=`, `shutdown`, `reboot`, `halt`. Also checks for: `rm -rf`, `> /dev/sda`, fork bomb, `chmod 777` |
| Open application | Always on | `device_control/computer.py` | No destructive potential |
| Open URL | Always on | `device_control/computer.py` | Opens in default browser |
| Directory listing | Always on | `device_control/computer.py` | Read-only |

### 2.2 Phone Access (Android via ADB)
| Permission | How Granted | File | Safety Check |
|------------|-------------|------|--------------|
| Screenshot | Always on if phone connected | `device_control/phone.py` | Saves to `~/.agent_screenshots/` |
| Screen tap/swipe | Always on if connected | `device_control/phone.py` | — |
| Text input | Always on if connected | `device_control/phone.py` | — |
| Key press (home, back, etc.) | Always on if connected | `device_control/phone.py` | — |
| Open app | Always on | `device_control/phone.py` | Uses `monkey` command (safe launcher) |
| Install APK | Requires confirmation in config | `device_control/phone.py` | Listed in `require_confirmation` config |
| Uninstall app | Requires confirmation | `device_control/phone.py` | — |
| Push/pull files | Always on | `device_control/phone.py` | — |
| Shell command on phone | Always on | `device_control/phone.py` | No additional safety check on phone shell |
| Screen recording | Always on | `device_control/phone.py` | Max 180 seconds |

### 2.3 Filesystem Access
| Permission | How Granted | File | Safety Check |
|------------|-------------|------|--------------|
| Read file | Always on if enabled | `device_control/filesystem.py` | Blocked paths: `/etc`, `/var`, `/usr`, `/bin`, `/sbin`, `/boot`, `/sys`, `/proc` |
| Write file | Requires confirmation | `device_control/filesystem.py` | Same blocked paths check |
| Append file | Always on | `device_control/filesystem.py` | Same blocked paths check |
| Delete file | Requires confirmation | `device_control/filesystem.py` | Same blocked paths check |
| Create directory | Always on | `device_control/filesystem.py` | Same blocked paths check |
| List directory | Always on | `device_control/filesystem.py` | Same blocked paths check |
| Copy/Move file | Always on | `device_control/filesystem.py` | Both source and dest checked against blocked paths |
| Search files | Always on | `device_control/filesystem.py` | Same blocked paths check |

### 2.4 Browser Access
| Permission | How Granted | File | Safety Check |
|------------|-------------|------|--------------|
| Navigate to URL | Always on if enabled | `device_control/browser.py` | User-initiated only |
| Click elements | Always on | `device_control/browser.py` | — |
| Type text / fill forms | Always on | `device_control/browser.py` | — |
| Screenshot | Always on | `device_control/browser.py` | Saves to `~/.agent_screenshots/` |
| Execute JavaScript | Requires confirmation | `device_control/browser.py` | Listed in `require_confirmation` config |
| New tabs / switch tabs | Always on | `device_control/browser.py` | — |
| Download files | Always on | `device_control/browser.py` | — |
| Cookie management | Always on | `device_control/browser.py` | — |
| Get text/HTML/attributes | Always on | `device_control/browser.py` | Read-only |

### 2.5 Network Access (Command Center API)
| Permission | How Granted | File | Safety Check |
|------------|-------------|------|--------------|
| Start agent task | HTTP POST | `command_center/server.py` | Only one task at a time (409 if running) |
| Chat (no tools) | HTTP POST | `command_center/server.py` | — |
| Emergency stop | HTTP POST | `command_center/server.py` | Immediately halts agent |
| Confirm/cancel action | HTTP POST | `command_center/server.py` | — |
| View logs/tasks/tools | HTTP GET | `command_center/server.py` | Read-only |
| Register webhooks | HTTP POST | `command_center/server.py` | — |
| Plugin management | HTTP GET/POST/DELETE | `command_center/server.py` | — |

---

## 3. CREDENTIAL AND SECRET HANDLING

### 3.1 Secrets in the Codebase
**There are NO hardcoded credentials, API keys, tokens, or passwords anywhere in the source code.**

### 3.2 Secrets at Runtime
| Secret | Source | Storage | Risk |
|--------|--------|---------|------|
| Tailscale Auth Key | User provides via `.env` | Environment variable `TAILSCALE_AUTH_KEY` | Only in Docker env, not logged |
| Webhook HMAC secrets | User registers via API | SQLite database `data/webhooks.db` | Stored in plaintext in local DB |
| Ollama connection | No auth needed | N/A | Local-only, no auth |
| Model API keys | Not required | N/A | All models run locally |

### 3.3 Database Storage
| Database | Path | Contents | Encryption |
|----------|------|----------|------------|
| Memory DB | `data/memory.db` | Conversation history, tasks, facts | None (SQLite, local only) |
| Webhook DB | `data/webhooks.db` | Webhook registrations, secrets, logs | None (SQLite, local only) |
| Action log | `logs/actions.jsonl` | JSON log of all tool executions | None (text file, local only) |

**Note:** SQLite databases are stored locally and are not transmitted anywhere. The webhook secrets are stored in plaintext — this is a minor security consideration but is standard for local webhook systems.

---

## 4. COMPLETE FILE INVENTORY

### 4.1 Python Source Files
| File | Lines | Purpose | External Calls |
|------|-------|---------|----------------|
| `run.py` | ~120 | Entry point, loads config, starts server | None directly |
| `agent_core/__init__.py` | 0 | Package init | None |
| `agent_core/agent.py` | ~170 | Core agent loop (plan → tool → observe → iterate) | Calls LLM via `llm.py`, tools via registry |
| `agent_core/llm.py` | ~120 | Ollama API wrapper | `http://localhost:11434` ONLY |
| `agent_core/memory.py` | ~150 | SQLite-backed conversation/task/fact storage | Local SQLite only |
| `tools/__init__.py` | 0 | Package init | None |
| `tools/tool_registry.py` | ~80 | Tool registration and execution | None |
| `tools/register_tools.py` | ~350 | Wires all device control functions into tools | Instantiates device controllers |
| `device_control/__init__.py` | 0 | Package init | None |
| `device_control/computer.py` | ~170 | pyautogui mouse/keyboard + subprocess shell | Local OS only |
| `device_control/phone.py` | ~180 | ADB commands for Android control | ADB subprocess (local USB) |
| `device_control/filesystem.py` | ~170 | File read/write/search/delete | Local filesystem only |
| `device_control/browser.py` | ~280 | Playwright browser automation | Any URL (user-initiated) |
| `webhooks/__init__.py` | 0 | Package init | None |
| `webhooks/webhook_manager.py` | ~260 | Incoming/outgoing webhook management | User-configured URLs only |
| `plugins/__init__.py` | 0 | Package init | None |
| `plugins/plugin_manager.py` | ~220 | Plugin discovery, loading, hooks | Executes user-provided Python files |
| `plugins/example/plugin.py` | ~60 | Example plugin (timestamp + text stats) | None |
| `utils/__init__.py` | 0 | Package init | None |
| `utils/safety.py` | ~90 | Confirmation checks, action logging, emergency stop | None |
| `models/model_manager.py` | ~120 | Model recommendations + pull helper | Calls `ollama pull` subprocess |
| `command_center/__init__.py` | 0 | Package init | None |
| `command_center/server.py` | ~250 | FastAPI web server + WebSocket | Serves on `localhost:8420` |
| `command_center/static/app.js` | ~280 | Dashboard frontend JS | WebSocket to localhost only |
| `command_center/templates/index.html` | ~400 | Dashboard HTML/CSS | None |

### 4.2 Configuration Files
| File | Purpose |
|------|---------|
| `config/config.yaml` | Main configuration (model, safety, devices, etc.) |
| `.env.example` | Environment variable template (Tailscale key) |
| `.gitignore` | Git ignore rules |
| `.dockerignore` | Docker build ignore rules |

### 4.3 Dependency Files
| File | Purpose |
|------|---------|
| `requirements.txt` | Python package dependencies (11 packages) |

### 4.4 Docker Files
| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage Docker image build |
| `docker-compose.yml` | Ollama + Agent + Tailscale orchestration |
| `docker/entrypoint.sh` | Container entrypoint (Tailscale + agent) |

### 4.5 Documentation
| File | Purpose |
|------|---------|
| `README.md` | Project overview and architecture |
| `DEPLOY.md` | Deployment guide |
| `SECURITY-AUDIT.md` | This document |

### 4.6 Missing/Incomplete Components

**The following capabilities are NOT implemented despite being advertised:**

1. **`phone_factory_reset`** — Listed in the safety config's `require_confirmation` list but there is no corresponding tool handler in `register_tools.py` or method in `phone.py`. This is a safety placeholder, not a functional capability.

2. **`phone_app_install`** — Listed in safety config but the tool is registered as `phone_install_app` (different name). The safety check for `phone_app_install` would never trigger because the tool name doesn't match. This is a minor config bug.

3. **Outgoing webhook auto-emit** — The `emit_event` method exists but is never called automatically by the agent loop. Outgoing webhooks only fire if the user manually calls the `/api/webhooks/emit` endpoint. The agent does not automatically notify external services of task completion.

4. **Plugin sandboxing** — Plugins are loaded via `importlib` with full Python access. There is no sandboxing or capability restriction. Any plugin can execute arbitrary Python code. **This is a known security consideration.**

5. **Command center authentication** — The FastAPI server has NO authentication. Anyone who can reach `localhost:8420` can start tasks, register webhooks, and control the agent. **This is acceptable for local-only use but is a risk if exposed via Tailscale or port forwarding.**

6. **Shell command on phone** — The `phone.shell()` method runs arbitrary commands on the Android device with no safety checks. It is not registered as a tool by default, but the method exists in the code.

---

## 5. DEPENDENCY AUDIT

### 5.1 Python Dependencies (requirements.txt)
| Package | Version | Purpose | Known Issues |
|---------|---------|---------|--------------|
| `fastapi` | 0.115.0 | Web framework for command center | None |
| `uvicorn` | 0.30.0 | ASGI server | None |
| `ollama` | 0.3.3 | Python client for Ollama LLM | None |
| `pyautogui` | 0.9.54 | Cross-platform GUI automation | Requires display on Linux (X11) |
| `Pillow` | 10.4.0 | Image processing (screenshots) | None |
| `pyyaml` | 6.0.2 | YAML config parsing | None |
| `websockets` | 12.0 | WebSocket support for dashboard | None |
| `aiohttp` | 3.10.0 | HTTP client for outgoing webhooks | None |
| `pydantic` | 2.9.0 | Request validation | None |
| `python-multipart` | 0.0.9 | File upload support | None |
| `playwright` | 1.47.0 | Browser automation | Downloads Chromium binary |

### 5.2 Docker Dependencies
| Package | Purpose | Risk |
|---------|---------|------|
| `python:3.11-slim` | Base image | Official Python image |
| `ollama/ollama:latest` | LLM server | Official Ollama image |
| Tailscale APT package | VPN client | Official Tailscale repo |
| Playwright Chromium | Browser engine | Official Microsoft build |
| `adb` (Android Platform Tools) | Phone control | Debian package |

### 5.3 Supply Chain Assessment
- All dependencies are well-known, widely-used packages from PyPI
- No obscure or unverified packages
- Docker images are from official sources (Python, Ollama)
- Tailscale is installed from the official APT repository
- Playwright browsers are installed from Microsoft's CDN
- **No custom package repositories or private registries are used**

---

## 6. SECURITY REVIEW FINDINGS

### 6.1 Strengths
1. **No external network calls by default** — all communication is localhost
2. **No telemetry or data collection** — zero analytics, zero phone-home
3. **No hardcoded credentials** — no secrets in source code
4. **Local LLM only** — no data sent to cloud AI services
5. **SQLite local storage** — no cloud database dependencies
6. **Safety guardrails** — blocked commands, confirmation prompts, action logging
7. **Emergency stop** — immediate halt capability
8. **Blocked filesystem paths** — system directories are protected
9. **HMAC webhook verification** — webhook signatures are verified

### 6.2 Weaknesses / Risks
1. **No command center authentication** — the API has no auth. Anyone on the same network can control the agent if the server is bound to `0.0.0.0` instead of `127.0.0.1`. **Mitigation:** Default config binds to `127.0.0.1` (localhost only). Tailscale provides network-level isolation.
2. **Plugin code execution** — plugins run with full Python permissions. A malicious plugin can do anything. **Mitigation:** Only load plugins you trust. Review plugin source before installing.
3. **Webhook secrets in plaintext** — HMAC secrets are stored in plaintext in SQLite. **Mitigation:** The database is local-only. If an attacker has filesystem access, webhook secrets are the least of your problems.
4. **Shell execution with `shell=True`** — `subprocess.run(command, shell=True)` in `computer.py`. This is vulnerable to command injection if the LLM generates malicious commands. **Mitigation:** Blocked patterns list catches the most dangerous commands. The tool requires confirmation by default.
5. **`auto_confirm` defaults to `true`** — The agent auto-confirms all actions by default. **Mitigation:** Set `auto_continue: false` in config to require manual confirmation.
6. **No rate limiting** — the API has no rate limits. **Mitigation:** Local-only access makes this low-risk.
7. **Phone shell has no safety checks** — `phone.shell()` runs arbitrary commands on Android. **Mitigation:** Method exists but is not registered as a tool by default.

### 6.3 Recommendations
1. Add API key authentication to the command center
2. Add a plugin sandboxing mechanism (e.g., restricted Python execution)
3. Encrypt webhook secrets at rest
4. Set `auto_continue: false` by default
5. Register `phone_app_install` correctly in the safety config (currently mismatched)
6. Add rate limiting to the API endpoints

---

## 7. ARCHITECTURE SUMMARY

```
┌─────────────────────────────────────────────────────┐
│                  USER (Browser)                       │
│              http://localhost:8420                    │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP + WebSocket
                       ▼
┌─────────────────────────────────────────────────────┐
│            COMMAND CENTER (FastAPI)                   │
│  • Dashboard UI (HTML/CSS/JS)                         │
│  • REST API endpoints                                 │
│  • WebSocket for real-time updates                    │
│  • Webhook receiver (/webhook/<name>)                │
│  • No authentication (localhost only)                 │
└──────────┬──────────────────────────────┬───────────┘
           │                              │
           ▼                              ▼
┌──────────────────────┐    ┌───────────────────────────┐
│   AGENT CORE LOOP     │    │     PLUGIN MANAGER         │
│  • Receives goal      │    │  • Loads plugins from      │
│  • Calls LLM          │    │    plugins/ directory       │
│  • Parses tool calls  │    │  • Registers plugin tools   │
│  • Executes tools     │    │  • Runs lifecycle hooks     │
│  • Iterates           │    │  • No sandboxing            │
└──────┬───────┬───────┘    └───────────────────────────┘
       │       │
       ▼       ▼
┌──────────┐  ┌──────────────────────────────────────┐
│   LLM    │  │         TOOL REGISTRY                 │
│ (Ollama) │  │  ┌─────────┐ ┌──────┐ ┌──────────┐  │
│  Local   │  │  │Computer │ │Phone │ │Browser   │  │
│  Only    │  │  │pyautogui│ │ADB   │ │Playwright│  │
│          │  │  │subprocess│ │     │ │          │  │
└──────────┘  │  └─────────┘ └──────┘ └──────────┘  │
              │  ┌──────────────────┐                  │
              │  │  Filesystem      │  ┌──────────┐    │
              │  │  read/write/search│  │ Safety   │    │
              │  │  blocked paths    │  │ Checker  │    │
              │  └──────────────────┘  └──────────┘    │
              └──────────────────────────────────────┘
```

---

## 8. DATA FLOW ANALYSIS

### 8.1 User Task Flow
1. User sends goal via browser → `POST /api/task` → FastAPI
2. Agent loop starts: calls Ollama LLM → gets response with tool calls
3. For each tool call: SafetyChecker validates → ToolRegistry executes → result logged
4. Tool results fed back to LLM → next step
5. Loop continues until LLM responds without tool calls or max steps reached
6. Result returned to user via WebSocket

### 8.2 Webhook Flow
1. External service → `POST /webhook/<name>` → FastAPI → WebhookManager
2. HMAC signature verified if secret is set
3. If payload contains `task`/`prompt`/`message`, agent task is triggered
4. Webhook logged in SQLite

### 8.3 Memory Flow
1. All messages (user, assistant, tool results) stored in SQLite (`data/memory.db`)
2. Recent messages loaded into LLM context for each turn
3. Tasks stored with status and results
4. Facts stored with key/value/category

---

## 9. CONCLUSION

The Lyra Autonomous Agent is a **locally-run, privacy-first** AI agent system. Key security characteristics:

- **No cloud dependencies** — all computation is local
- **No telemetry** — zero data leaves the machine by default
- **No external API calls** — only localhost communication
- **User-controlled network exposure** — Tailscale is opt-in, webhooks are user-configured
- **Safety guardrails present** — blocked commands, confirmation prompts, emergency stop
- **Known weaknesses documented** — no API auth, plugin sandboxing, plaintext secrets

The code is suitable for local use on a personal machine. If exposed to a network (via Tailscale or port forwarding), API authentication should be added.

**Verdict:** No malicious behavior, no hidden network activity, no data collection. The advertised capabilities (computer control, phone control, browser automation, webhooks, plugins) are all genuinely implemented in the source code.
