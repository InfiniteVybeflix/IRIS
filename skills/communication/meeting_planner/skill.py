"""Meeting Planner Skill — Coordinate meetings across time zones."""
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from skills import BaseSkill
logger = logging.getLogger(__name__)

class MeetingPlannerSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="meeting_planner", category="communication", capabilities=["meeting_planner"])
        self._timezones = {"UTC": 0, "London": 0, "Nairobi": 3, "New_York": -5, "Tokyo": 9, "Sydney": 11}

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "find_slot")
        if method == "find_slot": return self.find_slot(params)
        elif method == "convert_time": return self.convert_time(params)
        return {"error": f"Unknown method: {method}"}

    def find_slot(self, params: Dict[str, Any]) -> Dict[str, Any]:
        attendees = params.get("attendees", [])
        duration = params.get("duration_minutes", 60)
        business_hours = range(9, 18)
        slots = []
        for hour in business_hours:
            conversions = []
            valid = True
            base_time = datetime.utcnow().replace(hour=hour, minute=0, second=0, microsecond=0)
            for att in attendees:
                tz_offset = self._timezones.get(att.get("timezone", "UTC"), 0)
                local = base_time + timedelta(hours=tz_offset)
                local_hour = local.hour
                if not (9 <= local_hour < 18):
                    valid = False
                    break
                conversions.append({"attendee": att.get("name", ""), "local_time": local.strftime("%H:%M"), "timezone": att.get("timezone", "UTC")})
            if valid:
                slots.append({"utc_time": base_time.strftime("%H:%M"), "local_times": conversions})
        return {"success": True, "suggested_slots": slots[:5], "duration_minutes": duration}

    def convert_time(self, params: Dict[str, Any]) -> Dict[str, Any]:
        time_str = params.get("time", "")
        from_tz = params.get("from", "UTC")
        to_tz = params.get("to", "UTC")
        diff = self._timezones.get(to_tz, 0) - self._timezones.get(from_tz, 0)
        return {"success": True, "from": from_tz, "to": to_tz, "offset_hours": diff}
