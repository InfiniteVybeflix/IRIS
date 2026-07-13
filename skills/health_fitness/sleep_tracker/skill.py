"""Sleep Tracker Skill — Track sleep duration, quality, patterns."""
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from skills import BaseSkill
logger = logging.getLogger(__name__)

class SleepTrackerSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="sleep_tracker", category="health_fitness", capabilities=["sleep_tracker"])
        self._records: List[Dict[str, Any]] = []

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "log")
        if method == "log": return self.log_sleep(params)
        elif method == "stats": return self.stats(params)
        return {"error": f"Unknown method: {method}"}

    def log_sleep(self, params: Dict[str, Any]) -> Dict[str, Any]:
        bed = params.get("bedtime", "")
        wake = params.get("wake_time", "")
        quality = params.get("quality", 5)
        try:
            bed_dt = datetime.fromisoformat(bed)
            wake_dt = datetime.fromisoformat(wake)
            duration_hours = (wake_dt - bed_dt).total_seconds() / 3600
            if duration_hours < 0:
                duration_hours += 24
        except Exception:
            duration_hours = params.get("duration_hours", 0)
        record = {"date": wake_dt.strftime("%Y-%m-%d") if 'wake_dt' in dir() else datetime.utcnow().strftime("%Y-%m-%d"), "bedtime": bed, "wake_time": wake, "duration_hours": round(duration_hours, 1), "quality": quality}
        self._records.append(record)
        return {"success": True, "record": record}

    def stats(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self._records: return {"success": True, "average_duration": 0, "average_quality": 0, "records": 0}
        avg_dur = sum(r["duration_hours"] for r in self._records) / len(self._records)
        avg_qual = sum(r["quality"] for r in self._records) / len(self._records)
        return {"success": True, "average_duration": round(avg_dur, 1), "average_quality": round(avg_qual, 1), "records": len(self._records)}
