"""
Core agent — the main autonomous loop.
Plans, executes tools, observes results, and iterates.
"""

import json
import time
import logging
import asyncio
from typing import Optional, Callable

from .llm import LLMInterface
from .memory import AgentMemory
from tools.tool_registry import ToolRegistry
from utils.safety import SafetyChecker

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, llm: LLMInterface, tools: ToolRegistry, memory: AgentMemory,
                 safety: SafetyChecker, config: dict):
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self.safety = safety
        self.config = config
        
        self.is_running = False
        self.current_task_id = None
        self.step_count = 0
        self.max_steps = config.get("agent", {}).get("planning_depth", 5) * 10
        
        # Callbacks for the command center
        self.on_thinking: Optional[Callable] = None
        self.on_tool_call: Optional[Callable] = None
        self.on_tool_result: Optional[Callable] = None
        self.on_response: Optional[Callable] = None
        self.on_confirmation_request: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

    def _emit(self, callback, data):
        """Emit an event to a callback if set."""
        if callback:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    async def run_task(self, goal: str, auto_confirm: bool = None) -> dict:
        """
        Run a task autonomously.
        
        Args:
            goal: What the user wants the agent to do
            auto_confirm: Override the auto_confirm setting
            
        Returns:
            Final result dict
        """
        if auto_confirm is None:
            auto_confirm = self.config.get("agent", {}).get("auto_continue", True)
        
        self.is_running = True
        self.safety.reset_action_count()
        self.safety.clear_emergency_stop()
        
        # Create task in memory
        self.current_task_id = self.memory.create_task(goal)
        self.step_count = 0
        
        # Add the user's goal to conversation
        self.memory.add_message("user", goal)
        self._emit(self.on_thinking, {"step": 0, "message": "Starting task...", "goal": goal})
        
        # Get conversation context
        messages = self.memory.get_messages_for_context(
            max_turns=self.config.get("memory", {}).get("max_context_turns", 20)
        )
        
        result = {"status": "completed", "goal": goal, "steps": []}
        
        while self.is_running and self.step_count < self.max_steps:
            # Check emergency stop
            if self.safety.is_emergency_stopped():
                result["status"] = "stopped"
                result["message"] = "Emergency stop triggered"
                break
            
            self.step_count += 1
            self._emit(self.on_thinking, {
                "step": self.step_count,
                "message": f"Thinking (step {self.step_count})..."
            })
            
            try:
                # Call LLM with tools
                tools = self.tools.get_ollama_tools()
                response = self.llm.chat_with_tools(messages, tools)
                
                # Log assistant response
                if response["content"]:
                    self.memory.add_message("assistant", response["content"])
                    self._emit(self.on_response, {
                        "step": self.step_count,
                        "content": response["content"]
                    })
                
                # Process tool calls
                if response["tool_calls"]:
                    for tool_call in response["tool_calls"]:
                        tool_name = tool_call["name"]
                        tool_args = tool_call.get("arguments", {})
                        
                        self._emit(self.on_tool_call, {
                            "step": self.step_count,
                            "tool": tool_name,
                            "args": tool_args
                        })
                        
                        # Check if confirmation needed
                        needs_confirmation = self.safety.needs_confirmation(tool_name, tool_args)
                        
                        if needs_confirmation and not auto_confirm:
                            # Request confirmation from user
                            confirmed = False
                            if self.on_confirmation_request:
                                confirmed = await self.on_confirmation_request({
                                    "step": self.step_count,
                                    "tool": tool_name,
                                    "args": tool_args
                                })
                            
                            if not confirmed:
                                # Add a message telling the LLM the action was cancelled
                                cancel_msg = f"User cancelled the action '{tool_name}'."
                                self.memory.add_message("user", cancel_msg)
                                messages = self.memory.get_messages_for_context()
                                continue
                        elif needs_confirmation and auto_confirm:
                            # Auto-confirmed but still log it
                            self._emit(self.on_tool_call, {
                                "step": self.step_count,
                                "tool": tool_name,
                                "args": tool_args,
                                "auto_confirmed": True
                            })
                        
                        # Execute the tool
                        tool_result = self.tools.execute(tool_name, tool_args)
                        
                        # Log the action
                        self.safety.log_action(tool_name, tool_args, tool_result,
                                              confirmed=needs_confirmation)
                        
                        self._emit(self.on_tool_result, {
                            "step": self.step_count,
                            "tool": tool_name,
                            "result": tool_result
                        })
                        
                        # Add tool result to conversation
                        result_str = json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
                        # Truncate long results
                        if len(result_str) > 4000:
                            result_str = result_str[:4000] + "\n...[truncated]"
                        
                        messages.append({
                            "role": "tool",
                            "content": result_str,
                        })
                        self.memory.add_message("tool", result_str)
                        
                        result["steps"].append({
                            "step": self.step_count,
                            "tool": tool_name,
                            "args": tool_args,
                            "result": tool_result,
                        })
                    
                    # Continue loop — LLM will process tool results
                    continue
                
                else:
                    # No tool calls — agent is done or wants to respond
                    if response["content"]:
                        result["response"] = response["content"]
                        result["status"] = "completed"
                    else:
                        result["status"] = "completed"
                        result["message"] = "Agent finished without final response"
                    break
                    
            except Exception as e:
                logger.error(f"Agent loop error at step {self.step_count}: {e}")
                self._emit(self.on_error, {"step": self.step_count, "error": str(e)})
                result["status"] = "error"
                result["error"] = str(e)
                break
        
        if self.step_count >= self.max_steps:
            result["status"] = "max_steps_reached"
            result["message"] = f"Reached maximum of {self.max_steps} steps"
        
        # Update task in memory
        self.memory.update_task(
            self.current_task_id,
            status=result["status"],
            result=json.dumps(result),
        )
        
        self.is_running = False
        self.current_task_id = None
        return result

    def stop(self):
        """Stop the current task."""
        self.is_running = False
        self.safety.emergency_stop()

    def chat(self, message: str) -> str:
        """
        Simple chat without tool calling — for direct conversation.
        Returns a clear error string instead of crashing if Ollama is down.
        """
        self.memory.add_message("user", message)
        messages = self.memory.get_messages_for_context()

        try:
            response = self.llm.chat(messages)
        except Exception as e:
            logger.error(f"Chat failed (Ollama unreachable?): {e}")
            hint = ("I can't reach my language model. If this happened after switching "
                    "apps, Android likely killed the Ollama server in the background. "
                    "Run 'bash lyra.sh restart' and try again.")
            self.memory.add_message("assistant", hint)
            return hint

        if isinstance(response, dict):
            content = (response.get("message") or {}).get("content") or ""
        else:
            content = getattr(response.message, 'content', '') if hasattr(response, 'message') else str(response)
        if not content or not content.strip():
            content = "(I generated an empty response — try rephrasing.)"

        self.memory.add_message("assistant", content)
        return content

    def get_status(self) -> dict:
        """Get current agent status."""
        return {
            "is_running": self.is_running,
            "current_task_id": self.current_task_id,
            "step_count": self.step_count,
            "max_steps": self.max_steps,
            "action_count": self.safety.action_count,
            "emergency_stopped": self.safety.is_emergency_stopped(),
        }
