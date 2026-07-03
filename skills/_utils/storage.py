"""Shared storage abstraction for skills."""
import os
import json
import sqlite3
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class SkillStorage:
    """
    Unified storage for skills.
    Uses SQLite for structured data, JSON files for simple key-value.
    """

    def __init__(self, skill_name: str, data_dir: str = None):
        self.skill_name = skill_name
        self.data_dir = data_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", skill_name)
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, "storage.db")
        self.json_path = os.path.join(self.data_dir, "data.json")
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE,
                value TEXT,
                category TEXT DEFAULT 'general',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                start_time TEXT,
                end_time TEXT,
                category TEXT DEFAULT 'general',
                priority INTEGER DEFAULT 5,
                notified INTEGER DEFAULT 0,
                recurring TEXT,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                category TEXT DEFAULT 'general',
                tags TEXT,
                pinned INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    # === JSON key-value ===
    def get(self, key: str, default: Any = None) -> Any:
        data = self._read_json()
        return data.get(key, default)

    def set(self, key: str, value: Any):
        data = self._read_json()
        data[key] = value
        self._write_json(data)

    def delete(self, key: str):
        data = self._read_json()
        if key in data:
            del data[key]
            self._write_json(data)

    def _read_json(self) -> Dict:
        if not os.path.exists(self.json_path):
            return {}
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_json(self, data: Dict):
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    # === SQLite records ===
    def _conn(self):
        return sqlite3.connect(self.db_path)

    def record_set(self, key: str, value: Any, category: str = "general"):
        conn = self._conn()
        conn.execute(
            "INSERT OR REPLACE INTO records (key, value, category, updated_at) VALUES (?, ?, ?, ?)",
            (key, json.dumps(value, default=str), category, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

    def record_get(self, key: str) -> Optional[Any]:
        conn = self._conn()
        row = conn.execute("SELECT value FROM records WHERE key = ?", (key,)).fetchone()
        conn.close()
        if row:
            try:
                return json.loads(row[0])
            except Exception:
                return row[0]
        return None

    def record_search(self, query: str, category: str = None) -> List[Dict]:
        conn = self._conn()
        if category:
            rows = conn.execute(
                "SELECT * FROM records WHERE category = ? AND (key LIKE ? OR value LIKE ?)",
                (category, f"%{query}%", f"%{query}%")
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM records WHERE key LIKE ? OR value LIKE ?",
                (f"%{query}%", f"%{query}%")
            ).fetchall()
        conn.close()
        return [{"id": r[0], "key": r[1], "value": r[2], "category": r[3], "created_at": r[4]} for r in rows]

    def record_delete(self, key: str):
        conn = self._conn()
        conn.execute("DELETE FROM records WHERE key = ?", (key,))
        conn.commit()
        conn.close()

    # === Events (calendar/reminders) ===
    def event_add(self, title: str, start_time: str, end_time: str = None,
                  description: str = None, location: str = None,
                  category: str = "general", priority: int = 5,
                  recurring: str = None, metadata: Dict = None) -> int:
        conn = self._conn()
        cursor = conn.execute(
            """INSERT INTO events (title, description, start_time, end_time, location, category, priority, recurring, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, description, start_time, end_time, location, category, priority, recurring, json.dumps(metadata or {}))
        )
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return event_id

    def event_get(self, event_id: int) -> Optional[Dict]:
        conn = self._conn()
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        conn.close()
        if row:
            return self._row_to_dict(row, conn)
        return None

    def event_list(self, start: str = None, end: str = None, category: str = None) -> List[Dict]:
        conn = self._conn()
        conditions = ["1=1"]
        params = []
        if start:
            conditions.append("start_time >= ?")
            params.append(start)
        if end:
            conditions.append("start_time <= ?")
            params.append(end)
        if category:
            conditions.append("category = ?")
            params.append(category)
        query = f"SELECT * FROM events WHERE {' AND '.join(conditions)} ORDER BY start_time"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [self._row_to_dict_event(r) for r in rows]

    def event_upcoming(self, hours: int = 24) -> List[Dict]:
        from datetime import datetime, timedelta
        now = datetime.now().isoformat()
        future = (datetime.now() + timedelta(hours=hours)).isoformat()
        return self.event_list(start=now, end=future)

    def event_today(self) -> List[Dict]:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        return self.event_list(start=f"{today}T00:00:00", end=f"{today}T23:59:59")

    def event_delete(self, event_id: int):
        conn = self._conn()
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()
        conn.close()

    def event_mark_notified(self, event_id: int):
        conn = self._conn()
        conn.execute("UPDATE events SET notified = 1 WHERE id = ?", (event_id,))
        conn.commit()
        conn.close()

    def event_update(self, event_id: int, **kwargs):
        conn = self._conn()
        for key, value in kwargs.items():
            conn.execute(f"UPDATE events SET {key} = ? WHERE id = ?", (value, event_id))
        conn.commit()
        conn.close()

    def _row_to_dict_event(self, row) -> Dict:
        return {
            "id": row[0], "title": row[1], "description": row[2],
            "start_time": row[3], "end_time": row[4], "location": row[5],
            "category": row[6], "priority": row[7], "notified": row[8],
            "recurring": row[9], "metadata": row[10], "created_at": row[11]
        }

    # === Notes ===
    def note_add(self, title: str, content: str = "", category: str = "general", tags: List[str] = None) -> int:
        conn = self._conn()
        cursor = conn.execute(
            "INSERT INTO notes (title, content, category, tags) VALUES (?, ?, ?, ?)",
            (title, content, category, json.dumps(tags or []))
        )
        note_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return note_id

    def note_get(self, note_id: int) -> Optional[Dict]:
        conn = self._conn()
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        conn.close()
        if row:
            return self._row_to_dict_note(row)
        return None

    def note_list(self, category: str = None, search: str = None) -> List[Dict]:
        conn = self._conn()
        conditions = ["1=1"]
        params = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if search:
            conditions.append("(title LIKE ? OR content LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        query = f"SELECT * FROM notes WHERE {' AND '.join(conditions)} ORDER BY pinned DESC, updated_at DESC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [self._row_to_dict_note(r) for r in rows]

    def note_update(self, note_id: int, **kwargs):
        conn = self._conn()
        for key, value in kwargs.items():
            conn.execute(f"UPDATE notes SET {key} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (value, note_id))
        conn.commit()
        conn.close()

    def note_delete(self, note_id: int):
        conn = self._conn()
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        conn.close()

    def _row_to_dict_note(self, row) -> Dict:
        return {
            "id": row[0], "title": row[1], "content": row[2],
            "category": row[3], "tags": json.loads(row[4]) if row[4] else [],
            "pinned": row[5], "created_at": row[6], "updated_at": row[7]
        }
