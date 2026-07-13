"""
IRIS v1.0 — SkillMemory
Technique effectiveness tracking per agent.

Records which techniques work best for which task types, tracks
success rates, durations, and contexts. Enables technique
recommendation, emerging technique detection, and deprecation
warnings.

Features:
- Record technique usage with full context
- Get best technique for a task type
- Track overall technique statistics
- Suggest techniques under constraints
- Detect emerging high-success techniques
- Flag deprecated declining techniques

Storage:
    SQLite table `techniques` (JSON fallback).

Usage:
    sm = SkillMemory()
    sm.record_technique("Alpha", "sql_injection", "pentest", True, 5000, {"target": "mysql"})
    best = sm.get_best_technique("pentest")
    emerging = sm.get_emerging_techniques()

Author: IRIS Core Team
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .base_memory import BaseMemory

logger = logging.getLogger("iris.memory.skill")


class SkillMemory(BaseMemory):
    """
    Technique effectiveness tracking for intelligent task execution.

    Every technique used by every agent is recorded with outcome,
    enabling data-driven technique selection and continuous improvement.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        iris_core: Optional[Any] = None,
    ) -> None:
        """
        Initialize SkillMemory.

        Args:
            db_path: Path to SQLite database. Defaults to env var
                     IRIS_SKILL_MEMORY_DB or "iris_skill_memory.db".
            iris_core: Reference to IRIS core.
        """
        super().__init__(
            db_path=db_path or os.getenv("IRIS_SKILL_MEMORY_DB", "iris_skill_memory.db"),
            iris_core=iris_core,
        )
        self._create_skill_tables()

    def _create_skill_tables(self) -> None:
        """Create technique tracking tables."""
        with self._lock:
            if self._conn:
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS techniques (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_name TEXT NOT NULL,
                        technique TEXT NOT NULL,
                        task_type TEXT NOT NULL,
                        success INTEGER NOT NULL,
                        duration_ms INTEGER DEFAULT 0,
                        context TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                self._conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tech_task ON techniques(technique, task_type)"
                )
                self._conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_agent_tech ON techniques(agent_name, technique)"
                )
                self._conn.commit()

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------
    def store(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Store a technique record. Value must contain agent_name, technique, task_type, success."""
        if not isinstance(value, dict):
            return self._result(False, "store", errors=["Value must be dict with technique data"])
        return self.record_technique(
            value.get("agent_name", "unknown"),
            value.get("technique", key),
            value.get("task_type", "general"),
            value.get("success", False),
            value.get("duration_ms", 0),
            value.get("context"),
        )

    def retrieve(self, key: str) -> Dict[str, Any]:
        """Retrieve technique records by technique name."""
        return self.search(key)

    def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search techniques by name, task type, or agent."""
        start = time.perf_counter()
        try:
            results = []
            if self.use_sqlite:
                rows = self._sql_execute(
                    """
                    SELECT * FROM techniques
                    WHERE technique LIKE ? OR task_type LIKE ? OR agent_name LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (f"%{query}%", f"%{query}%", f"%{query}%", limit),
                )
                for row in rows:
                    results.append({
                        "id": row[0], "agent_name": row[1], "technique": row[2],
                        "task_type": row[3], "success": bool(row[4]),
                        "duration_ms": row[5], "context": json.loads(row[6]) if row[6] else {},
                        "created_at": row[7],
                    })
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
        """Update technique success status by id."""
        start = time.perf_counter()
        try:
            if self.use_sqlite:
                self._sql_execute(
                    "UPDATE techniques SET success = ? WHERE id = ?",
                    (1 if value else 0, key),
                )
            else:
                data = self._json_read(key)
                if data:
                    data["value"]["success"] = value
                    data["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self._json_write(key, data["value"], data.get("metadata"))
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "update", duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "update", errors=[str(exc)])

    def delete(self, key: str) -> Dict[str, Any]:
        """Delete a technique record by id."""
        start = time.perf_counter()
        try:
            if self.use_sqlite:
                self._sql_execute("DELETE FROM techniques WHERE id = ?", (key,))
            else:
                self._json_delete(key)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "delete", duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "delete", errors=[str(exc)])

    def list_all(self, filter_: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """List all technique records with optional filter."""
        start = time.perf_counter()
        try:
            results = []
            if self.use_sqlite:
                sql = "SELECT * FROM techniques"
                params = []
                conditions = []
                if filter_:
                    for k, v in filter_.items():
                        if k in ("agent_name", "technique", "task_type"):
                            conditions.append(f"{k} = ?")
                            params.append(v)
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
                sql += " ORDER BY created_at DESC"
                rows = self._sql_execute(sql, tuple(params))
                for row in rows:
                    results.append({
                        "id": row[0], "agent_name": row[1], "technique": row[2],
                        "task_type": row[3], "success": bool(row[4]),
                        "duration_ms": row[5], "context": json.loads(row[6]) if row[6] else {},
                        "created_at": row[7],
                    })
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

    # ------------------------------------------------------------------
    # Skill-specific methods
    # ------------------------------------------------------------------
    def record_technique(
        self,
        agent_name: str,
        technique: str,
        task_type: str,
        success: bool,
        duration_ms: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record a technique usage with outcome.

        Args:
            agent_name: Agent that used the technique.
            technique: Name of the technique.
            task_type: Category of task.
            success: Whether the technique succeeded.
            duration_ms: Execution time in milliseconds.
            context: Additional context (target, parameters, etc.).

        Returns:
            Standard result envelope.
        """
        start = time.perf_counter()
        try:
            context_json = json.dumps(context or {}, default=str)
            if self.use_sqlite:
                self._sql_execute(
                    """
                    INSERT INTO techniques
                    (agent_name, technique, task_type, success, duration_ms, context)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (agent_name, technique, task_type, 1 if success else 0, duration_ms, context_json),
                )
            else:
                record_id = f"tech_{agent_name}_{technique}_{int(time.time() * 1000)}"
                self._json_write(
                    record_id,
                    {
                        "agent_name": agent_name,
                        "technique": technique,
                        "task_type": task_type,
                        "success": success,
                        "duration_ms": duration_ms,
                        "context": context or {},
                    },
                )
            duration_ms = int((time.perf_counter() - start) * 1000)
            self.report({
                "action": "record_technique",
                "agent": agent_name,
                "technique": technique,
                "success": success,
            })
            return self._result(True, "record_technique", duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "record_technique", errors=[str(exc)])

    def get_best_technique(self, task_type: str) -> Dict[str, Any]:
        """
        Find the technique with the highest success rate for a task type.

        Args:
            task_type: Category of task.

        Returns:
            Standard result with best technique dict or None.
        """
        start = time.perf_counter()
        try:
            stats = self._get_task_type_stats(task_type)
            if not stats:
                return self._result(True, "get_best_technique", None, duration_ms=int((time.perf_counter()-start)*1000))
            best = max(stats.items(), key=lambda x: x[1]["success_rate"])
            data = {
                "technique": best[0],
                "success_rate": round(best[1]["success_rate"], 4),
                "total_uses": best[1]["total"],
                "avg_duration_ms": round(best[1]["avg_duration"], 2),
            }
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "get_best_technique", data, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "get_best_technique", errors=[str(exc)])

    def get_technique_stats(self, technique: str) -> Dict[str, Any]:
        """
        Get overall statistics for a specific technique.

        Args:
            technique: Technique name.

        Returns:
            Standard result with stats dict.
        """
        start = time.perf_counter()
        try:
            records = self.list_all({"technique": technique}).get("data", [])
            total = len(records)
            if total == 0:
                return self._result(True, "get_technique_stats", {
                    "technique": technique,
                    "success_rate": 0.0,
                    "total_uses": 0,
                    "avg_duration_ms": 0,
                    "task_types": [],
                })
            successes = sum(1 for r in records if r.get("success"))
            avg_dur = sum(r.get("duration_ms", 0) for r in records) / total
            task_types = list(set(r.get("task_type") for r in records))
            data = {
                "technique": technique,
                "success_rate": round(successes / total, 4) if total > 0 else 0.0,
                "total_uses": total,
                "avg_duration_ms": round(avg_dur, 2),
                "task_types": task_types,
            }
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "get_technique_stats", data, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "get_technique_stats", errors=[str(exc)])

    def suggest_technique(
        self,
        task_type: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Suggest the best technique for a task under constraints.

        Args:
            task_type: Category of task.
            constraints: Optional dict with keys like max_duration_ms,
                         min_success_rate, preferred_agents.

        Returns:
            Standard result with recommended technique or None.
        """
        start = time.perf_counter()
        try:
            stats = self._get_task_type_stats(task_type)
            candidates = []
            for tech, s in stats.items():
                ok = True
                if constraints:
                    if "max_duration_ms" in constraints and s["avg_duration"] > constraints["max_duration_ms"]:
                        ok = False
                    if "min_success_rate" in constraints and s["success_rate"] < constraints["min_success_rate"]:
                        ok = False
                if ok:
                    candidates.append((tech, s))
            if not candidates:
                return self._result(True, "suggest_technique", None, duration_ms=int((time.perf_counter()-start)*1000))
            candidates.sort(key=lambda x: x[1]["success_rate"], reverse=True)
            best = candidates[0]
            data = {
                "technique": best[0],
                "success_rate": round(best[1]["success_rate"], 4),
                "avg_duration_ms": round(best[1]["avg_duration"], 2),
            }
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "suggest_technique", data, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "suggest_technique", errors=[str(exc)])

    def get_emerging_techniques(self) -> Dict[str, Any]:
        """
        Detect new techniques with high success rates.

        Returns:
            Standard result with list of emerging techniques.
        """
        start = time.perf_counter()
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            all_records = self.list_all().get("data", [])
            recent = [r for r in all_records if r.get("created_at", "") > cutoff]
            tech_stats = defaultdict(lambda: {"total": 0, "success": 0})
            for r in recent:
                t = r["technique"]
                tech_stats[t]["total"] += 1
                if r.get("success"):
                    tech_stats[t]["success"] += 1
            emerging = []
            for tech, s in tech_stats.items():
                if s["total"] >= 3:
                    rate = s["success"] / s["total"]
                    if rate >= 0.85:
                        emerging.append({
                            "technique": tech,
                            "success_rate": round(rate, 4),
                            "uses": s["total"],
                        })
            emerging.sort(key=lambda x: x["success_rate"], reverse=True)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "get_emerging_techniques", emerging, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "get_emerging_techniques", errors=[str(exc)])

    def get_deprecated_techniques(self) -> Dict[str, Any]:
        """
        Flag techniques with declining success rates.

        Returns:
            Standard result with list of deprecated techniques.
        """
        start = time.perf_counter()
        try:
            all_records = self.list_all().get("data", [])
            tech_stats = defaultdict(lambda: {"total": 0, "success": 0, "recent_success": 0, "recent_total": 0})
            cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            for r in all_records:
                t = r["technique"]
                tech_stats[t]["total"] += 1
                if r.get("success"):
                    tech_stats[t]["success"] += 1
                if r.get("created_at", "") > cutoff:
                    tech_stats[t]["recent_total"] += 1
                    if r.get("success"):
                        tech_stats[t]["recent_success"] += 1

            deprecated = []
            for tech, s in tech_stats.items():
                if s["total"] >= 5 and s["recent_total"] >= 3:
                    overall = s["success"] / s["total"]
                    recent = s["recent_success"] / s["recent_total"]
                    if recent < overall * 0.7:  # Recent rate is 30% worse
                        deprecated.append({
                            "technique": tech,
                            "overall_rate": round(overall, 4),
                            "recent_rate": round(recent, 4),
                            "total_uses": s["total"],
                        })
            deprecated.sort(key=lambda x: x["recent_rate"])
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "get_deprecated_techniques", deprecated, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "get_deprecated_techniques", errors=[str(exc)])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_task_type_stats(self, task_type: str) -> Dict[str, Dict[str, Any]]:
        """Compute per-technique stats for a task type."""
        records = self.list_all({"task_type": task_type}).get("data", [])
        stats = defaultdict(lambda: {"total": 0, "success": 0, "duration_sum": 0})
        for r in records:
            t = r["technique"]
            stats[t]["total"] += 1
            if r.get("success"):
                stats[t]["success"] += 1
            stats[t]["duration_sum"] += r.get("duration_ms", 0)
        for t in stats:
            s = stats[t]
            s["success_rate"] = s["success"] / s["total"] if s["total"] > 0 else 0
            s["avg_duration"] = s["duration_sum"] / s["total"] if s["total"] > 0 else 0
        return dict(stats)


# ------------------------------------------------------------------
# Usage example
# ------------------------------------------------------------------
if __name__ == "__main__":
    sm = SkillMemory()
    sm.record_technique("Alpha", "port_scan", "reconnaissance", True, 1200, {"ports": "1-1000"})
    sm.record_technique("Beta", "osint", "reconnaissance", True, 3000, {"source": "social_media"})
    sm.record_technique("Alpha", "port_scan", "reconnaissance", False, 500, {"ports": "1-1000"})
    print(sm.get_best_technique("reconnaissance"))
    print(sm.get_technique_stats("port_scan"))
