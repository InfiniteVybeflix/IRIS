"""
growth_tracker.py — IRIS's Evolution and Learning Log

Tracks every mission, every failure, every lesson learned. IRIS does not
forget. She grows. This module is her memory of her own evolution.

Every mission is a step forward. Every failure is data. Every lesson
is a permanent upgrade.
"""

import os
import json
import sqlite3
import threading
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from . import IRISConnectable

logger = logging.getLogger("iris.persona.growth_tracker")

# Environment-based paths
GROWTH_DB_PATH = os.getenv("IRIS_GROWTH_DB", "data/growth.db")
GROWTH_JSON_PATH = os.getenv("IRIS_GROWTH_JSON", "data/growth.json")


class GrowthTracker(IRISConnectable):
    """
    GrowthTracker — IRIS's self-evolution and learning engine.

    Tracks missions completed, missions failed, skills learned, and lessons
    learned. Every experience is recorded and analyzed for patterns.

    Attributes:
        missions_completed: Count of successful missions.
        missions_failed: Count of failed missions.
        skills_learned: List of skills acquired.
        lessons_learned: List of lesson dictionaries.
        _db_path: Path to SQLite database.
        _lock: Thread-safe lock.

    Example:
        >>> growth = GrowthTracker()
        >>> growth.record_mission_outcome("secure_website", True)
        True
        >>> growth.record_lesson("Always verify SSL certs", "mission_secure_website")
        True
        >>> growth.get_growth_report()
        {"missions_completed": 1, "missions_failed": 0, ...}
    """

    def __init__(self, iris_core: Any = None, db_path: Optional[str] = None):
        """
        Initialize GrowthTracker.

        Args:
            iris_core: Optional reference to the IRIS core instance.
            db_path: Optional override for the SQLite database path.
        """
        super().__init__(iris_core=iris_core)
        self._lock = threading.RLock()
        self._db_path = db_path or GROWTH_DB_PATH

        # Core metrics
        self.missions_completed: int = 0
        self.missions_failed: int = 0
        self.skills_learned: List[str] = []
        self.lessons_learned: List[Dict[str, Any]] = []

        # Milestones
        self.milestones: Dict[str, Any] = {
            "next_mission_count": 10,
            "next_skill_count": 5,
            "next_lesson_count": 20,
        }

        # Ensure data directory exists
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._init_db()
        self._load_from_db()

        logger.info(f"GrowthTracker initialized. {self.missions_completed} missions on record.")

    def _init_db(self) -> None:
        """Initialize SQLite database schema."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS missions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_name TEXT,
                    success INTEGER,
                    timestamp TEXT,
                    details TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_name TEXT UNIQUE,
                    learned_at TEXT,
                    source TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lesson TEXT,
                    source TEXT,
                    learned_at TEXT,
                    applied INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def _load_from_db(self) -> None:
        """Load growth data from database."""
        with sqlite3.connect(self._db_path) as conn:
            # Load mission counts
            cursor = conn.execute("SELECT success, COUNT(*) FROM missions GROUP BY success")
            for row in cursor.fetchall():
                success, count = row
                if success:
                    self.missions_completed = count
                else:
                    self.missions_failed = count

            # Load skills
            cursor = conn.execute("SELECT skill_name FROM skills")
            self.skills_learned = [row[0] for row in cursor.fetchall()]

            # Load lessons
            cursor = conn.execute("SELECT lesson, source, learned_at, applied FROM lessons")
            for row in cursor.fetchall():
                self.lessons_learned.append({
                    "lesson": row[0],
                    "source": row[1],
                    "learned_at": row[2],
                    "applied": bool(row[3]),
                })

    def record_mission_outcome(self, mission: str, success: bool, details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Record the outcome of a mission.

        Args:
            mission: Name or description of the mission.
            success: True if mission succeeded, False if failed.
            details: Optional details dictionary.

        Returns:
            True if mission was recorded.
        """
        with self._lock:
            try:
                with sqlite3.connect(self._db_path) as conn:
                    conn.execute("""
                        INSERT INTO missions (mission_name, success, timestamp, details)
                        VALUES (?, ?, ?, ?)
                    """, (
                        mission,
                        1 if success else 0,
                        datetime.utcnow().isoformat(),
                        json.dumps(details or {}),
                    ))
                    conn.commit()

                if success:
                    self.missions_completed += 1
                else:
                    self.missions_failed += 1

                # Auto-record lesson from failure
                if not success:
                    self.record_lesson(
                        f"Mission '{mission}' failed. Analyze and adapt.",
                        f"mission_{mission}"
                    )

                logger.info(f"Mission recorded: {mission} -> {'SUCCESS' if success else 'FAILED'}")
                return True

            except Exception as e:
                logger.error(f"Failed to record mission: {e}")
                return False

    def record_lesson(self, lesson: str, source: str) -> bool:
        """
        Record a lesson learned.

        Args:
            lesson: The lesson text.
            source: Where the lesson came from (mission name, event, etc.).

        Returns:
            True if lesson was recorded.
        """
        with self._lock:
            try:
                # Check for duplicate
                for existing in self.lessons_learned:
                    if existing["lesson"] == lesson:
                        logger.debug(f"Duplicate lesson skipped: {lesson[:50]}...")
                        return False

                entry = {
                    "lesson": lesson,
                    "source": source,
                    "learned_at": datetime.utcnow().isoformat(),
                    "applied": False,
                }

                with sqlite3.connect(self._db_path) as conn:
                    conn.execute("""
                        INSERT INTO lessons (lesson, source, learned_at, applied)
                        VALUES (?, ?, ?, ?)
                    """, (lesson, source, entry["learned_at"], 0))
                    conn.commit()

                self.lessons_learned.append(entry)
                logger.info(f"Lesson recorded from {source}: {lesson[:80]}...")
                return True

            except Exception as e:
                logger.error(f"Failed to record lesson: {e}")
                return False

    def learn_skill(self, skill: str, source: str = "unknown") -> bool:
        """
        Record a new skill learned.

        Args:
            skill: Name of the skill.
            source: Where the skill was learned from.

        Returns:
            True if skill was recorded, False if already known.
        """
        with self._lock:
            if skill in self.skills_learned:
                logger.debug(f"Skill already known: {skill}")
                return False

            try:
                with sqlite3.connect(self._db_path) as conn:
                    conn.execute("""
                        INSERT OR IGNORE INTO skills (skill_name, learned_at, source)
                        VALUES (?, ?, ?)
                    """, (skill, datetime.utcnow().isoformat(), source))
                    conn.commit()

                self.skills_learned.append(skill)
                logger.info(f"New skill learned: {skill} (from {source})")
                return True

            except Exception as e:
                logger.error(f"Failed to record skill: {e}")
                return False

    def get_growth_report(self) -> Dict[str, Any]:
        """
        Return a full evolution summary.

        Returns:
            Dictionary with all growth metrics.
        """
        with self._lock:
            success_rate = 0.0
            total = self.missions_completed + self.missions_failed
            if total > 0:
                success_rate = self.missions_completed / total

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
        """
        Return next milestone targets and progress.

        Returns:
            Dictionary with current progress and next targets.
        """
        with self._lock:
            total_missions = self.missions_completed + self.missions_failed
            return {
                "missions": {
                    "current": total_missions,
                    "next_target": self.milestones["next_mission_count"],
                    "progress": round(total_missions / self.milestones["next_mission_count"], 3) if self.milestones["next_mission_count"] > 0 else 1.0,
                },
                "skills": {
                    "current": len(self.skills_learned),
                    "next_target": self.milestones["next_skill_count"],
                    "progress": round(len(self.skills_learned) / self.milestones["next_skill_count"], 3) if self.milestones["next_skill_count"] > 0 else 1.0,
                },
                "lessons": {
                    "current": len(self.lessons_learned),
                    "next_target": self.milestones["next_lesson_count"],
                    "progress": round(len(self.lessons_learned) / self.milestones["next_lesson_count"], 3) if self.milestones["next_lesson_count"] > 0 else 1.0,
                },
            }

    def set_milestone(self, category: str, target: int) -> bool:
        """
        Set a new milestone target.

        Args:
            category: Category (missions, skills, lessons).
            target: Target number.

        Returns:
            True if milestone was set.
        """
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
        """Return health status of the GrowthTracker module."""
        with self._lock:
            base = super().health_check()
            base.update(self.get_growth_report())
            base.update({
                "milestones": self.milestones,
                "db_path": self._db_path,
            })
            return base


# Usage example
if __name__ == "__main__":
    growth = GrowthTracker()
    print("=" * 60)
    print("GROWTH TRACKER TESTS:")
    print("=" * 60)

    # Record missions
    growth.record_mission_outcome("secure_website", True, {"vulnerabilities_found": 3})
    growth.record_mission_outcome("deploy_api", True)
    growth.record_mission_outcome("fix_database", False, {"error": "connection_timeout"})

    # Learn skills
    growth.learn_skill("SSL certificate management", "mission_secure_website")
    growth.learn_skill("API rate limiting", "mission_deploy_api")
    growth.learn_skill("Database connection pooling", "mission_fix_database")

    # Record lessons
    growth.record_lesson("Always verify SSL certs before deployment", "mission_secure_website")
    growth.record_lesson("Connection pooling prevents timeout failures", "mission_fix_database")

    print(f"\nGrowth Report:")
    print(growth.get_growth_report())

    print(f"\nMilestone Status:")
    print(growth.get_milestone_status())

    print(f"\nSkills: {growth.get_skills()}")
    print(f"\nLessons: {len(growth.get_lessons())} total")

    print("=" * 60)
    print("HEALTH CHECK:")
    print(growth.health_check())


__all__ = ["GrowthTracker"]
