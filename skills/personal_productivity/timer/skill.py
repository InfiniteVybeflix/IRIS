"""Timer Skill — Countdown timer with multiple named timers."""
import logging
import time
import threading
from typing import Dict, Any
from datetime import datetime, timedelta
from skills import BaseSkill
logger = logging.getLogger(__name__)

class TimerSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="timer", category="personal_productivity", capabilities=["timer"])
        self._timers: Dict[str, Dict[str, Any]] = {}

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "start")
        if method == "start": return self.start_timer(params)
        elif method == "status": return self.timer_status(params)
        elif method == "cancel": return self.cancel_timer(params)
        return {"error": f"Unknown method: {method}"}

    def start_timer(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tid = params.get("timer_id", f"timer_{len(self._timers)+1}")
        seconds = params.get("seconds", params.get("minutes", 0) * 60)
        end_time = datetime.utcnow() + timedelta(seconds=seconds)
        self._timers[tid] = {"id": tid, "duration": seconds, "end_time": end_time.isoformat(), "remaining": seconds, "active": True}
        return {"success": True, "timer": self._timers[tid]}

    def timer_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tid = params.get("timer_id", "")
        t = self._timers.get(tid)
        if not t: return {"success": False, "error": "Timer not found"}
        end = datetime.fromisoformat(t["end_time"])
        remaining = max(0, int((end - datetime.utcnow()).total_seconds()))
        t["remaining"] = remaining
        t["active"] = remaining > 0
        return {"success": True, "timer": t, "remaining_seconds": remaining, "remaining_formatted": f"{remaining//3600:02d}:{(remaining%3600)//60:02d}:{remaining%60:02d}"}

    def cancel_timer(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tid = params.get("timer_id", "")
        removed = self._timers.pop(tid, None)
        return {"success": True, "cancelled": removed is not None}
