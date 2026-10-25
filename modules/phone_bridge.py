"""IRIS v1 Phone Bridge — Android Control via ADB"""
import os
import subprocess
import json
from typing import Dict, List, Optional
from config import config

class PhoneBridge:
    """
    Control Android phone via ADB:
    - Contacts (list, search, call)
    - Messages (read, send)
    - Torch (on/off)
    - Settings (toggle WiFi, Bluetooth, etc.)
    - Notifications (read, dismiss)
    - Camera (open, take photo)
    - Screen (screenshot, record)
    - Free-form ADB command console (guided by the connect guide in the UI)
    """

    def __init__(self):
        self.device_id = config.ADB_DEVICE_ID
        self.enabled = config.PHONE_BRIDGE_ENABLED
        self.adb_available = self._check_adb()

    def _check_adb(self) -> bool:
        """Check if the adb binary exists. Device presence is checked per-call."""
        try:
            result = subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    def _adb(self, command: List[str], timeout: int = 30) -> Dict:
        """Execute ADB command."""
        if not self.adb_available:
            return {"success": False, "error": (
                "ADB is not installed on the host running IRIS. "
                "Install it (e.g. `sudo apt install adb` or platform-tools) and retry. "
                "On Vercel's serverless runtime ADB cannot run — self-host for phone control.")}
        if not self.enabled:
            return {"success": False, "error": "Phone bridge is disabled — set PHONE_BRIDGE_ENABLED=true"}
        try:
            cmd = ["adb"]
            if self.device_id:
                cmd.extend(["-s", self.device_id])
            cmd.extend(command)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            out = {
                "success": result.returncode == 0,
                "stdout": result.stdout[:8000],
                "stderr": result.stderr[:4000],
                "returncode": result.returncode
            }
            if result.returncode != 0 and result.stderr:
                out["error"] = result.stderr.strip()[:1000]
            return out
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"ADB command timed out after {timeout}s"}
        except FileNotFoundError:
            return {"success": False, "error": "ADB binary not found on PATH"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === CONNECTION / CONSOLE ===
    def list_devices(self) -> Dict:
        """List devices visible to adb (`adb devices -l`), parsed."""
        raw = self._adb(["devices", "-l"], timeout=10)
        if not raw.get("success") and "error" in raw:
            return raw
        devices = []
        for line in (raw.get("stdout") or "").splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            entry = {"id": parts[0], "state": parts[1] if len(parts) > 1 else "unknown"}
            for p in parts[2:]:
                if ":" in p:
                    k, _, v = p.partition(":")
                    entry[k] = v
            devices.append(entry)
        return {"success": True, "devices": devices, "count": len(devices),
                "raw": raw.get("stdout", "")}

    def connect(self, address: str) -> Dict:
        """Connect to a device over the network (`adb connect ip:5555`)."""
        address = (address or "").strip()
        if not address:
            return {"success": False, "error": "Address required — e.g. 192.168.1.20:5555"}
        if not all(c.isdigit() or c in ".:" for c in address):
            return {"success": False, "error": "Address must look like ip:port (e.g. 192.168.1.20:5555)"}
        res = self._adb(["connect", address], timeout=15)
        return {**res, "address": address}

    # Patterns that could destroy data — refused instead of executed.
    _BLOCKED = ("mkfs", "dd if=", "fastboot", "rm -rf /", ":(){", "wipe", "flash_image")

    def run_command(self, user_command: str) -> Dict:
        """Run a user-supplied ADB command from the Phone console.

        The command is everything AFTER the `adb` binary name (a leading
        `adb ` is accepted and stripped). Output is captured verbatim —
        nothing is simulated. Destructive patterns are refused explicitly.
        """
        cmd = (user_command or "").strip()
        if not cmd:
            return {"success": False, "error": "Type a command first — e.g. shell dumpsys battery"}
        if cmd.lower().startswith("adb "):
            cmd = cmd[4:].strip()
        low = cmd.lower()
        for pattern in self._BLOCKED:
            if pattern in low:
                return {"success": False,
                        "error": f"Refused: “{pattern}” is on the destructive-command blocklist."}
        parts = cmd.split()
        res = self._adb(parts, timeout=60)
        return {**res, "command": f"adb {cmd}"}

    # === CONTACTS ===
    def get_contacts(self) -> Dict:
        """Get all contacts from phone."""
        result = self._adb([
            "shell", "content", "query", "--uri", "content://com.android.contacts/data/phones",
            "--projection", "display_name:number"
        ])
        if result["success"]:
            contacts = []
            for line in result["stdout"].strip().split("\n"):
                if "display_name=" in line:
                    parts = line.split(", ")
                    name = parts[0].split("=")[1] if "=" in parts[0] else "Unknown"
                    number = parts[1].split("=")[1] if len(parts) > 1 and "=" in parts[1] else ""
                    contacts.append({"name": name, "number": number})
            return {"success": True, "contacts": contacts, "count": len(contacts)}
        return result

    def search_contacts(self, query: str) -> Dict:
        """Search contacts by name or number."""
        all_contacts = self.get_contacts()
        if not all_contacts.get("success"):
            return all_contacts
        filtered = [c for c in all_contacts["contacts"] if query.lower() in c["name"].lower() or query in c["number"]]
        return {"success": True, "contacts": filtered, "count": len(filtered)}

    def call_contact(self, name_or_number: str) -> Dict:
        """Initiate a phone call."""
        return self._adb(["shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{name_or_number}"])

    # === MESSAGES ===
    def get_messages(self, limit: int = 20) -> Dict:
        """Read SMS messages."""
        result = self._adb([
            "shell", "content", "query", "--uri", "content://sms/inbox",
            "--projection", "address:body:date",
            "--limit", str(limit)
        ])
        if result["success"]:
            messages = []
            for line in result["stdout"].strip().split("\n"):
                if "address=" in line:
                    parts = line.split(", ")
                    msg = {}
                    for part in parts:
                        if "=" in part:
                            key, val = part.split("=", 1)
                            msg[key.strip()] = val.strip()
                    messages.append(msg)
            return {"success": True, "messages": messages, "count": len(messages)}
        return result

    def send_message(self, number: str, text: str) -> Dict:
        """Send SMS message."""
        return self._adb([
            "shell", "am", "start", "-a", "android.intent.action.SENDTO",
            "-d", f"sms:{number}", "--es", "sms_body", text
        ])

    # === TORCH ===
    def torch(self, state: str = "toggle") -> Dict:
        """Control flashlight. state: on, off, toggle."""
        if state == "toggle":
            return self._adb(["shell", "input", "keyevent", "KEYCODE_CAMERA"])
        elif state == "on":
            return self._adb(["shell", "settings", "put", "system", "screen_brightness", "255"])
        elif state == "off":
            return self._adb(["shell", "settings", "put", "system", "screen_brightness", "0"])
        return {"success": False, "error": "Invalid state. Use: on, off, toggle"}

    # === SETTINGS ===
    def toggle_wifi(self, state: str = "toggle") -> Dict:
        """Toggle WiFi."""
        if state == "on":
            return self._adb(["shell", "svc", "wifi", "enable"])
        elif state == "off":
            return self._adb(["shell", "svc", "wifi", "disable"])
        else:
            # Toggle: check current state first
            current = self._adb(["shell", "settings", "get", "global", "wifi_on"])
            new_state = "disable" if current.get("stdout", "").strip() == "1" else "enable"
            return self._adb(["shell", "svc", "wifi", new_state])

    def toggle_bluetooth(self, state: str = "toggle") -> Dict:
        """Toggle Bluetooth."""
        if state == "on":
            return self._adb(["shell", "svc", "bluetooth", "enable"])
        elif state == "off":
            return self._adb(["shell", "svc", "bluetooth", "disable"])
        else:
            current = self._adb(["shell", "settings", "get", "global", "bluetooth_on"])
            new_state = "disable" if current.get("stdout", "").strip() == "1" else "enable"
            return self._adb(["shell", "svc", "bluetooth", new_state])

    def get_battery(self) -> Dict:
        """Get battery status."""
        result = self._adb(["shell", "dumpsys", "battery"])
        if result["success"]:
            level = None
            status = None
            for line in result["stdout"].split("\n"):
                if "level:" in line:
                    level = int(line.split(":")[1].strip())
                if "status:" in line:
                    status = line.split(":")[1].strip()
            return {"success": True, "level": level, "status": status}
        return result

    # === NOTIFICATIONS ===
    def get_notifications(self) -> Dict:
        """Read notifications via dumpsys."""
        result = self._adb(["shell", "dumpsys", "notification", "--noshort"])
        if result["success"]:
            notifications = []
            current = {}
            for line in result["stdout"].split("\n"):
                if "NotificationRecord" in line:
                    if current:
                        notifications.append(current)
                    current = {"app": line.split("pkg=")[1].split()[0] if "pkg=" in line else "unknown"}
                elif "tickerText=" in line and current:
                    current["text"] = line.split("tickerText=")[1].strip()
                elif "postTime=" in line and current:
                    current["time"] = line.split("postTime=")[1].split()[0]
            if current:
                notifications.append(current)
            return {"success": True, "notifications": notifications[:20], "count": len(notifications)}
        return result

    def dismiss_notification(self, index: int = 0) -> Dict:
        """Dismiss notification by index (requires accessibility service in production)."""
        return {"success": False, "error": "Notification dismissal requires accessibility service. Use swipe gesture instead."}

    # === CAMERA ===
    def open_camera(self) -> Dict:
        """Open camera app."""
        return self._adb(["shell", "am", "start", "-a", "android.media.action.STILL_IMAGE_CAMERA"])

    def take_photo(self) -> Dict:
        """Take a photo (camera must be open)."""
        return self._adb(["shell", "input", "keyevent", "KEYCODE_CAMERA"])

    # === SCREEN ===
    def screenshot(self, save_path: str = None) -> Dict:
        """Take screenshot and pull to local."""
        if not save_path:
            save_path = os.path.join(config.UPLOADS_DIR, f"screenshot_{int(time.time())}.png")
        remote_path = "/sdcard/screenshot.png"
        cap = self._adb(["shell", "screencap", "-p", remote_path])
        if cap["success"]:
            pull = self._adb(["pull", remote_path, save_path])
            if pull["success"]:
                return {"success": True, "path": save_path}
        return cap

    def screen_record(self, duration: int = 10, save_path: str = None) -> Dict:
        """Record screen for N seconds."""
        if not save_path:
            save_path = os.path.join(config.UPLOADS_DIR, f"screenrecord_{int(time.time())}.mp4")
        remote_path = "/sdcard/screenrecord.mp4"
        rec = self._adb(["shell", "screenrecord", "--time-limit", str(duration), remote_path])
        if rec["success"]:
            pull = self._adb(["pull", remote_path, save_path])
            if pull["success"]:
                return {"success": True, "path": save_path, "duration": duration}
        return rec

    def get_device_info(self) -> Dict:
        """Get phone device info."""
        result = self._adb(["shell", "getprop"])
        if result["success"]:
            info = {}
            for line in result["stdout"].split("\n"):
                if "]: [" in line:
                    key = line.split("[")[1].split("]")[0]
                    val = line.split(": [")[1].rstrip("]")
                    info[key] = val
            return {"success": True, "info": {
                "model": info.get("ro.product.model", "Unknown"),
                "brand": info.get("ro.product.brand", "Unknown"),
                "android_version": info.get("ro.build.version.release", "Unknown"),
                "sdk": info.get("ro.build.version.sdk", "Unknown"),
            }}
        return result

# Singleton
phone_bridge = PhoneBridge()
