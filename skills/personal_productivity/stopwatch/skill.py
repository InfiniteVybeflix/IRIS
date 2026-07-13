"""Stopwatch Skill — Lap timing and split tracking."""
import logging
from typing import Dict, Any, List
from datetime import datetime
from skills import BaseSkill
logger = logging.getLogger(__name__)

class StopwatchSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="stopwatch", category="personal_productivity", capabilities=["stopwatch"])
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "start")
        if method == "start": return self.start(params)
        elif method == "lap": return self.lap(params)
        elif method == "stop": return self.stop(params)
        elif method == "status": return self.status(params)
        return {"error": f"Unknown method: {method}"}

    def start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        sid = params.get("session_id", "default")
        self._sessions[sid] = {"id": sid, "start_time": datetime.utcnow().isoformat(), "laps": [], "running": True}
        return {"success": True, "session": self._sessions[sid]}

    def lap(self, params: Dict[str, Any]) -> Dict[str, Any]:
        sid = params.get("session_id", "default")
        s = self._sessions.get(sid)
        if not s or not s["running"]: return {"success": False, "error": "Stopwatch not running"}
        now = datetime.utcnow()
        start = datetime.fromisoformat(s["start_time"])
        elapsed = int((now - start).total_seconds() * 1000)
        s["laps"].append({"lap_number": len(s["laps"])+1, "elapsed_ms": elapsed, "timestamp": now.isoformat()})
        return {"success": True, "lap": s["laps"][-1], "total_laps": len(s["laps"])}

    def stop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        sid = params.get("session_id", "default")
        s = self._sessions.get(sid)
        if not s: return {"success": False, "error": "Session not found"}
        s["running"] = False
        s["end_time"] = datetime.utcnow().isoformat()
        start = datetime.fromisoformat(s["start_time"])
        end = datetime.fromisoformat(s["end_time"])
        s["total_elapsed_ms"] = int((end - start).total_seconds() * 1000)
        return {"success": True, "session": s}

    def status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        sid = params.get("session_id", "default")
        s = self._sessions.get(sid)
        if not s: return {"success": False, "error": "Session not found"}
        if s["running"]:
            elapsed = int((datetime.utcnow() - datetime.fromisoformat(s["start_time"])).total_seconds() * 1000)
        else:
            elapsed = s.get("total_elapsed_ms", 0)
        return {"success": True, "running": s["running"], "elapsed_ms": elapsed, "laps": len(s["laps"])}
