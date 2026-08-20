"""
Tool registration — wires up all device control functions into the tool registry.
Includes computer, phone, filesystem, browser, and plugin tools.
"""

import json
import asyncio
from ..tools.tool_registry import Tool, ToolRegistry
from ..device_control.computer import ComputerControl
from ..device_control.phone import PhoneControl
from ..device_control.filesystem import FilesystemControl
from ..device_control.browser import BrowserControl


def build_tool_registry(config: dict) -> ToolRegistry:
    """Build and populate the tool registry with all available tools."""
    registry = ToolRegistry()
    devices_config = config.get("devices", {})
    
    # === Computer Control Tools ===
    if devices_config.get("computer", {}).get("enabled", True):
        computer = ComputerControl(
            screen_scale=devices_config.get("computer", {}).get("screen_scale", 1.0),
            blocked_commands=config.get("safety", {}).get("blocked_commands", []),
        )
        
        registry.register(Tool(
            name="computer_screenshot",
            description="Take a screenshot of the computer screen. Returns the file path.",
            parameters={"type": "object", "properties": {}},
            handler=lambda **kw: computer.screenshot(),
            category="computer",
        ))
        registry.register(Tool(
            name="computer_screen_size",
            description="Get the screen dimensions in pixels.",
            parameters={"type": "object", "properties": {}},
            handler=lambda **kw: computer.get_screen_size(),
            category="computer",
        ))
        registry.register(Tool(
            name="computer_click",
            description="Click the mouse at the specified coordinates. If x and y are omitted, clicks at current position.",
            parameters={"type": "object", "properties": {
                "x": {"type": "integer", "description": "X coordinate (pixels from left)"},
                "y": {"type": "integer", "description": "Y coordinate (pixels from top)"},
                "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
                "clicks": {"type": "integer", "default": 1},
            }},
            handler=lambda **kw: computer.mouse_click(x=kw.get("x"), y=kw.get("y"), button=kw.get("button", "left"), clicks=kw.get("clicks", 1)),
            category="computer",
        ))
        registry.register(Tool(
            name="computer_mouse_move",
            description="Move the mouse cursor to the specified coordinates.",
            parameters={"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]},
            handler=lambda **kw: computer.mouse_move(kw["x"], kw["y"]),
            category="computer",
        ))
        registry.register(Tool(
            name="computer_drag",
            description="Drag the mouse from one point to another.",
            parameters={"type": "object", "properties": {"x1": {"type": "integer"}, "y1": {"type": "integer"}, "x2": {"type": "integer"}, "y2": {"type": "integer"}}, "required": ["x1", "y1", "x2", "y2"]},
            handler=lambda **kw: computer.mouse_drag(kw["x1"], kw["y1"], kw["x2"], kw["y2"]),
            category="computer",
        ))
        registry.register(Tool(
            name="computer_scroll",
            description="Scroll the mouse wheel. Positive clicks scroll up, negative scrolls down.",
            parameters={"type": "object", "properties": {"clicks": {"type": "integer", "default": 3}}},
            handler=lambda **kw: computer.mouse_scroll(kw.get("clicks", 3)),
            category="computer",
        ))
        registry.register(Tool(
            name="computer_type",
            description="Type text on the keyboard. Use this to enter text into fields.",
            parameters={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            handler=lambda **kw: computer.key_type(kw["text"]),
            category="computer",
        ))
        registry.register(Tool(
            name="computer_key_press",
            description="Press a key or key combination. Use '+' for combos like 'ctrl+c', 'alt+tab', 'cmd+space'.",
            parameters={"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
            handler=lambda **kw: computer.key_press(kw["key"]),
            category="computer",
        ))
        registry.register(Tool(
            name="computer_shell",
            description="Run a shell command on the computer. Returns stdout, stderr, and return code.",
            parameters={"type": "object", "properties": {"command": {"type": "string"}, "timeout": {"type": "integer", "default": 30}, "cwd": {"type": "string"}}, "required": ["command"]},
            handler=lambda **kw: computer.run_command(kw["command"], timeout=kw.get("timeout", 30), cwd=kw.get("cwd")),
            requires_confirmation=True,
            category="computer",
        ))
        registry.register(Tool(
            name="computer_open_app",
            description="Open an application by name.",
            parameters={"type": "object", "properties": {"app_name": {"type": "string"}}, "required": ["app_name"]},
            handler=lambda **kw: computer.open_application(kw["app_name"]),
            category="computer",
        ))
        registry.register(Tool(
            name="computer_open_url",
            description="Open a URL in the default browser.",
            parameters={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
            handler=lambda **kw: computer.open_url(kw["url"]),
            category="computer",
        ))
        registry.register(Tool(
            name="computer_system_info",
            description="Get system information (OS, processor, hostname).",
            parameters={"type": "object", "properties": {}},
            handler=lambda **kw: computer.get_system_info(),
            category="computer",
        ))
        registry.register(Tool(
            name="computer_list_directory",
            description="List the contents of a directory.",
            parameters={"type": "object", "properties": {"path": {"type": "string", "default": "."}}},
            handler=lambda **kw: computer.list_directory(kw.get("path", ".")),
            category="computer",
        ))
    
    # === Phone Control Tools ===
    if devices_config.get("phone", {}).get("enabled", True):
        phone = PhoneControl(
            device_serial=devices_config.get("phone", {}).get("device_serial", ""),
            screenshot_quality=devices_config.get("phone", {}).get("screenshot_quality", 80),
        )
        
        registry.register(Tool(
            name="phone_check_connection",
            description="Check if an Android phone is connected via ADB. Returns list of connected devices.",
            parameters={"type": "object", "properties": {}},
            handler=lambda **kw: phone.check_connection(),
            category="phone",
        ))
        registry.register(Tool(
            name="phone_screenshot",
            description="Take a screenshot of the Android phone screen. Returns the file path.",
            parameters={"type": "object", "properties": {}},
            handler=lambda **kw: phone.screenshot(),
            category="phone",
        ))
        registry.register(Tool(
            name="phone_tap",
            description="Tap the phone screen at the specified coordinates.",
            parameters={"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]},
            handler=lambda **kw: phone.tap(kw["x"], kw["y"]),
            category="phone",
        ))
        registry.register(Tool(
            name="phone_swipe",
            description="Swipe on the phone screen from one point to another.",
            parameters={"type": "object", "properties": {"x1": {"type": "integer"}, "y1": {"type": "integer"}, "x2": {"type": "integer"}, "y2": {"type": "integer"}, "duration": {"type": "integer", "default": 300}}, "required": ["x1", "y1", "x2", "y2"]},
            handler=lambda **kw: phone.swipe(kw["x1"], kw["y1"], kw["x2"], kw["y2"], kw.get("duration", 300)),
            category="phone",
        ))
        registry.register(Tool(
            name="phone_type_text",
            description="Type text on the phone keyboard.",
            parameters={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            handler=lambda **kw: phone.type_text(kw["text"]),
            category="phone",
        ))
        registry.register(Tool(
            name="phone_key_press",
            description="Press a phone key. Common keycodes: KEYCODE_HOME, KEYCODE_BACK, KEYCODE_MENU, KEYCODE_POWER, KEYCODE_VOLUME_UP, KEYCODE_VOLUME_DOWN, KEYCODE_ENTER, KEYCODE_DEL.",
            parameters={"type": "object", "properties": {"keycode": {"type": "string"}}, "required": ["keycode"]},
            handler=lambda **kw: phone.key_press(kw["keycode"]),
            category="phone",
        ))
        registry.register(Tool(
            name="phone_open_app",
            description="Open an app on the phone by package name (e.g. com.android.chrome, com.whatsapp).",
            parameters={"type": "object", "properties": {"package": {"type": "string"}}, "required": ["package"]},
            handler=lambda **kw: phone.open_app(kw["package"]),
            category="phone",
        ))
        registry.register(Tool(
            name="phone_list_apps",
            description="List all installed third-party apps on the phone.",
            parameters={"type": "object", "properties": {}},
            handler=lambda **kw: phone.list_packages(),
            category="phone",
        ))
        registry.register(Tool(
            name="phone_device_info",
            description="Get phone device information (model, brand, Android version).",
            parameters={"type": "object", "properties": {}},
            handler=lambda **kw: phone.get_device_info(),
            category="phone",
        ))
        registry.register(Tool(
            name="phone_screen_resolution",
            description="Get the phone screen resolution.",
            parameters={"type": "object", "properties": {}},
            handler=lambda **kw: phone.get_screen_resolution(),
            category="phone",
        ))
        registry.register(Tool(
            name="phone_install_app",
            description="Install an APK file on the phone.",
            parameters={"type": "object", "properties": {"apk_path": {"type": "string"}}, "required": ["apk_path"]},
            handler=lambda **kw: phone.install_app(kw["apk_path"]),
            requires_confirmation=True,
            category="phone",
        ))
        registry.register(Tool(
            name="phone_shell",
            description="Run an arbitrary shell command on the Android phone.",
            parameters={"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
            handler=lambda **kw: phone.shell(kw["command"]),
            requires_confirmation=True,
            category="phone",
        ))
    
    # === Filesystem Tools ===
    if devices_config.get("filesystem", {}).get("enabled", True):
        fs = FilesystemControl(
            allowed_roots=devices_config.get("filesystem", {}).get("allowed_roots", []),
            blocked_paths=devices_config.get("filesystem", {}).get("blocked_paths", []),
        )
        
        registry.register(Tool(
            name="file_read", description="Read the contents of a file.",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            handler=lambda **kw: fs.read_file(kw["path"]), category="filesystem",
        ))
        registry.register(Tool(
            name="file_write", description="Write content to a file. Creates the file if it doesn't exist.",
            parameters={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
            handler=lambda **kw: fs.write_file(kw["path"], kw["content"]), requires_confirmation=True, category="filesystem",
        ))
        registry.register(Tool(
            name="file_append", description="Append content to an existing file.",
            parameters={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
            handler=lambda **kw: fs.append_file(kw["path"], kw["content"]), category="filesystem",
        ))
        registry.register(Tool(
            name="file_delete", description="Delete a file.",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            handler=lambda **kw: fs.delete_file(kw["path"]), requires_confirmation=True, category="filesystem",
        ))
        registry.register(Tool(
            name="file_list", description="List contents of a directory.",
            parameters={"type": "object", "properties": {"path": {"type": "string", "default": "."}, "recursive": {"type": "boolean", "default": False}}},
            handler=lambda **kw: fs.list_directory(kw.get("path", "."), recursive=kw.get("recursive", False)), category="filesystem",
        ))
        registry.register(Tool(
            name="file_copy", description="Copy a file from one location to another.",
            parameters={"type": "object", "properties": {"src": {"type": "string"}, "dst": {"type": "string"}}, "required": ["src", "dst"]},
            handler=lambda **kw: fs.copy_file(kw["src"], kw["dst"]), category="filesystem",
        ))
        registry.register(Tool(
            name="file_move", description="Move or rename a file.",
            parameters={"type": "object", "properties": {"src": {"type": "string"}, "dst": {"type": "string"}}, "required": ["src", "dst"]},
            handler=lambda **kw: fs.move_file(kw["src"], kw["dst"]), category="filesystem",
        ))
        registry.register(Tool(
            name="file_search", description="Search for files by name pattern. Optionally search file contents.",
            parameters={"type": "object", "properties": {"directory": {"type": "string"}, "pattern": {"type": "string", "default": "*"}, "content_pattern": {"type": "string"}}, "required": ["directory"]},
            handler=lambda **kw: fs.search_files(kw["directory"], kw.get("pattern", "*"), kw.get("content_pattern")), category="filesystem",
        ))
        registry.register(Tool(
            name="file_info", description="Get detailed information about a file or directory.",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            handler=lambda **kw: fs.get_file_info(kw["path"]), category="filesystem",
        ))
        registry.register(Tool(
            name="file_mkdir", description="Create a directory.",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            handler=lambda **kw: fs.create_directory(kw["path"]), category="filesystem",
        ))
    
    # === Browser Automation Tools ===
    if devices_config.get("browser", {}).get("enabled", True):
        browser_config = devices_config.get("browser", {})
        browser = BrowserControl(
            headless=browser_config.get("headless", True),
            browser_type=browser_config.get("browser_type", "chromium"),
            default_timeout=browser_config.get("timeout", 30000),
        )
        
        # Helper to run async browser methods synchronously
        def _run_async(coro):
            """Run an async coroutine from a sync context."""
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context — create a task
                    task = asyncio.ensure_future(coro)
                    return asyncio.run(asyncio.wait_for(task, timeout=60))
                else:
                    return loop.run_until_complete(coro)
            except RuntimeError:
                return asyncio.run(coro)
        
        registry.register(Tool(
            name="browser_navigate",
            description="Navigate to a URL in the browser. Returns page title and status.",
            parameters={"type": "object", "properties": {"url": {"type": "string", "description": "URL to navigate to"}}, "required": ["url"]},
            handler=lambda **kw: _run_async(browser.navigate(kw["url"])),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_click",
            description="Click an element on the web page by CSS selector.",
            parameters={"type": "object", "properties": {"selector": {"type": "string", "description": "CSS selector for the element to click"}}, "required": ["selector"]},
            handler=lambda **kw: _run_async(browser.click(kw["selector"])),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_click_text",
            description="Click an element on the web page by its visible text.",
            parameters={"type": "object", "properties": {"text": {"type": "string", "description": "Visible text of the element to click"}}, "required": ["text"]},
            handler=lambda **kw: _run_async(browser.click_text(kw["text"])),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_type",
            description="Type text into a form field on the web page by CSS selector.",
            parameters={"type": "object", "properties": {"selector": {"type": "string", "description": "CSS selector for the input field"}, "text": {"type": "string", "description": "Text to type"}}, "required": ["selector", "text"]},
            handler=lambda **kw: _run_async(browser.type_text(kw["selector"], kw["text"])),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_get_text",
            description="Get text content from the web page. If selector is provided, gets text from that element; otherwise gets all page text.",
            parameters={"type": "object", "properties": {"selector": {"type": "string", "description": "CSS selector (optional — omit for full page text)"}}},
            handler=lambda **kw: _run_async(browser.get_text(kw.get("selector"))),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_get_html",
            description="Get HTML content from the web page. If selector is provided, gets HTML from that element; otherwise gets full page HTML.",
            parameters={"type": "object", "properties": {"selector": {"type": "string"}}},
            handler=lambda **kw: _run_async(browser.get_html(kw.get("selector"))),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_screenshot",
            description="Take a screenshot of the browser page. Returns the file path.",
            parameters={"type": "object", "properties": {"full_page": {"type": "boolean", "default": False, "description": "Capture full page (not just viewport)"}}},
            handler=lambda **kw: _run_async(browser.screenshot(full_page=kw.get("full_page", False))),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_execute_js",
            description="Execute JavaScript code on the current web page and return the result.",
            parameters={"type": "object", "properties": {"script": {"type": "string", "description": "JavaScript code to execute"}}, "required": ["script"]},
            handler=lambda **kw: _run_async(browser.execute_js(kw["script"])),
            requires_confirmation=True,
            category="browser",
        ))
        registry.register(Tool(
            name="browser_scroll",
            description="Scroll the web page. Directions: up, down, top, bottom.",
            parameters={"type": "object", "properties": {"direction": {"type": "string", "enum": ["up", "down", "top", "bottom"], "default": "down"}, "amount": {"type": "integer", "default": 500}}},
            handler=lambda **kw: _run_async(browser.scroll(kw.get("direction", "down"), kw.get("amount", 500))),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_press_key",
            description="Press a keyboard key on the browser page (e.g. 'Enter', 'Escape', 'Tab').",
            parameters={"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
            handler=lambda **kw: _run_async(browser.press_key(kw["key"])),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_wait_for",
            description="Wait for an element to appear on the web page.",
            parameters={"type": "object", "properties": {"selector": {"type": "string", "description": "CSS selector to wait for"}, "timeout": {"type": "integer", "default": 30000}}, "required": ["selector"]},
            handler=lambda **kw: _run_async(browser.wait_for(kw["selector"], kw.get("timeout"))),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_get_links",
            description="Extract all links from the current web page.",
            parameters={"type": "object", "properties": {}},
            handler=lambda **kw: _run_async(browser.get_links()),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_page_info",
            description="Get current page metadata (URL, title, open tabs).",
            parameters={"type": "object", "properties": {}},
            handler=lambda **kw: _run_async(browser.get_page_info()),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_new_tab",
            description="Open a new browser tab with a name. Optionally navigate to a URL.",
            parameters={"type": "object", "properties": {"name": {"type": "string", "description": "Name for the tab"}, "url": {"type": "string"}}, "required": ["name"]},
            handler=lambda **kw: _run_async(browser.new_tab(kw["name"], kw.get("url"))),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_switch_tab",
            description="Switch to a named browser tab.",
            parameters={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
            handler=lambda **kw: _run_async(browser.switch_tab(kw["name"])),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_list_tabs",
            description="List all open browser tabs.",
            parameters={"type": "object", "properties": {}},
            handler=lambda **kw: _run_async(browser.list_tabs()),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_fill_form",
            description="Fill multiple form fields at once. Pass a dictionary of {selector: value}.",
            parameters={"type": "object", "properties": {"fields": {"type": "object", "description": "Dictionary of CSS selectors to values"}}, "required": ["fields"]},
            handler=lambda **kw: _run_async(browser.fill_form(kw["fields"])),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_download",
            description="Download a file from a URL using the browser.",
            parameters={"type": "object", "properties": {"url": {"type": "string"}, "save_path": {"type": "string"}}, "required": ["url"]},
            handler=lambda **kw: _run_async(browser.download_file(kw["url"], kw.get("save_path"))),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_close",
            description="Close the browser and all open tabs.",
            parameters={"type": "object", "properties": {}},
            handler=lambda **kw: _run_async(browser.close()),
            category="browser",
        ))
        registry.register(Tool(
            name="browser_check_available",
            description="Check if browser automation is available (Playwright installed).",
            parameters={"type": "object", "properties": {}},
            handler=lambda **kw: _run_async(browser.is_available()),
            category="browser",
        ))
    
    return registry
