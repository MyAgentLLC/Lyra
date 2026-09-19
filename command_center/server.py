"""
Command center server — FastAPI web server for the agent dashboard.
Includes webhook endpoints and plugin management.
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TaskRequest(BaseModel):
    goal: str
    auto_confirm: bool = True


class ChatRequest(BaseModel):
    message: str


class ConfirmationResponse(BaseModel):
    approved: bool
    step: int


class WebhookRegister(BaseModel):
    name: str
    url: str = ""
    secret: str = ""
    event_types: list = ["incoming"]


class WebhookOutgoing(BaseModel):
    name: str
    url: str
    secret: str = ""
    event_types: list = []


def create_app(agent, tools_registry, memory, config: dict,
               webhook_manager=None, plugin_manager=None) -> FastAPI:
    """Create and configure the FastAPI app."""
    
    app = FastAPI(title="Autonomous Agent Command Center")
    
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    state = {
        "logs": [],
        "screenshots": [],
        "pending_confirmation": None,
        "confirmation_event": asyncio.Event(),
        "confirmation_result": None,
    }
    
    class ConnectionManager:
        def __init__(self):
            self.connections: list = []
        
        async def connect(self, ws: WebSocket):
            await ws.accept()
            self.connections.append(ws)
        
        def disconnect(self, ws: WebSocket):
            if ws in self.connections:
                self.connections.remove(ws)
        
        async def broadcast(self, message: dict):
            for ws in self.connections:
                try:
                    await ws.send_json(message)
                except:
                    pass
    
    manager = ConnectionManager()
    
    async def emit_log(message_type: str, data: dict):
        entry = {"type": message_type, "data": data, "timestamp": asyncio.get_event_loop().time()}
        state["logs"].append(entry)
        if len(state["logs"]) > 500:
            state["logs"] = state["logs"][-500:]
        await manager.broadcast(entry)
    
    # Confirmation handler
    async def on_confirmation_request(data: dict) -> bool:
        state["pending_confirmation"] = data
        state["confirmation_event"].clear()
        await emit_log("confirmation_request", data)
        try:
            await asyncio.wait_for(state["confirmation_event"].wait(), timeout=120)
        except asyncio.TimeoutError:
            pass
        state["pending_confirmation"] = None
        return state["confirmation_result"] or False
    
    agent.on_thinking = lambda data: asyncio.create_task(emit_log("thinking", data))
    agent.on_tool_call = lambda data: asyncio.create_task(emit_log("tool_call", data))
    agent.on_tool_result = lambda data: asyncio.create_task(emit_log("tool_result", data))
    agent.on_response = lambda data: asyncio.create_task(emit_log("response", data))
    agent.on_error = lambda data: asyncio.create_task(emit_log("error", data))
    agent.on_confirmation_request = on_confirmation_request
    
    # === Core Routes ===
    
    @app.get("/", response_class=HTMLResponse)
    async def index():
        template = Path(__file__).parent / "templates" / "index.html"
        return HTMLResponse(template.read_text())
    
    @app.get("/api/status")
    async def get_status():
        return agent.get_status()
    
    @app.get("/api/tools")
    async def get_tools():
        return tools_registry.get_tool_definitions()
    
    @app.get("/api/tools/categories")
    async def get_tool_categories():
        return tools_registry.list_by_category()
    
    @app.post("/api/task")
    async def run_task(request: TaskRequest):
        if agent.is_running:
            return JSONResponse({"error": "Agent is already running a task"}, status_code=409)
        asyncio.create_task(agent.run_task(request.goal, request.auto_confirm))
        return {"status": "started", "goal": request.goal}
    
    @app.post("/api/chat")
    async def chat(request: ChatRequest):
        response = agent.chat(request.message)
        await emit_log("chat", {"user": request.message, "assistant": response})
        return {"response": response}
    
    @app.post("/api/confirm")
    async def confirm(response: ConfirmationResponse):
        state["confirmation_result"] = response.approved
        state["confirmation_event"].set()
        return {"status": "confirmed" if response.approved else "cancelled"}
    
    @app.post("/api/stop")
    async def stop_agent():
        agent.stop()
        await emit_log("emergency_stop", {"message": "Emergency stop triggered by user"})
        return {"status": "stopped"}
    
    @app.get("/api/logs")
    async def get_logs(limit: int = 100):
        return state["logs"][-limit:]
    
    @app.get("/api/tasks")
    async def get_tasks():
        return memory.get_recent_tasks(20)
    
    @app.get("/api/task/{task_id}")
    async def get_task(task_id: int):
        task = memory.get_task(task_id)
        if task:
            return task
        return JSONResponse({"error": "Task not found"}, status_code=404)
    
    @app.get("/api/facts")
    async def get_facts():
        return memory.get_all_facts()
    
    @app.post("/api/fact")
    async def store_fact(key: str, value: str, category: str = "general"):
        memory.store_fact(key, value, category)
        return {"status": "saved"}
    
    @app.delete("/api/fact/{key}")
    async def delete_fact(key: str):
        memory.delete_fact(key)
        return {"status": "deleted"}
    
    @app.delete("/api/conversation")
    async def clear_conversation():
        memory.clear_conversation()
        state["logs"] = []
        return {"status": "cleared"}
    
    @app.get("/api/action-history")
    async def get_action_history():
        return agent.safety.get_action_history(100)
    
    @app.get("/api/models")
    async def list_models():
        return {"models": agent.llm.list_available_models()}
    
    @app.get("/api/phone/status")
    async def phone_status():
        from device_control.phone import PhoneControl
        phone_config = config.get("devices", {}).get("phone", {})
        phone = PhoneControl(device_serial=phone_config.get("device_serial", ""))
        return phone.check_connection()
    
    @app.get("/api/screenshot/{filename}")
    async def get_screenshot(filename: str):
        safe_name = os.path.basename(filename)
        import tempfile
        candidates = [
            os.path.join(tempfile.gettempdir(), safe_name),
            os.path.join(os.path.expanduser("~"), ".agent_screenshots", safe_name),
            safe_name,
        ]
        for path in candidates:
            if os.path.exists(path):
                return FileResponse(path)
        return JSONResponse({"error": "Screenshot not found"}, status_code=404)
    
    # === Webhook Routes ===
    
    @app.post("/webhook/{name}")
    async def incoming_webhook(name: str, request: Request):
        """Receive an incoming webhook from an external service."""
        if not webhook_manager:
            return JSONResponse({"error": "Webhooks not configured"}, status_code=503)
        
        body = await request.body()
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {"raw": body.decode(errors="ignore")}
        
        headers = dict(request.headers)
        result = await webhook_manager.handle_incoming(name, payload, headers)
        return result
    
    @app.get("/webhook/{name}/info")
    async def webhook_info(name: str):
        """Get info about a registered webhook."""
        if not webhook_manager:
            return JSONResponse({"error": "Webhooks not configured"}, status_code=503)
        webhooks = webhook_manager.list_webhooks()
        for w in webhooks.get("incoming", []) + webhooks.get("outgoing", []):
            if w["name"] == name:
                return w
        return JSONResponse({"error": "Webhook not found"}, status_code=404)
    
    @app.post("/api/webhooks/register")
    async def register_webhook(req: WebhookRegister):
        """Register a new webhook (incoming or outgoing)."""
        if not webhook_manager:
            return JSONResponse({"error": "Webhooks not configured"}, status_code=503)
        if req.url:
            return webhook_manager.register_outgoing(req.name, req.url, req.event_types, req.secret)
        else:
            return webhook_manager.register_incoming(req.name, req.secret)
    
    @app.delete("/api/webhooks/{name}")
    async def delete_webhook(name: str):
        if not webhook_manager:
            return JSONResponse({"error": "Webhooks not configured"}, status_code=503)
        return webhook_manager.delete_webhook(name)
    
    @app.patch("/api/webhooks/{name}")
    async def toggle_webhook(name: str, active: bool = True):
        if not webhook_manager:
            return JSONResponse({"error": "Webhooks not configured"}, status_code=503)
        return webhook_manager.toggle_webhook(name, active)
    
    @app.get("/api/webhooks")
    async def list_webhooks():
        if not webhook_manager:
            return {"incoming": [], "outgoing": []}
        return webhook_manager.list_webhooks()
    
    @app.get("/api/webhooks/incoming/log")
    async def incoming_webhook_log(limit: int = 50):
        if not webhook_manager:
            return []
        return webhook_manager.get_incoming_log(limit)
    
    @app.get("/api/webhooks/outgoing/log")
    async def outgoing_webhook_log(limit: int = 50):
        if not webhook_manager:
            return []
        return webhook_manager.get_outgoing_log(limit)
    
    @app.post("/api/webhooks/emit")
    async def emit_webhook_event(event_type: str, data: dict = None):
        """Manually emit an event to outgoing webhooks."""
        if not webhook_manager:
            return JSONResponse({"error": "Webhooks not configured"}, status_code=503)
        return await webhook_manager.emit_event(event_type, data or {})
    
    # === Plugin Routes ===
    
    @app.get("/api/plugins")
    async def list_plugins():
        if not plugin_manager:
            return {"plugins": [], "error": "Plugin system not initialized"}
        return {"plugins": plugin_manager.list_plugins()}
    
    @app.post("/api/plugins/reload")
    async def reload_all_plugins():
        if not plugin_manager:
            return JSONResponse({"error": "Plugin system not initialized"}, status_code=503)
        return plugin_manager.load_all()
    
    @app.post("/api/plugins/{name}/reload")
    async def reload_plugin(name: str):
        if not plugin_manager:
            return JSONResponse({"error": "Plugin system not initialized"}, status_code=503)
        return plugin_manager.reload_plugin(name)
    
    @app.delete("/api/plugins/{name}")
    async def unload_plugin(name: str):
        if not plugin_manager:
            return JSONResponse({"error": "Plugin system not initialized"}, status_code=503)
        return plugin_manager.unload_plugin(name)
    
    # === WebSocket ===
    
    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await manager.connect(ws)
        try:
            while True:
                data = await ws.receive_text()
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_json({"type": "pong"})
        except WebSocketDisconnect:
            manager.disconnect(ws)
    
    return app
