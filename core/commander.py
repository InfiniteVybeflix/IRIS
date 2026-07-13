"""
Aevibron Agent Corps — IRIS Supreme Commander
Task router, delegator, aggregator, and mission orchestrator.

Author: IRIS v1.0
"""

import json
import logging
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from base_agent import BaseAgent, AgentStatus, Task, TaskPriority, TaskResult
from communication import MessageBus
from registry import AgentRegistry
from shared_memory import SharedMemory
from task_queue import TaskQueue


@dataclass
class MissionPlan:
    """A structured plan for executing a user mission."""
    mission_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_request: str = ""
    tasks: List[Task] = field(default_factory=list)
    estimated_complexity: str = "medium"  # low, medium, high, critical
    required_agents: List[str] = field(default_factory=list)
    parallel_groups: List[List[str]] = field(default_factory=list)
    status: str = "planned"  # planned, active, completed, failed
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    results: List[TaskResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "user_request": self.user_request,
            "tasks": [t.to_dict() for t in self.tasks],
            "estimated_complexity": self.estimated_complexity,
            "required_agents": self.required_agents,
            "parallel_groups": self.parallel_groups,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "results": [r.to_dict() for r in self.results],
        }


@dataclass
class UnifiedReport:
    """Aggregated report from all agents for a mission."""
    mission_id: str = ""
    summary: str = ""
    findings: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    agent_contributions: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    success_rate: float = 0.0
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "summary": self.summary,
            "findings": self.findings,
            "recommendations": self.recommendations,
            "agent_contributions": self.agent_contributions,
            "execution_time": self.execution_time,
            "success_rate": self.success_rate,
            "timestamp": self.timestamp,
        }


