"""System Automation Skill — File ops, scheduled tasks, workflow automation."""

import os
import json
import logging
import threading
import subprocess
import time
from typing import Dict, Any
from datetime import datetime, timedelta
from skills import BaseSkill

logger = logging.getLogger(__name__)


class SystemAutomationSkill(BaseSkill):
    """File operations, scheduled tasks, and workflow automation."""

    def __init__(self):
        super().__init__(name="system_automation", category="productivity", capabilities=["system_automation"])
        self._schedules: Dict[str, Any] = {}
        self._watches: Dict[str, Any] = {}
        self._workflows: Dict[str, Any] = {}
        self._timers: Dict[str, threading.Timer] = {}

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "schedule_task")
        if method == "schedule_task":
            return self.schedule_task(params)
        elif method == "watch_file":
            return self.watch_file(params)
        elif method == "automate_workflow":
            return self.automate_workflow(params)
        elif method == "cancel_task":
            return self.cancel_task(params)
        elif method == "list_tasks":
            return self.list_tasks(params)
        return {"error": f"Unknown method: {method}"}

    def schedule_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        job_id = params.get("job_id", f"job_{int(time.time())}")
        capability_name = params.get("capability", "")
        task_params = params.get("params", {})
        interval = params.get("interval_seconds", 3600)
        max_runs = params.get("max_runs", None)
        if job_id in self._timers:
            return {"success": False, "error": f"Job '{job_id}' already exists. Cancel first."}
        runs = [0]
        def wrapper():
            if max_runs and runs[0] >= max_runs:
                return
            runs[0] += 1
            try:
                from skills import skill_router
                skill_router.execute(capability_name, task_params)
            except Exception as e:
                logger.error(f"Scheduled job '{job_id}' error: {e}")
            if (not max_runs or runs[0] < max_runs) and job_id in self._schedules:
                t = threading.Timer(interval, wrapper)
                t.daemon = True
                t.start()
                self._timers[job_id] = t
        timer = threading.Timer(interval, wrapper)
        timer.daemon = True
        timer.start()
        self._timers[job_id] = timer
        self._schedules[job_id] = {"capability": capability_name, "params": task_params, "interval": interval, "max_runs": max_runs, "created_at": datetime.utcnow().isoformat(), "runs": 0}
        return {"success": True, "job_id": job_id, "scheduled": True, "interval_seconds": interval, "max_runs": max_runs}

    def watch_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params.get("path", "")
        callback_capability = params.get("callback_capability", "")
        if not path or not os.path.exists(path):
            return {"success": False, "error": f"Path not found: {path}"}
        initial_mtime = os.path.getmtime(path)
        initial_size = os.path.getsize(path)
        self._watches[path] = {"path": path, "callback": callback_capability, "initial_mtime": initial_mtime, "initial_size": initial_size, "watching": True, "since": datetime.utcnow().isoformat()}
        def check():
            watch = self._watches.get(path)
            if not watch or not watch.get("watching"):
                return
            try:
                current_mtime = os.path.getmtime(path)
                if current_mtime != watch["initial_mtime"]:
                    watch["initial_mtime"] = current_mtime
                    if callback_capability:
                        from skills import skill_router
                        skill_router.execute(callback_capability, {"path": path, "event": "modified"})
            except OSError:
                pass
            threading.Timer(5, check).start()
        threading.Timer(5, check).start()
        return {"success": True, "path": path, "watching": True, "initial_size": initial_size}

    def automate_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        steps = params.get("steps", [])
        workflow_id = params.get("workflow_id", f"wf_{int(time.time())}")
        results = []
        for step in steps:
            cap = step.get("capability", "")
            step_params = step.get("params", {})
            try:
                from skills import skill_router
                result = skill_router.execute(cap, step_params)
                results.append({"capability": cap, "success": result.get("success", False), "result": result})
            except Exception as e:
                results.append({"capability": cap, "success": False, "error": str(e)})
        self._workflows[workflow_id] = {"steps": steps, "results": results, "created_at": datetime.utcnow().isoformat()}
        return {"success": True, "workflow_id": workflow_id, "steps_executed": len(results), "results": results}

    def cancel_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        job_id = params.get("job_id", "")
        timer = self._timers.pop(job_id, None)
        schedule = self._schedules.pop(job_id, None)
        if timer:
            timer.cancel()
            return {"success": True, "job_id": job_id, "cancelled": True}
        return {"success": False, "error": f"Job '{job_id}' not found"}

    def list_tasks(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        return {"success": True, "scheduled_jobs": len(self._schedules), "watches": len(self._watches), "workflows": len(self._workflows), "jobs": list(self._schedules.keys()), "watches_list": list(self._watches.keys())}
