"""
IRIS v1.0 — Planner
Mission planning and goal decomposition engine.

Breaks complex goals into step-by-step plans, sequences tasks with
dependency resolution, estimates durations and resources, optimizes
plans for speed/cost/stealth, and validates plans for feasibility.

Features:
- Decompose goals into subtasks
- Sequence tasks with dependency resolution
- Estimate duration and resource requirements
- Create complete plans with all metadata
- Optimize plans for time, cost, or stealth
- Validate plans and detect impossible steps

Storage:
    SQLite table `plans` (JSON fallback).

Usage:
    planner = Planner()
    plan = planner.create_plan("Secure website", context={"target": "example.com"})
    optimized = planner.optimize_plan(plan, metric="time")
    issues = planner.validate_plan(plan)

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

from .base_cortex import BaseCortex

logger = logging.getLogger("iris.cortex.planner")


class Planner(BaseCortex):
    """
    Mission planning engine with goal decomposition and optimization.

    Transforms high-level goals into executable, validated plans
    with resource estimates and risk awareness.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        iris_core: Optional[Any] = None,
    ) -> None:
        """
        Initialize Planner.

        Args:
            db_path: Path to SQLite database. Defaults to env var
                     IRIS_PLANNER_DB or "iris_planner.db".
            iris_core: Reference to IRIS core.
        """
        super().__init__(
            db_path=db_path or os.getenv("IRIS_PLANNER_DB", "iris_planner.db"),
            iris_core=iris_core,
        )
        self._create_planner_tables()

    def _create_planner_tables(self) -> None:
        """Create planner-specific tables."""
        with self._lock:
            if self._conn:
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS plans (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plan_id TEXT NOT NULL UNIQUE,
                        goal TEXT NOT NULL,
                        tasks TEXT NOT NULL,
                        sequence TEXT NOT NULL,
                        estimates TEXT NOT NULL,
                        optimized INTEGER DEFAULT 0,
                        validated INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                self._conn.commit()

    # ------------------------------------------------------------------
    # Core reasoning
    # ------------------------------------------------------------------
    def reason(self, input_data: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Core reasoning: create a plan from input goal.

        Args:
            input_data: Goal string or dict with goal key.
            context: Optional planning context.

        Returns:
            Standard result with plan dict.
        """
        goal = input_data if isinstance(input_data, str) else input_data.get("goal", "")
        return self.create_plan(goal, context)

    # ------------------------------------------------------------------
    # Planning methods
    # ------------------------------------------------------------------
    def decompose(
        self,
        goal: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Break a goal into subtasks.

        Uses rule-based decomposition with domain knowledge.

        Args:
            goal: High-level goal string.
            constraints: Optional constraints dict.

        Returns:
            Standard result with list of task dicts.
        """
        start = time.perf_counter()
        try:
            tasks = []
            goal_lower = goal.lower()

            # Domain-specific decomposition rules
            if "secure" in goal_lower or "security" in goal_lower:
                tasks = [
                    {"id": "t1", "type": "reconnaissance", "description": "Assess current security posture", "estimated_ms": 300000},
                    {"id": "t2", "type": "vulnerability_scan", "description": "Identify vulnerabilities", "estimated_ms": 600000},
                    {"id": "t3", "type": "patch", "description": "Apply security patches", "estimated_ms": 900000},
                    {"id": "t4", "type": "verification", "description": "Verify security improvements", "estimated_ms": 300000},
                ]
            elif "scan" in goal_lower or "recon" in goal_lower:
                tasks = [
                    {"id": "t1", "type": "reconnaissance", "description": "Initial reconnaissance", "estimated_ms": 120000},
                    {"id": "t2", "type": "port_scan", "description": "Port scanning", "estimated_ms": 300000},
                    {"id": "t3", "type": "service_enum", "description": "Service enumeration", "estimated_ms": 300000},
                    {"id": "t4", "type": "reporting", "description": "Compile findings", "estimated_ms": 180000},
                ]
            elif "deploy" in goal_lower or "install" in goal_lower:
                tasks = [
                    {"id": "t1", "type": "preparation", "description": "Prepare deployment environment", "estimated_ms": 300000},
                    {"id": "t2", "type": "deployment", "description": "Execute deployment", "estimated_ms": 600000},
                    {"id": "t3", "type": "verification", "description": "Verify deployment success", "estimated_ms": 300000},
                ]
            else:
                # Generic decomposition
                tasks = [
                    {"id": "t1", "type": "analysis", "description": f"Analyze goal: {goal}", "estimated_ms": 180000},
                    {"id": "t2", "type": "execution", "description": "Execute primary objective", "estimated_ms": 600000},
                    {"id": "t3", "type": "verification", "description": "Verify results", "estimated_ms": 180000},
                ]

            # Apply constraints
            if constraints:
                max_tasks = constraints.get("max_tasks")
                if max_tasks and len(tasks) > max_tasks:
                    tasks = tasks[:max_tasks]
                for t in tasks:
                    if "max_duration_per_task_ms" in constraints:
                        t["estimated_ms"] = min(t["estimated_ms"], constraints["max_duration_per_task_ms"])

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "decompose", tasks, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "decompose", errors=[str(exc)])

    def sequence(
        self,
        tasks: List[Dict[str, Any]],
        dependencies: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """
        Order tasks with dependency resolution.

        Uses topological sort for dependency-aware sequencing.

        Args:
            tasks: List of task dicts with "id" key.
            dependencies: Dict mapping task_id -> list of prerequisite task_ids.

        Returns:
            Standard result with ordered task list.
        """
        start = time.perf_counter()
        try:
            deps = dependencies or {}
            task_map = {t["id"]: t for t in tasks}
            in_degree = {t["id"]: 0 for t in tasks}
            adj = {t["id"]: [] for t in tasks}

            for tid, prereqs in deps.items():
                for prereq in prereqs:
                    if prereq in adj:
                        adj[prereq].append(tid)
                        in_degree[tid] = in_degree.get(tid, 0) + 1

            # Kahn's algorithm
            queue = [tid for tid, deg in in_degree.items() if deg == 0]
            ordered = []
            while queue:
                tid = queue.pop(0)
                ordered.append(task_map[tid])
                for neighbor in adj[tid]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

            # Add any remaining (circular dependency fallback)
            ordered_ids = {t["id"] for t in ordered}
            for t in tasks:
                if t["id"] not in ordered_ids:
                    ordered.append(t)

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "sequence", ordered, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "sequence", errors=[str(exc)])

    def estimate_duration(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Estimate total plan duration in milliseconds.

        Args:
            tasks: List of task dicts with "estimated_ms".

        Returns:
            Standard result with total_ms.
        """
        start = time.perf_counter()
        try:
            total = sum(t.get("estimated_ms", 0) for t in tasks)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "estimate_duration", {"total_ms": total, "task_count": len(tasks)}, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "estimate_duration", errors=[str(exc)])

    def estimate_resources(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Estimate CPU, memory, and API calls needed.

        Args:
            tasks: List of task dicts.

        Returns:
            Standard result with resource dict.
        """
        start = time.perf_counter()
        try:
            cpu_cores = 0
            memory_mb = 0
            api_calls = 0
            for t in tasks:
                ttype = t.get("type", "unknown")
                if ttype in ("reconnaissance", "port_scan", "vulnerability_scan"):
                    cpu_cores += 1
                    memory_mb += 256
                    api_calls += 5
                elif ttype in ("exploitation", "deployment"):
                    cpu_cores += 2
                    memory_mb += 512
                    api_calls += 10
                elif ttype in ("analysis", "verification"):
                    cpu_cores += 1
                    memory_mb += 128
                    api_calls += 2
                else:
                    cpu_cores += 1
                    memory_mb += 256
                    api_calls += 3

            data = {
                "cpu_cores": cpu_cores,
                "memory_mb": memory_mb,
                "api_calls": api_calls,
                "bandwidth_estimate_mb": len(tasks) * 10,
            }
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "estimate_resources", data, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "estimate_resources", errors=[str(exc)])

    def create_plan(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a complete plan from a goal.

        Args:
            goal: High-level goal string.
            context: Optional context dict.

        Returns:
            Standard result with complete plan dict.
        """
        start = time.perf_counter()
        try:
            constraints = context.get("constraints") if context else None
            tasks_result = self.decompose(goal, constraints)
            tasks = tasks_result.get("data", [])

            # Default dependencies: each task depends on previous
            deps = {}
            for i, t in enumerate(tasks):
                if i > 0:
                    deps[t["id"]] = [tasks[i - 1]["id"]]

            seq_result = self.sequence(tasks, deps)
            ordered = seq_result.get("data", tasks)

            dur_result = self.estimate_duration(ordered)
            resources = self.estimate_resources(ordered).get("data", {})

            plan_id = f"plan_{int(time.time() * 1000)}"
            plan = {
                "plan_id": plan_id,
                "goal": goal,
                "tasks": ordered,
                "sequence": [t["id"] for t in ordered],
                "dependencies": deps,
                "estimates": {
                    "total_duration_ms": dur_result.get("data", {}).get("total_ms", 0),
                    "resources": resources,
                },
                "context": context or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            # Persist
            if self._conn:
                self._conn.execute(
                    """
                    INSERT INTO plans (plan_id, goal, tasks, sequence, estimates)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (plan_id, goal, json.dumps(ordered), json.dumps(plan["sequence"]), json.dumps(plan["estimates"])),
                )
                self._conn.commit()

            duration_ms = int((time.perf_counter() - start) * 1000)
            self._log_reasoning("create_plan", {"goal": goal}, plan, 0.85, duration_ms)
            self.report({"action": "create_plan", "plan_id": plan_id, "tasks": len(ordered)})
            return self._result(True, "create_plan", plan, confidence=0.85, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "create_plan", errors=[str(exc)])

    def optimize_plan(
        self,
        plan: Dict[str, Any],
        metric: str = "time",
    ) -> Dict[str, Any]:
        """
        Reorder plan for speed, cost, or stealth.

        Args:
            plan: Plan dict from create_plan.
            metric: "time", "cost", or "stealth".

        Returns:
            Standard result with optimized plan.
        """
        start = time.perf_counter()
        try:
            tasks = plan.get("tasks", [])
            if metric == "time":
                # Sort by estimated duration ascending (shortest first)
                tasks.sort(key=lambda t: t.get("estimated_ms", 0))
            elif metric == "cost":
                # Sort by resource intensity ascending
                tasks.sort(key=lambda t: t.get("estimated_ms", 0) * 0.5 + t.get("api_calls", 0) * 100)
            elif metric == "stealth":
                # Sort by detectability descending (most stealthy first)
                stealth_order = {"reconnaissance": 3, "analysis": 2, "verification": 2, "exploitation": 1, "deployment": 1}
                tasks.sort(key=lambda t: stealth_order.get(t.get("type", ""), 0), reverse=True)

            plan["tasks"] = tasks
            plan["sequence"] = [t["id"] for t in tasks]
            plan["optimized_for"] = metric
            plan["optimized_at"] = datetime.now(timezone.utc).isoformat()

            # Recalculate estimates
            dur = self.estimate_duration(tasks).get("data", {}).get("total_ms", 0)
            plan["estimates"]["total_duration_ms"] = dur

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "optimize_plan", plan, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "optimize_plan", errors=[str(exc)])

    def validate_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect impossible or risky steps in a plan.

        Args:
            plan: Plan dict.

        Returns:
            Standard result with list of issues.
        """
        start = time.perf_counter()
        try:
            issues = []
            tasks = plan.get("tasks", [])
            deps = plan.get("dependencies", {})

            # Check for circular dependencies
            visited = set()
            rec_stack = set()
            def has_cycle(node, path):
                visited.add(node)
                rec_stack.add(node)
                for neighbor in deps.get(node, []):
                    if neighbor not in visited:
                        if has_cycle(neighbor, path + [neighbor]):
                            return True
                    elif neighbor in rec_stack:
                        issues.append({
                            "type": "circular_dependency",
                            "severity": "critical",
                            "description": f"Circular dependency detected: {' -> '.join(path + [neighbor])}",
                        })
                        return True
                rec_stack.remove(node)
                return False

            for t in tasks:
                if t["id"] not in visited:
                    has_cycle(t["id"], [t["id"]])

            # Check for missing prerequisites
            task_ids = {t["id"] for t in tasks}
            for tid, prereqs in deps.items():
                for prereq in prereqs:
                    if prereq not in task_ids:
                        issues.append({
                            "type": "missing_prerequisite",
                            "severity": "high",
                            "description": f"Task {tid} depends on missing task {prereq}",
                        })

            # Check for unrealistic estimates
            for t in tasks:
                if t.get("estimated_ms", 0) > 3600000:  # > 1 hour
                    issues.append({
                        "type": "long_task",
                        "severity": "medium",
                        "description": f"Task {t['id']} has very long estimate: {t['estimated_ms']}ms",
                    })
                if not t.get("type"):
                    issues.append({
                        "type": "missing_type",
                        "severity": "low",
                        "description": f"Task {t['id']} has no type assigned",
                    })

            # Check if plan is empty
            if not tasks:
                issues.append({
                    "type": "empty_plan",
                    "severity": "critical",
                    "description": "Plan contains no tasks",
                })

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "validate_plan", issues, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "validate_plan", errors=[str(exc)])


# ------------------------------------------------------------------
# Usage example
# ------------------------------------------------------------------
if __name__ == "__main__":
    planner = Planner()
    plan = planner.create_plan("Secure corporate website")
    print(json.dumps(plan, indent=2))
    optimized = planner.optimize_plan(plan["data"], metric="time")
    print(json.dumps(optimized, indent=2))
    issues = planner.validate_plan(plan["data"])
    print(json.dumps(issues, indent=2))
