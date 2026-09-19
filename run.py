#!/usr/bin/env python3
"""
Autonomous Agent — Main Entry Point
Starts the command center server and initializes the agent with all subsystems.
"""

import sys
import os
import yaml
import logging
import uvicorn

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(PROJECT_DIR, "agent.log")),
    ]
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = None) -> dict:
    if not config_path:
        # Allow: python3 run.py --config config/config.mobile.yaml
        #   or:  CONFIG=config/mobile.yaml python3 run.py
        config_path = os.environ.get("LYRA_CONFIG")
        if not config_path:
            for i, arg in enumerate(sys.argv):
                if arg == "--config" and i + 1 < len(sys.argv):
                    config_path = sys.argv[i + 1]
                    break
    if not config_path:
        config_path = os.path.join(PROJECT_DIR, "config", "config.yaml")
    
    if not os.path.exists(config_path):
        logger.warning(f"Config file not found: {config_path}. Using defaults.")
        return {
            "model": {"name": "llama3.1", "temperature": 0.7, "max_tokens": 4096,
                      "system_prompt": "You are an autonomous AI agent. You can control the computer, phone, browser, and filesystem."},
            "server": {"host": "127.0.0.1", "port": 8420},
            "safety": {"require_confirmation": ["shell_command", "file_delete", "file_write"],
                       "blocked_commands": ["rm -rf /", "mkfs"], "max_autonomous_actions": 25,
                       "action_log": "logs/actions.jsonl"},
            "devices": {"computer": {"enabled": True, "screen_scale": 1.0},
                        "phone": {"enabled": True, "device_serial": "", "screenshot_quality": 80},
                        "filesystem": {"enabled": True, "allowed_roots": [], "blocked_paths": ["/etc", "/var"]},
                        "browser": {"enabled": True, "headless": True, "browser_type": "chromium", "timeout": 30000}},
            "memory": {"db_path": "data/memory.db", "max_context_turns": 20, "max_tasks": 100},
            "agent": {"planning_depth": 5, "auto_continue": True, "action_delay": 0.5},
            "webhooks": {"enabled": True, "db_path": "data/webhooks.db"},
            "plugins": {"enabled": True, "directory": "plugins"},
        }
    
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    logger.info(f"Configuration loaded from {config_path}")
    return config


def main():
    print("""
    ╔══════════════════════════════════════════════════╗
    ║                                                  ║
    ║         ◈  AUTONOMOUS AGENT v2.0                ║
    ║         Local AI Agent Command Center             ║
    ║         Browser · Webhooks · Plugins              ║
    ║                                                  ║
    ╚══════════════════════════════════════════════════╝
    """)
    
    config = load_config()
    logger.info("Initializing agent components...")
    
    # LLM interface
    from agent_core.llm import LLMInterface
    llm_config = config.get("model", {})
    llm = LLMInterface(
        model_name=llm_config.get("name", "llama3.1"),
        temperature=llm_config.get("temperature", 0.7),
        max_tokens=llm_config.get("max_tokens", 4096),
        system_prompt=llm_config.get("system_prompt", ""),
    )
    
    if llm.check_connection():
        logger.info(f"✓ Connected to Ollama with model '{llm.model}'")
    else:
        logger.warning("⚠ Could not connect to Ollama or model not found.")
        logger.warning("  Make sure Ollama is running: 'ollama serve'")
        logger.warning(f"  And the model is pulled: 'ollama pull {llm.model}'")
        logger.warning("  The command center will start anyway — you can fix this later.")
    
    # Memory
    from agent_core.memory import AgentMemory
    memory = AgentMemory(config.get("memory", {}).get("db_path", "data/memory.db"))
    logger.info("✓ Memory initialized")
    
    # Safety
    from utils.safety import SafetyChecker
    safety = SafetyChecker(config.get("safety", {}))
    logger.info("✓ Safety checker initialized")
    
    # Tools (includes browser automation)
    from tools.register_tools import build_tool_registry
    tools = build_tool_registry(config)
    logger.info(f"✓ {len(tools.tools)} tools registered")
    
    # Agent
    from agent_core.agent import Agent
    agent = Agent(llm, tools, memory, safety, config)
    logger.info("✓ Agent initialized")
    
    # Webhook manager
    webhook_manager = None
    webhook_config = config.get("webhooks", {})
    if webhook_config.get("enabled", True):
        from webhooks.webhook_manager import WebhookManager
        webhook_manager = WebhookManager(
            db_path=webhook_config.get("db_path", "data/webhooks.db"),
            agent=agent,
        )
        agent.webhook_manager = webhook_manager
        logger.info("✓ Webhook manager initialized")
    
    # Plugin manager
    plugin_manager = None
    plugin_config = config.get("plugins", {})
    if plugin_config.get("enabled", True):
        from plugins.plugin_manager import PluginManager
        plugins_dir = os.path.join(PROJECT_DIR, plugin_config.get("directory", "plugins"))
        plugin_manager = PluginManager(
            plugins_dir=plugins_dir,
            tool_registry=tools,
            agent=agent,
            config=config,
        )
        results = plugin_manager.load_all()
        agent.plugin_manager = plugin_manager
        logger.info(f"✓ Plugin system initialized ({results['loaded']} plugins loaded)")
        # Run on_start hooks
        plugin_manager.run_hook("on_start")
    
    # Create and start server
    from command_center.server import create_app
    app = create_app(agent, tools, memory, config,
                     webhook_manager=webhook_manager,
                     plugin_manager=plugin_manager)
    
    server_config = config.get("server", {})
    host = server_config.get("host", "127.0.0.1")
    port = server_config.get("port", 8420)
    
    logger.info(f"✓ Command center starting at http://{host}:{port}")
    print(f"\n    Command Center:  http://{host}:{port}")
    print(f"    Webhook base:    http://{host}:{port}/webhook/<name>")
    print(f"    Tools:           {len(tools.tools)}")
    if plugin_manager:
        print(f"    Plugins:         {len(plugin_manager.plugins)} loaded")
    print(f"\n    Press Ctrl+C to stop.\n")
    
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n    Agent shutting down. Goodbye!\n")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n    Error: {e}\n")
        print("    Check agent.log for details.\n")
        sys.exit(1)
