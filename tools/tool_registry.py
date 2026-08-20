"""
Tool registry — defines all tools the agent can use.
Each tool has a name, description, parameters schema, and handler function.
"""

import json
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class Tool:
    def __init__(self, name: str, description: str, parameters: dict, handler: Callable,
                 requires_confirmation: bool = False, category: str = "general"):
        self.name = name
        self.description = description
        self.parameters = parameters  # JSON Schema for parameters
        self.handler = handler
        self.requires_confirmation = requires_confirmation
        self.category = category

    def to_ollama_format(self) -> dict:
        """Convert to Ollama tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    def execute(self, **kwargs) -> dict:
        """Execute the tool handler."""
        try:
            result = self.handler(**kwargs)
            if isinstance(result, dict):
                return result
            return {"result": result}
        except Exception as e:
            logger.error(f"Tool '{self.name}' error: {e}")
            return {"error": str(e)}


class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def get(self, name: str) -> Optional[Tool]:
        return self.tools.get(name)

    def execute(self, name: str, arguments: dict) -> dict:
        tool = self.get(name)
        if not tool:
            return {"error": f"Unknown tool: {name}"}
        return tool.execute(**arguments)

    def get_ollama_tools(self) -> list:
        """Get all tools in Ollama format."""
        return [tool.to_ollama_format() for tool in self.tools.values()]

    def get_tool_definitions(self) -> list:
        """Get tool definitions for display."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "requires_confirmation": t.requires_confirmation,
                "parameters": t.parameters,
            }
            for t in self.tools.values()
        ]

    def list_by_category(self) -> dict:
        """Group tools by category."""
        categories = {}
        for tool in self.tools.values():
            if tool.category not in categories:
                categories[tool.category] = []
            categories[tool.category].append(tool.name)
        return categories
