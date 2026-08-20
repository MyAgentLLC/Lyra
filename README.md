# Autonomous Local Agent v2.0

A fully autonomous, locally-run AI agent that can control your computer, phone, browser, and other devices. Uses local models from HuggingFace via Ollama. 100% free, 100% private — everything runs on your machine.

## What It Does

- **Computer Control**: Mouse, keyboard, screenshots, file operations, shell commands
- **Phone Control**: Android device control via ADB (screenshots, taps, swipes, app launches)
- **Browser Automation**: Full browser control via Playwright (navigate, click, type, screenshot, JS execution, tabs, downloads)
- **Webhooks**: Incoming webhook endpoints for external services to trigger agent tasks; outgoing webhooks to notify external services of events
- **Plugin System**: Drop-in plugins that add custom tools and hooks to the agent
- **Command Center**: Web-based dashboard to monitor and direct the agent
- **Local Models**: Runs entirely on local LLMs via Ollama (Llama 3.1, Qwen2.5, Mistral, etc.)
- **Autonomous Task Execution**: Give it a goal, it plans and executes step by step
- **Tool Calling**: Function calling for structured actions
- **Memory**: Persistent conversation and task memory

## Quick Start

### 1. Install Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows
# Download from https://ollama.com/download
```

### 2. Pull a Model

```bash
# Recommended: Qwen 2.5 7B (best tool calling)
ollama pull qwen2.5:7b

# Or Llama 3.1 8B
ollama pull llama3.1

# Or from HuggingFace directly (GGUF format)
ollama pull hf.co/Qwen/Qwen2.5-7B-Instruct-GGUF:Q4_K_M
```

### 3. Install and Run

```bash
cd autonomous-agent
chmod +x setup.sh && ./setup.sh
python run.py
```

Then open http://localhost:8420 in your browser.

### 4. (Optional) Set Up Android Control

```bash
# Install ADB
# macOS: brew install android-platform-tools
# Linux: sudo apt install adb

# Enable USB debugging on your phone, then:
adb devices
```

## Architecture

```
autonomous-agent/
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
│       ├── plugin.json           # Plugin manifest
│       └── plugin.py             # Plugin code
├── tools/
│   ├── tool_registry.py          # Tool definitions
│   └── register_tools.py         # Registers all built-in tools
├── utils/safety.py               # Safety checks
├── models/model_manager.py       # Model management
├── requirements.txt
└── setup.sh
```

## Browser Automation

The agent can control a real browser using Playwright:

```python
# The agent can do all of this via natural language:
"Go to google.com and search for 'latest AI news'"
"Fill out the form on that page with my details"
"Take a screenshot of the page"
"Click the login button"
"Scroll down and find the pricing table"
"Download the PDF from that link"
```

Features: navigation, clicking, typing, form filling, screenshots, JavaScript execution, scrolling, tab management, link extraction, file downloads, cookie management.

**Install browsers after pip install:**
```bash
python -m playwright install chromium
```

## Webhooks

### Incoming Webhooks

External services can trigger the agent by POSTing to a webhook endpoint:

```bash
# Register an incoming webhook
curl -X POST http://localhost:8420/api/webhooks/register \
  -H "Content-Type: application/json" \
  -d '{"name": "github-push", "secret": "my-secret"}'

# External service sends a request
curl -X POST http://localhost:8420/webhook/github-push \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: <hmac>" \
  -d '{"task": "Check the latest git push and run tests", "event": "push"}'
```

The agent will automatically start a task if the payload contains a `task`, `prompt`, or `message` field.

### Outgoing Webhooks

The agent can notify external services when events happen:

```bash
# Register an outgoing webhook
curl -X POST http://localhost:8420/api/webhooks/register \
  -H "Content-Type: application/json" \
  -d '{"name": "notify-slack", "url": "https://hooks.slack.com/...", "event_types": ["task_completed", "error"]}'
```

### Manage Webhooks

```bash
# List all webhooks
curl http://localhost:8420/api/webhooks

# View incoming/outgoing logs
curl http://localhost:8420/api/webhooks/incoming/log
curl http://localhost:8420/api/webhooks/outgoing/log

# Emit an event manually
curl -X POST "http://localhost:8420/api/webhooks/emit?event_type=task_completed" \
  -H "Content-Type: application/json" -d '{"message": "Done!"}'
```

## Plugin System

Create plugins by adding a directory to `plugins/` with a `plugin.json` manifest and a `plugin.py` entry point:

```
plugins/my_plugin/
├── plugin.json    # Manifest
└── plugin.py      # Code
```

### plugin.json

```json
{
    "name": "my_plugin",
    "version": "1.0.0",
    "description": "My custom plugin",
    "entry_point": "plugin.py",
    "config": {}
}
```

### plugin.py

```python
def setup(api):
    """Called when the plugin loads."""
    api.log("My plugin loaded!")
    
    # Register a tool the agent can call
    api.register_tool(
        name="my_tool",
        description="Does something cool",
        parameters={"type": "object", "properties": {"input": {"type": "string"}}},
        handler=my_handler,
        category="custom",
    )
    
    # Hook into agent lifecycle events
    api.add_hook("before_task", lambda goal: print(f"Starting: {goal}"))
    api.add_hook("after_task", lambda result: print(f"Done: {result['status']}"))

def my_handler(**kwargs):
    return {"result": "Did something cool with: " + kwargs.get("input", "")}

def teardown():
    """Called when the plugin unloads. Optional."""
    pass
```

### Available Hooks

| Hook | When | Arguments |
|------|------|-----------|
| `on_start` | Agent starts up | (none) |
| `on_shutdown` | Agent shuts down | (none) |
| `before_task` | Before a task begins | `goal: str` |
| `after_task` | After a task finishes | `result: dict` |
| `before_tool_call` | Before a tool executes | `name: str, args: dict` |
| `after_tool_call` | After a tool executes | `name: str, result: dict` |
| `on_error` | When an error occurs | `error: str` |

### Manage Plugins

```bash
# List loaded plugins
curl http://localhost:8420/api/plugins

# Reload all plugins
curl -X POST http://localhost:8420/api/plugins/reload

# Reload a specific plugin
curl -X POST http://localhost:8420/api/plugins/my_plugin/reload

# Unload a plugin
curl -X DELETE http://localhost:8420/api/plugins/my_plugin
```

## Safety

- **Confirmation prompts** for destructive actions (shell commands, file writes, JS execution)
- **Blocked command patterns** (rm -rf /, mkfs, shutdown, etc.)
- **Action logging** — everything is logged to `logs/actions.jsonl`
- **Emergency stop** — kill switch in the command center UI
- **Max autonomous actions** — stops after 25 consecutive actions by default

## Models

Works with any Ollama-compatible model:

| Model | Size | RAM | Tool Calling | Good For |
|-------|------|-----|-------------|----------|
| qwen2.5:7b | 7B | 8GB | ✅ | Best tool calling |
| llama3.1:8b | 8B | 8GB | ✅ | General purpose |
| mistral:7b | 7B | 8GB | ✅ | Fast inference |
| llama3.2:3b | 3B | 4GB | ⚠️ | Low-end hardware |
| qwen2.5:14b | 14B | 16GB | ✅ | Higher quality |
| llama3.1:70b | 70B | 48GB | ✅ | Best quality (GPU) |

HuggingFace models: `ollama pull hf.co/{user}/{repo}:{quantization}`

## License

MIT
