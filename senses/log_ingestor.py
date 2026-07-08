"""
IRIS v7.0 — Log Ingestor

Stream and parse logs from services. Detects brute force attacks,
privilege escalation attempts, and unusual error patterns.

Dependencies:
    - Standard library only

Safety:
    - Read-only log tailing.
    - No log modification.

Usage:
    from senses.log_ingestor import LogIngestor
    ingestor = LogIngestor()
    ingestor.tail_log("/var/log/auth.log")
"""

from __future__ import annotations

import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base_sense import BaseSense

logger = logging.getLogger(__name__)


class LogIngestor(BaseSense):
    """
    Log streaming and security event detection sense.

    Tails log files, parses syslog and web server formats,
    and detects brute force, privilege escalation, and error anomalies.

    Attributes:
        name: "log_ingestor"
        interval: 5 seconds
        thresholds: Alert thresholds.
    """

    name: str = "log_ingestor"
    interval: int = 5
    thresholds: Dict[str, Any] = {
        "brute_force_threshold": 5,
        "privilege_escalation_threshold": 3,
        "error_burst_threshold": 50,
    }

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._watched_files: Dict[str, int] = {}
        self._failed_logins: Dict[str, List[str]] = defaultdict(list)
        self._sudo_attempts: Dict[str, int] = defaultdict(int)
        self._error_counts: Dict[str, int] = defaultdict(int)

    def _sense(self) -> Dict[str, Any]:
        """
        Check all watched log files for new events.

        Returns:
            Dictionary with parsed events and detected anomalies.
        """
        findings: Dict[str, Any] = {
            "events": [],
            "brute_force_alerts": [],
            "privilege_escalation_alerts": [],
            "error_bursts": [],
        }

        for filepath, last_pos in list(self._watched_files.items()):
            if not os.path.exists(filepath):
                continue
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(last_pos)
                    new_lines = f.readlines()
                    self._watched_files[filepath] = f.tell()

                for line in new_lines:
                    line = line.strip()
                    if not line:
                        continue

                    parsed = self._parse_line(line, filepath)
                    if parsed:
                        findings["events"].append(parsed)

                        if parsed.get("type") == "failed_login":
                            src = parsed.get("source_ip", "unknown")
                            self._failed_logins[src].append(parsed.get("timestamp", ""))
                            if len(self._failed_logins[src]) > self.thresholds.get("brute_force_threshold", 5):
                                findings["brute_force_alerts"].append({"source_ip": src, "failed_count": len(self._failed_logins[src]), "severity": "high"})
                                self._failed_logins[src] = []

                        if parsed.get("type") == "sudo_attempt":
                            user = parsed.get("user", "unknown")
                            self._sudo_attempts[user] += 1
                            if self._sudo_attempts[user] > self.thresholds.get("privilege_escalation_threshold", 3):
                                findings["privilege_escalation_alerts"].append({"user": user, "sudo_count": self._sudo_attempts[user], "severity": "medium"})

                        if parsed.get("type") == "error":
                            service = parsed.get("service", "unknown")
                            self._error_counts[service] += 1
                            if self._error_counts[service] > self.thresholds.get("error_burst_threshold", 50):
                                findings["error_bursts"].append({"service": service, "error_count": self._error_counts[service], "severity": "medium"})

            except Exception as exc:
                logger.error(f"Log read error for {filepath}: {exc}")

        return findings

    def _parse_line(self, line: str, filepath: str) -> Optional[Dict[str, Any]]:
        """Parse a single log line into a structured event."""
        auth_match = re.match(r"^(\w+\s+\d+\s+\d+:\d+:\d+)\s+\S+\s+sshd\[\d+\]:\s+(\w+).*?(\d+\.\d+\.\d+\.\d+)?", line)
        if auth_match:
            action = auth_match.group(2).lower()
            ip = auth_match.group(3)
            if "failed" in action or "invalid" in action:
                return {"type": "failed_login", "timestamp": auth_match.group(1), "service": "ssh", "source_ip": ip, "raw": line}
            if "accepted" in action:
                return {"type": "successful_login", "timestamp": auth_match.group(1), "service": "ssh", "source_ip": ip, "raw": line}

        sudo_match = re.match(r"^(\w+\s+\d+\s+\d+:\d+:\d+)\s+\S+\s+sudo\[\d+\]:\s+(\w+).*", line)
        if sudo_match:
            return {"type": "sudo_attempt", "timestamp": sudo_match.group(1), "user": sudo_match.group(2), "raw": line}

        error_match = re.match(r"^(\[.*?\])\s+\[(\w+)\].*?error", line)
        if error_match:
            return {"type": "error", "timestamp": error_match.group(1).strip("[]"), "service": "web_server", "level": error_match.group(2), "raw": line}

        if "error" in line.lower() or "exception" in line.lower() or "fatal" in line.lower():
            return {"type": "error", "timestamp": datetime.now(timezone.utc).isoformat(), "service": "unknown", "raw": line[:500]}

        return None

    def tail_log(self, filepath: str) -> Dict[str, Any]:
        """Start tailing a log file."""
        self._begin_check()
        try:
            safe_path = os.path.abspath(os.path.expanduser(filepath))
            if not os.path.exists(safe_path):
                res = self._build_result(success=False, action="tail_log", errors=[f"File not found: {safe_path}"])
                self.last_result = res
                self._end_check(success=False)
                return res

            self._watched_files[safe_path] = os.path.getsize(safe_path)
            res = self._build_result(success=True, action="tail_log", output=f"Now tailing {safe_path}", parsed={"filepath": safe_path, "start_position": self._watched_files[safe_path]})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("LogIngestor tail_log failed")
            res = self._build_result(success=False, action="tail_log", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def parse_syslog(self, filepath: str) -> Dict[str, Any]:
        """Parse a syslog file into structured events."""
        self._begin_check()
        try:
            safe_path = os.path.abspath(os.path.expanduser(filepath))
            events: List[Dict[str, Any]] = []
            with open(safe_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parsed = self._parse_line(line.strip(), safe_path)
                    if parsed:
                        events.append(parsed)
            res = self._build_result(success=True, action="parse_syslog", output=events, parsed={"event_count": len(events), "events": events})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("LogIngestor parse_syslog failed")
            res = self._build_result(success=False, action="parse_syslog", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def parse_apache_nginx(self, filepath: str) -> Dict[str, Any]:
        """Parse Apache/Nginx access logs into structured events."""
        self._begin_check()
        try:
            safe_path = os.path.abspath(os.path.expanduser(filepath))
            pattern = re.compile(r'^(\S+)\s+\S+\s+\S+\s+\[(.*?)\]\s+"(\S+)\s+(.*?)\s+HTTP/\d\.\d"\s+(\d{3})\s+(\S+)')
            events: List[Dict[str, Any]] = []
            with open(safe_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    match = pattern.match(line.strip())
                    if match:
                        events.append({"source_ip": match.group(1), "timestamp": match.group(2), "method": match.group(3), "path": match.group(4), "status_code": int(match.group(5)), "bytes_sent": match.group(6) if match.group(6) != "-" else 0})
            res = self._build_result(success=True, action="parse_apache_nginx", output=events, parsed={"event_count": len(events), "events": events})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("LogIngestor parse_apache_nginx failed")
            res = self._build_result(success=False, action="parse_apache_nginx", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def detect_brute_force(self, filepath: Optional[str] = None) -> Dict[str, Any]:
        """Explicitly scan for brute force attack patterns."""
        self._begin_check()
        try:
            if filepath:
                safe_path = os.path.abspath(os.path.expanduser(filepath))
                with open(safe_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            else:
                lines = []
                for fp in self._watched_files:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        lines.extend(f.readlines())

            ip_failures: Dict[str, int] = defaultdict(int)
            for line in lines:
                if "failed" in line.lower() or "invalid" in line.lower():
                    ip_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
                    if ip_match:
                        ip_failures[ip_match.group(1)] += 1

            alerts = [{"source_ip": ip, "failed_count": count, "severity": "high"} for ip, count in ip_failures.items() if count > self.thresholds.get("brute_force_threshold", 5)]
            res = self._build_result(success=True, action="detect_brute_force", output=alerts, parsed={"alert_count": len(alerts), "alerts": alerts})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("LogIngestor detect_brute_force failed")
            res = self._build_result(success=False, action="detect_brute_force", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def detect_privilege_escalation(self, filepath: Optional[str] = None) -> Dict[str, Any]:
        """Explicitly scan for privilege escalation patterns."""
        self._begin_check()
        try:
            if filepath:
                safe_path = os.path.abspath(os.path.expanduser(filepath))
                with open(safe_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            else:
                lines = []
                for fp in self._watched_files:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        lines.extend(f.readlines())

            user_sudo: Dict[str, int] = defaultdict(int)
            for line in lines:
                if "sudo" in line.lower():
                    user_match = re.search(r"user=(\w+)", line)
                    if user_match:
                        user_sudo[user_match.group(1)] += 1

            alerts = [{"user": user, "sudo_count": count, "severity": "medium"} for user, count in user_sudo.items() if count > self.thresholds.get("privilege_escalation_threshold", 3)]
            res = self._build_result(success=True, action="detect_privilege_escalation", output=alerts, parsed={"alert_count": len(alerts), "alerts": alerts})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("LogIngestor detect_privilege_escalation failed")
            res = self._build_result(success=False, action="detect_privilege_escalation", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def _should_alert(self, result: Dict[str, Any]) -> bool:
        if not result.get("success"):
            return True
        output = result.get("output", {})
        if output.get("brute_force_alerts"):
            return True
        if output.get("privilege_escalation_alerts"):
            return True
        if output.get("error_bursts"):
            return True
        return False

    def _emit_alert(self, result: Dict[str, Any]) -> None:
        alert = {"type": "log_alert", "sense": self.name, "severity": "high" if result.get("output", {}).get("brute_force_alerts") else "medium", "message": "Log anomaly detected", "data": result.get("output", {})}
        self.report(alert)


__all__ = ["LogIngestor"]
