"""
Browser automation module — using Playwright for full browser control.
Supports Chromium, Firefox, and WebKit (Safari).
"""

import asyncio
import os
import time
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import Playwright
try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Run: pip install playwright && playwright install")


class BrowserControl:
    """Async browser automation controller using Playwright."""
    
    def __init__(self, headless: bool = True, browser_type: str = "chromium",
                 default_timeout: int = 30000, screenshot_dir: str = None):
        self.headless = headless
        self.browser_type = browser_type
        self.default_timeout = default_timeout
        self.screenshot_dir = screenshot_dir or os.path.join(
            os.path.expanduser("~"), ".agent_screenshots"
        )
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._pages: dict = {}  # Named tabs
        self._current_tab: str = "main"
    
    async def _ensure_browser(self):
        """Lazy-init the browser if not already running."""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install")
        
        if self._browser and self._browser.is_connected():
            return
        
        self._playwright = await async_playwright().start()
        
        browser_launcher = {
            "chromium": self._playwright.chromium,
            "firefox": self._playwright.firefox,
            "webkit": self._playwright.webkit,
        }.get(self.browser_type, self._playwright.chromium)
        
        self._browser = await browser_launcher.launch(headless=self.headless)
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (AutonomousAgent/1.0) Chrome/120.0",
        )
        self._page = await self._context.new_page()
        self._page.set_default_timeout(self.default_timeout)
        self._pages["main"] = self._page
        logger.info(f"Browser started ({self.browser_type}, headless={self.headless})")
    
    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> dict:
        """Navigate to a URL."""
        await self._ensure_browser()
        try:
            response = await self._page.goto(url, wait_until=wait_until)
            return {
                "status": "success",
                "url": self._page.url,
                "title": await self._page.title(),
                "status_code": response.status if response else None,
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def click(self, selector: str, timeout: int = None) -> dict:
        """Click an element by CSS selector."""
        await self._ensure_browser()
        try:
            await self._page.click(selector, timeout=timeout or self.default_timeout)
            return {"status": "success", "selector": selector}
        except Exception as e:
            return {"error": str(e)}
    
    async def click_text(self, text: str, timeout: int = None) -> dict:
        """Click an element by visible text."""
        await self._ensure_browser()
        try:
            await self._page.get_by_text(text).first.click(timeout=timeout or self.default_timeout)
            return {"status": "success", "text": text}
        except Exception as e:
            return {"error": str(e)}
    
    async def type_text(self, selector: str, text: str, delay: int = 50,
                        clear_first: bool = True) -> dict:
        """Type text into an input field."""
        await self._ensure_browser()
        try:
            if clear_first:
                await self._page.fill(selector, "")
            await self._page.type(selector, text, delay=delay)
            return {"status": "success", "selector": selector, "text": text}
        except Exception as e:
            return {"error": str(e)}
    
    async def fill_form(self, fields: dict) -> dict:
        """Fill multiple form fields at once."""
        await self._ensure_browser()
        results = {}
        for selector, value in fields.items():
            try:
                await self._page.fill(selector, str(value))
                results[selector] = "success"
            except Exception as e:
                results[selector] = f"error: {e}"
        return {"status": "success", "results": results}
    
    async def get_text(self, selector: str = None) -> dict:
        """Get text content of an element or the full page."""
        await self._ensure_browser()
        try:
            if selector:
                text = await self._page.inner_text(selector)
            else:
                text = await self._page.inner_text("body")
            if len(text) > 10000:
                text = text[:10000] + "\n...[truncated]"
            return {"status": "success", "text": text}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_html(self, selector: str = None) -> dict:
        """Get HTML content of an element or the full page."""
        await self._ensure_browser()
        try:
            if selector:
                html = await self._page.inner_html(selector)
            else:
                html = await self._page.content()
            if len(html) > 20000:
                html = html[:20000] + "\n...[truncated]"
            return {"status": "success", "html": html}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_attribute(self, selector: str, attribute: str) -> dict:
        """Get an attribute value of an element."""
        await self._ensure_browser()
        try:
            value = await self._page.get_attribute(selector, attribute)
            return {"status": "success", "attribute": attribute, "value": value}
        except Exception as e:
            return {"error": str(e)}
    
    async def screenshot(self, full_page: bool = False, save_path: str = None) -> dict:
        """Take a screenshot of the page."""
        await self._ensure_browser()
        if not save_path:
            save_path = os.path.join(self.screenshot_dir, f"browser_{int(time.time())}.png")
        try:
            await self._page.screenshot(path=save_path, full_page=full_page)
            return {"status": "success", "path": save_path}
        except Exception as e:
            return {"error": str(e)}
    
    async def execute_js(self, script: str) -> dict:
        """Execute JavaScript on the page and return the result."""
        await self._ensure_browser()
        try:
            result = await self._page.evaluate(script)
            return {"status": "success", "result": result}
        except Exception as e:
            return {"error": str(e)}
    
    async def scroll(self, direction: str = "down", amount: int = 500) -> dict:
        """Scroll the page in a direction."""
        await self._ensure_browser()
        try:
            if direction == "down":
                await self._page.mouse.wheel(0, amount)
            elif direction == "up":
                await self._page.mouse.wheel(0, -amount)
            elif direction == "top":
                await self._page.evaluate("window.scrollTo(0, 0)")
            elif direction == "bottom":
                await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            return {"status": "success", "direction": direction, "amount": amount}
        except Exception as e:
            return {"error": str(e)}
    
    async def wait_for(self, selector: str, timeout: int = None) -> dict:
        """Wait for an element to appear on the page."""
        await self._ensure_browser()
        try:
            await self._page.wait_for_selector(selector, timeout=timeout or self.default_timeout)
            return {"status": "success", "selector": selector}
        except Exception as e:
            return {"error": str(e)}
    
    async def wait_for_navigation(self, timeout: int = None) -> dict:
        """Wait for page navigation to complete."""
        await self._ensure_browser()
        try:
            await self._page.wait_for_load_state("networkidle", timeout=timeout or self.default_timeout)
            return {"status": "success", "url": self._page.url}
        except Exception as e:
            return {"error": str(e)}
    
    async def press_key(self, key: str) -> dict:
        """Press a keyboard key (e.g. 'Enter', 'Escape', 'Tab')."""
        await self._ensure_browser()
        try:
            await self._page.keyboard.press(key)
            return {"status": "success", "key": key}
        except Exception as e:
            return {"error": str(e)}
    
    async def new_tab(self, name: str, url: str = None) -> dict:
        """Open a new browser tab with a name."""
        await self._ensure_browser()
        try:
            page = await self._context.new_page()
            page.set_default_timeout(self.default_timeout)
            self._pages[name] = page
            self._current_tab = name
            if url:
                await page.goto(url)
            return {"status": "success", "tab": name, "url": page.url}
        except Exception as e:
            return {"error": str(e)}
    
    async def switch_tab(self, name: str) -> dict:
        """Switch to a named tab."""
        await self._ensure_browser()
        if name not in self._pages:
            return {"error": f"Tab '{name}' not found. Available: {list(self._pages.keys())}"}
        self._page = self._pages[name]
        self._current_tab = name
        return {"status": "success", "tab": name, "url": self._page.url}
    
    async def close_tab(self, name: str) -> dict:
        """Close a named tab."""
        await self._ensure_browser()
        if name not in self._pages:
            return {"error": f"Tab '{name}' not found"}
        await self._pages[name].close()
        del self._pages[name]
        if self._current_tab == name:
            self._current_tab = "main" if "main" in self._pages else (list(self._pages.keys())[0] if self._pages else None)
            if self._current_tab:
                self._page = self._pages[self._current_tab]
        return {"status": "success", "closed": name}
    
    async def list_tabs(self) -> dict:
        """List all open tabs."""
        await self._ensure_browser()
        tabs = {}
        for name, page in self._pages.items():
            tabs[name] = {"url": page.url, "current": name == self._current_tab}
        return {"status": "success", "tabs": tabs, "current": self._current_tab}
    
    async def get_links(self) -> dict:
        """Extract all links from the page."""
        await self._ensure_browser()
        try:
            links = await self._page.evaluate("""
                () => {
                    return Array.from(document.querySelectorAll('a[href]')).map(a => ({
                        text: a.textContent.trim().substring(0, 100),
                        href: a.href
                    })).filter(l => l.href && !l.href.startsWith('javascript:'))
                }
            """)
            return {"status": "success", "links": links[:100], "count": len(links)}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_page_info(self) -> dict:
        """Get current page metadata."""
        await self._ensure_browser()
        try:
            return {
                "status": "success",
                "url": self._page.url,
                "title": await self._page.title(),
                "current_tab": self._current_tab,
                "open_tabs": list(self._pages.keys()),
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def set_cookies(self, cookies: list) -> dict:
        """Set cookies on the browser context."""
        await self._ensure_browser()
        try:
            await self._context.add_cookies(cookies)
            return {"status": "success", "count": len(cookies)}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_cookies(self) -> dict:
        """Get all cookies from the browser context."""
        await self._ensure_browser()
        try:
            cookies = await self._context.cookies()
            return {"status": "success", "cookies": cookies}
        except Exception as e:
            return {"error": str(e)}
    
    async def download_file(self, url: str, save_path: str = None) -> dict:
        """Download a file from a URL."""
        await self._ensure_browser()
        if not save_path:
            save_path = os.path.join(os.path.expanduser("~"), "downloads",
                                     url.split("/")[-1].split("?")[0] or "download")
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        try:
            async with self._page.expect_download() as download_info:
                await self._page.goto(url)
            download = await download_info.value
            await download.save_as(save_path)
            return {"status": "success", "path": save_path, "url": url}
        except Exception as e:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        with open(save_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(8192):
                                f.write(chunk)
                return {"status": "success", "path": save_path, "url": url}
            except Exception as e2:
                return {"error": f"Download failed: {e2}"}
    
    async def close(self):
        """Close the browser."""
        if self._browser:
            try:
                await self._browser.close()
            except:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except:
                pass
        self._browser = None
        self._context = None
        self._page = None
        self._pages = {}
        logger.info("Browser closed")
    
    async def is_available(self) -> dict:
        """Check if browser automation is available."""
        return {
            "available": PLAYWRIGHT_AVAILABLE,
            "browser_type": self.browser_type if PLAYWRIGHT_AVAILABLE else None,
            "headless": self.headless,
        }
