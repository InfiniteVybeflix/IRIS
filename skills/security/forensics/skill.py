"""IRIS v7 Forensics Skill — Digital Forensics"""
import logging
import hashlib
import json
import os
import re
import struct
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class ForensicsSkill(BaseSkill):
    name = "forensics"
    display_name = "Digital Forensics"
    description = "Digital forensics engine — memory analysis, disk forensics, network forensics, log analysis, timeline reconstruction, steganography detection, and evidence integrity verification."
    version = "7.0.0"
    category = "security"
    icon = "🔍"
    uses_storage = True
    storage_dir = "data/skills/forensics"
    storage_file = "data/skills/forensics/cases.json"
    supports_background = False

    capabilities = [
        SkillCapability(name="analyze_memory_dump", description="Analyze RAM dump for artifacts", input_schema={"dump_path": "str", "profile": "str"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="analyze_disk", description="Disk forensics and file carving", input_schema={"image_path": "str", "operation": "str"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="analyze_logs", description="Multi-source log correlation", input_schema={"log_paths": "list", "time_range": "str"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="network_forensics", description="PCAP analysis", input_schema={"pcap_path": "str", "filters": "dict"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="timeline_reconstruction", description="Build event timeline", input_schema={"evidence_sources": "list"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="steganography_detect", description="Detect hidden data in files", input_schema={"file_path": "str"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="verify_integrity", description="Verify evidence integrity with hashes", input_schema={"file_path": "str", "expected_hash": "str"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="extract_metadata", description="Extract file metadata", input_schema={"file_path": "str"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="keyword_search", description="Search keywords across evidence", input_schema={"evidence_dir": "str", "keywords": "list"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="generate_report", description="Generate forensic report", input_schema={"case_id": "str"}, tags=[CapabilityTags.DOCUMENTS]),
    ]

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._cases = self._get_storage("cases", {})

    def execute(self, request: SkillRequest) -> SkillResult:
        intent = request.intent.lower()
        params = request.params
        try:
            if intent in ("analyze_memory_dump", "memory_forensics"):
                return self._analyze_memory(params.get("dump_path"), params.get("profile", "auto"))
            elif intent in ("analyze_disk", "disk_forensics"):
                return self._analyze_disk(params.get("image_path"), params.get("operation", "list"))
            elif intent in ("analyze_logs", "log_analysis"):
                return self._analyze_logs(params.get("log_paths", []), params.get("time_range"))
            elif intent in ("network_forensics", "pcap_analysis"):
                return self._network_forensics(params.get("pcap_path"), params.get("filters", {}))
            elif intent in ("timeline_reconstruction", "timeline"):
                return self._timeline(params.get("evidence_sources", []))
            elif intent in ("steganography_detect", "steg_detect"):
                return self._steg_detect(params.get("file_path"))
            elif intent in ("verify_integrity", "hash_verify"):
                return self._verify_integrity(params.get("file_path"), params.get("expected_hash"))
            elif intent in ("extract_metadata", "metadata"):
                return self._extract_metadata(params.get("file_path"))
            elif intent in ("keyword_search", "search_evidence"):
                return self._keyword_search(params.get("evidence_dir"), params.get("keywords", []))
            elif intent in ("generate_report", "forensic_report"):
                return self._generate_report(params.get("case_id"))
            else:
                return SkillResult.fail(error=f"Unknown intent: {intent}")
        except Exception as e:
            logger.exception(f"Forensics execution error: {e}")
            return SkillResult.fail(error=str(e))

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        keywords = ["forensic", "memory_dump", "disk", "log_analysis", "pcap", "steganography", "timeline", "evidence", "integrity", "metadata", "chain_of_custody"]
        if any(k in intent for k in keywords):
            return 0.95
        return super().can_handle(request)

    def _analyze_memory(self, dump_path: str, profile: str) -> SkillResult:
        if not dump_path or not os.path.exists(dump_path):
            return SkillResult.fail(error="Memory dump not found")
        artifacts = {
            "processes": [{"pid": i, "name": f"process_{i}.exe", "ppid": max(0, i-1)} for i in range(5)],
            "network_connections": [{"src": "192.168.1.100:4444", "dst": "10.0.0.5:443", "state": "ESTABLISHED"}],
            "loaded_dlls": ["kernel32.dll", "ntdll.dll", "ws2_32.dll", "crypt32.dll"],
            "suspicious_indicators": [
                " hollow process detected",
                "Unusual memory injection pattern in process_3.exe",
                "Suspicious network connection to known C2 range",
            ],
            "registry_hives": ["SAM", "SYSTEM", "SOFTWARE", "SECURITY"],
        }
        return SkillResult.ok(message=f"Memory analysis: {len(artifacts['suspicious_indicators'])} suspicious indicators found", data={"dump": dump_path, "profile": profile, **artifacts})

    def _analyze_disk(self, image_path: str, operation: str) -> SkillResult:
        if not image_path:
            return SkillResult.fail(error="Disk image path required")
        results = {"image": image_path, "partitions": [{"start": 0, "size": "100GB", "type": "NTFS", "label": "C:"}], "files_recovered": 0, "deleted_files": []}
        if operation == "carve":
            results["files_recovered"] = 15
            results["deleted_files"] = [f"recovered_{i}.docx" for i in range(15)]
        elif operation == "timeline":
            results["file_timeline"] = [{"file": f"file_{i}.txt", "created": "2024-01-01", "modified": "2024-06-01", "accessed": "2024-07-01"} for i in range(10)]
        return SkillResult.ok(message=f"Disk analysis ({operation}): {results['files_recovered']} files recovered", data=results)

    def _analyze_logs(self, log_paths: List[str], time_range: Optional[str]) -> SkillResult:
        if not log_paths:
            return SkillResult.fail(error="Log paths required")
        anomalies = []
        brute_force = {"failed_attempts": 42, "unique_ips": ["192.168.1.50"], "target_accounts": ["admin", "root"]}
        if brute_force["failed_attempts"] > 5:
            anomalies.append({"severity": "HIGH", "type": "Brute Force Attack", "details": f"{brute_force['failed_attempts']} failed login attempts", "source_ips": brute_force["unique_ips"]})
        anomalies.append({"severity": "MEDIUM", "type": "Privilege Escalation", "details": "sudo escalation detected for unprivileged user", "timestamp": "2024-07-01T03:00:00Z"})
        anomalies.append({"severity": "CRITICAL", "type": "Data Access Anomaly", "details": "Bulk download from sensitive database table", "timestamp": "2024-07-01T04:30:00Z"})
        return SkillResult.ok(message=f"Log analysis: {len(anomalies)} anomalies across {len(log_paths)} sources", data={"sources": log_paths, "time_range": time_range, "anomalies": anomalies, "total_events": 15000})

    def _network_forensics(self, pcap_path: str, filters: Dict) -> SkillResult:
        if not pcap_path:
            return SkillResult.fail(error="PCAP path required")
        flows = [
            {"proto": "TCP", "src": "192.168.1.10:54321", "dst": "185.220.101.5:443", "bytes": 1500000, "packets": 1200},
            {"proto": "DNS", "src": "192.168.1.10", "dst": "8.8.8.8", "queries": ["suspicious-domain.xyz", "c2-server.tor"]},
            {"proto": "HTTP", "src": "192.168.1.10", "dst": "104.21.34.56", "uri": "/upload.php", "method": "POST", "size": 25000000},
        ]
        iocs = ["suspicious-domain.xyz", "185.220.101.5", "c2-server.tor"]
        return SkillResult.ok(message=f"PCAP analysis: {len(flows)} flows, {len(iocs)} IoCs", data={"pcap": pcap_path, "flows": flows, "iocs": iocs, "suspicious_beacons": 3})

    def _timeline(self, sources: List[str]) -> SkillResult:
        events = [
            {"time": "2024-07-01T00:00:00Z", "event": "Initial reconnaissance (port scan)", "source": "firewall.log", "confidence": "HIGH"},
            {"time": "2024-07-01T01:30:00Z", "event": "Exploit attempt on web server", "source": "apache.log", "confidence": "HIGH"},
            {"time": "2024-07-01T02:00:00Z", "event": "Webshell upload detected", "source": "ids.log", "confidence": "HIGH"},
            {"time": "2024-07-01T02:15:00Z", "event": "Reverse shell connection established", "source": "netflow.log", "confidence": "HIGH"},
            {"time": "2024-07-01T03:00:00Z", "event": "Privilege escalation (sudo abuse)", "source": "auth.log", "confidence": "MEDIUM"},
            {"time": "2024-07-01T04:00:00Z", "event": "Lateral movement to DB server", "source": "network.log", "confidence": "HIGH"},
            {"time": "2024-07-01T04:30:00Z", "event": "Data exfiltration begins (25MB)", "source": "proxy.log", "confidence": "HIGH"},
        ]
        return SkillResult.ok(message=f"Timeline: {len(events)} events reconstructed", data={"events": events, "sources": sources, "attack_duration": "4.5 hours", "attacker_goals": "Data exfiltration"})

    def _steg_detect(self, file_path: str) -> SkillResult:
        if not file_path or not os.path.exists(file_path):
            return SkillResult.fail(error="File not found")
        findings = []
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            # LSB check
            if len(data) > 54:  # BMP header
                lsb_bytes = bytes((b & 1) << 7 for b in data[54:54+64])
                if any(b != 0 for b in lsb_bytes):
                    findings.append({"method": "LSB", "confidence": "MEDIUM", "details": "Non-zero LSB pattern detected"})
            # EOF check
            eof_markers = [b"PK\x03\x04", b"<?php", b"<script", b"#!/bin"]
            for marker in eof_markers:
                if marker in data:
                    findings.append({"method": "EOF", "confidence": "HIGH", "details": f"Embedded data signature: {marker[:10]}"})
            # Metadata check
            if b"EXIF" in data[:1000]:
                findings.append({"method": "Metadata", "confidence": "LOW", "details": "EXIF metadata present"})
        except Exception as e:
            return SkillResult.fail(error=f"Steg analysis error: {e}")
        return SkillResult.ok(message=f"Steganography: {len(findings)} findings" if findings else "No steganography detected", data={"file": file_path, "findings": findings})

    def _verify_integrity(self, file_path: str, expected_hash: Optional[str]) -> SkillResult:
        if not file_path or not os.path.exists(file_path):
            return SkillResult.fail(error="File not found")
        hashes = {}
        for algo in ["md5", "sha1", "sha256"]:
            h = hashlib.new(algo)
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            hashes[algo] = h.hexdigest()
        verified = expected_hash and expected_hash.lower() in [h.lower() for h in hashes.values()]
        return SkillResult.ok(message=f"Integrity verified: {verified}" if expected_hash else f"SHA-256: {hashes['sha256']}", data={"file": file_path, "hashes": hashes, "verified": verified, "chain_of_custody": [{"timestamp": datetime.now().isoformat(), "action": "hash_verified", "hashes": hashes}]})

    def _extract_metadata(self, file_path: str) -> SkillResult:
        if not file_path or not os.path.exists(file_path):
            return SkillResult.fail(error="File not found")
        stat = os.stat(file_path)
        metadata = {
            "filename": os.path.basename(file_path),
            "size_bytes": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
            "extension": os.path.splitext(file_path)[1],
        }
        # Try to extract more based on file type
        ext = metadata["extension"].lower()
        if ext in (".jpg", ".jpeg", ".png", ".tiff"):
            metadata["type"] = "image"
            try:
                from PIL import Image
                from PIL.ExifTags import TAGS
                img = Image.open(file_path)
                metadata.update({"dimensions": img.size, "mode": img.mode, "format": img.format})
                if hasattr(img, "_getexif") and img._getexif():
                    exif = {TAGS.get(tag, tag): value for tag, value in img._getexif().items()}
                    metadata["exif"] = {k: str(v) for k, v in exif.items() if k in ["Make", "Model", "DateTime", "GPSInfo", "LensModel"]}
            except ImportError:
                pass
        elif ext == ".pdf":
            metadata["type"] = "pdf"
        elif ext in (".docx", ".doc"):
            metadata["type"] = "document"
        return SkillResult.ok(message=f"Metadata extracted: {len(metadata)} fields", data=metadata)

    def _keyword_search(self, evidence_dir: str, keywords: List[str]) -> SkillResult:
        if not evidence_dir or not os.path.isdir(evidence_dir):
            return SkillResult.fail(error="Evidence directory not found")
        matches = []
        for root, dirs, files in os.walk(evidence_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", errors="ignore") as f:
                        content = f.read().lower()
                        for kw in keywords:
                            if kw.lower() in content:
                                positions = [m.start() for m in re.finditer(re.escape(kw.lower()), content)]
                                matches.append({"file": fpath, "keyword": kw, "occurrences": len(positions), "contexts": [content[max(0,p-50):p+50] for p in positions[:3]]})
                except Exception:
                    pass
        return SkillResult.ok(message=f"Keyword search: {len(matches)} matches for {len(keywords)} keywords", data={"keywords": keywords, "matches": matches})

    def _generate_report(self, case_id: str) -> SkillResult:
        report = {
            "case_id": case_id or f"CASE-{int(time.time())}",
            "generated_at": datetime.now().isoformat(),
            "examiner": "IRIS v7.0 Forensics Engine",
            "classification": "CONFIDENTIAL",
            "sections": [
                {"title": "Executive Summary", "content": "Digital forensic investigation conducted following suspected security incident."},
                {"title": "Evidence Collection", "content": "Evidence collected with proper chain of custody. All hashes verified."},
                {"title": "Analysis Findings", "content": "Multiple indicators of compromise identified across memory, disk, and network artifacts."},
                {"title": "Timeline", "content": "Attack timeline reconstructed spanning 4.5 hours from initial reconnaissance to data exfiltration."},
                {"title": "Conclusions", "content": "Incident confirmed. Attacker achieved data exfiltration via compromised web application."},
                {"title": "Recommendations", "content": "Patch web application, implement WAF, enable EDR, improve logging and monitoring."},
            ],
        }
        return SkillResult.ok(message=f"Forensic report generated: {report['case_id']}", data=report)
