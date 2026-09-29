"""
LLM interface for Ollama local models.
Handles chat completions, streaming, and tool/function calling.
"""

import ollama
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LLMInterface:
    def __init__(self, model_name: str, temperature: float = 0.7, max_tokens: int = 4096,
                 system_prompt: str = ""):
        self.model = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt
        self.client = ollama.Client(host="http://localhost:11434")

    def check_connection(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            models = self.client.list()
            model_names = [m.model for m in models.models] if hasattr(models, 'models') else []
            # Also check the models dict format
            if not model_names and isinstance(models, dict):
                model_names = [m.get('name', m.get('model', '')) for m in models.get('models', [])]
            
            if self.model in model_names or f"{self.model}:latest" in model_names:
                return True
            logger.warning(f"Model '{self.model}' not found. Available: {model_names}")
            return False
        except Exception as e:
            logger.error(f"Cannot connect to Ollama: {e}")
            return False

    def chat(self, messages: list, tools: Optional[list] = None, stream: bool = False):
        """
        Send a chat request to the local model.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions for function calling
            stream: Whether to stream the response
            
        Returns:
            Ollama response object
        """
        # Prepend system prompt if not already present
        if self.system_prompt and (not messages or messages[0].get("role") != "system"):
            messages = [{"role": "system", "content": self.system_prompt}] + messages

        kwargs = {
            "model": self.model,
            "messages": messages,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
            "stream": stream,
        }
        
        if tools:
            kwargs["tools"] = tools

        try:
            response = self.client.chat(**kwargs)
            return response
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            raise

    def chat_with_tools(self, messages: list, tools: list) -> dict:
        """
        Chat with tool calling support. Returns response with potential tool calls.
        
        Returns dict with:
            - 'content': str (assistant's text response)
            - 'tool_calls': list of {name, arguments} dicts
            - 'raw': raw response
        """
        response = self.chat(messages, tools=tools)
        
        message = response.get("message", {}) if isinstance(response, dict) else response.message

        # NOTE: qwen2.5 returns "tool_calls": null when it answers without calling
        # any tool, and "arguments" can be null or a JSON string. Handle all of it.
        if isinstance(message, dict):
            content = message.get("content") or ""
            tool_calls_raw = message.get("tool_calls") or []
        else:
            content = getattr(message, "content", None) or ""
            tool_calls_raw = getattr(message, "tool_calls", None) or []

        tool_calls = []
        for tc in tool_calls_raw:
            if isinstance(tc, dict):
                func = tc.get("function", {})
                args = func.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args) if args.strip() else {}
                    except json.JSONDecodeError:
                        args = {"_raw": args}
                tool_calls.append({
                    "name": func.get("name", ""),
                    "arguments": args or {},
                })
            else:
                func = getattr(tc, 'function', None)
                if func:
                    args = getattr(func, "arguments", None)
                    if isinstance(args, str):
                        try:
                            args = json.loads(args) if args.strip() else {}
                        except json.JSONDecodeError:
                            args = {"_raw": args}
                    tool_calls.append({
                        "name": getattr(func, "name", ""),
                        "arguments": args if isinstance(args, dict) else {},
                    })
        
        return {
            "content": content,
            "tool_calls": tool_calls,
            "raw": response,
        }

    def stream_chat(self, messages: list, tools: Optional[list] = None):
        """Generator that yields streaming response chunks."""
        if self.system_prompt and (not messages or messages[0].get("role") != "system"):
            messages = [{"role": "system", "content": self.system_prompt}] + messages

        kwargs = {
            "model": self.model,
            "messages": messages,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            for chunk in self.client.chat(**kwargs):
                if isinstance(chunk, dict):
                    msg = chunk.get("message", {})
                    content = msg.get("content", "")
                else:
                    content = getattr(chunk.message, 'content', '') if hasattr(chunk, 'message') else ""
                if content:
                    yield content
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"[Error: {e}]"

    def list_available_models(self) -> list:
        """List all models available in Ollama."""
        try:
            response = self.client.list()
            if isinstance(response, dict):
                return [m.get('name', m.get('model', 'unknown')) for m in response.get('models', [])]
            else:
                return [m.model for m in response.models] if hasattr(response, 'models') else []
        except Exception as e:
            logger.error(f"Cannot list models: {e}")
            return []

    def pull_model(self, model_name: str):
        """Pull a new model from Ollama registry."""
        try:
            stream = self.client.pull(model_name, stream=True)
            for chunk in stream:
                if isinstance(chunk, dict):
                    status = chunk.get("status", "")
                    if status:
                        yield status
                else:
                    yield str(chunk)
        except Exception as e:
            yield f"Error pulling model: {e}"
