"""
Personal kit — calculator, notes, reminders, todos.

All data is stored locally in data/personal/ as JSON and markdown.
"""

import ast
import json
import os
import time
import operator

DATA_DIR = os.path.join(os.getcwd(), "data", "personal")
NOTES_DIR = os.path.join(DATA_DIR, "notes")
REMINDERS_FILE = os.path.join(DATA_DIR, "reminders.json")
TODOS_FILE = os.path.join(DATA_DIR, "todos.json")


def _ensure_dirs():
    os.makedirs(NOTES_DIR, exist_ok=True)


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_json(path, data):
    _ensure_dirs()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── Calculator (safe AST eval — no exec) ──

_ALLOWED_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos, ast.FloorDiv: operator.floordiv,
}


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("unsupported expression")


def calculate(expression: str = "", **kw):
    """Evaluate a math expression safely (numbers and + - * / % // ** only)."""
    if not expression:
        return {"error": "expression is required"}
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree)
        return {"status": "success", "expression": expression, "result": result}
    except (ValueError, SyntaxError) as e:
        return {"error": f"invalid math expression: {e}"}


# ── Notes ──

def note_add(title: str = "", content: str = "", **kw):
    """Save a note. Title becomes the filename; same title overwrites."""
    if not title:
        return {"error": "title is required"}
    _ensure_dirs()
    safe_name = "".join(c for c in title if c.isalnum() or c in " _-").strip().replace(" ", "_")[:80]
    path = os.path.join(NOTES_DIR, safe_name + ".md")
    with open(path, "w") as f:
        f.write(f"# {title}\n\n{content}\n")
    return {"status": "success", "note": title, "path": path}


def note_read(title: str = "", **kw):
    """Read a saved note by its title."""
    if not title:
        return {"error": "title is required"}
    safe_name = "".join(c for c in title if c.isalnum() or c in " _-").strip().replace(" ", "_")[:80]
    path = os.path.join(NOTES_DIR, safe_name + ".md")
    if not os.path.exists(path):
        return {"error": f"note '{title}' not found"}
    with open(path) as f:
        return {"status": "success", "note": title, "content": f.read()}


def note_list(**kw):
    """List all saved notes."""
    _ensure_dirs()
    notes = [f[:-3].replace("_", " ") for f in os.listdir(NOTES_DIR) if f.endswith(".md")]
    return {"status": "success", "notes": sorted(notes), "count": len(notes)}


# ── Reminders ──

def reminder_add(task: str = "", due: str = "", **kw):
    """Add a reminder with an optional due description (e.g. 'tomorrow morning', 'friday 3pm')."""
    if not task:
        return {"error": "task is required"}
    reminders = _load_json(REMINDERS_FILE)
    reminders.append({
        "task": task,
        "due": due or "",
        "created": time.strftime("%Y-%m-%d %H:%M"),
        "done": False,
    })
    _save_json(REMINDERS_FILE, reminders)
    return {"status": "success", "task": task, "due": due}


def reminder_list(include_done: bool = False, **kw):
    """List reminders, optionally including completed ones."""
    reminders = _load_json(REMINDERS_FILE)
    items = [r for r in reminders if include_done or not r.get("done")]
    return {"status": "success", "reminders": items, "count": len(items)}


def reminder_done(task: str = "", **kw):
    """Mark a reminder done by matching part of its task text."""
    if not task:
        return {"error": "task is required"}
    reminders = _load_json(REMINDERS_FILE)
    found = False
    for r in reminders:
        if task.lower() in r["task"].lower() and not r.get("done"):
            r["done"] = True
            r["done_at"] = time.strftime("%Y-%m-%d %H:%M")
            found = True
    if not found:
        return {"error": f"no open reminder matching '{task}'"}
    _save_json(REMINDERS_FILE, reminders)
    return {"status": "success", "completed": task}


# ── Todos ──