class Commander:
    """
    Commander — IRIS Supreme. The brain of the Aevibron Agent Corps.

    IRIS receives missions from the user, analyzes requirements, decomposes
    complex tasks, assigns them to the right agents, coordinates parallel
    execution, aggregates results, and reports back.

    She learns from each mission — remembering which agents performed well,
    what strategies worked, and how to improve future missions.

    Attributes:
        name (str): "IRIS"
        registry (AgentRegistry): Agent registry reference.
        message_bus (MessageBus): Inter-agent communication bus.
        shared_memory (SharedMemory): Shared workspace.
        task_queue (TaskQueue): Priority task queue.
        _missions (dict): Active and completed missions.
        _findings (list): Recent findings from agents.
        _agent_performance (dict): Performance tracking per agent.
        _lock (threading.RLock): Thread-safe lock.
        _logger (logging.Logger): Logger instance.
        _executor (ThreadPoolExecutor): Thread pool for parallel execution.
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        message_bus: Optional[MessageBus] = None,
        shared_memory: Optional[SharedMemory] = None,
        task_queue: Optional[TaskQueue] = None,
        max_workers: int = 10,
    ):
        self.name = "IRIS"
        self.registry = registry or AgentRegistry()
        self.message_bus = message_bus or MessageBus()
        self.shared_memory = shared_memory or SharedMemory()
        self.task_queue = task_queue or TaskQueue()

        self._missions: Dict[str, MissionPlan] = {}
        self._findings: List[Dict[str, Any]] = []
        self._agent_performance: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._logger = logging.getLogger("Aevibron.Commander")
        self._logger.setLevel(logging.DEBUG)

        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

        self._executor = ThreadPoolExecutor(max_workers=max_workers)

        # Subscribe to all agent findings
        self.message_bus.subscribe("IRIS", self._handle_incoming_message)

        self._logger.info("[IRIS] Supreme Commander online. Aevibron Agent Corps ready for deployment.")

    def _handle_incoming_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming messages from agents."""
        msg_type = message.get("type", "unknown")

        if msg_type in ["finding", "error", "alert", "status"]:
            with self._lock:
                self._findings.append(message)
                if len(self._findings) > 1000:
                    self._findings = self._findings[-1000:]

        self._logger.debug(f"[IRIS] Received {msg_type} from {message.get('from', 'unknown')}")

    def receive_mission(self, user_request: str) -> MissionPlan:
        """
        Receive a mission from the user and create an execution plan.

        Args:
            user_request: The natural language request from the user.

        Returns:
            MissionPlan: The structured plan for execution.
        """
        self._logger.info(f"[IRIS] New mission received: {user_request[:100]}...")

        mission = MissionPlan(user_request=user_request)

        # Decompose the mission
        tasks = self.decompose(mission)
        mission.tasks = tasks

        # Estimate complexity
        mission.estimated_complexity = self._estimate_complexity(user_request, tasks)

        # Identify required agents
        mission.required_agents = list(set(t.agent_name for t in tasks if t.agent_name))

        # Determine parallel execution groups
        mission.parallel_groups = self._build_parallel_groups(tasks)

        with self._lock:
            self._missions[mission.mission_id] = mission

        # Store in shared memory
        self.shared_memory.store(
            f"mission_plan_{mission.mission_id}",
            mission.to_dict(),
            mission_id=mission.mission_id,
            agent_name="IRIS",
            tags=["mission", "plan"],
        )

        self._logger.info(f"[IRIS] Mission {mission.mission_id} planned: {len(tasks)} tasks, complexity={mission.estimated_complexity}")

        return mission

    def decompose(self, mission: MissionPlan) -> List[Task]:
        """
        Break a complex mission into sub-tasks.

        Uses keyword analysis and domain matching to determine
        which agents should handle each sub-task.

        Args:
            mission: The MissionPlan to decompose.

        Returns:
            List[Task]: Decomposed tasks.
        """
        request = mission.user_request.lower()
        tasks = []

        # Domain keyword mapping for task decomposition
        domain_keywords = {
            "software_engineering": {
                "agents": ["VAULT", "SCRIPT", "PROBE", "PIPE"],
                "keywords": [
                    "code", "program", "develop", "software", "app", "application",
                    "architecture", "design pattern", "microservice", "api", "database",
                    "schema", "refactor", "debug", "test", "ci/cd", "docker", "kubernetes",
                    "deploy", "build", "compile", "framework", "library", "module",
                    "function", "class", "interface", "rest", "graphql", "grpc",
                    "python", "javascript", "typescript", "java", "go", "rust", "c++",
                    "review", "lint", "format", "document", "readme",
                ],
            },
            "cyber_security": {
                "agents": ["SHADOW", "SCAR", "CRIMSON", "AEGIS", "SCALE", "TRACE", "OMEN"],
                "keywords": [
                    "scan", "vulnerability", "exploit", "penetration", "pentest",
                    "security", "hack", "reconnaissance", "osint", "footprint",
                    "firewall", "ids", "ips", "siem", "incident", "forensics",
                    "memory", "disk", "network", "pcap", "log", "threat",
                    "cve", "ioc", "malware", "phishing", "social engineering",
                    "red team", "blue team", "purple team", "defense", "monitor",
                    "certificate", "ssl", "tls", "port", "nmap", "subdomain",
                ],
            },
            "infrastructure": {
                "agents": ["NEBULA", "SHELL", "WEB", "CORE"],
                "keywords": [
                    "cloud", "aws", "azure", "gcp", "infrastructure", "server",
                    "container", "docker", "kubernetes", "k8s", "terraform",
                    "network", "bandwidth", "dns", "vpn", "ssl certificate",
                    "system", "process", "file", "backup", "automation",
                    "monitor", "optimize", "scale", "load balancer",
                ],
            },
            "intelligence": {
                "agents": ["CRUCIBLE", "SAGE", "QUILL"],
                "keywords": [
                    "scrape", "data", "research", "analyze", "extract",
                    "web", "crawl", "api", "clean", "normalize", "entity",
                    "literature", "paper", "patent", "comparison", "poc",
                    "document", "report", "write", "generate", "summarize",
                    "visualization", "dashboard", "chart", "graph",
                ],
            },
            "operations": {
                "agents": ["HERALD", "CANVAS", "ECHO", "GEAR"],
                "keywords": [
                    "email", "alert", "notify", "report", "visualization",
                    "chart", "dashboard", "graph", "voice", "speech", "audio",
                    "transcribe", "synthesize", "tts", "automation", "workflow",
                    "schedule", "trigger", "script", "cron",
                ],
            },
        }

        # Analyze request and create tasks
        matched_domains = []
        for domain, config in domain_keywords.items():
            score = sum(1 for kw in config["keywords"] if kw in request)
            if score > 0:
                matched_domains.append((score, domain, config))

        matched_domains.sort(key=lambda x: x[0], reverse=True)

        if not matched_domains:
            # Default to SCRIPT for general coding tasks
            matched_domains = [(1, "software_engineering", domain_keywords["software_engineering"])]

        # Create tasks based on matched domains
        task_id = 0
        for score, domain, config in matched_domains[:2]:  # Top 2 domains
            for agent_name in config["agents"]:
                agent = self.registry.get_by_name(agent_name)
                if not agent:
                    continue

                confidence = agent.can_handle(mission.user_request)
                if confidence > 0.1 or score >= 2:
                    task = Task(
                        mission_id=mission.mission_id,
                        agent_name=agent_name,
                        description=f"[{agent_name}] {mission.user_request[:100]}",
                        priority=TaskPriority.HIGH if score >= 3 else TaskPriority.MEDIUM,
                        payload={
                            "original_request": mission.user_request,
                            "domain": domain,
                            "confidence": confidence,
                            "matched_keywords": [kw for kw in config["keywords"] if kw in request][:10],
                        },
                    )
                    tasks.append(task)
                    task_id += 1

        # If no specific agents matched, create a general task for the top domain
        if not tasks and matched_domains:
            _, domain, config = matched_domains[0]
            for agent_name in config["agents"][:1]:
                task = Task(
                    mission_id=mission.mission_id,
                    agent_name=agent_name,
                    description=f"[{agent_name}] {mission.user_request[:100]}",
                    priority=TaskPriority.MEDIUM,
                    payload={"original_request": mission.user_request, "domain": domain},
                )
                tasks.append(task)

        # If still no tasks, assign to SCRIPT as fallback
        if not tasks:
            task = Task(
                mission_id=mission.mission_id,
                agent_name="SCRIPT",
                description=f"[SCRIPT] {mission.user_request[:100]}",
                priority=TaskPriority.MEDIUM,
                payload={"original_request": mission.user_request, "domain": "general"},
            )
            tasks.append(task)

        return tasks

    def _estimate_complexity(self, request: str, tasks: List[Task]) -> str:
        """Estimate mission complexity based on request and task count."""
        complexity_indicators = {
            "critical": ["emergency", "critical", "urgent", "breach", "attack", "compromise", "down", "failure"],
            "high": ["complex", "multiple", "integrate", "migrate", "refactor", "architecture", "system"],
            "low": ["simple", "quick", "basic", "hello", "test", "example"],
        }

        req_lower = request.lower()

        for level, keywords in complexity_indicators.items():
            if any(kw in req_lower for kw in keywords):
                return level

        if len(tasks) >= 4:
            return "high"
        elif len(tasks) >= 2:
            return "medium"

        return "low"

    def _build_parallel_groups(self, tasks: List[Task]) -> List[List[str]]:
        """Group tasks that can execute in parallel."""
        # Simple grouping: tasks with no dependencies and different agents can run in parallel
        groups = []
        current_group = []
        used_agents = set()

        for task in tasks:
            if not task.dependencies and task.agent_name not in used_agents:
                current_group.append(task.task_id)
                used_agents.add(task.agent_name)
            else:
                if current_group:
                    groups.append(current_group)
                current_group = [task.task_id]
                used_agents = {task.agent_name}

        if current_group:
            groups.append(current_group)

        return groups

    def assign(self, task: Task) -> Optional[TaskResult]:
        """
        Assign a task to the appropriate agent and execute it.

        Args:
            task: The Task to assign.

        Returns:
            TaskResult: The result of execution, or None if assignment failed.
        """
        agent_name = task.agent_name

        # Try to get the specified agent
        agent = self.registry.get_by_name(agent_name)

        if not agent:
            # Try to find best matching agent
            agent = self.registry.find_best_agent(task.description, domain=task.payload.get("domain"))
            if agent:
                task.agent_name = agent.name
                self._logger.info(f"[IRIS] Reassigned task {task.task_id} from {agent_name} to {agent.name}")
            else:
                self._logger.error(f"[IRIS] No agent available for task {task.task_id}")
                return TaskResult(
                    success=False,
                    agent_name="IRIS",
                    task_id=task.task_id,
                    mission_id=task.mission_id,
                    error=f"Agent {agent_name} not found and no suitable replacement available.",
                )

        # Check agent status
        if agent.status != AgentStatus.IDLE:
            # Queue the task for later
            self.task_queue.enqueue(task, priority=task.priority)
            self._logger.info(f"[IRIS] Agent {agent.name} busy. Task {task.task_id} queued.")
            return None

        # Execute the task
        self._logger.info(f"[IRIS] Assigning task {task.task_id} to {agent.name}")

        try:
            result = agent.execute(task)

            # Update performance tracking
            self._update_agent_performance(agent.name, result)

            # Store result in shared memory
            self.shared_memory.store(
                f"result_{task.task_id}",
                result.to_dict(),
                mission_id=task.mission_id,
                agent_name=agent.name,
                tags=["result", task.mission_id],
            )

            return result

        except Exception as e:
            self._logger.error(f"[IRIS] Task {task.task_id} execution failed: {e}", exc_info=True)
            return TaskResult(
                success=False,
                agent_name=agent.name,
                task_id=task.task_id,
                mission_id=task.mission_id,
                error=str(e),
            )

    def coordinate(self, mission: MissionPlan) -> List[TaskResult]:
        """
        Coordinate execution of all tasks in a mission.

        Handles parallel execution where possible and dependency ordering.

        Args:
            mission: The MissionPlan to execute.

        Returns:
            List[TaskResult]: Results from all task executions.
        """
        self._logger.info(f"[IRIS] Coordinating mission {mission.mission_id}")

        mission.status = "active"
        mission.started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        results = []
        completed_task_ids = set()

        # First pass: enqueue all tasks
        for task in mission.tasks:
            self.task_queue.enqueue(task)

        # Execute tasks respecting dependencies
        pending_tasks = list(mission.tasks)
        max_iterations = len(mission.tasks) * 3  # Prevent infinite loops
        iteration = 0

        while pending_tasks and iteration < max_iterations:
            iteration += 1
            ready_tasks = []
            still_pending = []

            for task in pending_tasks:
                # Check if all dependencies are completed
                deps_met = all(dep_id in completed_task_ids for dep_id in task.dependencies)
                if deps_met:
                    ready_tasks.append(task)
                else:
                    still_pending.append(task)

            if not ready_tasks:
                if still_pending:
                    # Check for circular dependencies or failed deps
                    self._logger.warning(f"[IRIS] No ready tasks but {len(still_pending)} pending. Possible dependency issue.")
                break

            # Execute ready tasks in parallel
            futures = {}
            for task in ready_tasks:
                future = self._executor.submit(self.assign, task)
                futures[future] = task

            for future in as_completed(futures):
                task = futures[future]
                try:
                    result = future.result(timeout=300)  # 5 minute timeout per task
                    if result:
                        results.append(result)
                        if result.success:
                            completed_task_ids.add(task.task_id)
                            self.task_queue.mark_completed(task.task_id, result)
                        else:
                            self.task_queue.mark_failed(task.task_id, result.error or "Unknown error")
                    else:
                        # Task was queued, will be handled later
                        still_pending.append(task)
                except Exception as e:
                    self._logger.error(f"[IRIS] Task {task.task_id} coordination error: {e}")
                    error_result = TaskResult(
                        success=False,
                        agent_name=task.agent_name,
                        task_id=task.task_id,
                        mission_id=mission.mission_id,
                        error=f"Coordination error: {str(e)}",
                    )
                    results.append(error_result)
                    self.task_queue.mark_failed(task.task_id, str(e))

            pending_tasks = still_pending

        mission.results = results
        mission.status = "completed" if all(r.success for r in results) else "failed"
        mission.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        self._logger.info(f"[IRIS] Mission {mission.mission_id} {mission.status}: {len(results)} results")

        return results

    def aggregate(self, mission: MissionPlan) -> UnifiedReport:
        """
        Aggregate results from all agents into a unified report.

        Args:
            mission: The completed MissionPlan.

        Returns:
            UnifiedReport: The aggregated findings and recommendations.
        """
        report = UnifiedReport(mission_id=mission.mission_id)

        # Collect all findings
        mission_findings = [
            f for f in self._findings
            if f.get("mission_id") == mission.mission_id
        ]

        report.findings = mission_findings

        # Build agent contributions
        for result in mission.results:
            report.agent_contributions[result.agent_name] = {
                "success": result.success,
                "output": result.output,
                "execution_time": result.execution_time,
                "error": result.error,
            }

        # Calculate success rate
        if mission.results:
            successful = sum(1 for r in mission.results if r.success)
            report.success_rate = successful / len(mission.results)

        # Generate summary
        report.summary = self._generate_summary(mission, report)

        # Extract recommendations
        report.recommendations = self._extract_recommendations(mission, mission_findings)

        # Calculate execution time
        if mission.started_at and mission.completed_at:
            try:
                start = time.mktime(time.strptime(mission.started_at, "%Y-%m-%dT%H:%M:%SZ"))
                end = time.mktime(time.strptime(mission.completed_at, "%Y-%m-%dT%H:%M:%SZ"))
                report.execution_time = end - start
            except:
                pass

        # Store report in shared memory
        self.shared_memory.store(
            f"report_{mission.mission_id}",
            report.to_dict(),
            mission_id=mission.mission_id,
            agent_name="IRIS",
            tags=["report", "final"],
        )

        self._logger.info(f"[IRIS] Report generated for mission {mission.mission_id}")

        return report

    def _generate_summary(self, mission: MissionPlan, report: UnifiedReport) -> str:
        """Generate a human-readable summary of the mission."""
        parts = []
        parts.append(f"## Mission Report: {mission.mission_id}")
        parts.append(f"**Request:** {mission.user_request}")
        parts.append(f"**Status:** {mission.status.upper()}")
        parts.append(f"**Success Rate:** {report.success_rate*100:.1f}%")
        parts.append(f"**Agents Deployed:** {', '.join(report.agent_contributions.keys()) or 'None'}")
        parts.append("")

        if report.findings:
            parts.append(f"**Findings:** {len(report.findings)} items")

        if report.recommendations:
            parts.append(f"**Recommendations:** {len(report.recommendations)} items")

        return "
