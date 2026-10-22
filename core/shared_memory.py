"""
Aevibron Agent Corps — Shared Memory
Common workspace for agents to share findings, data, and intermediate results.

Author: IRIS v1.0
"""

import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional


class SharedMemory:
    """
    SharedMemory — The collective consciousness of the Aevibron Agent Corps.

    Provides a mission-scoped key-value store with search capabilities,
    allowing agents to share findings, data, and intermediate results
    in a thread-safe manner.

    Features:
    - Mission-scoped storage (isolated per mission)
    - Full-text search across stored values
    - Persistence to disk
    - TTL (time-to-live) support for entries
    - Metadata tracking (who stored, when, tags)
    - Thread-safe operations

    Attributes:
        _store (dict): Nested dict {mission_id: {key: value_dict}}
        _lock (threading.RLock): Thread-safe lock.
        _logger (logging.Logger): Logger instance.
        _persistence_path (str): Path for persistence.
    """

    def __init__(self, persistence_path: Optional[str] = None):
        self._store: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        self._lock = threading.RLock()
        self._logger = logging.getLogger("Aevibron.SharedMemory")
        self._logger.setLevel(logging.DEBUG)

        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

        if persistence_path is None:
            try:
                from config import config
                default_dir = os.path.join(config.DATA_DIR, "agents")
                os.makedirs(default_dir, exist_ok=True)
                persistence_path = os.path.join(default_dir, "shared_memory.json")
            except Exception:
                persistence_path = os.path.join(os.getcwd(), "data", "agents", "shared_memory.json")
                os.makedirs(os.path.dirname(persistence_path), exist_ok=True)
        self._persistence_path = persistence_path
        Path(self._persistence_path).parent.mkdir(parents=True, exist_ok=True)

        self._logger.info("[SharedMemory] Collective consciousness initialized.")

    def store(
        self,
        key: str,
        value: Any,
        mission_id: str = "global",
        agent_name: str = "unknown",
        tags: Optional[List[str]] = None,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Store a value in shared memory.

        Args:
            key: Unique identifier for the value.
            value: The data to store (any JSON-serializable type).
            mission_id: Mission context for isolation.
            agent_name: Name of the agent storing the value.
            tags: Optional list of tags for categorization.
            ttl_seconds: Optional time-to-live in seconds.

        Returns:
            bool: True if stored successfully.
        """
        try:
            entry = {
                "value": value,
                "stored_by": agent_name,
                "stored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "tags": tags or [],
                "ttl_seconds": ttl_seconds,
                "expires_at": time.time() + ttl_seconds if ttl_seconds else None,
                "access_count": 0,
                "last_accessed": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

            with self._lock:
                self._store[mission_id][key] = entry

            self._logger.debug(f"[SharedMemory] {agent_name} stored '{key}' in mission '{mission_id}'")
            return True

        except Exception as e:
            self._logger.error(f"[SharedMemory] Store failed for key '{key}': {e}")
            return False

    def retrieve(self, key: str, mission_id: str = "global") -> Optional[Any]:
        """
        Retrieve a value from shared memory.

        Args:
            key: The key to retrieve.
            mission_id: Mission context.

        Returns:
            Any: The stored value, or None if not found or expired.
        """
        with self._lock:
            mission_store = self._store.get(mission_id, {})
            entry = mission_store.get(key)

            if not entry:
                return None

            # Check TTL
            if entry.get("expires_at") and time.time() > entry["expires_at"]:
                del mission_store[key]
                self._logger.debug(f"[SharedMemory] Key '{key}' expired and removed.")
                return None

            # Update access stats
            entry["access_count"] = entry.get("access_count", 0) + 1
            entry["last_accessed"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            return entry["value"]

    def retrieve_with_meta(self, key: str, mission_id: str = "global") -> Optional[Dict[str, Any]]:
        """
        Retrieve a value along with its metadata.

        Args:
            key: The key to retrieve.
            mission_id: Mission context.

        Returns:
            Dict: Full entry including value and metadata, or None.
        """
        with self._lock:
            mission_store = self._store.get(mission_id, {})
            entry = mission_store.get(key)

            if not entry:
                return None

            if entry.get("expires_at") and time.time() > entry["expires_at"]:
                del mission_store[key]
                return None

            entry["access_count"] = entry.get("access_count", 0) + 1
            entry["last_accessed"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            return dict(entry)

    def search(self, query: str, mission_id: Optional[str] = None, tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search shared memory for entries matching a query.

        Args:
            query: Search string (matched against keys and string values).
            mission_id: If provided, search only this mission. Otherwise search all.
            tags: Optional filter by tags.

        Returns:
            List[Dict]: Matching entries with key and metadata.
        """
        results = []
        query_lower = query.lower()

        with self._lock:
            missions_to_search = [mission_id] if mission_id else list(self._store.keys())

            for mid in missions_to_search:
                mission_store = self._store.get(mid, {})

                for key, entry in list(mission_store.items()):
                    # Check TTL
                    if entry.get("expires_at") and time.time() > entry["expires_at"]:
                        del mission_store[key]
                        continue

                    # Tag filter
                    if tags:
                        entry_tags = set(entry.get("tags", []))
                        if not any(tag in entry_tags for tag in tags):
                            continue

                    # Search in key
                    match = query_lower in key.lower()

                    # Search in value (if string or dict)
                    value = entry.get("value")
                    if isinstance(value, str):
                        match = match or query_lower in value.lower()
                    elif isinstance(value, dict):
                        value_str = json.dumps(value, default=str).lower()
                        match = match or query_lower in value_str
                    elif isinstance(value, list):
                        value_str = json.dumps(value, default=str).lower()
                        match = match or query_lower in value_str

                    if match:
                        results.append({
                            "key": key,
                            "mission_id": mid,
                            "stored_by": entry.get("stored_by"),
                            "stored_at": entry.get("stored_at"),
                            "tags": entry.get("tags", []),
                            "access_count": entry.get("access_count", 0),
                            "value_preview": str(value)[:200] if value is not None else None,
                        })

        self._logger.debug(f"[SharedMemory] Search '{query}' returned {len(results)} results")
        return results

    def list_keys(self, mission_id: str = "global") -> List[str]:
        """
        List all keys in a mission's shared memory.

        Args:
            mission_id: Mission context.

        Returns:
            List[str]: All keys in the mission.
        """
        with self._lock:
            mission_store = self._store.get(mission_id, {})
            # Clean expired entries
            expired = []
            for key, entry in list(mission_store.items()):
                if entry.get("expires_at") and time.time() > entry["expires_at"]:
                    expired.append(key)
            for key in expired:
                del mission_store[key]

            return list(mission_store.keys())

    def delete(self, key: str, mission_id: str = "global") -> bool:
        """
        Delete a key from shared memory.

        Args:
            key: The key to delete.
            mission_id: Mission context.

        Returns:
            bool: True if deleted, False if not found.
        """
        with self._lock:
            mission_store = self._store.get(mission_id, {})
            if key in mission_store:
                del mission_store[key]
                self._logger.debug(f"[SharedMemory] Deleted '{key}' from mission '{mission_id}'")
                return True
            return False

    def clear(self, mission_id: Optional[str] = None) -> None:
        """
        Clear shared memory.

        Args:
            mission_id: If provided, clear only this mission.
                       If None, clear ALL missions.
        """
        with self._lock:
            if mission_id:
                if mission_id in self._store:
                    del self._store[mission_id]
                    self._logger.info(f"[SharedMemory] Cleared mission '{mission_id}'")
            else:
                self._store.clear()
                self._logger.info("[SharedMemory] Cleared all missions.")

    def persist(self) -> bool:
        """
        Save shared memory to disk.

        Returns:
            bool: True if persistence succeeded.
        """
        try:
            with self._lock:
                # Clean expired entries before saving
                for mission_id, mission_store in list(self._store.items()):
                    expired = []
                    for key, entry in list(mission_store.items()):
                        if entry.get("expires_at") and time.time() > entry["expires_at"]:
                            expired.append(key)
                    for key in expired:
                        del mission_store[key]

                data = {
                    "store": dict(self._store),
                    "persisted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }

            with open(self._persistence_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

            self._logger.info(f"[SharedMemory] Persisted to {self._persistence_path}")
            return True

        except Exception as e:
            self._logger.error(f"[SharedMemory] Persistence failed: {e}")
            return False

    def load(self) -> bool:
        """
        Load shared memory from disk.

        Returns:
            bool: True if load succeeded.
        """
        try:
            if not os.path.exists(self._persistence_path):
                self._logger.info("[SharedMemory] No persistence file found. Starting fresh.")
                return False

            with open(self._persistence_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            with self._lock:
                self._store = defaultdict(dict, data.get("store", {}))

            total_entries = sum(len(v) for v in self._store.values())
            self._logger.info(f"[SharedMemory] Loaded {total_entries} entries from persistence.")
            return True

        except Exception as e:
            self._logger.error(f"[SharedMemory] Load failed: {e}")
            return False

    def get_stats(self, mission_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about shared memory.

        Args:
            mission_id: If provided, stats for specific mission only.

        Returns:
            Dict: Statistics about stored data.
        """
        with self._lock:
            if mission_id:
                mission_store = self._store.get(mission_id, {})
                return {
                    "mission_id": mission_id,
                    "total_keys": len(mission_store),
                    "agents_contributed": list(set(
                        entry.get("stored_by", "unknown") for entry in mission_store.values()
                    )),
                    "tags_used": list(set(
                        tag for entry in mission_store.values() for tag in entry.get("tags", [])
                    )),
                }
            else:
                total_keys = sum(len(v) for v in self._store.values())
                all_agents = set()
                all_tags = set()
                for mission_store in self._store.values():
                    for entry in mission_store.values():
                        all_agents.add(entry.get("stored_by", "unknown"))
                        all_tags.update(entry.get("tags", []))

                return {
                    "total_missions": len(self._store),
                    "total_keys": total_keys,
                    "agents_contributed": list(all_agents),
                    "tags_used": list(all_tags),
                }


__all__ = ["SharedMemory"]


# Usage Example:
# mem = SharedMemory()
# mem.store("scan_results", {"ports": [80, 443]}, mission_id="m1", agent_name="SHADOW", tags=["recon"])
# results = mem.retrieve("scan_results", mission_id="m1")
# search_results = mem.search("ports", mission_id="m1")
