"""
IRIS v1.0 — AgentMemory
Per-agent episodic memory of missions.

Tracks every mission an agent executes, their outcomes, performance
metrics, strengths, and weaknesses. Enables agent comparison and
recommendation for task assignment.

Features:
- Record complete missions with tasks and outcomes
- Retrieve agent history and performance statistics
- Identify agent strengths and weaknesses
- Compare agents for specific task types
- Suggest the best agent for a job

Storage:
    SQLite table `agent_missions` (JSON fallback).

Usage:
    am = AgentMemory()
    am.record_mission("Alpha", "m-001", tasks=[...], outcomes={"success": True}, duration_ms=5000)
    stats = am.get_agent_performance("Alpha")
    best = am.suggest_agent("reconnaissance", complexity=5)

Author: IRIS Core Team
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base_memory import BaseMemory

logger = logging.getLogger("iris.memory.agent")


class AgentMemory(BaseMemory):
    """
    Per-agent episodic memory.

    Stores every mission executed by every agent, enabling performance
    tracking, comparison, and intelligent task assignment.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        iris_core: Optional[Any] = None,
    ) -> None:
        """
        Initialize AgentMemory.

        Args:
            db_path: Path to SQLite database. Defaults to env var
                     IRIS_AGENT_MEMORY_DB or "iris_agent_memory.db".
            iris_core: Reference to IRIS core.
        """
        super().__init__(
            db_path=db_path or os.getenv("IRIS_AGENT_MEMORY_DB", "iris_agent_memory.db"),
            iris_core=iris_core,
        )
        self._create_agent_tables()

    def _create_agent_tables(self) -> None:
        """Create agent-specific tables."""
        with self._lock:
            if self._conn:
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_missions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_name TEXT NOT NULL,
                        mission_id TEXT NOT NULL UNIQUE,
                        tasks TEXT NOT NULL,
                        outcomes TEXT NOT NULL,
                        duration_ms INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                self._conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_agent ON agent_missions(agent_name)
                    """
                )
                self._conn.commit()

    # ------------------------------------------------------------------
    # Core interface implementations
    # ------------------------------------------------------------------
    def store(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Not used directly; use record_mission() instead."""
        return self._result(False, "store", errors=["Use record_mission() for AgentMemory"])

    def retrieve(self, key: str) -> Dict[str, Any]:
        """Retrieve a mission by mission_id."""
        start = time.perf_counter()
        try:
            if self.use_sqlite:
                row = self._sql_execute_one(
                    "SELECT * FROM agent_missions WHERE mission_id = ?", (key,)
                )
                if row:
                    data = {
                        "id": row[0],
                        "agent_name": row[1],
                        "mission_id": row[2],
                        "tasks": json.loads(row[3]),
                        "outcomes": json.loads(row[4]),
                        "duration_ms": row[5],
                        "created_at": row[6],
                    }
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    return self._result(True, "retrieve", data, duration_ms=duration_ms)
            else:
                data = self._json_read(key)
                if data:
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    return self._result(True, "retrieve", data, duration_ms=duration_ms)
            return self._result(False, "retrieve", errors=[f"Mission {key} not found"])
        except Exception as exc:
            return self._result(False, "retrieve", errors=[str(exc)])

    def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search missions by agent name or mission ID."""
        start = time.perf_counter()
        try:
            results = []
            if self.use_sqlite:
                rows = self._sql_execute(
                    """
                    SELECT * FROM agent_missions
                    WHERE agent_name LIKE ? OR mission_id LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (f"%{query}%", f"%{query}%", limit),
                )
                for row in rows:
                    results.append({
                        "id": row[0],
                        "agent_name": row[1],
                        "mission_id": row[2],
                        "tasks": json.loads(row[3]),
                        "outcomes": json.loads(row[4]),
                        "duration_ms": row[5],
                        "created_at": row[6],
                    })
            else:
                for item in self._json_list():
                    if query.lower() in item.get("agent_name", "").lower() or                        query.lower() in item.get("mission_id", "").lower():
                        results.append(item)
                    if len(results) >= limit:
                        break
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "search", results, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "search", errors=[str(exc)])

    def update(self, key: str, value: Any) -> Dict[str, Any]:
        """Update a mission's outcomes."""
        start = time.perf_counter()
        try:
            if self.use_sqlite:
                self._sql_execute(
                    "UPDATE agent_missions SET outcomes = ? WHERE mission_id = ?",
                    (json.dumps(value), key),
                )
            else:
                data = self._json_read(key)
                if data:
                    data["value"] = value
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
            if self.use_sqlite:
                self._sql_execute("DELETE FROM agent_missions WHERE mission_id = ?", (key,))
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
            if self.use_sqlite:
                sql = "SELECT * FROM agent_missions"
                params = []
                conditions = []
                if filter_:
                    if "agent_name" in filter_:
                        conditions.append("agent_name = ?")
                        params.append(filter_["agent_name"])
                    if "mission_id" in filter_:
                        conditions.append("mission_id = ?")
                        params.append(filter_["mission_id"])
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
                sql += " ORDER BY created_at DESC"
                rows = self._sql_execute(sql, tuple(params))
                for row in rows:
                    results.append({
                        "id": row[0],
                        "agent_name": row[1],
                        "mission_id": row[2],
                        "tasks": json.loads(row[3]),
                        "outcomes": json.loads(row[4]),
                        "duration_ms": row[5],
                        "created_at": row[6],
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
    # Agent-specific methods
    # ------------------------------------------------------------------
    def record_mission(
        self,
        agent_name: str,
        mission_id: str,
        tasks: List[Dict[str, Any]],
        outcomes: Dict[str, Any],
        duration_ms: int = 0,
    ) -> Dict[str, Any]:
        """
        Record a completed or in-progress mission for an agent.

        Args:
            agent_name: Name of the executing agent.
            mission_id: Unique mission identifier.
            tasks: List of task dictionaries.
            outcomes: Success/failure data and metrics.
            duration_ms: Total execution time in milliseconds.

        Returns:
            Standard result envelope.
        """
        start = time.perf_counter()
        try:
            tasks_json = json.dumps(tasks, default=str)
            outcomes_json = json.dumps(outcomes, default=str)
            if self.use_sqlite:
                self._sql_execute(
                    """
                    INSERT OR REPLACE INTO agent_missions
                    (agent_name, mission_id, tasks, outcomes, duration_ms)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (agent_name, mission_id, tasks_json, outcomes_json, duration_ms),
                )
            else:
                self._json_write(
                    mission_id,
                    {
                        "agent_name": agent_name,
                        "mission_id": mission_id,
                        "tasks": tasks,
                        "outcomes": outcomes,
                        "duration_ms": duration_ms,
                    },
                )
            duration_ms = int((time.perf_counter() - start) * 1000)
            self.report({
                "action": "record_mission",
                "agent": agent_name,
                "mission_id": mission_id,
            })
            return self._result(True, "record_mission", {"mission_id": mission_id}, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "record_mission", errors=[str(exc)])

    def get_agent_history(
        self,
        agent_name: str,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Retrieve past missions for a specific agent.

        Args:
            agent_name: Agent to query.
            limit: Maximum missions to return.

        Returns:
            Standard result with list of mission dicts.
        """
        start = time.perf_counter()
        try:
            if self.use_sqlite:
                rows = self._sql_execute(
                    """
                    SELECT * FROM agent_missions
                    WHERE agent_name = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (agent_name, limit),
                )
                results = []
                for row in rows:
                    results.append({
                        "id": row[0],
                        "agent_name": row[1],
                        "mission_id": row[2],
                        "tasks": json.loads(row[3]),
                        "outcomes": json.loads(row[4]),
                        "duration_ms": row[5],
                        "created_at": row[6],
                    })
            else:
                results = [
                    item for item in self._json_list()
                    if item.get("agent_name") == agent_name
                ][:limit]
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "get_agent_history", results, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "get_agent_history", errors=[str(exc)])

    def get_agent_performance(self, agent_name: str) -> Dict[str, Any]:
        """
        Calculate performance metrics for an agent.

        Returns:
            Dict with success_rate, avg_duration_ms, total_missions,
            successful_missions, failed_missions, common_errors.
        """
        start = time.perf_counter()
        try:
            history = self.get_agent_history(agent_name, limit=10000).get("data", [])
            total = len(history)
            if total == 0:
                return self._result(True, "get_agent_performance", {
                    "agent_name": agent_name,
                    "success_rate": 0.0,
                    "avg_duration_ms": 0,
                    "total_missions": 0,
                    "successful_missions": 0,
                    "failed_missions": 0,
                    "common_errors": [],
                })

            successful = sum(1 for m in history if m.get("outcomes", {}).get("success", False))
            failed = total - successful
            success_rate = successful / total if total > 0 else 0.0
            avg_duration = sum(m.get("duration_ms", 0) for m in history) / total if total > 0 else 0

            # Common errors
            errors = []
            for m in history:
                errs = m.get("outcomes", {}).get("errors", [])
                errors.extend(errs)
            from collections import Counter
            common = Counter(errors).most_common(5)

            data = {
                "agent_name": agent_name,
                "success_rate": round(success_rate, 4),
                "avg_duration_ms": round(avg_duration, 2),
                "total_missions": total,
                "successful_missions": successful,
                "failed_missions": failed,
                "common_errors": [e[0] for e in common],
            }
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "get_agent_performance", data, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "get_agent_performance", errors=[str(exc)])

    def get_agent_strengths(self, agent_name: str) -> Dict[str, Any]:
        """
        Identify what an agent excels at based on mission history.

        Returns:
            List of task types where success_rate > 0.8.
        """
        start = time.perf_counter()
        try:
            history = self.get_agent_history(agent_name, limit=10000).get("data", [])
            task_stats = {}
            for m in history:
                tasks = m.get("tasks", [])
                success = m.get("outcomes", {}).get("success", False)
                for t in tasks:
                    ttype = t.get("type", "unknown")
                    if ttype not in task_stats:
                        task_stats[ttype] = {"total": 0, "success": 0}
                    task_stats[ttype]["total"] += 1
                    if success:
                        task_stats[ttype]["success"] += 1

            strengths = []
            for ttype, stats in task_stats.items():
                rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
                if rate >= 0.8 and stats["total"] >= 3:
                    strengths.append(ttype)

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "get_agent_strengths", strengths, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "get_agent_strengths", errors=[str(exc)])

    def get_agent_weaknesses(self, agent_name: str) -> Dict[str, Any]:
        """
        Identify what an agent struggles with.

        Returns:
            List of task types where success_rate < 0.5.
        """
        start = time.perf_counter()
        try:
            history = self.get_agent_history(agent_name, limit=10000).get("data", [])
            task_stats = {}
            for m in history:
                tasks = m.get("tasks", [])
                success = m.get("outcomes", {}).get("success", False)
                for t in tasks:
                    ttype = t.get("type", "unknown")
                    if ttype not in task_stats:
                        task_stats[ttype] = {"total": 0, "success": 0}
                    task_stats[ttype]["total"] += 1
                    if success:
                        task_stats[ttype]["success"] += 1

            weaknesses = []
            for ttype, stats in task_stats.items():
                rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
                if rate < 0.5 and stats["total"] >= 3:
                    weaknesses.append(ttype)

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "get_agent_weaknesses", weaknesses, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "get_agent_weaknesses", errors=[str(exc)])

    def compare_agents(self, task_type: str) -> Dict[str, Any]:
        """
        Rank all agents by performance on a specific task type.

        Args:
            task_type: Type of task to compare.

        Returns:
            List of dicts sorted by success rate (descending).
        """
        start = time.perf_counter()
        try:
            all_missions = self.list_all().get("data", [])
            agent_stats = {}
            for m in all_missions:
                agent = m.get("agent_name")
                tasks = m.get("tasks", [])
                success = m.get("outcomes", {}).get("success", False)
                for t in tasks:
                    if t.get("type") == task_type:
                        if agent not in agent_stats:
                            agent_stats[agent] = {"total": 0, "success": 0}
                        agent_stats[agent]["total"] += 1
                        if success:
                            agent_stats[agent]["success"] += 1

            rankings = []
            for agent, stats in agent_stats.items():
                rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
                rankings.append({
                    "agent_name": agent,
                    "success_rate": round(rate, 4),
                    "missions": stats["total"],
                })
            rankings.sort(key=lambda x: x["success_rate"], reverse=True)

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "compare_agents", rankings, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "compare_agents", errors=[str(exc)])

    def suggest_agent(self, task_type: str, complexity: int = 5) -> Dict[str, Any]:
        """
        Recommend the best agent for a given task type.

        Args:
            task_type: Type of task.
            complexity: Complexity level 1-10.

        Returns:
            Agent name with highest success rate on this task.
        """
        start = time.perf_counter()
        try:
            rankings = self.compare_agents(task_type).get("data", [])
            if not rankings:
                return self._result(True, "suggest_agent", None, duration_ms=int((time.perf_counter()-start)*1000))
            best = rankings[0]["agent_name"]
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "suggest_agent", best, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "suggest_agent", errors=[str(exc)])


# ------------------------------------------------------------------
# Usage example
# ------------------------------------------------------------------
if __name__ == "__main__":
    am = AgentMemory()
    am.record_mission(
        agent_name="Alpha",
        mission_id="m-001",
        tasks=[{"type": "reconnaissance", "description": "Scan perimeter"}],
        outcomes={"success": True, "errors": []},
        duration_ms=3200,
    )
    print(am.get_agent_performance("Alpha"))
    print(am.suggest_agent("reconnaissance"))
