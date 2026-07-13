"""
IRIS v1.0 — LearningEngine
Pattern extraction and improvement engine.

Analyzes mission history to identify success/failure patterns,
predict mission success probability, suggest plan improvements,
detect skill gaps, generate training scenarios, and update
beliefs using Bayesian inference.

Features:
- Analyze mission patterns over time
- Predict success probability for plans
- Suggest specific plan improvements
- Detect missing capabilities
- Generate synthetic training missions
- Bayesian belief updates from evidence

Storage:
    SQLite table `beliefs` (JSON fallback).

Usage:
    le = LearningEngine(agent_memory, mission_archive, skill_memory)
    patterns = le.analyze_mission_patterns()
    prob = le.predict_success_probability(plan)
    gaps = le.detect_skill_gaps()
    le.update_beliefs({"technique_X_works": 0.9})

Author: IRIS Core Team
"""

from __future__ import annotations

import json
import logging
import os
import random
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base_memory import BaseMemory

logger = logging.getLogger("iris.memory.learning_engine")


class LearningEngine(BaseMemory):
    """
    Pattern extraction, prediction, and continuous improvement engine.

    Learns from historical mission data to improve future decisions
    through statistical analysis and Bayesian belief updating.
    """

    def __init__(
        self,
        agent_memory: Optional[Any] = None,
        mission_archive: Optional[Any] = None,
        skill_memory: Optional[Any] = None,
        db_path: Optional[str] = None,
        iris_core: Optional[Any] = None,
    ) -> None:
        """
        Initialize LearningEngine.

        Args:
            agent_memory: AgentMemory instance for agent performance data.
            mission_archive: MissionArchive instance for mission history.
            skill_memory: SkillMemory instance for technique data.
            db_path: Path to SQLite database. Defaults to env var
                     IRIS_LEARNING_DB or "iris_learning.db".
            iris_core: Reference to IRIS core.
        """
        super().__init__(
            db_path=db_path or os.getenv("IRIS_LEARNING_DB", "iris_learning.db"),
            iris_core=iris_core,
        )
        self.agent_memory = agent_memory
        self.mission_archive = mission_archive
        self.skill_memory = skill_memory
        self._create_learning_tables()

    def _create_learning_tables(self) -> None:
        """Create learning engine tables."""
        with self._lock:
            if self._conn:
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS beliefs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        belief_key TEXT NOT NULL UNIQUE,
                        probability REAL DEFAULT 0.5,
                        evidence_count INTEGER DEFAULT 0,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                self._conn.commit()

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------
    def store(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Store a belief. Value should be probability float."""
        if not isinstance(value, (int, float)):
            return self._result(False, "store", errors=["Value must be probability float 0.0-1.0"])
        return self.update_beliefs({key: float(value)})

    def retrieve(self, key: str) -> Dict[str, Any]:
        """Retrieve belief probability by key."""
        start = time.perf_counter()
        try:
            if self.use_sqlite:
                row = self._sql_execute_one("SELECT * FROM beliefs WHERE belief_key = ?", (key,))
                if row:
                    data = {"belief_key": row[1], "probability": row[2], "evidence_count": row[3], "updated_at": row[4]}
                    return self._result(True, "retrieve", data, duration_ms=int((time.perf_counter()-start)*1000))
            else:
                data = self._json_read(key)
                if data:
                    return self._result(True, "retrieve", data, duration_ms=int((time.perf_counter()-start)*1000))
            return self._result(False, "retrieve", errors=[f"Belief {key} not found"])
        except Exception as exc:
            return self._result(False, "retrieve", errors=[str(exc)])

    def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search beliefs by key."""
        start = time.perf_counter()
        try:
            results = []
            if self.use_sqlite:
                rows = self._sql_execute(
                    "SELECT * FROM beliefs WHERE belief_key LIKE ? LIMIT ?",
                    (f"%{query}%", limit),
                )
                for row in rows:
                    results.append({"belief_key": row[1], "probability": row[2], "evidence_count": row[3], "updated_at": row[4]})
            else:
                for item in self._json_list():
                    if query.lower() in str(item.get("belief_key", "")).lower():
                        results.append(item)
                    if len(results) >= limit:
                        break
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "search", results, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "search", errors=[str(exc)])

    def update(self, key: str, value: Any) -> Dict[str, Any]:
        """Update belief probability."""
        return self.store(key, value)

    def delete(self, key: str) -> Dict[str, Any]:
        """Delete a belief."""
        start = time.perf_counter()
        try:
            if self.use_sqlite:
                self._sql_execute("DELETE FROM beliefs WHERE belief_key = ?", (key,))
            else:
                self._json_delete(key)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "delete", duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "delete", errors=[str(exc)])

    def list_all(self, filter_: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """List all beliefs."""
        start = time.perf_counter()
        try:
            results = []
            if self.use_sqlite:
                rows = self._sql_execute("SELECT * FROM beliefs ORDER BY updated_at DESC", ())
                for row in rows:
                    results.append({"belief_key": row[1], "probability": row[2], "evidence_count": row[3], "updated_at": row[4]})
            else:
                results = self._json_list()
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "list_all", results, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "list_all", errors=[str(exc)])

    # ------------------------------------------------------------------
    # Learning methods
    # ------------------------------------------------------------------
    def analyze_mission_patterns(self, time_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Identify common success and failure patterns across missions.

        Args:
            time_range: Optional dict with "from" and "to" ISO dates.

        Returns:
            Standard result with patterns list.
        """
        start = time.perf_counter()
        try:
            if not self.mission_archive:
                return self._result(False, "analyze_mission_patterns", errors=["MissionArchive not connected"])

            missions = self.mission_archive.list_all().get("data", [])
            if time_range:
                missions = [
                    m for m in missions
                    if time_range.get("from", "") <= m.get("created_at", "") <= time_range.get("to", "9999")
                ]

            success_patterns = Counter()
            failure_patterns = Counter()

            for m in missions:
                tasks = m.get("tasks", [])
                outcomes = m.get("outcomes", {})
                success = outcomes.get("success", False)
                errors = outcomes.get("errors", [])

                for t in tasks:
                    pattern = f"{t.get('type', 'unknown')}:{t.get('technique', 'unknown')}"
                    if success:
                        success_patterns[pattern] += 1
                    else:
                        failure_patterns[pattern] += 1

                for err in errors:
                    failure_patterns[f"error:{err}"] += 1

            patterns = []
            for pat, count in success_patterns.most_common(10):
                patterns.append({
                    "pattern": pat,
                    "type": "success",
                    "frequency": count,
                    "confidence": round(count / len(missions), 4) if missions else 0,
                })
            for pat, count in failure_patterns.most_common(10):
                patterns.append({
                    "pattern": pat,
                    "type": "failure",
                    "frequency": count,
                    "confidence": round(count / len(missions), 4) if missions else 0,
                })

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "analyze_mission_patterns", patterns, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "analyze_mission_patterns", errors=[str(exc)])

    def predict_success_probability(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict the likelihood of success for a given plan.

        Uses historical mission data and technique success rates.

        Args:
            plan: Dict with tasks list, each task having type and technique.

        Returns:
            Standard result with probability 0.0-1.0.
        """
        start = time.perf_counter()
        try:
            if not self.mission_archive or not self.skill_memory:
                return self._result(False, "predict_success_probability", errors=["Dependencies not connected"])

            tasks = plan.get("tasks", [])
            if not tasks:
                return self._result(True, "predict_success_probability", 0.5, duration_ms=int((time.perf_counter()-start)*1000))

            scores = []
            for task in tasks:
                ttype = task.get("type", "unknown")
                tech = task.get("technique", "unknown")
                # Get technique stats
                stats = self.skill_memory.get_technique_stats(tech).get("data", {})
                rate = stats.get("success_rate", 0.5)
                # Get task type stats from missions
                missions = self.mission_archive.search_missions("", filters={"mission_type": ttype}).get("data", [])
                if missions:
                    successful = sum(1 for m in missions if m.get("outcomes", {}).get("success", False))
                    task_rate = successful / len(missions)
                else:
                    task_rate = 0.5
                # Blend
                scores.append(0.6 * rate + 0.4 * task_rate)

            probability = sum(scores) / len(scores) if scores else 0.5
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "predict_success_probability", round(probability, 4), duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "predict_success_probability", errors=[str(exc)])

    def suggest_plan_improvements(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recommend specific improvements to a plan.

        Args:
            plan: Dict with tasks list.

        Returns:
            Standard result with list of recommendations.
        """
        start = time.perf_counter()
        try:
            if not self.skill_memory:
                return self._result(False, "suggest_plan_improvements", errors=["SkillMemory not connected"])

            recommendations = []
            tasks = plan.get("tasks", [])
            for task in tasks:
                ttype = task.get("type", "unknown")
                tech = task.get("technique", "unknown")
                # Check if better technique exists
                best = self.skill_memory.get_best_technique(ttype).get("data")
                if best and best["technique"] != tech:
                    recommendations.append({
                        "type": "better_technique",
                        "task": task,
                        "current": tech,
                        "recommended": best["technique"],
                        "reason": f"Higher success rate ({best['success_rate']})",
                    })
                # Check if technique is deprecated
                deprecated = self.skill_memory.get_deprecated_techniques().get("data", [])
                for dep in deprecated:
                    if dep["technique"] == tech:
                        recommendations.append({
                            "type": "deprecated_technique",
                            "task": task,
                            "technique": tech,
                            "reason": f"Declining success rate: {dep['recent_rate']} (was {dep['overall_rate']})",
                        })

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "suggest_plan_improvements", recommendations, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "suggest_plan_improvements", errors=[str(exc)])

    def detect_skill_gaps(self) -> Dict[str, Any]:
        """
        Identify capabilities that are missing or underperforming.

        Returns:
            Standard result with list of skill gaps.
        """
        start = time.perf_counter()
        try:
            if not self.skill_memory or not self.agent_memory:
                return self._result(False, "detect_skill_gaps", errors=["Dependencies not connected"])

            gaps = []
            # Check all task types
            all_records = self.skill_memory.list_all().get("data", [])
            task_types = set(r.get("task_type") for r in all_records)

            for ttype in task_types:
                stats = self.skill_memory._get_task_type_stats(ttype)
                if not stats:
                    gaps.append({"task_type": ttype, "gap": "no_data", "severity": "high"})
                    continue
                best_rate = max((s["success_rate"] for s in stats.values()), default=0)
                if best_rate < 0.5:
                    gaps.append({
                        "task_type": ttype,
                        "gap": "low_success_rate",
                        "severity": "high",
                        "best_rate": round(best_rate, 4),
                    })
                elif best_rate < 0.7:
                    gaps.append({
                        "task_type": ttype,
                        "gap": "moderate_success_rate",
                        "severity": "medium",
                        "best_rate": round(best_rate, 4),
                    })

            # Check for task types with no successful agents
            for ttype in task_types:
                best_agent = self.agent_memory.compare_agents(ttype).get("data", [])
                if not best_agent or best_agent[0]["success_rate"] < 0.3:
                    gaps.append({
                        "task_type": ttype,
                        "gap": "no_capable_agent",
                        "severity": "critical",
                    })

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "detect_skill_gaps", gaps, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "detect_skill_gaps", errors=[str(exc)])

    def generate_training_scenarios(self) -> Dict[str, Any]:
        """
        Generate synthetic missions for practice.

        Creates missions based on identified skill gaps.

        Returns:
            Standard result with list of training scenarios.
        """
        start = time.perf_counter()
        try:
            gaps = self.detect_skill_gaps().get("data", [])
            scenarios = []
            for gap in gaps:
                ttype = gap.get("task_type", "general")
                scenarios.append({
                    "scenario_id": f"train_{ttype}_{int(time.time() * 1000)}",
                    "task_type": ttype,
                    "difficulty": "medium",
                    "objective": f"Practice and improve {ttype} skills",
                    "constraints": {"max_duration_ms": 300000, "allow_retries": True},
                    "evaluation_criteria": ["success", "duration", "cleanliness"],
                })

            # Add some random scenarios for variety
            task_types = ["reconnaissance", "exploitation", "persistence", "evasion", "data_exfiltration"]
            for _ in range(3):
                ttype = random.choice(task_types)
                scenarios.append({
                    "scenario_id": f"train_{ttype}_{int(time.time() * 1000)}_{random.randint(1000,9999)}",
                    "task_type": ttype,
                    "difficulty": random.choice(["easy", "medium", "hard"]),
                    "objective": f"Random training: {ttype}",
                    "constraints": {"max_duration_ms": random.choice([60000, 120000, 300000])},
                    "evaluation_criteria": ["success", "duration"],
                })

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "generate_training_scenarios", scenarios, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "generate_training_scenarios", errors=[str(exc)])

    def update_beliefs(self, evidence: Dict[str, float]) -> Dict[str, Any]:
        """
        Update beliefs using Bayesian inference.

        P(H|E) = P(E|H) * P(H) / P(E)

        Simplified: update probability toward evidence, weighted by
        evidence strength and prior confidence.

        Args:
            evidence: Dict mapping belief_key to observed probability (0.0-1.0).

        Returns:
            Standard result with updated beliefs.
        """
        start = time.perf_counter()
        try:
            updated = []
            for key, observed_prob in evidence.items():
                # Retrieve current belief
                current = self.retrieve(key).get("data", {})
                prior = current.get("probability", 0.5)
                count = current.get("evidence_count", 0)

                # Bayesian-like update: weighted average
                # New belief = (prior * count + observed) / (count + 1)
                new_prob = (prior * count + observed_prob) / (count + 1)
                new_count = count + 1

                if self.use_sqlite:
                    self._sql_execute(
                        """
                        INSERT OR REPLACE INTO beliefs
                        (belief_key, probability, evidence_count, updated_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (key, round(new_prob, 6), new_count, datetime.now(timezone.utc).isoformat()),
                    )
                else:
                    self._json_write(
                        key,
                        {"belief_key": key, "probability": new_prob, "evidence_count": new_count},
                    )
                updated.append({"belief_key": key, "probability": round(new_prob, 4), "evidence_count": new_count})

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "update_beliefs", updated, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "update_beliefs", errors=[str(exc)])


# ------------------------------------------------------------------
# Usage example
# ------------------------------------------------------------------
if __name__ == "__main__":
    le = LearningEngine()
    le.update_beliefs({"port_scanning_works": 0.9, "social_engineering_risky": 0.3})
    print(le.retrieve("port_scanning_works"))
    print(le.list_all())
