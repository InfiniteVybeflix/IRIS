"""
IRIS v7.0 — Wireshark Parser

PCAP file analysis without Wireshark GUI. Uses scapy and dpkt.
Conversation extraction, anomaly detection, file reconstruction, BPF filters.

Dependencies: scapy
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class WiresharkParser(BaseTool):
    """PCAP/PCAPNG file analyzer. Read-only."""

    name: str = "wireshark_parser"
    category: str = "forensics"
    dependencies: List[str] = ["scapy"]

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._packets: List[Any] = []
        self._filepath: Optional[str] = None

    def _load_scapy(self) -> Any:
        try:
            import scapy.all as scapy
            return scapy
        except ImportError:
            return None

    def _run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {}

    def read_pcap(self, filepath: str) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_path = os.path.abspath(os.path.expanduser(filepath))
            if not os.path.exists(safe_path):
                res = self._build_result(success=False, action="read_pcap", errors=[f"File not found: {safe_path}"])
                self.last_result = res
                self._end_execution(False)
                return res
            scapy = self._load_scapy()
            if scapy is None:
                res = self._build_result(success=False, action="read_pcap", errors=["scapy not installed."])
                self.last_result = res
                self._end_execution(False)
                return res
            self._packets = scapy.rdpcap(safe_path)
            self._filepath = safe_path
            protocols: Dict[str, int] = defaultdict(int)
            total_bytes = 0
            for pkt in self._packets:
                total_bytes += len(pkt)
                if pkt.haslayer(scapy.IP):
                    proto = {6: "TCP", 17: "UDP", 1: "ICMP", 2: "IGMP"}.get(pkt[scapy.IP].proto, f"IP-{pkt[scapy.IP].proto}")
                    protocols[proto] += 1
                elif pkt.haslayer(scapy.ARP):
                    protocols["ARP"] += 1
                else:
                    protocols["OTHER"] += 1
            res = self._build_result(success=True, action="read_pcap",
                output=f"Loaded {len(self._packets)} packets from {safe_path}",
                parsed={"filepath": safe_path, "packet_count": len(self._packets), "total_bytes": total_bytes,
                    "protocols": dict(protocols), "file_hash": self._hash_file(safe_path)})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("read_pcap failed")
            res = self._build_result(success=False, action="read_pcap", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def extract_conversations(self) -> Dict[str, Any]:
        self._begin_execution()
        try:
            if not self._packets:
                res = self._build_result(success=False, action="extract_conversations", errors=["No PCAP loaded."])
                self.last_result = res
                self._end_execution(False)
                return res
            scapy = self._load_scapy()
            if scapy is None:
                res = self._build_result(success=False, action="extract_conversations", errors=["scapy not installed."])
                self.last_result = res
                self._end_execution(False)
                return res
            conversations: Dict[str, Dict[str, Any]] = {}
            for pkt in self._packets:
                if not pkt.haslayer(scapy.IP):
                    continue
                ip = pkt[scapy.IP]
                proto_key = src_port = dst_port = None
                if ip.haslayer(scapy.TCP):
                    tcp = ip[scapy.TCP]
                    src_port, dst_port = tcp.sport, tcp.dport
                    proto_key = "TCP"
                elif ip.haslayer(scapy.UDP):
                    udp = ip[scapy.UDP]
                    src_port, dst_port = udp.sport, udp.dport
                    proto_key = "UDP"
                else:
                    continue
                endpoints = sorted([(ip.src, src_port), (ip.dst, dst_port)])
                flow_key = f"{proto_key}:{endpoints[0][0]}:{endpoints[0][1]}<->{endpoints[1][0]}:{endpoints[1][1]}"
                if flow_key not in conversations:
                    conversations[flow_key] = {"protocol": proto_key, "src": endpoints[0][0], "src_port": endpoints[0][1],
                        "dst": endpoints[1][0], "dst_port": endpoints[1][1], "packet_count": 0, "byte_count": 0}
                conversations[flow_key]["packet_count"] += 1
                conversations[flow_key]["byte_count"] += len(pkt)
            res = self._build_result(success=True, action="extract_conversations", output=list(conversations.keys()),
                parsed={"conversation_count": len(conversations), "conversations": list(conversations.values())})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("extract_conversations failed")
            res = self._build_result(success=False, action="extract_conversations", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def detect_anomalies(self) -> Dict[str, Any]:
        self._begin_execution()
        try:
            if not self._packets:
                res = self._build_result(success=False, action="detect_anomalies", errors=["No PCAP loaded."])
                self.last_result = res
                self._end_execution(False)
                return res
            scapy = self._load_scapy()
            if scapy is None:
                res = self._build_result(success=False, action="detect_anomalies", errors=["scapy not installed."])
                self.last_result = res
                self._end_execution(False)
                return res
            anomalies: List[Dict[str, Any]] = []
            src_dst_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
            large_packets = 0
            for pkt in self._packets:
                if pkt.haslayer(scapy.IP):
                    ip = pkt[scapy.IP]
                    src_dst_counts[ip.src][ip.dst] += 1
                    if len(pkt) > 1500:
                        large_packets += 1
            for src, dsts in src_dst_counts.items():
                if len(dsts) > 50:
                    anomalies.append({"type": "potential_port_scan", "source": src,
                        "unique_destinations": len(dsts), "severity": "high" if len(dsts) > 200 else "medium"})
            if large_packets > 100:
                anomalies.append({"type": "large_packets", "count": large_packets, "severity": "low"})
            res = self._build_result(success=True, action="detect_anomalies", output=anomalies,
                parsed={"anomaly_count": len(anomalies), "anomalies": anomalies})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("detect_anomalies failed")
            res = self._build_result(success=False, action="detect_anomalies", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def extract_files(self) -> Dict[str, Any]:
        self._begin_execution()
        try:
            if not self._packets:
                res = self._build_result(success=False, action="extract_files", errors=["No PCAP loaded."])
                self.last_result = res
                self._end_execution(False)
                return res
            scapy = self._load_scapy()
            if scapy is None:
                res = self._build_result(success=False, action="extract_files", errors=["scapy not installed."])
                self.last_result = res
                self._end_execution(False)
                return res
            extracted: List[Dict[str, Any]] = []
            for pkt in self._packets:
                if pkt.haslayer(scapy.TCP) and pkt.haslayer(scapy.Raw):
                    payload = bytes(pkt[scapy.Raw].load)
                    if payload.startswith(b"HTTP/"):
                        header_end = payload.find(b"\r\n\r\n")
                        if header_end > 0:
                            headers = payload[:header_end].decode("utf-8", errors="ignore")
                            body = payload[header_end + 4:]
                            content_type = ""
                            for line in headers.split("\r\n"):
                                if line.lower().startswith("content-type:"):
                                    content_type = line.split(":", 1)[1].strip()
                                    break
                            if body and len(body) > 100:
                                extracted.append({"type": "http_response", "content_type": content_type,
                                    "size": len(body), "hash": hashlib.sha256(body).hexdigest()[:16]})
            res = self._build_result(success=True, action="extract_files", output=extracted,
                parsed={"extracted_count": len(extracted), "files": extracted})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("extract_files failed")
            res = self._build_result(success=False, action="extract_files", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def filter_traffic(self, display_filter: str) -> Dict[str, Any]:
        self._begin_execution()
        try:
            if not self._packets:
                res = self._build_result(success=False, action="filter_traffic", errors=["No PCAP loaded."])
                self.last_result = res
                self._end_execution(False)
                return res
            scapy = self._load_scapy()
            if scapy is None:
                res = self._build_result(success=False, action="filter_traffic", errors=["scapy not installed."])
                self.last_result = res
                self._end_execution(False)
                return res
            try:
                filtered = scapy.sniff(offline=self._filepath, filter=display_filter)
            except Exception:
                filtered = []
                for pkt in self._packets:
                    if display_filter == "tcp" and pkt.haslayer(scapy.TCP):
                        filtered.append(pkt)
                    elif display_filter == "udp" and pkt.haslayer(scapy.UDP):
                        filtered.append(pkt)
                    elif display_filter == "icmp" and pkt.haslayer(scapy.ICMP):
                        filtered.append(pkt)
                    else:
                        filtered.append(pkt)
            res = self._build_result(success=True, action="filter_traffic",
                output=f"Filter matched {len(filtered)} packets",
                parsed={"filter": display_filter, "matched_count": len(filtered), "total_count": len(self._packets)})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("filter_traffic failed")
            res = self._build_result(success=False, action="filter_traffic", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def _hash_file(self, filepath: str) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()


__all__ = ["WiresharkParser"]
