"""Device Control Skill — screen capture, webcam, ADB phone operations.

Implements Hermes/ClosePaw-style device control:
  - screen_capture  → grab a screenshot of the current screen
  - webcam_capture  → grab a frame from the webcam
  - send_sms        → send SMS via ADB-connected Android
  - get_contacts    → list phone contacts via ADB
  - take_photo      → trigger the phone's camera via ADB

Each capability degrades gracefully when the underlying hardware or
permission isn't available (returns a clear error rather than crashing).
"""

from __future__ import annotations

import base64
import json
import logging
import os
import shutil
import subprocess
import sys
from typing import Any, Dict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from skills import BaseSkill

logger = logging.getLogger(__name__)


class DeviceControlSkill(BaseSkill):
    """Hermes/ClosePaw-style device control."""

    def __init__(self):
        super().__init__(
            name="device_control",
            category="media",
            capabilities=[
                "screen_capture", "webcam_capture",
                "send_sms", "get_contacts", "take_photo",
            ],
        )

    def init(self) -> bool:
        return True

    def shutdown(self) -> bool:
        return True

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if capability == "screen_capture":
                return self._screen_capture(params)
            elif capability == "webcam_capture":
                return self._webcam_capture(params)
            elif capability == "send_sms":
                return self._send_sms(params)
            elif capability == "get_contacts":
                return self._get_contacts(params)
            elif capability == "take_photo":
                return self._take_photo(params)
            return {"success": False, "error": f"unknown capability: {capability}"}
        except Exception as e:
            logger.exception("DeviceControl.execute failed for %s", capability)
            return {"success": False, "error": str(e), "capability": capability}

    # ─── Screen capture ────────────────────────────────────────────
    def _screen_capture(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Grab a screenshot via pyautogui → PIL.ImageGrab fallback."""
        save_path = params.get("save_path")
        # Try pyautogui first
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            if save_path:
                screenshot.save(save_path)
                return {"success": True, "path": save_path, "size": os.path.getsize(save_path)}
            # Return base64 instead
            from io import BytesIO
            buf = BytesIO()
            screenshot.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            return {"success": True, "format": "png", "base64": b64[:200] + "...", "size": len(b64)}
        except ImportError:
            pass
        # Fallback: PIL.ImageGrab (works on macOS + Windows)
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            if save_path:
                screenshot.save(save_path)
                return {"success": True, "path": save_path, "size": os.path.getsize(save_path), "backend": "PIL"}
            from io import BytesIO
            buf = BytesIO()
            screenshot.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            return {"success": True, "format": "png", "base64": b64[:200] + "...", "size": len(b64), "backend": "PIL"}
        except ImportError:
            return {"success": False, "error": "pyautogui and Pillow not installed (pip install pyautogui pillow)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Webcam capture ────────────────────────────────────────────
    def _webcam_capture(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Capture a frame from the webcam via OpenCV."""
        save_path = params.get("save_path")
        camera_index = int(params.get("camera_index", 0))
        try:
            import cv2
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                return {"success": False, "error": f"could not open camera {camera_index}"}
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return {"success": False, "error": "failed to read frame from camera"}
            if save_path:
                cv2.imwrite(save_path, frame)
                return {"success": True, "path": save_path, "size": os.path.getsize(save_path)}
            _, buf = cv2.imencode(".png", frame)
            b64 = base64.b64encode(buf.tobytes()).decode("ascii")
            return {"success": True, "format": "png", "base64": b64[:200] + "...", "size": len(b64)}
        except ImportError:
            return {"success": False, "error": "opencv-python not installed (pip install opencv-python)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── ADB phone operations ──────────────────────────────────────
    def _adb(self, args: list, timeout: int = 30) -> tuple:
        """Run an ADB command. Returns (returncode, stdout, stderr)."""
        if not shutil.which("adb"):
            return 127, "", "adb binary not found in PATH"
        try:
            r = subprocess.run(["adb"] + args, capture_output=True, text=True, timeout=timeout)
            return r.returncode, r.stdout, r.stderr
        except subprocess.TimeoutExpired:
            return 124, "", "adb command timed out"
        except Exception as e:
            return 1, "", str(e)

    def _send_sms(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send an SMS via ADB. Requires PHONE_BRIDGE_ENABLED=true + ADB device."""
        phone = params.get("phone_number") or params.get("phone")
        message = params.get("message") or params.get("text")
        if not phone or not message:
            return {"success": False, "error": "phone_number and message required"}
        if not os.environ.get("PHONE_BRIDGE_ENABLED", "False").lower() == "true":
            return {"success": False, "error": "PHONE_BRIDGE_ENABLED not set to true (safety guard)"}
        # Use ADB to compose + send the SMS via intent
        rc, out, err = self._adb([
            "shell", "am", "start", "-a", "android.intent.action.SENDTO",
            "-d", f"sms:{phone}", "--es", "sms_body", message, "--ez", "exit_on_sent", "true",
        ])
        if rc != 0:
            return {"success": False, "error": f"adb failed: {err or out}"}
        return {"success": True, "phone": phone, "message": message[:80]}

    def _get_contacts(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List phone contacts via ADB content provider."""
        if not os.environ.get("PHONE_BRIDGE_ENABLED", "False").lower() == "true":
            return {"success": False, "error": "PHONE_BRIDGE_ENABLED not set to true (safety guard)"}
        limit = int(params.get("limit", 50))
        rc, out, err = self._adb([
            "shell", "content", "query",
            "--uri", "content://com.android.contacts/data/phones",
            "--projection", "display_name:data1",
        ])
        if rc != 0:
            return {"success": False, "error": f"adb failed: {err or out}"}
        contacts = []
        for line in out.strip().split("\n")[:limit]:
            if "display_name=" in line:
                parts = line.split("display_name=")[1].split(" data1=")
                name = parts[0].strip() if parts else ""
                number = parts[1].strip() if len(parts) > 1 else ""
                contacts.append({"name": name, "number": number})
        return {"success": True, "count": len(contacts), "contacts": contacts}

    def _take_photo(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger the phone's camera via ADB and pull the photo."""
        if not os.environ.get("PHONE_BRIDGE_ENABLED", "False").lower() == "true":
            return {"success": False, "error": "PHONE_BRIDGE_ENABLED not set to true (safety guard)"}
        save_path = params.get("save_path", "/tmp/iris-photo.jpg")
        # Open camera app
        rc, out, err = self._adb([
            "shell", "am", "start", "-a", "android.media.action.STILL_IMAGE_CAMERA"
        ])
        if rc != 0:
            return {"success": False, "error": f"could not open camera: {err}"}
        # Wait for the user to take the photo (camera requires manual trigger)
        import time
        time.sleep(3)
        # Pull the most recent photo from DCIM
        rc, out, err = self._adb([
            "shell", "ls", "-t", "/sdcard/DCIM/Camera/"
        ])
        if rc != 0 or not out.strip():
            return {"success": False, "error": "no photos found in /sdcard/DCIM/Camera/"}
        latest = out.strip().split("\n")[0]
        rc, out, err = self._adb(["pull", f"/sdcard/DCIM/Camera/{latest}", save_path])
        if rc != 0:
            return {"success": False, "error": f"could not pull photo: {err}"}
        return {"success": True, "path": save_path, "size": os.path.getsize(save_path)}
