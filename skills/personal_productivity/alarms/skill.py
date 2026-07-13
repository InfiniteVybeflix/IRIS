"""Alarms Skill — One-time and recurring alarms."""
import logging
import threading
from typing import Dict, Any, List
from datetime import datetime, timedelta
from skills import BaseSkill
logger = logging.getLogger(__name__)

class AlarmsSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="alarms", category="personal_productivity", capabilities=["alarms"])
        self._alarms: Dict[str, Dict[str, Any]] = {}

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "set")
        if method == "set": return self.set_alarm(params)
        elif method == "list": return self.list_alarms(params)
        elif method == "cancel": return self.cancel_alarm(params)
        return {"error": f"Unknown method: {method}"}

    def set_alarm(self, params: Dict[str, Any]) -> Dict[str, Any]:
        aid = params.get("alarm_id", f"alarm_{len(self._alarms)+1}")
        self._alarms[aid] = {"id": aid, "time": params.get("time", ""), "label": params.get("label", ""), "sound": params.get("sound", "default"), "recurring": params.get("recurring", []), "active": True}
        return {"success": True, "alarm": self._alarms[aid]}

    def list_alarms(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"success": True, "alarms": list(self._alarms.values()), "count": len(self._alarms)}

    def cancel_alarm(self, params: Dict[str, Any]) -> Dict[str, Any]:
        aid = params.get("alarm_id", "")
        removed = self._alarms.pop(aid, None)
        return {"success": True, "cancelled": removed is not None}
