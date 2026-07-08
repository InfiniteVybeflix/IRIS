"""
IRIS v7.0 — HypothesisTester
"What-if" simulation and falsification engine.

Generates hypotheses from observations, tests them against available
data, simulates outcomes of actions, compares scenarios side-by-side,
and identifies what would falsify a hypothesis.

Features:
- Generate hypotheses from observations
- Test hypotheses against available data
- Simulate action outcomes
- Compare multiple scenarios
- Falsify hypotheses by identifying disproving conditions

Storage:
    SQLite table `hypotheses` (JSON fallback).

Usage:
    ht = HypothesisTester()
    hypotheses = ht.generate_hypotheses({"anomaly": "unusual_traffic"})
    test = ht.test_hypothesis(hypotheses[0], available_data)
    sim = ht.simulate_outcome("block_ip", {"current_state": "under_attack"})

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

logger = logging.getLogger("iris.cortex.hypothesis_tester")


class HypothesisTester(BaseCortex):
    """
    Hypothesis generation, testing, and falsification engine.

    Enables IRIS to reason about possible explanations, predict
    outcomes, and identify conditions that would disprove beliefs.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        iris_core: Optional[Any] = None,
    ) -> None:
        """
        Initialize HypothesisTester.

        Args:
            db_path: Path to SQLite database. Defaults to env var
                     IRIS_HYPOTHESIS_DB or "iris_hypothesis_tester.db".
            iris_core: Reference to IRIS core.
        """
        super().__init__(
            db_path=db_path or os.getenv("IRIS_HYPOTHESIS_DB", "iris_hypothesis_tester.db"),
            iris_core=iris_core,
        )
        self._create_hypothesis_tables()

    def _create_hypothesis_tables(self) -> None:
        """Create hypothesis tracking tables."""
        with self._lock:
            if self._conn:
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS hypotheses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        hypothesis_id TEXT NOT NULL UNIQUE,
                        observation TEXT NOT NULL,
                        hypothesis TEXT NOT NULL,
                        test_result TEXT,
                        confidence REAL DEFAULT 0.5,
                        status TEXT DEFAULT "pending",
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
        Core reasoning: generate and test hypotheses.

        Args:
            input_data: Observation dict.
            context: Optional context with available data.

        Returns:
            Standard result with tested hypotheses.
        """
        if isinstance(input_data, dict):
            hypotheses = self.generate_hypotheses(input_data).get("data", [])
            if hypotheses and context:
                return self.test_hypothesis(hypotheses[0], context)
            return self._result(True, "reason", hypotheses)
        return self._result(False, "reason", errors=["Input must be observation dict"])

    # ------------------------------------------------------------------
    # Hypothesis methods
    # ------------------------------------------------------------------
    def generate_hypotheses(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate possible explanations for an observation.

        Args:
            observation: Dict describing what was observed.

        Returns:
            Standard result with list of hypothesis dicts.
        """
        start = time.perf_counter()
        try:
            hypotheses = []
            obs_type = observation.get("type", "unknown")
            obs_value = observation.get("value", observation)

            # Pattern-based hypothesis generation
            if obs_type == "anomaly" or "anomaly" in str(obs_value).lower():
                hypotheses.extend([
                    {"id": f"hyp_{int(time.time()*1000)}_1", "description": "System under active attack", "category": "security", "prior_probability": 0.3},
                    {"id": f"hyp_{int(time.time()*1000)}_2", "description": "Normal traffic spike from legitimate users", "category": "benign", "prior_probability": 0.4},
                    {"id": f"hyp_{int(time.time()*1000)}_3", "description": "Misconfigured monitoring generating false positives", "category": "technical", "prior_probability": 0.2},
                    {"id": f"hyp_{int(time.time()*1000)}_4", "description": "Insider threat or compromised credentials", "category": "security", "prior_probability": 0.1},
                ])
            elif obs_type == "failure" or "failure" in str(obs_value).lower():
                hypotheses.extend([
                    {"id": f"hyp_{int(time.time()*1000)}_1", "description": "Resource exhaustion (CPU/memory)", "category": "technical", "prior_probability": 0.35},
                    {"id": f"hyp_{int(time.time()*1000)}_2", "description": "Dependency service failure", "category": "technical", "prior_probability": 0.3},
                    {"id": f"hyp_{int(time.time()*1000)}_3", "description": "Code bug introduced in recent deployment", "category": "technical", "prior_probability": 0.25},
                    {"id": f"hyp_{int(time.time()*1000)}_4", "description": "External interference or attack", "category": "security", "prior_probability": 0.1},
                ])
            elif obs_type == "performance_degradation":
                hypotheses.extend([
                    {"id": f"hyp_{int(time.time()*1000)}_1", "description": "Database query bottleneck", "category": "technical", "prior_probability": 0.4},
                    {"id": f"hyp_{int(time.time()*1000)}_2", "description": "Network latency increase", "category": "technical", "prior_probability": 0.3},
                    {"id": f"hyp_{int(time.time()*1000)}_3", "description": "Increased load beyond capacity", "category": "scaling", "prior_probability": 0.2},
                    {"id": f"hyp_{int(time.time()*1000)}_4", "description": "Memory leak causing GC pressure", "category": "technical", "prior_probability": 0.1},
                ])
            else:
                hypotheses.extend([
                    {"id": f"hyp_{int(time.time()*1000)}_1", "description": f"Standard behavior for {obs_type}", "category": "normal", "prior_probability": 0.5},
                    {"id": f"hyp_{int(time.time()*1000)}_2", "description": "Minor deviation within acceptable range", "category": "normal", "prior_probability": 0.3},
                    {"id": f"hyp_{int(time.time()*1000)}_3", "description": "Requires further investigation", "category": "uncertain", "prior_probability": 0.2},
                ])

            # Persist
            if self._conn:
                for h in hypotheses:
                    self._conn.execute(
                        "INSERT INTO hypotheses (hypothesis_id, observation, hypothesis, status) VALUES (?, ?, ?, ?)",
                        (h["id"], json.dumps(observation), h["description"], "pending"),
                    )
                self._conn.commit()

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "generate_hypotheses", hypotheses, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "generate_hypotheses", errors=[str(exc)])

    def test_hypothesis(
        self,
        hypothesis: Dict[str, Any],
        available_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Test a hypothesis against available data.

        Args:
            hypothesis: Hypothesis dict from generate_hypotheses.
            available_data: Dict with evidence, metrics, logs.

        Returns:
            Standard result with test outcome.
        """
        start = time.perf_counter()
        try:
            desc = hypothesis.get("description", "").lower()
            evidence = available_data.get("evidence", {})
            metrics = available_data.get("metrics", {})
            logs = available_data.get("logs", [])

            supporting = []
            contradicting = []
            confidence = hypothesis.get("prior_probability", 0.5)

            # Test logic based on hypothesis type
            if "attack" in desc or "compromised" in desc:
                if evidence.get("failed_logins", 0) > 10:
                    supporting.append(f"High failed login count: {evidence['failed_logins']}")
                    confidence += 0.2
                if evidence.get("unusual_ips"):
                    supporting.append(f"Unusual IPs detected: {evidence['unusual_ips']}")
                    confidence += 0.15
                if metrics.get("cpu_usage", 0) < 0.3:
                    contradicting.append("Low CPU usage contradicts attack hypothesis")
                    confidence -= 0.1

            elif "resource exhaustion" in desc or "bottleneck" in desc:
                if metrics.get("cpu_usage", 0) > 0.9:
                    supporting.append(f"High CPU: {metrics['cpu_usage']}")
                    confidence += 0.25
                if metrics.get("memory_usage", 0) > 0.9:
                    supporting.append(f"High memory: {metrics['memory_usage']}")
                    confidence += 0.25
                if metrics.get("cpu_usage", 0) < 0.5 and metrics.get("memory_usage", 0) < 0.5:
                    contradicting.append("Normal resource usage contradicts exhaustion")
                    confidence -= 0.2

            elif "network" in desc or "latency" in desc:
                if metrics.get("network_latency_ms", 0) > 500:
                    supporting.append(f"High latency: {metrics['network_latency_ms']}ms")
                    confidence += 0.2
                if metrics.get("packet_loss", 0) > 0.05:
                    supporting.append(f"Packet loss: {metrics['packet_loss']}")
                    confidence += 0.15

            elif "database" in desc:
                if metrics.get("db_query_time_ms", 0) > 1000:
                    supporting.append(f"Slow queries: {metrics['db_query_time_ms']}ms")
                    confidence += 0.2
                if logs and any("timeout" in str(log).lower() for log in logs):
                    supporting.append("Database timeouts in logs")
                    confidence += 0.15

            confidence = max(0.0, min(1.0, confidence))

            result = {
                "hypothesis": hypothesis,
                "confidence": round(confidence, 4),
                "supporting_evidence": supporting,
                "contradicting_evidence": contradicting,
                "verdict": "supported" if confidence >= 0.7 else "rejected" if confidence <= 0.3 else "uncertain",
            }

            # Update hypothesis status
            if self._conn:
                self._conn.execute(
                    "UPDATE hypotheses SET test_result = ?, confidence = ?, status = ? WHERE hypothesis_id = ?",
                    (json.dumps(result), confidence, result["verdict"], hypothesis.get("id", "")),
                )
                self._conn.commit()

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "test_hypothesis", result, confidence=confidence, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "test_hypothesis", errors=[str(exc)])

    def simulate_outcome(
        self,
        action: str,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Predict the result of taking an action in a given state.

        Args:
            action: Action name.
            state: Current system state dict.

        Returns:
            Standard result with predicted outcome.
        """
        start = time.perf_counter()
        try:
            action_lower = action.lower()
            current_state = state.get("status", "unknown")
            threat_level = state.get("threat_level", 0.5)
            resources = state.get("resources", {})

            predicted = {
                "action": action,
                "current_state": current_state,
                "predicted_state": current_state,
                "success_probability": 0.5,
                "side_effects": [],
                "resource_impact": {},
            }

            if "block" in action_lower or "deny" in action_lower:
                predicted["predicted_state"] = "protected"
                predicted["success_probability"] = 0.85
                predicted["side_effects"] = ["May block legitimate traffic", "Could trigger retaliation"]
                predicted["resource_impact"] = {"cpu": 0.1, "memory": 0.05}

            elif "scan" in action_lower or "probe" in action_lower:
                predicted["predicted_state"] = "information_gathered"
                predicted["success_probability"] = 0.9
                predicted["side_effects"] = ["May be detected by target", "Generates network traffic"]
                predicted["resource_impact"] = {"cpu": 0.2, "bandwidth": 0.3}

            elif "patch" in action_lower or "fix" in action_lower:
                predicted["predicted_state"] = "remediated"
                predicted["success_probability"] = 0.8
                predicted["side_effects"] = ["May cause service interruption", "Requires testing"]
                predicted["resource_impact"] = {"cpu": 0.3, "memory": 0.1, "downtime_ms": 30000}

            elif "escalate" in action_lower or "alert" in action_lower:
                predicted["predicted_state"] = "alerted"
                predicted["success_probability"] = 0.95
                predicted["side_effects"] = ["Human intervention required", "May cause panic"]
                predicted["resource_impact"] = {"cpu": 0.05}

            elif "isolate" in action_lower or "quarantine" in action_lower:
                predicted["predicted_state"] = "contained"
                predicted["success_probability"] = 0.75
                predicted["side_effects"] = ["Service disruption", "Data access limited"]
                predicted["resource_impact"] = {"cpu": 0.15, "connectivity": -1.0}

            else:
                predicted["predicted_state"] = "modified"
                predicted["success_probability"] = 0.6
                predicted["side_effects"] = ["Unknown side effects possible"]

            # Adjust based on threat level
            if threat_level > 0.7:
                predicted["success_probability"] = max(0.0, predicted["success_probability"] - 0.15)
                predicted["side_effects"].append("High threat environment reduces effectiveness")

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "simulate_outcome", predicted, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "simulate_outcome", errors=[str(exc)])

    def compare_scenarios(self, scenarios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Side-by-side comparison of multiple scenarios.

        Args:
            scenarios: List of scenario dicts, each with name, actions, expected_outcome.

        Returns:
            Standard result with comparison list.
        """
        start = time.perf_counter()
        try:
            comparisons = []
            for scenario in scenarios:
                name = scenario.get("name", "unknown")
                actions = scenario.get("actions", [])
                expected = scenario.get("expected_outcome", {})

                # Simulate each action in sequence
                current_state = scenario.get("initial_state", {})
                total_prob = 1.0
                side_effects = []
                for action in actions:
                    sim = self.simulate_outcome(action, current_state).get("data", {})
                    total_prob *= sim.get("success_probability", 0.5)
                    current_state = {"status": sim.get("predicted_state", "unknown")}
                    side_effects.extend(sim.get("side_effects", []))

                comparisons.append({
                    "scenario": name,
                    "actions": actions,
                    "cumulative_success_probability": round(total_prob, 4),
                    "final_predicted_state": current_state.get("status", "unknown"),
                    "side_effects": list(set(side_effects)),
                    "expected_vs_predicted": "match" if current_state.get("status") == expected.get("state") else "mismatch",
                })

            # Sort by success probability descending
            comparisons.sort(key=lambda x: x["cumulative_success_probability"], reverse=True)

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "compare_scenarios", comparisons, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "compare_scenarios", errors=[str(exc)])

    def falsify_hypothesis(self, hypothesis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Identify what would prove a hypothesis wrong.

        Args:
            hypothesis: Hypothesis dict.

        Returns:
            Standard result with falsification conditions.
        """
        start = time.perf_counter()
        try:
            desc = hypothesis.get("description", "").lower()
            falsifiers = []

            if "attack" in desc or "compromised" in desc or "breach" in desc:
                falsifiers = [
                    "No failed login attempts detected",
                    "All traffic originates from known sources",
                    "No anomalous process behavior observed",
                    "Security logs show no indicators of compromise",
                    "Network traffic patterns match baseline",
                ]
            elif "resource exhaustion" in desc or "bottleneck" in desc:
                falsifiers = [
                    "CPU and memory usage within normal ranges",
                    "No processes consuming excessive resources",
                    "System responds within SLA thresholds",
                    "No queue buildup or backpressure detected",
                ]
            elif "network" in desc or "latency" in desc:
                falsifiers = [
                    "Latency measurements within normal range",
                    "No packet loss detected",
                    "Traceroute shows normal path",
                    "DNS resolution functioning correctly",
                ]
            elif "database" in desc:
                falsifiers = [
                    "Query execution times within normal range",
                    "No connection pool exhaustion",
                    "Database locks not causing contention",
                    "Index usage is optimal",
                ]
            else:
                falsifiers = [
                    "Observation does not repeat under same conditions",
                    "Alternative explanation better fits the data",
                    "Predicted consequences do not materialize",
                ]

            result = {
                "hypothesis": hypothesis,
                "falsification_conditions": falsifiers,
                "test_recommendation": "Monitor for these conditions; if any are observed, reject the hypothesis",
            }

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "falsify_hypothesis", result, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "falsify_hypothesis", errors=[str(exc)])


# ------------------------------------------------------------------
# Usage example
# ------------------------------------------------------------------
if __name__ == "__main__":
    ht = HypothesisTester()
    obs = {"type": "anomaly", "value": "unusual_traffic_spike"}
    hypotheses = ht.generate_hypotheses(obs)
    print(json.dumps(hypotheses, indent=2))

    data = {"evidence": {"failed_logins": 15, "unusual_ips": ["10.0.0.99"]}, "metrics": {"cpu_usage": 0.95}}
    test = ht.test_hypothesis(hypotheses["data"][0], data)
    print(json.dumps(test, indent=2))
