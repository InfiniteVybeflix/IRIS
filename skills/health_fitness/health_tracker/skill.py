"""Health Tracker Skill — Track vitals, symptoms, and health metrics."""
import logging
from typing import Dict, Any, List
from datetime import datetime
from skills import BaseSkill
logger = logging.getLogger(__name__)

class HealthTrackerSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="health_tracker", category="health_fitness", capabilities=["health_tracker"])
        self._records: List[Dict[str, Any]] = []

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "log")
        if method == "log": return self.log(params)
        elif method == "history": return self.history(params)
        elif method == "trends": return self.trends(params)
        return {"error": f"Unknown method: {method}"}

    def log(self, params: Dict[str, Any]) -> Dict[str, Any]:
        record = {"timestamp": datetime.utcnow().isoformat(), "type": params.get("type", ""), "value": params.get("value", 0), "unit": params.get("unit", "")}
        self._records.append(record)
        return {"success": True, "record": record}

    def history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        rtype = params.get("record_type", "")
        records = [r for r in self._records if not rtype or r["type"] == rtype]
        return {"success": True, "records": records[-50:], "count": len(records)}

    def trends(self, params: Dict[str, Any]) -> Dict[str, Any]:
        rtype = params.get("record_type", "")
        values = [r["value"] for r in self._records if r["type"] == rtype]
        if not values: return {"success": False, "error": "No data"}
        avg = sum(values) / len(values)
        return {"success": True, "average": round(avg, 2), "min": min(values), "max": max(values), "count": len(values)}
