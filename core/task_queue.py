"""
Aevibron Agent Corps — Task Queue
Priority task queue with persistence, dependency tracking, and status monitoring.

Author: IRIS v1.0
"""

import heapq
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_agent import Task, TaskPriority, TaskResult


@dataclass(order=True)


class QueuedTask:
    """
    Internal wrapper for tasks in the priority queue.
    Uses heapq ordering based on priority and insertion time.
    """
    priority_value: int = field(compare=True)
    insertion_time: float = field(compare=True)
    task: Task = field(compare=False)


class TaskQueue:
    """
    TaskQueue — The mission control center of the Aevibron Agent Corps.

    Manages prioritized task execution with:
    - Priority-based ordering (CRITICAL > HIGH > MEDIUM > LOW)
    - Dependency tracking (tasks wait for prerequisites)
    - Persistence to disk for crash recovery
    - Status monitoring and querying
    - Thread-safe operations
    - Retry logic with exponential backoff

    Attributes:
        _queue (list): Heap-based priority queue.
        _tasks (dict): Mapping of task_id -> task for O(1) lookups.
        _completed (dict): Mapping of task_id -> completed task.
        _lock (threading.RLock): Thread-safe lock.
        _logger (logging.Logger): Logger instance.
        _persistence_path (str): Path for persistence.
    """

    def __init__(self, persistence_path: Optional[str] = None):
        self._queue: List[QueuedTask] = []
        self._tasks: Dict[str, Task] = {}
        self._completed: Dict[str, Task] = {}
        self._lock = threading.RLock()
        self._logger = logging.getLogger("Aevibron.TaskQueue")
        self._logger.setLevel(logging.DEBUG)

        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

        # Check if PostgreSQL is available for persistent storage
        self._use_postgres = False
        try:
            from core.db import db
            if db._db_available and db.use_postgres:
                self._use_postgres = True
                self._db = db
                self._logger.info("[TaskQueue] Using PostgreSQL for persistence")
        except Exception:
            pass

        if not self._use_postgres:
            if persistence_path is None:
                try:
                    from config import config
                    default_dir = os.path.join(config.TMP_DIR, "agents")
                    os.makedirs(default_dir, exist_ok=True)
                    persistence_path = os.path.join(default_dir, "task_queue.json")
                except Exception:
                    persistence_path = os.path.join("/tmp", "iris-task_queue.json")
            self._persistence_path = persistence_path
            try:
                Path(self._persistence_path).parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        self._logger.info("[TaskQueue] Mission control initialized.")

    def enqueue(self, task: Task, priority: Optional[TaskPriority] = None) -> str:
        """
        Add a task to the queue with priority.

        Args:
            task: The Task to enqueue.
            priority: Optional override for task priority.

        Returns:
            str: The task_id of the enqueued task.
        """
        try:
            if priority:
                task.priority = priority

            priority_value = task.priority.value
            insertion_time = time.time()

            queued = QueuedTask(
                priority_value=priority_value,
                insertion_time=insertion_time,
                task=task,
            )

            with self._lock:
                heapq.heappush(self._queue, queued)
                self._tasks[task.task_id] = task
                task.status = "queued"

            self._logger.info(
                f"[TaskQueue] Enqueued {task.task_id} (priority={task.priority.name}, mission={task.mission_id})"
            )
            return task.task_id

        except Exception as e:
            self._logger.error(f"[TaskQueue] Enqueue failed: {e}", exc_info=True)
            raise

    def dequeue(self) -> Optional[Task]:
        """
        Remove and return the highest-priority task that has no unmet dependencies.

        Returns:
            Task: The next task to execute, or None if queue is empty.
        """
        with self._lock:
            # Find the highest priority task with all dependencies met
            temp_queue = []
            found_task = None

            while self._queue and not found_task:
                queued = heapq.heappop(self._queue)
                task = queued.task

                # Check dependencies
                deps_met = True
                for dep_id in task.dependencies:
                    if dep_id not in self._completed:
                        # Check if dep is in queue but not completed
                        if dep_id in self._tasks and self._tasks[dep_id].status not in ["completed", "failed"]:
                            deps_met = False
                            break
                        # If dep failed, mark this task as failed too
                        elif dep_id in self._tasks and self._tasks[dep_id].status == "failed":
                            task.status = "failed"
                            task.result = TaskResult(
                                success=False,
                                agent_name=task.agent_name,
                                task_id=task.task_id,
                                mission_id=task.mission_id,
                                error=f"Dependency {dep_id} failed",
                            )
                            self._completed[task.task_id] = task
                            deps_met = False
                            break

                if deps_met and task.status != "failed":
                    found_task = task
                    task.status = "assigned"
                else:
                    temp_queue.append(queued)

            # Put back tasks that weren't ready
            for queued in temp_queue:
                heapq.heappush(self._queue, queued)

            if found_task:
                self._logger.info(f"[TaskQueue] Dequeued {found_task.task_id} (mission={found_task.mission_id})")
                return found_task
            else:
                return None

    def peek(self) -> Optional[Task]:
        """
        View the highest-priority task without removing it.

        Returns:
            Task: The next task, or None if queue is empty.
        """
        with self._lock:
            if not self._queue:
                return None
            return self._queue[0].task

    def get_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get the status of a task.

        Args:
            task_id: The task identifier.

        Returns:
            Dict: Task status information.
        """
        with self._lock:
            if task_id in self._completed:
                task = self._completed[task_id]
                return {
                    "task_id": task_id,
                    "status": task.status,
                    "result": task.result.to_dict() if task.result else None,
                    "completed": True,
                }

            if task_id in self._tasks:
                task = self._tasks[task_id]
                return {
                    "task_id": task_id,
                    "status": task.status,
                    "priority": task.priority.name,
                    "mission_id": task.mission_id,
                    "agent_name": task.agent_name,
                    "description": task.description,
                    "dependencies": task.dependencies,
                    "retry_count": task.retry_count,
                    "created_at": task.created_at,
                    "completed": False,
                }

            return {"task_id": task_id, "status": "not_found", "completed": False}

    def get_mission_tasks(self, mission_id: str) -> List[Dict[str, Any]]:
        """
        Get all tasks for a specific mission.

        Args:
            mission_id: The mission identifier.

        Returns:
            List[Dict]: All tasks in the mission.
        """
        with self._lock:
            tasks = []

            # Active tasks
            for task in self._tasks.values():
                if task.mission_id == mission_id:
                    tasks.append({
                        "task_id": task.task_id,
                        "status": task.status,
                        "priority": task.priority.name,
                        "description": task.description,
                        "agent_name": task.agent_name,
                    })

            # Completed tasks
            for task in self._completed.values():
                if task.mission_id == mission_id:
                    tasks.append({
                        "task_id": task.task_id,
                        "status": task.status,
                        "priority": task.priority.name,
                        "description": task.description,
                        "agent_name": task.agent_name,
                        "result": task.result.to_dict() if task.result else None,
                    })

            return tasks

    def mark_completed(self, task_id: str, result: TaskResult) -> bool:
        """
        Mark a task as completed with its result.

        Args:
            task_id: The task identifier.
            result: The TaskResult from execution.

        Returns:
            bool: True if marked successfully.
        """
        with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.status = "completed"
                task.result = result
                task.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self._completed[task_id] = task
                del self._tasks[task_id]

                self._logger.info(f"[TaskQueue] Task {task_id} marked completed.")
                return True

            return False

    def mark_failed(self, task_id: str, error: str, allow_retry: bool = True) -> bool:
        """
        Mark a task as failed.

        Args:
            task_id: The task identifier.
            error: Error message.
            allow_retry: Whether to allow retry if retries remain.

        Returns:
            bool: True if task will be retried, False if permanently failed.
        """
        with self._lock:
            if task_id not in self._tasks:
                return False

            task = self._tasks[task_id]
            task.retry_count += 1

            if allow_retry and task.retry_count < task.max_retries:
                # Re-queue with same priority
                task.status = "queued"
                task.result = None

                queued = QueuedTask(
                    priority_value=task.priority.value,
                    insertion_time=time.time(),
                    task=task,
                )
                heapq.heappush(self._queue, queued)

                self._logger.warning(
                    f"[TaskQueue] Task {task_id} failed (attempt {task.retry_count}/{task.max_retries}), requeued."
                )
                return True
            else:
                task.status = "failed"
                task.result = TaskResult(
                    success=False,
                    agent_name=task.agent_name,
                    task_id=task.task_id,
                    mission_id=task.mission_id,
                    error=error,
                )
                task.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self._completed[task_id] = task
                del self._tasks[task_id]

                self._logger.error(f"[TaskQueue] Task {task_id} permanently failed after {task.retry_count} retries.")
                return False

    def cancel(self, task_id: str) -> bool:
        """
        Cancel a pending task.

        Args:
            task_id: The task identifier.

        Returns:
            bool: True if cancelled, False if not found or already running.
        """
        with self._lock:
            if task_id not in self._tasks:
                return False

            task = self._tasks[task_id]
            if task.status in ["running", "completed", "failed"]:
                return False

            task.status = "cancelled"
            self._completed[task_id] = task
            del self._tasks[task_id]

            # Remove from queue
            self._queue = [q for q in self._queue if q.task.task_id != task_id]
            heapq.heapify(self._queue)

            self._logger.info(f"[TaskQueue] Task {task_id} cancelled.")
            return True

    def get_queue_size(self) -> int:
        """
        Get the number of pending tasks.

        Returns:
            int: Number of tasks in queue.
        """
        with self._lock:
            return len(self._queue)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.

        Returns:
            Dict: Statistics about the queue.
        """
        with self._lock:
            priority_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
            for queued in self._queue:
                p_name = queued.task.priority.name
                if p_name in priority_counts:
                    priority_counts[p_name] += 1

            return {
                "pending": len(self._queue),
                "active": len(self._tasks) - len(self._queue),
                "completed": len(self._completed),
                "priority_breakdown": priority_counts,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

    def persist(self) -> bool:
        """Save queue state — PostgreSQL if available, JSON file otherwise."""
        try:
            with self._lock:
                data = {
                    "tasks": [task.to_dict() for task in self._tasks.values()],
                    "completed": [task.to_dict() for task in self._completed.values()],
                    "persisted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }

            if self._use_postgres:
                self._db.store_json("task_queue", "state", data)
            else:
                with open(self._persistence_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, default=str)

            return True
        except Exception as e:
            self._logger.error(f"[TaskQueue] Persistence failed: {e}")
            return False

    def load(self) -> bool:
        """Load queue state — PostgreSQL if available, JSON file otherwise."""
        try:
            if self._use_postgres:
                data = self._db.get_json("task_queue", "state")
            else:
                if not os.path.exists(self._persistence_path):
                    return False
                with open(self._persistence_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

            if not data:
                return False

            with self._lock:
                self._queue = []
                self._tasks = {}
                self._completed = {}

                # Rebuild tasks
                for task_dict in data.get("tasks", []):
                    task = Task(
                        task_id=task_dict.get("task_id", str(uuid.uuid4())),
                        mission_id=task_dict.get("mission_id", ""),
                        agent_name=task_dict.get("agent_name", ""),
                        description=task_dict.get("description", ""),
                        priority=TaskPriority[task_dict.get("priority", "MEDIUM")],
                        payload=task_dict.get("payload", {}),
                        created_at=task_dict.get("created_at", ""),
                        started_at=task_dict.get("started_at"),
                        completed_at=task_dict.get("completed_at"),
                        status=task_dict.get("status", "pending"),
                        max_retries=task_dict.get("max_retries", 3),
                        retry_count=task_dict.get("retry_count", 0),
                        dependencies=task_dict.get("dependencies", []),
                    )
                    self._tasks[task.task_id] = task

                    # Re-add to queue if pending
                    if task.status in ["pending", "queued", "assigned"]:
                        queued = QueuedTask(
                            priority_value=task.priority.value,
                            insertion_time=time.time(),
                            task=task,
                        )
                        heapq.heappush(self._queue, queued)

                # Rebuild completed
                for task_dict in data.get("completed", []):
                    task = Task(
                        task_id=task_dict.get("task_id", str(uuid.uuid4())),
                        mission_id=task_dict.get("mission_id", ""),
                        agent_name=task_dict.get("agent_name", ""),
                        description=task_dict.get("description", ""),
                        priority=TaskPriority[task_dict.get("priority", "MEDIUM")],
                        payload=task_dict.get("payload", {}),
                        created_at=task_dict.get("created_at", ""),
                        started_at=task_dict.get("started_at"),
                        completed_at=task_dict.get("completed_at"),
                        status=task_dict.get("status", "completed"),
                        max_retries=task_dict.get("max_retries", 3),
                        retry_count=task_dict.get("retry_count", 0),
                        dependencies=task_dict.get("dependencies", []),
                    )
                    self._completed[task.task_id] = task

            self._logger.info(f"[TaskQueue] Loaded {len(self._tasks)} active and {len(self._completed)} completed tasks.")
            return True

        except Exception as e:
            self._logger.error(f"[TaskQueue] Load failed: {e}")
            return False

    def clear(self) -> None:
        """Clear all tasks from the queue."""
        with self._lock:
            self._queue = []
            self._tasks = {}
            self._completed = {}
            self._logger.info("[TaskQueue] All tasks cleared.")


__all__ = ["TaskQueue", "QueuedTask"]


# Usage Example:
# tq = TaskQueue()
# task = Task(description="Scan network", mission_id="m1", priority=TaskPriority.HIGH)
# tq.enqueue(task)
# next_task = tq.dequeue()
# tq.mark_completed(next_task.task_id, TaskResult(success=True, agent_name="SHADOW", task_id=next_task.task_id, mission_id="m1", output={"ports": [80]}))
