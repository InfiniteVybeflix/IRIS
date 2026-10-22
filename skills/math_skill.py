"""IRIS Math Skill Adapter — bridges legacy API routes.

The api/routes/math.py blueprint expects a `math_skill` singleton with
methods like `solve`, `simplify`, `differentiate`, `integrate`, `evaluate`,
`statistics`, `convert_units`.  This adapter implements that interface
using `sympy` (declared in requirements.txt) and falls back gracefully
when the optional dependency is missing.
"""
from __future__ import annotations

import logging
import math as _math
import statistics as _stats
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import sympy as sp  # type: ignore
    _x = sp.symbols("x")
    _SYMPY_AVAILABLE = True
except Exception:  # pragma: no cover
    sp = None  # type: ignore
    _SYMPY_AVAILABLE = False


class _MathSkillAdapter:
    """Adapter exposing the route-facing math API."""

    def solve(self, expression: str, variable: str = "x") -> Dict[str, Any]:
        if not _SYMPY_AVAILABLE:
            return {"success": False, "error": "sympy not installed", "expression": expression}
        try:
            var = sp.symbols(variable)
            expr = sp.sympify(expression)
            solutions = sp.solve(expr, var)
            return {"success": True, "expression": expression, "variable": variable,
                    "solutions": [str(s) for s in solutions]}
        except Exception as exc:
            return {"success": False, "error": str(exc), "expression": expression}

    def simplify(self, expression: str) -> Dict[str, Any]:
        if not _SYMPY_AVAILABLE:
            return {"success": False, "error": "sympy not installed", "expression": expression}
        try:
            simplified = sp.simplify(sp.sympify(expression))
            return {"success": True, "expression": expression, "simplified": str(simplified)}
        except Exception as exc:
            return {"success": False, "error": str(exc), "expression": expression}

    def differentiate(self, expression: str, variable: str = "x",
                      order: int = 1) -> Dict[str, Any]:
        if not _SYMPY_AVAILABLE:
            return {"success": False, "error": "sympy not installed", "expression": expression}
        try:
            var = sp.symbols(variable)
            derivative = sp.diff(sp.sympify(expression), var, int(order))
            return {"success": True, "expression": expression, "variable": variable,
                    "order": order, "derivative": str(derivative)}
        except Exception as exc:
            return {"success": False, "error": str(exc), "expression": expression}

    def integrate(self, expression: str, variable: str = "x",
                  limits: Optional[List[float]] = None) -> Dict[str, Any]:
        if not _SYMPY_AVAILABLE:
            return {"success": False, "error": "sympy not installed", "expression": expression}
        try:
            var = sp.symbols(variable)
            expr = sp.sympify(expression)
            if limits and len(limits) == 2:
                result = sp.integrate(expr, (var, limits[0], limits[1]))
            else:
                result = sp.integrate(expr, var)
            return {"success": True, "expression": expression, "variable": variable,
                    "limits": limits, "integral": str(result)}
        except Exception as exc:
            return {"success": False, "error": str(exc), "expression": expression}

    def evaluate(self, expression: str) -> Dict[str, Any]:
        safe_dict = {
            "__builtins__": {},
            "abs": abs, "round": round, "max": max, "min": min,
            "sum": sum, "pow": pow, "len": len,
            "sin": _math.sin, "cos": _math.cos, "tan": _math.tan,
            "sqrt": _math.sqrt, "log": _math.log, "log10": _math.log10,
            "exp": _math.exp, "pi": _math.pi, "e": _math.e,
            "floor": _math.floor, "ceil": _math.ceil,
        }
        try:
            result = eval(expression, safe_dict, {})  # noqa: S307 - sandboxed eval
            return {"success": True, "expression": expression, "result": result}
        except Exception as exc:
            return {"success": False, "error": str(exc), "expression": expression}

    def statistics(self, values: List[float], operation: str = "all") -> Dict[str, Any]:
        try:
            if not values:
                return {"success": False, "error": "No values provided"}
            if operation == "all":
                return {
                    "success": True,
                    "count": len(values),
                    "mean": _stats.mean(values),
                    "median": _stats.median(values),
                    "stdev": _stats.stdev(values) if len(values) > 1 else 0,
                    "min": min(values),
                    "max": max(values),
                }
            ops = {
                "mean": _stats.mean, "median": _stats.median,
                "variance": _stats.variance, "stdev": _stats.stdev,
            }
            if operation not in ops:
                return {"success": False, "error": f"Unknown operation: {operation}"}
            return {"success": True, "operation": operation, "result": ops[operation](values)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def convert_units(self, value: float, from_unit: str, to_unit: str) -> Dict[str, Any]:
        if not _SYMPY_AVAILABLE:
            return {"success": False, "error": "sympy not installed"}
        try:
            quantity = float(value) * sp.Unit(from_unit)
            result = float(sp.convert_to(quantity, to_unit).subs(sp.Unit(from_unit), 1))
            return {"success": True, "value": value, "from": from_unit,
                    "to": to_unit, "result": result}
        except Exception as exc:
            return {"success": False, "error": str(exc),
                    "value": value, "from": from_unit, "to": to_unit}


math_skill = _MathSkillAdapter()

__all__ = ["math_skill", "_MathSkillAdapter"]
