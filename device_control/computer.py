"""
Computer control module — mouse, keyboard, screenshots, and shell commands.
"""

import subprocess
import platform
import time
import os
import logging

# pyautogui is only available on desktop (X11/macOS/Windows).
# On Android/Termux it cannot be installed — guard the import so the
# rest of the module (shell commands, system info, directory listing)
# still works on headless/mobile environments.
try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
    PYAUTOGUI_AVAILABLE = True
except Exception:
    PYAUTOGUI_AVAILABLE = False

logger = logging.getLogger(__name__)


def _require_pyautogui():
    if not PYAUTOGUI_AVAILABLE:
        raise RuntimeError(
            "pyautogui is not available on this platform "
            "(no desktop display / not installed). "
            "Enable the desktop environment or use a config where "
            "devices.computer.gui is disabled."
        )


class ComputerControl:
    def __init__(self, screen_scale: float = 1.0, blocked_commands: list = None):
        self.screen_scale = screen_scale
        self.blocked_commands = blocked_commands or []
        self.system = platform.system()

    def _scale_coords(self, x: int, y: int) -> tuple:
        """Scale coordinates for HiDPI displays."""
        return int(x * self.screen_scale), int(y * self.screen_scale)

    # === Screen ===
    
    def screenshot(self, save_path: str = None) -> dict:
        """Take a screenshot."""

        if not PYAUTOGUI_AVAILABLE:
            return {"error": "pyautogui unavailable on this platform (no desktop display). GUI control is disabled."}
        try:
            screenshot = pyautogui.screenshot()
            if save_path:
                screenshot.save(save_path)
                return {"status": "success", "path": save_path, "size": screenshot.size}
            # Save to temp and return
            import tempfile
            path = os.path.join(tempfile.gettempdir(), f"agent_screenshot_{int(time.time())}.png")
            screenshot.save(path)
            return {"status": "success", "path": path, "size": screenshot.size}
        except Exception as e:
            return {"error": str(e)}

    def get_screen_size(self) -> dict:
        """Get screen dimensions."""

        if not PYAUTOGUI_AVAILABLE:
            return {"error": "pyautogui unavailable on this platform (no desktop display). GUI control is disabled."}
        try:
            w, h = pyautogui.size()
            return {"width": w, "height": h}
        except Exception as e:
            return {"error": str(e)}

    # === Mouse ===
    
    def mouse_move(self, x: int, y: int) -> dict:
        """Move mouse to coordinates."""

        if not PYAUTOGUI_AVAILABLE:
            return {"error": "pyautogui unavailable on this platform (no desktop display). GUI control is disabled."}
        try:
            x, y = self._scale_coords(x, y)
            pyautogui.moveTo(x, y, duration=0.3)
            return {"status": "success", "x": x, "y": y}
        except Exception as e:
            return {"error": str(e)}

    def mouse_click(self, x: int = None, y: int = None, button: str = "left",
                     clicks: int = 1, duration: float = 0.3) -> dict:
        """Click the mouse at coordinates or current position."""

        if not PYAUTOGUI_AVAILABLE:
            return {"error": "pyautogui unavailable on this platform (no desktop display). GUI control is disabled."}
        try:
            if x is not None and y is not None:
                x, y = self._scale_coords(x, y)
                pyautogui.click(x, y, button=button, clicks=clicks, duration=duration)
            else:
                pyautogui.click(button=button, clicks=clicks)
            return {"status": "success", "x": x, "y": y, "button": button, "clicks": clicks}
        except Exception as e:
            return {"error": str(e)}

    def mouse_right_click(self, x: int = None, y: int = None) -> dict:
        """Right-click the mouse."""

        if not PYAUTOGUI_AVAILABLE:
            return {"error": "pyautogui unavailable on this platform (no desktop display). GUI control is disabled."}
        return self.mouse_click(x=x, y=y, button="right")

    def mouse_double_click(self, x: int = None, y: int = None) -> dict:
        """Double-click the mouse."""

        if not PYAUTOGUI_AVAILABLE:
            return {"error": "pyautogui unavailable on this platform (no desktop display). GUI control is disabled."}
        return self.mouse_click(x=x, y=y, clicks=2)

    def mouse_drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> dict:
        """Drag from one point to another."""

        if not PYAUTOGUI_AVAILABLE:
            return {"error": "pyautogui unavailable on this platform (no desktop display). GUI control is disabled."}
        try:
            x1, y1 = self._scale_coords(x1, y1)
            x2, y2 = self._scale_coords(x2, y2)
            pyautogui.moveTo(x1, y1, duration=0.2)
            pyautogui.dragTo(x2, y2, duration=duration, button="left")
            return {"status": "success", "from": [x1, y1], "to": [x2, y2]}
        except Exception as e:
            return {"error": str(e)}

    def mouse_scroll(self, clicks: int = 3, x: int = None, y: int = None) -> dict:
        """Scroll the mouse wheel."""

        if not PYAUTOGUI_AVAILABLE:
            return {"error": "pyautogui unavailable on this platform (no desktop display). GUI control is disabled."}
        try:
            if x is not None and y is not None:
                x, y = self._scale_coords(x, y)
                pyautogui.moveTo(x, y)
            pyautogui.scroll(clicks)
            return {"status": "success", "scroll": clicks}
        except Exception as e:
            return {"error": str(e)}

    # === Keyboard ===
    
    def key_type(self, text: str, interval: float = 0.05) -> dict:
        """Type a string of text."""

        if not PYAUTOGUI_AVAILABLE:
            return {"error": "pyautogui unavailable on this platform (no desktop display). GUI control is disabled."}
        try:
            pyautogui.typewrite(text, interval=interval)
            return {"status": "success", "text": text}
        except Exception as e:
            return {"error": str(e)}

    def key_press(self, key: str, presses: int = 1) -> dict:
        """Press a single key or key combination."""

        if not PYAUTOGUI_AVAILABLE:
            return {"error": "pyautogui unavailable on this platform (no desktop display). GUI control is disabled."}
        try:
            # Support combinations like "ctrl+c", "alt+tab"
            if "+" in key:
                keys = key.split("+")
                pyautogui.hotkey(*keys)
            else:
                pyautogui.press(key, presses=presses)
            return {"status": "success", "key": key}
        except Exception as e:
            return {"error": str(e)}

    def key_hotkey(self, *keys) -> dict:
        """Press a key combination."""

        if not PYAUTOGUI_AVAILABLE:
            return {"error": "pyautogui unavailable on this platform (no desktop display). GUI control is disabled."}
        try:
            pyautogui.hotkey(*keys)
            return {"status": "success", "keys": list(keys)}
        except Exception as e:
            return {"error": str(e)}

    # === Shell ===
    
    def run_command(self, command: str, timeout: int = 30, cwd: str = None) -> dict:
        """Run a shell command."""
        # Check blocked commands
        for blocked in self.blocked_commands:
            if blocked in command:
                return {"error": f"Blocked command: contains '{blocked}'"}

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
            return {
                "status": "success" if result.returncode == 0 else "error",
                "stdout": result.stdout[:5000],  # Limit output
                "stderr": result.stderr[:5000] if result.stderr else "",
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {timeout}s", "timeout": True}
        except Exception as e:
            return {"error": str(e)}

    # === System Info ===
    
    def get_system_info(self) -> dict:
        """Get system information."""
        return {
            "os": self.system,
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
        }

    def list_directory(self, path: str = ".") -> dict:
        """List contents of a directory."""
        try:
            entries = []
            for entry in os.listdir(path):
                full_path = os.path.join(path, entry)
                entries.append({
                    "name": entry,
                    "type": "directory" if os.path.isdir(full_path) else "file",
                    "size": os.path.getsize(full_path) if os.path.isfile(full_path) else None,
                })
            return {"status": "success", "path": path, "entries": entries}
        except Exception as e:
            return {"error": str(e)}

    def open_application(self, app_name: str) -> dict:
        """Open an application."""
        try:
            if self.system == "Darwin":  # macOS
                subprocess.Popen(["open", "-a", app_name])
            elif self.system == "Windows":
                subprocess.Popen(["start", app_name], shell=True)
            else:  # Linux
                subprocess.Popen([app_name])
            return {"status": "success", "app": app_name}
        except Exception as e:
            return {"error": str(e)}

    def open_url(self, url: str) -> dict:
        """Open a URL in the default browser."""
        try:
            if self.system == "Darwin":
                subprocess.Popen(["open", url])
            elif self.system == "Windows":
                subprocess.Popen(["start", url], shell=True)
            else:
                subprocess.Popen(["xdg-open", url])
            return {"status": "success", "url": url}
        except Exception as e:
            return {"error": str(e)}
