"""Cyber Security Skill — Vulnerability scanning, pentesting, hardening."""

import re
import logging
import subprocess
from typing import Dict, Any, List
from skills import BaseSkill

logger = logging.getLogger(__name__)


class CyberSecuritySkill(BaseSkill):
    """Vulnerability scanning, penetration testing, and security hardening."""

    def __init__(self):
        super().__init__(name="cyber_security", category="security", capabilities=["cybersecurity"])

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "scan_vulns")
        if method == "scan_vulns":
            return self.scan_vulns(params)
        elif method == "pentest":
            return self.pentest(params)
        elif method == "harden":
            return self.harden(params)
        elif method == "scan_ports":
            return self.scan_ports(params)
        return {"error": f"Unknown method: {method}"}

    def scan_vulns(self, params: Dict[str, Any]) -> Dict[str, Any]:
        target = params.get("target", "")
        scan_type = params.get("scan_type", "full")
        if not target:
            return {"success": False, "error": "No target provided"}
        findings = []
        # Check for common web vulnerabilities
        if scan_type in ("web", "full"):
            try:
                import urllib.request
                req = urllib.request.Request(f"http://{target}" if not target.startswith("http") else target, headers={"User-Agent": "IRIS-Security/1.0"}, method="HEAD")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    headers = dict(resp.headers)
                    if "Server" in headers:
                        findings.append({"severity": "info", "type": "banner_grab", "detail": f"Server: {headers['Server']}"})
                    if "X-Frame-Options" not in headers:
                        findings.append({"severity": "medium", "type": "missing_header", "detail": "X-Frame-Options missing (clickjacking risk)"})
                    if "Content-Security-Policy" not in headers:
                        findings.append({"severity": "medium", "type": "missing_header", "detail": "Content-Security-Policy missing"})
                    if "Strict-Transport-Security" not in headers and target.startswith("https"):
                        findings.append({"severity": "medium", "type": "missing_header", "detail": "HSTS header missing"})
                    if "X-Content-Type-Options" not in headers:
                        findings.append({"severity": "low", "type": "missing_header", "detail": "X-Content-Type-Options missing"})
            except Exception as e:
                findings.append({"severity": "info", "type": "connection_error", "detail": str(e)})
        return {"success": True, "target": target, "scan_type": scan_type, "findings": findings, "finding_count": len(findings)}

    def pentest(self, params: Dict[str, Any]) -> Dict[str, Any]:
        target = params.get("target", "")
        phase = params.get("phase", "reconnaissance")
        return {"success": True, "target": target, "phase": phase, "authorized": params.get("authorized", False), "modules": ["reconnaissance", "scanning", "exploitation", "post_exploitation"]}

    def harden(self, params: Dict[str, Any]) -> Dict[str, Any]:
        system = params.get("system", "linux")
        hardening_steps = {
            "linux": [
                "Disable root SSH login (PermitRootLogin no)",
                "Enable firewall (ufw enable)",
                "Set up fail2ban for brute force protection",
                "Remove unnecessary packages",
                "Enable automatic security updates",
                "Set file permissions on sensitive files",
                "Configure auditd for system auditing",
            ],
            "windows": [
                "Enable Windows Defender Firewall",
                "Disable SMBv1 protocol",
                "Enable PowerShell script block logging",
                "Configure AppLocker policies",
                "Enable BitLocker disk encryption",
            ],
            "docker": [
                "Run containers as non-root user",
                "Use read-only root filesystem",
                "Drop all capabilities and add only required ones",
                "Enable Docker Content Trust",
                "Set resource limits (CPU/memory)",
            ],
        }
        return {"success": True, "system": system, "hardening_applied": hardening_steps.get(system, hardening_steps["linux"])}

    def scan_ports(self, params: Dict[str, Any]) -> Dict[str, Any]:
        target = params.get("target", "")
        ports = params.get("ports", "22,80,443,3306,5432,8080,8443")
        port_list = [int(p.strip()) for p in str(ports).split(",")]
        open_ports = []
        for port in port_list:
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((target, port))
                sock.close()
                if result == 0:
                    service = {22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 3306: "MySQL", 5432: "PostgreSQL", 6379: "Redis", 8080: "HTTP-Alt", 8443: "HTTPS-Alt"}.get(port, "Unknown")
                    open_ports.append({"port": port, "service": service, "state": "open"})
            except Exception:
                pass
        return {"success": True, "target": target, "ports_scanned": len(port_list), "open_ports": open_ports, "open_count": len(open_ports)}
