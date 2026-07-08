"""
IRIS v7.0 — Tools Package (Self-Contained)

The operational actuator layer. Every tool executes REAL commands against REAL systems.
No simulations. No placeholders. No stubs. No TODOs.

Import:
    from iris_v7.tools import ToolRegistry
    registry = ToolRegistry()
    registry.discover()
    result = registry.execute("nmap_wrapper", target="192.168.1.1")
"""

from .registry import ToolRegistry
from .base_tool import BaseTool, IRISConnectable

__version__ = "7.0.0"
__all__ = ["ToolRegistry", "BaseTool", "IRISConnectable"]
