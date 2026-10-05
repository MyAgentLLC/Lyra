"""
Token authentication for the Lyra command center.

Everything served by the dashboard (pages, API, websocket) requires a valid
token, except:
  - /login            (the login page itself)
  - /static/*         (dashboard assets)
  - /webhook/*        (incoming webhooks use their own per-webhook secrets)

Three ways to authenticate:
  1. Session cookie set by POST /login  (used by the browser dashboard)
  2. Authorization: Bearer <token> header (scripts / API clients)
  3. ?token=<token> query parameter      (quick scripts, websocket)

Token resolution order:
  1. LYRA_API_TOKEN environment variable
  2. server.api_token in the YAML config
  3. Auto-generated token persisted at data/.api_token (mode 600, gitignored)
"""

import base64
import hashlib
import hmac
import logging
import os
import secrets
import time
from pathlib import Path
from urllib.parse import parse_qsl, quote

logger = logging.getLogger(__name__)

COOKIE_NAME = "lyra_session"
SESSION_TTL_SECONDS = 30 * 24 * 3600  # 30 days
TOKEN_FILE_NAME = ".api_token"


def resolve_api_token(config: dict, project_dir: str = None) -> str:
    """Return the dashboard API token, generating + persisting one if needed."""
    env_token = os.environ.get("LYRA_API_TOKEN", "").strip()
    if env_token:
        logger.info("Command center auth: using token from LYRA_API_TOKEN")
        return env_token

    server_cfg = (config or {}).get("server", {}) or {}
    cfg_token = str(server_cfg.get("api_token", "") or "").strip()
    if not cfg_token:
        auth_cfg = (config or {}).get("auth", {}) or {}
        cfg_token = str(auth_cfg.get("token", "") or "").strip()
    if cfg_token:
        logger.info("Command center auth: using token from config file")
        return cfg_token

    base = Path(project_dir) if project_dir else Path.cwd()
    token_file = base / "data" / TOKEN_FILE_NAME
    if token_file.exists():
        saved = token_file.read_text().strip()
        if saved:
            logger.info("Command center auth: using persisted token at %s", token_file)
            return saved

    token = secrets.token_urlsafe(32)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(token + "\n")
    try:
        os.chmod(token_file, 0o600)
    except OSError:
        pass
    logger.warning(
        "Command center auth: no token configured — generated a new one and "
        "saved it to %s (mode 600). Your dashboard login uses this token. "
        "To set your own, use the LYRA_API_TOKEN env var or server.api_token "
        "in the config file.",
        token_file,
    )
    return token


def verify_token(candidate: str, token: str) -> bool:
    """Constant-time token comparison. Never True on empty values."""
    if not candidate or not token:
        return False
    return hmac.compare_digest(candidate.encode(), token.encode())


def make_session_cookie(token: str) -> str:
    """Create a signed session cookie value: <ts_hex>.<hmac_hex>."""
    ts_hex = format(int(time.time()), "x")
    sig = hmac.new(token.encode(), ts_hex.encode(), hashlib.sha256).hexdigest()
    return f"{ts_hex}.{sig}"


