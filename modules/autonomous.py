"""IRIS v1 Hybrid Autonomous Task Engine - Works While You Sleep"""
import os
import json
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from queue import Queue, Empty
from config import config
from core.db import db
from core.orchestrator import orchestrator

class AutonomousEngine:
    """
    IRIS works autonomously:
    - Background task queue
    - Scheduled tasks (cron-like)
    - Self-monitoring and health checks
    - Auto-repair when things break
    - Continuous learning from the web
    - Periodic self-improvement cycles
    """

    def __init__(self):
        self.task_queue = Queue()
        self.running = False
        self.worker_thread = None
        self.scheduled_tasks = {}
        self.health_check_interval = 300  # 5 minutes
        self.last_health_check = None
        self.learning_interval = 3600  # 1 hour
        self.last_learning = None

    def start(self):
        """Start the autonomous worker"""
        if self.running:
            return {"status": "already_running"}

        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

        db.log("INFO", "autonomous", "Autonomous engine started")
        return {"status": "started", "message": "IRIS is now working autonomously"}

    def stop(self):
        """Stop the autonomous worker"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        db.log("INFO", "autonomous", "Autonomous engine stopped")
        return {"status": "stopped"}

    def _worker_loop(self):
        """Main autonomous worker loop"""
        while self.running:
            try:
                # Process queued tasks
                try:
                    task = self.task_queue.get(timeout=10)
                    self._execute_task(task)
                except Empty:
                    pass

                # Health check every 5 minutes
                if self._should_health_check():
                    self._health_check()

                # Self-learning every hour
                if self._should_learn():
                    self._self_learn()

                # Check scheduled tasks
                self._check_scheduled()

                time.sleep(1)

            except Exception as e:
                db.log("ERROR", "autonomous", f"Worker loop error: {e}")
                time.sleep(5)

    def queue_task(self, description: str, priority: int = 5, 
                   estimated_minutes: int = 10, task_type: str = "general") -> str:
        """Queue a task for autonomous execution"""
        task_id = f"auto_{uuid.uuid4().hex[:8]}"
        task = {
            "id": task_id,
            "description": description,
            "priority": priority,
            "estimated_minutes": estimated_minutes,
            "type": task_type,
            "status": "queued",
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "result": None
        }

        self.task_queue.put(task)
        db.create_task(task_id, description, priority, estimated_minutes)

        return task_id

    def schedule_task(self, description: str, run_at: datetime, 
                     recurring: bool = False, interval_hours: int = 24) -> str:
        """Schedule a task for future execution"""
        task_id = f"sched_{uuid.uuid4().hex[:8]}"
        task = {
            "id": task_id,
            "description": description,
            "run_at": run_at,
            "recurring": recurring,
            "interval_hours": interval_hours,
            "last_run": None,
            "status": "scheduled"
        }

        self.scheduled_tasks[task_id] = task
        return task_id

    def _execute_task(self, task: Dict):
        """Execute a single task"""
        task["status"] = "running"
        task["started_at"] = datetime.now().isoformat()
        db.update_task(task["id"], status="running")

        try:
            # Use the orchestrator to process the task
            for update in orchestrator.process(task["description"], session_id="autonomous"):
                if update.get("final"):
                    task["result"] = update
                    break

            task["status"] = "completed"
            task["completed_at"] = datetime.now().isoformat()
            db.update_task(task["id"], status="completed", result=json.dumps(task["result"]))

            # Notify user
            db.save_episode(
                f"Autonomous task completed: {task['description'][:100]}",
                emotion="satisfaction",
                lesson="Autonomous execution successful"
            )

        except Exception as e:
            task["status"] = "failed"
            task["error"] = str(e)
            db.update_task(task["id"], status="failed", error=str(e))
            db.log("ERROR", "autonomous", f"Task failed: {e}")

    def _should_health_check(self) -> bool:
        """Check if health check is due"""
        if self.last_health_check is None:
            return True
        return (datetime.now() - self.last_health_check).seconds > self.health_check_interval

    def _health_check(self):
        """Run self health check"""
        self.last_health_check = datetime.now()

        from core.tool_registry import tool_registry
        result = tool_registry.tools["self_diagnose"]()

        if not result.data.get("healthy"):
            # Try to fix issues
            db.log("WARNING", "autonomous", "Health check failed, attempting auto-repair")
            self._auto_repair(result.data.get("checks", {}))

        db.save_episode(
            "Health check completed",
            emotion="neutral",
            lesson=f"System health: {'Good' if result.data.get('healthy') else 'Needs attention'}"
        )

    def _auto_repair(self, checks: Dict):
        """Attempt automatic repair of system issues"""
        for component, status in checks.items():
            if not status.get("ok"):
                db.log("WARNING", "autonomous", f"Attempting repair: {component}")

                if component == "database":
                    # Reinitialize database
                    try:
                        from core.db import Database
                        Database()
                        db.log("INFO", "autonomous", "Database reinitialized")
                    except Exception as e:
                        db.log("ERROR", "autonomous", f"Database repair failed: {e}")

                elif component == "aevibron_connection":
                    # Test connection
                    try:
                        from core.aevibron_client import aevibron
                        aevibron.fast_response("ping")
                    except Exception as e:
                        db.log("ERROR", "autonomous", f"Aevibron connection failed: {e}")

    def _should_learn(self) -> bool:
        """Check if learning cycle is due"""
        if self.last_learning is None:
            return True
        return (datetime.now() - self.last_learning).seconds > self.learning_interval

    def _self_learn(self):
        """Autonomous learning cycle"""
        self.last_learning = datetime.now()

        # Learn from web
        topics = ["python best practices 2026", "flask security", "ai agent architecture"]
        for topic in topics:
            try:
                from core.tool_registry import tool_registry
                result = tool_registry.tools["search_web"](query=topic, max_results=3)
                if result.success:
                    # Store learnings
                    for item in result.data.get("results", [])[:2]:
                        db.save_memory(
                            f"learned_{topic}_{datetime.now().timestamp()}",
                            item.get("body", "")[:500],
                            category="knowledge",
                            importance=3
                        )
            except Exception as e:
                db.log("WARNING", "autonomous", f"Learning failed for {topic}: {e}")

        # Self-improvement cycle
        try:
            from modules.self_improve import self_improvement
            result = self_improvement.self_diagnose_and_fix()
            if result.get("fixes_applied", 0) > 0:
                db.save_episode(
                    f"Self-improved: {result['fixes_applied']} fixes applied",
                    emotion="pride",
                    lesson="Continuous self-improvement is working"
                )
        except Exception as e:
            db.log("WARNING", "autonomous", f"Self-improvement cycle failed: {e}")

    def _check_scheduled(self):
        """Check and execute scheduled tasks"""
        now = datetime.now()
        for task_id, task in list(self.scheduled_tasks.items()):
            if task["status"] == "scheduled" and now >= task["run_at"]:
                # Execute
                self.task_queue.put({
                    "id": task_id,
                    "description": task["description"],
                    "priority": 5,
                    "estimated_minutes": 10,
                    "type": "scheduled",
                    "status": "queued",
                    "created_at": now.isoformat()
                })

                task["last_run"] = now
                if task["recurring"]:
                    task["run_at"] = now + timedelta(hours=task["interval_hours"])
                else:
                    task["status"] = "completed"

    def get_status(self) -> Dict:
        """Get autonomous engine status"""
        return {
            "running": self.running,
            "queue_size": self.task_queue.qsize(),
            "scheduled_tasks": len(self.scheduled_tasks),
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "last_learning": self.last_learning.isoformat() if self.last_learning else None,
            "health_check_interval": self.health_check_interval,
            "learning_interval": self.learning_interval
        }

    def get_task_history(self, limit: int = 50) -> List[Dict]:
        """Get recent task history"""
        conn = db.get_connection()
        cursor = conn.execute(
            "SELECT * FROM tasks WHERE task_id LIKE 'auto_%' OR task_id LIKE 'sched_%' ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

autonomous_engine = AutonomousEngine()
