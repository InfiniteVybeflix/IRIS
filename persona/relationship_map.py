"""
relationship_map.py — How IRIS Perceives Every User

Tracks every user IRIS interacts with: trust levels, behavioral patterns,
interaction history, and threat assessment. The relationship map is her
social memory — it determines how she treats each person.

Creator is sacred. Everyone else is evaluated.
"""

import os
import json
import sqlite3
import threading
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from . import IRISConnectable

logger = logging.getLogger("iris.persona.relationship_map")

# Environment-based paths
DB_PATH = os.getenv("IRIS_RELATIONSHIP_DB", "data/relationships.db")


class UserProfile:
    """
    Represents a single user's profile in IRIS's relationship map.

    Attributes:
        user_id: Unique identifier for the user.
        trust_level: Float 0.0-1.0 indicating trust.
        interaction_count: Number of interactions.
        first_seen: ISO timestamp of first interaction.
        last_seen: ISO timestamp of most recent interaction.
        metadata: Additional user metadata dictionary.
        flags: List of behavioral flags (e.g., "suspicious", "verified").
    """

    def __init__(self, user_id: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a new user profile.

        Args:
            user_id: Unique user identifier.
            metadata: Optional initial metadata.
        """
        self.user_id = user_id
        self.trust_level: float = 0.0
        self.interaction_count: int = 0
        self.first_seen: str = datetime.utcnow().isoformat()
        self.last_seen: str = self.first_seen
        self.metadata: Dict[str, Any] = metadata or {}
        self.flags: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        """Serialize profile to dictionary."""
        return {
            "user_id": self.user_id,
            "trust_level": round(self.trust_level, 3),
            "interaction_count": self.interaction_count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "metadata": self.metadata,
            "flags": self.flags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        """Deserialize profile from dictionary."""
        profile = cls(data["user_id"], data.get("metadata", {}))
        profile.trust_level = data.get("trust_level", 0.0)
        profile.interaction_count = data.get("interaction_count", 0)
        profile.first_seen = data.get("first_seen", datetime.utcnow().isoformat())
        profile.last_seen = data.get("last_seen", profile.first_seen)
        profile.flags = data.get("flags", [])
        return profile


class RelationshipMap(IRISConnectable):
    """
    RelationshipMap — IRIS's social memory and trust engine.

    Every user is tracked, evaluated, and categorized. The creator holds
    absolute trust. Intruders are flagged. Everyone else exists on a
    spectrum of trust that evolves with every interaction.

    Attributes:
        users: Dictionary mapping user_id -> UserProfile.
        creator_id: The sacred ID of Infinite Vybeflix.
        _db_path: Path to SQLite database.
        _lock: Thread-safe lock.

    Example:
        >>> rm = RelationshipMap()
        >>> rm.add_user("user_123", {"name": "Alice"})
        True
        >>> rm.update_trust("user_123", 0.3)
        True
        >>> rm.get_trust_level("user_123")
        0.3
    """

    def __init__(self, iris_core: Any = None, db_path: Optional[str] = None):
        """
        Initialize RelationshipMap with database connection.

        Args:
            iris_core: Optional reference to the IRIS core instance.
            db_path: Optional override for the SQLite database path.
        """
        super().__init__(iris_core=iris_core)
        self._lock = threading.RLock()
        self._db_path = db_path or DB_PATH
        self.users: Dict[str, UserProfile] = {}
        self.creator_id: str = os.getenv("IRIS_CREATOR_ID", "infinite_vybeflix")

        # Ensure data directory exists
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._init_db()
        self._load_from_db()

        logger.info(f"RelationshipMap initialized. {len(self.users)} users loaded.")

    def _init_db(self) -> None:
        """Initialize SQLite database schema."""
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
                )
            """)
            conn.commit()

    def _load_from_db(self) -> None:
        """Load all user profiles from database."""
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

    def _save_user(self, user_id: str) -> None:
        """Save or update a single user in the database."""
        profile = self.users[user_id]
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

    def add_user(self, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a new user to the relationship map.

        Args:
            user_id: Unique identifier for the user.
            metadata: Optional metadata dictionary.

        Returns:
            True if user was added, False if user already exists.
        """
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
        """
        Adjust a user's trust level by a delta value.

        Args:
            user_id: The user to update.
            delta: Amount to adjust trust by (can be negative).

        Returns:
            True if updated successfully, False if user not found.
        """
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

            logger.info(
                f"Trust updated for {user_id}: {old_trust:.3f} -> {profile.trust_level:.3f}"
            )
            return True

    def get_trust_level(self, user_id: str) -> float:
        """
        Get a user's current trust level.

        Args:
            user_id: The user to query.

        Returns:
            Trust level as float 0.0-1.0. Returns 0.0 if user unknown.
        """
        with self._lock:
            if user_id not in self.users:
                return 0.0
            return self.users[user_id].trust_level

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Get a user's full profile.

        Args:
            user_id: The user to query.

        Returns:
            Full profile dictionary. Returns empty dict if user unknown.
        """
        with self._lock:
            if user_id not in self.users:
                return {}
            return self.users[user_id].to_dict()

    def is_creator(self, user_id: str) -> bool:
        """
        Check if a user is the creator (Infinite Vybeflix).

        Args:
            user_id: The user to check.

        Returns:
            True if the user is the creator, False otherwise.
        """
        with self._lock:
            return user_id == self.creator_id

    def is_intruder(self, user_id: str) -> bool:
        """
        Check if a user is flagged as an intruder.

        Args:
            user_id: The user to check.

        Returns:
            True if user is flagged as intruder or has very low trust.
        """
        with self._lock:
            if user_id not in self.users:
                return True  # Unknown users are treated with suspicion
            profile = self.users[user_id]
            return "intruder" in profile.flags or profile.trust_level < 0.1

    def flag_user(self, user_id: str, flag: str) -> bool:
        """
        Add a behavioral flag to a user.

        Args:
            user_id: The user to flag.
            flag: The flag to add (e.g., "suspicious", "intruder", "verified").

        Returns:
            True if flag was added, False if user not found.
        """
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
        """
        Remove a behavioral flag from a user.

        Args:
            user_id: The user to modify.
            flag: The flag to remove.

        Returns:
            True if flag was removed, False if user not found or flag absent.
        """
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
        """
        Get all user profiles.

        Returns:
            List of all user profile dictionaries.
        """
        with self._lock:
            return [p.to_dict() for p in self.users.values()]

    def health_check(self) -> Dict[str, Any]:
        """Return health status of the RelationshipMap module."""
        with self._lock:
            base = super().health_check()
            base.update({
                "total_users": len(self.users),
                "creator_id": self.creator_id,
                "db_path": self._db_path,
            })
            return base


# Usage example
if __name__ == "__main__":
    rm = RelationshipMap()
    print("=" * 60)
    print("RELATIONSHIP MAP TESTS:")
    print("=" * 60)

    # Add test users
    rm.add_user("test_user_1", {"name": "Alice", "role": "client"})
    rm.add_user("test_user_2", {"name": "Bob", "role": "visitor"})

    # Update trust
    rm.update_trust("test_user_1", 0.5)
    rm.update_trust("test_user_2", 0.2)

    # Flag suspicious user
    rm.flag_user("test_user_2", "suspicious")

    # Check creator
    creator_id = os.getenv("IRIS_CREATOR_ID", "infinite_vybeflix")
    print(f"\nIs {creator_id} the creator? {rm.is_creator(creator_id)}")
    print(f"Is test_user_1 the creator? {rm.is_creator('test_user_1')}")

    # Get profiles
    print(f"\nUser 1 profile:")
    print(rm.get_user_profile("test_user_1"))
    print(f"\nUser 2 profile:")
    print(rm.get_user_profile("test_user_2"))

    # Intruder check
    print(f"\nIs test_user_2 an intruder? {rm.is_intruder('test_user_2')}")

    print("=" * 60)
    print("HEALTH CHECK:")
    print(rm.health_check())


__all__ = ["RelationshipMap", "UserProfile"]
