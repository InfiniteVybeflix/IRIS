"""
IRIS v7.0 — Strategist
Approach selection and adaptation engine.

Selects optimal approaches for tasks, evaluates trade-offs between
speed and thoroughness, stealth and visibility, parallel vs sequential
execution, and adapts strategy mid-mission based on new intelligence.

Features:
- Select best approach for a task
- Evaluate speed vs thoroughness trade-offs
- Evaluate stealth vs visibility risks
- Choose parallel vs sequential execution
- Adapt strategy dynamically mid-mission

Storage:
    SQLite table `strategies` (JSON fallback).

Usage:
    st = Strategist()
    approach = st.select_approach(task, ["Alpha", "Beta"], context)
    tradeoff = st.evaluate_speed_vs_thoroughness(task)
    adapted = st.adapt_strategy(current_strategy, new_intel)

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

logger = logging.getLogger("iris.cortex.strategist")


class Strategist(BaseCortex):
    """
    Strategic reasoning engine for approach selection and adaptation.

    Evaluates multiple dimensions of strategy to maximize mission
    success while minimizing risk and resource consumption.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        iris_core: Optional[Any] = None,
    ) -> None:
        """
        Initialize Strategist.

        Args:
            db_path: Path to SQLite database. Defaults to env var
                     IRIS_STRATEGIST_DB or "iris_strategist.db".
            iris_core: Reference to IRIS core.
        """
        super().__init__(
            db_path=db_path or os.getenv("IRIS_STRATEGIST_DB", "iris_strategist.db"),
            iris_core=iris_core,
        )
        self._create_strategist_tables()

    def _create_strategist_tables(self) -> None:
        """Create strategist-specific tables."""
        with self._lock:
            if self._conn:
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS strategies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        strategy_id TEXT NOT NULL UNIQUE,
                        task_type TEXT NOT NULL,
                        approach TEXT NOT NULL,
                        rationale TEXT,
                        outcome TEXT,
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
        Core reasoning: select approach for given task.

        Args:
            input_data: Task dict or string.
            context: Optional context.

        Returns:
            Standard result with approach recommendation.
        """
        task = input_data if isinstance(input_data, dict) else {"description": input_data, "type": "general"}
        agents = context.get("available_agents", []) if context else []
        return self.select_approach(task, agents, context)

    # ------------------------------------------------------------------
    # Strategy methods
    # ------------------------------------------------------------------
    def select_approach(
        self,
        task: Dict[str, Any],
        available_agents: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Select the best approach for a task.

        Evaluates available agents against task requirements.

        Args:
            task: Task dict with type, description, complexity.
            available_agents: List of agent names.
            context: Optional context with preferences.

        Returns:
            Standard result with recommended approach dict.
        """
        start = time.perf_counter()
        try:
            task_type = task.get("type", "general")
            complexity = task.get("complexity", 5)
            description = task.get("description", "")

            # Evaluate each agent
            scored_agents = []
            for agent in available_agents:
                score = 0.5  # Base score
                # Agent specialization boost
                if task_type in ("reconnaissance", "scan") and "recon" in agent.lower():
                    score += 0.3
                if task_type in ("exploitation", "attack") and "exploit" in agent.lower():
                    score += 0.3
                if task_type in ("analysis", "intel") and "analyst" in agent.lower():
                    score += 0.3
                # Complexity matching
                if complexity <= 3 and "light" in agent.lower():
                    score += 0.2
                if complexity >= 8 and "heavy" in agent.lower():
                    score += 0.2
                scored_agents.append({"agent": agent, "score": round(score, 4)})

            scored_agents.sort(key=lambda x: x["score"], reverse=True)
            best_agent = scored_agents[0]["agent"] if scored_agents else "default"

            # Determine approach style
            if complexity <= 3:
                approach = "fast_direct"
            elif complexity <= 7:
                approach = "balanced"
            else:
                approach = "thorough_cautious"

            # Context overrides
            if context:
                if context.get("stealth_required"):
                    approach = "stealthy"
                if context.get("speed_priority"):
                    approach = "fast_direct"
                if context.get("thoroughness_priority"):
                    approach = "thorough_cautious"

            result = {
                "task_type": task_type,
                "recommended_agent": best_agent,
                "approach": approach,
                "agent_scores": scored_agents,
                "rationale": f"Selected {approach} approach with {best_agent} based on task complexity {complexity} and type {task_type}",
            }

            # Persist
            if self._conn:
                sid = f"strat_{int(time.time() * 1000)}"
                self._conn.execute(
                    "INSERT INTO strategies (strategy_id, task_type, approach, rationale) VALUES (?, ?, ?, ?)",
                    (sid, task_type, approach, result["rationale"]),
                )
                self._conn.commit()

            duration_ms = int((time.perf_counter() - start) * 1000)
            self._log_reasoning("select_approach", task, result, 0.8, duration_ms)
            return self._result(True, "select_approach", result, confidence=0.8, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "select_approach", errors=[str(exc)])

    def evaluate_speed_vs_thoroughness(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze trade-off between speed and thoroughness.

        Args:
            task: Task dict.

        Returns:
            Standard result with trade-off analysis.
        """
        start = time.perf_counter()
        try:
            complexity = task.get("complexity", 5)
            time_sensitive = task.get("time_sensitive", False)
            criticality = task.get("criticality", 5)

            # Speed score: higher when time-sensitive or low complexity
            speed_score = 0.5
            if time_sensitive:
                speed_score += 0.3
            if complexity <= 3:
                speed_score += 0.2
            if criticality <= 3:
                speed_score += 0.1
            speed_score = min(1.0, speed_score)

            # Thoroughness score: higher when high complexity or critical
            thorough_score = 0.5
            if complexity >= 8:
                thorough_score += 0.3
            if criticality >= 8:
                thorough_score += 0.2
            if not time_sensitive:
                thorough_score += 0.1
            thorough_score = min(1.0, thorough_score)

            recommendation = "balanced"
            if speed_score > thorough_score + 0.2:
                recommendation = "prioritize_speed"
            elif thorough_score > speed_score + 0.2:
                recommendation = "prioritize_thoroughness"

            result = {
                "speed_score": round(speed_score, 4),
                "thoroughness_score": round(thorough_score, 4),
                "recommendation": recommendation,
                "trade_off": "Speed may miss edge cases; thoroughness takes longer but is more reliable.",
            }
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "evaluate_speed_vs_thoroughness", result, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "evaluate_speed_vs_thoroughness", errors=[str(exc)])

    def evaluate_stealth_vs_visibility(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze risk of detection vs operational effectiveness.

        Args:
            task: Task dict.

        Returns:
            Standard result with risk analysis.
        """
        start = time.perf_counter()
        try:
            task_type = task.get("type", "general")
            target_sensitivity = task.get("target_sensitivity", 5)
            detection_tolerance = task.get("detection_tolerance", 0.1)

            # Stealth score: higher when target is sensitive
            stealth_score = 0.5
            if target_sensitivity >= 8:
                stealth_score += 0.3
            if task_type in ("reconnaissance", "intel"):
                stealth_score += 0.2
            if detection_tolerance <= 0.05:
                stealth_score += 0.2
            stealth_score = min(1.0, stealth_score)

            # Visibility score: higher when aggressive action needed
            visibility_score = 0.5
            if task_type in ("exploitation", "disruption"):
                visibility_score += 0.3
            if target_sensitivity <= 3:
                visibility_score += 0.2
            visibility_score = min(1.0, visibility_score)

            recommendation = "balanced"
            if stealth_score > visibility_score + 0.2:
                recommendation = "maximize_stealth"
            elif visibility_score > stealth_score + 0.2:
                recommendation = "accept_visibility"

            result = {
                "stealth_score": round(stealth_score, 4),
                "visibility_score": round(visibility_score, 4),
                "recommendation": recommendation,
                "risk_level": "high" if stealth_score >= 0.8 else "medium" if stealth_score >= 0.5 else "low",
            }
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "evaluate_stealth_vs_visibility", result, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "evaluate_stealth_vs_visibility", errors=[str(exc)])

    def select_parallel_vs_sequential(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Determine optimal execution strategy for a set of tasks.

        Args:
            tasks: List of task dicts.

        Returns:
            Standard result with execution strategy.
        """
        start = time.perf_counter()
        try:
            if not tasks:
                return self._result(True, "select_parallel_vs_sequential", {"strategy": "sequential", "reason": "No tasks provided"})

            # Check for dependencies
            has_deps = any(t.get("dependencies") for t in tasks)
            task_count = len(tasks)

            # Independent tasks with no data dependencies can run in parallel
            if not has_deps and task_count <= 5:
                strategy = "parallel"
                reason = "Tasks are independent and manageable in parallel"
            elif not has_deps and task_count > 5:
                strategy = "hybrid"
                reason = "Many independent tasks; batch into parallel groups"
            else:
                strategy = "sequential"
                reason = "Tasks have dependencies requiring ordered execution"

            # Resource consideration
            total_estimated = sum(t.get("estimated_ms", 0) for t in tasks)
            if total_estimated > 1800000:  # > 30 min
                if strategy == "sequential":
                    strategy = "hybrid"
                    reason += "; long total duration suggests partial parallelization"

            result = {
                "strategy": strategy,
                "task_count": task_count,
                "has_dependencies": has_deps,
                "total_estimated_ms": total_estimated,
                "reason": reason,
                "batches": self._create_batches(tasks) if strategy == "hybrid" else [],
            }
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "select_parallel_vs_sequential", result, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "select_parallel_vs_sequential", errors=[str(exc)])

    def _create_batches(self, tasks: List[Dict[str, Any]]) -> List[List[str]]:
        """Create execution batches for hybrid strategy."""
        batches = []
        current = []
        batch_weight = 0
        max_weight = 600000  # 10 minutes per batch
        for t in tasks:
            weight = t.get("estimated_ms", 0)
            if batch_weight + weight > max_weight and current:
                batches.append([x["id"] for x in current])
                current = [t]
                batch_weight = weight
            else:
                current.append(t)
                batch_weight += weight
        if current:
            batches.append([x["id"] for x in current])
        return batches

    def adapt_strategy(
        self,
        mid_mission: Dict[str, Any],
        new_intel: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Pivot strategy based on new intelligence mid-mission.

        Args:
            mid_mission: Current mission state dict.
            new_intel: New intelligence dict.

        Returns:
            Standard result with adapted strategy.
        """
        start = time.perf_counter()
        try:
            current_strategy = mid_mission.get("strategy", "balanced")
            changes = []

            # Adapt based on new intel
            if new_intel.get("detection_alert"):
                changes.append("Switch to stealth mode due to detection alert")
                current_strategy = "stealth"
            if new_intel.get("unexpected_defense"):
                changes.append("Increase thoroughness due to unexpected defenses")
                current_strategy = "thorough_cautious"
            if new_intel.get("shortcut_available"):
                changes.append("Speed up using discovered shortcut")
                current_strategy = "fast_direct"
            if new_intel.get("target_changed"):
                changes.append("Re-evaluate approach due to target change")
                current_strategy = "adaptive"
            if new_intel.get("resource_constraint"):
                changes.append("Optimize for resource efficiency")
                current_strategy = "resource_optimized"

            if not changes:
                changes.append("No significant changes; maintaining current strategy")

            result = {
                "previous_strategy": mid_mission.get("strategy", "balanced"),
                "new_strategy": current_strategy,
                "changes": changes,
                "trigger": new_intel,
                "adapted_at": datetime.now(timezone.utc).isoformat(),
            }

            # Persist
            if self._conn:
                sid = f"adapt_{int(time.time() * 1000)}"
                self._conn.execute(
                    "INSERT INTO strategies (strategy_id, task_type, approach, rationale) VALUES (?, ?, ?, ?)",
                    (sid, "adaptation", current_strategy, json.dumps(changes)),
                )
                self._conn.commit()

            duration_ms = int((time.perf_counter() - start) * 1000)
            self._log_reasoning("adapt_strategy", mid_mission, result, 0.75, duration_ms)
            return self._result(True, "adapt_strategy", result, confidence=0.75, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "adapt_strategy", errors=[str(exc)])


# ------------------------------------------------------------------
# Usage example
# ------------------------------------------------------------------
if __name__ == "__main__":
    st = Strategist()
    task = {"type": "reconnaissance", "description": "Map network topology", "complexity": 6}
    print(st.select_approach(task, ["Alpha", "Beta-Recon", "Gamma"]))
    print(st.evaluate_speed_vs_thoroughness(task))
    print(st.evaluate_stealth_vs_visibility(task))
