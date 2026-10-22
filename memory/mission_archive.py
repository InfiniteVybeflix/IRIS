"""
IRIS v1.0 — MissionArchive
Complete mission logs with outcomes.

Archives every mission with full details, enables search across
all missions, timeline reconstruction, statistics, comparison,
and lesson extraction.

Features:
- Archive complete mission records
- Retrieve mission by ID
- Search missions with filters
- Reconstruct mission timeline
- Aggregate mission statistics
- Compare missions side-by-side
- Extract lessons learned

Storage:
    SQLite table `missions` (JSON fallback).

Usage:
    ma = MissionArchive()
    mid = ma.archive_mission({"id": "m-001", "agent": "Alpha", ...})
    mission = ma.get_mission("m-001")
    stats = ma.get_mission_stats()
    lessons = ma.extract_lessons("m-001")

Author: IRIS Core Team
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .base_memory import BaseMemory

logger = logging.getLogger("iris.memory.mission_archive")


class MissionArchive(BaseMemory):
    """
    Complete mission archive with search, timeline, and lesson extraction.

    Every mission is stored with full context, enabling retrospective
    analysis and continuous improvement.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        iris_core: Optional[Any] = None,
    ) -> None:
        """
        Initialize MissionArchive.

        Args:
            db_path: Path to SQLite database. Defaults to env var
                     IRIS_MISSION_ARCHIVE_DB or "iris_mission_archive.db".
            iris_core: Reference to IRIS core.
        """
        super().__init__(
            db_path=db_path or os.getenv("IRIS_MISSION_ARCHIVE_DB", "iris_mission_archive.db"),
            iris_core=iris_core,
        )
        self._create_mission_tables()

    def _create_mission_tables(self) -> None:
        """Create mission archive tables."""
        with self._lock:
                self._execute_sql(
                    """
                    CREATE TABLE IF NOT EXISTS missions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        mission_id TEXT NOT NULL UNIQUE,
                        agent_name TEXT,
                        mission_type TEXT,
                        description TEXT,
                        tasks TEXT NOT NULL,
                        outcomes TEXT NOT NULL,
                        timeline TEXT,
                        metadata TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                self._execute_sql(
                    "CREATE INDEX IF NOT EXISTS idx_mission_type ON missions(mission_type)"
                )
                self._execute_sql(
                    "CREATE INDEX IF NOT EXISTS idx_agent ON missions(agent_name)"
                )
                
    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------
    def store(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Store a mission. Value must be a mission dict."""
        if not isinstance(value, dict):
            return self._result(False, "store", errors=["Value must be a mission dict"])
        return self.archive_mission(value)

    def retrieve(self, key: str) -> Dict[str, Any]:
        """Retrieve a mission by mission_id."""
        return self.get_mission(key)

    def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search missions by description, type, or agent."""
        start = time.perf_counter()
        try:
            results = []
            if self._use_postgres or self.use_sqlite:
                rows = self._sql_execute(
                    """
                    SELECT * FROM missions
                    WHERE description LIKE ? OR mission_type LIKE ? OR agent_name LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (f"%{query}%", f"%{query}%", f"%{query}%", limit),
                )
                for row in rows:
                    results.append(self._row_to_dict(row))
            else:
                for item in self._json_list():
                    if any(query.lower() in str(v).lower() for v in item.values()):
                        results.append(item)
                    if len(results) >= limit:
                        break
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "search", results, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "search", errors=[str(exc)])

    def update(self, key: str, value: Any) -> Dict[str, Any]:
        """Update mission outcomes by mission_id."""
        start = time.perf_counter()
        try:
            if self._use_postgres or self.use_sqlite:
                self._sql_execute(
                    "UPDATE missions SET outcomes = ? WHERE mission_id = ?",
                    (json.dumps(value, default=str), key),
                )
            else:
                data = self._json_read(key)
                if data:
                    data["value"]["outcomes"] = value
                    data["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self._json_write(key, data["value"], data.get("metadata"))
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "update", duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "update", errors=[str(exc)])

    def delete(self, key: str) -> Dict[str, Any]:
        """Delete a mission by mission_id."""
        start = time.perf_counter()
        try:
            if self._use_postgres or self.use_sqlite:
                self._sql_execute("DELETE FROM missions WHERE mission_id = ?", (key,))
            else:
                self._json_delete(key)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "delete", duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "delete", errors=[str(exc)])

    def list_all(self, filter_: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """List all missions with optional filter."""
        start = time.perf_counter()
        try:
            results = []
            if self._use_postgres or self.use_sqlite:
                sql = "SELECT * FROM missions"
                params = []
                conditions = []
                if filter_:
                    for k, v in filter_.items():
                        if k in ("mission_type", "agent_name", "mission_id"):
                            conditions.append(f"{k} = ?")
                            params.append(v)
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
                sql += " ORDER BY created_at DESC"
                rows = self._sql_execute(sql, tuple(params))
                for row in rows:
                    results.append(self._row_to_dict(row))
            else:
                for item in self._json_list():
                    if filter_:
                        match = True
                        for k, v in filter_.items():
                            if item.get(k) != v:
                                match = False
                                break
                        if not match:
                            continue
                    results.append(item)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "list_all", results, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "list_all", errors=[str(exc)])

    def _row_to_dict(self, row: tuple) -> Dict[str, Any]:
        """Convert SQLite row to mission dict."""
        return {
            "id": row[0],
            "mission_id": row[1],
            "agent_name": row[2],
            "mission_type": row[3],
            "description": row[4],
            "tasks": json.loads(row[5]) if row[5] else [],
            "outcomes": json.loads(row[6]) if row[6] else {},
            "timeline": json.loads(row[7]) if row[7] else [],
            "metadata": json.loads(row[8]) if row[8] else {},
            "created_at": row[9],
        }

    # ------------------------------------------------------------------
    # Mission-specific methods
    # ------------------------------------------------------------------
    def archive_mission(self, mission: Dict[str, Any]) -> Dict[str, Any]:
        """
        Archive a complete mission record.

        Args:
            mission: Dict with keys: id, agent_name, mission_type,
                     description, tasks, outcomes, timeline, metadata.

        Returns:
            Standard result with generated mission_id.
        """
        start = time.perf_counter()
        try:
            mission_id = mission.get("id", f"mission_{int(time.time() * 1000)}")
            agent = mission.get("agent_name", "unknown")
            mtype = mission.get("mission_type", "general")
            desc = mission.get("description", "")
            tasks = json.dumps(mission.get("tasks", []), default=str)
            outcomes = json.dumps(mission.get("outcomes", {}), default=str)
            timeline = json.dumps(mission.get("timeline", []), default=str)
            metadata = json.dumps(mission.get("metadata", {}), default=str)

            if self._use_postgres or self.use_sqlite:
                self._sql_execute(
                    """
                    INSERT OR REPLACE INTO missions
                    (mission_id, agent_name, mission_type, description, tasks, outcomes, timeline, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (mission_id, agent, mtype, desc, tasks, outcomes, timeline, metadata),
                )
            else:
                self._json_write(
                    mission_id,
                    {
                        "mission_id": mission_id,
                        "agent_name": agent,
                        "mission_type": mtype,
                        "description": desc,
                        "tasks": mission.get("tasks", []),
                        "outcomes": mission.get("outcomes", {}),
                        "timeline": mission.get("timeline", []),
                        "metadata": mission.get("metadata", {}),
                    },
                )
            duration_ms = int((time.perf_counter() - start) * 1000)
            self.report({"action": "archive_mission", "mission_id": mission_id})
            return self._result(True, "archive_mission", {"mission_id": mission_id}, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "archive_mission", errors=[str(exc)])

    def get_mission(self, mission_id: str) -> Dict[str, Any]:
        """
        Retrieve a complete mission by ID.

        Args:
            mission_id: Unique mission identifier.

        Returns:
            Standard result with mission dict.
        """
        start = time.perf_counter()
        try:
            if self._use_postgres or self.use_sqlite:
                row = self._sql_execute_one("SELECT * FROM missions WHERE mission_id = ?", (mission_id,))
                if row:
                    data = self._row_to_dict(row)
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    return self._result(True, "get_mission", data, duration_ms=duration_ms)
            else:
                data = self._json_read(mission_id)
                if data:
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    return self._result(True, "get_mission", data, duration_ms=duration_ms)
            return self._result(False, "get_mission", errors=[f"Mission {mission_id} not found"])
        except Exception as exc:
            return self._result(False, "get_mission", errors=[str(exc)])

    def search_missions(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Search across all missions with optional filters.

        Args:
            query: Search string for description/type/agent.
            filters: Dict with keys like mission_type, agent_name,
                     date_from, date_to, success.

        Returns:
            Standard result with matching missions.
        """
        start = time.perf_counter()
        try:
            results = []
            if self._use_postgres or self.use_sqlite:
                sql = """
                    SELECT * FROM missions
                    WHERE (description LIKE ? OR mission_type LIKE ? OR agent_name LIKE ?)
                """
                params = [f"%{query}%", f"%{query}%", f"%{query}%"]
                if filters:
                    if "mission_type" in filters:
                        sql += " AND mission_type = ?"
                        params.append(filters["mission_type"])
                    if "agent_name" in filters:
                        sql += " AND agent_name = ?"
                        params.append(filters["agent_name"])
                    if "date_from" in filters:
                        sql += " AND created_at >= ?"
                        params.append(filters["date_from"])
                    if "date_to" in filters:
                        sql += " AND created_at <= ?"
                        params.append(filters["date_to"])
                sql += " ORDER BY created_at DESC"
                rows = self._sql_execute(sql, tuple(params))
                for row in rows:
                    mission = self._row_to_dict(row)
                    if filters and "success" in filters:
                        if mission.get("outcomes", {}).get("success") != filters["success"]:
                            continue
                    results.append(mission)
            else:
                for item in self._json_list():
                    if query.lower() in str(item.get("description", "")).lower() or                        query.lower() in str(item.get("mission_type", "")).lower() or                        query.lower() in str(item.get("agent_name", "")).lower():
                        if filters:
                            match = True
                            for k, v in filters.items():
                                if k == "success":
                                    if item.get("outcomes", {}).get("success") != v:
                                        match = False
                                        break
                                elif item.get(k) != v:
                                    match = False
                                    break
                            if not match:
                                continue
                        results.append(item)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "search_missions", results, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "search_missions", errors=[str(exc)])

    def get_mission_timeline(self, mission_id: str) -> Dict[str, Any]:
        """
        Reconstruct chronological events for a mission.

        Args:
            mission_id: Mission identifier.

        Returns:
            Standard result with timeline list.
        """
        start = time.perf_counter()
        try:
            mission = self.get_mission(mission_id).get("data", {})
            timeline = mission.get("timeline", [])
            timeline.sort(key=lambda x: x.get("timestamp", ""))
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "get_mission_timeline", timeline, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "get_mission_timeline", errors=[str(exc)])

    def get_mission_stats(self, time_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Aggregate statistics across missions.

        Args:
            time_range: Optional dict with "from" and "to" ISO dates.

        Returns:
            Standard result with stats dict.
        """
        start = time.perf_counter()
        try:
            missions = self.list_all().get("data", [])
            if time_range:
                missions = [
                    m for m in missions
                    if time_range.get("from", "") <= m.get("created_at", "") <= time_range.get("to", "9999")
                ]
            total = len(missions)
            successful = sum(1 for m in missions if m.get("outcomes", {}).get("success", False))
            failed = total - successful
            success_rate = successful / total if total > 0 else 0.0

            # By type
            by_type = {}
            for m in missions:
                mt = m.get("mission_type", "unknown")
                if mt not in by_type:
                    by_type[mt] = {"total": 0, "successful": 0}
                by_type[mt]["total"] += 1
                if m.get("outcomes", {}).get("success", False):
                    by_type[mt]["successful"] += 1

            for mt in by_type:
                t = by_type[mt]["total"]
                s = by_type[mt]["successful"]
                by_type[mt]["success_rate"] = round(s / t, 4) if t > 0 else 0.0

            data = {
                "total_missions": total,
                "successful": successful,
                "failed": failed,
                "success_rate": round(success_rate, 4),
                "by_type": by_type,
            }
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "get_mission_stats", data, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "get_mission_stats", errors=[str(exc)])

    def compare_missions(self, mission_ids: List[str]) -> Dict[str, Any]:
        """
        Side-by-side comparison of multiple missions.

        Args:
            mission_ids: List of mission identifiers.

        Returns:
            Standard result with comparison list.
        """
        start = time.perf_counter()
        try:
            missions = []
            for mid in mission_ids:
                m = self.get_mission(mid).get("data")
                if m:
                    missions.append(m)
            comparison = []
            for m in missions:
                comparison.append({
                    "mission_id": m.get("mission_id"),
                    "agent": m.get("agent_name"),
                    "type": m.get("mission_type"),
                    "success": m.get("outcomes", {}).get("success"),
                    "task_count": len(m.get("tasks", [])),
                    "created_at": m.get("created_at"),
                })
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "compare_missions", comparison, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "compare_missions", errors=[str(exc)])

    def extract_lessons(self, mission_id: str) -> Dict[str, Any]:
        """
        Extract lessons learned from a mission.

        Analyzes outcomes to identify what worked and what didn't.

        Args:
            mission_id: Mission identifier.

        Returns:
            Standard result with lessons list.
        """
        start = time.perf_counter()
        try:
            mission = self.get_mission(mission_id).get("data", {})
            outcomes = mission.get("outcomes", {})
            tasks = mission.get("tasks", [])
            lessons = []

            success = outcomes.get("success", False)
            errors = outcomes.get("errors", [])
            warnings = outcomes.get("warnings", [])

            if success:
                lessons.append({
                    "type": "success",
                    "lesson": "Mission completed successfully.",
                    "confidence": 1.0,
                })
                for t in tasks:
                    if t.get("success", False):
                        lessons.append({
                            "type": "technique_worked",
                            "lesson": f"Technique '{t.get('technique', 'unknown')}' worked for {t.get('type', 'task')}.",
                            "confidence": 0.9,
                        })
            else:
                lessons.append({
                    "type": "failure",
                    "lesson": f"Mission failed: {errors[0] if errors else 'Unknown error'}",
                    "confidence": 1.0,
                })

            for err in errors:
                lessons.append({
                    "type": "error_pattern",
                    "lesson": f"Error encountered: {err}",
                    "confidence": 0.95,
                })

            for warn in warnings:
                lessons.append({
                    "type": "warning",
                    "lesson": f"Warning: {warn}",
                    "confidence": 0.8,
                })

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "extract_lessons", lessons, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "extract_lessons", errors=[str(exc)])


# ------------------------------------------------------------------
# Usage example
# ------------------------------------------------------------------
if __name__ == "__main__":
    ma = MissionArchive()
    mission = {
        "id": "m-001",
        "agent_name": "Alpha",
        "mission_type": "reconnaissance",
        "description": "Perimeter scan",
        "tasks": [{"type": "scan", "technique": "port_scan", "success": True}],
        "outcomes": {"success": True, "errors": [], "warnings": ["Slow response on port 443"]},
        "timeline": [{"timestamp": "2024-01-01T00:00:00Z", "event": "started"}],
    }
    ma.archive_mission(mission)
    print(ma.get_mission("m-001"))
    print(ma.extract_lessons("m-001"))
