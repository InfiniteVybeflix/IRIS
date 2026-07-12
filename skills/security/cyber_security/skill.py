"""IRIS v7 Cyber Security Skill — Cyber Warfare & Defense"""
import logging
import re
import socket
import ssl
import subprocess
import threading
import time
import json
import hashlib
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class CyberSecuritySkill(BaseSkill):
    name = "cyber_security"
    display_name = "Cyber Security"
    description = "Comprehensive cybersecurity engine — vulnerability assessment, penetration testing, system hardening, incident response, threat intelligence, and compliance auditing."
    version = "7.0.0"
    category = "security"
    icon = "🛡️"
    uses_storage = True
    storage_dir = "data/skills/cyber_security"
    storage_file = "data/skills/cyber_security/storage.json"
    supports_background = True
    background_interval_seconds = 300

    capabilities = [
        SkillCapability(name="scan_vulnerabilities", description="Scan web apps for OWASP Top 10 vulnerabilities", input_schema={"target": "str", "scan_type": "str"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="check_ssl", description="Analyze SSL/TLS configuration", input_schema={"hostname": "str", "port": "int"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="check_headers", description="Check security headers", input_schema={"url": "str"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="port_scan", description="Network port scanning", input_schema={"target": "str", "ports": "list"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="check_password_strength", description="Analyze password strength", input_schema={"password": "str"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="generate_cve_report", description="Lookup CVE details", input_schema={"cve_id": "str"}, tags=[CapabilityTags.RESEARCH]),
        SkillCapability(name="check_compliance", description="Check compliance frameworks", input_schema={"framework": "str", "config": "dict"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="analyze_threat", description="Analyze IP/file/domain reputation", input_schema={"indicator": "str", "type": "str"}, tags=[CapabilityTags.RESEARCH]),
        SkillCapability(name="create_incident_response", description="Generate incident response playbook", input_schema={"incident_type": "str"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="harden_system", description="Generate system hardening recommendations", input_schema={"os_type": "str", "services": "list"}, tags=[CapabilityTags.TRUST_SAFETY]),
    ]

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._scan_cache: Dict[str, Any] = {}
        self._threat_cache: Dict[str, Any] = {}
        self._load_cache()

    def _load_cache(self):
        data = self._read_storage()
        self._scan_cache = data.get("scan_cache", {})
        self._threat_cache = data.get("threat_cache", {})

    def _save_cache(self):
        self._write_storage({"scan_cache": self._scan_cache, "threat_cache": self._threat_cache})

    def execute(self, request: SkillRequest) -> SkillResult:
        intent = request.intent.lower()
        params = request.params

        try:
            if intent in ("scan_vulnerabilities", "vuln_scan"):
                return self._scan_vulnerabilities(params.get("target"), params.get("scan_type", "full"))
            elif intent in ("check_ssl", "ssl_scan"):
                return self._check_ssl(params.get("hostname"), params.get("port", 443))
            elif intent in ("check_headers", "headers"):
                return self._check_headers(params.get("url"))
            elif intent in ("port_scan", "scan_ports"):
                return self._port_scan(params.get("target"), params.get("ports", [80, 443, 22, 21, 3306, 5432, 6379, 8080]))
            elif intent in ("check_password_strength", "password_check"):
                return self._check_password_strength(params.get("password"))
            elif intent in ("generate_cve_report", "cve_lookup"):
                return self._cve_lookup(params.get("cve_id"))
            elif intent in ("check_compliance", "compliance"):
                return self._check_compliance(params.get("framework", "owasp"), params.get("config", {}))
            elif intent in ("analyze_threat", "threat_intel"):
                return self._analyze_threat(params.get("indicator"), params.get("type", "ip"))
            elif intent in ("create_incident_response", "incident_response"):
                return self._incident_response(params.get("incident_type", "breach"))
            elif intent in ("harden_system", "system_hardening"):
                return self._harden_system(params.get("os_type", "linux"), params.get("services", []))
            else:
                return SkillResult.fail(error=f"Unknown intent: {intent}")
        except Exception as e:
            logger.exception(f"CyberSecurity execution error: {e}")
            return SkillResult.fail(error=str(e))

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        keywords = ["security", "vuln", "scan", "pentest", "ssl", "cve", "exploit", "threat", "harden", "incident", "forensic", "compliance", "gdpr", "hipaa", "nist", "owasp", "password", "port", "firewall", "malware", "phishing"]
        if any(k in intent for k in keywords):
            return 0.9
        return super().can_handle(request)

    def _scan_vulnerabilities(self, target: str, scan_type: str) -> SkillResult:
        if not target:
            return SkillResult.fail(error="No target provided")
        findings = []
        url = target if target.startswith("http") else f"http://{target}"

        # SQLi detection
        sqli_payloads = ["\'", "\";--", "\' OR \'1\'=\'1", "\"; DROP TABLE"]
        for payload in sqli_payloads:
            try:
                test_url = f"{url}?id={payload}"
                req = urllib.request.Request(test_url, headers={"User-Agent": "IRIS-Security-Scanner/7.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = resp.read().decode("utf-8", errors="ignore").lower()
                    if any(err in body for err in ["sql", "mysql", "sqlite", "syntax error", "unexpected"]):
                        findings.append({"severity": "CRITICAL", "type": "SQL Injection", "evidence": f"Payload triggered DB error: {payload[:30]}", "remediation": "Use parameterized queries and ORM. Validate all inputs."})
                        break
            except Exception:
                pass

        # XSS detection
        xss_payload = "<script>alert(1)</script>"
        try:
            test_url = f"{url}?q={xss_payload}"
            req = urllib.request.Request(test_url, headers={"User-Agent": "IRIS-Security-Scanner/7.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                if xss_payload in body:
                    findings.append({"severity": "HIGH", "type": "Reflected XSS", "evidence": "Payload reflected in response", "remediation": "Encode all output. Use Content-Security-Policy. Implement XSS filters."})
        except Exception:
            pass

        # IDOR detection
        try:
            req1 = urllib.request.Request(f"{url}?id=1", headers={"User-Agent": "IRIS-Security-Scanner/7.0"})
            req2 = urllib.request.Request(f"{url}?id=2", headers={"User-Agent": "IRIS-Security-Scanner/7.0"})
            with urllib.request.urlopen(req1, timeout=10) as r1, urllib.request.urlopen(req2, timeout=10) as r2:
                if r1.read() != r2.read() and r1.getcode() == 200:
                    findings.append({"severity": "HIGH", "type": "IDOR", "evidence": "Different IDs return different resources without auth check", "remediation": "Implement authorization checks on every resource access."})
        except Exception:
            pass

        # Security headers
        headers_result = self._check_headers(url)
        if headers_result.success:
            findings.extend(headers_result.data.get("missing", []))

        result = {"target": target, "scan_type": scan_type, "findings": findings, "risk_score": self._calculate_risk(findings), "timestamp": datetime.now().isoformat()}
        self._scan_cache[target] = result
        self._save_cache()
        return SkillResult.ok(message=f"Vulnerability scan complete. {len(findings)} findings.", data=result)

    def _check_ssl(self, hostname: str, port: int = 443) -> SkillResult:
        if not hostname:
            return SkillResult.fail(error="No hostname provided")
        findings = []
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()

                    if version in ("TLSv1", "TLSv1.1"):
                        findings.append({"severity": "HIGH", "issue": f"Deprecated TLS version: {version}", "fix": "Upgrade to TLS 1.2 minimum, preferably TLS 1.3"})
                    if cipher and "NULL" in cipher[0]:
                        findings.append({"severity": "CRITICAL", "issue": "NULL cipher detected", "fix": "Disable NULL ciphers immediately"})

                    cert_not_after = cert.get("notAfter")
                    if cert_not_after:
                        expiry = datetime.strptime(cert_not_after, "%b %d %H:%M:%S %Y %Z")
                        days_until = (expiry - datetime.now()).days
                        if days_until < 30:
                            findings.append({"severity": "MEDIUM", "issue": f"Certificate expires in {days_until} days", "fix": "Renew SSL certificate"})
                        if days_until < 0:
                            findings.append({"severity": "CRITICAL", "issue": "Certificate EXPIRED", "fix": "Renew SSL certificate immediately"})

                    result = {"hostname": hostname, "port": port, "tls_version": version, "cipher": cipher[0] if cipher else "unknown", "cert_expiry_days": days_until if cert_not_after else None, "findings": findings, "grade": "A" if not findings else "F" if any(f["severity"] == "CRITICAL" for f in findings) else "C"}
                    return SkillResult.ok(message=f"SSL analysis complete. Grade: {result['grade']}", data=result)
        except ssl.SSLError as e:
            return SkillResult.ok(message="SSL analysis found issues", data={"hostname": hostname, "findings": [{"severity": "HIGH", "issue": f"SSL Error: {e}", "fix": "Fix SSL configuration"}]})
        except Exception as e:
            return SkillResult.fail(error=f"SSL check failed: {e}")

    def _check_headers(self, url: str) -> SkillResult:
        if not url:
            return SkillResult.fail(error="No URL provided")
        required = {"Strict-Transport-Security": "Enforces HTTPS", "Content-Security-Policy": "Prevents XSS/injection", "X-Frame-Options": "Prevents clickjacking", "X-Content-Type-Options": "Prevents MIME sniffing", "Referrer-Policy": "Controls referrer info", "Permissions-Policy": "Restricts browser features"}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "IRIS-Security-Scanner/7.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                headers = {k.lower(): v for k, v in resp.headers.items()}
                missing = [{"severity": "MEDIUM", "type": "Missing Security Header", "header": h, "description": desc, "remediation": f"Add {h} header"} for h, desc in required.items() if h.lower() not in headers]
                cookie_issues = []
                if "set-cookie" in headers:
                    cookie = headers["set-cookie"]
                    if "secure" not in cookie.lower():
                        cookie_issues.append({"severity": "MEDIUM", "type": "Insecure Cookie", "issue": "Missing Secure flag", "remediation": "Set Secure attribute on all cookies"})
                    if "httponly" not in cookie.lower():
                        cookie_issues.append({"severity": "MEDIUM", "type": "Insecure Cookie", "issue": "Missing HttpOnly flag", "remediation": "Set HttpOnly attribute on all cookies"})
                return SkillResult.ok(message=f"Header check: {len(missing)} missing, {len(cookie_issues)} cookie issues", data={"url": url, "missing": missing, "cookie_issues": cookie_issues, "present": list(headers.keys())})
        except Exception as e:
            return SkillResult.fail(error=f"Header check failed: {e}")

    def _port_scan(self, target: str, ports: List[int]) -> SkillResult:
        open_ports = []
        for port in ports:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex((target, port))
                    if result == 0:
                        service = self._identify_service(port)
                        risk = "HIGH" if port in [21, 23, 3389, 5900] else "MEDIUM" if port in [80, 443, 8080] else "LOW"
                        open_ports.append({"port": port, "service": service, "risk": risk})
            except Exception:
                pass
        return SkillResult.ok(message=f"Port scan: {len(open_ports)} open ports found", data={"target": target, "open_ports": open_ports, "total_scanned": len(ports)})

    def _identify_service(self, port: int) -> str:
        services = {21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP", 443: "HTTPS", 3306: "MySQL", 5432: "PostgreSQL", 6379: "Redis", 8080: "HTTP-ALT", 3389: "RDP", 5900: "VNC"}
        return services.get(port, "UNKNOWN")

    def _check_password_strength(self, password: str) -> SkillResult:
        if not password:
            return SkillResult.fail(error="No password provided")
        score = 0
        checks = {
            "length_12": len(password) >= 12,
            "has_upper": bool(re.search(r"[A-Z]", password)),
            "has_lower": bool(re.search(r"[a-z]", password)),
            "has_digit": bool(re.search(r"\d", password)),
            "has_special": bool(re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"|,.<>/?]", password)),
            "no_common": password.lower() not in ["password", "123456", "qwerty", "admin", "letmein"],
            "no_repeats": not re.search(r"(.)\1{2,}", password),
        }
        score = sum(1 for v in checks.values() if v)
        strength = "STRONG" if score >= 6 else "MODERATE" if score >= 4 else "WEAK"
        time_to_crack = self._estimate_crack_time(password)
        return SkillResult.ok(message=f"Password strength: {strength} ({score}/7)", data={"strength": strength, "score": score, "checks": checks, "estimated_crack_time": time_to_crack})

    def _estimate_crack_time(self, password: str) -> str:
        charset = 0
        if re.search(r"[a-z]", password): charset += 26
        if re.search(r"[A-Z]", password): charset += 26
        if re.search(r"\d", password): charset += 10
        if re.search(r"[^a-zA-Z0-9]", password): charset += 32
        combinations = charset ** len(password) if charset else 0
        seconds = combinations / 1e10 if combinations else float("inf")
        if seconds < 1: return "Instant"
        elif seconds < 60: return f"{seconds:.1f} seconds"
        elif seconds < 3600: return f"{seconds/60:.1f} minutes"
        elif seconds < 86400: return f"{seconds/3600:.1f} hours"
        elif seconds < 31536000: return f"{seconds/86400:.1f} days"
        elif seconds < 3153600000: return f"{seconds/31536000:.1f} years"
        else: return "Centuries"

    def _cve_lookup(self, cve_id: str) -> SkillResult:
        if not cve_id:
            return SkillResult.fail(error="No CVE ID provided")
        try:
            url = f"https://cve.circl.lu/api/cve/{cve_id}"
            req = urllib.request.Request(url, headers={"User-Agent": "IRIS-Security/7.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                result = {"cve_id": cve_id, "summary": data.get("summary", "N/A"), "cvss": data.get("cvss", "N/A"), "references": data.get("references", [])[:5], "published": data.get("Published", "N/A"), "last_modified": data.get("last-modified", "N/A")}
                return SkillResult.ok(message=f"CVE {cve_id}: CVSS {result['cvss']}", data=result)
        except Exception as e:
            return SkillResult.ok(message=f"CVE lookup (offline mode)", data={"cve_id": cve_id, "summary": "CVE data unavailable offline", "cvss": "unknown", "note": f"Error: {e}"})

    def _check_compliance(self, framework: str, config: Dict) -> SkillResult:
        frameworks = {
            "owasp": {"name": "OWASP Top 10", "controls": ["A01: Broken Access Control", "A02: Cryptographic Failures", "A03: Injection", "A04: Insecure Design", "A05: Security Misconfiguration", "A06: Vulnerable Components", "A07: Auth Failures", "A08: Data Integrity Failures", "A09: Logging Failures", "A10: SSRF"]},
            "gdpr": {"name": "GDPR", "controls": ["Lawful processing", "Data minimization", "Right to erasure", "Data portability", "Privacy by design", "Breach notification", "DPO appointment"]},
            "hipaa": {"name": "HIPAA", "controls": ["Access controls", "Audit controls", "Integrity controls", "Transmission security", "Breach notification"]},
            "pci": {"name": "PCI-DSS", "controls": ["Firewall config", "No default passwords", "Protect stored data", "Encrypt transmission", "Anti-virus", "Secure systems", "Restrict access", "Unique IDs", "Physical access", "Monitor networks", "Regular testing", "Info security policy"]},
            "nist": {"name": "NIST CSF", "controls": ["Identify", "Protect", "Detect", "Respond", "Recover"]},
        }
        fw = frameworks.get(framework.lower(), frameworks["owasp"])
        result = {"framework": fw["name"], "controls": fw["controls"], "compliance_score": "manual_review_required", "recommendations": [f"Implement {c}" for c in fw["controls"][:3]]}
        return SkillResult.ok(message=f"{fw['name']} compliance check: {len(fw['controls'])} controls defined", data=result)

    def _analyze_threat(self, indicator: str, indicator_type: str) -> SkillResult:
        if not indicator:
            return SkillResult.fail(error="No indicator provided")
        result = {"indicator": indicator, "type": indicator_type, "reputation": "unknown", "first_seen": "N/A", "last_seen": "N/A", "related": [], "recommendation": "Monitor traffic. Block if malicious activity confirmed."}
        if indicator_type == "ip":
            # Check private ranges
            private_patterns = [r"^10\.", r"^172\.(1[6-9]|2[0-9]|3[01])\.", r"^192\.168\.", r"^127\."]
            if any(re.match(p, indicator) for p in private_patterns):
                result["reputation"] = "private_range"
                result["recommendation"] = "Private IP — check internal security controls"
        elif indicator_type == "domain":
            suspicious_tlds = [".tk", ".ml", ".ga", ".cf", ".top", ".xyz"]
            if any(indicator.endswith(t) for t in suspicious_tlds):
                result["reputation"] = "suspicious_tld"
                result["recommendation"] = "Suspicious TLD — verify legitimacy"
        return SkillResult.ok(message=f"Threat analysis for {indicator}: {result['reputation']}", data=result)

    def _incident_response(self, incident_type: str) -> SkillResult:
        playbooks = {
            "breach": {"steps": ["1. Identify and contain the breach", "2. Preserve evidence (logs, disk images)", "3. Notify stakeholders within 72h (GDPR)", "4. Engage forensic team", "5. Remediate vulnerabilities", "6. Document lessons learned"], "severity": "CRITICAL"},
            "malware": {"steps": ["1. Isolate infected systems", "2. Identify malware family via hash/sandbox", "3. Remove malware and clean systems", "4. Patch exploited vulnerabilities", "5. Restore from clean backups", "6. Monitor for persistence"], "severity": "HIGH"},
            "ddos": {"steps": ["1. Activate DDoS mitigation (Cloudflare/AWS Shield)", "2. Scale infrastructure", "3. Identify attack source/type", "4. Contact ISP/upstream", "5. Document and report"], "severity": "HIGH"},
            "insider": {"steps": ["1. Restrict user access immediately", "2. Preserve audit logs", "3. Assess data exposure scope", "4. Legal/HR engagement", "5. Forensic analysis of user activity"], "severity": "HIGH"},
            "ransomware": {"steps": ["1. ISOLATE immediately (disconnect network)", "2. DO NOT PAY — contact authorities", "3. Identify ransomware variant", "4. Restore from offline backups", "5. Patch entry vector", "6. Report to FBI/CISA"], "severity": "CRITICAL"},
        }
        playbook = playbooks.get(incident_type.lower(), playbooks["breach"])
        return SkillResult.ok(message=f"Incident response playbook ({playbook['severity']}): {len(playbook['steps'])} steps", data={"incident_type": incident_type, **playbook})

    def _harden_system(self, os_type: str, services: List[str]) -> SkillResult:
        recommendations = []
        if os_type.lower() in ("linux", "ubuntu", "debian", "centos"):
            recommendations = [
                "Disable root SSH login (PermitRootLogin no)",
                "Use key-based auth only (PasswordAuthentication no)",
                "Enable UFW/Firewalld (deny all, allow specific)",
                "Install fail2ban for brute force protection",
                "Enable automatic security updates",
                "Configure auditd for system auditing",
                "Set sysctl: net.ipv4.icmp_echo_ignore_broadcasts=1",
                "Disable unused services (systemctl mask)",
                "Enable AppArmor/SELinux enforcing mode",
                "Configure logrotate and remote syslog",
            ]
        elif os_type.lower() in ("windows", "win"):
            recommendations = [
                "Enable Windows Defender + ASR rules",
                "Configure AppLocker/WDAC policies",
                "Enable PowerShell Constrained Language Mode",
                "Disable SMBv1 protocol",
                "Enable Credential Guard + Device Guard",
                "Configure Windows Firewall (advanced)",
                "Enable advanced audit policies",
                "Apply EMET/Exploit Protection settings",
                "Implement LAPS for local admin passwords",
                "Enable BitLocker full disk encryption",
            ]
        for svc in services:
            recommendations.append(f"Harden {svc}: use latest version, disable default accounts, enable logging")
        return SkillResult.ok(message=f"{os_type} hardening: {len(recommendations)} recommendations", data={"os_type": os_type, "services": services, "recommendations": recommendations})

    def _calculate_risk(self, findings: List[Dict]) -> int:
        scores = {"CRITICAL": 10, "HIGH": 7, "MEDIUM": 4, "LOW": 1}
        return min(100, sum(scores.get(f.get("severity", "LOW"), 1) for f in findings))

    def background_tick(self):
        return []
