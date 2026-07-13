"""Screen Control Skill — Remote screen control and automation."""
import logging
from typing import Dict, Any
from skills import BaseSkill
logger = logging.getLogger(__name__)

class ScreenControlSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="screen_control", category="media", capabilities=["screen_control"])

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "click")
        if method == "click": return self.click(params)
        elif method == "type": return self.type_text(params)
        elif method == "screenshot": return self.screenshot(params)
        return {"error": f"Unknown method: {method}"}

    def click(self, params: Dict[str, Any]) -> Dict[str, Any]:
        x, y = params.get("x", 0), params.get("y", 0)
        try:
            import pyautogui
            pyautogui.click(x, y)
            return {"success": True, "action": "click", "x": x, "y": y}
        except ImportError:
            return {"success": False, "error": "pyautogui required. Install: pip install pyautogui"}

    def type_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text = params.get("text", "")
        try:
            import pyautogui
            pyautogui.typewrite(text)
            return {"success": True, "action": "type", "text": text[:50]}
        except ImportError:
            return {"success": False, "error": "pyautogui required"}

    def screenshot(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import pyautogui
            import io, base64
            img = pyautogui.screenshot()
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            b64 = base64.b64encode(buf.getvalue()).decode()
            return {"success": True, "base64": b64, "size": img.size}
        except ImportError:
            return {"success": False, "error": "pyautogui required"}
