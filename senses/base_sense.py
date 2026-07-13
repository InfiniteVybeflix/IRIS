"""
IRIS v1.0 — Base Sense & IRISConnectable Interface

Defines the contract every sense must fulfill. All senses inherit from BaseSense.
Uniform monitoring patterns, alert thresholds, anomaly detection, reporting.
"""

from __future__ import annotations

import abc
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class IRISConnectable(abc.ABC):
    """Abstract interface for any component connecting to the IRIS core."""

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        self.iris_core: Optional[Any] = iris_core
        self.status: str = "idle"
        self.last_result: Optional[Dict[str, Any]] = None
        self._lock: threading.Lock = threading.Lock()
        self._start_time: Optional[float] = None

    @abc.abstractmethod
    def health_check(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abc.abstractmethod
    def check(self) -> Dict[str, Any]:
        raise NotImplementedError

    def report(self, finding: Dict[str, Any]) -> None:
        finding["reported_by"] = self.__class__.__name__
        finding["reported_at"] = datetime.now(timezone.utc).isoformat()
        if self.iris_core is not None and hasattr(self.iris_core, "receive_finding"):
            try:
                self.iris_core.receive_finding(finding)
            except Exception as exc:
                logger.error(f"Failed to report: {exc}")
                logger.info(f"[{self.__class__.__name__}] {finding}")
        else:
            logger.info(f"[{self.__class__.__name__}] {finding}")

    def _build_result(self, success: bool, action: str, output: Any = None,
                      parsed: Optional[Dict[str, Any]] = None,
                      errors: Optional[List[str]] = None,
                      warnings: Optional[List[str]] = None) -> Dict[str, Any]:
        duration_ms = int((time.perf_counter() - self._start_time) * 1000) if self._start_time else 0
        return {
            "success": success, "sense": self.__class__.__name__, "action": action,
            "output": output, "parsed": parsed or {}, "errors": errors or [],
            "warnings": warnings or [], "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _begin_check(self) -> None:
        self._start_time = time.perf_counter()
        with self._lock:
            self.status = "active"

    def _end_check(self, success: bool) -> None:
        with self._lock:
            self.status = "idle" if success else "error"


class BaseSense(IRISConnectable, abc.ABC):
    """Abstract base class for all IRIS senses."""

    name: str = "base_sense"
    interval: int = 60
    thresholds: Dict[str, Any] = {}

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._baseline: Dict[str, Any] = {}
        self._history: List[Dict[str, Any]] = []
        self._max_history: int = 1000

    def start(self) -> None:
        if self._running:
            logger.warning(f"{self.name} already running.")
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info(f"{self.name} started (interval={self.interval}s).")

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self.interval + 5)
        logger.info(f"{self.name} stopped.")

    def _monitor_loop(self) -> None:
        while self._running:
            try:
                result = self.check()
                self._store_history(result)
                if self._should_alert(result):
                    self._emit_alert(result)
            except Exception as exc:
                logger.exception(f"{self.name} loop error: {exc}")
            for _ in range(self.interval):
                if not self._running:
                    break
                time.sleep(1)

    def _store_history(self, result: Dict[str, Any]) -> None:
        with self._lock:
            self._history.append(result)
            if len(self._history) > self._max_history:
                self._history.pop(0)

    def _should_alert(self, result: Dict[str, Any]) -> bool:
        return bool(result.get("errors"))

    def _emit_alert(self, result: Dict[str, Any]) -> None:
        self.report({"type": "sense_alert", "sense": self.name, "severity": "warning",
            "message": f"{self.name} detected anomaly.", "data": result})

    def check(self) -> Dict[str, Any]:
        self._begin_check()
        try:
            output = self._sense()
            result = self._build_result(success=True, action="check", output=output)
            self.last_result = result
            self._end_check(True)
            return result
        except Exception as exc:
            logger.exception(f"{self.name} check failed")
            result = self._build_result(success=False, action="check", errors=[str(exc)])
            self.last_result = result
            self._end_check(False)
            return result

    @abc.abstractmethod
    def _sense(self) -> Any:
        raise NotImplementedError

    def is_anomaly(self, current: Any, baseline: Any) -> bool:
        if isinstance(current, (int, float)) and isinstance(baseline, (int, float)):
            if baseline == 0:
                return current != 0
            return abs(current - baseline) / abs(baseline) > 0.2
        return current != baseline

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            return self._history[-limit:]

    def set_baseline(self, baseline: Dict[str, Any]) -> None:
        with self._lock:
            self._baseline = baseline

    def health_check(self) -> Dict[str, Any]:
        return {"status": "available", "message": f"{self.name} operational.",
            "details": {"interval": self.interval, "running": self._running, "history_size": len(self._history)}}


__all__ = ["IRISConnectable", "BaseSense"]
