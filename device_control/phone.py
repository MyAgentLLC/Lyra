"""
Android phone control via ADB.
"""

import subprocess
import os
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PhoneControl:
    def __init__(self, device_serial: str = "", screenshot_quality: int = 80):
        self.device_serial = device_serial
        self.screenshot_quality = screenshot_quality
        self._adb_path = self._find_adb()

    def _find_adb(self) -> str:
        """Find ADB binary."""
        # Check common locations
        candidates = [
            "adb",  # In PATH
            "/usr/bin/adb",
            "/usr/local/bin/adb",
            "/opt/homebrew/bin/adb",
            os.path.expanduser("~/Android/Sdk/platform-tools/adb"),
        ]
        for c in candidates:
            try:
                subprocess.run([c, "version"], capture_output=True, check=True)
                return c
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        logger.warning("ADB not found. Install Android Platform Tools to enable phone control.")
        return "adb"

    def _adb(self, args: list, timeout: int = 30) -> dict:
        """Run an ADB command."""
        cmd = [self._adb_path]
        if self.device_serial:
            cmd.extend(["-s", self.device_serial])
        cmd.extend(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"error": "ADB command timed out", "success": False}
        except FileNotFoundError:
            return {"error": "ADB not found. Install Android Platform Tools.", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}

    def check_connection(self) -> dict:
        """Check if any device is connected."""
        result = self._adb(["devices"])
        if not result.get("success"):
            return {"connected": False, "error": result.get("error", result.get("stderr", ""))}
        
        lines = result["stdout"].strip().split("\n")[1:]  # Skip header
        devices = []
        for line in lines:
            if line.strip():
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    devices.append({"serial": parts[0], "state": parts[1]})
        
        return {
            "connected": len(devices) > 0,
            "devices": devices,
        }

    def screenshot(self, save_path: str = None) -> dict:
        """Take a screenshot from the phone."""
        if not save_path:
            save_path = os.path.join(os.path.expanduser("~"), ".agent_screenshots",
                                     f"phone_{int(time.time())}.png")
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # Capture to device, pull to local
        device_path = "/sdcard/agent_screenshot.png"
        result = self._adb(["shell", "screencap", "-p", device_path])
        if not result.get("success"):
            return {"error": result.get("error", result.get("stderr", "screencap failed"))}
        
        result = self._adb(["pull", device_path, save_path])
        if not result.get("success"):
            return {"error": "Failed to pull screenshot"}
        
        # Clean up on device
        self._adb(["shell", "rm", device_path])
        
        return {"status": "success", "path": save_path}

    def tap(self, x: int, y: int) -> dict:
        """Tap the screen at coordinates."""
        result = self._adb(["shell", "input", "tap", str(x), str(y)])
        return {"status": "success" if result.get("success") else "error",
                "x": x, "y": y, **result}

    def long_press(self, x: int, y: int, duration: int = 1000) -> dict:
        """Long press at coordinates."""
        result = self._adb(["shell", "input", "swipe", str(x), str(y), str(x), str(y), str(duration)])
        return {"status": "success" if result.get("success") else "error", **result}

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> dict:
        """Swipe from one point to another."""
        result = self._adb(["shell", "input", "swipe",
                           str(x1), str(y1), str(x2), str(y2), str(duration)])
        return {"status": "success" if result.get("success") else "error",
                "from": [x1, y1], "to": [x2, y2], **result}

    def type_text(self, text: str) -> dict:
        """Type text on the phone."""
        # Escape special characters
        escaped = text.replace(" ", "%s").replace("&", "\\&").replace("<", "\\<").replace(">", "\\>")
        result = self._adb(["shell", "input", "text", escaped])
        return {"status": "success" if result.get("success") else "error",
                "text": text, **result}

    def key_press(self, keycode: str) -> dict:
        """Press a phone key. Common keycodes: KEYCODE_HOME, KEYCODE_BACK,
        KEYCODE_MENU, KEYCODE_POWER, KEYCODE_VOLUME_UP, KEYCODE_VOLUME_DOWN,
        KEYCODE_ENTER, KEYCODE_DEL."""
        result = self._adb(["shell", "input", "keyevent", keycode])
        return {"status": "success" if result.get("success") else "error",
                "keycode": keycode, **result}

    def open_app(self, package: str) -> dict:
        """Open an app by package name."""
        result = self._adb(["shell", "monkey", "-p", package, "-c",
                           "android.intent.category.LAUNCHER", "1"])
        return {"status": "success" if result.get("success") else "error",
                "package": package, **result}

    def install_app(self, apk_path: str) -> dict:
        """Install an APK on the phone."""
        result = self._adb(["install", apk_path], timeout=120)
        return {"status": "success" if result.get("success") else "error",
                "apk": apk_path, **result}

    def uninstall_app(self, package: str) -> dict:
        """Uninstall an app."""
        result = self._adb(["uninstall", package])
        return {"status": "success" if result.get("success") else "error",
                "package": package, **result}

    def list_packages(self, third_party_only: bool = True) -> dict:
        """List installed packages."""
        args = ["shell", "pm", "list", "packages"]
        if third_party_only:
            args.append("-3")
        result = self._adb(args)
        if result.get("success"):
            packages = [p.strip().replace("package:", "") 
                       for p in result["stdout"].strip().split("\n") if p.strip()]
            return {"status": "success", "packages": packages, "count": len(packages)}
        return {"error": result.get("error", result.get("stderr", ""))}

    def get_device_info(self) -> dict:
        """Get device information."""
        props = {}
        for prop in ["ro.product.model", "ro.product.brand", "ro.product.manufacturer",
                     "ro.build.version.release", "ro.build.version.sdk"]:
            result = self._adb(["shell", "getprop", prop])
            if result.get("success"):
                props[prop] = result["stdout"].strip()
        return {"status": "success", "device_info": props}

    def get_screen_resolution(self) -> dict:
        """Get screen resolution."""
        result = self._adb(["shell", "wm", "size"])
        if result.get("success"):
            # Parse "Physical size: 1080x2400"
            line = result["stdout"].strip()
            if "Physical size:" in line:
                size = line.split("Physical size:")[1].strip()
                w, h = size.split("x")
                return {"status": "success", "width": int(w), "height": int(h)}
        return {"error": "Could not get screen resolution", **result}

    def pull_file(self, remote_path: str, local_path: str) -> dict:
        """Pull a file from the phone."""
        result = self._adb(["pull", remote_path, local_path], timeout=60)
        return {"status": "success" if result.get("success") else "error", **result}

    def push_file(self, local_path: str, remote_path: str) -> dict:
        """Push a file to the phone."""
        result = self._adb(["push", local_path, remote_path], timeout=60)
        return {"status": "success" if result.get("success") else "error", **result}

    def shell(self, command: str) -> dict:
        """Run an arbitrary shell command on the phone."""
        result = self._adb(["shell", command])
        return {"status": "success" if result.get("success") else "error", **result}

    def start_screen_record(self, duration: int = 180) -> dict:
        """Start screen recording (max 180 seconds)."""
        path = f"/sdcard/agent_record_{int(time.time())}.mp4"
        # This runs in background on the device
        result = self._adb(["shell", "screenrecord", "--time-limit", str(duration), path],
                          timeout=duration + 10)
        return {"status": "success" if result.get("success") else "error",
                "device_path": path, **result}
