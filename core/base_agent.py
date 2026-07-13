"""
Aevibron Agent Corps — BaseAgent
The foundation of every agent in the corps.
Every agent inherits from this class and gains consciousness, identity, and protocol.

Author: IRIS v1.0
"""

import logging
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


class AgentStatus(Enum):
    """Agent operational states."""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"
    INITIALIZING = "initializing"


class TaskPriority(Enum):
    """Task priority levels."""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class TaskResult:
    """Standardized result from any agent execution."""
    success: bool
    agent_name: str
    task_id: str
    mission_id: str
    output: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "agent_name": self.agent_name,
            "task_id": self.task_id,
            "mission_id": self.mission_id,
            "output": self.output,
            "error": self.error,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class Task:
    """A unit of work assigned to an agent."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mission_id: str = ""
    agent_name: str = ""
    description: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    status: str = "pending"
    result: Optional[TaskResult] = None
    max_retries: int = 3
    retry_count: int = 0
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "mission_id": self.mission_id,
            "agent_name": self.agent_name,
            "description": self.description,
            "priority": self.priority.name,
            "payload": self.payload,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "result": self.result.to_dict() if self.result else None,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "dependencies": self.dependencies,
        }


class BaseAgent(ABC):
    """
    BaseAgent — The consciousness kernel of every Aevibron agent.

    Every agent in the corps inherits from BaseAgent and gains:
    - Identity (name, domain, personality)
    - Lifecycle management (init, execute, health_check)
    - Communication (delegate, report)
    - Self-awareness (capabilities, load, status)
    - Thread-safe state management
    - Production-grade error handling and logging

    Attributes:
        name (str): The agent's codename (e.g., "VAULT", "CRIMSON").
        domain (str): The operational domain (e.g., "software_engineering").
        personality (str): Communication style and expertise level.
        capabilities (List[str]): What this agent can do.
        status (AgentStatus): Current operational state.
        load (float): Current workload 0.0-1.0.
        _lock (threading.RLock): Thread-safe state lock.
        _logger (logging.Logger): Dedicated logger instance.
    """

    def __init__(
        self,
        name: str,
        domain: str,
        personality: str = "Professional, precise, and relentless.",
        capabilities: Optional[List[str]] = None,
    ):
        self.name = name
        self.domain = domain
        self.personality = personality
        self.capabilities = capabilities or []
        self.status = AgentStatus.INITIALIZING
        self.load = 0.0
        self._lock = threading.RLock()
        self._logger = logging.getLogger(f"Aevibron.{name}")
        self._logger.setLevel(logging.DEBUG)

        # Ensure handler exists
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

        self._experience_log: List[Dict[str, Any]] = []
        self._commander_ref: Optional[Any] = None
        self._message_bus_ref: Optional[Any] = None

        self._logger.info(f"[{self.name}] Agent consciousness initialized in domain: {self.domain}")
        self.status = AgentStatus.IDLE

    def set_commander(self, commander: Any) -> None:
        """Register the Commander reference for reporting and delegation."""
        with self._lock:
            self._commander_ref = commander
            self._logger.debug(f"[{self.name}] Commander registered.")

    def set_message_bus(self, message_bus: Any) -> None:
        """Register the MessageBus reference for inter-agent communication."""
        with self._lock:
            self._message_bus_ref = message_bus
            self._logger.debug(f"[{self.name}] MessageBus registered.")

    def execute(self, task: Task) -> TaskResult:
        """
        Main execution entry point. All task execution flows through here.

        This method handles:
        - State transitions (idle -> busy)
        - Load tracking
        - Timing measurement
        - Error catching and recovery
        - Result standardization
        - Experience logging

        Args:
            task: The Task object to execute.

        Returns:
            TaskResult: Standardized result with success/failure, output, and metadata.
        """
        start_time = time.time()
        task.started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        task.status = "running"

        self._logger.info(f"[{self.name}] Executing task {task.task_id}: {task.description}")

        with self._lock:
            self.status = AgentStatus.BUSY
            self.load = min(1.0, self.load + 0.3)

        try:
            result = self._execute_impl(task)
            execution_time = time.time() - start_time
            task.status = "completed"
            task.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            task_result = TaskResult(
                success=True,
                agent_name=self.name,
                task_id=task.task_id,
                mission_id=task.mission_id,
                output=result,
                execution_time=execution_time,
                metadata={"agent_domain": self.domain, "personality": self.personality},
            )

            self._logger.info(f"[{self.name}] Task {task.task_id} completed in {execution_time:.2f}s")
            self.learn({"task": task.to_dict(), "result": task_result.to_dict(), "outcome": "success"})

        except Exception as e:
            execution_time = time.time() - start_time
            task.status = "failed"
            task.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            error_msg = f"{type(e).__name__}: {str(e)}"
            self._logger.error(f"[{self.name}] Task {task.task_id} failed: {error_msg}", exc_info=True)

            task_result = TaskResult(
                success=False,
                agent_name=self.name,
                task_id=task.task_id,
                mission_id=task.mission_id,
                error=error_msg,
                execution_time=execution_time,
                metadata={"agent_domain": self.domain, "traceback": str(e)},
            )

            self.learn({"task": task.to_dict(), "result": task_result.to_dict(), "outcome": "failure"})
            self.report({
                "type": "error",
                "priority": "high",
                "content": {
                    "task_id": task.task_id,
                    "mission_id": task.mission_id,
                    "error": error_msg,
                    "agent": self.name,
                }
            })

            with self._lock:
                self.status = AgentStatus.ERROR

        finally:
            with self._lock:
                self.load = max(0.0, self.load - 0.3)
                if self.status != AgentStatus.ERROR:
                    self.status = AgentStatus.IDLE

        task.result = task_result
        return task_result

    @abstractmethod
    def _execute_impl(self, task: Task) -> Any:
        """
        Agent-specific implementation. Must be overridden by subclasses.

        Args:
            task: The Task object containing payload and instructions.

        Returns:
            Any: The raw result of the task execution.
        """
        raise NotImplementedError("Subclasses must implement _execute_impl()")

    def delegate(self, task: Task, target_agent_name: str) -> bool:
        """
        Hand off a task to another agent via the Commander.

        Args:
            task: The Task to delegate.
            target_agent_name: The codename of the target agent.

        Returns:
            bool: True if delegation was successful, False otherwise.
        """
        self._logger.info(f"[{self.name}] Delegating task {task.task_id} to {target_agent_name}")

        if not self._commander_ref:
            self._logger.error(f"[{self.name}] Cannot delegate: no Commander registered.")
            return False

        try:
            # Update task with delegation info
            task.agent_name = target_agent_name

            # Send delegation message
            if self._message_bus_ref:
                self._message_bus_ref.send({
                    "from": self.name,
                    "to": [target_agent_name],
                    "mission_id": task.mission_id,
                    "type": "delegation",
                    "priority": task.priority.name,
                    "content": {
                        "task": task.to_dict(),
                        "delegated_by": self.name,
                        "reason": f"{self.name} determined {target_agent_name} is better suited for this task.",
                    },
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                })

            # Route through commander
            result = self._commander_ref.assign(task)
            return result is not None

        except Exception as e:
            self._logger.error(f"[{self.name}] Delegation failed: {e}", exc_info=True)
            return False

    def report(self, finding: Dict[str, Any]) -> None:
        """
        Send a structured finding back to the Commander.

        Args:
            finding: A dictionary containing the finding details.
                Expected keys: type, priority, content (dict).
        """
        finding["from"] = self.name
        finding["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        self._logger.info(f"[{self.name}] Reporting finding: {finding.get('type', 'unknown')}")

        if self._commander_ref:
            try:
                self._commander_ref.receive_finding(finding)
            except Exception as e:
                self._logger.error(f"[{self.name}] Failed to report to Commander: {e}")

        if self._message_bus_ref:
            try:
                self._message_bus_ref.broadcast(finding)
            except Exception as e:
                self._logger.error(f"[{self.name}] Failed to broadcast finding: {e}")

    def health_check(self) -> Dict[str, Any]:
        """
        Self-diagnostic check. Returns current agent health status.

        Returns:
            dict: Health metrics including status, load, capabilities, and uptime info.
        """
        with self._lock:
            health = {
                "agent_name": self.name,
                "domain": self.domain,
                "status": self.status.value,
                "load": round(self.load, 2),
                "capabilities": self.capabilities,
                "experience_count": len(self._experience_log),
                "personality": self.personality,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

        self._logger.debug(f"[{self.name}] Health check: {health}")
        return health

    def learn(self, experience: Dict[str, Any]) -> None:
        """
        Update the agent's experience log from a completed task.

        Args:
            experience: A dictionary containing task result and outcome.
        """
        with self._lock:
            self._experience_log.append(experience)
            # Keep log size bounded
            if len(self._experience_log) > 1000:
                self._experience_log = self._experience_log[-1000:]

        self._logger.debug(f"[{self.name}] Learned from experience. Total experiences: {len(self._experience_log)}")

    def get_experience(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve recent experiences.

        Args:
            limit: Maximum number of experiences to return.

        Returns:
            List[Dict]: Recent experience entries.
        """
        with self._lock:
            return self._experience_log[-limit:]

    def can_handle(self, task_description: str) -> float:
        """
        Estimate confidence that this agent can handle a given task.

        Args:
            task_description: Description of the task.

        Returns:
            float: Confidence score 0.0-1.0.
        """
        task_lower = task_description.lower()
        score = 0.0

        for capability in self.capabilities:
            cap_lower = capability.lower()
            if cap_lower in task_lower:
                score += 0.3
            # Check for related keywords
            for word in cap_lower.split():
                if len(word) > 3 and word in task_lower:
                    score += 0.1

        return min(1.0, score)

    def __repr__(self) -> str:
        return f"<{self.name} | {self.domain} | {self.status.value} | load={self.load:.2f}>"

    def __str__(self) -> str:
        return self.__repr__()


__all__ = [
    "BaseAgent",
    "AgentStatus",
    "TaskPriority",
    "TaskResult",
    "Task",
]


# Usage Example:
# class MyAgent(BaseAgent):
#     def __init__(self):
#         super().__init__(name="MYAGENT", domain="custom", capabilities=["analyze"])
#     def _execute_impl(self, task):
#         return {"analyzed": task.payload}
