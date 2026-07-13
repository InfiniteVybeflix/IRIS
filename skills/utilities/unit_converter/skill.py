"""Unit Converter Skill — Convert between units of measurement."""
import logging
from typing import Dict, Any
from skills import BaseSkill
logger = logging.getLogger(__name__)

class UnitConverterSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="unit_converter", category="utilities", capabilities=["unit_converter"])
        self._conversions = {
            "length": {"m": 1, "km": 1000, "cm": 0.01, "mm": 0.001, "ft": 0.3048, "in": 0.0254, "yd": 0.9144, "mi": 1609.34},
            "weight": {"kg": 1, "g": 0.001, "mg": 0.000001, "lb": 0.453592, "oz": 0.0283495, "t": 1000},
            "temperature": {"special": True},
            "volume": {"l": 1, "ml": 0.001, "gal": 3.78541, "qt": 0.946353, "pt": 0.473176, "cup": 0.236588, "fl_oz": 0.0295735},
            "speed": {"mps": 1, "kph": 0.277778, "mph": 0.44704, "knot": 0.514444},
            "data": {"b": 1/8, "B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4, "Pb": 1024**5},
            "time": {"s": 1, "min": 60, "h": 3600, "d": 86400, "wk": 604800, "mo": 2592000, "yr": 31536000},
            "area": {"sq_m": 1, "sq_km": 1e6, "sq_ft": 0.092903, "sq_mi": 2.59e6, "acre": 4046.86, "ha": 10000},
        }

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "convert")
        if method == "convert": return self.convert(params)
        elif method == "list_units": return self.list_units(params)
        return {"error": f"Unknown method: {method}"}

    def convert(self, params: Dict[str, Any]) -> Dict[str, Any]:
        category = params.get("category", "")
        value = params.get("value", 0)
        from_unit = params.get("from", "")
        to_unit = params.get("to", "")
        if category == "temperature":
            return self._convert_temperature(value, from_unit, to_unit)
        units = self._conversions.get(category, {})
        if from_unit not in units or to_unit not in units:
            return {"success": False, "error": f"Unknown units in {category}. Available: {list(units.keys())}"}
        base = value * units[from_unit]
        result = base / units[to_unit]
        return {"success": True, "value": value, "from": from_unit, "to": to_unit, "result": round(result, 6), "category": category}

    def _convert_temperature(self, value: float, from_unit: str, to_unit: str) -> Dict[str, Any]:
        if from_unit == to_unit: return {"success": True, "result": value}
        c = value if from_unit == "C" else (value - 32) * 5/9 if from_unit == "F" else value - 273.15
        result = c if to_unit == "C" else c * 9/5 + 32 if to_unit == "F" else c + 273.15
        return {"success": True, "value": value, "from": from_unit, "to": to_unit, "result": round(result, 2), "category": "temperature"}

    def list_units(self, params: Dict[str, Any]) -> Dict[str, Any]:
        category = params.get("category", "")
        if category:
            return {"success": True, "category": category, "units": list(self._conversions.get(category, {}).keys())}
        return {"success": True, "categories": list(self._conversions.keys())}
