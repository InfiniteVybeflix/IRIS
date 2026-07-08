"""
IRIS v7.0 — Uptime Monitor

Service availability monitoring for HTTP endpoints, TCP ports,
DNS resolution, and SSL certificate health.

Dependencies:
    - requests
    - Standard library (socket, ssl, datetime)

Safety:
    - Read-only health checks.
    - No modifications to monitored services.

Usage:
    from senses.uptime_monitor import UptimeMonitor
    monitor = UptimeMonitor()
    monitor.start()
"""

from __future__ import annotations

import logging
import socket
import ssl
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from .base_sense import BaseSense

logger = logging.getLogger(__name__)


class UptimeMonitor(BaseSense):
    """
    Service availability and health monitoring sense.

    Monitors HTTP endpoints, TCP ports, DNS resolution,
    and SSL certificate expiry.

    Attributes:
        name: "uptime_monitor"
        interval: 60 seconds
        thresholds: Alert thresholds.
    """

    name: str = "uptime_monitor"
    interval: int = 60
    thresholds: Dict[str, Any] = {
        "response_time_ms": 5000,
        "cert_expiry_days": 30,
        "downtime_count_threshold": 3,
    }

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._monitored_urls: List[str] = []
        self._monitored_tcp: List[Dict[str, Any]] = []
        self._monitored_dns: List[str] = []
        self._monitored_certs: List[str] = []
        self._downtime_counts: Dict[str, int] = {}
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "IRIS-v7.0/Uptime-Monitor"})
        self._session.verify = True

    def add_http_target(self, url: str) -> None:
        safe_url = self.sanitize_input(url)
        self._monitored_urls.append(safe_url)
        self._downtime_counts[safe_url] = 0
        logger.info(f"Added HTTP target: {safe_url}")

    def add_tcp_target(self, host: str, port: int) -> None:
        safe_host = self.sanitize_input(host)
        target = {"host": safe_host, "port": port}
        self._monitored_tcp.append(target)
        self._downtime_counts[f"{safe_host}:{port}"] = 0
        logger.info(f"Added TCP target: {safe_host}:{port}")

    def add_dns_target(self, domain: str) -> None:
        safe_domain = self.sanitize_input(domain)
        self._monitored_dns.append(safe_domain)
        self._downtime_counts[f"dns:{safe_domain}"] = 0
        logger.info(f"Added DNS target: {safe_domain}")

    def add_cert_target(self, domain: str) -> None:
        safe_domain = self.sanitize_input(domain)
        self._monitored_certs.append(safe_domain)
        logger.info(f"Added cert target: {safe_domain}")

    def _sense(self) -> Dict[str, Any]:
        findings: Dict[str, Any] = {"http": [], "tcp": [], "dns": [], "cert": []}

        for url in self._monitored_urls:
            try:
                start = datetime.now(timezone.utc)
                resp = self._session.get(url, timeout=30)
                elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
                status = {"url": url, "status_code": resp.status_code, "response_time_ms": elapsed_ms, "up": resp.status_code < 400, "ssl_valid": url.startswith("https") and resp.status_code < 400}
                if status["up"]:
                    self._downtime_counts[url] = 0
                else:
                    self._downtime_counts[url] += 1
                findings["http"].append(status)
            except Exception as exc:
                self._downtime_counts[url] += 1
                findings["http"].append({"url": url, "status_code": None, "response_time_ms": None, "up": False, "error": str(exc)})

        for target in self._monitored_tcp:
            try:
                sock = socket.create_connection((target["host"], target["port"]), timeout=10)
                sock.close()
                self._downtime_counts[f"{target['host']}:{target['port']}"] = 0
                findings["tcp"].append({"host": target["host"], "port": target["port"], "up": True})
            except Exception as exc:
                key = f"{target['host']}:{target['port']}"
                self._downtime_counts[key] += 1
                findings["tcp"].append({"host": target["host"], "port": target["port"], "up": False, "error": str(exc)})

        for domain in self._monitored_dns:
            try:
                ip = socket.gethostbyname(domain)
                self._downtime_counts[f"dns:{domain}"] = 0
                findings["dns"].append({"domain": domain, "resolved_ip": ip, "up": True})
            except Exception as exc:
                self._downtime_counts[f"dns:{domain}"] += 1
                findings["dns"].append({"domain": domain, "resolved_ip": None, "up": False, "error": str(exc)})

        for domain in self._monitored_certs:
            try:
                context = ssl.create_default_context()
                with socket.create_connection((domain, 443), timeout=10) as sock:
                    with context.wrap_socket(sock, server_hostname=domain) as ssock:
                        cert = ssock.getpeercert()
                        expiry = cert.get("notAfter")
                        if expiry:
                            expiry_date = datetime.strptime(expiry, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                            days_until = (expiry_date - datetime.now(timezone.utc)).days
                            findings["cert"].append({"domain": domain, "expiry_date": expiry_date.isoformat(), "days_until_expiry": days_until, "issuer": cert.get("issuer"), "up": True})
                        else:
                            findings["cert"].append({"domain": domain, "expiry_date": None, "error": "No expiry date", "up": False})
            except Exception as exc:
                findings["cert"].append({"domain": domain, "up": False, "error": str(exc)})

        return findings

    def _should_alert(self, result: Dict[str, Any]) -> bool:
        if not result.get("success"):
            return True
        output = result.get("output", {})
        for http in output.get("http", []):
            if not http.get("up") and self._downtime_counts.get(http["url"], 0) >= self.thresholds.get("downtime_count_threshold", 3):
                return True
            if http.get("response_time_ms", 0) > self.thresholds.get("response_time_ms", 5000):
                return True
        for tcp in output.get("tcp", []):
            if not tcp.get("up") and self._downtime_counts.get(f"{tcp['host']}:{tcp['port']}", 0) >= self.thresholds.get("downtime_count_threshold", 3):
                return True
        for dns in output.get("dns", []):
            if not dns.get("up") and self._downtime_counts.get(f"dns:{dns['domain']}", 0) >= self.thresholds.get("downtime_count_threshold", 3):
                return True
        for cert in output.get("cert", []):
            if cert.get("days_until_expiry", 999) < self.thresholds.get("cert_expiry_days", 30):
                return True
        return False

    def _emit_alert(self, result: Dict[str, Any]) -> None:
        alert = {"type": "uptime_alert", "sense": self.name, "severity": "high", "message": "Service health issue detected", "data": result.get("output", {})}
        self.report(alert)

    def check_http(self, url: str, timeout: int = 30) -> Dict[str, Any]:
        self._begin_check()
        try:
            safe_url = self.sanitize_input(url)
            start = datetime.now(timezone.utc)
            resp = self._session.get(safe_url, timeout=timeout)
            elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            res = self._build_result(success=resp.status_code < 400, action="check_http", output=resp.text[:1000], parsed={"url": safe_url, "status_code": resp.status_code, "response_time_ms": elapsed_ms, "headers": dict(resp.headers)}, errors=[] if resp.status_code < 400 else [f"HTTP {resp.status_code}"])
            self.last_result = res
            self._end_check(success=res["success"])
            return res
        except Exception as exc:
            logger.exception("UptimeMonitor check_http failed")
            res = self._build_result(success=False, action="check_http", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def check_tcp(self, host: str, port: int, timeout: int = 10) -> Dict[str, Any]:
        self._begin_check()
        try:
            safe_host = self.sanitize_input(host)
            sock = socket.create_connection((safe_host, port), timeout=timeout)
            sock.close()
            res = self._build_result(success=True, action="check_tcp", output=f"Connected to {safe_host}:{port}", parsed={"host": safe_host, "port": port, "reachable": True})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("UptimeMonitor check_tcp failed")
            res = self._build_result(success=False, action="check_tcp", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def check_dns(self, domain: str) -> Dict[str, Any]:
        self._begin_check()
        try:
            safe_domain = self.sanitize_input(domain)
            ip = socket.gethostbyname(safe_domain)
            res = self._build_result(success=True, action="check_dns", output=ip, parsed={"domain": safe_domain, "resolved_ip": ip})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("UptimeMonitor check_dns failed")
            res = self._build_result(success=False, action="check_dns", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def check_certificate(self, domain: str) -> Dict[str, Any]:
        self._begin_check()
        try:
            safe_domain = self.sanitize_input(domain)
            context = ssl.create_default_context()
            with socket.create_connection((safe_domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=safe_domain) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    expiry = cert.get("notAfter")
                    expiry_date = datetime.strptime(expiry, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                    days_until = (expiry_date - datetime.now(timezone.utc)).days
                    res = self._build_result(success=True, action="check_certificate", output=cert, parsed={"domain": safe_domain, "expiry_date": expiry_date.isoformat(), "days_until_expiry": days_until, "issuer": cert.get("issuer"), "subject": cert.get("subject"), "cipher": cipher})
                    self.last_result = res
                    self._end_check(success=True)
                    return res
        except Exception as exc:
            logger.exception("UptimeMonitor check_certificate failed")
            res = self._build_result(success=False, action="check_certificate", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res


__all__ = ["UptimeMonitor"]
