"""
Memory module — persistent conversation and task memory.
Uses SQLite for lightweight, local storage.
"""

import sqlite3
import json
import os
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AgentMemory:
    def __init__(self, db_path: str = "data/memory.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True) if os.path.dirname(db_path) else None
        self._init_db()

    def _init_db(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Conversation history
        c.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL,
                metadata TEXT
            )
        """)
        
        # Tasks
        c.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                plan TEXT,
                steps TEXT,
                current_step INTEGER DEFAULT 0,
                result TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        
        # Facts/learnings
        c.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    # === Conversations ===
    
    def add_message(self, role: str, content: str, metadata: dict = None):
        """Add a message to conversation history."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO conversations (role, content, timestamp, metadata) VALUES (?, ?, ?, ?)",
            (role, content, time.time(), json.dumps(metadata) if metadata else None)
        )
        conn.commit()
        conn.close()

    def get_recent_messages(self, limit: int = 20) -> list:
        """Get recent conversation messages."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "SELECT role, content, timestamp, metadata FROM conversations "
            "ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = c.fetchall()
        conn.close()
        rows.reverse()
        return [
            {"role": r[0], "content": r[1], "timestamp": r[2],
             "metadata": json.loads(r[3]) if r[3] else None}
            for r in rows
        ]

    def get_messages_for_context(self, max_turns: int = 20) -> list:
        """Get messages formatted for LLM context."""
        messages = self.get_recent_messages(limit=max_turns)
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    def clear_conversation(self):
        """Clear conversation history."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("DELETE FROM conversations")
        conn.commit()
        conn.close()

    # === Tasks ===
    
    def create_task(self, goal: str, plan: str = None) -> int:
        """Create a new task."""
        conn = self._connect()
        c = conn.cursor()
        now = time.time()
        c.execute(
            "INSERT INTO tasks (goal, plan, status, created_at, updated_at) "
            "VALUES (?, ?, 'pending', ?, ?)",
            (goal, plan, now, now)
        )
        task_id = c.lastrowid
        conn.commit()
        conn.close()
        return task_id

    def update_task(self, task_id: int, status: str = None, plan: str = None,
                    steps: str = None, current_step: int = None, result: str = None):
        """Update a task."""
        conn = self._connect()
        c = conn.cursor()
        updates = []
        values = []
        if status:
            updates.append("status = ?")
            values.append(status)
        if plan is not None:
            updates.append("plan = ?")
            values.append(plan)
        if steps is not None:
            updates.append("steps = ?")
            values.append(steps)
        if current_step is not None:
            updates.append("current_step = ?")
            values.append(current_step)
        if result is not None:
            updates.append("result = ?")
            values.append(result)
        updates.append("updated_at = ?")
        values.append(time.time())
        values.append(task_id)
        
        c.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
        conn.close()

    def get_task(self, task_id: int) -> dict:
        """Get a task by ID."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": row[0], "goal": row[1], "status": row[2], "plan": row[3],
            "steps": row[4], "current_step": row[5], "result": row[6],
            "created_at": row[7], "updated_at": row[8]
        }

    def get_recent_tasks(self, limit: int = 10) -> list:
        """Get recent tasks."""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "SELECT id, goal, status, current_step, result, created_at "
            "FROM tasks ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = c.fetchall()
        conn.close()
        return [
            {"id": r[0], "goal": r[1], "status": r[2], "current_step": r[3],
             "result": r[4], "created_at": r[5]}
            for r in rows
        ]

    # === Facts ===
    
    def store_fact(self, key: str, value: str, category: str = "general"):
        """Store or update a fact."""
        conn = self._connect()
        c = conn.cursor()
        now = time.time()
        c.execute(
            "INSERT INTO facts (key, value, category, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = ?, category = ?, updated_at = ?",
            (key, value, category, now, now, value, category, now)
        )
        conn.commit()
        conn.close()

    def get_fact(self, key: str) -> Optional[str]:
        """Get a fact by key."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT value FROM facts WHERE key = ?", (key,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    def get_all_facts(self) -> list:
        """Get all facts."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT key, value, category FROM facts ORDER BY category")
        rows = c.fetchall()
        conn.close()
        return [{"key": r[0], "value": r[1], "category": r[2]} for r in rows]

    def delete_fact(self, key: str):
        """Delete a fact."""
        conn = self._connect()
        c = conn.cursor()
        c.execute("DELETE FROM facts WHERE key = ?", (key,))
        conn.commit()
        conn.close()