def todo_add(task: str = "", priority: str = "normal", **kw):
    """Add a todo. priority: low, normal, high."""
    if not task:
        return {"error": "task is required"}
    if priority not in ("low", "normal", "high"):
        priority = "normal"
    todos = _load_json(TODOS_FILE)
    todos.append({"task": task, "priority": priority, "done": False,
                  "created": time.strftime("%Y-%m-%d %H:%M")})
    _save_json(TODOS_FILE, todos)
    return {"status": "success", "task": task, "priority": priority}


def todo_list(**kw):
    """List open todos, sorted by priority (high first)."""
    todos = [t for t in _load_json(TODOS_FILE) if not t.get("done")]
    order = {"high": 0, "normal": 1, "low": 2}
    todos.sort(key=lambda t: order.get(t.get("priority", "normal"), 1))
    return {"status": "success", "todos": todos, "count": len(todos)}


def todo_done(task: str = "", **kw):
    """Mark a todo done by matching part of its task text."""
    if not task:
        return {"error": "task is required"}
    todos = _load_json(TODOS_FILE)
    found = False
    for t in todos:
        if task.lower() in t["task"].lower() and not t.get("done"):
            t["done"] = True
            found = True
    if not found:
        return {"error": f"no open todo matching '{task}'"}
    _save_json(TODOS_FILE, todos)
    return {"status": "success", "completed": task}


# ── Setup ──

def setup(api):
    api.log("personal_kit plugin loading")
    _ensure_dirs()

    api.register_tool(
        name="calculate",
        description="Evaluate a math expression (+ - * / % // **). More reliable than doing arithmetic in your head.",
        parameters={"type": "object", "properties": {
            "expression": {"type": "string", "description": "e.g. '(12 * 4.5) / 3'"},
        }, "required": ["expression"]},
        handler=calculate,
        category="personal",
    )
    api.register_tool(
        name="note_add",
        description="Save a markdown note. Same title overwrites the previous version.",
        parameters={"type": "object", "properties": {
            "title": {"type": "string"},
            "content": {"type": "string"},
        }, "required": ["title", "content"]},
        handler=note_add,
        category="personal",
    )
    api.register_tool(
        name="note_read",
        description="Read a saved note by title.",
        parameters={"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]},
        handler=note_read,
        category="personal",
    )
    api.register_tool(
        name="note_list",
        description="List all saved note titles.",
        parameters={"type": "object", "properties": {}},
        handler=note_list,
        category="personal",
    )
    api.register_tool(
        name="reminder_add",
        description="Add a reminder for the user. 'due' is free text like 'tomorrow 9am'.",
        parameters={"type": "object", "properties": {
            "task": {"type": "string"},
            "due": {"type": "string"},
        }, "required": ["task"]},
        handler=reminder_add,
        category="personal",
    )
    api.register_tool(
        name="reminder_list",
        description="List open reminders.",
        parameters={"type": "object", "properties": {"include_done": {"type": "boolean", "default": False}}},
        handler=reminder_list,
        category="personal",
    )
    api.register_tool(
        name="reminder_done",
        description="Mark a reminder as done. Matches any open reminder containing the given text.",
        parameters={"type": "object", "properties": {"task": {"type": "string"}}, "required": ["task"]},
        handler=reminder_done,
        category="personal",
    )
    api.register_tool(
        name="todo_add",
        description="Add a todo item with priority (low, normal, high).",
        parameters={"type": "object", "properties": {
            "task": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "normal", "high"], "default": "normal"},
        }, "required": ["task"]},
        handler=todo_add,
        category="personal",
    )
    api.register_tool(
        name="todo_list",
        description="List open todos sorted by priority.",
        parameters={"type": "object", "properties": {}},
        handler=todo_list,
        category="personal",
    )
    api.register_tool(
        name="todo_done",
        description="Mark a todo as done. Matches any open todo containing the given text.",
        parameters={"type": "object", "properties": {"task": {"type": "string"}}, "required": ["task"]},
        handler=todo_done,
        category="personal",
    )

    api.log(f"personal_kit registered {len(api._tools_added)} tools")


def teardown():
    pass
