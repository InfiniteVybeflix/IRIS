#!/usr/bin/env python3
"""
core/commander_extensions.py — IRIS v1.0 Commander Extensions
Extended mission decomposition with agent-specific routing,
cross-agent dependency chains, and intelligent task scheduling.
"""

import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .base_agent import BaseAgent, Task, TaskPriority, TaskResult
from .commander import Commander, MissionPlan, UnifiedReport


@dataclass
class AgentTaskChain:
    """A chain of tasks that must execute sequentially across multiple agents."""
    chain_id: str
    tasks: List[Task] = field(default_factory=list)
    description: str = ""


class ExtendedCommander(Commander):
    """
    Extended Commander with advanced routing and cross-agent orchestration.

    Adds:
    - Agent-specific task routing with confidence scoring
    - Cross-agent dependency chains (e.g., SHADOW -> SCAR -> QUILL)
    - Intelligent retry with agent fallback
    - Mission templates for common workflows
    """

    # Predefined mission templates
    MISSION_TEMPLATES = {
        "security_assessment": {
            "description": "Full security assessment workflow",
            "chain": [
                {"agent": "SHADOW", "action": "recon", "description": "Reconnaissance phase"},
                {"agent": "SCAR", "action": "scan", "description": "Vulnerability scanning", "depends_on": 0},
                {"agent": "OMEN", "action": "check_cve", "description": "Threat intelligence correlation", "depends_on": 1},
                {"agent": "QUILL", "action": "generate_report", "description": "Generate security report", "depends_on": [0, 1, 2]},
            ],
        },
        "code_review_pipeline": {
            "description": "Automated code review and deployment pipeline",
            "chain": [
                {"agent": "SCRIPT", "action": "review_code", "description": "Code review"},
                {"agent": "PROBE", "action": "generate_tests", "description": "Test generation", "depends_on": 0},
                {"agent": "PIPE", "action": "generate_dockerfile", "description": "Containerization", "depends_on": [0, 1]},
                {"agent": "SHELL", "action": "review_dockerfile", "description": "Container security review", "depends_on": 2},
            ],
        },
        "threat_hunt": {
            "description": "Active threat hunting and incident response",
            "chain": [
                {"agent": "AEGIS", "action": "monitor", "description": "Real-time monitoring"},
                {"agent": "TRACE", "action": "analyze_memory", "description": "Memory forensics", "depends_on": 0},
                {"agent": "SCALE", "action": "gap_analysis", "description": "Detection gap analysis", "depends_on": [0, 1]},
            ],
        },
        "data_pipeline": {
            "description": "ETL pipeline with monitoring and alerting",
            "chain": [
                {"agent": "CRUCIBLE", "action": "scrape", "description": "Data ingestion"},
                {"agent": "CRUCIBLE", "action": "clean_data", "description": "Data cleaning", "depends_on": 0},
                {"agent": "TENSOR", "action": "preprocess", "description": "ML preprocessing", "depends_on": 1},
                {"agent": "CANVAS", "action": "create_dashboard", "description": "Visualization dashboard", "depends_on": 2},
                {"agent": "HERALD", "action": "send_email", "description": "Alert notification", "depends_on": 3},
            ],
        },
        "infrastructure_audit": {
            "description": "Full infrastructure security and compliance audit",
            "chain": [
                {"agent": "NEBULA", "action": "audit_aws", "description": "Cloud security audit"},
                {"agent": "SHELL", "action": "scan_image", "description": "Container image scan"},
                {"agent": "WEB", "action": "check_ssl", "description": "SSL/TLS audit"},
                {"agent": "PORTAL", "action": "generate_openapi", "description": "API documentation", "depends_on": [0, 1, 2]},
                {"agent": "QUILL", "action": "generate_report", "description": "Compliance report", "depends_on": 3},
            ],
        },
        "mobile_security_review": {
            "description": "Mobile application security assessment",
            "chain": [
                {"agent": "GUARD", "action": "analyze_apk", "description": "APK static analysis"},
                {"agent": "GUARD", "action": "frida_inject", "description": "Dynamic analysis", "depends_on": 0},
                {"agent": "SCAR", "action": "scan", "description": "Web API vulnerability scan", "depends_on": 1},
                {"agent": "QUILL", "action": "generate_report", "description": "Security report", "depends_on": [0, 1, 2]},
            ],
        },
        "blockchain_audit": {
            "description": "Smart contract and blockchain security audit",
            "chain": [
                {"agent": "CHAIN", "action": "audit_solidity", "description": "Smart contract audit"},
                {"agent": "CHAIN", "action": "check_wallet", "description": "Wallet security check", "depends_on": 0},
                {"agent": "QBIT", "action": "inventory_crypto", "description": "Cryptographic inventory", "depends_on": 1},
                {"agent": "QUILL", "action": "generate_report", "description": "Audit report", "depends_on": [0, 1, 2]},
            ],
        },
        "quantum_readiness": {
            "description": "Post-quantum cryptography migration assessment",
            "chain": [
                {"agent": "QBIT", "action": "inventory_crypto", "description": "Crypto inventory"},
                {"agent": "QBIT", "action": "recommend_pqc", "description": "PQC recommendations", "depends_on": 0},
                {"agent": "QBIT", "action": "migration_roadmap", "description": "Migration roadmap", "depends_on": 1},
                {"agent": "QUILL", "action": "generate_report", "description": "Quantum readiness report", "depends_on": [0, 1, 2]},
            ],
        },
    }

    def execute_template(self, template_name: str, params: Dict[str, Any]) -> UnifiedReport:
        """
        Execute a predefined mission template with parameters.

        Args:
            template_name: Key from MISSION_TEMPLATES
            params: Template parameters (e.g., {"target": "example.com"})

        Returns:
            UnifiedReport: Aggregated results
        """
        template = self.MISSION_TEMPLATES.get(template_name)
        if not template:
            raise ValueError(f"Unknown template: {template_name}. Available: {list(self.MISSION_TEMPLATES.keys())}")

        # Build task chain from template
        tasks = []
        task_map = {}  # index -> task_id

        for i, step in enumerate(template["chain"]):
            task = Task(
                mission_id="",  # Will be set by receive_mission
                agent_name=step["agent"],
                description=step["description"],
                priority=TaskPriority.HIGH,
                payload={
                    "action": step["action"],
                    **params,
                    "template_step": i,
                },
            )

            # Set dependencies
            deps = step.get("depends_on")
            if deps is not None:
                if isinstance(deps, int):
                    task.dependencies = [task_map[deps]]
                elif isinstance(deps, list):
                    task.dependencies = [task_map[d] for d in deps]

            task_map[i] = task.task_id
            tasks.append(task)

        # Create mission
        mission = MissionPlan(
            user_request=f"[{template_name}] {template['description']} with params: {params}",
            tasks=tasks,
            estimated_complexity="high",
            required_agents=list(set(t.agent_name for t in tasks)),
        )

        for t in tasks:
            t.mission_id = mission.mission_id

        with self._lock:
            self._missions[mission.mission_id] = mission

        # Execute
        self.coordinate(mission)
        return self.aggregate(mission)

    def route_to_agent(self, task: Task, preferred_agents: List[str] = None) -> Optional[TaskResult]:
        """
        Route a task to the best available agent with fallback.

        Args:
            task: The task to route
            preferred_agents: Ordered list of preferred agent codenames

        Returns:
            TaskResult or None
        """
        if preferred_agents:
            for agent_name in preferred_agents:
                agent = self.registry.get_by_name(agent_name)
                if agent and agent.status.value == "idle":
                    task.agent_name = agent_name
                    return self.assign(task)

        # Fallback to best match
        return self.assign(task)

    def create_cross_agent_chain(self, chain: AgentTaskChain) -> MissionPlan:
        """
        Create a mission from a cross-agent task chain.

        Args:
            chain: AgentTaskChain with sequential tasks

        Returns:
            MissionPlan: Ready-to-execute mission
        """
        mission = MissionPlan(
            user_request=f"Cross-agent chain: {chain.description}",
            tasks=chain.tasks,
            estimated_complexity="high",
        )

        for i, task in enumerate(chain.tasks):
            task.mission_id = mission.mission_id
            if i > 0:
                task.dependencies = [chain.tasks[i-1].task_id]

        with self._lock:
            self._missions[mission.mission_id] = mission

        return mission

    def get_template_list(self) -> List[Dict[str, str]]:
        """List all available mission templates."""
        return [
            {"name": name, "description": t["description"], "agents": ", ".join(set(s["agent"] for s in t["chain"]))}
            for name, t in self.MISSION_TEMPLATES.items()
        ]


# Monkey-patch Commander with extended methods for backward compatibility
def patch_commander():
    """Apply extensions to the base Commander class."""
    Commander.execute_template = ExtendedCommander.execute_template
    Commander.route_to_agent = ExtendedCommander.route_to_agent
    Commander.create_cross_agent_chain = ExtendedCommander.create_cross_agent_chain
    Commander.get_template_list = ExtendedCommander.get_template_list
    Commander.MISSION_TEMPLATES = ExtendedCommander.MISSION_TEMPLATES


__all__ = ["ExtendedCommander", "AgentTaskChain", "patch_commander"]
