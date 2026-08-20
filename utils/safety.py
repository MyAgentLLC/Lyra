"""
Safety module — confirmation prompts, action logging, and guardrails.
"""

import json
import os
import time
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class SafetyChecker:
    def __init__(self, config: dict, confirmation_callback: Optional[Callable] = None):
        self.require_confirmation = set(config.get("require_confirmation", []))
        self.blocked_commands = config.get("blocked_commands", [])
        self.max_autonomous_actions = config.get("max_autonomous_actions", 25)
        self.action_log_path = config.get("action_log", "logs/actions.jsonl")
        
        os.makedirs(os.path.dirname(self.action_log_path), exist_ok=True) if os.path.dirname(self.action_log_path) else None
        
        self.confirmation_callback = confirmation_callback
        self.action_count = 0
        self.action_history = []

    def needs_confirmation(self, tool_name: str, tool_args: dict) -> bool:
        """Check if an action needs user confirmation."""
        # Reset counter if we're checking a new task
        if self.action_count >= self.max_autonomous_actions:
            return True
        
        if tool_name in self.require_confirmation:
            return True
        
        # Check for dangerous patterns in arguments
        args_str = json.dumps(tool_args).lower()
        for blocked in self.blocked_commands:
            if blocked.lower() in args_str:
                return True
        
        return False

    def check_command_safety(self, command: str) -> tuple:
        """Check if a shell command is safe to run.
        Returns (is_safe, reason)."""
        for blocked in self.blocked_commands:
            if blocked in command:
                return False, f"Command contains blocked pattern: '{blocked}'"
        
        # Check for suspicious patterns
        suspicious = [
            ("rm -rf", "Recursive force delete"),
            ("> /dev/sda", "Writing to disk device"),
            (":(){ :|:& };:", "Fork bomb"),
            ("chmod 777", "Setting world-writable permissions"),
        ]
        for pattern, reason in suspicious:
            if pattern in command:
                return False, f"Blocked: {reason}"
        
        return True, "OK"

    def log_action(self, tool_name: str, args: dict, result: dict, confirmed: bool = False):
        """Log an action to the action log."""
        entry = {
            "timestamp": time.time(),
            "tool": tool_name,
            "args": args,
            "result": result,
            "confirmed": confirmed,
            "action_number": self.action_count,
        }
        self.action_history.append(entry)
        self.action_count += 1
        
        try:
            with open(self.action_log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to log action: {e}")

    def reset_action_count(self):
        """Reset the action counter (new task)."""
        self.action_count = 0

    def get_action_history(self, limit: int = 50) -> list:
        """Get recent action history."""
        return self.action_history[-limit:]

    def emergency_stop(self):
        """Emergency stop — can be called to halt the agent."""
        logger.warning("EMERGENCY STOP triggered!")
        # This will be checked by the agent loop
        self.emergency_stopped = True

    def is_emergency_stopped(self) -> bool:
        """Check if emergency stop was triggered."""
        return getattr(self, "emergency_stopped", False)

    def clear_emergency_stop(self):
        """Clear the emergency stop flag."""
        self.emergency_stopped = False
