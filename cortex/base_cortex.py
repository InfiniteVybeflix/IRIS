"""
IRIS v1.0 — BaseCortex
Abstract base class for all reasoning modules.

Provides the foundation for IRIS's cognitive reasoning with:
- Core reasoning method with structured output
- Option evaluation against criteria
- Human-readable explanation generation
- Self-assessed confidence scoring
- Thread-safe operations
- Standard result envelope

Every reasoning module in IRIS inherits from BaseCortex.

Usage:
    class MyReasoner(BaseCortex):
        def reason(self, input_data, context=None):
            # Real reasoning logic here
            return self._result(True, "reason", {"conclusion": "..."})

Author: IRIS Core Team
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("iris.cortex.base")


class IRISConnectable:
    """Interface contract: every module connects to IRIS core."""

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        self.iris_core = iris_core
        self.status = "idle"
        self._lock = threading.RLock()

    def health_check(self) -> Dict[str, Any]:
        """Return health status: available, degraded, or error."""
        return {
            "status": self.status,
            "module": self.__class__.__name__,
            "available": self.status != "error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def status_report(self) -> Dict[str, Any]:
        """Current operational status."""
        return {
            "module": self.__class__.__name__,
            "status": self.status,
            "iris_connected": self.iris_core is not None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def report(self, finding: Dict[str, Any]) -> None:
        """Send finding to IRIS core or log if unavailable."""
        if self.iris_core:
            self.iris_core.receive_finding(finding)
        else:
            logger.info(f"[{self.__class__.__name__}] {finding}")


class BaseCortex(IRISConnectable, ABC):
    """
    Abstract base for all IRIS reasoning modules.

    Provides structured reasoning, evaluation, explanation, and
    confidence assessment with thread-safe operations.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        iris_core: Optional[Any] = None,
    ) -> None:
        """
        Initialize BaseCortex.

        Args:
            db_path: Path to SQLite database for reasoning logs.
                     Defaults to env var IRIS_CORTEX_DB or "iris_cortex.db".
            iris_core: Reference to IRIS core.
        """
        super().__init__(iris_core=iris_core)
        self.db_path = db_path or os.getenv("IRIS_CORTEX_DB", "iris_cortex.db")
        self._conn: Optional[sqlite3.Connection] = None
        self._init_storage()
        self.status = "ready"
        logger.info(f"BaseCortex initialized: db={self.db_path}")

    def _init_storage(self) -> None:
        """Initialize SQLite storage for reasoning logs."""
        try:
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA foreign_keys=ON;")
            self._create_tables()
        except Exception as exc:
            logger.warning(f"Cortex storage init failed: {exc}")
            self._conn = None

    def _create_tables(self) -> None:
        """Create reasoning logs table."""
        with self._lock:
            if self._conn:
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reasoning_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        module TEXT NOT NULL,
                        action TEXT NOT NULL,
                        input_data TEXT,
                        output_data TEXT,
                        confidence REAL,
                        duration_ms INTEGER,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                self._conn.commit()

    def _result(
        self,
        success: bool,
        action: str,
        data: Any = None,
        confidence: float = 1.0,
        errors: Optional[List[str]] = None,
        duration_ms: int = 0,
    ) -> Dict[str, Any]:
        """Build a standard result dictionary."""
        return {
            "success": success,
            "module": self.__class__.__name__,
            "action": action,
            "data": data,
            "confidence": confidence,
            "errors": errors or [],
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _log_reasoning(
        self,
        action: str,
        input_data: Any,
        output_data: Any,
        confidence: float,
        duration_ms: int,
    ) -> None:
        """Log reasoning operation to database."""
        try:
            if self._conn:
                self._conn.execute(
                    """
                    INSERT INTO reasoning_logs (module, action, input_data, output_data, confidence, duration_ms)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.__class__.__name__,
                        action,
                        json.dumps(input_data, default=str),
                        json.dumps(output_data, default=str),
                        confidence,
                        duration_ms,
                    ),
                )
                self._conn.commit()
        except Exception as exc:
            logger.warning(f"Failed to log reasoning: {exc}")

    # ------------------------------------------------------------------
    # Core abstract interface
    # ------------------------------------------------------------------
    @abstractmethod
    def reason(self, input_data: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Core reasoning method. Must be implemented by subclasses."""
        ...

    def evaluate(self, options: List[Dict[str, Any]], criteria: List[str]) -> List[Dict[str, Any]]:
        """
        Score options against criteria.

        Args:
            options: List of option dicts, each with at least a "name" key.
            criteria: List of criterion names to evaluate against.

        Returns:
            List of scored options with scores per criterion.
        """
        start = time.perf_counter()
        try:
            scored = []
            for opt in options:
                scores = {}
                total = 0
                for crit in criteria:
                    # Default scoring: if option has the criterion as a key, use its value
                    # Otherwise score 0.5 (neutral)
                    val = opt.get(crit, opt.get("scores", {}).get(crit, 0.5))
                    if isinstance(val, bool):
                        val = 1.0 if val else 0.0
                    scores[crit] = round(float(val), 4)
                    total += float(val)
                avg = total / len(criteria) if criteria else 0.5
                scored.append({
                    "option": opt.get("name", "unknown"),
                    "scores": scores,
                    "average_score": round(avg, 4),
                    "raw": opt,
                })
            scored.sort(key=lambda x: x["average_score"], reverse=True)
            duration_ms = int((time.perf_counter() - start) * 1000)
            self._log_reasoning("evaluate", {"options": len(options), "criteria": criteria}, scored, 0.8, duration_ms)
            return scored
        except Exception as exc:
            logger.error(f"Evaluate failed: {exc}")
            return []

    def explain(self, decision: Dict[str, Any]) -> str:
        """
        Generate human-readable explanation of a decision.

        Args:
            decision: Decision dict from a reasoning module.

        Returns:
            Human-readable explanation string.
        """
        try:
            parts = []
            parts.append(f"Decision: {decision.get('action', 'unknown')}")
            parts.append(f"Module: {decision.get('module', 'unknown')}")
            parts.append(f"Confidence: {decision.get('confidence', 0.0):.2%}")
            data = decision.get("data", {})
            if isinstance(data, dict):
                for k, v in data.items():
                    parts.append(f"  {k}: {v}")
            if decision.get("errors"):
                parts.append(f"Errors: {', '.join(decision['errors'])}")
            return "\n".join(parts)
        except Exception as exc:
            return f"Explanation failed: {exc}"

    def confidence(self, assessment: Dict[str, Any]) -> float:
        """
        Calculate self-assessed confidence from assessment data.

        Args:
            assessment: Dict with factors affecting confidence.

        Returns:
            Confidence score 0.0-1.0.
        """
        try:
            base = 0.5
            factors = assessment.get("factors", [])
            for f in factors:
                weight = f.get("weight", 0.1)
                value = f.get("value", 0.5)
                base += weight * (value - 0.5)
            return max(0.0, min(1.0, base))
        except Exception as exc:
            logger.warning(f"Confidence calculation failed: {exc}")
            return 0.5

    def close(self) -> None:
        """Close SQLite connection cleanly."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
                logger.info("BaseCortex SQLite connection closed.")

    def __enter__(self) -> "BaseCortex":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# ------------------------------------------------------------------
# Usage example
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("BaseCortex is abstract. Inherit from it to build reasoning modules.")
