#!/usr/bin/env python3
"""
Lyra terminal chat — talk to her directly in Termux, no browser needed.

Usage:
    python chat.py                          (auto-detects mobile/desktop config)
    python chat.py --config config/config.mobile.yaml

Commands inside the chat:
    /help    show commands
    /tools   list available tools
    /status  show agent status
    /reset   clear the conversation (memory of facts/tasks is kept)
    /exit    quit (or Ctrl+C / Ctrl+D)
"""

import sys
import os
import asyncio

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from run import load_config  # noqa: E402


def pick_config() -> str:
    for arg in sys.argv[1:]:
        if arg == "--config" and sys.argv.index(arg) + 1 < len(sys.argv):
            return sys.argv[sys.argv.index(arg) + 1]
    # Auto-detect: Termux defaults to the mobile config
    if "com.termux" in os.environ.get("PREFIX", ""):
        mobile = os.path.join(PROJECT_DIR, "config", "config.mobile.yaml")
        if os.path.exists(mobile):
            return mobile
    return os.path.join(PROJECT_DIR, "config", "config.yaml")


def build_agent(config: dict):
    """Assemble the agent exactly like run.py does."""
    from agent_core.llm import LLMInterface
    from agent_core.memory import AgentMemory
    from agent_core.agent import Agent
    from utils.safety import SafetyChecker
    from tools.register_tools import build_tool_registry

    llm_cfg = config.get("model", {})
    llm = LLMInterface(
        model_name=llm_cfg.get("name", "llama3.1"),
        temperature=llm_cfg.get("temperature", 0.7),
        max_tokens=llm_cfg.get("max_tokens", 4096),
        system_prompt=llm_cfg.get("system_prompt", ""),
    )
    memory = AgentMemory(config.get("memory", {}).get("db_path", "data/memory.db"))
    safety = SafetyChecker(config.get("safety", {}))
    tools = build_tool_registry(config)
    agent = Agent(llm, tools, memory, safety, config)

    # Load plugins too — same as the command center
    if config.get("plugins", {}).get("enabled", True):
        from plugins.plugin_manager import PluginManager
        pm = PluginManager(
            plugins_dir=os.path.join(PROJECT_DIR, "plugins"),
            tool_registry=tools,
            agent=agent,
            config=config,
        )
        pm.load_all()
        agent.plugin_manager = pm
        pm.run_hook("on_start")
    return agent


def main():
    config_path = pick_config()
    config = load_config(config_path)
    agent = build_agent(config)

    # Live-print what she's doing
    def on_tool_call(d):
        args = str(d.get("args", {}))
        if len(args) > 120:
            args = args[:120] + "..."
        print(f"\n  ⚙ {d.get('tool')}{args}")

    def on_tool_result(d):
        r = str(d.get("result", ""))
        if len(r) > 200:
            r = r[:200] + "..."
        print(f"  ↳ {r}")

    def on_error(d):
        print(f"\n  ✗ error: {d.get('error')}")

    agent.on_tool_call = on_tool_call
    agent.on_tool_result = on_tool_result
    agent.on_error = on_error

    print()
    print("    ◈  Lyra — terminal chat")
    print(f"       model: {config.get('model', {}).get('name', '?')}  |  tools: {len(agent.tools.tools)}")
    print("       type /help for commands, /exit to quit")
    print()

    if not agent.llm.check_connection():
        print("  ⚠ Can't reach Ollama. Start it with: bash lyra.sh start")
        print()

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n    Bye. Lyra keeps her memory — just run chat.py again.\n")
            break

        if not user_input:
            continue

        if user_input in ("/exit", "/quit"):
            print("\n    Bye. Lyra keeps her memory — just run chat.py again.\n")
            break
        if user_input == "/help":
            print("  /help /tools /status /reset /exit")
            continue
        if user_input == "/tools":
            cats = agent.tools.list_by_category()
            for cat, names in sorted(cats.items()):
                print(f"  [{cat}] {', '.join(names)}")
            continue
        if user_input == "/status":
            s = agent.get_status()
            print(f"  {s}")
            continue
        if user_input == "/reset":
            agent.memory.clear_conversation()
            print("  Conversation cleared. Facts and tasks are kept.")
            continue

        print()
        try:
            result = asyncio.run(agent.run_task(user_input))
        except KeyboardInterrupt:
            print("\n  (interrupted)")
            continue
        except Exception as e:
            print(f"  ✗ {e}\n    If Ollama was killed in the background, run: bash lyra.sh restart")
            continue

        reply = result.get("response") or result.get("message") or "(no response)"
        print(f"\nLyra> {reply}\n")


if __name__ == "__main__":
    main()
