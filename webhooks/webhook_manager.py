"""
Webhook manager — handles incoming and outgoing webhooks.
Incoming: external services trigger agent tasks.
Outgoing: agent notifies external services of events.
"""

import hashlib
import hmac
import json
import time
import logging
import asyncio
import os
from typing import Callable, Optional
import sqlite3

logger = logging.getLogger(__name__)


class WebhookManager:
    """Manages webhook registrations, incoming handlers, and outgoing dispatch."""
    
    def __init__(self, db_path: str = "data/webhooks.db", agent=None):
        self.db_path = db_path
        self.agent = agent
        self._outgoing_handlers = {}  # event_type -> list of webhook configs
        os.makedirs(os.path.dirname(db_path), exist_ok=True) if os.path.dirname(db_path) else None
        self._init_db()
    
    def _init_db(self):
        """Initialize webhook storage."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                url TEXT NOT NULL,
                secret TEXT,
                event_types TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at REAL NOT NULL
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS incoming_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                webhook_name TEXT NOT NULL,
                payload TEXT,
                event_type TEXT,
                status TEXT,
                timestamp REAL NOT NULL
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS outgoing_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                webhook_name TEXT NOT NULL,
                url TEXT NOT NULL,
                event_type TEXT,
                payload TEXT,
                response_code INTEGER,
                response_body TEXT,
                timestamp REAL NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _connect(self):
        return sqlite3.connect(self.db_path)
    
    # === Incoming Webhooks ===
    
    def register_incoming(self, name: str, secret: str = None) -> dict:
        """Register an incoming webhook endpoint.
        
        This creates a URL like /webhook/{name} that external services can POST to.
        The secret is used for HMAC signature verification.
        """
        conn = self._connect()
        c = conn.cursor()
        
        try:
            c.execute(
                "INSERT INTO webhooks (name, url, secret, event_types, created_at) "
                "VALUES (?, '', ?, 'incoming', ?)",
                (name, secret or "", time.time())
            )
            conn.commit()
            logger.info(f"Registered incoming webhook: {name}")
            return {"status": "success", "name": name, "endpoint": f"/webhook/{name}"}
        except sqlite3.IntegrityError:
            return {"error": f"Webhook '{name}' already exists"}
        finally:
            conn.close()
    
    def verify_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify HMAC-SHA256 signature of incoming webhook."""
        if not secret:
            return True  # No secret = no verification
        expected = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature or "")
    
    async def handle_incoming(self, name: str, payload: dict, headers: dict) -> dict:
        """Handle an incoming webhook request."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT secret FROM webhooks WHERE name = ? AND is_active = 1", (name,))
        row = c.fetchone()
        conn.close()
        
        if not row:
            return {"error": f"Webhook '{name}' not found or inactive"}
        
        secret = row[0]
        
        # Verify signature if secret is set
        if secret:
            signature = headers.get("x-webhook-signature", headers.get("x-hub-signature-256", ""))
            raw_payload = json.dumps(payload, sort_keys=True).encode()
            if not self.verify_signature(raw_payload, signature, secret):
                return {"error": "Invalid signature"}
        
        # Log the incoming webhook
        event_type = payload.get("event", payload.get("type", "unknown"))
        self._log_incoming(name, payload, event_type, "received")
        
        # Trigger agent task if configured
        task_prompt = payload.get("task") or payload.get("prompt") or payload.get("message")
        if task_prompt and self.agent and not self.agent.is_running:
            logger.info(f"Webhook '{name}' triggering agent task: {task_prompt[:100]}")
            asyncio.create_task(self.agent.run_task(task_prompt, auto_confirm=True))
            self._log_incoming(name, payload, event_type, "task_triggered")
            return {"status": "received", "task_triggered": True, "event_type": event_type}
        
        # Store the event for later processing
        self._log_incoming(name, payload, event_type, "stored")
        return {"status": "received", "task_triggered": False, "event_type": event_type}
    
    def _log_incoming(self, name: str, payload: dict, event_type: str, status: str):
        """Log an incoming webhook."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO incoming_log (webhook_name, payload, event_type, status, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, json.dumps(payload)[:5000], event_type, status, time.time())
        )
        conn.commit()
        conn.close()
    
    def get_incoming_log(self, limit: int = 50) -> list:
        """Get recent incoming webhook logs."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "SELECT id, webhook_name, event_type, status, timestamp FROM incoming_log "
            "ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = c.fetchall()
        conn.close()
        return [
            {"id": r[0], "webhook_name": r[1], "event_type": r[2], "status": r[3], "timestamp": r[4]}
            for r in rows
        ]
    
    # === Outgoing Webhooks ===
    
    def register_outgoing(self, name: str, url: str, event_types: list,
                          secret: str = None) -> dict:
        """Register an outgoing webhook.
        
        When the agent emits one of the event_types, it will POST to the URL.
        """
        conn = self._connect()
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO webhooks (name, url, secret, event_types, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, url, secret or "", json.dumps(event_types), time.time())
            )
            conn.commit()
            logger.info(f"Registered outgoing webhook: {name} -> {url} for events {event_types}")
            return {"status": "success", "name": name, "url": url}
        except sqlite3.IntegrityError:
            # Update existing
            c.execute(
                "UPDATE webhooks SET url = ?, secret = ?, event_types = ? WHERE name = ?",
                (url, secret or "", json.dumps(event_types), name)
            )
            conn.commit()
            return {"status": "updated", "name": name, "url": url}
        finally:
            conn.close()
    
    async def emit_event(self, event_type: str, data: dict) -> dict:
        """Emit an event to all registered outgoing webhooks that listen for this event type."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT name, url, secret FROM webhooks WHERE is_active = 1")
        rows = c.fetchall()
        conn.close()
        
        results = []
        for name, url, secret in rows:
            try:
                event_types = json.loads(
                    self._connect().execute(
                        "SELECT event_types FROM webhooks WHERE name = ?", (name,)
                    ).fetchone()[0]
                )
            except:
                continue
            
            if event_type not in event_types and "*" not in event_types:
                continue
            
            # Send the webhook
            import aiohttp
            payload = {
                "event": event_type,
                "data": data,
                "timestamp": time.time(),
                "source": "autonomous-agent",
            }
            
            headers = {"Content-Type": "application/json"}
            if secret:
                payload_str = json.dumps(payload, sort_keys=True)
                sig = hmac.new(secret.encode(), payload_str.encode(), hashlib.sha256).hexdigest()
                headers["X-Webhook-Signature"] = sig
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        body = await resp.text()
                        self._log_outgoing(name, url, event_type, payload, resp.status, body[:1000])
                        results.append({
                            "webhook": name,
                            "status_code": resp.status,
                            "success": 200 <= resp.status < 300,
                        })
            except Exception as e:
                self._log_outgoing(name, url, event_type, payload, 0, str(e))
                results.append({"webhook": name, "error": str(e), "success": False})
        
        return {"dispatched": len(results), "results": results}
    
    def _log_outgoing(self, name: str, url: str, event_type: str, payload: dict,
                      response_code: int, response_body: str):
        """Log an outgoing webhook."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO outgoing_log (webhook_name, url, event_type, payload, "
            "response_code, response_body, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, url, event_type, json.dumps(payload)[:5000],
             response_code, response_body[:1000], time.time())
        )
        conn.commit()
        conn.close()
    
    def get_outgoing_log(self, limit: int = 50) -> list:
        """Get recent outgoing webhook logs."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "SELECT id, webhook_name, url, event_type, response_code, timestamp "
            "FROM outgoing_log ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = c.fetchall()
        conn.close()
        return [
            {"id": r[0], "webhook_name": r[1], "url": r[2], "event_type": r[3],
             "response_code": r[4], "timestamp": r[5]}
            for r in rows
        ]
    
    # === Management ===
    
    def list_webhooks(self) -> dict:
        """List all registered webhooks."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT name, url, event_types, is_active, created_at FROM webhooks")
        rows = c.fetchall()
        conn.close()
        
        incoming = []
        outgoing = []
        for r in rows:
            entry = {
                "name": r[0], "url": r[1],
                "event_types": json.loads(r[2]) if r[2] else [],
                "is_active": bool(r[3]),
                "created_at": r[4],
            }
            if entry["event_types"] == ["incoming"] or not entry["url"]:
                entry["endpoint"] = f"/webhook/{r[0]}"
                incoming.append(entry)
            else:
                outgoing.append(entry)
        
        return {"incoming": incoming, "outgoing": outgoing}
    
    def delete_webhook(self, name: str) -> dict:
        """Delete a webhook."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("DELETE FROM webhooks WHERE name = ?", (name,))
        deleted = c.rowcount
        conn.commit()
        conn.close()
        return {"status": "deleted" if deleted else "not_found", "name": name}
    
    def toggle_webhook(self, name: str, active: bool) -> dict:
        """Activate or deactivate a webhook."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("UPDATE webhooks SET is_active = ? WHERE name = ?", (1 if active else 0, name))
        updated = c.rowcount
        conn.commit()
        conn.close()
        return {"status": "updated" if updated else "not_found", "name": name, "active": active}
