"""IRIS v1 Hybrid Database — Postgres (Vercel) + SQLite (Local) Dual Engine"""
import os
import json
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from config import config

logger = logging.getLogger(__name__)

class Database:
    """Production-grade database with Postgres (Vercel/Supabase) + SQLite (local) support.

    Resilience: NEVER crashes at startup. If DB is unavailable, IRIS boots
    with an in-memory SQLite (data lost on cold start, but IRIS works).
    """

    def __init__(self):
        self.use_postgres = config.USE_POSTGRES
        self.db_path = config.LOCAL_DB_PATH.replace("sqlite:///", "") if config.LOCAL_DB_PATH else "/tmp/iris.db"
        self.pg_conn = None
        self._db_available = True

        try:
            if self.use_postgres:
                self._init_postgres()
            else:
                # Use /tmp/ for SQLite (writable on Vercel serverless)
                if not self.db_path or self.db_path.startswith("data/"):
                    self.db_path = "/tmp/iris.db"
                # Ensure directory exists
                db_dir = os.path.dirname(self.db_path)
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)

            self._init_tables()
        except Exception as e:
            logger.warning(f"Database init failed: {e}. Using in-memory SQLite as fallback.")
            self.use_postgres = False
            self.db_path = ":memory:"
            self._db_available = False
            try:
                self._init_tables()
            except Exception as e2:
                logger.error(f"Even in-memory SQLite failed: {e2}")
                self._db_available = False

    def _init_postgres(self):
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            self.pg_conn = psycopg2.connect(
                config.DATABASE_URL,
                cursor_factory=RealDictCursor,
                connect_timeout=15,
                options='-c statement_timeout=30000'
            )
            self.pg_conn.autocommit = False
            logger.info("PostgreSQL connected (Vercel)")
        except Exception as e:
            logger.error(f"PostgreSQL failed: {e}. Falling back to SQLite.")
            self.use_postgres = False

    def _get_conn(self):
        if self.use_postgres:
            try:
                self.pg_conn.cursor().execute("SELECT 1")
                return self.pg_conn
            except Exception:
                self._init_postgres()
                return self.pg_conn
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn

    def _execute(self, query: str, params: tuple = ()):
        max_retries = 3
        for attempt in range(max_retries):
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return cursor
            except Exception as e:
                conn.rollback()
                if attempt == max_retries - 1:
                    raise e
                if self.use_postgres:
                    self._init_postgres()
                import time
                time.sleep(0.5 * (2 ** attempt))
        return None

    def _fetchall(self, query: str, params: tuple = ()) -> List[Dict]:
        max_retries = 3
        for attempt in range(max_retries):
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.commit()
                return [dict(row) for row in rows]
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"DB fetch error: {e}")
                    return []
                if self.use_postgres:
                    self._init_postgres()
                import time
                time.sleep(0.5 * (2 ** attempt))
        return []

    def _fetchone(self, query: str, params: tuple = ()) -> Optional[Dict]:
        rows = self._fetchall(query, params)
        return rows[0] if rows else None

    def _init_tables(self):
        pg = self.use_postgres
        ai = "INTEGER" if not pg else "SERIAL"
        ts = "TIMESTAMP" if pg else "TEXT"
        ph = "%s" if pg else "?"
        now = "CURRENT_TIMESTAMP" if pg else "CURRENT_TIMESTAMP"
        or_ignore = "ON CONFLICT DO NOTHING" if pg else "OR IGNORE"

        # Messages
        self._execute(f"""
            CREATE TABLE IF NOT EXISTS messages (
                id {ai} PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                reasoning TEXT,
                tool_calls TEXT,
                model_used TEXT,
                tokens_used INTEGER DEFAULT 0,
                timestamp {ts} DEFAULT {now}
            )
        """)

        # Tasks
        self._execute(f"""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 5,
                estimated_duration INTEGER,
                steps TEXT,
                result TEXT,
                created_at {ts} DEFAULT {now},
                completed_at {ts}
            )
        """)

        # Memories
        self._execute(f"""
            CREATE TABLE IF NOT EXISTS memories (
                id {ai} PRIMARY KEY,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                importance INTEGER DEFAULT 5,
                source TEXT,
                embedding TEXT,
                timestamp {ts} DEFAULT {now}
            )
        """)

        # Episodes
        self._execute(f"""
            CREATE TABLE IF NOT EXISTS episodes (
                id {ai} PRIMARY KEY,
                event TEXT NOT NULL,
                context TEXT,
                emotion TEXT DEFAULT 'neutral',
                lesson TEXT,
                severity INTEGER DEFAULT 5,
                timestamp {ts} DEFAULT {now}
            )
        """)

        # Owner
        self._execute(f"""
            CREATE TABLE IF NOT EXISTS owner (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT DEFAULT 'Infinite Vybeflix',
                aliases TEXT DEFAULT 'Infinite',
                preferences TEXT,
                personality_notes TEXT,
                tech_stack_prefs TEXT,
                project_history TEXT,
                secrets TEXT,
                wake_phrases TEXT,
                created_at {ts} DEFAULT {now},
                updated_at {ts} DEFAULT {now}
            )
        """)

        # Calendar
        self._execute(f"""
            CREATE TABLE IF NOT EXISTS calendar_events (
                id {ai} PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                start_time {ts} NOT NULL,
                end_time {ts},
                location TEXT,
                category TEXT DEFAULT 'general',
                priority INTEGER DEFAULT 5,
                notified INTEGER DEFAULT 0,
                recurring TEXT,
                created_at {ts} DEFAULT {now}
            )
        """)

        # Notes
        self._execute(f"""
            CREATE TABLE IF NOT EXISTS notes (
                id {ai} PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT,
                category TEXT DEFAULT 'general',
                tags TEXT,
                pinned INTEGER DEFAULT 0,
                created_at {ts} DEFAULT {now},
                updated_at {ts} DEFAULT {now}
            )
        """)

        # Logs
        self._execute(f"""
            CREATE TABLE IF NOT EXISTS logs (
                id {ai} PRIMARY KEY,
                level TEXT NOT NULL,
                component TEXT NOT NULL,
                message TEXT NOT NULL,
                metadata TEXT,
                timestamp {ts} DEFAULT {now}
            )
        """)

        # Sessions
        self._execute(f"""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT DEFAULT 'owner',
                device_info TEXT,
                created_at {ts} DEFAULT {now},
                expires_at {ts},
                last_active {ts} DEFAULT {now}
            )
        """)

        # Proactive tasks
        self._execute(f"""
            CREATE TABLE IF NOT EXISTS proactive_tasks (
                id {ai} PRIMARY KEY,
                trigger_type TEXT NOT NULL,
                trigger_condition TEXT,
                action TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                last_triggered {ts},
                created_at {ts} DEFAULT {now}
            )
        """)

        # Health metrics
        self._execute(f"""
            CREATE TABLE IF NOT EXISTS health_metrics (
                id {ai} PRIMARY KEY,
                metric_name TEXT NOT NULL,
                metric_value REAL,
                metadata TEXT,
                timestamp {ts} DEFAULT {now}
            )
        """)

        # Default owner
        self._execute(
            f"INSERT {or_ignore} INTO owner (id, name, aliases) VALUES (1, {ph}, {ph})",
            (config.OWNER_NAME, config.OWNER_ALIAS)
        )

    # === MESSAGES ===
    def save_message(self, session_id: str, role: str, content: str, reasoning: str = None,
                     tool_calls: List[str] = None, model_used: str = None, tokens_used: int = 0):
        ph = "%s" if self.use_postgres else "?"
        self._execute(
            f"INSERT INTO messages (session_id, role, content, reasoning, tool_calls, model_used, tokens_used) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
            (session_id, role, content, reasoning, json.dumps(tool_calls) if tool_calls else None, model_used, tokens_used)
        )

    def get_conversation(self, session_id: str, limit: int = 50) -> List[Dict]:
        ph = "%s" if self.use_postgres else "?"
        rows = self._fetchall(
            f"SELECT * FROM messages WHERE session_id = {ph} ORDER BY timestamp DESC LIMIT {ph}",
            (session_id, limit)
        )
        return rows[::-1]

    def get_all_sessions(self) -> List[Dict]:
        return self._fetchall(
            "SELECT session_id, MAX(timestamp) as last_message, COUNT(*) as message_count FROM messages GROUP BY session_id ORDER BY last_message DESC"
        )

    # === TASKS ===
    def create_task(self, task_id: str, description: str, priority: int = 5, estimated_duration: int = None):
        ph = "%s" if self.use_postgres else "?"
        self._execute(
            f"INSERT INTO tasks (id, description, priority, estimated_duration) VALUES ({ph}, {ph}, {ph}, {ph})",
            (task_id, description, priority, estimated_duration)
        )

    def update_task(self, task_id: str, status: str = None, steps: List = None, result: str = None):
        updates = []
        params = []
        pg = self.use_postgres
        if status:
            updates.append("status = %s" if pg else "status = ?")
            params.append(status)
        if steps is not None:
            updates.append("steps = %s" if pg else "steps = ?")
            params.append(json.dumps(steps))
        if result:
            updates.append("result = %s" if pg else "result = ?")
            params.append(result)
        if status == "completed":
            updates.append("completed_at = CURRENT_TIMESTAMP")
        if updates:
            ph = "%s" if pg else "?"
            params.append(task_id)
            self._execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = {ph}", tuple(params))

    def get_pending_tasks(self) -> List[Dict]:
        return self._fetchall("SELECT * FROM tasks WHERE status = 'pending' ORDER BY priority DESC, created_at ASC")

    # === MEMORIES ===
    def save_memory(self, key: str, value: str, category: str = "general", importance: int = 5, source: str = None, embedding: str = None):
        ph = "%s" if self.use_postgres else "?"
        if self.use_postgres:
            self._execute(
                f"""INSERT INTO memories (key, value, category, importance, source, embedding)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                    ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    importance = excluded.importance,
                    embedding = excluded.embedding,
                    timestamp = CURRENT_TIMESTAMP""",
                (key, value, category, importance, source, embedding)
            )
        else:
            self._execute(
                f"""INSERT OR REPLACE INTO memories (key, value, category, importance, source, embedding, timestamp)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, CURRENT_TIMESTAMP)""",
                (key, value, category, importance, source, embedding)
            )

    def search_memory(self, query: str, category: str = None, limit: int = 10) -> List[Dict]:
        ph = "%s" if self.use_postgres else "?"
        if category:
            return self._fetchall(
                f"SELECT * FROM memories WHERE category = {ph} AND (key LIKE {ph} OR value LIKE {ph}) ORDER BY importance DESC, timestamp DESC LIMIT {ph}",
                (category, f"%{query}%", f"%{query}%", limit)
            )
        return self._fetchall(
            f"SELECT * FROM memories WHERE key LIKE {ph} OR value LIKE {ph} ORDER BY importance DESC, timestamp DESC LIMIT {ph}",
            (f"%{query}%", f"%{query}%", limit)
        )

    def get_memories_by_category(self, category: str, limit: int = 50) -> List[Dict]:
        ph = "%s" if self.use_postgres else "?"
        return self._fetchall(
            f"SELECT * FROM memories WHERE category = {ph} ORDER BY importance DESC, timestamp DESC LIMIT {ph}",
            (category, limit)
        )

    # === EPISODES ===
    def save_episode(self, event: str, context: str = None, emotion: str = "neutral", lesson: str = None, severity: int = 5):
        ph = "%s" if self.use_postgres else "?"
        self._execute(
            f"INSERT INTO episodes (event, context, emotion, lesson, severity) VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
            (event, context, emotion, lesson, severity)
        )

    def get_episodes(self, limit: int = 20) -> List[Dict]:
        ph = "%s" if self.use_postgres else "?"
        return self._fetchall(f"SELECT * FROM episodes ORDER BY timestamp DESC LIMIT {ph}", (limit,))

    def get_episodes_by_emotion(self, emotion: str, limit: int = 10) -> List[Dict]:
        ph = "%s" if self.use_postgres else "?"
        return self._fetchall(
            f"SELECT * FROM episodes WHERE emotion = {ph} ORDER BY timestamp DESC LIMIT {ph}",
            (emotion, limit)
        )

    # === OWNER ===
    def get_owner(self) -> Dict:
        return self._fetchone("SELECT * FROM owner WHERE id = 1") or {}

    def update_owner(self, **kwargs):
        for key, value in kwargs.items():
            ph = "%s" if self.use_postgres else "?"
            self._execute(
                f"UPDATE owner SET {key} = {ph}, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
                (value,)
            )

    # === CALENDAR ===
    def add_calendar_event(self, title: str, start_time: str, end_time: str = None,
                           description: str = None, location: str = None,
                           category: str = "general", priority: int = 5, recurring: str = None) -> int:
        ph = "%s" if self.use_postgres else "?"
        cursor = self._execute(
            f"""INSERT INTO calendar_events
                (title, description, start_time, end_time, location, category, priority, recurring)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})""" +
            (" RETURNING id" if self.use_postgres else ""),
            (title, description, start_time, end_time, location, category, priority, recurring)
        )
        if self.use_postgres:
            return cursor.fetchone()["id"]
        return cursor.lastrowid

    def get_calendar_events(self, start: str = None, end: str = None, category: str = None) -> List[Dict]:
        conditions = ["1=1"]
        params = []
        pg = self.use_postgres
        if start:
            conditions.append("start_time >= %s" if pg else "start_time >= ?")
            params.append(start)
        if end:
            conditions.append("start_time <= %s" if pg else "start_time <= ?")
            params.append(end)
        if category:
            conditions.append("category = %s" if pg else "category = ?")
            params.append(category)
        query = f"SELECT * FROM calendar_events WHERE {' AND '.join(conditions)} ORDER BY start_time"
        return self._fetchall(query, tuple(params))

    def get_upcoming_events(self, hours: int = 24) -> List[Dict]:
        from datetime import datetime, timedelta
        now = datetime.now().isoformat()
        future = (datetime.now() + timedelta(hours=hours)).isoformat()
        return self.get_calendar_events(start=now, end=future)

    def mark_notified(self, event_id: int):
        ph = "%s" if self.use_postgres else "?"
        self._execute(f"UPDATE calendar_events SET notified = 1 WHERE id = {ph}", (event_id,))

    # === NOTES ===
    def add_note(self, title: str, content: str = "", category: str = "general", tags: List[str] = None) -> int:
        ph = "%s" if self.use_postgres else "?"
        cursor = self._execute(
            f"INSERT INTO notes (title, content, category, tags) VALUES ({ph}, {ph}, {ph}, {ph})" +
            (" RETURNING id" if self.use_postgres else ""),
            (title, content, category, json.dumps(tags or []))
        )
        if self.use_postgres:
            return cursor.fetchone()["id"]
        return cursor.lastrowid

    def get_notes(self, category: str = None, search: str = None) -> List[Dict]:
        conditions = ["1=1"]
        params = []
        pg = self.use_postgres
        if category:
            conditions.append("category = %s" if pg else "category = ?")
            params.append(category)
        if search:
            conditions.append("(title LIKE %s OR content LIKE %s)" if pg else "(title LIKE ? OR content LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        query = f"SELECT * FROM notes WHERE {' AND '.join(conditions)} ORDER BY pinned DESC, updated_at DESC"
        return self._fetchall(query, tuple(params))

    def update_note(self, note_id: int, **kwargs):
        for key, value in kwargs.items():
            ph = "%s" if self.use_postgres else "?"
            self._execute(
                f"UPDATE notes SET {key} = {ph}, updated_at = CURRENT_TIMESTAMP WHERE id = {ph}",
                (value, note_id)
            )

    # === LOGS ===
    def log(self, level: str, component: str, message: str, metadata: Dict = None):
        ph = "%s" if self.use_postgres else "?"
        self._execute(
            f"INSERT INTO logs (level, component, message, metadata) VALUES ({ph}, {ph}, {ph}, {ph})",
            (level, component, message, json.dumps(metadata) if metadata else None)
        )

    def get_logs(self, level: str = None, component: str = None, limit: int = 100) -> List[Dict]:
        conditions = ["1=1"]
        params = []
        pg = self.use_postgres
        if level:
            conditions.append("level = %s" if pg else "level = ?")
            params.append(level)
        if component:
            conditions.append("component = %s" if pg else "component = ?")
            params.append(component)
        query = f"SELECT * FROM logs WHERE {' AND '.join(conditions)} ORDER BY timestamp DESC LIMIT %s" if pg else f"SELECT * FROM logs WHERE {' AND '.join(conditions)} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        return self._fetchall(query, tuple(params))

    # === SESSIONS ===
    def create_session(self, session_id: str, user_id: str = "owner", device_info: str = None, expires_hours: int = 24):
        from datetime import timedelta
        expires = (datetime.now() + timedelta(hours=expires_hours)).isoformat()
        ph = "%s" if self.use_postgres else "?"
        self._execute(
            f"INSERT INTO sessions (session_id, user_id, device_info, expires_at) VALUES ({ph}, {ph}, {ph}, {ph})",
            (session_id, user_id, device_info, expires)
        )

    def validate_session(self, session_id: str) -> bool:
        ph = "%s" if self.use_postgres else "?"
        now = datetime.now().isoformat()
        row = self._fetchone(
            f"SELECT * FROM sessions WHERE session_id = {ph} AND expires_at > {ph}",
            (session_id, now)
        )
        if row:
            self._execute(
                f"UPDATE sessions SET last_active = CURRENT_TIMESTAMP WHERE session_id = {ph}",
                (session_id,)
            )
            return True
        return False

    def get_active_sessions(self) -> List[Dict]:
        now = datetime.now().isoformat()
        ph = "%s" if self.use_postgres else "?"
        return self._fetchall(
            f"SELECT * FROM sessions WHERE expires_at > {ph} ORDER BY last_active DESC",
            (now,)
        )

    # === PROACTIVE TASKS ===
    def add_proactive_task(self, trigger_type: str, trigger_condition: str, action: str) -> int:
        ph = "%s" if self.use_postgres else "?"
        cursor = self._execute(
            f"INSERT INTO proactive_tasks (trigger_type, trigger_condition, action) VALUES ({ph}, {ph}, {ph})" +
            (" RETURNING id" if self.use_postgres else ""),
            (trigger_type, trigger_condition, action)
        )
        if self.use_postgres:
            return cursor.fetchone()["id"]
        return cursor.lastrowid

    def get_active_proactive_tasks(self) -> List[Dict]:
        return self._fetchall("SELECT * FROM proactive_tasks WHERE status = 'active' ORDER BY created_at DESC")

    def update_proactive_task(self, task_id: int, status: str = None, last_triggered: str = None):
        updates = []
        params = []
        pg = self.use_postgres
        if status:
            updates.append("status = %s" if pg else "status = ?")
            params.append(status)
        if last_triggered:
            updates.append("last_triggered = %s" if pg else "last_triggered = ?")
            params.append(last_triggered)
        if updates:
            ph = "%s" if pg else "?"
            params.append(task_id)
            self._execute(f"UPDATE proactive_tasks SET {', '.join(updates)} WHERE id = {ph}", tuple(params))

    # === HEALTH METRICS ===
    def record_health_metric(self, metric_name: str, metric_value: float, metadata: Dict = None):
        ph = "%s" if self.use_postgres else "?"
        self._execute(
            f"INSERT INTO health_metrics (metric_name, metric_value, metadata) VALUES ({ph}, {ph}, {ph})",
            (metric_name, metric_value, json.dumps(metadata) if metadata else None)
        )

    def get_health_metrics(self, metric_name: str = None, hours: int = 24) -> List[Dict]:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        conditions = [f"timestamp > {('%s' if self.use_postgres else '?')}"]
        params = [cutoff]
        if metric_name:
            conditions.append(f"metric_name = {('%s' if self.use_postgres else '?')}")
            params.append(metric_name)
        query = f"SELECT * FROM health_metrics WHERE {' AND '.join(conditions)} ORDER BY timestamp DESC"
        return self._fetchall(query, tuple(params))


# Singleton
db = Database()
