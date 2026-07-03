"""IRIS Calendar Skill — Full implementation with reminders & notifications."""
import os
import re
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags
from skills._utils.storage import SkillStorage
from skills._utils.notifications import NotificationQueue

logger = logging.getLogger(__name__)


class CalendarSkill(BaseSkill):
    name = "calendar"
    display_name = "Calendar"
    description = "Full calendar management with events, reminders, recurring events, and natural language parsing."
    version = "2.0.0"
    category = "productivity"
    icon = "📅"
    uses_storage = True
    supports_background = True
    background_interval_seconds = 30

    capabilities = [
        SkillCapability(
            name="add_event",
            description="Create a new calendar event",
            input_schema={"title": "str", "start_time": "str (ISO or natural)", "end_time": "str (optional)", "description": "str", "location": "str", "category": "str", "priority": "int 1-10", "recurring": "str: daily|weekly|monthly|yearly"},
            output_schema={"event_id": "int", "title": "str", "start_time": "str"},
            tags=[CapabilityTags.CALENDAR],
        ),
        SkillCapability(
            name="list_events",
            description="List events in a date range",
            input_schema={"start": "str (ISO)", "end": "str (ISO)", "category": "str"},
            output_schema={"events": "list", "count": "int"},
            tags=[CapabilityTags.CALENDAR],
        ),
        SkillCapability(
            name="today",
            description="Get today's events",
            input_schema={},
            output_schema={"events": "list", "count": "int"},
            tags=[CapabilityTags.CALENDAR],
        ),
        SkillCapability(
            name="upcoming",
            description="Get upcoming events within N hours",
            input_schema={"hours": "int (default 24)"},
            output_schema={"events": "list", "count": "int"},
            tags=[CapabilityTags.CALENDAR],
        ),
        SkillCapability(
            name="edit_event",
            description="Edit an existing event",
            input_schema={"event_id": "int", "title": "str", "start_time": "str", "end_time": "str", "description": "str", "location": "str", "category": "str", "priority": "int"},
            output_schema={"success": "bool", "message": "str"},
            tags=[CapabilityTags.CALENDAR],
        ),
        SkillCapability(
            name="delete_event",
            description="Delete an event by ID",
            input_schema={"event_id": "int"},
            output_schema={"success": "bool", "message": "str"},
            tags=[CapabilityTags.CALENDAR],
        ),
        SkillCapability(
            name="parse_natural",
            description="Parse natural language date/time",
            input_schema={"text": "str"},
            output_schema={"parsed_date": "str (ISO)", "original": "str"},
            tags=[CapabilityTags.CALENDAR],
        ),
        SkillCapability(
            name="check_reminders",
            description="Check for events needing notification",
            input_schema={},
            output_schema={"notifications": "list", "count": "int"},
            supports_background=True,
            tags=[CapabilityTags.CALENDAR, CapabilityTags.REMINDERS],
        ),
        SkillCapability(
            name="export_ics",
            description="Export events to ICS format",
            input_schema={},
            output_schema={"ics_content": "str"},
            tags=[CapabilityTags.CALENDAR],
        ),
        SkillCapability(
            name="mark_completed",
            description="Mark an event as completed",
            input_schema={"event_id": "int"},
            output_schema={"success": "bool"},
            tags=[CapabilityTags.CALENDAR],
        ),
    ]

    def __init__(self):
        super().__init__()
        self.storage = SkillStorage(self.name)
        self.notifications = NotificationQueue()
        self._reminder_window_minutes = 5

    def execute(self, request: SkillRequest) -> SkillResult:
        intent = request.intent.lower()
        params = request.params

        if intent in ("add_event", "create_event", "calendar_add"):
            return self._add_event(params)
        elif intent in ("list_events", "get_events", "calendar_list"):
            return self._list_events(params)
        elif intent in ("today", "calendar_today"):
            return self._today()
        elif intent in ("upcoming", "calendar_upcoming"):
            return self._upcoming(params)
        elif intent in ("edit_event", "update_event"):
            return self._edit_event(params)
        elif intent in ("delete_event", "remove_event"):
            return self._delete_event(params)
        elif intent in ("parse_natural", "parse_date", "calendar_parse"):
            return self._parse_natural(params)
        elif intent in ("check_reminders", "reminders"):
            return self._check_reminders()
        elif intent in ("export_ics", "calendar_export"):
            return self._export_ics(params)
        elif intent in ("mark_completed", "complete_event"):
            return self._mark_completed(params)
        else:
            return SkillResult.fail(error=f"Unknown calendar intent: {intent}")

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        keywords = ["calendar", "event", "schedule", "appointment", "meeting", "remind", "reminder", "upcoming", "today"]
        if any(k in intent for k in keywords):
            return 0.95
        return super().can_handle(request)

    def background_tick(self) -> List[SkillResult]:
        """Check for upcoming events and push notifications."""
        results = []
        now = datetime.now()
        window = now + timedelta(minutes=self._reminder_window_minutes)

        events = self.storage.event_list(
            start=now.isoformat(),
            end=window.isoformat()
        )

        for event in events:
            if not event.get("notified") and not event.get("completed"):
                self.notifications.push(
                    title=f"📅 {event['title']}",
                    message=f"Starting at {event['start_time']}" + (f" at {event['location']}" if event.get('location') else ""),
                    skill=self.name,
                    priority=event.get("priority", 5),
                    metadata={"event_id": event["id"], "type": "calendar_reminder"},
                    action_url=f"/api/calendar/events/{event['id']}"
                )
                self.storage.event_mark_notified(event["id"])
                results.append(SkillResult.ok(
                    message=f"Reminder sent for: {event['title']}",
                    data={"event_id": event["id"], "title": event["title"]}
                ))

        return results

    # === Implementation ===

    def _add_event(self, params: Dict) -> SkillResult:
        title = params.get("title")
        start_time = params.get("start_time")
        if not title or not start_time:
            return SkillResult.fail(error="Title and start_time are required")

        # Parse natural language if needed
        parsed = self._parse_date(start_time)
        if parsed:
            start_time = parsed

        end_time = params.get("end_time")
        if end_time:
            end_parsed = self._parse_date(end_time)
            if end_parsed:
                end_time = end_parsed

        try:
            event_id = self.storage.event_add(
                title=title,
                start_time=start_time,
                end_time=end_time,
                description=params.get("description"),
                location=params.get("location"),
                category=params.get("category", "general"),
                priority=params.get("priority", 5),
                recurring=params.get("recurring"),
                metadata=params.get("metadata", {})
            )
            return SkillResult.ok(
                message=f"Event '{title}' added to calendar.",
                data={"event_id": event_id, "title": title, "start_time": start_time}
            )
        except Exception as e:
            return SkillResult.fail(error=str(e))

    def _list_events(self, params: Dict) -> SkillResult:
        events = self.storage.event_list(
            start=params.get("start"),
            end=params.get("end"),
            category=params.get("category")
        )
        return SkillResult.ok(
            data={"events": events, "count": len(events)},
            message=f"Found {len(events)} events."
        )

    def _today(self) -> SkillResult:
        events = self.storage.event_today()
        return SkillResult.ok(
            data={"events": events, "count": len(events)},
            message=f"You have {len(events)} event(s) today."
        )

    def _upcoming(self, params: Dict) -> SkillResult:
        hours = params.get("hours", 24)
        events = self.storage.event_upcoming(hours=hours)
        return SkillResult.ok(
            data={"events": events, "count": len(events), "hours": hours},
            message=f"Found {len(events)} upcoming event(s) in the next {hours}h."
        )

    def _edit_event(self, params: Dict) -> SkillResult:
        event_id = params.get("event_id")
        if not event_id:
            return SkillResult.fail(error="event_id is required")

        updates = {}
        for key in ["title", "start_time", "end_time", "description", "location", "category", "priority"]:
            if key in params:
                updates[key] = params[key]

        if not updates:
            return SkillResult.fail(error="No fields to update")

        try:
            self.storage.event_update(event_id, **updates)
            return SkillResult.ok(message=f"Event {event_id} updated.")
        except Exception as e:
            return SkillResult.fail(error=str(e))

    def _delete_event(self, params: Dict) -> SkillResult:
        event_id = params.get("event_id")
        if not event_id:
            return SkillResult.fail(error="event_id is required")
        try:
            self.storage.event_delete(event_id)
            return SkillResult.ok(message=f"Event {event_id} deleted.")
        except Exception as e:
            return SkillResult.fail(error=str(e))

    def _parse_natural(self, params: Dict) -> SkillResult:
        text = params.get("text", "")
        result = self._parse_date(text, return_dict=True)
        if result:
            return SkillResult.ok(data=result, message="Date parsed successfully.")
        return SkillResult.fail(error="Could not parse date from text.")

    def _check_reminders(self) -> SkillResult:
        now = datetime.now()
        window = now + timedelta(minutes=self._reminder_window_minutes)
        events = self.storage.event_list(start=now.isoformat(), end=window.isoformat())
        notifications = []
        for event in events:
            if not event.get("notified"):
                notifications.append({
                    "event_id": event["id"],
                    "title": event["title"],
                    "start_time": event["start_time"],
                    "location": event.get("location"),
                    "message": f"Upcoming: {event['title']} at {event['start_time']}"
                })
        return SkillResult.ok(
            data={"notifications": notifications, "count": len(notifications)},
            message=f"{len(notifications)} reminder(s) pending."
        )

    def _export_ics(self, params: Dict) -> SkillResult:
        events = self.storage.event_list()
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Aevibron//IRIS Calendar//EN"]
        for event in events:
            dtstart = event.get("start_time", "").replace("-", "").replace(":", "").replace("T", "T")[:15]
            lines.extend([
                "BEGIN:VEVENT",
                f"SUMMARY:{event.get('title', '')}",
                f"DTSTART:{dtstart}",
                f"DESCRIPTION:{event.get('description', '')}",
                f"LOCATION:{event.get('location', '')}",
                "END:VEVENT"
            ])
        lines.append("END:VCALENDAR")
        return SkillResult.ok(data={"ics_content": "\r\n".join(lines)}, message="ICS exported.")

    def _mark_completed(self, params: Dict) -> SkillResult:
        event_id = params.get("event_id")
        if not event_id:
            return SkillResult.fail(error="event_id required")
        self.storage.event_update(event_id, completed=1)
        return SkillResult.ok(message=f"Event {event_id} marked as completed.")

    # === Helpers ===

    def _parse_date(self, text: str, return_dict: bool = False):
        """Parse natural language to ISO datetime."""
        now = datetime.now()
        text_lower = text.lower().strip()

        # Handle ISO already
        if re.match(r'^\d{4}-\d{2}-\d{2}', text):
            return {"parsed_date": text, "original": text} if return_dict else text

        result_date = now
        time_set = False

        # Date keywords
        if "tomorrow" in text_lower:
            result_date = now + timedelta(days=1)
        elif "today" in text_lower:
            result_date = now
        elif "next week" in text_lower:
            result_date = now + timedelta(weeks=1)
        elif "next month" in text_lower:
            result_date = now + timedelta(days=30)
        elif "yesterday" in text_lower:
            result_date = now - timedelta(days=1)
        elif "in an hour" in text_lower:
            result_date = now + timedelta(hours=1)
        elif "in 30 minutes" in text_lower or "in half an hour" in text_lower:
            result_date = now + timedelta(minutes=30)
        elif "in 15 minutes" in text_lower or "in a quarter hour" in text_lower:
            result_date = now + timedelta(minutes=15)
        elif "in 5 minutes" in text_lower:
            result_date = now + timedelta(minutes=5)
        elif re.search(r'in (\d+) minutes?', text_lower):
            m = re.search(r'in (\d+) minutes?', text_lower)
            result_date = now + timedelta(minutes=int(m.group(1)))
        elif re.search(r'in (\d+) hours?', text_lower):
            m = re.search(r'in (\d+) hours?', text_lower)
            result_date = now + timedelta(hours=int(m.group(1)))
        elif re.search(r'in (\d+) days?', text_lower):
            m = re.search(r'in (\d+) days?', text_lower)
            result_date = now + timedelta(days=int(m.group(1)))

        # Time extraction
        time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)?', text_lower)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            period = time_match.group(3)
            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0
            result_date = result_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            time_set = True

        if not time_set:
            result_date = result_date.replace(hour=9, minute=0, second=0, microsecond=0)

        iso = result_date.isoformat()
        if return_dict:
            return {"parsed_date": iso, "original": text}
        return iso
