"""Habit Tracker Skill — Track habits, streaks, and progress."""
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from skills import BaseSkill
logger = logging.getLogger(__name__)

class HabitTrackerSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="habit_tracker", category="personal_productivity", capabilities=["habit_tracker"])
        self._habits: Dict[str, Dict[str, Any]] = {}

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "create")
        if method == "create": return self.create_habit(params)
        elif method == "log": return self.log_entry(params)
        elif method == "status": return self.habit_status(params)
        elif method == "list": return self.list_habits(params)
        return {"error": f"Unknown method: {method}"}

    def create_habit(self, params: Dict[str, Any]) -> Dict[str, Any]:
        hid = params.get("habit_id", params.get("name", "").lower().replace(" ", "_"))
        self._habits[hid] = {"id": hid, "name": params.get("name", ""), "frequency": params.get("frequency", "daily"), "goal": params.get("goal", 1), "log": [], "streak": 0, "created_at": datetime.utcnow().isoformat()}
        return {"success": True, "habit": self._habits[hid]}

    def log_entry(self, params: Dict[str, Any]) -> Dict[str, Any]:
        hid = params.get("habit_id", "")
        h = self._habits.get(hid)
        if not h: return {"success": False, "error": "Habit not found"}
        h["log"].append(datetime.utcnow().strftime("%Y-%m-%d"))
        h["log"] = list(set(h["log"]))
        h["log"].sort()
        # Calculate streak
        streak = 0
        today = datetime.utcnow().date()
        for i in range(365):
            check = (today - timedelta(days=i)).isoformat()
            if check in h["log"]:
                streak += 1
            else:
                break
        h["streak"] = streak
        h["total_completions"] = len(h["log"])
        return {"success": True, "habit": h, "streak": streak}

    def habit_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        hid = params.get("habit_id", "")
        h = self._habits.get(hid)
        return {"success": True, "habit": h} if h else {"success": False, "error": "Habit not found"}

    def list_habits(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"success": True, "habits": list(self._habits.values()), "count": len(self._habits)}
