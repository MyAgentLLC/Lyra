"""
Web tools — fetch pages, download files, and web search.

Privacy note: these tools ONLY make network calls when the agent is
explicitly asked to fetch a URL or search. Nothing fires automatically.
"""

import json
import os
import re
import urllib.request
import urllib.parse

USER_AGENT = "Mozilla/5.0 (Linux; Android 14) LyraAgent/2.0"
MAX_TEXT = 20000


def _fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _strip_html(html: str) -> str:
    """Very basic HTML → text."""
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</p>", "\n\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


import html as _html_mod


def _clean_title(s: str) -> str:
    """Clean a search-result title: drop tags (no spaces), unescape entities, collapse whitespace."""
    s = re.sub(r"<[^>]+>", "", s)
    s = _html_mod.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


# ── Tools ──

def fetch_url(url: str = "", max_chars: int = 8000, **kw):
    """Fetch a URL and return readable text content."""
    if not url:
        return {"error": "url is required"}
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        html = _fetch(url)
        text = _strip_html(html)
        truncated = len(text) > max_chars
        return {
            "status": "success",
            "url": url,
            "content": text[:max_chars],
            "truncated": truncated,
        }
    except Exception as e:
        return {"error": f"failed to fetch {url}: {e}"}


def download_file(url: str = "", path: str = "", **kw):
    """Download a file from a URL to a local path."""
    if not url or not path:
        return {"error": "url and path are required"}
    if not url.startswith(("http://", "https://")):
        return {"error": "only http/https URLs are supported"}
    # Keep downloads inside the user's home for safety
    full = os.path.abspath(os.path.expanduser(path))
    home = os.path.expanduser("~")
    if not full.startswith(home):
        return {"error": "path must be inside your home directory"}
    try:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=120) as resp, open(full, "wb") as f:
            f.write(resp.read())
        size = os.path.getsize(full)
        return {"status": "success", "path": full, "bytes": size}
    except Exception as e:
        return {"error": f"download failed: {e}"}


def _search_ddg(query: str, max_results: int) -> list:
    """Search DuckDuckGo HTML endpoint. Returns [] if throttled/unparseable."""
    q = urllib.parse.quote_plus(query)
    html = _fetch(f"https://html.duckduckgo.com/html/?q={q}")
    link_re = re.compile(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
    snip_re = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)
    links = link_re.findall(html)
    snippets = snip_re.findall(html)
    results = []
    for i, (href, title) in enumerate(links[:max_results]):
        if "uddg=" in href:
            m = re.search(r"uddg=([^&]+)", href)
            if m:
                href = urllib.parse.unquote(m.group(1))
        snippet = _strip_html(snippets[i]) if i < len(snippets) else ""
        results.append({"title": _clean_title(title), "url": href, "snippet": snippet[:300]})
    return results


def _search_bing(query: str, max_results: int) -> list:
    """Search Bing. Fallback engine — reliable, no hard throttle."""
    q = urllib.parse.quote_plus(query)
    html = _fetch(f"https://www.bing.com/search?q={q}")
    item_re = re.compile(
        r'<div class="b_algoheader"><a href="([^"]+)"[^>]*><h2[^>]*>(.*?)</h2></a></div>'
        r'.*?<p class="b_lineclamp3"[^>]*>(.*?)</p>', re.DOTALL)
    results = []
    for href, title, snippet in item_re.findall(html)[:max_results]:
        results.append({
            "title": _clean_title(title),
            "url": href,
            "snippet": _strip_html(snippet)[:300],
        })
    return results


def web_search(query: str = "", max_results: int = 5, **kw):
    """Search the web. Tries DuckDuckGo first, falls back to Bing when throttled."""
    if not query:
        return {"error": "query is required"}
    errors = []
    for engine_name, engine in (("duckduckgo", _search_ddg), ("bing", _search_bing)):
        try:
            results = engine(query, max_results)
            if results:
                return {"status": "success", "query": query, "engine": engine_name,
                        "results": results,
                        "note": "Use fetch_url on any result for full content."}
            errors.append(f"{engine_name}: no results")
        except Exception as e:
            errors.append(f"{engine_name}: {e}")
    return {"error": f"all search engines failed: {'; '.join(errors)}"}


def setup(api):
    api.log("web_tools plugin loading")

    api.register_tool(
        name="fetch_url",
        description="Fetch a web page or API URL and return its readable text content. Use for reading articles, docs, or JSON APIs.",
        parameters={"type": "object", "properties": {
            "url": {"type": "string"},
            "max_chars": {"type": "integer", "default": 8000},
        }, "required": ["url"]},
        handler=fetch_url,
        category="web",
    )
    api.register_tool(
        name="download_file",
        description="Download a file from a URL and save it to a local path in the home directory.",
        parameters={"type": "object", "properties": {
            "url": {"type": "string"},
            "path": {"type": "string", "description": "Local file path to save to"},
        }, "required": ["url", "path"]},
        handler=download_file,
        requires_confirmation=True,
        category="web",
    )
    api.register_tool(
        name="web_search",
        description="Search the web (DuckDuckGo with Bing fallback). Returns titles, URLs, and snippets. Follow up with fetch_url to read a result.",
        parameters={"type": "object", "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "default": 5},
        }, "required": ["query"]},
        handler=web_search,
        category="web",
    )

    api.log(f"web_tools registered {len(api._tools_added)} tools")


def teardown():
    pass
