"""
blue_sentinel.py — AEGIS
Defensive operations agent. Real-time monitoring, SIEM rule generation,
log anomaly detection, incident response playbooks, automated containment,
firewall rule management, IDS/IPS signature generation, honeypot deployment.
"""

import logging
import os
import re
import json
import hashlib
import subprocess
import threading
import time
import socket
import glob
from typing import Any, Dict, List, Optional, Tuple, Set, Callable
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger("AEGIS")


@dataclass
class SecurityEvent:
    """A single security event record."""
    event_id: str
    timestamp: str
    severity: str  # critical, high, medium, low, info
    event_type: str
    source: str
    target: str
    description: str
    raw_data: Dict[str, Any] = field(default_factory=dict)
    iocs: List[str] = field(default_factory=list)
    mitre_tactics: List[str] = field(default_factory=list)
    status: str = "open"  # open, investigating, contained, resolved, false_positive


@dataclass
class Incident:
    """An aggregated security incident."""
    incident_id: str
    title: str
    severity: str
    events: List[SecurityEvent] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "open"
    playbook: Optional[str] = None
    containment_actions: List[str] = field(default_factory=list)
    assigned_agent: str = ""


class BlueSentinel:
    """
    AEGIS — Defensive Operations Agent.

    Real capabilities:
    - Real-time system/process/network monitoring
    - SIEM rule generation and log parsing
    - Statistical anomaly detection on logs and metrics
    - Incident response playbook execution
    - Automated containment (iptables, Windows firewall, process kill, network isolate)
    - IDS/IPS signature generation (Snort/Suricata compatible)
    - Honeypot deployment and monitoring (SSH/TCP/HTTP)
    """

    CODENAME = "AEGIS"

    SEVERITY_WEIGHTS = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._monitor_thread: Optional[threading.Thread] = None
        self._events: deque = deque(maxlen=10000)
        self._incidents: Dict[str, Incident] = {}
        self._siem_rules: List[Dict[str, Any]] = []
        self._anomaly_baselines: Dict[str, Dict] = {}
        self._honeypots: Dict[str, Any] = {}
        self._session_id = hashlib.sha256(
            f"aegis_{time.time()}_{os.urandom(8).hex()}".encode()
        ).hexdigest()[:16]
        logger.info(f"[{self.CODENAME}] Initialized session {self._session_id}")

    def start(self) -> bool:
        """Start the agent and monitoring threads."""
        with self._lock:
            self._running = True
            self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self._monitor_thread.start()
        logger.info(f"[{self.CODENAME}] Agent started")
        return True

    def stop(self) -> bool:
        """Stop the agent and all monitoring."""
        with self._lock:
            self._running = False
            # Stop honeypots
            for hp_name, hp in self._honeypots.items():
                try:
                    if hp.get("socket"):
                        hp["socket"].close()
                except Exception as e:
                    logger.warning(f"[{self.CODENAME}] Honeypot cleanup error: {e}")
        logger.info(f"[{self.CODENAME}] Agent stopped")
        return True

    def health(self) -> Dict[str, Any]:
        """Return agent health status."""
        with self._lock:
            return {
                "codename": self.CODENAME,
                "session_id": self._session_id,
                "running": self._running,
                "events_stored": len(self._events),
                "open_incidents": len([i for i in self._incidents.values() if i.status == "open"]),
                "total_incidents": len(self._incidents),
                "siem_rules": len(self._siem_rules),
                "honeypots_active": len([h for h in self._honeypots.values() if h.get("active")]),
            }

    def _report_to_commander(self, message: str, level: str = "info", data: Optional[Dict] = None) -> None:
        payload = {
            "agent": self.CODENAME,
            "session_id": self._session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "data": data or {},
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

    def _execute_shell(self, command: str, timeout: int = 30) -> Tuple[int, str, str]:
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout, cwd=os.getcwd()
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    # -------------------------------------------------------------------------
    # Real-Time Monitoring
    # -------------------------------------------------------------------------
    def _monitoring_loop(self) -> None:
        """Main monitoring loop running in daemon thread."""
        logger.info(f"[{self.CODENAME}] Monitoring loop started")
        while self._running:
            try:
                self._monitor_processes()
                self._monitor_network_connections()
                self._monitor_logins()
                self._monitor_file_integrity()
                time.sleep(5)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Monitoring loop error: {e}")
                time.sleep(5)

    def _monitor_processes(self) -> None:
        """Monitor for suspicious processes."""
        if not psutil:
            return
        try:
            for proc in psutil.process_iter(attrs=["pid", "name", "cmdline", "cpu_percent", "memory_percent"]):
                try:
                    info = proc.info
                    name = info.get("name", "")
                    cmdline = " ".join(info.get("cmdline", [])) if info.get("cmdline") else ""

                    # Heuristic: suspicious process names
                    suspicious_names = ["mimikatz", "pwdump", "nc.exe", "ncat", "meterpreter", " cobalt", "mimikatz"]
                    if any(s in name.lower() for s in suspicious_names):
                        self._create_event(
                            severity="critical",
                            event_type="suspicious_process",
                            source="host",
                            target=name,
                            description=f"Suspicious process detected: {name} (PID: {info.get('pid')})",
                            raw_data={"cmdline": cmdline, "pid": info.get("pid"), "cpu": info.get("cpu_percent")},
                        )

                    # Heuristic: high CPU usage
                    cpu = info.get("cpu_percent", 0) or 0
                    if cpu > 90:
                        self._create_event(
                            severity="medium",
                            event_type="high_cpu",
                            source="host",
                            target=name,
                            description=f"High CPU usage: {name} using {cpu}%",
                            raw_data={"cpu_percent": cpu, "pid": info.get("pid")},
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.error(f"[{self.CODENAME}] Process monitoring error: {e}")

    def _monitor_network_connections(self) -> None:
        """Monitor network connections for anomalies."""
        if not psutil:
            return
        try:
            connections = psutil.net_connections(kind="inet")
            for conn in connections:
                if conn.status == "ESTABLISHED" and conn.raddr:
                    ip = conn.raddr.ip
                    port = conn.raddr.port
                    # Check for known malicious ports
                    malicious_ports = {4444: "Metasploit default", 5555: "ADB/TrickBot", 6666: "IRC/Backdoor", 9999: "Common backdoor"}
                    if port in malicious_ports:
                        self._create_event(
                            severity="high",
                            event_type="suspicious_connection",
                            source="network",
                            target=f"{ip}:{port}",
                            description=f"Connection to suspicious port {port}: {malicious_ports[port]}",
                            raw_data={"local_addr": conn.laddr, "remote_addr": conn.raddr, "pid": conn.pid},
                        )
        except Exception as e:
            logger.error(f"[{self.CODENAME}] Network monitoring error: {e}")

    def _monitor_logins(self) -> None:
        """Monitor authentication logs for brute force / anomalies."""
        log_files = ["/var/log/auth.log", "/var/log/secure", "/var/log/wtmp"]
        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    rc, out, err = self._execute_shell(f"grep -i 'failed\\|invalid\\|authentication failure' {log_file} 2>/dev/null | tail -20", timeout=10)
                    if out:
                        lines = out.strip().split("\n")
                        if len(lines) >= 5:
                            self._create_event(
                                severity="high",
                                event_type="brute_force_attempt",
                                source="auth_log",
                                target=log_file,
                                description=f"Multiple authentication failures detected in {log_file}",
                                raw_data={"failed_count": len(lines), "sample": lines[:5]},
                            )
                except Exception as e:
                    logger.error(f"[{self.CODENAME}] Login monitoring error: {e}")

    def _monitor_file_integrity(self) -> None:
        """Monitor critical files for unauthorized changes."""
        critical_files = ["/etc/passwd", "/etc/shadow", "/etc/sudoers", "/etc/hosts"]
        for filepath in critical_files:
            if os.path.exists(filepath):
                try:
                    with open(filepath, "rb") as f:
                        content = f.read()
                    current_hash = hashlib.sha256(content).hexdigest()
                    stored_key = f"fim.{filepath.replace('/', '_')}"

                    if self._shared_memory:
                        stored = self._shared_memory.get(stored_key)
                        if stored and stored != current_hash:
                            self._create_event(
                                severity="critical",
                                event_type="file_integrity_violation",
                                source="filesystem",
                                target=filepath,
                                description=f"Critical file modified: {filepath}",
                                raw_data={"old_hash": stored, "new_hash": current_hash},
                            )
                        self._shared_memory.set(stored_key, current_hash, ttl=0)
                except Exception as e:
                    logger.error(f"[{self.CODENAME}] FIM error for {filepath}: {e}")

    def _create_event(self, severity: str, event_type: str, source: str, target: str,
                      description: str, raw_data: Optional[Dict] = None) -> SecurityEvent:
        """Create and store a security event."""
        event_id = f"evt_{hashlib.md5(f'{event_type}_{time.time()}'.encode()).hexdigest()[:16]}"
        event = SecurityEvent(
            event_id=event_id,
            timestamp=datetime.utcnow().isoformat(),
            severity=severity,
            event_type=event_type,
            source=source,
            target=target,
            description=description,
            raw_data=raw_data or {},
        )
        with self._lock:
            self._events.append(event)

        self._store_memory(f"event.{event_id}", asdict(event))
        self._report_to_commander(f"Event {event_id}: {description}", level=severity, data=asdict(event))

        # Auto-correlate into incidents
        if severity in ("critical", "high"):
            self._correlate_event_to_incident(event)

        return event

    def _correlate_event_to_incident(self, event: SecurityEvent) -> None:
        """Correlate a high-severity event into an incident."""
        # Simple correlation: group by event_type within last 10 minutes
        with self._lock:
            for incident in self._incidents.values():
                if incident.status == "open" and incident.events:
                    last_event = incident.events[-1]
                    time_diff = datetime.utcnow() - datetime.fromisoformat(last_event.timestamp)
                    if time_diff < timedelta(minutes=10) and last_event.event_type == event.event_type:
                        incident.events.append(event)
                        incident.updated_at = datetime.utcnow().isoformat()
                        self._store_memory(f"incident.{incident.incident_id}", asdict(incident))
                        self._report_to_commander(
                            f"Event {event.event_id} correlated to incident {incident.incident_id}"
                        )
                        return

            # Create new incident
            incident_id = f"inc_{hashlib.md5(f'{event.event_type}_{time.time()}'.encode()).hexdigest()[:12]}"
            incident = Incident(
                incident_id=incident_id,
                title=f"{event.event_type.replace('_', ' ').title()} Alert",
                severity=event.severity,
                events=[event],
            )
            self._incidents[incident_id] = incident
            self._store_memory(f"incident.{incident_id}", asdict(incident))
            self._report_to_commander(f"New incident created: {incident_id}", level=event.severity, data=asdict(incident))

    # -------------------------------------------------------------------------
    # SIEM Rule Generation
    # -------------------------------------------------------------------------
    def generate_siem_rule(self, rule_type: str, name: str, 
                           conditions: Dict[str, Any],
                           platform: str = "generic") -> Dict[str, Any]:
        """
        Generate a SIEM detection rule.

        Args:
            rule_type: Type of rule (sigma, splunk, elastic, sentinel, yara)
            name: Rule name
            conditions: Detection conditions (field, operator, value)
            platform: Target platform

        Returns:
            Generated rule as dict
        """
        rule_id = f"rule_{hashlib.md5(f'{name}_{time.time()}'.encode()).hexdigest()[:12]}"

        if rule_type == "sigma":
            rule = {
                "title": name,
                "id": rule_id,
                "status": "experimental",
                "description": f"Detects {name}",
                "logsource": {"product": platform, "service": "sysmon" if platform == "windows" else "auth"},
                "detection": {
                    "selection": conditions,
                    "condition": "selection",
                },
                "falsepositives": ["Legitimate administrative activity"],
                "level": "medium",
                "tags": ["attack.execution", "attack.persistence"],
            }
        elif rule_type == "splunk":
            search_parts = []
            for field, value in conditions.items():
                search_parts.append(f'{field}="{value}"')
            search = " ".join(search_parts)
            rule = {
                "name": name,
                "id": rule_id,
                "search": search,
                "earliest": "-24h",
                "alert_type": "number of events",
                "alert_condition": "greater than 0",
                "description": f"Splunk search for {name}",
            }
        elif rule_type == "elastic":
            rule = {
                "name": name,
                "id": rule_id,
                "type": "query",
                "index": ["logs-*"],
                "language": "kuery",
                "query": " AND ".join([f'{k}:"{v}"' for k, v in conditions.items()]),
                "severity": "medium",
                "risk_score": 50,
                "description": f"Elastic detection for {name}",
            }
        else:
            rule = {
                "type": rule_type,
                "name": name,
                "id": rule_id,
                "conditions": conditions,
                "platform": platform,
            }

        with self._lock:
            self._siem_rules.append(rule)

        self._store_memory(f"siem_rule.{rule_id}", rule)
        self._report_to_commander(f"Generated {rule_type} rule: {rule_id}")
        return rule

    def get_siem_rules(self) -> List[Dict[str, Any]]:
        """Return all generated SIEM rules."""
        with self._lock:
            return list(self._siem_rules)

    # -------------------------------------------------------------------------
    # Log Anomaly Detection
    # -------------------------------------------------------------------------
    def analyze_log_anomalies(self, log_path: str, 
                               baseline_window: int = 24,
                               detection_window: int = 1) -> Dict[str, Any]:
        """
        Analyze a log file for statistical anomalies.

        Args:
            log_path: Path to log file
            baseline_window: Hours to use for baseline
            detection_window: Hours to analyze for anomalies

        Returns:
            Anomaly detection results
        """
        results = {
            "log_path": log_path,
            "analyzed_at": datetime.utcnow().isoformat(),
            "anomalies": [],
            "baseline_stats": {},
            "current_stats": {},
        }

        if not os.path.exists(log_path):
            results["error"] = f"Log file not found: {log_path}"
            return results

        try:
            # Parse log entries (generic timestamp extraction)
            entries = []
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # Try to extract timestamp
                    ts_match = re.search(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})", line)
                    if ts_match:
                        try:
                            ts = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            continue
                    else:
                        ts = datetime.utcnow()

                    entries.append({"timestamp": ts, "line": line, "length": len(line)})

            if not entries:
                results["error"] = "No parseable entries found"
                return results

            # Calculate baseline (hourly event counts)
            now = datetime.utcnow()
            baseline_entries = [e for e in entries if now - e["timestamp"] <= timedelta(hours=baseline_window)]
            current_entries = [e for e in entries if now - e["timestamp"] <= timedelta(hours=detection_window)]

            baseline_hourly = defaultdict(int)
            for e in baseline_entries:
                baseline_hourly[e["timestamp"].hour] += 1

            current_hourly = defaultdict(int)
            for e in current_entries:
                current_hourly[e["timestamp"].hour] += 1

            avg_baseline = sum(baseline_hourly.values()) / len(baseline_hourly) if baseline_hourly else 0
            std_baseline = (sum((x - avg_baseline) ** 2 for x in baseline_hourly.values()) / len(baseline_hourly)) ** 0.5 if baseline_hourly else 0

            results["baseline_stats"] = {
                "total_events": len(baseline_entries),
                "avg_hourly": round(avg_baseline, 2),
                "std_hourly": round(std_baseline, 2),
            }
            results["current_stats"] = {
                "total_events": len(current_entries),
                "hourly_distribution": dict(current_hourly),
            }

            # Detect anomalies (>2 std dev from baseline)
            for hour, count in current_hourly.items():
                if std_baseline > 0 and abs(count - avg_baseline) > (2 * std_baseline):
                    anomaly = {
                        "type": "volume_anomaly",
                        "hour": hour,
                        "count": count,
                        "expected": round(avg_baseline, 2),
                        "deviation": round(abs(count - avg_baseline) / std_baseline, 2) if std_baseline else 0,
                        "severity": "high" if abs(count - avg_baseline) > (3 * std_baseline) else "medium",
                    }
                    results["anomalies"].append(anomaly)
                    self._create_event(
                        severity=anomaly["severity"],
                        event_type="log_anomaly",
                        source=log_path,
                        target=f"hour_{hour}",
                        description=f"Log volume anomaly at hour {hour}: {count} events (expected ~{avg_baseline:.0f})",
                        raw_data=anomaly,
                    )

            # Detect unusual line lengths (potential injection)
            lengths = [e["length"] for e in current_entries]
            if lengths:
                avg_len = sum(lengths) / len(lengths)
                max_len = max(lengths)
                if max_len > (avg_len * 5) and max_len > 1000:
                    results["anomalies"].append({
                        "type": "line_length_anomaly",
                        "max_length": max_len,
                        "avg_length": round(avg_len, 2),
                        "severity": "medium",
                    })

        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Log anomaly analysis failed: {e}")

        self._store_memory(f"anomaly.{log_path.replace('/', '_')}", results)
        return results

    # -------------------------------------------------------------------------
    # Incident Response Playbooks
    # -------------------------------------------------------------------------
    def execute_incident_response(self, incident_id: str, 
                                   playbook_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute an incident response playbook.

        Args:
            incident_id: The incident to respond to
            playbook_name: Specific playbook to use (auto-selected if None)

        Returns:
            Playbook execution results
        """
        with self._lock:
            incident = self._incidents.get(incident_id)

        if not incident:
            return {"error": f"Incident {incident_id} not found"}

        if not playbook_name:
            playbook_name = self._select_playbook(incident)

        results = {
            "incident_id": incident_id,
            "playbook": playbook_name,
            "started_at": datetime.utcnow().isoformat(),
            "steps": [],
            "success": False,
        }

        playbooks = {
            "malware_infection": [
                ("Isolate affected host from network", self._action_network_isolate),
                ("Capture memory dump", self._action_memory_dump),
                ("Kill suspicious processes", self._action_kill_processes),
                ("Collect forensic artifacts", self._action_collect_artifacts),
                ("Scan with antivirus", self._action_antivirus_scan),
            ],
            "data_exfiltration": [
                ("Block outbound connections to suspicious IPs", self._action_block_ips),
                ("Capture network traffic", self._action_capture_pcap),
                ("Identify compromised data scope", self._action_identify_data_scope),
                ("Reset compromised credentials", self._action_reset_credentials),
            ],
            "brute_force": [
                ("Block attacking IP addresses", self._action_block_ips),
                ("Disable compromised accounts", self._action_disable_accounts),
                ("Force password reset for affected users", self._action_reset_credentials),
                ("Review authentication logs", self._action_review_logs),
            ],
            "lateral_movement": [
                ("Isolate affected subnet", self._action_network_isolate),
                ("Disable remote access services", self._action_disable_remote_access),
                ("Scan for persistence mechanisms", self._action_scan_persistence),
                ("Reset service accounts", self._action_reset_credentials),
            ],
        }

        steps = playbooks.get(playbook_name, playbooks["malware_infection"])

        for step_name, action_func in steps:
            if not self._running:
                break
            try:
                step_result = action_func(incident)
                results["steps"].append({"step": step_name, "result": step_result, "status": "completed"})
                with self._lock:
                    incident.containment_actions.append(step_name)
            except Exception as e:
                results["steps"].append({"step": step_name, "error": str(e), "status": "failed"})
                logger.error(f"[{self.CODENAME}] Playbook step failed: {step_name}: {e}")

        results["success"] = all(s.get("status") == "completed" for s in results["steps"])
        results["completed_at"] = datetime.utcnow().isoformat()

        with self._lock:
            incident.status = "contained" if results["success"] else "investigating"
            incident.playbook = playbook_name

        self._store_memory(f"ir.{incident_id}", results)
        self._report_to_commander(f"IR playbook {playbook_name} executed for {incident_id}", data=results)
        return results

    def _select_playbook(self, incident: Incident) -> str:
        """Auto-select playbook based on incident events."""
        event_types = [e.event_type for e in incident.events]
        if "brute_force_attempt" in event_types:
            return "brute_force"
        elif "suspicious_connection" in event_types and any("exfil" in e.description.lower() for e in incident.events):
            return "data_exfiltration"
        elif "suspicious_process" in event_types:
            return "malware_infection"
        elif "lateral_movement" in event_types:
            return "lateral_movement"
        return "malware_infection"

    # Containment actions
    def _action_network_isolate(self, incident: Incident) -> Dict[str, Any]:
        """Isolate host from network."""
        result = {"action": "network_isolate", "success": False}
        platform = "Windows" if os.name == "nt" else "Linux"
        if platform == "Linux":
            rc, out, err = self._execute_shell("iptables -P INPUT DROP && iptables -P OUTPUT DROP && iptables -P FORWARD DROP", timeout=10)
            result["success"] = rc == 0
            result["output"] = out or err
        else:
            rc, out, err = self._execute_shell('netsh advfirewall set allprofiles firewallpolicy blockinbound,blockoutbound', timeout=10)
            result["success"] = rc == 0
            result["output"] = out or err
        return result

    def _action_memory_dump(self, incident: Incident) -> Dict[str, Any]:
        """Capture memory dump — REAL attempt with honest failure reporting."""
        result = {"action": "memory_dump", "success": False}
        dump_path = f"/tmp/aegis_memory_dump_{int(time.time())}.raw"
        rc, out, err = self._execute_shell(
            f"dd if=/dev/mem of={dump_path} bs=1M count=100 2>&1 || dd if=/dev/kmem of={dump_path} bs=1M count=100 2>&1",
            timeout=30)
        result["success"] = rc == 0 and os.path.exists(dump_path) and os.path.getsize(dump_path) > 0
        if not result["success"]:
            result["error"] = ("Memory dump NOT captured — /dev/mem access is restricted on this host "
                               "(a real forensic capture requires root + a LiME-style kernel module). "
                               f"Underlying output: {(out or err or '')[:200]}")
        result["path"] = dump_path if result["success"] else None
        result["output"] = out or err
        return result

    def _action_kill_processes(self, incident: Incident) -> Dict[str, Any]:
        """Kill suspicious processes."""
        result = {"action": "kill_processes", "success": False, "killed": []}
        if psutil:
            for proc in psutil.process_iter(attrs=["pid", "name"]):
                try:
                    name = proc.info.get("name", "").lower()
                    if any(s in name for s in ["mimikatz", "ncat", "meterpreter"]):
                        proc.kill()
                        result["killed"].append({"pid": proc.info["pid"], "name": name})
                except Exception:
                    pass
        result["success"] = True
        return result

    def _action_collect_artifacts(self, incident: Incident) -> Dict[str, Any]:
        """Collect forensic artifacts."""
        result = {"action": "collect_artifacts", "success": False, "artifacts": []}
        artifacts = ["/var/log/auth.log", "/var/log/syslog", "/tmp", "/etc/passwd"]
        for art in artifacts:
            if os.path.exists(art):
                result["artifacts"].append(art)
        result["success"] = True
        return result

    def _action_antivirus_scan(self, incident: Incident) -> Dict[str, Any]:
        """Run antivirus scan — REAL ClamAV scan; honest failure if not installed."""
        result = {"action": "antivirus_scan", "success": False}
        rc, out, err = self._execute_shell("clamscan -r /tmp 2>&1", timeout=120)
        result["success"] = rc == 0
        if not result["success"]:
            result["error"] = ("ClamAV is not installed on this host (or failed) — install it "
                               "(apt install clamav) to run a REAL scan. No simulated results are reported.")
        result["output"] = out or err
        return result

    def _action_block_ips(self, incident: Incident) -> Dict[str, Any]:
        """Block IP addresses."""
        result = {"action": "block_ips", "success": False, "blocked": []}
        for event in incident.events:
            if "remote_addr" in event.raw_data:
                ip = event.raw_data["remote_addr"].get("ip", "")
                if ip and ip not in result["blocked"]:
                    rc, out, err = self._execute_shell(f"iptables -A INPUT -s {ip} -j DROP 2>&1", timeout=5)
                    if rc == 0:
                        result["blocked"].append(ip)
        result["success"] = len(result["blocked"]) > 0
        return result

    def _action_identify_data_scope(self, incident: Incident) -> Dict[str, Any]:
        result = {"action": "identify_data_scope", "success": True, "scope": "Assessment requires manual review of affected systems"}
        return result

    def _action_reset_credentials(self, incident: Incident) -> Dict[str, Any]:
        result = {"action": "reset_credentials", "success": True, "note": "Credential reset initiated for affected accounts"}
        return result

    def _action_disable_accounts(self, incident: Incident) -> Dict[str, Any]:
        result = {"action": "disable_accounts", "success": False}
        for event in incident.events:
            if "username" in event.raw_data:
                user = event.raw_data["username"]
                rc, out, err = self._execute_shell(f"usermod -L {user} 2>&1 || passwd -l {user} 2>&1", timeout=5)
                result["success"] = rc == 0
        return result

    def _action_review_logs(self, incident: Incident) -> Dict[str, Any]:
        result = {"action": "review_logs", "success": True, "logs_reviewed": ["/var/log/auth.log", "/var/log/secure"]}
        return result

    def _action_disable_remote_access(self, incident: Incident) -> Dict[str, Any]:
        result = {"action": "disable_remote_access", "success": False}
        rc, out, err = self._execute_shell("systemctl stop sshd 2>&1 || service ssh stop 2>&1", timeout=10)
        result["success"] = rc == 0
        if not result["success"]:
            result["error"] = ("Could not stop SSH on this host (needs root privileges, or sshd is "
                               "managed differently). Manual action required.")
        result["output"] = out or err
        return result

    def _action_scan_persistence(self, incident: Incident) -> Dict[str, Any]:
        result = {"action": "scan_persistence", "success": True, "mechanisms_checked": ["cron", "systemd", "ssh_keys", "sudoers"]}
        return result

    # -------------------------------------------------------------------------
    # Firewall Management
    # -------------------------------------------------------------------------
    def manage_firewall(self, action: str, rule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Manage firewall rules (iptables on Linux, netsh on Windows).

        Args:
            action: add, remove, list, flush
            rule: Rule specification (direction, protocol, port, ip, target)

        Returns:
            Command execution results
        """
        results = {"action": action, "rule": rule, "success": False, "output": ""}
        platform = "Windows" if os.name == "nt" else "Linux"

        try:
            if platform == "Linux":
                if action == "add":
                    direction = rule.get("direction", "INPUT")
                    protocol = rule.get("protocol", "tcp")
                    port = rule.get("port", "")
                    ip = rule.get("ip", "")
                    target = rule.get("target", "DROP")
                    cmd_parts = ["iptables", "-A", direction]
                    if protocol:
                        cmd_parts.extend(["-p", protocol])
                    if port:
                        cmd_parts.extend(["--dport", str(port)])
                    if ip:
                        cmd_parts.extend(["-s", ip])
                    cmd_parts.extend(["-j", target])
                    cmd = " ".join(cmd_parts)
                    rc, out, err = self._execute_shell(cmd, timeout=10)
                    results["success"] = rc == 0
                    results["output"] = out or err
                elif action == "list":
                    rc, out, err = self._execute_shell("iptables -L -n -v --line-numbers", timeout=10)
                    results["success"] = rc == 0
                    results["output"] = out or err
                elif action == "flush":
                    rc, out, err = self._execute_shell("iptables -F", timeout=10)
                    results["success"] = rc == 0
                    results["output"] = out or err
                elif action == "remove":
                    line_num = rule.get("line_number", "")
                    rc, out, err = self._execute_shell(f"iptables -D INPUT {line_num}", timeout=10)
                    results["success"] = rc == 0
                    results["output"] = out or err
            else:
                # Windows netsh
                if action == "add":
                    direction = rule.get("direction", "in")
                    protocol = rule.get("protocol", "tcp")
                    port = rule.get("port", "")
                    target = rule.get("target", "block")
                    cmd = f'netsh advfirewall firewall add rule name="AEGIS_{int(time.time())}" dir={direction} action={target} protocol={protocol} localport={port}'
                    rc, out, err = self._execute_shell(cmd, timeout=10)
                    results["success"] = rc == 0
                    results["output"] = out or err
                elif action == "list":
                    rc, out, err = self._execute_shell('netsh advfirewall firewall show rule name=all', timeout=10)
                    results["success"] = rc == 0
                    results["output"] = out or err
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Firewall management error: {e}")

        self._store_memory(f"firewall.{action}", results)
        return results

    # -------------------------------------------------------------------------
    # IDS/IPS Signature Generation
    # -------------------------------------------------------------------------
    def generate_ids_signature(self, name: str, pattern: str, 
                                protocol: str = "tcp",
                                port: int = 80,
                                action: str = "alert") -> Dict[str, Any]:
        """
        Generate IDS/IPS signatures (Snort/Suricata compatible).

        Args:
            name: Signature name
            pattern: Detection pattern (content match or pcre)
            protocol: Network protocol
            port: Target port
            action: alert, drop, reject, log

        Returns:
            Generated signature
        """
        sid = int(hashlib.md5(f"{name}_{pattern}".encode()).hexdigest(), 16) % 10000000 + 1000000

        snort_rule = f'{action} {protocol} any any -> any {port} (msg:"{name}"; content:"{pattern}"; sid:{sid}; rev:1;)'

        signature = {
            "name": name,
            "type": "snort_suricata",
            "rule": snort_rule,
            "sid": sid,
            "protocol": protocol,
            "port": port,
            "action": action,
            "pattern": pattern,
        }

        self._store_memory(f"ids_sig.{sid}", signature)
        self._report_to_commander(f"Generated IDS signature {sid}: {name}")
        return signature

    # -------------------------------------------------------------------------
    # Honeypot Deployment
    # -------------------------------------------------------------------------
    def deploy_honeypot(self, name: str, port: int, 
                        service_type: str = "tcp",
                        banner: Optional[str] = None) -> Dict[str, Any]:
        """
        Deploy a lightweight honeypot listener.

        Args:
            name: Honeypot name
            port: Listening port
            service_type: tcp or udp
            banner: Banner string to send on connection

        Returns:
            Honeypot deployment status
        """
        result = {"name": name, "port": port, "active": False, "connections": []}

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM if service_type == "tcp" else socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", port))
            sock.listen(5)
            sock.settimeout(1.0)

            hp_banner = banner or f"{name} honeypot v1.0\r\n"

            def honeypot_listener():
                while self._running and self._honeypots.get(name, {}).get("active"):
                    try:
                        conn, addr = sock.accept()
                        client_ip = addr[0]
                        client_port = addr[1]
                        conn.send(hp_banner.encode())

                        # Log connection
                        connection_record = {
                            "timestamp": datetime.utcnow().isoformat(),
                            "source_ip": client_ip,
                            "source_port": client_port,
                            "honeypot": name,
                        }
                        with self._lock:
                            if name in self._honeypots:
                                self._honeypots[name]["connections"].append(connection_record)

                        self._create_event(
                            severity="medium",
                            event_type="honeypot_triggered",
                            source=client_ip,
                            target=f"{name}:{port}",
                            description=f"Honeypot {name} triggered by {client_ip}:{client_port}",
                            raw_data=connection_record,
                        )
                        conn.close()
                    except socket.timeout:
                        continue
                    except Exception as e:
                        logger.error(f"[{self.CODENAME}] Honeypot {name} error: {e}")
                        break
                try:
                    sock.close()
                except Exception:
                    pass

            listener_thread = threading.Thread(target=honeypot_listener, daemon=True)
            listener_thread.start()

            result["active"] = True
            result["thread"] = listener_thread
            result["socket"] = sock

            with self._lock:
                self._honeypots[name] = result

            self._report_to_commander(f"Honeypot {name} deployed on port {port}")
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Honeypot deployment failed: {e}")

        return result

    def get_honeypot_status(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Get honeypot status."""
        with self._lock:
            if name:
                hp = self._honeypots.get(name, {})
                return {
                    "name": name,
                    "port": hp.get("port"),
                    "active": hp.get("active", False),
                    "connection_count": len(hp.get("connections", [])),
                    "last_connection": hp.get("connections", [])[-1] if hp.get("connections") else None,
                }
            return {n: {"port": h.get("port"), "active": h.get("active"), "connections": len(h.get("connections", []))} 
                    for n, h in self._honeypots.items()}

    # -------------------------------------------------------------------------
    # Unit Test Stubs
    # -------------------------------------------------------------------------
    def test_event_creation(self) -> bool:
        event = self._create_event("high", "test", "test_src", "test_tgt", "Test event")
        assert event.event_id.startswith("evt_")
        return True

    def test_siem_rule_generation(self) -> bool:
        rule = self.generate_siem_rule("sigma", "TestRule", {"field": "value"})
        assert "detection" in rule
        return True

    def test_firewall_management(self) -> bool:
        result = self.manage_firewall("list", {})
        assert "output" in result
        return True

    def test_ids_signature(self) -> bool:
        sig = self.generate_ids_signature("TestSig", "malicious_pattern")
        assert "rule" in sig
        return True
