"""Medication Reminders Skill — Track medications, doses, schedules."""
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from skills import BaseSkill
logger = logging.getLogger(__name__)

class MedicationRemindersSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="medication_reminders", category="health_fitness", capabilities=["medication_reminders"])
        self._medications: Dict[str, Dict[str, Any]] = {}
        self._doses: List[Dict[str, Any]] = []

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "add")
        if method == "add": return self.add_medication(params)
        elif method == "log_dose": return self.log_dose(params)
        elif method == "schedule": return self.get_schedule(params)
        elif method == "list": return self.list_medications(params)
        return {"error": f"Unknown method: {method}"}

    def add_medication(self, params: Dict[str, Any]) -> Dict[str, Any]:
        mid = params.get("name", "").lower().replace(" ", "_")
        self._medications[mid] = {"name": params.get("name", ""), "dosage": params.get("dosage", ""), "frequency": params.get("frequency", ""), "times": params.get("times", []), "notes": params.get("notes", "")}
        return {"success": True, "medication": self._medications[mid]}

    def log_dose(self, params: Dict[str, Any]) -> Dict[str, Any]:
        mid = params.get("medication_id", "")
        dose = {"medication": mid, "timestamp": datetime.utcnow().isoformat(), "taken": params.get("taken", True)}
        self._doses.append(dose)
        return {"success": True, "dose": dose}

    def get_schedule(self, params: Dict[str, Any]) -> Dict[str, Any]:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        schedule = []
        for mid, med in self._medications.items():
            for t in med.get("times", []):
                schedule.append({"medication": med["name"], "time": t, "dosage": med["dosage"]})
        return {"success": True, "date": today, "schedule": sorted(schedule, key=lambda x: x["time"])}

    def list_medications(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"success": True, "medications": list(self._medications.values()), "count": len(self._medications)}
