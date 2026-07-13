"""
IRIS v1.0 — Docker Engine

Docker container control, inspection, vulnerability scanning (Trivy),
and CIS Docker benchmark security checks.

Dependencies: docker
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class DockerEngine(BaseTool):
    """Docker container management and security analysis."""

    name: str = "docker_engine"
    category: str = "container"
    dependencies: List[str] = ["docker"]

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import docker
                self._client = docker.from_env()
            except Exception as exc:
                raise RuntimeError(f"Docker connection failed: {exc}")
        return self._client

    def _run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {}

    def list_containers(self, all_containers: bool = True) -> Dict[str, Any]:
        self._begin_execution()
        try:
            client = self._get_client()
            containers = client.containers.list(all=all_containers)
            data = [{"id": c.id, "name": c.name, "image": c.image.tags[0] if c.image.tags else c.image.id,
                "status": c.status, "state": c.attrs.get("State", {}), "ports": c.ports, "created": c.attrs.get("Created")}
                for c in containers]
            res = self._build_result(success=True, action="list_containers", output=data,
                parsed={"container_count": len(data), "running": len([c for c in data if c["status"] == "running"]), "containers": data})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("list_containers failed")
            res = self._build_result(success=False, action="list_containers", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def inspect_container(self, cid: str) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_cid = self.sanitize_input(cid)
            client = self._get_client()
            container = client.containers.get(safe_cid)
            attrs = container.attrs
            res = self._build_result(success=True, action="inspect_container", output=attrs,
                parsed={"id": attrs.get("Id"), "name": attrs.get("Name"), "image": attrs.get("Config", {}).get("Image"),
                    "cmd": attrs.get("Config", {}).get("Cmd"), "env": attrs.get("Config", {}).get("Env"),
                    "labels": attrs.get("Config", {}).get("Labels"), "network_mode": attrs.get("HostConfig", {}).get("NetworkMode"),
                    "privileged": attrs.get("HostConfig", {}).get("Privileged", False), "mounts": attrs.get("Mounts"),
                    "health": attrs.get("State", {}).get("Health", {})})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("inspect_container failed")
            res = self._build_result(success=False, action="inspect_container", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def scan_image(self, image: str) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_image = self.sanitize_input(image)
            findings: List[Dict[str, Any]] = []
            scanner_used = "none"
            import shutil
            if shutil.which("trivy"):
                scanner_used = "trivy"
                cmd = ["trivy", "image", "--format", "json", "-o", "/tmp/trivy_iris.json", safe_image]
                result = self._run_subprocess(cmd, timeout=600)
                if result.returncode == 0 and os.path.exists("/tmp/trivy_iris.json"):
                    with open("/tmp/trivy_iris.json") as f:
                        trivy_data = json.load(f)
                    for result_item in trivy_data.get("Results", []):
                        for vuln in result_item.get("Vulnerabilities", []):
                            findings.append({"vulnerability_id": vuln.get("VulnerabilityID"), "severity": vuln.get("Severity"),
                                "package": vuln.get("PkgName"), "installed_version": vuln.get("InstalledVersion"), "fixed_version": vuln.get("FixedVersion")})
            if not findings:
                scanner_used = "docker_history"
                client = self._get_client()
                img = client.images.get(safe_image)
                for layer in img.history():
                    if layer.get("Size", 0) > 100 * 1024 * 1024:
                        findings.append({"type": "large_layer", "size_mb": layer.get("Size", 0) / (1024 * 1024), "created_by": layer.get("CreatedBy", "")})
            severity_counts: Dict[str, int] = {}
            for f in findings:
                sev = f.get("severity", "unknown")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
            res = self._build_result(success=True, action="scan_image", output=findings,
                parsed={"image": safe_image, "scanner": scanner_used, "vulnerability_count": len(findings), "severity_breakdown": severity_counts, "findings": findings})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("scan_image failed")
            res = self._build_result(success=False, action="scan_image", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def check_security(self, cid: str) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_cid = self.sanitize_input(cid)
            client = self._get_client()
            container = client.containers.get(safe_cid)
            attrs = container.attrs
            host_config = attrs.get("HostConfig", {})
            config = attrs.get("Config", {})
            checks: List[Dict[str, Any]] = []
            checks.append({"check": "privileged_mode", "status": "fail" if host_config.get("Privileged", False) else "pass",
                "description": "Container should not run in privileged mode"})
            checks.append({"check": "read_only_rootfs", "status": "pass" if host_config.get("ReadonlyRootfs", False) else "fail",
                "description": "Container root filesystem should be read-only"})
            cap_drop = host_config.get("CapDrop", [])
            checks.append({"check": "cap_drop_all", "status": "pass" if "ALL" in cap_drop else "fail",
                "description": "All capabilities should be dropped"})
            checks.append({"check": "no_new_privileges", "status": "pass" if host_config.get("SecurityOpt", []) and "no-new-privileges" in str(host_config.get("SecurityOpt", [])) else "fail",
                "description": "Container should not gain new privileges"})
            env_vars = config.get("Env", []) or []
            secret_patterns = ["PASSWORD", "SECRET", "TOKEN", "API_KEY", "PRIVATE_KEY"]
            exposed = [e for e in env_vars if any(p in e for p in secret_patterns)]
            checks.append({"check": "secrets_in_env", "status": "fail" if exposed else "pass",
                "description": "No secrets should be exposed in environment variables", "evidence": exposed})
            passed = sum(1 for c in checks if c["status"] == "pass")
            res = self._build_result(success=True, action="check_security", output=checks,
                parsed={"container": safe_cid, "total_checks": len(checks), "passed": passed, "failed": len(checks) - passed, "checks": checks})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("check_security failed")
            res = self._build_result(success=False, action="check_security", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def exec_command(self, cid: str, command: str) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_cid = self.sanitize_input(cid)
            safe_cmd = self.sanitize_input(command)
            client = self._get_client()
            container = client.containers.get(safe_cid)
            exit_code, output = container.exec_run(safe_cmd)
            res = self._build_result(success=exit_code == 0, action="exec_command",
                output=output.decode("utf-8", errors="replace") if isinstance(output, bytes) else output,
                parsed={"container": safe_cid, "command": safe_cmd, "exit_code": exit_code},
                errors=[] if exit_code == 0 else [f"Exit code: {exit_code}"])
            self.last_result = res
            self._end_execution(exit_code == 0)
            return res
        except Exception as exc:
            logger.exception("exec_command failed")
            res = self._build_result(success=False, action="exec_command", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def get_logs(self, cid: str, tail: int = 100) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_cid = self.sanitize_input(cid)
            client = self._get_client()
            container = client.containers.get(safe_cid)
            logs = container.logs(tail=tail, timestamps=True)
            res = self._build_result(success=True, action="get_logs",
                output=logs.decode("utf-8", errors="replace") if isinstance(logs, bytes) else logs,
                parsed={"container": safe_cid, "tail": tail, "log_length": len(logs)})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("get_logs failed")
            res = self._build_result(success=False, action="get_logs", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res


__all__ = ["DockerEngine"]
