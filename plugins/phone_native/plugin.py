"""
Phone native skills — powered by the Termux:API app.

Gives Lyra direct access to phone hardware and OS features:
notifications, text-to-speech, clipboard, battery status, location,
flashlight (torch), volume control, wifi info, and device info.

Requires:
  pkg install termux-api
  and the Termux:API companion app (F-Droid) for some commands.
All tools degrade gracefully with install instructions if missing.
"""

import json
import shutil
import subprocess
import platform
import os

TOOL_BIN = "termux-notification"


def _have_termux_api() -> bool:
    return shutil.which(TOOL_BIN) is not None


def _api_help() -> dict:
    return {
        "error": "Termux:API not installed. Run 'pkg install termux-api' "
                 "and install the Termux:API app from F-Droid, then try again."
    }


def _run(cmd: list, timeout: int = 20) -> dict:
    """Run a termux-api command and return parsed output."""
    if not _have_termux_api():
        return _api_help()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            return {"error": r.stderr.strip() or "command failed", "returncode": r.returncode}
        out = r.stdout.strip()
        # Many termux-api commands return JSON
        if out.startswith("{") or out.startswith("["):
            try:
                return {"status": "success", "data": json.loads(out)}
            except json.JSONDecodeError:
                pass
        return {"status": "success", "output": out}
    except subprocess.TimeoutExpired:
        return {"error": f"timed out after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}


# ── Tools ──

def phone_notify(title: str = "Lyra", text: str = "", **kw):
    """Send a notification to the phone."""
    if not text:
        return {"error": "text is required"}
    return _run([TOOL_BIN, "--title", title, "--content", text])


def phone_speak(text: str = "", **kw):
    """Speak text aloud with the phone's text-to-speech voice."""
    if not text:
        return {"error": "text is required"}
    return _run(["termux-tts-speak", text], timeout=60)


def phone_clipboard_get(**kw):
    """Read the phone clipboard contents."""
    return _run(["termux-clipboard-get"])


def phone_clipboard_set(text: str = "", **kw):
    """Write text to the phone clipboard."""
    if not text:
        return {"error": "text is required"}
    return _run(["termux-clipboard-set", text])


def phone_battery(**kw):
    """Get battery status (level, charging state, temperature, health)."""
    return _run(["termux-battery-status"])


def phone_location(provider: str = "network", **kw):
    """Get the current location. provider: 'gps' (accurate, slow) or 'network' (fast)."""
    if provider not in ("gps", "network"):
        provider = "network"
    return _run(["termux-location", "-p", provider], timeout=60)


def phone_flashlight(on: bool = True, **kw):
    """Turn the phone flashlight/LED torch on or off."""
    # on/off must be literal strings for termux-torch
    cmd = ["termux-torch", "on" if on else "off"]
    if not _have_termux_api():
        return _api_help()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        state = "on" if on else "off"
        if r.returncode != 0:
            return {"error": r.stderr.strip() or "torch command failed"}
        return {"status": "success", "flashlight": state}
    except Exception as e:
        return {"error": str(e)}


def phone_volume(percent: int = 50, stream: str = "music", **kw):
    """Set a volume level (0-100). stream: music, ring, notification, alarm."""
    if not isinstance(percent, int) or not 0 <= percent <= 100:
        return {"error": "percent must be an integer 0-100"}
    if stream not in ("music", "ring", "notification", "alarm", "system"):
        stream = "music"
    return _run(["termux-volume", stream, str(percent)])


def phone_wifi_info(**kw):
    """Get current wifi connection info (SSID, speed, signal)."""
    return _run(["termux-wifi-connectioninfo"])


def phone_device_info(**kw):
    """Get device info — Android version, kernel, CPU, memory, storage."""
    info = {"platform": platform.system()}
    try:
        # Android version + device name from system properties
        for prop in ("ro.build.version.release", "ro.product.model",
                     "ro.product.brand", "ro.build.version.sdk"):
            r = subprocess.run(["getprop", prop], capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                info[prop.replace("ro.", "")] = r.stdout.strip()
    except Exception:
        pass
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith(("MemTotal", "MemAvailable")):
                    k, v = line.split(":", 1)
                    info[k.strip()] = v.strip()
                    break
    except Exception:
        pass
    try:
        st = os.statvfs(os.path.expanduser("~"))
        info["storage_free_gb"] = round((st.f_bavail * st.f_frsize) / (1024 ** 3), 2)
        info["storage_total_gb"] = round((st.f_blocks * st.f_frsize) / (1024 ** 3), 2)
    except Exception:
        pass
    return {"status": "success", "data": info}


def setup(api):
    api.log("phone_native plugin loading — Termux:API skills")

    api.register_tool(
        name="phone_notify",
        description="Send a notification to the phone's notification tray. Use for alerts, task completion, or reminders.",
        parameters={"type": "object", "properties": {
            "title": {"type": "string", "default": "Lyra"},
            "text": {"type": "string", "description": "Notification message"},
        }, "required": ["text"]},
        handler=phone_notify,
        category="phone-native",
    )
    api.register_tool(
        name="phone_speak",
        description="Speak text aloud using the phone's text-to-speech voice.",
        parameters={"type": "object", "properties": {
            "text": {"type": "string", "description": "Text to speak aloud"},
        }, "required": ["text"]},
        handler=phone_speak,
        category="phone-native",
    )
    api.register_tool(
        name="phone_clipboard_get",
        description="Read the current clipboard contents on the phone.",
        parameters={"type": "object", "properties": {}},
        handler=phone_clipboard_get,
        category="phone-native",
    )
    api.register_tool(
        name="phone_clipboard_set",
        description="Copy text to the phone clipboard.",
        parameters={"type": "object", "properties": {
            "text": {"type": "string"},
        }, "required": ["text"]},
        handler=phone_clipboard_set,
        category="phone-native",
    )
    api.register_tool(
        name="phone_battery",
        description="Get battery status: charge level, charging state, temperature, health.",
        parameters={"type": "object", "properties": {}},
        handler=phone_battery,
        category="phone-native",
    )
    api.register_tool(
        name="phone_location",
        description="Get the current GPS location. provider='gps' is accurate but slow; provider='network' is fast.",
        parameters={"type": "object", "properties": {
            "provider": {"type": "string", "enum": ["gps", "network"], "default": "network"},
        }},
        handler=phone_location,
        category="phone-native",
    )
    api.register_tool(
        name="phone_flashlight",
        description="Turn the phone's flashlight (LED torch) on or off.",
        parameters={"type": "object", "properties": {
            "on": {"type": "boolean", "default": True},
        }},
        handler=phone_flashlight,
        category="phone-native",
    )
    api.register_tool(
        name="phone_volume",
        description="Set the phone volume (0-100) for a stream: music, ring, notification, alarm.",
        parameters={"type": "object", "properties": {
            "percent": {"type": "integer"},
            "stream": {"type": "string", "enum": ["music", "ring", "notification", "alarm"], "default": "music"},
        }, "required": ["percent"]},
        handler=phone_volume,
        category="phone-native",
    )
    api.register_tool(
        name="phone_wifi_info",
        description="Get current wifi connection details (SSID, link speed, signal strength).",
        parameters={"type": "object", "properties": {}},
        handler=phone_wifi_info,
        category="phone-native",
    )
    api.register_tool(
        name="phone_device_info",
        description="Get device info: Android version, model, memory, and free storage.",
        parameters={"type": "object", "properties": {}},
        handler=phone_device_info,
        category="phone-native",
    )

    api.log(f"phone_native registered {len(api._tools_added)} tools")


def teardown():
    pass
