"""
IRIS v7.0 — BaseMemory
Abstract base class for all memory systems.

Provides the foundation for persistent, queryable memory with:
- SQLite persistence (JSON file fallback)
- Thread-safe operations via RLock
- Standard result format for all operations
- Graceful degradation on storage failures
- Comprehensive logging

Every memory module in IRIS inherits from BaseMemory.

Usage:
    class MyMemory(BaseMemory):
        def __init__(self, db_path="my_memory.db"):
            super().__init__(db_path=db_path)

        def store(self, key, value, metadata=None):
            return super().store(key, value, metadata)

Author: IRIS Core Team
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
    """Interface contract: every module connects to IRIS core."""

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        self.iris_core = iris_core
        self.status = "idle"
        self._lock = threading.RLock()

    def health_check(self) -> Dict[str, Any]:
        """Return health status: available, degraded, or error."""
        return {
            "status": self.status,
            "module": self.__class__.__name__,
            "available": self.status != "error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def status_report(self) -> Dict[str, Any]:
        """Current operational status."""
        return {
            "module": self.__class__.__name__,
            "status": self.status,
            "iris_connected": self.iris_core is not None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def report(self, finding: Dict[str, Any]) -> None:
        """Send finding to IRIS core or log if unavailable."""
        if self.iris_core:
            self.iris_core.receive_finding(finding)
        else:
            logger.info(f"[{self.__class__.__name__}] {finding}")


class BaseMemory(IRISConnectable, ABC):
    """
    Abstract base for all IRIS memory systems.

    Provides SQLite persistence with JSON fallback, thread-safe operations,
    and a standard result envelope for every operation.

    Attributes:
        db_path: Path to SQLite database (or JSON directory if SQLite fails).
        use_sqlite: Whether SQLite is functional.
        json_dir: Directory for JSON fallback storage.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        iris_core: Optional[Any] = None,
    ) -> None:
        """
        Initialize BaseMemory with storage backend.

        Args:
            db_path: Path to SQLite database. Defaults to env var
                     IRIS_MEMORY_DB or "iris_memory.db".
            iris_core: Reference to IRIS core for reporting.
        """
        super().__init__(iris_core=iris_core)
        self.db_path = db_path or os.getenv("IRIS_MEMORY_DB", "iris_memory.db")
        self.use_sqlite: bool = True
        self.json_dir: str = os.path.splitext(self.db_path)[0] + "_json_fallback"
        self._conn: Optional[sqlite3.Connection] = None
        self._init_storage()
        self.status = "ready"
        logger.info(f"BaseMemory initialized: db={self.db_path}, sqlite={self.use_sqlite}")

    # ------------------------------------------------------------------
    # Storage initialization
    # ------------------------------------------------------------------
    def _init_storage(self) -> None:
        """Initialize SQLite or fall back to JSON directory."""
        try:
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA foreign_keys=ON;")
            self._create_tables()
            self.use_sqlite = True
        except Exception as exc:
            logger.warning(f"SQLite init failed ({exc}), falling back to JSON.")
            self.use_sqlite = False
            self._conn = None
            os.makedirs(self.json_dir, exist_ok=True)

    def _create_tables(self) -> None:
        """Create the generic memory table. Override in subclasses."""
        with self._lock:
            if self._conn:
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_store (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        metadata TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                self._conn.commit()

    # ------------------------------------------------------------------
    # Result envelope
    # ------------------------------------------------------------------
    def _result(
        self,
        success: bool,
        action: str,
        data: Any = None,
        confidence: float = 1.0,
        errors: Optional[List[str]] = None,
        duration_ms: int = 0,
    ) -> Dict[str, Any]:
        """Build a standard result dictionary."""
        return {
            "success": success,
            "module": self.__class__.__name__,
            "action": action,
            "data": data,
            "confidence": confidence,
            "errors": errors or [],
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Core abstract interface (must be implemented by subclasses)
    # ------------------------------------------------------------------
    @abstractmethod
    def store(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Persist data under *key*."""
        ...

    @abstractmethod
    def retrieve(self, key: str) -> Dict[str, Any]:
        """Fetch data by *key*."""
        ...

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Semantic + keyword search."""
        ...

    @abstractmethod
    def update(self, key: str, value: Any) -> Dict[str, Any]:
        """Modify existing entry."""
        ...

    @abstractmethod
    def delete(self, key: str) -> Dict[str, Any]:
        """Remove entry by *key*."""
        ...

    @abstractmethod
    def list_all(self, filter_: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Enumerate entries with optional filtering."""
        ...

    def export(self, format_: str = "json") -> str:
        """Dump all data as JSON string (default) or other format."""
        start = time.perf_counter()
        try:
            items = self.list_all().get("data", [])
            payload = json.dumps(items, indent=2, default=str)
            duration_ms = int((time.perf_counter() - start) * 1000)
            self.report({"action": "export", "format": format_, "count": len(items)})
            return payload
        except Exception as exc:
            logger.error(f"Export failed: {exc}")
            return json.dumps({"error": str(exc)})

    def import_(self, data: str, format_: str = "json") -> Dict[str, Any]:
        """Load data from JSON string (default) or other format."""
        start = time.perf_counter()
        try:
            items = json.loads(data)
            count = 0
            for item in items:
                k = item.get("key")
                v = item.get("value")
                m = item.get("metadata")
                if k is not None:
                    self.store(k, v, m)
                    count += 1
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(
                True, "import", {"imported": count}, duration_ms=duration_ms
            )
        except Exception as exc:
            return self._result(False, "import", errors=[str(exc)])

    # ------------------------------------------------------------------
    # SQLite helpers
    # ------------------------------------------------------------------
    def _sql_execute(self, sql: str, params: tuple = ()) -> List[tuple]:
        """Thread-safe SQL execution returning rows."""
        with self._lock:
            if not self._conn:
                raise RuntimeError("SQLite not available")
            cur = self._conn.execute(sql, params)
            rows = cur.fetchall()
            self._conn.commit()
            return rows

    def _sql_execute_one(self, sql: str, params: tuple = ()) -> Optional[tuple]:
        """Thread-safe SQL execution returning single row or None."""
        rows = self._sql_execute(sql, params)
        return rows[0] if rows else None

    # ------------------------------------------------------------------
    # JSON fallback helpers
    # ------------------------------------------------------------------
    def _json_path(self, key: str) -> str:
        """Safe filename for JSON fallback."""
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
        return os.path.join(self.json_dir, f"{safe}.json")

    def _json_read(self, key: str) -> Optional[Dict[str, Any]]:
        """Read a single JSON fallback file."""
        path = self._json_path(key)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _json_write(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Write a single JSON fallback file."""
        path = self._json_path(key)
        payload = {
            "key": key,
            "value": value,
            "metadata": metadata or {},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

    def _json_delete(self, key: str) -> bool:
        """Delete a single JSON fallback file."""
        path = self._json_path(key)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def _json_list(self) -> List[Dict[str, Any]]:
        """List all JSON fallback entries."""
        items = []
        if not os.path.isdir(self.json_dir):
            return items
        for fname in os.listdir(self.json_dir):
            if fname.endswith(".json"):
                with open(os.path.join(self.json_dir, fname), "r", encoding="utf-8") as f:
                    items.append(json.load(f))
        return items

    def close(self) -> None:
        """Close SQLite connection cleanly."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
                logger.info("BaseMemory SQLite connection closed.")

    def __enter__(self) -> "BaseMemory":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# ------------------------------------------------------------------
# Usage example
# ------------------------------------------------------------------
if __name__ == "__main__":
    # This is an abstract class — instantiate a concrete subclass to use.
    print("BaseMemory is abstract. Inherit from it to build memory modules.")
