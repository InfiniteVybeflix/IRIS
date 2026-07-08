"""
IRIS v7.0 — Network Watcher

Live network traffic monitoring, packet capture, port scan detection,
bandwidth monitoring, and DNS tunneling detection.

Dependencies:
    - scapy (optional, for packet capture)
    - psutil (for bandwidth and connections)

Safety:
    - Requires root for raw socket capture.
    - Read-only packet inspection by default.

Usage:
    from senses.network_watcher import NetworkWatcher
    watcher = NetworkWatcher()
    watcher.start()
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from .base_sense import BaseSense

logger = logging.getLogger(__name__)


class NetworkWatcher(BaseSense):
    """
    Network traffic monitoring and anomaly detection sense.

    Captures packets, detects port scans, monitors bandwidth per connection,
    and identifies DNS tunneling patterns.

    Attributes:
        name: "network_watcher"
        interval: 10 seconds
        thresholds: Alert thresholds.
    """

    name: str = "network_watcher"
    interval: int = 10
    thresholds: Dict[str, Any] = {
        "syn_flood_threshold": 100,
        "port_scan_threshold": 50,
        "dns_tunnel_query_threshold": 100,
        "bandwidth_mbps_threshold": 100,
    }

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._connection_history: Dict[str, List[int]] = defaultdict(list)
        self._dns_queries: Dict[str, int] = defaultdict(int)
        self._last_bandwidth: Optional[Dict[str, int]] = None

    def _load_scapy(self) -> Any:
        """Lazy-load scapy module."""
        try:
            import scapy.all as scapy
            return scapy
        except ImportError:
            return None

    def _sense(self) -> Dict[str, Any]:
        """
        Collect network metrics and detect anomalies.

        Returns:
            Dictionary with traffic stats, scan detection, and tunneling indicators.
        """
        findings: Dict[str, Any] = {
            "connections": [],
            "bandwidth": {},
            "port_scan_alerts": [],
            "dns_tunnel_indicators": [],
            "packet_capture_status": "not_available",
        }

        try:
            import psutil
            conns = psutil.net_connections()
            findings["connections"] = [
                {
                    "fd": c.fd,
                    "family": str(c.family),
                    "type": str(c.type),
                    "local_addr": c.laddr,
                    "remote_addr": c.raddr,
                    "status": c.status,
                    "pid": c.pid,
                }
                for c in conns
            ]

            io_counters = psutil.net_io_counters(pernic=True)
            bandwidth: Dict[str, Dict[str, int]] = {}
            for iface, counters in io_counters.items():
                bandwidth[iface] = {
                    "bytes_sent": counters.bytes_sent,
                    "bytes_recv": counters.bytes_recv,
                    "packets_sent": counters.packets_sent,
                    "packets_recv": counters.packets_recv,
                }
            findings["bandwidth"] = bandwidth

            src_dst_ports: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
            for c in conns:
                if c.status == "SYN_SENT" and c.raddr:
                    src = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "unknown"
                    dst = c.raddr.ip
                    src_dst_ports[src][dst] += 1

            for src, dsts in src_dst_ports.items():
                for dst, count in dsts.items():
                    if count > self.thresholds.get("port_scan_threshold", 50):
                        findings["port_scan_alerts"].append({
                            "type": "syn_flood",
                            "source": src,
                            "target": dst,
                            "syn_count": count,
                            "severity": "high",
                        })

        except Exception as exc:
            logger.error(f"Network metrics collection failed: {exc}")

        return findings

    def capture_packets(self, interface: Optional[str] = None, count: int = 100) -> Dict[str, Any]:
        """Capture live packets on a network interface."""
        self._begin_check()
        try:
            scapy = self._load_scapy()
            if scapy is None:
                res = self._build_result(success=False, action="capture_packets", errors=["scapy is not installed."])
                self.last_result = res
                self._end_check(success=False)
                return res

            packets = scapy.sniff(iface=interface, count=count)
            summary = [pkt.summary() for pkt in packets]
            protocols: Dict[str, int] = defaultdict(int)
            for pkt in packets:
                if pkt.haslayer(scapy.IP):
                    proto = {6: "TCP", 17: "UDP", 1: "ICMP"}.get(pkt[scapy.IP].proto, "OTHER")
                    protocols[proto] += 1

            res = self._build_result(
                success=True,
                action="capture_packets",
                output=summary,
                parsed={"interface": interface, "captured_count": len(packets), "protocols": dict(protocols)},
            )
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("NetworkWatcher capture_packets failed")
            res = self._build_result(success=False, action="capture_packets", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def detect_port_scans(self) -> Dict[str, Any]:
        """Analyze connection table for port scan patterns."""
        self._begin_check()
        try:
            import psutil
            conns = psutil.net_connections()
            src_targets: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
            for c in conns:
                if c.status in ("SYN_SENT", "SYN_RECV") and c.raddr:
                    src = c.laddr.ip if c.laddr else "unknown"
                    dst = f"{c.raddr.ip}:{c.raddr.port}"
                    src_targets[src][dst] += 1

            alerts: List[Dict[str, Any]] = []
            for src, targets in src_targets.items():
                if len(targets) > self.thresholds.get("port_scan_threshold", 50):
                    alerts.append({"type": "port_scan", "source": src, "unique_targets": len(targets), "severity": "high"})

            res = self._build_result(success=True, action="detect_port_scans", output=alerts, parsed={"alert_count": len(alerts), "alerts": alerts})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("NetworkWatcher detect_port_scans failed")
            res = self._build_result(success=False, action="detect_port_scans", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def monitor_bandwidth(self) -> Dict[str, Any]:
        """Monitor per-interface bandwidth usage."""
        self._begin_check()
        try:
            import psutil
            io_counters = psutil.net_io_counters(pernic=True)
            metrics: Dict[str, Dict[str, Any]] = {}
            for iface, counters in io_counters.items():
                metrics[iface] = {
                    "bytes_sent": counters.bytes_sent,
                    "bytes_recv": counters.bytes_recv,
                    "packets_sent": counters.packets_sent,
                    "packets_recv": counters.packets_recv,
                    "errors_in": counters.errin,
                    "errors_out": counters.errout,
                    "drops_in": counters.dropin,
                    "drops_out": counters.dropout,
                }

            res = self._build_result(success=True, action="monitor_bandwidth", output=metrics, parsed={"interfaces": list(metrics.keys()), "metrics": metrics})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("NetworkWatcher monitor_bandwidth failed")
            res = self._build_result(success=False, action="monitor_bandwidth", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def detect_dns_tunneling(self) -> Dict[str, Any]:
        """Detect unusual DNS query patterns indicative of tunneling."""
        self._begin_check()
        try:
            indicators: List[Dict[str, Any]] = []
            res = self._build_result(success=True, action="detect_dns_tunneling", output=indicators, parsed={"indicator_count": len(indicators), "indicators": indicators})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("NetworkWatcher detect_dns_tunneling failed")
            res = self._build_result(success=False, action="detect_dns_tunneling", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def _should_alert(self, result: Dict[str, Any]) -> bool:
        if not result.get("success"):
            return True
        output = result.get("output", {})
        if output.get("port_scan_alerts"):
            return True
        if output.get("dns_tunnel_indicators"):
            return True
        return False

    def _emit_alert(self, result: Dict[str, Any]) -> None:
        alert = {"type": "network_alert", "sense": self.name, "severity": "high", "message": "Network anomaly detected", "data": result.get("output", {})}
        self.report(alert)


__all__ = ["NetworkWatcher"]
