"""Calendar Skill — Event scheduling, meeting planning, availability checking."""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from skills import BaseSkill

logger = logging.getLogger(__name__)


class CalendarSkill(BaseSkill):
    """Full calendar management with events, scheduling, and meeting planning."""

    def __init__(self):
        super().__init__(name="calendar", category="personal_productivity", capabilities=["calendar"])
        self._events: List[Dict[str, Any]] = []

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "create_event")
        if method == "create_event":
            return self.create_event(params)
        elif method == "list_events":
            return self.list_events(params)
        elif method == "delete_event":
            return self.delete_event(params)
        elif method == "check_availability":
            return self.check_availability(params)
        elif method == "schedule_meeting":
            return self.schedule_meeting(params)
        elif method == "find_free_slots":
            return self.find_free_slots(params)
        return {"error": f"Unknown method: {method}"}

    def create_event(self, params: Dict[str, Any]) -> Dict[str, Any]:
        event = {
            "id": len(self._events) + 1,
            "title": params.get("title", "Untitled Event"),
            "start": params.get("start", datetime.utcnow().isoformat()),
            "end": params.get("end", ""),
            "description": params.get("description", ""),
            "location": params.get("location", ""),
            "attendees": params.get("attendees", []),
            "recurring": params.get("recurring", False),
            "reminder_minutes": params.get("reminder_minutes", 15),
            "created_at": datetime.utcnow().isoformat(),
        }
        if not event["end"]:
            start_dt = datetime.fromisoformat(event["start"].replace('Z', '+00:00')) if event["start"] else datetime.utcnow()
            event["end"] = (start_dt + timedelta(hours=1)).isoformat()
        self._events.append(event)
        return {"success": True, "event": event}

    def list_events(self, params: Dict[str, Any]) -> Dict[str, Any]:
        date_filter = params.get("date", "")
        events = self._events
        if date_filter:
            events = [e for e in events if date_filter in e.get("start", "")]
        return {"success": True, "events": events, "count": len(events)}

    def delete_event(self, params: Dict[str, Any]) -> Dict[str, Any]:
        event_id = params.get("event_id", 0)
        self._events = [e for e in self._events if e.get("id") != event_id]
        return {"success": True, "deleted": True}

    def check_availability(self, params: Dict[str, Any]) -> Dict[str, Any]:
        check_start = params.get("start", "")
        check_end = params.get("end", "")
        conflicts = [e for e in self._events if e["start"] < check_end and e["end"] > check_start]
        return {"success": True, "available": len(conflicts) == 0, "conflicts": conflicts}

    def schedule_meeting(self, params: Dict[str, Any]) -> Dict[str, Any]:
        title = params.get("title", "Meeting")
        duration_minutes = params.get("duration_minutes", 30)
        attendees = params.get("attendees", [])
        result = self.find_free_slots(params)
        slots = result.get("free_slots", [])
        if slots:
            slot = slots[0]
            start = datetime.fromisoformat(slot["start"])
            end = start + timedelta(minutes=duration_minutes)
            return self.create_event({"title": title, "start": start.isoformat(), "end": end.isoformat(), "attendees": attendees, "description": params.get("description", "")})
        return {"success": False, "error": "No free slots found"}

    def find_free_slots(self, params: Dict[str, Any]) -> Dict[str, Any]:
        date_str = params.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
        slot_duration = params.get("slot_duration_minutes", 30)
        day_start = datetime.strptime(f"{date_str} 09:00", "%Y-%m-%d %H:%M")
        day_end = datetime.strptime(f"{date_str} 17:00", "%Y-%m-%d %H:%M")
        busy = [(datetime.fromisoformat(e["start"].replace('Z', '+00:00').replace('+00:00', '')), datetime.fromisoformat(e["end"].replace('Z', '+00:00').replace('+00:00', ''))) for e in self._events if date_str in e.get("start", "")]
        free_slots = []
        current = day_start
        for start, end in sorted(busy):
            if current < start and (start - current).total_seconds() / 60 >= slot_duration:
                free_slots.append({"start": current.isoformat(), "end": start.isoformat(), "duration_minutes": int((start - current).total_seconds() / 60)})
            current = max(current, end)
        if current < day_end and (day_end - current).total_seconds() / 60 >= slot_duration:
            free_slots.append({"start": current.isoformat(), "end": day_end.isoformat(), "duration_minutes": int((day_end - current).total_seconds() / 60)})
        return {"success": True, "date": date_str, "free_slots": free_slots}
