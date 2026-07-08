"""
IRIS v7.0 — Tools Connector

Single import point for wiring tools into your main project.
Drop this file + the tools/ folder into your project and import from here.

Usage:
    from tools.tools_connector import get_tool_registry, get_tool

    registry = get_tool_registry()
    registry.discover()

    nmap = get_tool("nmap_wrapper")
    result = nmap.scan_ports("192.168.1.1")
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .registry import ToolRegistry
from .base_tool import BaseTool


# Singleton registry instance
_TOOL_REGISTRY: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get or create the singleton ToolRegistry."""
    global _TOOL_REGISTRY
    if _TOOL_REGISTRY is None:
        _TOOL_REGISTRY = ToolRegistry()
    return _TOOL_REGISTRY


def get_tool(name: str) -> Optional[BaseTool]:
    """Get a tool by name from the singleton registry."""
    return get_tool_registry().get(name)


def discover_tools() -> List[str]:
    """Auto-discover and register all tools. Returns list of registered names."""
    registry = get_tool_registry()
    registry.discover()
    return registry.list_tools()


def execute_tool(name: str, **kwargs: Any) -> Dict[str, Any]:
    """Execute a tool by name with kwargs."""
    return get_tool_registry().execute(name, **kwargs)


def health_check_tools() -> Dict[str, Dict[str, Any]]:
    """Run health checks on all registered tools."""
    return get_tool_registry().health_check_all()


__all__ = [
    "get_tool_registry", "get_tool", "discover_tools",
    "execute_tool", "health_check_tools",
]
