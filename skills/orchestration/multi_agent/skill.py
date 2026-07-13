"""Multi-Agent Skill — Swarm coordination and task delegation."""

import uuid
import logging
from typing import Dict, Any, List
from datetime import datetime
from skills import BaseSkill

logger = logging.getLogger(__name__)


class MultiAgentSkill(BaseSkill):
    """Multi-agent swarm coordination and task delegation."""

    SPECIALTIES = ["frontend", "backend", "testing", "security", "devops", "documentation", "analysis", "research", "creative"]

    def __init__(self):
        super().__init__(
            name="multi_agent",
            category="orchestration",
            capabilities=["multi_agent"]
        )
        self._agents: Dict[str, Dict] = {}
        self._tasks: Dict[str, Dict] = {}
        self._results: Dict[str, List] = {}
        self._init_default_agents()

    def _init_default_agents(self):
        for specialty in self.SPECIALTIES:
            agent_id = f"iris_{specialty}_{uuid.uuid4().hex[:6]}"
            self._agents[agent_id] = {"specialty": specialty, "status": "idle", "current_task": None, "completed_tasks": 0, "created_at": datetime.utcnow().isoformat()}

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "delegate")
        if method == "delegate":
            return self.delegate(params)
        elif method == "coordinate":
            return self.coordinate(params)
        elif method == "aggregate":
            return self.aggregate(params)
        elif method == "assign":
            return self.assign(params)
        elif method == "list_agents":
            return self.list_agents(params)
        return {"error": f"Unknown method: {method}"}

    def delegate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        task = params.get("task", {})
        specialty = params.get("specialty", "")
        # Find best agent
        best_agent = None
        if specialty:
            for aid, agent in self._agents.items():
                if agent["specialty"] == specialty and agent["status"] == "idle":
                    best_agent = aid
                    break
        if not best_agent:
            for aid, agent in self._agents.items():
                if agent["status"] == "idle":
                    best_agent = aid
                    break
        if not best_agent:
            best_agent = self._create_agent(specialty or "general")
        self._agents[best_agent]["status"] = "working"
        self._agents[best_agent]["current_task"] = task
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        self._tasks[task_id] = {"agent": best_agent, "task": task, "status": "delegated", "timestamp": datetime.utcnow().isoformat()}
        return {"success": True, "task_id": task_id, "agent": best_agent, "specialty": self._agents[best_agent]["specialty"], "status": "delegated"}

    def coordinate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        agent_ids = params.get("agent_ids", list(self._agents.keys()))
        sync_mode = params.get("sync_mode", "broadcast")
        coordinated = []
        for aid in agent_ids:
            if aid in self._agents:
                coordinated.append({"agent": aid, "status": self._agents[aid]["status"], "synced": True})
        return {"success": True, "agents_coordinated": len(coordinated), "sync_mode": sync_mode, "agents": coordinated}

    def aggregate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        task_ids = params.get("task_ids", list(self._tasks.keys()))
        results = []
        for tid in task_ids:
            if tid in self._tasks:
                results.append({"task_id": tid, **self._tasks[tid]})
        # Simple consensus: majority vote if results are categorical
        consensus = "none"
        if results and all("result" in r for r in results):
            values = [str(r["result"]) for r in results]
            from collections import Counter
            most_common = Counter(values).most_common(1)
            if most_common:
                consensus = most_common[0][0]
        return {"success": True, "aggregated_count": len(results), "results": results, "consensus": consensus}

    def assign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        specialty = params.get("specialty", "general")
        task = params.get("task", {})
        agent_id = self._create_agent(specialty)
        self._agents[agent_id]["status"] = "assigned"
        self._tasks[f"task_{uuid.uuid4().hex[:8]}"] = {"agent": agent_id, "task": task, "status": "assigned", "specialty": specialty}
        return {"success": True, "agent_id": agent_id, "specialty": specialty, "agents_total": len(self._agents)}

    def list_agents(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        idle = sum(1 for a in self._agents.values() if a["status"] == "idle")
        working = sum(1 for a in self._agents.values() if a["status"] == "working")
        return {"success": True, "total": len(self._agents), "idle": idle, "working": working, "agents": dict(self._agents)}

    def _create_agent(self, specialty: str) -> str:
        agent_id = f"iris_{specialty}_{uuid.uuid4().hex[:6]}"
        self._agents[agent_id] = {"specialty": specialty, "status": "idle", "current_task": None, "completed_tasks": 0, "created_at": datetime.utcnow().isoformat()}
        return agent_id