".join(parts)

    def _extract_recommendations(self, mission: MissionPlan, findings: List[Dict[str, Any]]) -> List[str]:
        """Extract recommendations from findings and results."""
        recommendations = []

        for finding in findings:
            content = finding.get("content", {})
            if isinstance(content, dict):
                rec = content.get("recommendation") or content.get("recommendations")
                if rec:
                    if isinstance(rec, list):
                        recommendations.extend(rec)
                    else:
                        recommendations.append(rec)

        for result in mission.results:
            if result.success and isinstance(result.output, dict):
                rec = result.output.get("recommendations") or result.output.get("recommendation")
                if rec:
                    if isinstance(rec, list):
                        recommendations.extend(rec)
                    else:
                        recommendations.append(rec)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for r in recommendations:
            if r and r not in seen:
                seen.add(r)
                unique.append(r)

        return unique

    def report_to_user(self, report: UnifiedReport) -> str:
        """
        Generate a human-readable summary for the user.

        Args:
            report: The UnifiedReport to summarize.

        Returns:
            str: Human-readable report.
        """
        lines = []
        lines.append("=" * 60)
        lines.append("  AEVIBRON AGENT CORPS — MISSION REPORT")
        lines.append("=" * 60)
        lines.append("")
        lines.append(report.summary)
        lines.append("")

        if report.agent_contributions:
            lines.append("--- AGENT CONTRIBUTIONS ---")
            for agent_name, contrib in report.agent_contributions.items():
                status = "✅" if contrib["success"] else "❌"
                lines.append(f"{status} {agent_name}: {contrib.get('output', 'No output')}")
                if contrib.get("error"):
                    lines.append(f"   Error: {contrib['error']}")
            lines.append("")

        if report.findings:
            lines.append("--- KEY FINDINGS ---")
            for i, finding in enumerate(report.findings[:10], 1):
                f_type = finding.get("type", "unknown")
                priority = finding.get("priority", "normal")
                content = finding.get("content", {})
                lines.append(f"{i}. [{priority.upper()}] {f_type}: {str(content)[:150]}")
            lines.append("")

        if report.recommendations:
            lines.append("--- RECOMMENDATIONS ---")
            for i, rec in enumerate(report.recommendations[:10], 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        lines.append(f"Execution Time: {report.execution_time:.2f}s")
        lines.append("=" * 60)

        return "
".join(lines)

    def get_agent_status(self) -> Dict[str, Any]:
        """
        Get status of all agents.

        Returns:
            Dict: Agent status summary.
        """
        return self.registry.get_stats()

    def handle_failure(self, task: Task, agent: BaseAgent) -> Optional[Task]:
        """
        Handle a task failure by reassigning or escalating.

        Args:
            task: The failed task.
            agent: The agent that failed.

        Returns:
            Task: A reassigned task, or None if no reassignment possible.
        """
        self._logger.warning(f"[IRIS] Handling failure of task {task.task_id} by {agent.name}")

        # Try to find another agent in the same domain
        domain_agents = self.registry.get_by_domain(agent.domain)
        for alt_agent in domain_agents:
            if alt_agent.name != agent.name and alt_agent.status == AgentStatus.IDLE:
                task.agent_name = alt_agent.name
                task.retry_count += 1
                self._logger.info(f"[IRIS] Reassigning task {task.task_id} to {alt_agent.name}")
                return task

        # If no alternative, report to user
        self._logger.error(f"[IRIS] No alternative agent available for task {task.task_id}")
        return None

    def receive_finding(self, finding: Dict[str, Any]) -> None:
        """Receive a finding from an agent."""
        with self._lock:
            self._findings.append(finding)
            if len(self._findings) > 1000:
                self._findings = self._findings[-1000:]

        self._logger.info(f"[IRIS] Finding received from {finding.get('from', 'unknown')}: {finding.get('type', 'unknown')}")

    def _update_agent_performance(self, agent_name: str, result: TaskResult) -> None:
        """Track agent performance metrics."""
        with self._lock:
            if agent_name not in self._agent_performance:
                self._agent_performance[agent_name] = {
                    "total_tasks": 0,
                    "successful_tasks": 0,
                    "failed_tasks": 0,
                    "total_execution_time": 0.0,
                    "average_execution_time": 0.0,
                }

            perf = self._agent_performance[agent_name]
            perf["total_tasks"] += 1

            if result.success:
                perf["successful_tasks"] += 1
            else:
                perf["failed_tasks"] += 1

            perf["total_execution_time"] += result.execution_time
            perf["average_execution_time"] = perf["total_execution_time"] / perf["total_tasks"]

    def get_performance_report(self) -> Dict[str, Any]:
        """Get performance report for all agents."""
        with self._lock:
            return dict(self._agent_performance)

    def get_mission_status(self, mission_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific mission."""
        with self._lock:
            mission = self._missions.get(mission_id)
            if mission:
                return mission.to_dict()
            return None

    def get_all_missions(self) -> List[Dict[str, Any]]:
        """Get all missions."""
        with self._lock:
            return [m.to_dict() for m in self._missions.values()]

    def learn(self, mission: MissionPlan) -> None:
        """
        Learn from a completed mission to improve future performance.

        Args:
            mission: The completed MissionPlan.
        """
        # Store mission learnings in shared memory
        learning = {
            "mission_id": mission.mission_id,
            "user_request": mission.user_request,
            "complexity": mission.estimated_complexity,
            "status": mission.status,
            "successful_agents": [r.agent_name for r in mission.results if r.success],
            "failed_agents": [r.agent_name for r in mission.results if not r.success],
            "execution_time": mission.completed_at,
        }

        self.shared_memory.store(
            f"learning_{mission.mission_id}",
            learning,
            mission_id=mission.mission_id,
            agent_name="IRIS",
            tags=["learning", "experience"],
        )

        self._logger.info(f"[IRIS] Learned from mission {mission.mission_id}")

    def execute_mission(self, user_request: str) -> str:
        """
        Full pipeline: receive -> decompose -> coordinate -> aggregate -> report.

        Args:
            user_request: The user's natural language request.

        Returns:
            str: Human-readable mission report.
        """
        start_time = time.time()

        # 1. Receive and plan
        mission = self.receive_mission(user_request)

        # 2. Coordinate execution
        self.coordinate(mission)

        # 3. Aggregate results
        report = self.aggregate(mission)

        # 4. Learn
        self.learn(mission)

        # 5. Report to user
        user_report = self.report_to_user(report)

        total_time = time.time() - start_time
        self._logger.info(f"[IRIS] Mission complete in {total_time:.2f}s")

        return user_report

    def shutdown(self) -> None:
        """Shutdown the Commander and all subsystems."""
        self._logger.info("[IRIS] Commander shutting down...")
        self._executor.shutdown(wait=True)
        self.registry.shutdown()
        self.message_bus.persist()
        self.shared_memory.persist()
        self.task_queue.persist()
        self._logger.info("[IRIS] Commander offline. Aevibron Agent Corps standing down.")


__all__ = ["Commander", "MissionPlan", "UnifiedReport"]


# Usage Example:
# commander = Commander()
# report = commander.execute_mission("Scan my network for vulnerabilities and generate a security report")
# print(report)
