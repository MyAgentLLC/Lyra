"""
Example plugin — shows how to build a plugin for the Autonomous Agent.

A plugin is a Python file with a setup(api) function that receives a PluginAPI.
Use the API to register tools, add hooks, and access config.

Available hooks:
  - before_task(goal: str) -> called before agent starts a task
  - after_task(result: dict) -> called after agent finishes a task
  - before_tool_call(name: str, args: dict) -> before a tool executes
  - after_tool_call(name: str, result: dict) -> after a tool executes
  - on_error(error: str) -> when an error occurs
  - on_start() -> when the agent starts up
  - on_shutdown() -> when the agent shuts down
"""

import time


def setup(api):
    """Initialize the plugin. Called when the plugin is loaded."""
    api.log("Example plugin loaded!")
    
    # Register a custom tool
    api.register_tool(
        name="get_timestamp",
        description="Get the current Unix timestamp and formatted date.",
        parameters={"type": "object", "properties": {}},
        handler=get_timestamp,
        category="example",
    )
    
    api.register_tool(
        name="text_stats",
        description="Get statistics about a text string (word count, char count, etc.).",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to analyze"},
            },
            "required": ["text"],
        },
        handler=text_stats,
        category="example",
    )
    
    # Register hooks
    api.add_hook("before_task", on_before_task)
    api.add_hook("after_task", on_after_task)
    api.add_hook("on_start", on_start)
    
    api.log(f"Registered {len(api._tools_added)} tools", "debug")


def teardown():
    """Called when the plugin is unloaded. Optional."""
    pass


# === Tool Handlers ===

def get_timestamp(**kwargs):
    """Get current timestamp."""
    now = time.time()
    return {
        "unix": now,
        "iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
        "timezone": time.tzname,
    }


def text_stats(**kwargs):
    """Get text statistics."""
    text = kwargs.get("text", "")
    words = text.split()
    return {
        "characters": len(text),
        "characters_no_spaces": len(text.replace(" ", "")),
        "words": len(words),
        "lines": text.count("\n") + 1,
        "sentences": text.count(".") + text.count("!") + text.count("?"),
    }


# === Hook Handlers ===

def on_before_task(goal):
    """Called before the agent starts a task."""
    print(f"  [example plugin] Task starting: {goal[:80]}")

def on_after_task(result):
    """Called after the agent finishes a task."""
    print(f"  [example plugin] Task finished: {result.get('status', 'unknown')}")

def on_start():
    """Called when the agent starts up."""
    print("  [example plugin] Agent started — example plugin is active")
