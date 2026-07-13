"""
IRIS v1.0 — MetaLearner
Self-improvement and bias detection engine.

Records outcomes of plans, identifies systematic reasoning biases,
suggests improvements to reasoning processes, tracks prediction
accuracy, and updates internal models from new data.

Features:
- Record plan outcomes for learning
- Identify systematic biases in reasoning
- Suggest reasoning improvements
- Track prediction accuracy over time
- Update internal models from accumulated data

Storage:
    SQLite tables `outcomes`, `biases`, `predictions` (JSON fallback).

Usage:
    ml = MetaLearner()
    ml.record_outcome(plan, {"success": True, "duration_ms": 5000})
    biases = ml.identify_biases()
    improvements = ml.suggest_reasoning_improvements()
    accuracy = ml.track_prediction_accuracy()
    ml.update_models()

Author: IRIS Core Team
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .base_cortex import BaseCortex

logger = logging.getLogger("iris.cortex.meta_learner")


class MetaLearner(BaseCortex):
    """
    Self-improvement engine that learns from execution outcomes.

    Detects biases, tracks accuracy, and continuously refines
    reasoning models based on real-world feedback.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        iris_core: Optional[Any] = None,
    ) -> None:
        """
        Initialize MetaLearner.

        Args:
            db_path: Path to SQLite database. Defaults to env var
                     IRIS_META_LEARNER_DB or "iris_meta_learner.db".
            iris_core: Reference to IRIS core.
        """
        super().__init__(
            db_path=db_path or os.getenv("IRIS_META_LEARNER_DB", "iris_meta_learner.db"),
            iris_core=iris_core,
        )
        self._create_meta_tables()

    def _create_meta_tables(self) -> None:
        """Create meta-learning tables."""
        with self._lock:
            if self._conn:
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS outcomes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plan_id TEXT NOT NULL,
                        predicted_outcome TEXT,
                        actual_outcome TEXT,
                        accuracy REAL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS biases (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        bias_type TEXT NOT NULL,
                        description TEXT,
                        frequency INTEGER DEFAULT 1,
                        severity REAL DEFAULT 0.5,
                        detected_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS predictions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        prediction_id TEXT NOT NULL UNIQUE,
                        prediction_type TEXT,
                        predicted_value REAL,
                        actual_value REAL,
                        error REAL,
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
        Core reasoning: learn from an outcome.

        Args:
            input_data: Dict with plan and actual_result.
            context: Optional context.

        Returns:
            Standard result with learning outcome.
        """
        if isinstance(input_data, dict) and "plan" in input_data and "actual_result" in input_data:
            return self.record_outcome(input_data["plan"], input_data["actual_result"])
        return self._result(False, "reason", errors=["Input must contain plan and actual_result"])

    # ------------------------------------------------------------------
    # Meta-learning methods
    # ------------------------------------------------------------------
    def record_outcome(
        self,
        plan: Dict[str, Any],
        actual_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Record the outcome of a plan execution for learning.

        Args:
            plan: Plan dict that was executed.
            actual_result: Dict with actual success, duration, errors.

        Returns:
            Standard result with learning record.
        """
        start = time.perf_counter()
        try:
            plan_id = plan.get("plan_id", f"plan_{int(time.time() * 1000)}")
            predicted = plan.get("predicted_success", plan.get("estimates", {}))
            actual_success = actual_result.get("success", False)
            actual_duration = actual_result.get("duration_ms", 0)

            # Calculate accuracy
            predicted_success = predicted.get("success_probability", 0.5) if isinstance(predicted, dict) else 0.5
            accuracy = 1.0 - abs(predicted_success - (1.0 if actual_success else 0.0))

            outcome_record = {
                "plan_id": plan_id,
                "predicted": predicted,
                "actual": actual_result,
                "accuracy": round(accuracy, 4),
                "duration_delta_ms": actual_duration - plan.get("estimates", {}).get("total_duration_ms", 0),
            }

            # Persist
            if self._conn:
                self._conn.execute(
                    "INSERT INTO outcomes (plan_id, predicted_outcome, actual_outcome, accuracy) VALUES (?, ?, ?, ?)",
                    (plan_id, json.dumps(predicted), json.dumps(actual_result), accuracy),
                )
                self._conn.commit()

            duration_ms = int((time.perf_counter() - start) * 1000)
            self._log_reasoning("record_outcome", plan, outcome_record, accuracy, duration_ms)
            return self._result(True, "record_outcome", outcome_record, confidence=accuracy, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "record_outcome", errors=[str(exc)])

    def identify_biases(self) -> Dict[str, Any]:
        """
        Detect systematic errors in reasoning from outcome history.

        Returns:
            Standard result with list of detected biases.
        """
        start = time.perf_counter()
        try:
            biases = []

            if self._conn:
                rows = self._conn.execute(
                    "SELECT predicted_outcome, actual_outcome FROM outcomes ORDER BY created_at DESC LIMIT 100"
                ).fetchall()
            else:
                rows = []

            if not rows:
                biases.append({
                    "bias_type": "insufficient_data",
                    "description": "Not enough outcomes recorded to detect biases",
                    "severity": 0.3,
                    "recommendation": "Execute more missions to gather data",
                })
                duration_ms = int((time.perf_counter() - start) * 1000)
                return self._result(True, "identify_biases", biases, duration_ms=duration_ms)

            # Analyze prediction patterns
            overconfident = 0
            underconfident = 0
            total = len(rows)

            for row in rows:
                pred = json.loads(row[0]) if row[0] else {}
                actual = json.loads(row[1]) if row[1] else {}
                pred_prob = pred.get("success_probability", 0.5) if isinstance(pred, dict) else 0.5
                actual_success = actual.get("success", False) if isinstance(actual, dict) else False

                if pred_prob > 0.7 and not actual_success:
                    overconfident += 1
                if pred_prob < 0.3 and actual_success:
                    underconfident += 1

            if overconfident / total > 0.3:
                biases.append({
                    "bias_type": "overconfidence",
                    "description": f"Predicted high success but failed in {overconfident}/{total} cases",
                    "frequency": overconfident,
                    "severity": round(overconfident / total, 4),
                    "recommendation": "Add safety margin to success probability estimates",
                })

            if underconfident / total > 0.3:
                biases.append({
                    "bias_type": "underconfidence",
                    "description": f"Predicted low success but succeeded in {underconfident}/{total} cases",
                    "frequency": underconfident,
                    "severity": round(underconfident / total, 4),
                    "recommendation": "Review risk assessment criteria; may be too conservative",
                })

            # Check for recency bias
            if total >= 10:
                recent = rows[:10]
                older = rows[-10:] if len(rows) >= 20 else rows[10:]
                recent_accuracy = sum(1 for r in recent if json.loads(r[1] or '{}').get('success', False)) / len(recent) if recent else 0
                older_accuracy = sum(1 for r in older if json.loads(r[1] or '{}').get('success', False)) / len(older) if older else 0
                if abs(recent_accuracy - older_accuracy) > 0.3:
                    biases.append({
                        "bias_type": "recency_bias",
                        "description": f"Recent accuracy ({recent_accuracy:.2f}) differs significantly from older ({older_accuracy:.2f})",
                        "severity": 0.5,
                        "recommendation": "Weight historical data more evenly; recent events may be anomalies",
                    })

            if not biases:
                biases.append({
                    "bias_type": "none_detected",
                    "description": "No significant biases detected in current data",
                    "severity": 0.0,
                    "recommendation": "Continue monitoring",
                })

            # Persist detected biases
            if self._conn:
                for b in biases:
                    if b["bias_type"] != "none_detected":
                        self._conn.execute(
                            """
                            INSERT INTO biases (bias_type, description, frequency, severity)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(bias_type) DO UPDATE SET
                            frequency = frequency + excluded.frequency,
                            severity = (severity + excluded.severity) / 2
                            """,
                            (b["bias_type"], b["description"], b.get("frequency", 1), b["severity"]),
                        )
                self._conn.commit()

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "identify_biases", biases, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "identify_biases", errors=[str(exc)])

    def suggest_reasoning_improvements(self) -> Dict[str, Any]:
        """
        Suggest how to improve reasoning based on detected biases.

        Returns:
            Standard result with list of improvement suggestions.
        """
        start = time.perf_counter()
        try:
            biases = self.identify_biases().get("data", [])
            suggestions = []

            for bias in biases:
                btype = bias.get("bias_type", "")
                if btype == "overconfidence":
                    suggestions.append({
                        "area": "confidence_calibration",
                        "suggestion": "Apply a 0.8 confidence discount factor to all predictions above 0.7",
                        "expected_impact": "Reduce false positive rate by ~15%",
                        "priority": "high",
                    })
                    suggestions.append({
                        "area": "risk_assessment",
                        "suggestion": "Increase risk score buffer by 0.1 for all high-confidence plans",
                        "expected_impact": "Catch edge cases earlier",
                        "priority": "high",
                    })
                elif btype == "underconfidence":
                    suggestions.append({
                        "area": "confidence_calibration",
                        "suggestion": "Remove conservative penalty for well-tested techniques",
                        "expected_impact": "Increase true positive rate by ~10%",
                        "priority": "medium",
                    })
                elif btype == "recency_bias":
                    suggestions.append({
                        "area": "data_weighting",
                        "suggestion": "Use exponential decay weighting for historical outcomes",
                        "expected_impact": "More stable predictions across time periods",
                        "priority": "medium",
                    })
                elif btype == "insufficient_data":
                    suggestions.append({
                        "area": "data_collection",
                        "suggestion": "Run synthetic training missions to build dataset",
                        "expected_impact": "Enable bias detection within 50 more samples",
                        "priority": "high",
                    })

            if not suggestions:
                suggestions.append({
                    "area": "general",
                    "suggestion": "Continue current reasoning approach; no significant issues detected",
                    "expected_impact": "Maintain current performance",
                    "priority": "low",
                })

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "suggest_reasoning_improvements", suggestions, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "suggest_reasoning_improvements", errors=[str(exc)])

    def track_prediction_accuracy(self) -> Dict[str, Any]:
        """
        Calculate how often predictions were correct.

        Returns:
            Standard result with accuracy statistics.
        """
        start = time.perf_counter()
        try:
            if self._conn:
                rows = self._conn.execute(
                    "SELECT accuracy FROM outcomes ORDER BY created_at DESC LIMIT 1000"
                ).fetchall()
                accuracies = [r[0] for r in rows if r[0] is not None]
            else:
                accuracies = []

            if not accuracies:
                return self._result(True, "track_prediction_accuracy", {
                    "total_predictions": 0,
                    "mean_accuracy": 0.0,
                    "median_accuracy": 0.0,
                    "trend": "insufficient_data",
                }, duration_ms=int((time.perf_counter()-start)*1000))

            total = len(accuracies)
            mean_acc = sum(accuracies) / total
            sorted_acc = sorted(accuracies)
            median_acc = sorted_acc[total // 2] if total % 2 == 1 else (sorted_acc[total // 2 - 1] + sorted_acc[total // 2]) / 2

            # Trend analysis
            if total >= 10:
                recent = sum(accuracies[:10]) / 10
                older = sum(accuracies[-10:]) / 10 if total >= 20 else mean_acc
                if recent > older + 0.05:
                    trend = "improving"
                elif recent < older - 0.05:
                    trend = "declining"
                else:
                    trend = "stable"
            else:
                trend = "insufficient_data"

            data = {
                "total_predictions": total,
                "mean_accuracy": round(mean_acc, 4),
                "median_accuracy": round(median_acc, 4),
                "min_accuracy": round(min(accuracies), 4),
                "max_accuracy": round(max(accuracies), 4),
                "trend": trend,
            }
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "track_prediction_accuracy", data, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "track_prediction_accuracy", errors=[str(exc)])

    def update_models(self) -> Dict[str, Any]:
        """
        Retrain internal models from accumulated data.

        Updates success probability baselines based on historical accuracy.

        Returns:
            Standard result with update status.
        """
        start = time.perf_counter()
        try:
            accuracy_stats = self.track_prediction_accuracy().get("data", {})
            mean_acc = accuracy_stats.get("mean_accuracy", 0.5)
            total = accuracy_stats.get("total_predictions", 0)

            if total < 10:
                return self._result(True, "update_models", {
                    "status": "skipped",
                    "reason": "Insufficient data for model update",
                    "minimum_required": 10,
                    "current": total,
                }, duration_ms=int((time.perf_counter()-start)*1000))

            # Adjust confidence calibration based on accuracy
            calibration_factor = mean_acc
            if mean_acc < 0.6:
                calibration_factor = 0.7  # Reduce overconfidence
            elif mean_acc > 0.9:
                calibration_factor = 1.0  # Well calibrated

            # Update stored calibration
            if self._conn:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO predictions
                    (prediction_id, prediction_type, predicted_value, actual_value, error)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    ("calibration", "meta", calibration_factor, mean_acc, abs(calibration_factor - mean_acc)),
                )
                self._conn.commit()

            data = {
                "status": "updated",
                "calibration_factor": round(calibration_factor, 4),
                "based_on_predictions": total,
                "mean_accuracy": round(mean_acc, 4),
                "next_update_recommended": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            }
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "update_models", data, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "update_models", errors=[str(exc)])


# ------------------------------------------------------------------
# Usage example
# ------------------------------------------------------------------
if __name__ == "__main__":
    ml = MetaLearner()
    plan = {"plan_id": "p-001", "predicted_success": {"success_probability": 0.9}, "estimates": {"total_duration_ms": 300000}}
    actual = {"success": False, "duration_ms": 600000, "errors": ["timeout"]}
    print(ml.record_outcome(plan, actual))
    print(ml.identify_biases())
    print(ml.suggest_reasoning_improvements())
