#!/usr/bin/env python3
"""
core/monitoring.py — IRIS v1.0 System Monitoring
Real-time metrics collection, alerting, and health dashboards.
"""

import threading
import time
import json
import logging
from typing import Dict, Any, List, Optional
from collections import deque, defaultdict
from datetime import datetime


class SystemMonitor:
    """
    Real-time monitoring dashboard for the Aevibron Agent Corps.

    Tracks:
    - Agent health over time
    - Task throughput and latency
    - Message bus traffic
    - Shared memory usage
    - Error rates and alerting
    """

    def __init__(self, commander, max_history: int = 1000):
        self.commander = commander
        self.max_history = max_history
        self._lock = threading.RLock()
        self._logger = logging.getLogger("IRIS.Monitor")
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Metrics buffers
        self.agent_health_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.task_latency: deque = deque(maxlen=max_history)
        self.task_throughput: deque = deque(maxlen=max_history)
        self.error_count: int = 0
        self.alert_log: deque = deque(maxlen=100)
        self._last_tick = time.time()
        self._tasks_completed_tick = 0

    def start(self) -> None:
        """Start the monitoring thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()
        self._logger.info("[Monitor] System monitoring started.")

    def stop(self) -> None:
        """Stop the monitoring thread."""
        with self._lock:
            self._running = False
        self._logger.info("[Monitor] System monitoring stopped.")

    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                self._collect_metrics()
                time.sleep(5)
            except Exception as e:
                self._logger.error(f"[Monitor] Metric collection error: {e}")

    def _collect_metrics(self) -> None:
        """Collect current system metrics."""
        now = time.time()

        # Agent health snapshots
        health = self.commander.registry.health_check_all()
        for name, h in health.items():
            self.agent_health_history[name].append({
                "timestamp": now,
                "status": h.get("status"),
                "load": h.get("load", 0),
            })

        # Task throughput (tasks per 5s window)
        total_completed = sum(
            1 for m in self.commander.get_all_missions()
            for r in m.get("results", [])
            if r.get("success")
        )
        delta = total_completed - self._tasks_completed_tick
        self.task_throughput.append({"timestamp": now, "rate": delta / 5.0})
        self._tasks_completed_tick = total_completed

        # Check for alerts
        for name, h in health.items():
            if h.get("status") == "error":
                self.alert_log.append({
                    "timestamp": now,
                    "level": "error",
                    "agent": name,
                    "message": f"Agent {name} in error state",
                })
                self.error_count += 1

    def get_dashboard(self) -> Dict[str, Any]:
        """Get current monitoring dashboard data."""
        with self._lock:
            health = self.commander.registry.health_check_all()
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "agents": {
                    "total": len(health),
                    "online": sum(1 for h in health.values() if h.get("status") in ("idle", "busy")),
                    "error": sum(1 for h in health.values() if h.get("status") == "error"),
                    "avg_load": round(sum(h.get("load", 0) for h in health.values()) / max(len(health), 1), 2),
                },
                "tasks": {
                    "total_missions": len(self.commander.get_all_missions()),
                    "throughput_5s": list(self.task_throughput)[-1]["rate"] if self.task_throughput else 0,
                    "avg_latency": round(sum(l["latency"] for l in self.task_latency) / max(len(self.task_latency), 1), 2) if self.task_latency else 0,
                },
                "errors": {
                    "total": self.error_count,
                    "recent_alerts": list(self.alert_log)[-10:],
                },
                "memory": self.commander.shared_memory.get_stats(),
                "bus": self.commander.message_bus.get_stats(),
            }

    def get_agent_history(self, agent_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get health history for a specific agent."""
        with self._lock:
            return list(self.agent_health_history.get(agent_name, deque()))[-limit:]

    def export_metrics(self, filepath: str) -> bool:
        """Export all metrics to JSON file."""
        try:
            data = {
                "dashboard": self.get_dashboard(),
                "agent_history": {k: list(v) for k, v in self.agent_health_history.items()},
                "throughput": list(self.task_throughput),
                "alerts": list(self.alert_log),
            }
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except Exception as e:
            self._logger.error(f"[Monitor] Export failed: {e}")
            return False


__all__ = ["SystemMonitor"]
