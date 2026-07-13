"""Clock & World Time Skill — Current time, world clocks, time zones."""
import logging
from datetime import datetime
from typing import Dict, Any, List
from skills import BaseSkill
logger = logging.getLogger(__name__)

class ClockWorldtimeSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="clock_worldtime", category="utilities", capabilities=["clock_worldtime"])
        self._timezones = {
            "UTC": 0, "London": 0, "Paris": 1, "Berlin": 1, "Rome": 1, "Madrid": 1,
            "Cairo": 2, "Nairobi": 3, "Dubai": 4, "Mumbai": 5.5, "Bangkok": 7,
            "Singapore": 8, "Hong_Kong": 8, "Beijing": 8, "Tokyo": 9, "Sydney": 11,
            "Auckland": 13, "New_York": -5, "Chicago": -6, "Denver": -7,
            "Los_Angeles": -8, "Honolulu": -10,
        }

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "now")
        if method == "now": return self.now(params)
        elif method == "world_clock": return self.world_clock(params)
        elif method == "convert": return self.convert_time(params)
        return {"error": f"Unknown method: {method}"}

    def now(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tz = params.get("timezone", "UTC")
        offset = self._timezones.get(tz, 0)
        from datetime import timezone, timedelta
        tz_obj = timezone(timedelta(hours=offset))
        now = datetime.now(tz_obj)
        return {"success": True, "timezone": tz, "time": now.strftime("%Y-%m-%d %H:%M:%S"), "offset_hours": offset, "iso": now.isoformat()}

    def world_clock(self, params: Dict[str, Any]) -> Dict[str, Any]:
        cities = params.get("cities", ["New_York", "London", "Tokyo", "Nairobi"])
        clocks = []
        for city in cities:
            result = self.now({"timezone": city})
            if result["success"]:
                clocks.append({"city": city, "time": result["time"]})
        return {"success": True, "clocks": clocks}

    def convert_time(self, params: Dict[str, Any]) -> Dict[str, Any]:
        time_str = params.get("time", "")
        from_tz = params.get("from", "UTC")
        to_tz = params.get("to", "UTC")
        offset_from = self._timezones.get(from_tz, 0)
        offset_to = self._timezones.get(to_tz, 0)
        diff = offset_to - offset_from
        return {"success": True, "from": from_tz, "to": to_tz, "time_difference_hours": diff, "note": f"Add {diff} hours to convert from {from_tz} to {to_tz}"}
