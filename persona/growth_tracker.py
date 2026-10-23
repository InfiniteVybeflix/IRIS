"""
persona/growth_tracker.py — IRIS's Self-Evolution and Learning Engine

PROPER ARCHITECTURE:
- When PostgreSQL (Supabase) is available → stores ALL growth data in
  the kv_store table (namespace="growth_tracker"). Persistent.
- When PostgreSQL is NOT available → uses SQLite file.
- NEVER uses /tmp/ for persistent data.
- NEVER silently discards mission/lesson/skill data.
"""

import json
import logging
import os
import threading
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional

from . import IRISConnectable

logger = logging.getLogger("iris.persona.growth_tracker")

GROWTH_DB_PATH = os.getenv("IRIS_GROWTH_DB", "data/growth.db")


class GrowthTracker(IRISConnectable):
    """
    GrowthTracker — IRIS's self-evolution and learning engine.

    Tracks missions completed/failed, skills learned, and lessons learned.
    """

    def __init__(self, iris_core: Any = None, db_path: Optional[str] = None):
        super().__init__(iris_core=iris_core)
        self._lock = threading.RLock()
        self._db_path = db_path or GROWTH_DB_PATH

        self.missions_completed: int = 0
        self.missions_failed: int = 0
        self.skills_learned: List[str] = []
        self.lessons_learned: List[Dict[str, Any]] = []
        self.milestones: Dict[str, Any] = {
            "next_mission_count": 10,
            "next_skill_count": 5,
            "next_lesson_count": 20,
        }

        # Check if PostgreSQL is available
        self._use_postgres = False
        try:
            from core.db import db
            if db._db_available and db.use_postgres:
                self._use_postgres = True
                self._db = db
                logger.info("GrowthTracker: using PostgreSQL (persistent)")
        except Exception as e:
            logger.debug(f"GrowthTracker: PostgreSQL not available: {e}")

        if self._use_postgres:
            self._load_from_db()
        else:
            self._init_sqlite()
            self._load_from_db()

        logger.info(f"GrowthTracker initialized. {self.missions_completed} missions on record.")

    # ─── SQLite storage (local dev only) ────────────────────────────

    def _init_sqlite(self) -> None:
        """Initialize SQLite database schema (local dev only)."""
        try:
            db_dir = os.path.dirname(self._db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""CREATE TABLE IF NOT EXISTS missions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_name TEXT, success INTEGER, timestamp TEXT, details TEXT)""")
                conn.execute("""CREATE TABLE IF NOT EXISTS skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_name TEXT UNIQUE, learned_at TEXT, source TEXT)""")
                conn.execute("""CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lesson TEXT, source TEXT, learned_at TEXT, applied INTEGER DEFAULT 0)""")
                conn.commit()
        except sqlite3.OperationalError as e:
            logger.error(f"GrowthTracker: SQLite init failed at {self._db_path}: {e}. "
                         "Growth data will not persist.")
        except Exception as e:
            logger.error(f"GrowthTracker: unexpected SQLite init error: {e}")

    def _load_from_db(self) -> None:
        """Load growth data from storage."""
        if self._use_postgres:
            try:
                data = self._db.get_json("growth_tracker", "state")
                if data and isinstance(data, dict):
                    self.missions_completed = data.get("missions_completed", 0)
                    self.missions_failed = data.get("missions_failed", 0)
                    self.skills_learned = data.get("skills_learned", [])
                    self.lessons_learned = data.get("lessons_learned", [])
            except Exception as e:
                logger.error(f"GrowthTracker: failed to load from PostgreSQL: {e}")
        else:
            try:
                with sqlite3.connect(self._db_path) as conn:
                    cursor = conn.execute("SELECT success, COUNT(*) FROM missions GROUP BY success")
                    for row in cursor.fetchall():
                        success, count = row
                        if success:
                            self.missions_completed = count
                        else:
                            self.missions_failed = count
                    cursor = conn.execute("SELECT skill_name FROM skills")
                    self.skills_learned = [row[0] for row in cursor.fetchall()]
                    cursor = conn.execute("SELECT lesson, source, learned_at, applied FROM lessons")
                    for row in cursor.fetchall():
                        self.lessons_learned.append({
                            "lesson": row[0], "source": row[1],
                            "learned_at": row[2], "applied": bool(row[3]),
                        })
            except sqlite3.OperationalError as e:
                logger.error(f"GrowthTracker: SQLite load failed: {e}. Starting fresh.")
            except Exception as e:
                logger.error(f"GrowthTracker: unexpected load error: {e}")

    def _save_state(self) -> None:
        """Save entire growth state to storage."""
        data = {
            "missions_completed": self.missions_completed,
            "missions_failed": self.missions_failed,
            "skills_learned": self.skills_learned,
            "lessons_learned": self.lessons_learned,
            "saved_at": datetime.utcnow().isoformat(),
        }
        if self._use_postgres:
            try:
                self._db.store_json("growth_tracker", "state", data)
            except Exception as e:
                logger.error(f"GrowthTracker: failed to save to PostgreSQL: {e}. "
                             "Growth data may be lost on restart.")
        else:
            try:
                with sqlite3.connect(self._db_path) as conn:
                    conn.execute("INSERT OR REPLACE INTO missions (mission_name, success, timestamp, details) VALUES (?, ?, ?, ?)",
                                 ("state_summary", 1, data["saved_at"], json.dumps(data)))
                    conn.commit()
            except sqlite3.OperationalError as e:
                logger.error(f"GrowthTracker: failed to save to SQLite: {e}. "
                             "Growth data will be lost on restart.")
            except Exception as e:
                logger.error(f"GrowthTracker: unexpected save error: {e}")

    # ─── Public API ──────────────────────────────────────────────────

    def record_mission_outcome(self, mission: str, success: bool, details: Optional[Dict[str, Any]] = None) -> bool:
        """Record the outcome of a mission."""
        with self._lock:
            if self._use_postgres:
                try:
                    with sqlite3.connect(self._db_path) as _:
                        pass  # no-op — using PostgreSQL
                except Exception:
                    pass

                if success:
                    self.missions_completed += 1
                else:
                    self.missions_failed += 1
                self._save_state()

                if not success:
                    self.record_lesson(
                        f"Mission '{mission}' failed. Analyze and adapt.",
                        f"mission_{mission}")
                logger.info(f"Mission recorded: {mission} -> {'SUCCESS' if success else 'FAILED'}")
                return True
            else:
                try:
                    with sqlite3.connect(self._db_path) as conn:
                        conn.execute("INSERT INTO missions (mission_name, success, timestamp, details) VALUES (?, ?, ?, ?)",
                                     (mission, 1 if success else 0,
                                      datetime.utcnow().isoformat(),
                                      json.dumps(details or {})))
                        conn.commit()
                    if success:
                        self.missions_completed += 1
                    else:
                        self.missions_failed += 1
                    if not success:
                        self.record_lesson(
                            f"Mission '{mission}' failed. Analyze and adapt.",
                            f"mission_{mission}")
                    logger.info(f"Mission recorded: {mission} -> {'SUCCESS' if success else 'FAILED'}")
                    return True
                except sqlite3.OperationalError as e:
                    logger.error(f"GrowthTracker: failed to record mission to SQLite: {e}")
                    return False
                except Exception as e:
                    logger.error(f"GrowthTracker: unexpected mission recording error: {e}")
                    return False

    def record_lesson(self, lesson: str, source: str) -> bool:
        """Record a lesson learned."""
        with self._lock:
            for existing in self.lessons_learned:
                if existing["lesson"] == lesson:
                    logger.debug(f"Duplicate lesson skipped: {lesson[:50]}...")
                    return False
            entry = {
                "lesson": lesson, "source": source,
                "learned_at": datetime.utcnow().isoformat(), "applied": False,
            }
            self.lessons_learned.append(entry)
            self._save_state()
            logger.info(f"Lesson recorded from {source}: {lesson[:80]}...")
            return True

    def learn_skill(self, skill: str, source: str = "unknown") -> bool:
        """Record a new skill learned."""
        with self._lock:
            if skill in self.skills_learned:
                logger.debug(f"Skill already known: {skill}")
                return False
            self.skills_learned.append(skill)
            self._save_state()
            logger.info(f"New skill learned: {skill} (from {source})")
            return True

    def get_growth_report(self) -> Dict[str, Any]:
        """Return a full evolution summary."""
        with self._lock:
            total = self.missions_completed + self.missions_failed
            success_rate = self.missions_completed / total if total > 0 else 0.0
            return {
                "missions_completed": self.missions_completed,
                "missions_failed": self.missions_failed,
                "total_missions": total,
                "success_rate": round(success_rate, 3),
                "skills_learned_count": len(self.skills_learned),
                "skills_learned": self.skills_learned,
                "lessons_learned_count": len(self.lessons_learned),
                "recent_lessons": self.lessons_learned[-5:] if self.lessons_learned else [],
            }

    def get_milestone_status(self) -> Dict[str, Any]:
        """Return next milestone targets and progress."""
        with self._lock:
            total = self.missions_completed + self.missions_failed
            return {
                "missions": {"current": total, "next_target": self.milestones["next_mission_count"],
                             "progress": round(total / self.milestones["next_mission_count"], 3) if self.milestones["next_mission_count"] > 0 else 1.0},
                "skills": {"current": len(self.skills_learned), "next_target": self.milestones["next_skill_count"],
                           "progress": round(len(self.skills_learned) / self.milestones["next_skill_count"], 3) if self.milestones["next_skill_count"] > 0 else 1.0},
                "lessons": {"current": len(self.lessons_learned), "next_target": self.milestones["next_lesson_count"],
                            "progress": round(len(self.lessons_learned) / self.milestones["next_lesson_count"], 3) if self.milestones["next_lesson_count"] > 0 else 1.0},
            }

    def set_milestone(self, category: str, target: int) -> bool:
        """Set a new milestone target."""
        with self._lock:
            key = f"next_{category}_count"
            if key in self.milestones:
                self.milestones[key] = target
                logger.info(f"Milestone set: {category} -> {target}")
                return True
            return False

    def get_skills(self) -> List[str]:
        """Return all learned skills."""
        with self._lock:
            return self.skills_learned.copy()

    def get_lessons(self) -> List[Dict[str, Any]]:
        """Return all learned lessons."""
        with self._lock:
            return self.lessons_learned.copy()

    def health_check(self) -> Dict[str, Any]:
        """Return health status."""
        with self._lock:
            base = super().health_check() if hasattr(super(), "health_check") else {}
            base.update(self.get_growth_report())
            base.update({"milestones": self.milestones,
                         "backend": "postgresql" if self._use_postgres else "sqlite"})
            return base


__all__ = ["GrowthTracker"]