def verify_session_cookie(value: str, token: str) -> bool:
    """Validate a session cookie's signature and expiry."""
    if not value or not token or "." not in value:
        return False
    ts_hex, _, sig = value.partition(".")
    try:
        ts = int(ts_hex, 16)
    except ValueError:
        return False
    now = int(time.time())
    if ts > now + 300:  # reject timestamps from the future (clock skew margin)
        return False
    if now - ts > SESSION_TTL_SECONDS:
        return False
    expected = hmac.new(token.encode(), ts_hex.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


def _get_header(scope: dict, name: str) -> str:
    for key, val in scope.get("headers", []):
        if key.decode("latin-1").lower() == name:
            return val.decode("latin-1")
    return ""


def _get_query_param(scope: dict, name: str) -> str:
    qs = scope.get("query_string", b"").decode("latin-1")
    for key, val in parse_qsl(qs, keep_blank_values=True):
        if key == name:
            return val
    return ""


def _get_cookie(scope: dict, name: str) -> str:
    cookie_header = _get_header(scope, "cookie")
    for part in cookie_header.split(";"):
        key, _, val = part.partition("=")
        if key.strip() == name:
            return val.strip().strip('"')
    return ""


def is_authenticated(scope: dict, token: str) -> bool:
    """Check Bearer header, ?token= param, or session cookie."""
    auth_header = _get_header(scope, "authorization")
    if auth_header.lower().startswith("bearer "):
        if verify_token(auth_header[7:].strip(), token):
            return True
    if verify_token(_get_query_param(scope, "token"), token):
        return True
    if verify_session_cookie(_get_cookie(scope, COOKIE_NAME), token):
        return True
    return False


def safe_next(next_url: str) -> str:
    """Only allow relative redirect targets on this host."""
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return "/"


def login_page_html(next_url: str = "/", error: bool = False) -> str:
    """Standalone login page (inline CSS, no external assets needed)."""
    safe = safe_next(next_url)
    err_html = (
        '<p class="err">Wrong token. Try again.</p>' if error else ""
    )
    # quote() the next target for the hidden field
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lyra — Sign in</title>
<style>
  body {{ background:#0d1117; color:#e6edf3; font-family:system-ui,sans-serif;
         display:flex; align-items:center; justify-content:center;
         min-height:100vh; margin:0; }}
  .card {{ background:#161b22; border:1px solid #30363d; border-radius:12px;
           padding:32px; width:min(92vw,380px); box-shadow:0 8px 32px #0008; }}
  h1 {{ margin:0 0 4px; font-size:22px; }}
  p.sub {{ color:#8b949e; font-size:13px; margin:0 0 20px; }}
  input {{ width:100%; box-sizing:border-box; padding:12px; border-radius:8px;
           border:1px solid #30363d; background:#0d1117; color:#e6edf3;
           font-size:16px; margin-bottom:12px; }}
  button {{ width:100%; padding:12px; border:0; border-radius:8px;
            background:#d4a017; color:#111; font-size:16px; font-weight:700;
            cursor:pointer; }}
  button:hover {{ background:#e5b32a; }}
  .err {{ color:#f85149; font-size:14px; }}
  .hint {{ color:#8b949e; font-size:12px; margin-top:16px; line-height:1.5; }}
  code {{ background:#0d1117; padding:2px 6px; border-radius:4px; }}
</style></head>
<body><div class="card">
  <h1>&#x1F512; Lyra</h1>
  <p class="sub">Enter your dashboard token to continue.</p>
  {err_html}
  <form method="post" action="/login">
    <input type="hidden" name="next" value="{quote(safe)}">
    <input type="password" name="token" placeholder="Dashboard token"
           autocomplete="current-password" autofocus>
    <button type="submit">Sign in</button>
  </form>
  <p class="hint">The token is in <code>data/.api_token</code> on first run,
  or set <code>LYRA_API_TOKEN</code> / <code>server.api_token</code> to use
  your own.</p>
</div></body></html>"""


class AuthMiddleware:
    """Pure-ASGI auth gate: HTTP + websocket. Exempts /login, /static, /webhook."""

    EXEMPT_PREFIXES = ("/login", "/static/", "/webhook/", "/webhook")

    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    def _exempt(self, path: str) -> bool:
        return path == "/login" or any(
            path == p or path.startswith(p) for p in self.EXEMPT_PREFIXES if p != "/login"
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "") or "/"
        if self._exempt(path):
            await self.app(scope, receive, send)
            return

        if is_authenticated(scope, self.token):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 4401})
            return

        accept = _get_header(scope, "accept")
        if "text/html" in accept:
            location = "/login?next=" + quote(path, safe="")
            await self._respond(
                send, 302, [(b"location", location.encode("latin-1"))], b""
            )
        else:
            body = b'{"detail":"Unauthorized: a valid dashboard token is required"}'
            await self._respond(
                send, 401, [(b"content-type", b"application/json")], body
            )

    @staticmethod
    async def _respond(send, status: int, headers: list, body: bytes):
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers,
            }
        )
        await send({"type": "http.response.body", "body": body})
