"""
persona/relationship_map.py — IRIS's Relationship Map

PROPER ARCHITECTURE:
- When PostgreSQL (Supabase) is available → stores ALL user profiles in
  the kv_store table (namespace="relationship_map"). Persistent across
  cold starts, shared across instances.
- When PostgreSQL is NOT available (local dev) → uses SQLite file at
  data/relationships.db.
- NEVER uses /tmp/ for persistent data.
- NEVER silently discards data — logs errors with context.
"""

import json
import logging
import os
import threading
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional

from . import IRISConnectable

logger = logging.getLogger("iris.persona.relationship_map")

DB_PATH = os.getenv("IRIS_RELATIONSHIP_DB", "data/relationships.db")


class UserProfile:
    """Represents a single user's profile in IRIS's relationship map."""

    def __init__(self, user_id: str, metadata: Optional[Dict[str, Any]] = None):
        self.user_id = user_id
        self.trust_level: float = 0.0
        self.interaction_count: int = 0
        self.first_seen: str = datetime.utcnow().isoformat()
        self.last_seen: str = self.first_seen
        self.metadata: Dict[str, Any] = metadata or {}
        self.flags: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "trust_level": self.trust_level,
            "interaction_count": self.interaction_count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "metadata": self.metadata,
            "flags": self.flags,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UserProfile":
        p = cls(d["user_id"], d.get("metadata", {}))
        p.trust_level = d.get("trust_level", 0.0)
        p.interaction_count = d.get("interaction_count", 0)
        p.first_seen = d.get("first_seen", p.first_seen)
        p.last_seen = d.get("last_seen", p.last_seen)
        p.flags = d.get("flags", [])
        return p


