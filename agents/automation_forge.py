#!/usr/bin/env python3
"""
automation_forge.py — GEAR
Workflow Automation Agent for IRIS v7.0
Visual workflow builder (JSON-based DAG), triggers (time/file/event/webhook/cron),
conditional logic (if/else/switch), error handling/retry with backoff,
script generation (Python/bash from DAG).
"""

import threading
import hashlib
import json
import logging
import time
import os
import subprocess
import sched
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Tuple, Optional, Callable
from datetime import datetime, timedelta
from queue import Queue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GEAR")


class AutomationForge:
    CODENAME = "GEAR"

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._session_id = hashlib.sha256(f"{self.CODENAME}{time.time()}".encode()).hexdigest()[:16]
        self._workflows: Dict[str, Dict[str, Any]] = {}
        self._triggers: Dict[str, threading.Thread] = {}
        self._scheduler = sched.scheduler(time.time, time.sleep)
        self._scheduler_thread: Optional[threading.Thread] = None
        logger.info(f"[{self.CODENAME}] Session {self._session_id} initialized.")

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True
            self._running = True
            self._scheduler_thread = threading.Thread(target=self._scheduler.run, daemon=True)
            self._scheduler_thread.start()
            self._report_to_commander("GEAR started", level="info")
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return True
            self._running = False
            for t in self._triggers.values():
                if t.is_alive():
                    # Threads are daemon; they will exit with process
                    pass
            self._report_to_commander("GEAR stopped", level="info")
            return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "agent": self.CODENAME,
                "session_id": self._session_id,
                "running": self._running,
                "workflows": len(self._workflows),
                "active_triggers": len(self._triggers),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _report_to_commander(self, message: str, level: str = "info", data: Any = None) -> None:
        payload = {
            "agent": self.CODENAME,
            "session_id": self._session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "data": data,
        }
        if self._commander_bus:
            try:
                self._commander_bus.publish(f"agent.{self.CODENAME}", payload)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Bus error: {e}")
        else:
            logger.log(getattr(logging, level.upper(), logging.INFO), f"[{self.CODENAME}] {message}")

    def _store_memory(self, key: str, value: Any) -> None:
        if self._shared_memory:
            try:
                self._shared_memory.set(f"{self.CODENAME}.{key}", value, ttl=86400)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Memory store error: {e}")

    def _execute_shell(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------
    def create_workflow(self, workflow_id: str, dag: Dict[str, Any]) -> Dict[str, Any]:
        """Register a JSON-based DAG workflow."""
        if not self._running:
            raise RuntimeError("Agent not running")
        with self._lock:
            self._workflows[workflow_id] = {
                "id": workflow_id,
                "dag": dag,
                "created_at": datetime.utcnow().isoformat(),
                "runs": 0,
                "status": "idle",
            }
        self._store_memory(f"workflow:{workflow_id}", self._workflows[workflow_id])
        self._report_to_commander(f"Workflow '{workflow_id}' created", data={"nodes": len(dag.get("nodes", []))})
        return self._workflows[workflow_id]

    def run_workflow(self, workflow_id: str, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a workflow DAG with dependency resolution and retry logic."""
        if not self._running:
            raise RuntimeError("Agent not running")
        wf = self._workflows.get(workflow_id)
        if not wf:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        dag = wf["dag"]
        nodes: Dict[str, Dict] = {n["id"]: n for n in dag.get("nodes", [])}
        edges = dag.get("edges", [])
        adjacency: Dict[str, List[str]] = {n: [] for n in nodes}
        in_degree: Dict[str, int] = {n: 0 for n in nodes}
        for e in edges:
            src, tgt = e.get("from"), e.get("to")
            if src in adjacency and tgt in adjacency:
                adjacency[src].append(tgt)
                in_degree[tgt] += 1

        results: Dict[str, Any] = {}
        ready = [n for n, d in in_degree.items() if d == 0]
        executed: set = set()
        start_time = time.time()

        while ready:
            node_id = ready.pop(0)
            node = nodes[node_id]
            action = node.get("action", "noop")
            params = node.get("params", {})
            retry = node.get("retry", 3)
            backoff = node.get("backoff", 1.0)

            # Merge inputs into params
            ctx = {**(inputs or {}), **results}
            for k, v in params.items():
                if isinstance(v, str) and v.startswith("$"):
                    params[k] = ctx.get(v[1:], v)

            success = False
            last_error = ""
            for attempt in range(retry):
                try:
                    result = self._execute_action(action, params)
                    results[node_id] = result
                    success = True
                    break
                except Exception as e:
                    last_error = str(e)
                    time.sleep(backoff * (2 ** attempt))
            if not success:
                results[node_id] = {"error": last_error, "attempts": retry}
                self._report_to_commander(f"Workflow node '{node_id}' failed after {retry} attempts", level="error", data=results[node_id])
                # Continue execution for independent branches
            executed.add(node_id)
            for neighbor in adjacency[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    ready.append(neighbor)

        duration = round(time.time() - start_time, 3)
        wf["runs"] += 1
        wf["last_run"] = datetime.utcnow().isoformat()
        wf["status"] = "completed" if all(results.get(n, {}).get("error") is None for n in nodes) else "partial_failure"
        summary = {"workflow_id": workflow_id, "duration": duration, "results": results, "status": wf["status"]}
        self._store_memory(f"run:{workflow_id}:{int(time.time())}", summary)
        return summary

    def _execute_action(self, action: str, params: Dict[str, Any]) -> Any:
        """Execute a single workflow action."""
        if action == "shell":
            rc, out, err = self._execute_shell(params.get("command", ""), timeout=params.get("timeout", 60))
            return {"returncode": rc, "stdout": out, "stderr": err}
        elif action == "http":
            method = params.get("method", "GET")
            url = params.get("url", "")
            data = json.dumps(params.get("body")).encode() if params.get("body") else None
            req = urllib.request.Request(url, data=data, method=method,
                                         headers={"Content-Type": "application/json", **params.get("headers", {})})
            with urllib.request.urlopen(req, timeout=params.get("timeout", 30)) as resp:
                return {"status": resp.status, "body": resp.read().decode("utf-8", errors="replace")[:2000]}
        elif action == "python":
            code = params.get("code", "")
            local_ns: Dict[str, Any] = {}
            exec(code, {"__builtins__": __builtins__}, local_ns)
            return {"locals": {k: str(v) for k, v in local_ns.items()}}
        elif action == "file_op":
            op = params.get("op", "read")
            path = params.get("path", "")
            if op == "read":
                with open(path, "r") as f:
                    return {"content": f.read()}
            elif op == "write":
                with open(path, "w") as f:
                    f.write(params.get("content", ""))
                return {"written": True}
            elif op == "delete":
                os.remove(path)
                return {"deleted": True}
            else:
                return {"error": f"Unknown file op: {op}"}
        elif action == "condition":
            expr = params.get("expression", "True")
            return {"eval": eval(expr, {"__builtins__": {}}, params)}
        elif action == "wait":
            time.sleep(params.get("seconds", 1))
            return {"waited": params.get("seconds", 1)}
        else:
            return {"error": f"Unknown action: {action}"}

    def add_trigger(self, trigger_id: str, trigger_type: str, config: Dict[str, Any], workflow_id: str) -> Dict[str, Any]:
        """Add a trigger that fires a workflow on time/file/event/webhook/cron."""
        if not self._running:
            raise RuntimeError("Agent not running")
        if trigger_type == "cron":
            # Simple cron-like: minute hour day month dow
            parts = config.get("cron", "* * * * *").split()
            interval = config.get("interval_seconds", 60)
            def cron_loop():
                while self._running:
                    self.run_workflow(workflow_id, config.get("inputs"))
                    time.sleep(interval)
            t = threading.Thread(target=cron_loop, daemon=True)
            t.start()
            self._triggers[trigger_id] = t
        elif trigger_type == "webhook":
            # Webhook trigger would be handled by an external HTTP server; store config for lookup
            self._store_memory(f"trigger:webhook:{trigger_id}", {"workflow_id": workflow_id, "config": config})
        elif trigger_type == "file":
            path = config.get("path", "")
            def file_loop():
                last_mtime = 0
                while self._running:
                    try:
                        mtime = os.path.getmtime(path)
                        if mtime != last_mtime:
                            last_mtime = mtime
                            self.run_workflow(workflow_id, {**config.get("inputs", {}), "file_path": path, "mtime": mtime})
                    except FileNotFoundError:
                        pass
                    time.sleep(config.get("poll_interval", 5))
            t = threading.Thread(target=file_loop, daemon=True)
            t.start()
            self._triggers[trigger_id] = t
        elif trigger_type == "event":
            # Event triggers listen on the message bus
            self._store_memory(f"trigger:event:{trigger_id}", {"workflow_id": workflow_id, "config": config})
        else:
            raise ValueError(f"Unknown trigger type: {trigger_type}")
        return {"trigger_id": trigger_id, "type": trigger_type, "workflow_id": workflow_id, "status": "active"}

    def generate_script(self, workflow_id: str, language: str = "python") -> str:
        """Generate a standalone Python or bash script from a workflow DAG."""
        wf = self._workflows.get(workflow_id)
        if not wf:
            raise ValueError(f"Workflow '{workflow_id}' not found")
        dag = wf["dag"]
        if language == "python":
            lines = ["#!/usr/bin/env python3", "# Auto-generated by GEAR / IRIS v7.0", ""]
            for node in dag.get("nodes", []):
                nid = node["id"]
                action = node.get("action", "noop")
                params = node.get("params", {})
                if action == "shell":
                    lines.append(f"import subprocess")
                    lines.append(f"result_{nid} = subprocess.run({repr(params.get('command',''))}, shell=True, capture_output=True, text=True)")
                elif action == "http":
                    lines.append(f"import urllib.request")
                    lines.append(f"req = urllib.request.Request({repr(params.get('url',''))}, method={repr(params.get('method','GET'))})")
                    lines.append(f"with urllib.request.urlopen(req) as resp: result_{nid} = resp.read().decode()")
                elif action == "file_op":
                    lines.append(f"with open({repr(params.get('path',''))}, 'r') as f: result_{nid} = f.read()")
                else:
                    lines.append(f"result_{nid} = None  # action: {action}")
            lines.append("")
            lines.append("if __name__ == '__main__':")
            lines.append("    print('Workflow executed')")
            return "\n".join(lines)
        elif language == "bash":
            lines = ["#!/usr/bin/env bash", "# Auto-generated by GEAR / IRIS v7.0", ""]
            for node in dag.get("nodes", []):
                action = node.get("action", "noop")
                params = node.get("params", {})
                if action == "shell":
                    lines.append(params.get("command", "# no command"))
                elif action == "file_op":
                    lines.append(f"cat {params.get('path', '/dev/null')}")
                else:
                    lines.append(f"# action: {action}")
            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported language: {language}")

    # ------------------------------------------------------------------
    # Unit test stubs
    # ------------------------------------------------------------------
    def test_create_and_run_workflow(self) -> bool:
        dag = {
            "nodes": [
                {"id": "a", "action": "shell", "params": {"command": "echo hello"}},
                {"id": "b", "action": "condition", "params": {"expression": "True"}},
            ],
            "edges": [{"from": "a", "to": "b"}],
        }
        self.create_workflow("test_wf", dag)
        r = self.run_workflow("test_wf")
        return r["results"]["a"]["returncode"] == 0

    def test_generate_script(self) -> bool:
        dag = {"nodes": [{"id": "a", "action": "shell", "params": {"command": "echo hi"}}], "edges": []}
        self.create_workflow("test_script", dag)
        s = self.generate_script("test_script", "python")
        return "subprocess" in s

    def test_add_trigger(self) -> bool:
        dag = {"nodes": [{"id": "a", "action": "wait", "params": {"seconds": 0.1}}], "edges": []}
        self.create_workflow("test_trig", dag)
        r = self.add_trigger("t1", "cron", {"interval_seconds": 3600}, "test_trig")
        return r["status"] == "active"


if __name__ == "__main__":
    agent = AutomationForge()
    agent.start()
    print(agent.health())
    agent.stop()
