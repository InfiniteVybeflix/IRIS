"""Notification queue for skills to push alerts."""
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime


class NotificationQueue:
    """Simple notification queue that skills can push to."""

    def __init__(self, queue_path: str = None):
        self.queue_path = queue_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "notifications.json"
        )
        os.makedirs(os.path.dirname(self.queue_path), exist_ok=True)

    def push(self, title: str, message: str, skill: str = "unknown",
             priority: int = 5, metadata: Dict = None, action_url: str = None):
        notifications = self._read()
        notifications.append({
            "id": len(notifications) + 1,
            "title": title,
            "message": message,
            "skill": skill,
            "priority": priority,
            "timestamp": datetime.now().isoformat(),
            "read": False,
            "metadata": metadata or {},
            "action_url": action_url,
        })
        self._write(notifications)

    def pop(self) -> Optional[Dict]:
        notifications = self._read()
        unread = [n for n in notifications if not n["read"]]
        if unread:
            unread[0]["read"] = True
            self._write(notifications)
            return unread[0]
        return None

    def get_unread(self, limit: int = 50) -> List[Dict]:
        return [n for n in self._read() if not n["read"]][:limit]

    def get_all(self, limit: int = 100) -> List[Dict]:
        return self._read()[-limit:]

    def clear(self):
        self._write([])

    def _read(self) -> List[Dict]:
        if not os.path.exists(self.queue_path):
            return []
        try:
            with open(self.queue_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _write(self, data: List[Dict]):
        with open(self.queue_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
