"""
IRIS v7.0 — Tool Registry

Auto-discovers, registers, health-checks, and executes all tools.
Central dispatcher for the IRIS operational layer.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import os
import pkgutil
import threading
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for all IRIS tools. Thread-safe."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self._lock: threading.RLock = threading.RLock()
        self._discovered: bool = False

    def register(self, tool: BaseTool) -> None:
        with self._lock:
            if tool.name in self._tools:
                raise ValueError(f"Tool '{tool.name}' already registered.")
            self._tools[tool.name] = tool
            logger.info(f"Registered: {tool.name} ({tool.category})")

    def discover(self, package_path: Optional[str] = None) -> List[BaseTool]:
        discovered: List[BaseTool] = []
        if package_path is None:
            package_path = os.path.dirname(os.path.abspath(__file__))
        for _, module_name, _ in pkgutil.iter_modules([package_path]):
            if module_name in ("base_tool", "registry"):
                continue
            try:
                full_module = f"{__package__}.{module_name}"
                module = importlib.import_module(full_module)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (inspect.isclass(attr) and issubclass(attr, BaseTool)
                            and attr is not BaseTool and not inspect.isabstract(attr)):
                        try:
                            instance = attr()
                            self.register(instance)
                            discovered.append(instance)
                        except Exception as exc:
                            logger.error(f"Failed to instantiate {attr_name}: {exc}")
            except Exception as exc:
                logger.error(f"Failed to import {module_name}: {exc}")
        self._discovered = True
        logger.info(f"Discovery complete. {len(discovered)} tools registered.")
        return discovered

    def get(self, name: str) -> Optional[BaseTool]:
        with self._lock:
            return self._tools.get(name)

    def get_by_category(self, category: str) -> List[BaseTool]:
        with self._lock:
            return [t for t in self._tools.values() if t.category == category]

    def list_tools(self) -> List[str]:
        with self._lock:
            return sorted(self._tools.keys())

    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}
        with self._lock:
            for name, tool in self._tools.items():
                try:
                    results[name] = tool.health_check()
                except Exception as exc:
                    logger.error(f"Health check failed for {name}: {exc}")
                    results[name] = {"status": "error", "message": str(exc), "details": {}}
        return results

    def execute(self, name: str, **kwargs: Any) -> Dict[str, Any]:
        tool = self.get(name)
        if tool is None:
            return {
                "success": False, "tool": name, "action": "execute", "output": None,
                "parsed": {}, "errors": [f"Tool '{name}' not registered."],
                "warnings": [], "duration_ms": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        return tool.execute(**kwargs)

    def unregister(self, name: str) -> None:
        with self._lock:
            if name in self._tools:
                del self._tools[name]
                logger.info(f"Unregistered: {name}")

    def clear(self) -> None:
        with self._lock:
            self._tools.clear()
            self._discovered = False
            logger.info("Registry cleared.")


__all__ = ["ToolRegistry"]
