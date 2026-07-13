"""
IRIS v1.0 — Sense Registry

Auto-discovers, registers, starts, stops, and monitors all senses.
Central nervous system for the IRIS perceptual layer.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import os
import pkgutil
import threading
from typing import Any, Dict, List, Optional

from .base_sense import BaseSense

logger = logging.getLogger(__name__)


class SenseRegistry:
    """Central registry for all IRIS senses. Thread-safe."""

    def __init__(self) -> None:
        self._senses: Dict[str, BaseSense] = {}
        self._lock: threading.RLock = threading.RLock()
        self._discovered: bool = False
        self._alerts: List[Dict[str, Any]] = []

    def register(self, sense: BaseSense) -> None:
        with self._lock:
            if sense.name in self._senses:
                raise ValueError(f"Sense '{sense.name}' already registered.")
            self._senses[sense.name] = sense
            logger.info(f"Registered: {sense.name}")

    def discover(self, package_path: Optional[str] = None) -> List[BaseSense]:
        discovered: List[BaseSense] = []
        if package_path is None:
            package_path = os.path.dirname(os.path.abspath(__file__))
        for _, module_name, _ in pkgutil.iter_modules([package_path]):
            if module_name in ("base_sense", "registry"):
                continue
            try:
                full_module = f"{__package__}.{module_name}"
                module = importlib.import_module(full_module)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (inspect.isclass(attr) and issubclass(attr, BaseSense)
                            and attr is not BaseSense and not inspect.isabstract(attr)):
                        try:
                            instance = attr()
                            self.register(instance)
                            discovered.append(instance)
                        except Exception as exc:
                            logger.error(f"Failed to instantiate {attr_name}: {exc}")
            except Exception as exc:
                logger.error(f"Failed to import {module_name}: {exc}")
        self._discovered = True
        logger.info(f"Discovery complete. {len(discovered)} senses registered.")
        return discovered

    def start_all(self) -> None:
        with self._lock:
            for name, sense in self._senses.items():
                try:
                    sense.start()
                except Exception as exc:
                    logger.error(f"Failed to start {name}: {exc}")

    def stop_all(self) -> None:
        with self._lock:
            for name, sense in self._senses.items():
                try:
                    sense.stop()
                except Exception as exc:
                    logger.error(f"Failed to stop {name}: {exc}")

    def get(self, name: str) -> Optional[BaseSense]:
        with self._lock:
            return self._senses.get(name)

    def list_senses(self) -> List[str]:
        with self._lock:
            return sorted(self._senses.keys())

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}
        with self._lock:
            for name, sense in self._senses.items():
                try:
                    results[name] = {"status": sense.status, "health": sense.health_check(),
                        "last_result": sense.last_result, "interval": sense.interval, "running": sense._running}
                except Exception as exc:
                    results[name] = {"status": "error", "message": str(exc)}
        return results

    def get_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            return self._alerts[-limit:]

    def add_alert(self, alert: Dict[str, Any]) -> None:
        with self._lock:
            self._alerts.append(alert)
            if len(self._alerts) > 10000:
                self._alerts = self._alerts[-5000:]

    def clear_alerts(self) -> None:
        with self._lock:
            self._alerts.clear()

    def unregister(self, name: str) -> None:
        with self._lock:
            if name in self._senses:
                self._senses[name].stop()
                del self._senses[name]
                logger.info(f"Unregistered: {name}")

    def clear(self) -> None:
        with self._lock:
            for sense in self._senses.values():
                sense.stop()
            self._senses.clear()
            self._discovered = False


__all__ = ["SenseRegistry"]
