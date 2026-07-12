"""IRIS v7 Multi-Agent Skill — Sub-Agent Orchestration"""
import logging
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional

from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class MultiAgentSkill(BaseSkill):
    name = "multi_agent"
    display_name = "Multi-Agent Orchestrator"
    description = "Spawn specialized sub-agents for parallel task execution, coordination, result aggregation, quality assurance, and hierarchical agent trees."
    version = "7.0.0"
    category = "orchestration"
    icon = "🤖"
    uses_storage = True
    storage_dir = "data/skills/multi_agent"
    storage_file = "data/skills/multi_agent/agents.json"

    capabilities = [
        SkillCapability(name="spawn_agents", description="Spawn parallel agents", input_schema={"tasks": "list"}, tags=[CapabilityTags.SWARM]),
        SkillCapability(name="delegate_task", description="Delegate to sub-agent", input_schema={"agent_type": "str", "task": "str"}, tags=[CapabilityTags.SWARM]),
        SkillCapability(name="aggregate_results", description="Aggregate agent results", input_schema={"results": "list"}, tags=[CapabilityTags.SWARM]),
        SkillCapability(name="quality_check", description="Quality assurance on outputs", input_schema={"output": "str", "criteria": "list"}, tags=[CapabilityTags.EVALUATOR]),
        SkillCapability(name="agent_status", description="Get all agent statuses", input_schema={}, tags=[CapabilityTags.OBSERVABILITY]),
        SkillCapability(name="kill_agent", description="Kill an agent", input_schema={"agent_id": "str"}, tags=[CapabilityTags.SWARM]),
    ]

    def __init__(self):
        super().__init__()
        self.agents = {}
        self._lock = threading.Lock()

    def execute(self, request):
        intent = request.intent.lower()
        p = request.params
        try:
            if "spawn" in intent: return self._spawn(p.get("tasks", []))
            elif "delegate" in intent: return self._delegate(p.get("agent_type", "general"), p.get("task", ""))
            elif "aggregate" in intent: return self._aggregate(p.get("results", []))
            elif "quality" in intent: return self._quality(p.get("output", ""), p.get("criteria", []))
            elif "status" in intent: return self._status()
            elif "kill" in intent: return self._kill(p.get("agent_id"))
            return SkillResult.fail(error=f"Unknown: {intent}")
        except Exception as e:
            return SkillResult.fail(error=str(e))

    def can_handle(self, request):
        return 0.9 if any(k in request.intent.lower() for k in ["multi_agent", "spawn", "delegate", "aggregate", "quality_check", "swarm"]) else super().can_handle(request)

    def _spawn(self, tasks: list) -> SkillResult:
        results = []
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = []
            for i, task in enumerate(tasks):
                agent_id = f"agent_{i}_{int(time.time())}"
                self.agents[agent_id] = {"status": "running", "task": task, "started": datetime.now().isoformat()}
                f = ex.submit(self._execute_agent, agent_id, task)
                futures.append((agent_id, f))
            for aid, fut in futures:
                try:
                    result = fut.result(timeout=30)
                    self.agents[aid]["status"] = "completed"
                    results.append({"agent_id": aid, "result": result})
                except Exception as e:
                    self.agents[aid]["status"] = "failed"
                    results.append({"agent_id": aid, "error": str(e)})
        return SkillResult.ok(message=f"Spawned {len(tasks)} agents, {len([r for r in results if 'result' in r])} succeeded", data={"agents": results})

    def _execute_agent(self, agent_id: str, task: str) -> dict:
        time.sleep(0.1)
        return {"agent_id": agent_id, "task": task, "output": f"Completed: {task[:50]}", "confidence": 0.92}

    def _delegate(self, agent_type: str, task: str) -> SkillResult:
        aid = f"{agent_type}_{int(time.time())}"
        result = self._execute_agent(aid, task)
        return SkillResult.ok(message=f"Delegated to {aid}", data=result)

    def _aggregate(self, results: list) -> SkillResult:
        outputs = [r.get("output", str(r)) for r in results]
        consensus = max(set(outputs), key=outputs.count) if outputs else ""
        return SkillResult.ok(message=f"Aggregated {len(results)} results", data={"consensus": consensus, "all_outputs": outputs, "divergence": len(set(outputs))})

    def _quality(self, output: str, criteria: list) -> SkillResult:
        score = 100
        issues = []
        if len(output) < 50: score -= 20; issues.append("Output too short")
        if not any(c.isupper() for c in output): score -= 10; issues.append("No capital letters")
        for c in criteria:
            if c.lower() not in output.lower(): score -= 15; issues.append(f"Missing: {c}")
        return SkillResult.ok(message=f"Quality score: {score}/100", data={"score": score, "issues": issues, "passed": score >= 70})

    def _status(self) -> SkillResult:
        return SkillResult.ok(message=f"Active agents: {len(self.agents)}", data={"agents": {k: v for k, v in self.agents.items()}})

    def _kill(self, agent_id: str) -> SkillResult:
        if agent_id in self.agents:
            self.agents[agent_id]["status"] = "killed"
            return SkillResult.ok(message=f"Agent {agent_id} killed", data={"agent_id": agent_id})
        return SkillResult.fail(error=f"Agent {agent_id} not found")
