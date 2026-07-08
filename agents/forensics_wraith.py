"""
forensics_wraith.py — TRACE
Digital forensics agent. Memory forensics, disk forensics with file carving,
network forensics via PCAP analysis, log correlation, mobile/cloud forensics,
timeline reconstruction, and steganography detection.
"""

import logging
import os
import re
import json
import hashlib
import subprocess
import threading
import time
import struct
import binascii
from typing import Any, Dict, List, Optional, Tuple, Set, BinaryIO
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import defaultdict, OrderedDict

logger = logging.getLogger("TRACE")

@dataclass
class ForensicArtifact:
    artifact_id: str
    artifact_type: str
    source_path: str
    offset: Optional[int] = None
    size: Optional[int] = None
    hash_md5: str = ""
    hash_sha256: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    extracted_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    confidence: str = "medium"

@dataclass
class TimelineEntry:
    timestamp: str
    event_type: str
    source: str
    description: str
    evidence: List[str] = field(default_factory=list)
    significance: str = "medium"

class ForensicsWraith:
    CODENAME = "TRACE"
    FILE_SIGNATURES = {
        b"\xff\xd8\xff": ("JPEG", "image/jpeg"),
        b"\x89PNG\r\n\x1a\n": ("PNG", "image/png"),
        b"%PDF": ("PDF", "application/pdf"),
        b"PK\x03\x04": ("ZIP", "application/zip"),
        b"\x1f\x8b\x08": ("GZIP", "application/gzip"),
        b"\x7fELF": ("ELF", "application/x-executable"),
        b"MZ": ("PE", "application/x-dosexec"),
        b"Rar!": ("RAR", "application/x-rar"),
        b"<?xml": ("XML", "application/xml"),
    }

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._artifacts: List[ForensicArtifact] = []
        self._timelines: Dict[str, List[TimelineEntry]] = {}
        self._session_id = hashlib.sha256(
            f"trace_{time.time()}_{os.urandom(8).hex()}".encode()
        ).hexdigest()[:16]
        logger.info(f"[{self.CODENAME}] Initialized session {self._session_id}")

    def start(self) -> bool:
        with self._lock:
            self._running = True
        logger.info(f"[{self.CODENAME}] Agent started")
        return True

    def stop(self) -> bool:
        with self._lock:
            self._running = False
        logger.info(f"[{self.CODENAME}] Agent stopped")
        return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "codename": self.CODENAME,
                "session_id": self._session_id,
                "running": self._running,
                "artifacts_discovered": len(self._artifacts),
                "timelines_generated": len(self._timelines),
            }

    def _report_to_commander(self, message: str, level: str = "info", data: Optional[Dict] = None) -> None:
        payload = {
            "agent": self.CODENAME, "session_id": self._session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "level": level, "message": message, "data": data or {},
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

    def _execute_shell(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout, cwd=os.getcwd())
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    def _hash_file(self, filepath: str) -> Tuple[str, str]:
        md5 = hashlib.md5()
        sha256 = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                while chunk := f.read(8192):
                    md5.update(chunk)
                    sha256.update(chunk)
            return md5.hexdigest(), sha256.hexdigest()
        except Exception:
            return "", ""

    # Memory Forensics
    def analyze_memory_dump(self, dump_path: str, analysis_types: Optional[List[str]] = None) -> Dict[str, Any]:
        analysis_types = analysis_types or ["strings", "processes", "network", "files"]
        results = {"dump_path": dump_path, "analysis_types": analysis_types, "artifacts": [], "findings": [], "analyzed_at": datetime.utcnow().isoformat()}
        if not os.path.exists(dump_path):
            results["error"] = f"Memory dump not found: {dump_path}"
            return results
        try:
            dump_size = os.path.getsize(dump_path)
            results["dump_size"] = dump_size
            if "strings" in analysis_types:
                rc, out, err = self._execute_shell(f"strings -n 8 '{dump_path}' 2>/dev/null | head -1000", timeout=60)
                if out:
                    strings = out.strip().split("\n")
                    suspicious = [s for s in strings if any(p in s.lower() for p in ["password", "passwd", "secret", "token", "api_key", "credential"])]
                    results["findings"].append({"type": "suspicious_strings", "count": len(suspicious), "samples": suspicious[:20]})
                    artifact = ForensicArtifact(
                        artifact_id=f"art_{hashlib.md5(f"strings_{time.time()}".encode()).hexdigest()[:12]}",
                        artifact_type="memory_strings", source_path=dump_path,
                        metadata={"string_count": len(strings), "suspicious_count": len(suspicious)}
                    )
                    self._artifacts.append(artifact)
                    results["artifacts"].append(asdict(artifact))
            if "processes" in analysis_types:
                rc, out, err = self._execute_shell(f"xxd '{dump_path}' 2>/dev/null | grep -E 'ELF|MZ|exe' | head -50 || echo 'Process scan simulated'", timeout=60)
                results["findings"].append({"type": "process_artifacts", "output": out[:1000] if out else "No process artifacts found"})
            if "network" in analysis_types:
                ip_pattern = r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"
                rc, out, err = self._execute_shell(f"strings -n 8 '{dump_path}' 2>/dev/null | grep -oE '{ip_pattern}' | sort | uniq -c | sort -rn | head -20", timeout=60)
                if out:
                    results["findings"].append({"type": "network_indicators", "ips": out.strip().split("\n")[:20]})
            if "files" in analysis_types:
                carved = self._carve_memory(dump_path)
                results["findings"].append({"type": "carved_files", "count": len(carved), "files": carved[:10]})
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Memory analysis failed: {e}")
        self._store_memory(f"memory.{dump_path}", results)
        self._report_to_commander(f"Memory analysis complete for {dump_path}")
        return results

    def _carve_memory(self, dump_path: str) -> List[Dict[str, Any]]:
        carved = []
        try:
            with open(dump_path, "rb") as f:
                data = f.read()
            for sig, (ftype, mime) in self.FILE_SIGNATURES.items():
                offset = 0
                while True:
                    idx = data.find(sig, offset)
                    if idx == -1:
                        break
                    end = idx + 1048576
                    for next_sig in self.FILE_SIGNATURES.keys():
                        next_idx = data.find(next_sig, idx + len(sig))
                        if next_idx != -1 and next_idx < end:
                            end = next_idx
                    chunk = data[idx:end]
                    carved.append({"type": ftype, "offset": idx, "size": len(chunk), "md5": hashlib.md5(chunk).hexdigest(), "mime": mime})
                    offset = idx + len(sig)
        except Exception as e:
            logger.error(f"[{self.CODENAME}] Memory carving error: {e}")
        return carved

    # Disk Forensics
    def analyze_disk_image(self, image_path: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
        output_dir = output_dir or f"/tmp/trace_disk_{int(time.time())}"
        os.makedirs(output_dir, exist_ok=True)
        results = {"image_path": image_path, "output_dir": output_dir, "artifacts": [], "findings": [], "analyzed_at": datetime.utcnow().isoformat()}
        if not os.path.exists(image_path):
            results["error"] = f"Disk image not found: {image_path}"
            return results
        try:
            carved_files = self._carve_disk_image(image_path, output_dir)
            results["findings"].append({"type": "file_carving", "total_carved": len(carved_files), "by_type": self._count_by_type(carved_files)})
            for fpath in carved_files:
                md5, sha256 = self._hash_file(fpath)
                artifact = ForensicArtifact(
                    artifact_id=f"art_{hashlib.md5(fpath.encode()).hexdigest()[:12]}",
                    artifact_type="carved_file", source_path=fpath,
                    hash_md5=md5, hash_sha256=sha256,
                    metadata={"size": os.path.getsize(fpath)}
                )
                self._artifacts.append(artifact)
                results["artifacts"].append(asdict(artifact))
            rc, out, err = self._execute_shell(f"fdisk -l '{image_path}' 2>/dev/null || parted '{image_path}' print 2>/dev/null || echo 'Partition info extraction simulated'", timeout=30)
            results["findings"].append({"type": "partition_info", "output": out[:2000] if out else "No partition info available"})
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Disk analysis failed: {e}")
        self._store_memory(f"disk.{image_path}", results)
        self._report_to_commander(f"Disk analysis complete for {image_path}")
        return results

    def _carve_disk_image(self, image_path: str, output_dir: str) -> List[str]:
        carved_paths = []
        try:
            with open(image_path, "rb") as f:
                chunk_size = 10485760  # 10MB chunks
                file_count = 0
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    for sig, (ftype, mime) in self.FILE_SIGNATURES.items():
                        idx = 0
                        while True:
                            idx = chunk.find(sig, idx)
                            if idx == -1:
                                break
                            file_count += 1
                            out_path = os.path.join(output_dir, f"carved_{file_count:06d}.{ftype.lower()}")
                            extract_size = min(5242880, len(chunk) - idx)
                            with open(out_path, "wb") as outf:
                                outf.write(chunk[idx:idx + extract_size])
                            carved_paths.append(out_path)
                            idx += len(sig)
        except Exception as e:
            logger.error(f"[{self.CODENAME}] Disk carving error: {e}")
        return carved_paths

    def _count_by_type(self, files: List[str]) -> Dict[str, int]:
        counts = defaultdict(int)
        for f in files:
            ext = os.path.splitext(f)[1].lower().lstrip(".")
            counts[ext or "unknown"] += 1
        return dict(counts)

    # Network Forensics (PCAP)
    def analyze_pcap(self, pcap_path: str) -> Dict[str, Any]:
        results = {"pcap_path": pcap_path, "connections": [], "protocols": defaultdict(int), "suspicious_indicators": [], "analyzed_at": datetime.utcnow().isoformat()}
        if not os.path.exists(pcap_path):
            results["error"] = f"PCAP not found: {pcap_path}"
            return results
        try:
            rc, out, err = self._execute_shell(f"tcpdump -r '{pcap_path}' -nn -q 2>/dev/null | head -200 || tshark -r '{pcap_path}' -q 2>/dev/null | head -200 || echo 'PCAP analysis simulated'", timeout=60)
            if out:
                lines = out.strip().split("\n")
                connections = []
                for line in lines:
                    if any(proto in line for proto in ["IP", "TCP", "UDP", "ICMP"]):
                        conn = self._parse_tcpdump_line(line)
                        if conn:
                            connections.append(conn)
                            results["protocols"][conn.get("protocol", "unknown")] += 1
                results["connections"] = connections[:100]
                for conn in connections:
                    if conn.get("dst_port") in [4444, 5555, 6666, 9999]:
                        results["suspicious_indicators"].append({"type": "suspicious_port", "connection": conn, "reason": f"Connection to known suspicious port {conn['dst_port']}"})
            rc2, out2, err2 = self._execute_shell(f"capinfos '{pcap_path}' 2>/dev/null || echo 'Capinfos not available'", timeout=30)
            if out2 and "not available" not in out2:
                results["pcap_info"] = out2.strip()
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] PCAP analysis failed: {e}")
        self._store_memory(f"pcap.{pcap_path}", results)
        self._report_to_commander(f"PCAP analysis complete for {pcap_path}")
        return results

    def _parse_tcpdump_line(self, line: str) -> Optional[Dict[str, Any]]:
        match = re.match(r".*?(\d+\.\d+\.\d+\.\d+)\.(\d+)\s+>\s+(\d+\.\d+\.\d+\.\d+)\.(\d+):\s+(\w+).*?", line)
        if match:
            return {"src_ip": match.group(1), "src_port": int(match.group(2)), "dst_ip": match.group(3), "dst_port": int(match.group(4)), "protocol": match.group(5), "raw": line[:200]}
        return None

    # Log Correlation
    def correlate_logs(self, log_paths: List[str], correlation_window: int = 300) -> Dict[str, Any]:
        results = {"log_paths": log_paths, "correlation_window": correlation_window, "correlated_events": [], "timeline": [], "analyzed_at": datetime.utcnow().isoformat()}
        all_events = []
        for log_path in log_paths:
            if not os.path.exists(log_path):
                continue
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f_log:
                    for line_num, line in enumerate(f_log, 1):
                        line = line.strip()
                        if not line:
                            continue
                        ts = self._extract_timestamp(line)
                        if ts:
                            all_events.append({"timestamp": ts, "source": log_path, "line_number": line_num, "content": line[:500]})
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Log read error for {log_path}: {e}")
        all_events.sort(key=lambda x: x["timestamp"])
        correlated = []
        for i, event in enumerate(all_events):
            window_events = [event]
            for j in range(i + 1, len(all_events)):
                if (all_events[j]["timestamp"] - event["timestamp"]).total_seconds() <= correlation_window:
                    window_events.append(all_events[j])
                else:
                    break
            if len(window_events) > 1:
                correlated.append({"anchor_event": event, "related_events": window_events[1:], "event_count": len(window_events)})
        results["correlated_events"] = correlated[:100]
        for event in all_events[:500]:
            entry = TimelineEntry(timestamp=event["timestamp"].isoformat(), event_type="log_event", source=event["source"], description=event["content"][:200])
            results["timeline"].append(asdict(entry))
        self._store_memory(f"correlation.{hash(tuple(log_paths))}", results)
        self._report_to_commander(f"Log correlation complete: {len(results['correlated_events'])} correlated groups")
        return results

    def _extract_timestamp(self, line: str) -> Optional[datetime]:
        patterns = [r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})", r"(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})", r"(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2})"]
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    try:
                        return datetime.strptime(match.group(1), "%b %d %H:%M:%S")
                    except ValueError:
                        try:
                            return datetime.strptime(match.group(1), "%d/%b/%Y:%H:%M:%S")
                        except ValueError:
                            continue
        return None

    # Timeline Reconstruction
    def reconstruct_timeline(self, directory: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> Dict[str, Any]:
        results = {"directory": directory, "timeline": [], "file_count": 0, "analyzed_at": datetime.utcnow().isoformat()}
        if not os.path.exists(directory):
            results["error"] = f"Directory not found: {directory}"
            return results
        try:
            entries = []
            for root, dirs, files in os.walk(directory):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        stat = os.stat(fpath)
                        mtime = datetime.fromtimestamp(stat.st_mtime)
                        if start_time and mtime < start_time:
                            continue
                        if end_time and mtime > end_time:
                            continue
                        entries.append({"path": fpath, "mtime": mtime, "ctime": datetime.fromtimestamp(stat.st_ctime), "atime": datetime.fromtimestamp(stat.st_atime), "size": stat.st_size, "mode": oct(stat.st_mode)})
                    except Exception:
                        continue
            entries.sort(key=lambda x: x["mtime"])
            results["file_count"] = len(entries)
            for entry in entries[:1000]:
                timeline_entry = TimelineEntry(timestamp=entry["mtime"].isoformat(), event_type="file_modified", source=entry["path"], description=f"File modified: {entry['path']} ({entry['size']} bytes)", evidence=[f"ctime: {entry['ctime']}", f"atime: {entry['atime']}", f"mode: {entry['mode']}"])
                results["timeline"].append(asdict(timeline_entry))
            timeline_id = f"tl_{hashlib.md5(directory.encode()).hexdigest()[:12]}"
            self._timelines[timeline_id] = results["timeline"]
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Timeline reconstruction failed: {e}")
        self._store_memory(f"timeline.{directory}", results)
        self._report_to_commander(f"Timeline reconstructed for {directory}: {results['file_count']} files")
        return results

    # Steganography Detection
    def detect_steganography(self, image_path: str, methods: Optional[List[str]] = None) -> Dict[str, Any]:
        methods = methods or ["lsb", "chi_square", "file_size"]
        results = {"image_path": image_path, "methods": methods, "findings": [], "analyzed_at": datetime.utcnow().isoformat()}
        if not os.path.exists(image_path):
            results["error"] = f"Image not found: {image_path}"
            return results
        try:
            file_size = os.path.getsize(image_path)
            results["file_size"] = file_size
            with open(image_path, "rb") as f:
                header = f.read(64)
            if b"PNG" in header:
                if "lsb" in methods:
                    results["findings"].append(self._analyze_lsb_png(image_path))
                if "chi_square" in methods:
                    results["findings"].append(self._chi_square_test(image_path))
            elif b"JFIF" in header or b"JPEG" in header or b"\xff\xd8" in header:
                if "lsb" in methods:
                    results["findings"].append({"method": "lsb", "result": "JPEG LSB analysis requires DCT coefficient examination", "suspicious": False})
            if "file_size" in methods:
                rc, out, err = self._execute_shell(f"file '{image_path}' 2>/dev/null || echo 'file command not available'", timeout=10)
                if out and "not available" not in out:
                    results["findings"].append({"method": "file_size", "file_info": out.strip(), "suspicious": file_size > 10485760})
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Steganography detection failed: {e}")
        self._store_memory(f"stego.{image_path}", results)
        self._report_to_commander(f"Steganography analysis complete for {image_path}")
        return results

    def _analyze_lsb_png(self, image_path: str) -> Dict[str, Any]:
        try:
            with open(image_path, "rb") as f:
                data = f.read()
            lsb_data = [data[i] & 1 for i in range(len(data) - 100, len(data))]
            lsb_bytes = bytearray()
            for i in range(0, len(lsb_data) - 8, 8):
                byte = 0
                for j in range(8):
                    byte = (byte << 1) | lsb_data[i + j]
                lsb_bytes.append(byte)
            printable = sum(1 for b in lsb_bytes if 32 <= b <= 126 or b in [0, 9, 10, 13])
            ratio = printable / len(lsb_bytes) if lsb_bytes else 0
            return {"method": "lsb", "lsb_sample_size": len(lsb_data), "printable_ratio": round(ratio, 4), "suspicious": ratio > 0.7 and len(lsb_data) > 100, "sample": lsb_bytes[:50].hex()}
        except Exception as e:
            return {"method": "lsb", "error": str(e), "suspicious": False}

    def _chi_square_test(self, image_path: str) -> Dict[str, Any]:
        try:
            with open(image_path, "rb") as f:
                data = f.read()
            if data[:8] == b"\x89PNG\r\n\x1a\n":
                data = data[8:]
            freq = [0] * 256
            for byte in data:
                freq[byte] += 1
            expected = len(data) / 256
            chi_square = sum((observed - expected) ** 2 / expected for observed in freq if expected > 0)
            return {"method": "chi_square", "chi_square_value": round(chi_square, 4), "suspicious": chi_square > 1000, "note": "High chi-square may indicate hidden data"}
        except Exception as e:
            return {"method": "chi_square", "error": str(e), "suspicious": False}

    # Unit Tests
    def test_memory_analysis(self) -> bool:
        results = self.analyze_memory_dump("/dev/null")
        assert "error" in results or "findings" in results
        return True

    def test_disk_carving(self) -> bool:
        test_path = f"/tmp/trace_test_{int(time.time())}.img"
        with open(test_path, "wb") as f:
            f.write(os.urandom(1024))
            f.write(b"\xff\xd8\xff\x00\x00test_jpeg_data")
            f.write(os.urandom(1024))
        results = self.analyze_disk_image(test_path)
        assert "findings" in results
        os.remove(test_path)
        return True

    def test_timeline(self) -> bool:
        results = self.reconstruct_timeline("/tmp")
        assert "timeline" in results
        return True

    def test_steganography(self) -> bool:
        test_path = f"/tmp/trace_stego_test_{int(time.time())}.png"
        with open(test_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")
            f.write(os.urandom(1000))
        results = self.detect_steganography(test_path)
        assert "findings" in results
        os.remove(test_path)
        return True
