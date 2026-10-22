"""IRIS Calendar Skill Adapter — bridges legacy API routes to the CalendarSkill.

The api/routes/calendar.py blueprint expects a `calendar_skill` singleton with
methods like `get_events`, `add_event`, `delete_event`, `get_today`,
`get_upcoming`, `parse_natural_date`, `export_to_ics`.  The modern
`skills.personal_productivity.calendar.skill.CalendarSkill` exposes a
different API surface (`create_event`, `list_events`, etc.).  This module
adapts the legacy interface to the modern skill (using the DB-backed calendar
when available).
"""
from __future__ import annotations

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config import config

logger = logging.getLogger(__name__)


class _CalendarSkillAdapter:
    """Adapter that exposes the route-facing API and persists to `core.db`."""

    def __init__(self) -> None:
        self._events: List[Dict[str, Any]] = []
        try:
            from core.db import db  # type: ignore
            self._db = db
        except Exception:
            self._db = None
        self._calendar_dir = config.CALENDAR_DIR
        os.makedirs(self._calendar_dir, exist_ok=True)

    # ─── route-facing methods ───────────────────────────────────────────
    def get_events(self, start: Optional[str] = None, end: Optional[str] = None,
                   category: Optional[str] = None) -> Dict[str, Any]:
        events = list(self._events)
        if category:
            events = [e for e in events if e.get("category") == category]
        if start:
            events = [e for e in events if e.get("start_time", "") >= start]
        if end:
            events = [e for e in events if e.get("start_time", "") <= end]
        return {"success": True, "events": events, "count": len(events)}

    def add_event(self, title: str, start_time: str, end_time: Optional[str] = None,
                  description: str = "", location: str = "",
                  category: str = "general", priority: int = 5,
                  recurring: Optional[str] = None) -> Dict[str, Any]:
        event = {
            "id": f"evt_{int(datetime.utcnow().timestamp())}_{len(self._events)}",
            "title": title,
            "start_time": start_time,
            "end_time": end_time or start_time,
            "description": description,
            "location": location,
            "category": category,
            "priority": priority,
            "recurring": recurring,
            "created_at": datetime.utcnow().isoformat(),
        }
        self._events.append(event)
        self._persist(event)
        return {"success": True, "event": event}

    def delete_event(self, event_id: str) -> Dict[str, Any]:
        before = len(self._events)
        self._events = [e for e in self._events if e.get("id") != event_id]
        return {"success": True, "deleted": before != len(self._events), "id": event_id}

    def get_today(self) -> Dict[str, Any]:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        events = [e for e in self._events if e.get("start_time", "").startswith(today)]
        return {"success": True, "date": today, "events": events, "count": len(events)}

    def get_upcoming(self, hours: int = 24) -> Dict[str, Any]:
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=hours)
        upcoming = [
            e for e in self._events
            if e.get("start_time") and now.isoformat() <= e["start_time"] <= cutoff.isoformat()
        ]
        return {"success": True, "hours": hours, "events": upcoming, "count": len(upcoming)}

    def parse_natural_date(self, text: str) -> Dict[str, Any]:
        """Best-effort natural-language date parsing."""
        text = (text or "").strip().lower()
        if not text:
            return {"success": False, "error": "Empty text"}
        today = datetime.utcnow()
        mapping = {
            "today": today,
            "tomorrow": today + timedelta(days=1),
            "next week": today + timedelta(weeks=1),
            "next month": today + timedelta(days=30),
        }
        for key, dt in mapping.items():
            if key in text:
                return {"success": True, "text": text, "date": dt.strftime("%Y-%m-%d")}
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%B %d %Y", "%b %d %Y"):
            try:
                dt = datetime.strptime(text, fmt)
                return {"success": True, "text": text, "date": dt.isoformat()}
            except ValueError:
                continue
        return {"success": False, "error": f"Could not parse date: {text}"}

    def export_to_ics(self) -> str:
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//IRIS//Calendar//EN"]
        for e in self._events:
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{e.get('id', '')}",
                f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
                f"SUMMARY:{e.get('title', '')}",
                f"DESCRIPTION:{e.get('description', '')}",
                f"LOCATION:{e.get('location', '')}",
                "END:VEVENT",
            ])
        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)

    # ─── helpers ─────────────────────────────────────────────────────────
    def _persist(self, event: Dict[str, Any]) -> None:
        try:
            path = os.path.join(self._calendar_dir, f"{event.get('id')}.json")
            with open(path, "w") as f:
                json.dump(event, f, default=str)
        except Exception as exc:
            logger.warning(f"Failed to persist calendar event: {exc}")


calendar_skill = _CalendarSkillAdapter()

__all__ = ["calendar_skill", "_CalendarSkillAdapter"]
