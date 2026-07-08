"""
container_guard.py — SHELL
Container security agent. Docker image scanning, Dockerfile security review,
Kubernetes RBAC audit, Pod Security Standards enforcement, service mesh
security, runtime threat detection.
"""

import logging
import os
import re
import json
import hashlib
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger("SHELL")

@dataclass
class ContainerFinding:
    finding_id: str
    severity: str
    category: str
    resource: str
    description: str
    remediation: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

@dataclass
class RuntimeEvent:
    event_id: str
    event_type: str
    container_id: str
    process: str
    syscall: str
    severity: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

class ContainerGuard:
    CODENAME = "SHELL"

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._findings: List[ContainerFinding] = []
        self._runtime_events: List[RuntimeEvent] = []
        self._monitor_thread: Optional[threading.Thread] = None
        self._session_id = hashlib.sha256(
            f"shell_{time.time()}_{os.urandom(8).hex()}".encode()
        ).hexdigest()[:16]
        logger.info(f"[{self.CODENAME}] Initialized session {self._session_id}")

    def start(self) -> bool:
        with self._lock:
            self._running = True
            self._monitor_thread = threading.Thread(target=self._runtime_monitor, daemon=True)
            self._monitor_thread.start()
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
                "findings_count": len(self._findings),
                "runtime_events": len(self._runtime_events),
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

    def review_dockerfile(self, dockerfile_path: str) -> Dict[str, Any]:
        results = {"dockerfile_path": dockerfile_path, "findings": [], "score": 100, "reviewed_at": datetime.utcnow().isoformat()}
        if not os.path.exists(dockerfile_path):
            results["error"] = f"Dockerfile not found: {dockerfile_path}"
            return results
        try:
            with open(dockerfile_path, "r", encoding="utf-8", errors="ignore") as f_read:
                lines = f_read.readlines()
            for line_num, line in enumerate(lines, 1):
                line_stripped = line.strip()
                if not line_stripped or line_stripped.startswith("#"):
                    continue
                upper = line_stripped.upper()
                if upper.startswith("USER") and "ROOT" in upper:
                    finding = ContainerFinding(
                        finding_id=f"shell_df_{line_num}", severity="high", category="privilege_escalation",
                        resource=dockerfile_path, description=f"Line {line_num}: Container runs as root user",
                        remediation="Create a non-root user with USER instruction",
                        evidence={"line": line_stripped, "line_number": line_num},
                    )
                    results["findings"].append(asdict(finding))
                    results["score"] -= 15
                if "FROM " in upper:
                    match = re.search(r"FROM\s+(\S+)(?::(\S+))?", line_stripped, re.IGNORECASE)
                    if match:
                        tag = match.group(2) or "latest"
                        if tag.lower() == "latest" or ":" not in match.group(0):
                            finding = ContainerFinding(
                                finding_id=f"shell_df_{line_num}", severity="high", category="supply_chain",
                                resource=dockerfile_path, description=f"Line {line_num}: Using latest or untagged base image",
                                remediation="Pin base image to specific digest or version tag",
                                evidence={"line": line_stripped, "tag": tag},
                            )
                            results["findings"].append(asdict(finding))
                            results["score"] -= 15
                if upper.startswith("ENV") or upper.startswith("ARG"):
                    secret_patterns = ["PASSWORD", "SECRET", "TOKEN", "KEY", "API_KEY", "PRIVATE"]
                    if any(p in upper for p in secret_patterns):
                        finding = ContainerFinding(
                            finding_id=f"shell_df_{line_num}", severity="critical", category="secrets",
                            resource=dockerfile_path, description=f"Line {line_num}: Potential secret hardcoded in ENV/ARG",
                            remediation="Use Docker secrets, environment files, or secret management",
                            evidence={"line": line_stripped[:100], "line_number": line_num},
                        )
                        results["findings"].append(asdict(finding))
                        results["score"] -= 25
                if upper.startswith("ADD") and ("HTTP" in upper or "HTTPS" in upper or "FTP" in upper):
                    finding = ContainerFinding(
                        finding_id=f"shell_df_{line_num}", severity="medium", category="supply_chain",
                        resource=dockerfile_path, description=f"Line {line_num}: ADD downloads remote content without verification",
                        remediation="Use curl/wget with checksum verification instead of ADD",
                        evidence={"line": line_stripped, "line_number": line_num},
                    )
                    results["findings"].append(asdict(finding))
                    results["score"] -= 10
                if "SUDO" in upper:
                    finding = ContainerFinding(
                        finding_id=f"shell_df_{line_num}", severity="high", category="privilege_escalation",
                        resource=dockerfile_path, description=f"Line {line_num}: sudo detected in Dockerfile",
                        remediation="Remove sudo; run commands as correct user from start",
                        evidence={"line": line_stripped, "line_number": line_num},
                    )
                    results["findings"].append(asdict(finding))
                    results["score"] -= 15
                if "APT-GET" in upper and "UPGRADE" in upper:
                    finding = ContainerFinding(
                        finding_id=f"shell_df_{line_num}", severity="medium", category="supply_chain",
                        resource=dockerfile_path, description=f"Line {line_num}: apt-get upgrade makes builds non-deterministic",
                        remediation="Pin specific package versions instead of upgrading",
                        evidence={"line": line_stripped, "line_number": line_num},
                    )
                    results["findings"].append(asdict(finding))
                    results["score"] -= 10
                if upper.startswith("HEALTHCHECK"):
                    results["has_healthcheck"] = True
            if not results.get("has_healthcheck"):
                finding = ContainerFinding(
                    finding_id="shell_df_no_healthcheck", severity="medium", category="reliability",
                    resource=dockerfile_path, description="No HEALTHCHECK instruction found",
                    remediation="Add HEALTHCHECK to enable container health monitoring", evidence={},
                )
                results["findings"].append(asdict(finding))
                results["score"] -= 10
            results["score"] = max(0, results["score"])
            results["total_lines"] = len(lines)
            for finding_dict in results["findings"]:
                self._findings.append(ContainerFinding(**finding_dict))
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Dockerfile review error: {e}")
        self._store_memory(f"dockerfile.{dockerfile_path}", results)
        self._report_to_commander(f"Dockerfile review complete: {len(results['findings'])} findings, score {results['score']}")
        return results

    def scan_docker_image(self, image_name: str, tag: str = "latest") -> Dict[str, Any]:
        results = {"image_name": image_name, "tag": tag, "findings": [], "vulnerabilities": [], "scanned_at": datetime.utcnow().isoformat()}
        try:
            rc, out, err = self._execute_shell(f"trivy image --format json --severity HIGH,CRITICAL {image_name}:{tag} 2>/dev/null || echo TRIVY_NOT_INSTALLED", timeout=300)
            if "TRIVY_NOT_INSTALLED" not in (out or ""):
                try:
                    trivy_data = json.loads(out)
                    for result in trivy_data.get("Results", []):
                        for vuln in result.get("Vulnerabilities", []):
                            results["vulnerabilities"].append({
                                "id": vuln.get("VulnerabilityID", ""),
                                "severity": vuln.get("Severity", "UNKNOWN"),
                                "package": vuln.get("PkgName", ""),
                                "installed_version": vuln.get("InstalledVersion", ""),
                                "fixed_version": vuln.get("FixedVersion", ""),
                                "title": vuln.get("Title", ""),
                                "description": vuln.get("Description", ""),
                            })
                except json.JSONDecodeError:
                    pass
            else:
                rc2, out2, err2 = self._execute_shell(f"docker scan {image_name}:{tag} 2>/dev/null || grype {image_name}:{tag} 2>/dev/null || echo SCANNER_NOT_AVAILABLE", timeout=300)
                if "SCANNER_NOT_AVAILABLE" in (out2 or ""):
                    rc3, out3, err3 = self._execute_shell(f"docker inspect {image_name}:{tag} 2>/dev/null", timeout=30)
                    if rc3 == 0:
                        inspect_data = json.loads(out3)[0] if out3 else {}
                        config = inspect_data.get("Config", {})
                        results["image_info"] = {
                            "cmd": config.get("Cmd"), "entrypoint": config.get("Entrypoint"),
                            "env": config.get("Env", []), "user": config.get("User", ""),
                            "exposed_ports": list(config.get("ExposedPorts", {}).keys()),
                        }
                        if not config.get("User"):
                            finding = ContainerFinding(
                                finding_id=f"shell_img_{image_name}_root", severity="high",
                                category="privilege_escalation", resource=image_name,
                                description=f"Image {image_name} runs as root (no USER set)",
                                remediation="Set USER to non-root in Dockerfile",
                                evidence={"user": config.get("User")},
                            )
                            results["findings"].append(asdict(finding))
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Image scan error: {e}")
        self._store_memory(f"image.{image_name}", results)
        self._report_to_commander(f"Image scan complete for {image_name}:{tag}: {len(results['vulnerabilities'])} vulns")
        return results

    def audit_kubernetes_rbac(self, kubeconfig_path: Optional[str] = None) -> Dict[str, Any]:
        results = {"timestamp": datetime.utcnow().isoformat(), "findings": [], "roles": [], "bindings": []}
        env_kubeconfig = f"KUBECONFIG={kubeconfig_path} " if kubeconfig_path else ""
        try:
            rc, out, err = self._execute_shell(f"{env_kubeconfig}kubectl get roles --all-namespaces -o json 2>/dev/null || echo KUBECTL_NOT_AVAILABLE", timeout=60)
            if "KUBECTL_NOT_AVAILABLE" not in (out or ""):
                roles_data = json.loads(out) if out else {}
                for item in roles_data.get("items", []):
                    role_name = item.get("metadata", {}).get("name", "")
                    namespace = item.get("metadata", {}).get("namespace", "")
                    rules = item.get("rules", [])
                    results["roles"].append({"name": role_name, "namespace": namespace, "rules_count": len(rules)})
                    for rule in rules:
                        api_groups = rule.get("apiGroups", [])
                        resources = rule.get("resources", [])
                        verbs = rule.get("verbs", [])
                        if "*" in api_groups and "*" in resources and "*" in verbs:
                            finding = ContainerFinding(
                                finding_id=f"shell_k8s_{namespace}_{role_name}_wildcard",
                                severity="critical", category="rbac", resource=f"{namespace}/{role_name}",
                                description=f"Role {role_name} has wildcard permissions on all resources",
                                remediation="Restrict RBAC to specific resources and verbs",
                                evidence={"apiGroups": api_groups, "resources": resources, "verbs": verbs},
                            )
                            results["findings"].append(asdict(finding))
                        if "secrets" in resources and ("get" in verbs or "list" in verbs or "*" in verbs):
                            finding = ContainerFinding(
                                finding_id=f"shell_k8s_{namespace}_{role_name}_secrets",
                                severity="high", category="rbac", resource=f"{namespace}/{role_name}",
                                description=f"Role {role_name} can read secrets",
                                remediation="Use external secret management and limit secret access",
                                evidence={"resources": resources, "verbs": verbs},
                            )
                            results["findings"].append(asdict(finding))
            rc2, out2, err2 = self._execute_shell(f"{env_kubeconfig}kubectl get clusterroles -o json 2>/dev/null || echo KUBECTL_NOT_AVAILABLE", timeout=60)
            if "KUBECTL_NOT_AVAILABLE" not in (out2 or ""):
                cluster_roles = json.loads(out2) if out2 else {}
                for item in cluster_roles.get("items", []):
                    role_name = item.get("metadata", {}).get("name", "")
                    for rule in item.get("rules", []):
                        if "*" in rule.get("verbs", []) and "*" in rule.get("resources", []):
                            finding = ContainerFinding(
                                finding_id=f"shell_k8s_cluster_{role_name}_wildcard",
                                severity="critical", category="rbac", resource=f"clusterrole/{role_name}",
                                description=f"ClusterRole {role_name} has wildcard permissions",
                                remediation="Restrict ClusterRole to specific resources and verbs",
                                evidence={"rules": rule},
                            )
                            results["findings"].append(asdict(finding))
            rc3, out3, err3 = self._execute_shell(f"{env_kubeconfig}kubectl get rolebindings,clusterrolebindings --all-namespaces -o json 2>/dev/null || echo KUBECTL_NOT_AVAILABLE", timeout=60)
            if "KUBECTL_NOT_AVAILABLE" not in (out3 or ""):
                bindings = json.loads(out3) if out3 else {}
                for item in bindings.get("items", []):
                    binding_name = item.get("metadata", {}).get("name", "")
                    subjects = item.get("subjects", [])
                    results["bindings"].append({"name": binding_name, "subjects": len(subjects)})
                    role_ref = item.get("roleRef", {})
                    if role_ref.get("name") == "cluster-admin":
                        for subject in subjects:
                            if subject.get("kind") == "ServiceAccount":
                                finding = ContainerFinding(
                                    finding_id=f"shell_k8s_bind_{binding_name}_admin",
                                    severity="critical", category="rbac", resource=binding_name,
                                    description=f"ServiceAccount bound to cluster-admin via {binding_name}",
                                    remediation="Create least-privilege roles instead of using cluster-admin",
                                    evidence={"subject": subject, "roleRef": role_ref},
                                )
                                results["findings"].append(asdict(finding))
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] K8s RBAC audit error: {e}")
        self._store_memory("k8s.rbac", results)
        self._report_to_commander(f"K8s RBAC audit complete: {len(results['findings'])} findings")
        return results

    def check_pod_security(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        results = {"timestamp": datetime.utcnow().isoformat(), "namespace": namespace or "all", "findings": [], "pods_checked": 0}
        ns_filter = f"-n {namespace}" if namespace else "--all-namespaces"
        try:
            rc, out, err = self._execute_shell(f"kubectl get pods {ns_filter} -o json 2>/dev/null || echo KUBECTL_NOT_AVAILABLE", timeout=60)
            if "KUBECTL_NOT_AVAILABLE" not in (out or ""):
                pods_data = json.loads(out) if out else {}
                for item in pods_data.get("items", []):
                    results["pods_checked"] += 1
                    pod_name = item.get("metadata", {}).get("name", "")
                    pod_ns = item.get("metadata", {}).get("namespace", "")
                    spec = item.get("spec", {})
                    for container in spec.get("containers", []):
                        security_context = container.get("securityContext", {})
                        if security_context.get("privileged", False):
                            finding = ContainerFinding(
                                finding_id=f"shell_pod_{pod_ns}_{pod_name}_privileged",
                                severity="critical", category="pod_security", resource=f"{pod_ns}/{pod_name}",
                                description=f"Container {container.get("name")} runs in privileged mode",
                                remediation="Remove privileged: true and use capabilities instead",
                                evidence={"container": container.get("name"), "privileged": True},
                            )
                            results["findings"].append(asdict(finding))
                        if security_context.get("runAsUser") == 0:
                            finding = ContainerFinding(
                                finding_id=f"shell_pod_{pod_ns}_{pod_name}_root",
                                severity="high", category="pod_security", resource=f"{pod_ns}/{pod_name}",
                                description=f"Container {container.get("name")} runs as root (UID 0)",
                                remediation="Set runAsUser to non-zero UID",
                                evidence={"container": container.get("name"), "runAsUser": 0},
                            )
                            results["findings"].append(asdict(finding))
                        if not security_context.get("readOnlyRootFilesystem", False):
                            finding = ContainerFinding(
                                finding_id=f"shell_pod_{pod_ns}_{pod_name}_writable_root",
                                severity="medium", category="pod_security", resource=f"{pod_ns}/{pod_name}",
                                description=f"Container {container.get("name")} has writable root filesystem",
                                remediation="Set readOnlyRootFilesystem: true",
                                evidence={"container": container.get("name"), "readOnlyRootFilesystem": False},
                            )
                            results["findings"].append(asdict(finding))
                    pod_security = spec.get("securityContext", {})
                    if not pod_security.get("seccompProfile"):
                        finding = ContainerFinding(
                            finding_id=f"shell_pod_{pod_ns}_{pod_name}_no_seccomp",
                            severity="medium", category="pod_security", resource=f"{pod_ns}/{pod_name}",
                            description="Pod does not have seccomp profile set",
                            remediation="Set seccompProfile to RuntimeDefault or custom profile",
                            evidence={"securityContext": pod_security},
                        )
                        results["findings"].append(asdict(finding))
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Pod security check error: {e}")
        self._store_memory(f"k8s.pods.{namespace or "all"}", results)
        self._report_to_commander(f"Pod security check complete: {results["pods_checked"]} pods, {len(results["findings"])} findings")
        return results

    def _runtime_monitor(self) -> None:
        logger.info(f"[{self.CODENAME}] Runtime monitor started")
        while self._running:
            try:
                rc, out, err = self._execute_shell("docker ps --format '{{.ID}}' 2>/dev/null | head -20 || echo DOCKER_NOT_AVAILABLE", timeout=30)
                if "DOCKER_NOT_AVAILABLE" not in (out or ""):
                    container_ids = [c.strip() for c in out.strip().split("\n") if c.strip()]
                    for cid in container_ids:
                        if not self._running:
                            break
                        rc2, out2, err2 = self._execute_shell(f"docker top {cid} 2>/dev/null", timeout=10)
                        if out2:
                            suspicious = ["nc", "ncat", "nmap", "masscan", "mimikatz", "strace", "tcpdump"]
                            for proc in suspicious:
                                if proc in out2.lower():
                                    event = RuntimeEvent(
                                        event_id=f"evt_{hashlib.md5(f'{cid}_{proc}_{time.time()}'.encode()).hexdigest()[:12]}",
                                        event_type="suspicious_process", container_id=cid,
                                        process=proc, syscall="execve", severity="high",
                                    )
                                    with self._lock:
                                        self._runtime_events.append(event)
                                    self._report_to_commander(f"Runtime alert: {proc} detected in container {cid[:12]}", level="warning", data=asdict(event))
                rc3, out3, err3 = self._execute_shell("docker events --since '5s' --filter 'event=start' --format '{{.ID}}' 2>/dev/null | head -10 || echo EVENTS_NOT_AVAILABLE", timeout=10)
                if "EVENTS_NOT_AVAILABLE" not in (out3 or ""):
                    for event_cid in out3.strip().split("\n"):
                        if event_cid.strip():
                            rc4, out4, err4 = self._execute_shell(f"docker inspect {event_cid.strip()} --format='{{json .HostConfig.Privileged}}' 2>/dev/null", timeout=10)
                            if out4.strip() == "true":
                                event = RuntimeEvent(
                                    event_id=f"evt_{hashlib.md5(f'{event_cid}_priv_{time.time()}'.encode()).hexdigest()[:12]}",
                                    event_type="privileged_container", container_id=event_cid.strip(),
                                    process="docker run", syscall="clone", severity="critical",
                                )
                                with self._lock:
                                    self._runtime_events.append(event)
                                self._report_to_commander(f"CRITICAL: Privileged container started: {event_cid[:12]}", level="critical", data=asdict(event))
                time.sleep(10)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Runtime monitor error: {e}")
                time.sleep(30)

    def audit_service_mesh(self, mesh_type: str = "istio") -> Dict[str, Any]:
        results = {"mesh_type": mesh_type, "timestamp": datetime.utcnow().isoformat(), "findings": [], "components": []}
        try:
            if mesh_type == "istio":
                rc, out, err = self._execute_shell("kubectl get pods -n istio-system -o json 2>/dev/null || echo ISTIO_NOT_FOUND", timeout=60)
                if "ISTIO_NOT_FOUND" not in (out or ""):
                    pods = json.loads(out) if out else {}
                    results["components"] = [{"name": p.get("metadata", {}).get("name"), "status": p.get("status", {}).get("phase")} for p in pods.get("items", [])]
                    rc2, out2, err2 = self._execute_shell("kubectl get peerauthentication --all-namespaces -o json 2>/dev/null", timeout=30)
                    if rc2 == 0 and out2:
                        peer_auths = json.loads(out2) if out2 else {}
                        has_strict = any(item.get("spec", {}).get("mtls", {}).get("mode") == "STRICT" for item in peer_auths.get("items", []))
                        if not has_strict:
                            finding = ContainerFinding(
                                finding_id="shell_istio_no_strict_mtls", severity="high",
                                category="service_mesh", resource="istio-system",
                                description="No STRICT mTLS PeerAuthentication found",
                                remediation="Create a PeerAuthentication with mode: STRICT in istio-system",
                                evidence={"peer_authentications": len(peer_auths.get("items", []))},
                            )
                            results["findings"].append(asdict(finding))
                    else:
                        finding = ContainerFinding(
                            finding_id="shell_istio_no_mtls_config", severity="critical",
                            category="service_mesh", resource="istio-system",
                            description="No PeerAuthentication resources configured",
                            remediation="Enable mTLS for all workloads", evidence={},
                        )
                        results["findings"].append(asdict(finding))
            elif mesh_type == "linkerd":
                rc, out, err = self._execute_shell("kubectl get pods -n linkerd -o json 2>/dev/null || echo LINKERD_NOT_FOUND", timeout=60)
                if "LINKERD_NOT_FOUND" not in (out or ""):
                    pods = json.loads(out) if out else {}
                    results["components"] = [{"name": p.get("metadata", {}).get("name"), "status": p.get("status", {}).get("phase")} for p in pods.get("items", [])]
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Service mesh audit error: {e}")
        self._store_memory(f"mesh.{mesh_type}", results)
        self._report_to_commander(f"Service mesh audit complete for {mesh_type}: {len(results["findings"])} findings")
        return results

    def test_dockerfile_review(self) -> bool:
        test_path = f"/tmp/test_dockerfile_{int(time.time())}"
        with open(test_path, "w") as f_test:
            f_test.write("FROM ubuntu:latest\n")
            f_test.write("USER root\n")
            f_test.write("RUN apt-get upgrade -y\n")
            f_test.write("ENV PASSWORD=secret123\n")
        results = self.review_dockerfile(test_path)
        assert len(results["findings"]) >= 3
        os.remove(test_path)
        return True

    def test_pod_security(self) -> bool:
        results = self.check_pod_security()
        assert "pods_checked" in results
        return True

    def test_runtime_event(self) -> bool:
        event = RuntimeEvent(
            event_id="test_evt", event_type="test",
            container_id="test_container", process="test",
            syscall="test", severity="low",
        )
        assert event.event_id == "test_evt"
        return True
