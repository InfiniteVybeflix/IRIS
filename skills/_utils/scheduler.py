"""Simple scheduler for skill background tasks."""
import time
import threading
import logging
from typing import Callable, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class SkillScheduler:
    """Lightweight scheduler for recurring skill tasks."""

    def __init__(self):
        self._tasks: Dict[str, Dict] = {}
        self._thread: threading.Thread = None
        self._running = False

    def add(self, name: str, interval_seconds: int, callback: Callable, args: tuple = ()):
        self._tasks[name] = {
            "interval": interval_seconds,
            "callback": callback,
            "args": args,
            "last_run": 0,
        }
        logger.info(f"Scheduled task '{name}' every {interval_seconds}s")

    def remove(self, name: str):
        if name in self._tasks:
            del self._tasks[name]

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("SkillScheduler started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self):
        while self._running:
            now = time.time()
            for name, task in self._tasks.items():
                if now - task["last_run"] >= task["interval"]:
                    try:
                        task["callback"](*task["args"])
                    except Exception as e:
                        logger.error(f"Scheduler task '{name}' failed: {e}")
                    task["last_run"] = now
            time.sleep(1)
