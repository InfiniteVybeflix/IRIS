"""Calculator Skill — Basic and scientific calculations, expression evaluation."""
import logging
import math
from typing import Dict, Any
from skills import BaseSkill
logger = logging.getLogger(__name__)

class CalculatorSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="calculator", category="utilities", capabilities=["calculator"])

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "evaluate")
        if method == "evaluate": return self.evaluate(params)
        elif method == "scientific": return self.scientific(params)
        return {"error": f"Unknown method: {method}"}

    def evaluate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        expr = params.get("expression", "")
        try:
            safe_dict = {"__builtins__": {}, "abs": abs, "round": round, "max": max, "min": min, "sum": sum, "pow": pow}
            result = eval(expr, safe_dict)
            return {"success": True, "expression": expr, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e), "expression": expr}

    def scientific(self, params: Dict[str, Any]) -> Dict[str, Any]:
        op = params.get("operation", "")
        val = params.get("value", 0)
        ops = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "sqrt": math.sqrt, "log": math.log10, "ln": math.log, "factorial": math.factorial, "abs": abs}
        if op in ops:
            try:
                result = ops[op](val)
                return {"success": True, "operation": op, "value": val, "result": result}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": f"Unknown operation: {op}"}
