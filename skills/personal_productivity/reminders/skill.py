"""Reminders Skill — Time-based and location-based reminders."""
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from skills import BaseSkill
logger = logging.getLogger(__name__)

class RemindersSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="reminders", category="personal_productivity", capabilities=["reminders"])
        self._reminders: List[Dict[str, Any]] = []

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "set")
        if method == "set": return self.set_reminder(params)
        elif method == "list": return self.list_reminders(params)
        elif method == "cancel": return self.cancel_reminder(params)
        elif method == "snooze": return self.snooze(params)
        return {"error": f"Unknown method: {method}"}

    def set_reminder(self, params: Dict[str, Any]) -> Dict[str, Any]:
        r = {"id": len(self._reminders)+1, "title": params.get("title", ""), "time": params.get("time", ""), "recurring": params.get("recurring", ""), "priority": params.get("priority", "normal"), "created_at": datetime.utcnow().isoformat()}
        self._reminders.append(r)
        return {"success": True, "reminder": r}

    def list_reminders(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"success": True, "reminders": self._reminders, "count": len(self._reminders)}

    def cancel_reminder(self, params: Dict[str, Any]) -> Dict[str, Any]:
        rid = params.get("reminder_id", 0)
        self._reminders = [r for r in self._reminders if r["id"] != rid]
        return {"success": True, "cancelled": True}

    def snooze(self, params: Dict[str, Any]) -> Dict[str, Any]:
        rid = params.get("reminder_id", 0)
        mins = params.get("minutes", 10)
        for r in self._reminders:
            if r["id"] == rid:
                new_time = datetime.utcnow() + timedelta(minutes=mins)
                r["time"] = new_time.isoformat()
                return {"success": True, "new_time": r["time"]}
        return {"success": False, "error": "Reminder not found"}
