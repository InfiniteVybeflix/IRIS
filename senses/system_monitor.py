"""
IRIS v1.0 — System Monitor

Real-time CPU, RAM, disk, network, and temperature monitoring.
Alerts on threshold breaches.

Dependencies: psutil
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base_sense import BaseSense

logger = logging.getLogger(__name__)


class SystemMonitor(BaseSense):
    """Real-time system resource monitor."""

    name: str = "system_monitor"
    interval: int = 5
    thresholds: Dict[str, Any] = {"cpu_percent": 90.0, "ram_percent": 85.0, "disk_percent": 90.0, "temperature_c": 80.0}

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._psutil: Optional[Any] = None

    def _load_psutil(self) -> Any:
        if self._psutil is None:
            try:
                import psutil
                self._psutil = psutil
            except ImportError:
                raise RuntimeError("psutil not installed.")
        return self._psutil

    def _sense(self) -> Dict[str, Any]:
        psutil = self._load_psutil()
        metrics: Dict[str, Any] = {}
        metrics["cpu"] = {"percent": psutil.cpu_percent(interval=1), "per_cpu": psutil.cpu_percent(interval=1, percpu=True),
            "count": psutil.cpu_count(), "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None}
        ram = psutil.virtual_memory()
        metrics["ram"] = {"total": ram.total, "available": ram.available, "used": ram.used, "percent": ram.percent,
            "top_processes": self._get_top_processes(psutil, 5)}
        disk_partitions = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disk_partitions.append({"device": part.device, "mountpoint": part.mountpoint, "fstype": part.fstype,
                    "total": usage.total, "used": usage.used, "free": usage.free, "percent": usage.percent})
            except PermissionError:
                continue
        metrics["disk"] = {"partitions": disk_partitions}
        net_io = psutil.net_io_counters()
        metrics["network"] = {"bytes_sent": net_io.bytes_sent, "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent, "packets_recv": net_io.packets_recv,
            "connections": len(psutil.net_connections())}
        metrics["temperature"] = self._get_temperatures(psutil)
        return metrics

    def _get_top_processes(self, psutil: Any, n: int) -> List[Dict[str, Any]]:
        processes = []
        for proc in psutil.process_iter(["pid", "name", "memory_percent"]):
            try:
                processes.append(proc.info)
            except Exception:
                pass
        processes.sort(key=lambda x: x.get("memory_percent", 0) or 0, reverse=True)
        return processes[:n]

    def _get_temperatures(self, psutil: Any) -> Dict[str, Any]:
        temps: Dict[str, Any] = {}
        try:
            if hasattr(psutil, "sensors_temperatures"):
                sensors = psutil.sensors_temperatures()
                if sensors:
                    for name, entries in sensors.items():
                        temps[name] = [{"label": e.label, "current": e.current, "high": e.high, "critical": e.critical} for e in entries]
        except Exception:
            pass
        return temps

    def _should_alert(self, result: Dict[str, Any]) -> bool:
        if not result.get("success"):
            return True
        output = result.get("output", {})
        alerts: List[str] = []
        cpu = output.get("cpu", {}).get("percent", 0)
        if cpu > self.thresholds.get("cpu_percent", 90):
            alerts.append(f"CPU {cpu}% > {self.thresholds['cpu_percent']}%")
        ram = output.get("ram", {}).get("percent", 0)
        if ram > self.thresholds.get("ram_percent", 85):
            alerts.append(f"RAM {ram}% > {self.thresholds['ram_percent']}%")
        for part in output.get("disk", {}).get("partitions", []):
            if part.get("percent", 0) > self.thresholds.get("disk_percent", 90):
                alerts.append(f"Disk {part.get('mountpoint')} {part['percent']}% > {self.thresholds['disk_percent']}%")
        for sensor_name, entries in output.get("temperature", {}).items():
            for entry in entries:
                current = entry.get("current")
                if current and current > self.thresholds.get("temperature_c", 80):
                    alerts.append(f"Temp {sensor_name}/{entry.get('label')} {current}°C > {self.thresholds['temperature_c']}°C")
        if alerts:
            result["warnings"] = alerts
            return True
        return False

    def _emit_alert(self, result: Dict[str, Any]) -> None:
        self.report({"type": "system_alert", "sense": self.name, "severity": "warning",
            "message": "; ".join(result.get("warnings", [])), "data": result.get("output", {})})


__all__ = ["SystemMonitor"]
