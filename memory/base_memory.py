"""
IRIS v1.0 — BaseMemory
Abstract base class for all memory systems.

PROPER ARCHITECTURE:
- When PostgreSQL (Supabase) is available → uses db.store_kv()/get_kv()
  for ALL persistent storage. No files, no SQLite, no /tmp/.
- When PostgreSQL is NOT available (local dev) → uses SQLite files.
- NEVER crashes on read-only filesystems (Vercel serverless).

Every memory module in IRIS inherits from BaseMemory.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("iris.memory.base")


class IRISConnectable:
    """Mixin for objects that can be connected to the IRIS core."""
    def __init__(self, iris_core=None):
        self.iris_core = iris_core


class BaseMemory(IRISConnectable, ABC):
    """Base class for all IRIS memory systems."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        iris_core=None,
        module_name: str = "memory",
    ) -> None:
        super().__init__(iris_core=iris_core)
        self.module_name = module_name
        self._lock = threading.RLock()
        self.status = "initializing"

        # Check if PostgreSQL is available via core/db
        self._use_postgres = False
        try:
            from core.db import db
            if db._db_available and db.use_postgres:
                self._use_postgres = True
                self._db = db
                logger.info(f"BaseMemory [{module_name}]: using PostgreSQL (persistent)")
        except Exception:
            pass

        if not self._use_postgres:
            # Fall back to SQLite (local dev only)
            raw_path = db_path or os.getenv("IRIS_MEMORY_DB", "iris_memory.db")
            if not os.path.isabs(raw_path) and os.environ.get("VERCEL"):
                raw_path = os.path.join("/tmp/iris-data", raw_path)
            self.db_path = raw_path
            self.use_sqlite = True
            self._conn: Optional[sqlite3.Connection] = None
            self._init_storage()
            logger.info(f"BaseMemory [{module_name}]: using SQLite at {self.db_path}")
        else:
            # PostgreSQL — set the attributes subclasses expect to None
            # so they don't crash with AttributeError. Subclass methods
            # that check `if self._conn:` will skip the SQLite path and
            # fall through to the PostgreSQL path via _execute_sql().
            self.db_path = "postgresql"
            self.use_sqlite = False
            self._conn = None

        self.status = "ready"

    def _init_storage(self) -> None:
        """Initialize SQLite storage (local dev only — PostgreSQL path doesn't need this)."""
        try:
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA foreign_keys=ON;")
            self._create_tables()
            self.use_sqlite = True
        except Exception as exc:
            logger.warning(f"SQLite init failed ({exc}), using in-memory.")
            self.use_sqlite = False
            self._conn = None

    def _create_tables(self) -> None:
        """Create the memory table in SQLite (local dev only)."""
        if self._conn:
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS memory_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # SQL abstraction layer — subclasses use these instead of self._conn
    # Routes to PostgreSQL (persistent) or SQLite (local dev) automatically.
    # ------------------------------------------------------------------

    def _execute_sql(self, query: str, params: tuple = ()) -> Optional[Any]:
        """Execute SQL — PostgreSQL or SQLite depending on backend.

        Handles ? → %s placeholder conversion for PostgreSQL.
        Subclasses should use this instead of self._conn.execute().
        """
        try:
            if self._use_postgres:
                query = query.replace("?", "%s")
                return self._db._execute(query, params)
            elif self._conn:
                cursor = self._conn.execute(query, params)
                self._conn.commit()
                return cursor
        except Exception as e:
            logger.debug(f"[{self.module_name}] _execute_sql failed: {e}")
        return None

    def _fetchall_sql(self, query: str, params: tuple = ()) -> List[Dict]:
        """Fetch all rows — PostgreSQL or SQLite."""
        try:
            if self._use_postgres:
                query = query.replace("?", "%s")
                return self._db._fetchall(query, params) or []
            elif self._conn:
                cursor = self._conn.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows] if rows else []
        except Exception as e:
            logger.debug(f"[{self.module_name}] _fetchall_sql failed: {e}")
        return []

    def _fetchone_sql(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """Fetch one row — PostgreSQL or SQLite."""
        try:
            if self._use_postgres:
                query = query.replace("?", "%s")
                return self._db._fetchone(query, params)
            elif self._conn:
                cursor = self._conn.execute(query, params)
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.debug(f"[{self.module_name}] _fetchone_sql failed: {e}")
        return None

    # ------------------------------------------------------------------
    # Storage operations — abstract interface that works with both
    # PostgreSQL (via core/db) and SQLite (local dev)
    # ------------------------------------------------------------------

    def store(self, key: str, value: str, metadata: Optional[str] = None) -> bool:
        """Store a key-value pair."""
        with self._lock:
            try:
                if self._use_postgres:
                    self._db.store_kv(self.module_name, key, value, metadata)
                elif self._conn:
                    ph = "?"
                    self._conn.execute(
                        f"DELETE FROM memory_store WHERE key = {ph}", (key,)
                    )
                    self._conn.execute(
                        f"INSERT INTO memory_store (key, value, metadata) VALUES ({ph}, {ph}, {ph})",
                        (key, value, metadata)
                    )
                    self._conn.commit()
                return True
            except Exception as e:
                logger.error(f"[{self.module_name}] store failed: {e}")
                return False

    def get(self, key: str) -> Optional[str]:
        """Get a value by key."""
        with self._lock:
            try:
                if self._use_postgres:
                    return self._db.get_kv(self.module_name, key)
                elif self._conn:
                    row = self._conn.execute(
                        "SELECT value FROM memory_store WHERE key = ?", (key,)
                    ).fetchone()
                    return row["value"] if row else None
            except Exception as e:
                logger.error(f"[{self.module_name}] get failed: {e}")
            return None

    def get_all(self) -> Dict[str, str]:
        """Get all key-value pairs."""
        with self._lock:
            try:
                if self._use_postgres:
                    return self._db.get_all_kv(self.module_name)
                elif self._conn:
                    rows = self._conn.execute(
                        "SELECT key, value FROM memory_store"
                    ).fetchall()
                    return {row["key"]: row["value"] for row in rows} if rows else {}
            except Exception as e:
                logger.error(f"[{self.module_name}] get_all failed: {e}")
            return {}

    def delete(self, key: str) -> bool:
        """Delete a key-value pair."""
        with self._lock:
            try:
                if self._use_postgres:
                    self._db.delete_kv(self.module_name, key)
                elif self._conn:
                    self._conn.execute(
                        "DELETE FROM memory_store WHERE key = ?", (key,)
                    )
                    self._conn.commit()
                return True
            except Exception as e:
                logger.error(f"[{self.module_name}] delete failed: {e}")
                return False

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Search values containing the query string."""
        with self._lock:
            try:
                if self._use_postgres:
                    ph = "%s"
                    rows = self._db._fetchall(
                        f"SELECT key, value, metadata FROM kv_store WHERE namespace = {ph} AND value LIKE {ph} LIMIT {ph}",
                        (self.module_name, f"%{query}%", limit)
                    )
                    return rows if rows else []
                elif self._conn:
                    rows = self._conn.execute(
                        "SELECT key, value, metadata FROM memory_store WHERE value LIKE ? LIMIT ?",
                        (f"%{query}%", limit)
                    ).fetchall()
                    return [dict(row) for row in rows] if rows else []
            except Exception as e:
                logger.error(f"[{self.module_name}] search failed: {e}")
            return []

    def health(self) -> Dict[str, Any]:
        """Return health status."""
        return {
            "module": self.module_name,
            "backend": "postgresql" if self._use_postgres else ("sqlite" if self._conn else "none"),
            "status": self.status,
        }

    def shutdown(self) -> None:
        """Clean up resources."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None
        self.status = "shutdown"
