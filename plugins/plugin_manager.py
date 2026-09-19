"""
Plugin system — load plugins from the plugins/ directory.
Each plugin can register tools, add hooks, and extend the agent.
"""

import os
import sys
import json
import importlib
import importlib.util
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class PluginManifest:
    """Plugin manifest loaded from plugin.json."""
    
    def __init__(self, name: str, version: str, description: str = "",
                 author: str = "", entry_point: str = "plugin.py",
                 dependencies: list = None, config: dict = None):
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.entry_point = entry_point
        self.dependencies = dependencies or []
        self.config = config or {}
    
    @classmethod
    def from_dict(cls, data: dict) -> "PluginManifest":
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "0.0.1"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            entry_point=data.get("entry_point", "plugin.py"),
            dependencies=data.get("dependencies", []),
            config=data.get("config", {}),
        )
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "entry_point": self.entry_point,
            "dependencies": self.dependencies,
            "config": self.config,
        }


class Plugin:
    """A loaded plugin instance."""
    
    def __init__(self, manifest: PluginManifest, module, path: str):
        self.manifest = manifest
        self.module = module
        self.path = path
        self.is_loaded = True
        self.tools_registered = 0
        self.hooks = {}


class PluginManager:
    """Discovers, loads, and manages plugins."""
    
    def __init__(self, plugins_dir: str = "plugins", tool_registry=None,
                 agent=None, config: dict = None):
        self.plugins_dir = os.path.abspath(plugins_dir)
        self.tool_registry = tool_registry
        self.agent = agent
        self.config = config or {}
        self.plugins: dict = {}  # name -> Plugin
        self._hooks = {
            "before_task": [],
            "after_task": [],
            "before_tool_call": [],
            "after_tool_call": [],
            "on_error": [],
            "on_start": [],
            "on_shutdown": [],
        }
        
        os.makedirs(self.plugins_dir, exist_ok=True)
    
    def discover_plugins(self) -> list:
        """Find all plugin directories with a plugin.json manifest."""
        plugins = []
        if not os.path.isdir(self.plugins_dir):
            return plugins
        
        for entry in os.listdir(self.plugins_dir):
            plugin_path = os.path.join(self.plugins_dir, entry)
            manifest_path = os.path.join(plugin_path, "plugin.json")
            
            if os.path.isfile(manifest_path):
                try:
                    with open(manifest_path, "r") as f:
                        data = json.load(f)
                    manifest = PluginManifest.from_dict(data)
                    manifest._path = plugin_path
                    plugins.append(manifest)
                except Exception as e:
                    logger.error(f"Failed to load plugin manifest at {plugin_path}: {e}")
        
        return plugins
    
    def load_plugin(self, manifest: PluginManifest) -> dict:
        """Load a single plugin."""
        plugin_path = manifest._path
        entry_file = os.path.join(plugin_path, manifest.entry_point)
        
        if not os.path.isfile(entry_file):
            return {"error": f"Entry point not found: {entry_file}"}
        
        # Add plugin directory to Python path for imports
        if plugin_path not in sys.path:
            sys.path.insert(0, plugin_path)
        
        # Load the module
        module_name = f"plugin_{manifest.name.replace('-', '_').replace(' ', '_')}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, entry_file)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error(f"Failed to load plugin '{manifest.name}': {e}")
            return {"error": str(e)}
        
        plugin = Plugin(manifest, module, plugin_path)
        
        # Initialize plugin if it has an init function
        plugin_api = PluginAPI(manifest, self.tool_registry, self.agent,
                                self._hooks, self.config.get("plugins", {}).get(manifest.name, {}))
        
        if hasattr(module, "setup"):
            try:
                module.setup(plugin_api)
                plugin.tools_registered = len(plugin_api._tools_added)
            except Exception as e:
                logger.error(f"Plugin '{manifest.name}' setup failed: {e}")
                return {"error": str(e)}
        
        self.plugins[manifest.name] = plugin
        logger.info(f"Plugin loaded: {manifest.name} v{manifest.version} "
                    f"({plugin.tools_registered} tools registered)")
        
        return {
            "status": "loaded",
            "name": manifest.name,
            "version": manifest.version,
            "tools_registered": plugin.tools_registered,
        }
    
    def load_all(self) -> dict:
        """Discover and load all plugins."""
        manifests = self.discover_plugins()
        results = {"loaded": 0, "failed": 0, "plugins": []}
        
        for manifest in manifests:
            result = self.load_plugin(manifest)
            if result.get("status") == "loaded":
                results["loaded"] += 1
            else:
                results["failed"] += 1
            results["plugins"].append(result)
        
        logger.info(f"Plugins: {results['loaded']} loaded, {results['failed']} failed")
        return results
    
    def unload_plugin(self, name: str) -> dict:
        """Unload a plugin."""
        if name not in self.plugins:
            return {"error": f"Plugin '{name}' not loaded"}
        
        plugin = self.plugins[name]
        
        # Call plugin teardown if available
        if hasattr(plugin.module, "teardown"):
            try:
                plugin.module.teardown()
            except Exception as e:
                logger.error(f"Plugin '{name}' teardown failed: {e}")
        
        # Unregister tools
        if self.tool_registry:
            to_remove = [t for t in self.tool_registry.tools if t.startswith(f"plugin_{name}_")]
            for t in to_remove:
                del self.tool_registry.tools[t]
        
        del self.plugins[name]
        logger.info(f"Plugin unloaded: {name}")
        return {"status": "unloaded", "name": name}
    
    def reload_plugin(self, name: str) -> dict:
        """Reload a plugin."""
        if name not in self.plugins:
            return {"error": f"Plugin '{name}' not loaded"}
        
        plugin = self.plugins[name]
        self.unload_plugin(name)
        return self.load_plugin(plugin.manifest)
    
    def get_hook(self, hook_name: str) -> list:
        """Get all handlers for a hook."""
        return self._hooks.get(hook_name, [])
    
    def run_hook(self, hook_name: str, *args, **kwargs):
        """Run all handlers for a hook."""
        results = []
        for handler in self._hooks.get(hook_name, []):
            try:
                result = handler(*args, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Hook '{hook_name}' handler error: {e}")
        return results
    
    def list_plugins(self) -> list:
        """List all loaded plugins."""
        return [
            {
                "name": p.manifest.name,
                "version": p.manifest.version,
                "description": p.manifest.description,
                "tools_registered": p.tools_registered,
                "is_loaded": p.is_loaded,
            }
            for p in self.plugins.values()
        ]
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a loaded plugin by name."""
        return self.plugins.get(name)


class PluginAPI:
    """API exposed to plugins for registering tools and hooks."""
    
    def __init__(self, manifest: PluginManifest, tool_registry, agent,
                 hooks: dict, plugin_config: dict):
        self.manifest = manifest
        self.tool_registry = tool_registry
        self.agent = agent
        self.hooks = hooks
        self.config = plugin_config
        self._tools_added = []
    
    def register_tool(self, name: str, description: str, parameters: dict,
                      handler: Callable, requires_confirmation: bool = False,
                      category: str = "plugin"):
        """Register a tool with the tool registry."""
        # Absolute import — plugin modules load via importlib without a
        # package context, so a relative import here breaks plugin loading.
        # (PROJECT_DIR is on sys.path via run.py.)
        from tools.tool_registry import Tool
        
        full_name = f"plugin_{self.manifest.name}_{name}"
        tool = Tool(
            name=full_name,
            description=description,
            parameters=parameters,
            handler=handler,
            requires_confirmation=requires_confirmation,
            category=category or self.manifest.name,
        )
        
        if self.tool_registry:
            self.tool_registry.register(tool)
            self._tools_added.append(full_name)
            return {"status": "registered", "name": full_name}
        return {"error": "Tool registry not available"}
    
    def add_hook(self, hook_name: str, handler: Callable):
        """Register a hook handler."""
        if hook_name in self.hooks:
            self.hooks[hook_name].append(handler)
            return {"status": "registered"}
        return {"error": f"Unknown hook: {hook_name}"}
    
    def get_config(self, key: str, default=None):
        """Get a plugin-specific config value."""
        return self.config.get(key, default)
    
    def log(self, message: str, level: str = "info"):
        """Log a message."""
        getattr(logger, level, logger.info)(f"[{self.manifest.name}] {message}")
