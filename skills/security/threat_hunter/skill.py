"""Threat Hunter Skill — IOC search, behavioral analysis, threat detection."""

import re
import logging
from typing import Dict, Any, List
from datetime import datetime
from skills import BaseSkill

logger = logging.getLogger(__name__)


class ThreatHunterSkill(BaseSkill):
    """IOC hunting, behavioral analysis, and threat detection."""

    def __init__(self):
        super().__init__(name="threat_hunter", category="security", capabilities=["threat_hunting"])
        self._known_iocs: Dict[str, List[str]] = {"ip": [], "domain": [], "hash": [], "email": []}

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "hunt_iocs")
        if method == "hunt_iocs":
            return self.hunt_iocs(params)
        elif method == "behavioral_analysis":
            return self.behavioral_analysis(params)
        elif method == "detect_threats":
            return self.detect_threats(params)
        return {"error": f"Unknown method: {method}"}

    def hunt_iocs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        iocs = params.get("iocs", [])
        source = params.get("source", "")
        if not iocs:
            return {"success": False, "error": "No IOCs provided"}
        matches = []
        for ioc in iocs:
            ioc_type = self._classify_ioc(ioc)
            match_info = {"ioc": ioc, "type": ioc_type, "matches": [], "timestamp": datetime.utcnow().isoformat()}
            if ioc_type == "ip":
                # Check against known malicious IP patterns
                if ioc.startswith(("10.", "192.168.", "127.")):
                    match_info["context"] = "private_ip"
                # Try threat intelligence lookup
                try:
                    import urllib.request
                    req = urllib.request.Request(f"https://www.virustotal.com/api/v3/ip_addresses/{ioc}", headers={"User-Agent": "IRIS-Security/1.0"}, method="GET")
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        match_info["vt_lookup"] = "found" if resp.status == 200 else "not_found"
                except Exception:
                    match_info["vt_lookup"] = "unavailable"
            elif ioc_type == "domain":
                try:
                    import socket
                    socket.gethostbyname(ioc)
                    match_info["resolvable"] = True
                except socket.gaierror:
                    match_info["resolvable"] = False
            elif ioc_type == "hash":
                hash_len = len(ioc)
                match_info["hash_type"] = "md5" if hash_len == 32 else "sha1" if hash_len == 40 else "sha256" if hash_len == 64 else "unknown"
            matches.append(match_info)
        return {"success": True, "iocs_searched": len(iocs), "matches": matches}

    def _classify_ioc(self, ioc: str) -> str:
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ioc):
            return "ip"
        if re.match(r'^[a-f0-9]{32}$', ioc, re.IGNORECASE) or re.match(r'^[a-f0-9]{40}$', ioc, re.IGNORECASE) or re.match(r'^[a-f0-9]{64}$', ioc, re.IGNORECASE):
            return "hash"
        if re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', ioc):
            return "email"
        if re.match(r'^[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}$', ioc):
            return "domain"
        return "unknown"

    def behavioral_analysis(self, params: Dict[str, Any]) -> Dict[str, Any]:
        process_data = params.get("process_data", {})
        baseline = params.get("baseline", {})
        anomalies = []
        if process_data:
            cpu_usage = process_data.get("cpu_usage", 0)
            memory_usage = process_data.get("memory_usage", 0)
            network_connections = process_data.get("network_connections", 0)
            baseline_cpu = baseline.get("cpu_avg", 10)
            baseline_mem = baseline.get("memory_avg", 30)
            if cpu_usage > baseline_cpu * 3:
                anomalies.append({"type": "cpu_spike", "severity": "high", "value": cpu_usage, "baseline": baseline_cpu})
            if memory_usage > baseline_mem * 2:
                anomalies.append({"type": "memory_spike", "severity": "medium", "value": memory_usage, "baseline": baseline_mem})
            if network_connections > baseline.get("conn_avg", 10) * 5:
                anomalies.append({"type": "network_spike", "severity": "high", "value": network_connections, "baseline": baseline.get("conn_avg", 10)})
        return {"success": True, "anomalies_detected": len(anomalies), "anomalies": anomalies, "behavior_profile": "baseline_comparison"}

    def detect_threats(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("source", "")
        indicators = params.get("indicators", [])
        detected = []
        for ind in indicators:
            ind_type = ind.get("type", "")
            value = ind.get("value", "")
            if ind_type == "file_write" and any(s in value for s in ["/etc/passwd", "/etc/shadow", "\\Windows\\System32"]):
                detected.append({"type": "suspicious_file_write", "severity": "critical", "value": value})
            elif ind_type == "network" and any(s in value for s in ["tor", "pastebin", "transfer.sh"]):
                detected.append({"type": "suspicious_network", "severity": "high", "value": value})
            elif ind_type == "process" and any(s in value for s in ["mimikatz", "powersploit", "bloodhound"]):
                detected.append({"type": "known_tool", "severity": "critical", "value": value})
        return {"success": True, "source": source, "threats_found": len(detected), "detections": detected, "severity": "critical" if any(d["severity"] == "critical" for d in detected) else "high" if detected else "low"}