class RelationshipMap(IRISConnectable):
    """
    RelationshipMap — IRIS's knowledge of everyone she has interacted with.

    Tracks trust levels, interaction counts, flags, and metadata for
    each user. The creator (Infinite Vybeflix) has unconditional trust.
    """

    def __init__(
        self,
        iris_core: Any = None,
        db_path: Optional[str] = None,
    ):
        super().__init__(iris_core=iris_core)
        self._lock = threading.RLock()
        self._db_path = db_path or DB_PATH
        self.users: Dict[str, UserProfile] = {}
        self.creator_id: str = os.getenv("IRIS_CREATOR_ID", "infinite_vybeflix")

        # Check if PostgreSQL is available for persistent storage
        self._use_postgres = False
        try:
            from core.db import db
            if db._db_available and db.use_postgres:
                self._use_postgres = True
                self._db = db
                logger.info("RelationshipMap: using PostgreSQL (persistent)")
        except Exception as e:
            logger.debug(f"RelationshipMap: PostgreSQL not available: {e}")

        if self._use_postgres:
            self._load_from_db()
        else:
            self._init_sqlite()
            self._load_from_db()

        logger.info(f"RelationshipMap initialized. {len(self.users)} users loaded.")

    # ─── SQLite storage (local dev only) ────────────────────────────

    def _init_sqlite(self) -> None:
        """Initialize SQLite database schema (local dev only)."""
        try:
            db_dir = os.path.dirname(self._db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    trust_level REAL DEFAULT 0.0,
                    interaction_count INTEGER DEFAULT 0,
                    first_seen TEXT,
                    last_seen TEXT,
                    metadata TEXT,
                    flags TEXT
                )""")
                conn.commit()
        except sqlite3.OperationalError as e:
            logger.error(f"RelationshipMap: SQLite init failed at {self._db_path}: {e}. "
                         f"Relationship data will not persist.")
        except Exception as e:
            logger.error(f"RelationshipMap: unexpected SQLite init error: {e}")

    def _load_from_db(self) -> None:
        """Load all user profiles from storage."""
        if self._use_postgres:
            try:
                data = self._db.get_json("relationship_map", "users")
                if data and isinstance(data, dict):
                    for user_id, profile_dict in data.items():
                        self.users[user_id] = UserProfile.from_dict(profile_dict)
            except Exception as e:
                logger.error(f"RelationshipMap: failed to load from PostgreSQL: {e}")
        else:
            try:
                with sqlite3.connect(self._db_path) as conn:
                    cursor = conn.execute("SELECT * FROM users")
                    for row in cursor.fetchall():
                        user_id, trust, count, first, last, meta, flags = row
                        profile = UserProfile(user_id)
                        profile.trust_level = trust
                        profile.interaction_count = count
                        profile.first_seen = first
                        profile.last_seen = last
                        profile.metadata = json.loads(meta) if meta else {}
                        profile.flags = json.loads(flags) if flags else []
                        self.users[user_id] = profile
            except sqlite3.OperationalError as e:
                logger.error(f"RelationshipMap: SQLite load failed: {e}. "
                             f"Starting with empty relationship map.")
            except Exception as e:
                logger.error(f"RelationshipMap: unexpected load error: {e}")

    def _save_user(self, user_id: str) -> None:
        """Save or update a single user in storage."""
        if user_id not in self.users:
            logger.error(f"RelationshipMap: cannot save — user {user_id} not in memory")
            return
        profile = self.users[user_id]

        if self._use_postgres:
            try:
                # Save the entire users dict as JSON (for simplicity + consistency)
                all_users = {uid: p.to_dict() for uid, p in self.users.items()}
                self._db.store_json("relationship_map", "users", all_users)
            except Exception as e:
                logger.error(f"RelationshipMap: failed to save user {user_id} to PostgreSQL: {e}")
        else:
            try:
                with sqlite3.connect(self._db_path) as conn:
                    conn.execute("""
                    INSERT OR REPLACE INTO users
                    (user_id, trust_level, interaction_count, first_seen, last_seen, metadata, flags)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        profile.user_id,
                        profile.trust_level,
                        profile.interaction_count,
                        profile.first_seen,
                        profile.last_seen,
                        json.dumps(profile.metadata),
                        json.dumps(profile.flags),
                    ))
                    conn.commit()
            except sqlite3.OperationalError as e:
                logger.error(f"RelationshipMap: failed to save user {user_id} to SQLite: {e}. "
                             f"Data will be lost on restart.")
            except Exception as e:
                logger.error(f"RelationshipMap: unexpected save error for user {user_id}: {e}")

    # ─── Public API ──────────────────────────────────────────────────

    def add_user(self, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Add a new user. Returns True if added, False if already exists."""
        with self._lock:
            if user_id in self.users:
                logger.debug(f"User {user_id} already exists in relationship map.")
                return False
            profile = UserProfile(user_id, metadata)
            self.users[user_id] = profile
            self._save_user(user_id)
            logger.info(f"New user added: {user_id}")
            return True

    def update_trust(self, user_id: str, delta: float) -> bool:
        """Adjust trust by delta. Returns True if updated, False if user not found."""
        with self._lock:
            if user_id not in self.users:
                logger.warning(f"Cannot update trust: user {user_id} not found.")
                return False
            profile = self.users[user_id]
            old_trust = profile.trust_level
            profile.trust_level = max(0.0, min(1.0, profile.trust_level + delta))
            profile.interaction_count += 1
            profile.last_seen = datetime.utcnow().isoformat()
            self._save_user(user_id)
            logger.info(f"Trust updated for {user_id}: {old_trust:.3f} -> {profile.trust_level:.3f}")
            return True

    def get_trust_level(self, user_id: str) -> float:
        """Get trust level. Returns 0.0 for unknown users."""
        with self._lock:
            if user_id not in self.users:
                return 0.0
            return self.users[user_id].trust_level

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get full profile dict. Returns empty dict if unknown."""
        with self._lock:
            if user_id not in self.users:
                return {}
            return self.users[user_id].to_dict()

    def is_creator(self, user_id: str) -> bool:
        """Check if user is the creator."""
        with self._lock:
            return user_id == self.creator_id

    def is_intruder(self, user_id: str) -> bool:
        """Check if user is flagged as intruder or has very low trust."""
        with self._lock:
            if user_id not in self.users:
                return True  # Unknown users are treated with suspicion
            profile = self.users[user_id]
            return "intruder" in profile.flags or profile.trust_level < 0.1

    def flag_user(self, user_id: str, flag: str) -> bool:
        """Add a behavioral flag. Returns True if added, False if user not found."""
        with self._lock:
            if user_id not in self.users:
                return False
            profile = self.users[user_id]
            if flag not in profile.flags:
                profile.flags.append(flag)
                self._save_user(user_id)
                logger.warning(f"Flag '{flag}' added to user {user_id}")
            return True

    def unflag_user(self, user_id: str, flag: str) -> bool:
        """Remove a behavioral flag. Returns True if removed."""
        with self._lock:
            if user_id not in self.users:
                return False
            profile = self.users[user_id]
            if flag in profile.flags:
                profile.flags.remove(flag)
                self._save_user(user_id)
                logger.info(f"Flag '{flag}' removed from user {user_id}")
            return True

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all user profiles."""
        with self._lock:
            return [p.to_dict() for p in self.users.values()]

    def health_check(self) -> Dict[str, Any]:
        """Return health status."""
        with self._lock:
            base = super().health_check() if hasattr(super(), "health_check") else {}
            base.update({
                "total_users": len(self.users),
                "creator_id": self.creator_id,
                "backend": "postgresql" if self._use_postgres else "sqlite",
            })
            return base
