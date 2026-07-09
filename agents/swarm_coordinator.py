"""IRIS v9 Hybrid Swarm Coordinator - Multiple Agents Working Together"""
import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from config import config
from core.db import db

class SwarmAgent:
    """Individual agent in the swarm"""

    def __init__(self, agent_id: str, specialty: str, status: str = "idle"):
        self.agent_id = agent_id
        self.specialty = specialty  # 'frontend', 'backend', 'testing', 'security', 'devops'
        self.status = status
        self.current_task = None
        self.completed_tasks = []
        self.created_at = datetime.now().isoformat()

    def assign_task(self, task: Dict) -> bool:
        """Assign a task to this agent"""
        if self.status != "idle":
            return False
        self.status = "working"
        self.current_task = task
        return True

    def complete_task(self, result: Dict):
        """Mark task as complete"""
        self.status = "idle"
        self.completed_tasks.append({
            "task": self.current_task,
            "result": result,
            "completed_at": datetime.now().isoformat()
        })
        self.current_task = None

    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "specialty": self.specialty,
            "status": self.status,
            "current_task": self.current_task,
            "completed_count": len(self.completed_tasks),
            "created_at": self.created_at
        }

class SwarmCoordinator:
    """
    Coordinate multiple IRIS agents:
    - Frontend agent: React/Vue/Next.js
    - Backend agent: FastAPI/Node/Go
    - Testing agent: Unit tests, integration tests
    - Security agent: Audit, vulnerability scanning
    - DevOps agent: Docker, CI/CD, deployment
    """

    def __init__(self):
        self.agents: Dict[str, SwarmAgent] = {}
        self.task_queue: List[Dict] = []
        self._init_default_agents()

    def _init_default_agents(self):
        """Initialize default swarm agents"""
        specialties = ['frontend', 'backend', 'testing', 'security', 'devops', 'documentation']
        for specialty in specialties:
            agent_id = f"iris_{specialty}_{uuid.uuid4().hex[:6]}"
            self.agents[agent_id] = SwarmAgent(agent_id, specialty)

    def create_agent(self, specialty: str) -> str:
        """Create a new specialized agent"""
        agent_id = f"iris_{specialty}_{uuid.uuid4().hex[:6]}"
        self.agents[agent_id] = SwarmAgent(agent_id, specialty)
        return agent_id

    def assign_project(self, project_description: str) -> Dict:
        """Break down project and assign to swarm"""
        # Break into subtasks
        subtasks = self._break_down_project(project_description)

        assignments = []
        for task in subtasks:
            agent_id = self._find_best_agent(task["specialty"])
            if agent_id:
                self.agents[agent_id].assign_task(task)
                assignments.append({
                    "task": task,
                    "agent": agent_id,
                    "status": "assigned"
                })
            else:
                # Queue for later
                self.task_queue.append(task)
                assignments.append({
                    "task": task,
                    "agent": None,
                    "status": "queued"
                })

        return {
            "success": True,
            "project": project_description,
            "assignments": assignments,
            "queued": len(self.task_queue)
        }

    def _break_down_project(self, description: str) -> List[Dict]:
        """Break project into subtasks"""
        # In production, use AI to break down
        # For now, use keyword matching
        tasks = []
        desc_lower = description.lower()

        if any(k in desc_lower for k in ['frontend', 'ui', 'page', 'component', 'react', 'next']):
            tasks.append({"specialty": "frontend", "description": f"Build frontend: {description}", "priority": 1})

        if any(k in desc_lower for k in ['backend', 'api', 'server', 'database', 'endpoint']):
            tasks.append({"specialty": "backend", "description": f"Build backend: {description}", "priority": 1})

        if any(k in desc_lower for k in ['test', 'testing', 'spec', 'jest', 'pytest']):
            tasks.append({"specialty": "testing", "description": f"Write tests for: {description}", "priority": 2})
        else:
            # Always add testing
            tasks.append({"specialty": "testing", "description": f"Write tests for: {description}", "priority": 3})

        if any(k in desc_lower for k in ['security', 'auth', 'login', 'password']):
            tasks.append({"specialty": "security", "description": f"Security audit for: {description}", "priority": 2})

        if any(k in desc_lower for k in ['deploy', 'docker', 'ci/cd', 'vercel', 'aws']):
            tasks.append({"specialty": "devops", "description": f"Setup deployment for: {description}", "priority": 3})
        else:
            tasks.append({"specialty": "devops", "description": f"Setup deployment for: {description}", "priority": 4})

        tasks.append({"specialty": "documentation", "description": f"Document: {description}", "priority": 5})

        return tasks

    def _find_best_agent(self, specialty: str) -> Optional[str]:
        """Find best available agent for specialty"""
        # First, exact match
        for agent_id, agent in self.agents.items():
            if agent.specialty == specialty and agent.status == "idle":
                return agent_id

        # Fallback: any idle agent
        for agent_id, agent in self.agents.items():
            if agent.status == "idle":
                return agent_id

        return None

    def get_status(self) -> Dict:
        """Get swarm status"""
        return {
            "total_agents": len(self.agents),
            "idle": sum(1 for a in self.agents.values() if a.status == "idle"),
            "working": sum(1 for a in self.agents.values() if a.status == "working"),
            "queued_tasks": len(self.task_queue),
            "agents": [a.to_dict() for a in self.agents.values()]
        }

    def get_agent_results(self, agent_id: str) -> List[Dict]:
        """Get results from a specific agent"""
        agent = self.agents.get(agent_id)
        if agent:
            return agent.completed_tasks
        return []

swarm_coordinator = SwarmCoordinator()
