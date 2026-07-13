"""
IRIS v1.0 — ResourceOptimizer
Efficient resource allocation and scheduling engine.

Estimates costs, optimizes plans for budget constraints, schedules
tasks optimally, identifies caching opportunities, and load-balances
work across agents.

Features:
- Estimate plan costs (tokens, compute, bandwidth)
- Optimize plans for budget constraints
- Schedule tasks given resource availability
- Identify caching opportunities
- Load-balance tasks across agents

Storage:
    SQLite table `resource_plans` (JSON fallback).

Usage:
    ro = ResourceOptimizer()
    cost = ro.estimate_cost(plan)
    optimized = ro.optimize_for_budget(plan, budget={"max_tokens": 10000})
    schedule = ro.schedule_tasks(plan["tasks"], resources={"agents": ["Alpha", "Beta"]})

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

logger = logging.getLogger("iris.cortex.resource_optimizer")


class ResourceOptimizer(BaseCortex):
    """
    Resource optimization engine for efficient execution.

    Minimizes cost and maximizes throughput while respecting
    budget and capacity constraints.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        iris_core: Optional[Any] = None,
    ) -> None:
        """
        Initialize ResourceOptimizer.

        Args:
            db_path: Path to SQLite database. Defaults to env var
                     IRIS_RESOURCE_DB or "iris_resource_optimizer.db".
            iris_core: Reference to IRIS core.
        """
        super().__init__(
            db_path=db_path or os.getenv("IRIS_RESOURCE_DB", "iris_resource_optimizer.db"),
            iris_core=iris_core,
        )
        self._create_resource_tables()

    def _create_resource_tables(self) -> None:
        """Create resource optimization tables."""
        with self._lock:
            if self._conn:
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS resource_plans (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plan_id TEXT NOT NULL UNIQUE,
                        original_plan TEXT NOT NULL,
                        optimized_plan TEXT,
                        cost_estimate TEXT,
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
        Core reasoning: optimize resources for a plan.

        Args:
            input_data: Plan dict or cost estimation request.
            context: Optional context with budget constraints.

        Returns:
            Standard result with optimized plan or cost estimate.
        """
        if isinstance(input_data, dict) and "tasks" in input_data:
            budget = context.get("budget") if context else None
            if budget:
                return self.optimize_for_budget(input_data, budget)
            return self.estimate_cost(input_data)
        return self._result(False, "reason", errors=["Input must be a plan dict with tasks"])

    # ------------------------------------------------------------------
    # Resource methods
    # ------------------------------------------------------------------
    def estimate_cost(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Estimate API tokens, compute time, and bandwidth for a plan.

        Args:
            plan: Plan dict with tasks list.

        Returns:
            Standard result with cost estimate dict.
        """
        start = time.perf_counter()
        try:
            tasks = plan.get("tasks", [])
            total_tokens = 0
            total_compute_ms = 0
            total_bandwidth_mb = 0

            for t in tasks:
                ttype = t.get("type", "unknown")
                est_ms = t.get("estimated_ms", 0)

                # Token estimates based on task type
                if ttype in ("reconnaissance", "analysis", "verification"):
                    tokens = 500
                elif ttype in ("exploitation", "deployment"):
                    tokens = 2000
                elif ttype in ("scan", "enumerate"):
                    tokens = 1000
                else:
                    tokens = 800

                # Compute estimate
                compute = est_ms

                # Bandwidth estimate
                bandwidth = 5 if ttype in ("scan", "exfiltration") else 1

                total_tokens += tokens
                total_compute_ms += compute
                total_bandwidth_mb += bandwidth

            cost = {
                "api_tokens": total_tokens,
                "compute_time_ms": total_compute_ms,
                "bandwidth_mb": total_bandwidth_mb,
                "estimated_cost_usd": round(total_tokens * 0.00002 + total_compute_ms * 0.000001, 4),
            }

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "estimate_cost", cost, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "estimate_cost", errors=[str(exc)])

    def optimize_for_budget(
        self,
        plan: Dict[str, Any],
        budget: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Trim or substitute expensive steps to fit budget.

        Args:
            plan: Plan dict with tasks.
            budget: Dict with max_tokens, max_compute_ms, max_cost_usd.

        Returns:
            Standard result with optimized plan.
        """
        start = time.perf_counter()
        try:
            tasks = plan.get("tasks", [])
            cost = self.estimate_cost(plan).get("data", {})

            max_tokens = budget.get("max_tokens", float("inf"))
            max_compute = budget.get("max_compute_ms", float("inf"))
            max_cost = budget.get("max_cost_usd", float("inf"))

            optimized_tasks = list(tasks)
            changes = []

            # Iteratively remove lowest-priority tasks until within budget
            while optimized_tasks:
                current_cost = self._estimate_cost_for_tasks(optimized_tasks)
                if (current_cost["api_tokens"] <= max_tokens and
                    current_cost["compute_time_ms"] <= max_compute and
                    current_cost["estimated_cost_usd"] <= max_cost):
                    break

                # Find least critical task to remove
                least_critical = min(optimized_tasks, key=lambda t: t.get("priority", 5))
                changes.append(f"Removed task {least_critical.get('id', 'unknown')} to fit budget")
                optimized_tasks.remove(least_critical)

            # Substitute expensive techniques with cheaper alternatives
            for i, t in enumerate(optimized_tasks):
                ttype = t.get("type", "unknown")
                if ttype == "exploitation":
                    optimized_tasks[i]["type"] = "reconnaissance"
                    optimized_tasks[i]["description"] = t.get("description", "") + " (budget-optimized)"
                    changes.append(f"Substituted exploitation with reconnaissance for task {t.get('id')}")

            optimized_plan = dict(plan)
            optimized_plan["tasks"] = optimized_tasks
            optimized_plan["optimized_for_budget"] = True
            optimized_plan["budget_constraints"] = budget
            optimized_plan["changes"] = changes
            optimized_plan["original_cost"] = cost
            optimized_plan["optimized_cost"] = self._estimate_cost_for_tasks(optimized_tasks)

            # Persist
            if self._conn:
                pid = f"res_{int(time.time() * 1000)}"
                self._conn.execute(
                    "INSERT INTO resource_plans (plan_id, original_plan, optimized_plan, cost_estimate) VALUES (?, ?, ?, ?)",
                    (pid, json.dumps(plan), json.dumps(optimized_plan), json.dumps(optimized_plan["optimized_cost"])),
                )
                self._conn.commit()

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "optimize_for_budget", optimized_plan, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "optimize_for_budget", errors=[str(exc)])

    def _estimate_cost_for_tasks(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Quick cost estimate for a subset of tasks."""
        total_tokens = 0
        total_compute = 0
        total_bw = 0
        for t in tasks:
            ttype = t.get("type", "unknown")
            tokens = 2000 if ttype == "exploitation" else 1000 if ttype in ("scan", "enumerate") else 500
            total_tokens += tokens
            total_compute += t.get("estimated_ms", 0)
            total_bw += 5 if ttype in ("scan", "exfiltration") else 1
        return {
            "api_tokens": total_tokens,
            "compute_time_ms": total_compute,
            "bandwidth_mb": total_bw,
            "estimated_cost_usd": round(total_tokens * 0.00002 + total_compute * 0.000001, 4),
        }

    def schedule_tasks(
        self,
        tasks: List[Dict[str, Any]],
        resources: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Create optimal execution schedule given resource constraints.

        Args:
            tasks: List of task dicts.
            resources: Dict with available_agents, max_parallel, time_windows.

        Returns:
            Standard result with schedule list.
        """
        start = time.perf_counter()
        try:
            agents = resources.get("available_agents", ["default"])
            max_parallel = resources.get("max_parallel", len(agents))
            time_windows = resources.get("time_windows", None)

            schedule = []
            current_time = 0
            agent_idx = 0

            for t in tasks:
                assigned_agent = agents[agent_idx % len(agents)]
                start_time = current_time
                end_time = start_time + t.get("estimated_ms", 0)

                if time_windows:
                    # Check if task fits in time window
                    fits = False
                    for window in time_windows:
                        w_start = window.get("start_ms", 0)
                        w_end = window.get("end_ms", float("inf"))
                        if start_time >= w_start and end_time <= w_end:
                            fits = True
                            break
                    if not fits:
                        # Delay to next window
                        current_time = min(w.get("start_ms", 0) for w in time_windows if w.get("start_ms", 0) > start_time)
                        start_time = current_time
                        end_time = start_time + t.get("estimated_ms", 0)

                schedule.append({
                    "task_id": t.get("id", "unknown"),
                    "agent": assigned_agent,
                    "start_ms": start_time,
                    "end_ms": end_time,
                    "duration_ms": t.get("estimated_ms", 0),
                })

                agent_idx += 1
                if agent_idx % max_parallel == 0:
                    current_time = max(s["end_ms"] for s in schedule[-max_parallel:])

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "schedule_tasks", schedule, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "schedule_tasks", errors=[str(exc)])

    def cache_opportunities(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Identify where caching results would be beneficial.

        Args:
            plan: Plan dict with tasks.

        Returns:
            Standard result with list of cache opportunities.
        """
        start = time.perf_counter()
        try:
            tasks = plan.get("tasks", [])
            opportunities = []

            for t in tasks:
                ttype = t.get("type", "unknown")
                tid = t.get("id", "unknown")

                # Tasks that benefit from caching
                if ttype in ("reconnaissance", "scan", "enumerate", "analysis"):
                    opportunities.append({
                        "task_id": tid,
                        "task_type": ttype,
                        "rationale": "Results are deterministic and reusable",
                        "cache_key": f"cache_{ttype}_{hash(str(t.get('description', '')))}",
                        "ttl_seconds": 3600,
                    })
                elif ttype in ("verification", "reporting"):
                    opportunities.append({
                        "task_id": tid,
                        "task_type": ttype,
                        "rationale": "Intermediate results can be cached for reporting",
                        "cache_key": f"cache_{ttype}_{tid}",
                        "ttl_seconds": 1800,
                    })

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "cache_opportunities", opportunities, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "cache_opportunities", errors=[str(exc)])

    def load_balance(
        self,
        agents: List[str],
        tasks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Distribute tasks evenly across agents.

        Args:
            agents: List of agent names.
            tasks: List of task dicts.

        Returns:
            Standard result with agent-task assignments.
        """
        start = time.perf_counter()
        try:
            if not agents:
                return self._result(False, "load_balance", errors=["No agents provided"])

            # Sort tasks by estimated duration (longest first) for better balance
            sorted_tasks = sorted(tasks, key=lambda t: t.get("estimated_ms", 0), reverse=True)

            # Track load per agent
            agent_load = {a: 0 for a in agents}
            assignments = {a: [] for a in agents}

            for t in sorted_tasks:
                # Assign to least loaded agent
                least_loaded = min(agent_load, key=agent_load.get)
                assignments[least_loaded].append(t.get("id", "unknown"))
                agent_load[least_loaded] += t.get("estimated_ms", 0)

            result = {
                "assignments": assignments,
                "agent_loads": {a: load for a, load in agent_load.items()},
                "total_tasks": len(tasks),
                "balance_score": round(1.0 - (max(agent_load.values()) - min(agent_load.values())) / (sum(agent_load.values()) or 1), 4),
            }

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "load_balance", result, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "load_balance", errors=[str(exc)])


# ------------------------------------------------------------------
# Usage example
# ------------------------------------------------------------------
if __name__ == "__main__":
    ro = ResourceOptimizer()
    plan = {
        "tasks": [
            {"id": "t1", "type": "reconnaissance", "estimated_ms": 300000},
            {"id": "t2", "type": "scan", "estimated_ms": 600000},
            {"id": "t3", "type": "exploitation", "estimated_ms": 900000},
        ]
    }
    print(ro.estimate_cost(plan))
    print(ro.optimize_for_budget(plan, {"max_tokens": 2000}))
    print(ro.load_balance(["Alpha", "Beta"], plan["tasks"]))
