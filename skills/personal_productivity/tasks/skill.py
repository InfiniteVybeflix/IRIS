"""Tasks Skill — To-do lists, task management, prioritization."""
import logging
from typing import Dict, Any, List
from datetime import datetime
from skills import BaseSkill
logger = logging.getLogger(__name__)

class TasksSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="tasks", category="personal_productivity", capabilities=["tasks"])
        self._tasks: List[Dict[str, Any]] = []
        self._task_id = 0

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "create")
        if method == "create": return self.create_task(params)
        elif method == "list": return self.list_tasks(params)
        elif method == "complete": return self.complete_task(params)
        elif method == "delete": return self.delete_task(params)
        elif method == "prioritize": return self.prioritize(params)
        return {"error": f"Unknown method: {method}"}

    def create_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self._task_id += 1
        t = {"id": self._task_id, "title": params.get("title", ""), "description": params.get("description", ""), "priority": params.get("priority", "medium"), "due": params.get("due", ""), "tags": params.get("tags", []), "completed": False, "created_at": datetime.utcnow().isoformat()}
        self._tasks.append(t)
        return {"success": True, "task": t}

    def list_tasks(self, params: Dict[str, Any]) -> Dict[str, Any]:
        status = params.get("status", "")
        tasks = [t for t in self._tasks if not status or (status == "completed" and t["completed"]) or (status == "pending" and not t["completed"])]
        return {"success": True, "tasks": tasks, "count": len(tasks)}

    def complete_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tid = params.get("task_id", 0)
        for t in self._tasks:
            if t["id"] == tid:
                t["completed"] = True
                t["completed_at"] = datetime.utcnow().isoformat()
                return {"success": True, "task": t}
        return {"success": False, "error": "Task not found"}

    def delete_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tid = params.get("task_id", 0)
        self._tasks = [t for t in self._tasks if t["id"] != tid]
        return {"success": True, "deleted": True}

    def prioritize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self._tasks.sort(key=lambda x: {"urgent": 0, "high": 1, "medium": 2, "low": 3}.get(x["priority"], 2))
        return {"success": True, "tasks": self._tasks}
