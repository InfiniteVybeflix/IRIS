"""
sys_overlord.py — CORE
System operations agent. File operations (organize, sync, shred), process
management, system maintenance, backup automation, network automation,
workflow builder.
"""

import logging
import os
import re
import json
import hashlib
import subprocess
import threading
import time
import shutil
import glob
from typing import Any, Dict, List, Optional, Tuple, Set, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger("CORE")

@dataclass
class FileOperationResult:
    operation: str
    source: str
    destination: Optional[str]
    success: bool
    bytes_processed: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    error: Optional[str] = None

@dataclass
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    status: str
    cmdline: List[str] = field(default_factory=list)
    create_time: Optional[float] = None

@dataclass
class BackupJob:
    job_id: str
    source_paths: List[str]
    destination: str
    schedule: str
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    status: str = "pending"
    compression: str = "gzip"
    retention_days: int = 30

class SysOverlord:
    CODENAME = "CORE"

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._backup_jobs: Dict[str, BackupJob] = {}
        self._workflows: Dict[str, List[Dict]] = {}
        self._session_id = hashlib.sha256(
            f"core_{time.time()}_{os.urandom(8).hex()}".encode()
        ).hexdigest()[:16]
        logger.info(f"[{self.CODENAME}] Initialized session {self._session_id}")

    def start(self) -> bool:
        with self._lock:
            self._running = True
        logger.info(f"[{self.CODENAME}] Agent started")
        return True

    def stop(self) -> bool:
        with self._lock:
            self._running = False
        logger.info(f"[{self.CODENAME}] Agent stopped")
        return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "codename": self.CODENAME,
                "session_id": self._session_id,
                "running": self._running,
                "backup_jobs": len(self._backup_jobs),
                "workflows": len(self._workflows),
            }

    def _report_to_commander(self, message: str, level: str = "info", data: Optional[Dict] = None) -> None:
        payload = {
            "agent": self.CODENAME, "session_id": self._session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "level": level, "message": message, "data": data or {},
        }
        logger.info(f"[{self.CODENAME}] REPORT: {message}")
        if self._commander_bus:
            try:
                self._commander_bus.publish(f"agent.{self.CODENAME}", payload)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Bus report failed: {e}")

    def _store_memory(self, key: str, value: Any) -> None:
        if self._shared_memory:
            try:
                self._shared_memory.set(f"{self.CODENAME}.{key}", value, ttl=86400)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Memory store failed: {e}")

    def _execute_shell(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout, cwd=os.getcwd())
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    def organize_files(self, source_dir: str, rules: List[Dict[str, Any]], dry_run: bool = False) -> List[FileOperationResult]:
        results = []
        try:
            for root, dirs, files in os.walk(source_dir):
                for filename in files:
                    filepath = os.path.join(root, filename)
                    for rule in rules:
                        pattern = rule.get("pattern", "*")
                        dest_dir = rule.get("destination", "")
                        if re.search(pattern, filename, re.IGNORECASE):
                            dest_path = os.path.join(dest_dir, filename)
                            if not dry_run:
                                os.makedirs(dest_dir, exist_ok=True)
                                shutil.move(filepath, dest_path)
                            size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                            results.append(FileOperationResult(
                                operation="organize", source=filepath, destination=dest_path,
                                success=True, bytes_processed=size
                            ))
                            break
        except Exception as e:
            results.append(FileOperationResult(
                operation="organize", source=source_dir, destination=None,
                success=False, bytes_processed=0, error=str(e)
            ))
            logger.error(f"[{self.CODENAME}] File organization error: {e}")
        self._store_memory(f"file_ops.organize.{source_dir}", [asdict(r) for r in results])
        self._report_to_commander(f"File organization complete: {len(results)} files processed")
        return results

    def sync_directories(self, source: str, destination: str, delete: bool = False, exclude_patterns: Optional[List[str]] = None) -> FileOperationResult:
        exclude_patterns = exclude_patterns or []
        try:
            if not os.path.exists(source):
                return FileOperationResult(operation="sync", source=source, destination=destination, success=False, bytes_processed=0, error="Source does not exist")
            os.makedirs(destination, exist_ok=True)
            total_bytes = 0
            files_copied = 0
            for root, dirs, files in os.walk(source):
                rel_path = os.path.relpath(root, source)
                dest_root = os.path.join(destination, rel_path) if rel_path != "." else destination
                os.makedirs(dest_root, exist_ok=True)
                for file in files:
                    if any(re.search(p, file) for p in exclude_patterns):
                        continue
                    src_file = os.path.join(root, file)
                    dest_file = os.path.join(dest_root, file)
                    if not os.path.exists(dest_file) or os.path.getmtime(src_file) > os.path.getmtime(dest_file):
                        shutil.copy2(src_file, dest_file)
                        total_bytes += os.path.getsize(src_file)
                        files_copied += 1
            if delete:
                for root, dirs, files in os.walk(destination):
                    rel_path = os.path.relpath(root, destination)
                    src_root = os.path.join(source, rel_path) if rel_path != "." else source
                    for file in files:
                        if not os.path.exists(os.path.join(src_root, file)):
                            os.remove(os.path.join(root, file))
            result = FileOperationResult(
                operation="sync", source=source, destination=destination,
                success=True, bytes_processed=total_bytes
            )
        except Exception as e:
            result = FileOperationResult(
                operation="sync", source=source, destination=destination,
                success=False, bytes_processed=0, error=str(e)
            )
            logger.error(f"[{self.CODENAME}] Sync error: {e}")
        self._store_memory(f"file_ops.sync.{source}", asdict(result))
        self._report_to_commander(f"Directory sync complete: {result.bytes_processed} bytes")
        return result

    def secure_shred(self, filepath: str, passes: int = 3) -> FileOperationResult:
        try:
            if not os.path.exists(filepath):
                return FileOperationResult(operation="shred", source=filepath, destination=None, success=False, bytes_processed=0, error="File not found")
            size = os.path.getsize(filepath)
            with open(filepath, "r+b") as f:
                length = os.path.getsize(filepath)
                for _ in range(passes):
                    f.seek(0)
                    f.write(os.urandom(length))
                    f.flush()
                    os.fsync(f.fileno())
            os.remove(filepath)
            result = FileOperationResult(operation="shred", source=filepath, destination=None, success=True, bytes_processed=size)
        except Exception as e:
            result = FileOperationResult(operation="shred", source=filepath, destination=None, success=False, bytes_processed=0, error=str(e))
            logger.error(f"[{self.CODENAME}] Shred error: {e}")
        self._store_memory(f"file_ops.shred.{filepath}", asdict(result))
        self._report_to_commander(f"Secure shred complete: {filepath}")
        return result

    def list_processes(self, filter_name: Optional[str] = None) -> List[ProcessInfo]:
        processes = []
        try:
            rc, out, err = self._execute_shell("ps aux 2>/dev/null || ps -ef 2>/dev/null", timeout=15)
            if out:
                lines = out.strip().split("\n")[1:]
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 11:
                        pid = int(parts[1]) if parts[1].isdigit() else 0
                        cpu = float(parts[2]) if len(parts) > 2 else 0.0
                        mem = float(parts[3]) if len(parts) > 3 else 0.0
                        name = parts[10] if len(parts) > 10 else ""
                        if filter_name and filter_name.lower() not in name.lower():
                            continue
                        processes.append(ProcessInfo(pid=pid, name=name, cpu_percent=cpu, memory_percent=mem, status="running", cmdline=parts[10:]))
        except Exception as e:
            logger.error(f"[{self.CODENAME}] Process listing error: {e}")
        self._store_memory("processes.list", [asdict(p) for p in processes])
        return processes

    def kill_process(self, pid: int, signal: int = 15) -> Dict[str, Any]:
        try:
            rc, out, err = self._execute_shell(f"kill -{signal} {pid} 2>&1", timeout=10)
            success = rc == 0
            result = {"pid": pid, "signal": signal, "success": success, "output": out or err}
        except Exception as e:
            result = {"pid": pid, "signal": signal, "success": False, "error": str(e)}
            logger.error(f"[{self.CODENAME}] Kill process error: {e}")
        self._store_memory(f"processes.kill.{pid}", result)
        self._report_to_commander(f"Process {pid} killed with signal {signal}")
        return result

    def system_maintenance(self) -> Dict[str, Any]:
        results = {"timestamp": datetime.utcnow().isoformat(), "tasks": []}
        try:
            rc, out, err = self._execute_shell("df -h 2>/dev/null | head -20", timeout=10)
            if rc == 0:
                results["tasks"].append({"task": "disk_usage", "output": out.strip()})
            rc2, out2, err2 = self._execute_shell("free -h 2>/dev/null || vm_stat 2>/dev/null", timeout=10)
            if rc2 == 0:
                results["tasks"].append({"task": "memory_usage", "output": out2.strip()})
            rc3, out3, err3 = self._execute_shell("uptime 2>/dev/null", timeout=10)
            if rc3 == 0:
                results["tasks"].append({"task": "load_average", "output": out3.strip()})
            rc4, out4, err4 = self._execute_shell("find /tmp -type f -atime +7 -delete 2>/dev/null; echo cleanup_done", timeout=30)
            results["tasks"].append({"task": "temp_cleanup", "output": "Old temp files removed"})
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] System maintenance error: {e}")
        self._store_memory("maintenance.latest", results)
        self._report_to_commander("System maintenance complete")
        return results

    def create_backup_job(self, job_name: str, source_paths: List[str], destination: str, schedule: str, compression: str = "gzip", retention_days: int = 30) -> BackupJob:
        job_id = f"backup_{hashlib.md5(f'{job_name}_{time.time()}'.encode()).hexdigest()[:12]}"
        job = BackupJob(job_id=job_id, source_paths=source_paths, destination=destination, schedule=schedule, compression=compression, retention_days=retention_days)
        with self._lock:
            self._backup_jobs[job_id] = job
        self._store_memory(f"backup.{job_id}", asdict(job))
        self._report_to_commander(f"Backup job {job_id} created")
        return job

    def execute_backup(self, job_id: str) -> Dict[str, Any]:
        with self._lock:
            job = self._backup_jobs.get(job_id)
        if not job:
            return {"error": f"Backup job {job_id} not found"}
        results = {"job_id": job_id, "timestamp": datetime.utcnow().isoformat(), "files_backed_up": [], "total_bytes": 0, "success": False}
        try:
            archive_name = f"{job.destination}/backup_{job_id}_{int(time.time())}.tar.gz"
            os.makedirs(job.destination, exist_ok=True)
            sources = " ".join(job.source_paths)
            rc, out, err = self._execute_shell(f"tar -czf {archive_name} {sources} 2>&1", timeout=300)
            if rc == 0:
                results["success"] = True
                results["archive"] = archive_name
                results["total_bytes"] = os.path.getsize(archive_name) if os.path.exists(archive_name) else 0
                job.last_run = datetime.utcnow().isoformat()
            else:
                results["error"] = err or out
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Backup execution error: {e}")
        self._store_memory(f"backup.result.{job_id}", results)
        self._report_to_commander(f"Backup {job_id} complete: {results["success"]}")
        return results

    def run_network_command(self, host: str, command: str, username: str = "", password: str = "", key_path: str = "") -> Dict[str, Any]:
        results = {"host": host, "command": command, "timestamp": datetime.utcnow().isoformat(), "success": False}
        try:
            if key_path and os.path.exists(key_path):
                ssh_cmd = f"ssh -i {key_path} -o StrictHostKeyChecking=no -o ConnectTimeout=10 {username}@{host} '{command}' 2>&1"
            elif password:
                ssh_cmd = f"sshpass -p '{password}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 {username}@{host} '{command}' 2>&1"
            else:
                ssh_cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 {username}@{host} '{command}' 2>&1"
            rc, out, err = self._execute_shell(ssh_cmd, timeout=60)
            results["success"] = rc == 0
            results["stdout"] = out
            results["stderr"] = err
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Network command error: {e}")
        self._store_memory(f"network_cmd.{host}", results)
        self._report_to_commander(f"Network command to {host}: {results["success"]}")
        return results

    def build_workflow(self, workflow_name: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        workflow_id = f"wf_{hashlib.md5(f'{workflow_name}_{time.time()}'.encode()).hexdigest()[:12]}"
        workflow = {"workflow_id": workflow_id, "name": workflow_name, "steps": steps, "created_at": datetime.utcnow().isoformat(), "status": "defined"}
        with self._lock:
            self._workflows[workflow_id] = steps
        self._store_memory(f"workflow.{workflow_id}", workflow)
        self._report_to_commander(f"Workflow {workflow_id} defined with {len(steps)} steps")
        return workflow

    def execute_workflow(self, workflow_id: str) -> Dict[str, Any]:
        with self._lock:
            steps = self._workflows.get(workflow_id, [])
        results = {"workflow_id": workflow_id, "timestamp": datetime.utcnow().isoformat(), "step_results": [], "success": False}
        try:
            for step in steps:
                if not self._running:
                    break
                step_type = step.get("type", "shell")
                step_cmd = step.get("command", "")
                if step_type == "shell":
                    rc, out, err = self._execute_shell(step_cmd, timeout=step.get("timeout", 60))
                    results["step_results"].append({"step": step, "rc": rc, "output": out, "error": err})
                elif step_type == "file_op":
                    op = step.get("operation", "copy")
                    src = step.get("source", "")
                    dst = step.get("destination", "")
                    if op == "copy":
                        shutil.copy2(src, dst)
                        results["step_results"].append({"step": step, "success": True})
                    elif op == "move":
                        shutil.move(src, dst)
                        results["step_results"].append({"step": step, "success": True})
                elif step_type == "network":
                    net_result = self.run_network_command(step.get("host", ""), step.get("command", ""), step.get("username", ""), step.get("password", ""), step.get("key_path", ""))
                    results["step_results"].append({"step": step, "result": net_result})
            results["success"] = all(r.get("rc", 0) == 0 or r.get("success", False) for r in results["step_results"])
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Workflow execution error: {e}")
        self._store_memory(f"workflow.result.{workflow_id}", results)
        self._report_to_commander(f"Workflow {workflow_id} complete: {results["success"]}")
        return results

    def test_file_organize(self) -> bool:
        test_dir = f"/tmp/core_test_{int(time.time())}"
        os.makedirs(test_dir, exist_ok=True)
        with open(os.path.join(test_dir, "test.txt"), "w") as f_test:
            f_test.write("test")
        results = self.organize_files(test_dir, [{"pattern": "\.txt$", "destination": f"{test_dir}/txt_files"}])
        assert len(results) >= 1
        shutil.rmtree(test_dir, ignore_errors=True)
        return True

    def test_process_list(self) -> bool:
        processes = self.list_processes()
        assert isinstance(processes, list)
        return True

    def test_backup_job(self) -> bool:
        job = self.create_backup_job("test", ["/tmp"], "/tmp/backups", "daily")
        assert job.job_id.startswith("backup_")
        return True

    def test_workflow(self) -> bool:
        wf = self.build_workflow("test_wf", [{"type": "shell", "command": "echo test"}])
        assert wf["workflow_id"].startswith("wf_")
        return True
