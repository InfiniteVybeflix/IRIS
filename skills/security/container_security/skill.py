"""Container Security Skill — Docker/K8s security scanning and hardening."""

import re
import logging
import subprocess
from typing import Dict, Any, List
from skills import BaseSkill

logger = logging.getLogger(__name__)


class ContainerSecuritySkill(BaseSkill):
    """Docker and Kubernetes security scanning and hardening."""

    def __init__(self):
        super().__init__(name="container_security", category="security", capabilities=["container_security"])

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "scan_image")
        if method == "scan_image":
            return self.scan_image(params)
        elif method == "audit_k8s":
            return self.audit_k8s(params)
        elif method == "check_dockerfile":
            return self.check_dockerfile(params)
        return {"error": f"Unknown method: {method}"}

    def scan_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        image = params.get("image", "")
        if not image:
            return {"success": False, "error": "No image provided"}
        vulnerabilities = []
        # Try trivy first
        try:
            result = subprocess.run(["trivy", "image", "--severity", "HIGH,CRITICAL", "--format", "json", image], capture_output=True, text=True, timeout=300)
            if result.returncode in (0, 1):
                import json
                report = json.loads(result.stdout)
                for result_item in report.get("Results", []):
                    for vuln in result_item.get("Vulnerabilities", []):
                        vulnerabilities.append({"id": vuln.get("VulnerabilityID", ""), "severity": vuln.get("Severity", ""), "package": vuln.get("PkgName", ""), "installed": vuln.get("InstalledVersion", ""), "fixed": vuln.get("FixedVersion", ""), "title": vuln.get("Title", "")})
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        # Fallback to docker scout if available
        if not vulnerabilities:
            try:
                result = subprocess.run(["docker", "scout", "cves", "--format", "json", image], capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    import json
                    report = json.loads(result.stdout)
                    for vuln in report.get("vulnerabilities", []):
                        vulnerabilities.append({"id": vuln.get("id", ""), "severity": vuln.get("severity", ""), "package": vuln.get("package", ""), "title": vuln.get("title", "")})
            except (FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired):
                pass
        return {"success": True, "image": image, "scanner": "trivy/docker_scout", "vulnerabilities": vulnerabilities, "critical": len([v for v in vulnerabilities if v.get("severity") == "CRITICAL"]), "high": len([v for v in vulnerabilities if v.get("severity") == "HIGH"])}

    def audit_k8s(self, params: Dict[str, Any]) -> Dict[str, Any]:
        namespace = params.get("namespace", "default")
        findings = []
        try:
            # Check privileged pods
            result = subprocess.run(["kubectl", "get", "pods", "-n", namespace, "-o", "json"], capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                import json
                pods = json.loads(result.stdout)
                for pod in pods.get("items", []):
                    pod_name = pod["metadata"]["name"]
                    for container in pod.get("spec", {}).get("containers", []):
                        sec = container.get("securityContext", {})
                        if sec.get("privileged", False):
                            findings.append({"severity": "critical", "resource": f"pod/{pod_name}", "container": container["name"], "issue": "Container running as privileged"})
                        if not sec.get("readOnlyRootFilesystem", False):
                            findings.append({"severity": "medium", "resource": f"pod/{pod_name}", "container": container["name"], "issue": "readOnlyRootFilesystem not set"})
                        if not sec.get("runAsNonRoot", False):
                            findings.append({"severity": "medium", "resource": f"pod/{pod_name}", "container": container["name"], "issue": "runAsNonRoot not set"})
        except FileNotFoundError:
            findings.append({"severity": "info", "issue": "kubectl not found"})
        except Exception as e:
            findings.append({"severity": "info", "issue": f"K8s audit error: {e}"})
        return {"success": True, "namespace": namespace, "findings": findings, "finding_count": len(findings)}

    def check_dockerfile(self, params: Dict[str, Any]) -> Dict[str, Any]:
        dockerfile = params.get("dockerfile", "")
        dockerfile_path = params.get("dockerfile_path", "")
        if dockerfile_path and not dockerfile:
            try:
                with open(dockerfile_path, 'r') as f:
                    dockerfile = f.read()
            except Exception as e:
                return {"success": False, "error": str(e)}
        if not dockerfile:
            return {"success": False, "error": "No Dockerfile provided"}
        issues = []
        lines = dockerfile.split("\n")
        # Check FROM tag
        from_lines = [l for l in lines if l.strip().startswith("FROM")]
        for line in from_lines:
            if ":latest" in line or (":" not in line.split()[-1] and "AS" not in line):
                issues.append({"severity": "medium", "line": line.strip(), "message": "Avoid 'latest' tag or missing explicit version in FROM", "rule": "DL3007"})
        # Check USER
        has_user = any(l.strip().startswith("USER") and "root" not in l.lower() for l in lines)
        if not has_user:
            issues.append({"severity": "high", "message": "No non-root USER instruction found", "rule": "DL3002"})
        # Check secrets
        for line in lines:
            if re.search(r'(password|secret|token|key)\s*=\s*["\'][^"\']+["\']', line, re.IGNORECASE):
                issues.append({"severity": "critical", "line": line.strip(), "message": "Potential secret hardcoded in Dockerfile", "rule": "secrets_exposure"})
        # Check ADD vs COPY
        add_lines = [l for l in lines if l.strip().startswith("ADD") and not any(url in l for url in ["http://", "https://", "git@"])]
        for line in add_lines:
            issues.append({"severity": "low", "line": line.strip(), "message": "Use COPY instead of ADD for local files", "rule": "DL3020"})
        # Healthcheck
        if not any(l.strip().startswith("HEALTHCHECK") for l in lines):
            issues.append({"severity": "low", "message": "HEALTHCHECK instruction not found", "rule": "DL4006"})
        return {"success": True, "issues": issues, "total_lines": len(lines), "recommendations": ["Use specific version tags", "Create non-root USER", "Use COPY instead of ADD", "Add HEALTHCHECK", "Use multi-stage builds", "Scan with trivy before deployment"]}
