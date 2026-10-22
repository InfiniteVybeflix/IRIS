"""IRIS v1 Proactive Engine — Jarvis-Level Context Awareness"""
import os
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from config import config
from core.db import db
from core.aevibron_client import aevibron

logger = logging.getLogger(__name__)

class ProactiveEngine:
    """Jarvis-level proactive intelligence."""

    def __init__(self):
        self.enabled = config.PROACTIVE_MODE
        self.check_interval = config.PROACTIVE_CHECK_INTERVAL
        self.running = False
        self.thread = None
        self.last_check = datetime.now()
        self.context_history = []
        self.max_history = 100
        self.owner_patterns = {}
        self._load_patterns()

    def _load_patterns(self):
        pattern_file = os.path.join(config.SELF_DIR, "owner_patterns.json")
        if os.path.exists(pattern_file):
            try:
                with open(pattern_file, 'r') as f:
                    self.owner_patterns = json.load(f)
            except:
                self.owner_patterns = {}

    def _save_patterns(self):
        pattern_file = os.path.join(config.SELF_DIR, "owner_patterns.json")
        os.makedirs(os.path.dirname(pattern_file), exist_ok=True)
        with open(pattern_file, 'w') as f:
            json.dump(self.owner_patterns, f, indent=2)

    def start(self):
        if not self.enabled or self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("Proactive engine started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Proactive engine stopped")

    def _monitor_loop(self):
        while self.running:
            try:
                self._check_calendar()
                self._check_patterns()
                self._check_system_health()
                self._check_learning_opportunities()
                self.last_check = datetime.now()
            except Exception as e:
                logger.error(f"Proactive check error: {e}")
            time.sleep(self.check_interval)

    def _check_calendar(self):
        try:
            upcoming = db.get_upcoming_events(hours=1)
            for event in upcoming:
                if not event.get("notified"):
                    start_time = event.get("start_time", "")
                    try:
                        if isinstance(start_time, str):
                            event_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                        else:
                            event_dt = start_time
                        now = datetime.now()
                        if isinstance(event_dt, datetime):
                            time_diff = (event_dt - now).total_seconds()
                            if 0 < time_diff < 3600:
                                self._notify_owner(
                                    "calendar",
                                    f"Upcoming: {event['title']} in {int(time_diff / 60)} minutes",
                                    {"event_id": event["id"], "location": event.get("location", "")}
                                )
                                db.mark_notified(event["id"])
                    except:
                        continue
        except Exception as e:
            logger.error(f"Calendar check error: {e}")

    def _check_patterns(self):
        try:
            hour = datetime.now().hour
            if 6 <= hour <= 9:
                if self.owner_patterns.get("morning_check", 0) > 3:
                    self._notify_owner("routine", "Good morning! Ready to check today's schedule and news?", {"type": "morning_routine"})
            if 18 <= hour <= 21:
                if self.owner_patterns.get("evening_wrap", 0) > 3:
                    self._notify_owner("routine", "Evening check-in. Want me to summarize today's progress?", {"type": "evening_wrap"})
        except Exception as e:
            logger.error(f"Pattern check error: {e}")

    def _check_system_health(self):
        try:
            stats = aevibron.get_stats()
            if stats.get("error_rate", 0) > 0.5:
                self._notify_owner("system", f"High error rate: {stats['error_rate']:.1%}. Gateway may be unstable.", {"error_rate": stats["error_rate"]})
        except Exception as e:
            logger.error(f"Health check error: {e}")

    def _check_learning_opportunities(self):
        try:
            failed_tasks = db._fetchall("SELECT * FROM tasks WHERE status = 'failed' ORDER BY created_at DESC LIMIT 5")
            if len(failed_tasks) >= 3:
                self._notify_owner("learning", f"I've encountered {len(failed_tasks)} failed tasks. Should I analyze and improve?", {"failed_count": len(failed_tasks)})
        except Exception as e:
            logger.error(f"Learning check error: {e}")

    def _notify_owner(self, notification_type: str, message: str, data: Dict = None):
        notification = {"type": notification_type, "message": message, "data": data or {}, "timestamp": datetime.now().isoformat(), "read": False}
        db.save_episode(event="proactive_notification", context=message, emotion="curious", lesson=f"Proactive: {notification_type}", severity=3)
        logger.info(f"Proactive: {message}")
        return notification

    def record_interaction(self, user_input: str, response_type: str, success: bool):
        self.context_history.append({"input": user_input, "type": response_type, "success": success, "hour": datetime.now().hour, "timestamp": datetime.now().isoformat()})
        if len(self.context_history) > self.max_history:
            self.context_history.pop(0)
        hour = datetime.now().hour
        if 6 <= hour <= 9:
            self.owner_patterns["morning_check"] = self.owner_patterns.get("morning_check", 0) + 1
        elif 18 <= hour <= 21:
            self.owner_patterns["evening_wrap"] = self.owner_patterns.get("evening_wrap", 0) + 1
        if len(self.context_history) % 10 == 0:
            self._save_patterns()

    def get_context_summary(self) -> str:
        now = datetime.now()
        recent_messages = db.get_conversation("system", limit=5)
        upcoming = db.get_upcoming_events(hours=24)
        stats = aevibron.get_stats()
        summary = f"""Current Context:
- Time: {now.strftime('%Y-%m-%d %H:%M')} ({now.strftime('%A')})
- Upcoming events (24h): {len(upcoming)}
- Recent interactions: {len(self.context_history)}
- Gateway health: {'Good' if stats.get('error_rate', 1) < 0.1 else 'Degraded'}
- Proactive mode: {'Active' if self.enabled else 'Inactive'}
"""
        if upcoming:
            summary += f"- Next event: {upcoming[0]['title']} at {upcoming[0]['start_time']}\n"
        return summary

    def suggest_action(self, context: str = "") -> Optional[str]:
        if not self.enabled:
            return None
        suggestions = [
            "I noticed you haven't committed code in a while. Want me to review your changes?",
            "Your calendar shows a meeting in 30 minutes. Should I prepare a summary?",
            "I've learned a new pattern from your recent tasks. Want to see it?",
            "The gateway error rate is elevated. Should I run diagnostics?",
            "It's been 2 hours since your last break. Consider taking a short walk.",
        ]
        hour = datetime.now().hour
        if 9 <= hour <= 17:
            return suggestions[0]
        elif hour >= 22 or hour <= 5:
            return suggestions[4]
        return suggestions[2]

proactive_engine = ProactiveEngine()
