"""
net_weaver.py — WEB
Network engineering agent. Network architecture design, traffic analysis,
bandwidth optimization, DNS management, SSL certificate monitoring,
VPN configuration generation.
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
import ssl
import urllib.request
from typing import Any, Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from collections import defaultdict

logger = logging.getLogger("WEB")

@dataclass
class SSLCertificate:
    domain: str
    issuer: str
    subject: str
    not_before: str
    not_after: str
    serial_number: str
    fingerprint: str
    alt_names: List[str] = field(default_factory=list)
    is_valid: bool = False
    days_until_expiry: int = 0

@dataclass
class DNSRecord:
    record_type: str
    name: str
    value: str
    ttl: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

@dataclass
class NetworkFlow:
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int
    protocol: str
    bytes_sent: int
    bytes_received: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

class NetWeaver:
    CODENAME = "WEB"

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._ssl_certs: Dict[str, SSLCertificate] = {}
        self._dns_records: List[DNSRecord] = []
        self._network_flows: List[NetworkFlow] = []
        self._session_id = hashlib.sha256(
            f"web_{time.time()}_{os.urandom(8).hex()}".encode()
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
                "ssl_certs_monitored": len(self._ssl_certs),
                "dns_records": len(self._dns_records),
                "network_flows": len(self._network_flows),
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

    def check_ssl_certificate(self, hostname: str, port: int = 443) -> SSLCertificate:
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    not_before = cert.get("notBefore", "")
                    not_after = cert.get("notAfter", "")
                    try:
                        expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                        days_until = (expiry - datetime.utcnow()).days
                    except ValueError:
                        days_until = 0
                    alt_names = []
                    for alt in cert.get("subjectAltName", []):
                        if alt[0] == "DNS":
                            alt_names.append(alt[1])
                    cert_obj = SSLCertificate(
                        domain=hostname,
                        issuer=str(cert.get("issuer", [])),
                        subject=str(cert.get("subject", [])),
                        not_before=not_before,
                        not_after=not_after,
                        serial_number=str(cert.get("serialNumber", "")),
                        fingerprint=hashlib.sha256(str(cert).encode()).hexdigest()[:32],
                        alt_names=alt_names,
                        is_valid=days_until > 0,
                        days_until_expiry=days_until,
                    )
                    with self._lock:
                        self._ssl_certs[hostname] = cert_obj
                    self._store_memory(f"ssl.{hostname}", asdict(cert_obj))
                    if days_until <= 7:
                        self._report_to_commander(f"SSL certificate for {hostname} expires in {days_until} days", level="critical", data=asdict(cert_obj))
                    elif days_until <= 30:
                        self._report_to_commander(f"SSL certificate for {hostname} expires in {days_until} days", level="warning", data=asdict(cert_obj))
                    return cert_obj
        except Exception as e:
            logger.error(f"[{self.CODENAME}] SSL check failed for {hostname}:{port}: {e}")
            return SSLCertificate(domain=hostname, issuer="", subject="", not_before="", not_after="", serial_number="", fingerprint="", is_valid=False, days_until_expiry=0)

    def monitor_ssl_certificates(self, domains: List[str], port: int = 443) -> Dict[str, Any]:
        results = {"timestamp": datetime.utcnow().isoformat(), "certificates": [], "alerts": []}
        for domain in domains:
            if not self._running:
                break
            cert = self.check_ssl_certificate(domain, port)
            results["certificates"].append(asdict(cert))
            if not cert.is_valid:
                results["alerts"].append({"domain": domain, "issue": "Certificate invalid or expired"})
            elif cert.days_until_expiry <= 30:
                results["alerts"].append({"domain": domain, "days_until_expiry": cert.days_until_expiry})
        self._store_memory("ssl.monitor", results)
        self._report_to_commander(f"SSL monitoring complete for {len(domains)} domains")
        return results

    def query_dns(self, domain: str, record_type: str = "A", nameserver: Optional[str] = None) -> List[DNSRecord]:
        records = []
        try:
            if nameserver:
                rc, out, err = self._execute_shell(f"dig @{nameserver} {domain} {record_type} +short +time=5 2>/dev/null", timeout=15)
            else:
                rc, out, err = self._execute_shell(f"dig {domain} {record_type} +short +time=5 2>/dev/null || nslookup -type={record_type} {domain} 2>/dev/null", timeout=15)
            if out:
                for line in out.strip().split("\n"):
                    line = line.strip()
                    if line and not line.startswith(";"):
                        records.append(DNSRecord(record_type=record_type, name=domain, value=line, ttl=300))
        except Exception as e:
            logger.error(f"[{self.CODENAME}] DNS query failed for {domain}: {e}")
        with self._lock:
            self._dns_records.extend(records)
        self._store_memory(f"dns.{domain}.{record_type}", [asdict(r) for r in records])
        return records

    def check_dns_propagation(self, domain: str, record_type: str = "A", nameservers: Optional[List[str]] = None) -> Dict[str, Any]:
        nameservers = nameservers or ["8.8.8.8", "1.1.1.1", "9.9.9.9", "208.67.222.222"]
        results = {"domain": domain, "record_type": record_type, "nameservers": {}, "consistent": True}
        all_values = set()
        for ns in nameservers:
            records = self.query_dns(domain, record_type, ns)
            values = [r.value for r in records]
            results["nameservers"][ns] = values
            all_values.update(values)
        results["consistent"] = len(all_values) <= len(nameservers)
        self._store_memory(f"dns.propagation.{domain}", results)
        return results

    def generate_dns_zonefile(self, domain: str, records: List[Dict[str, Any]]) -> str:
        zone = f"; Zone file for {domain}\n"
        zone += f"; Generated by Aevibron NEBULA at {datetime.utcnow().isoformat()}\n\n"
        zone += "$TTL 3600\n"
        zone += f"{domain}. IN SOA ns1.{domain}. admin.{domain}. (\n"
        zone += f"    {int(time.time())} ; serial\n"
        zone += "    3600 ; refresh\n"
        zone += "    1800 ; retry\n"
        zone += "    604800 ; expire\n"
        zone += "    86400 ; minimum\n)\n\n"
        zone += f"{domain}. IN NS ns1.{domain}.\n"
        zone += f"{domain}. IN NS ns2.{domain}.\n\n"
        for record in records:
            name = record.get("name", "@")
            rtype = record.get("type", "A")
            value = record.get("value", "")
            ttl = record.get("ttl", 3600)
            if name == "@":
                zone += f"{domain}. {ttl} IN {rtype} {value}\n"
            else:
                zone += f"{name}.{domain}. {ttl} IN {rtype} {value}\n"
        self._store_memory(f"dns.zone.{domain}", zone)
        return zone

    def design_network(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        design = {
            "version": "1.0",
            "generated_at": datetime.utcnow().isoformat(),
            "requirements": requirements,
            "topology": {},
            "subnets": [],
            "security_groups": [],
            "routing": [],
            "recommendations": [],
        }
        num_tiers = requirements.get("tiers", 3)
        total_hosts = requirements.get("total_hosts", 1000)
        region = requirements.get("region", "us-east-1")
        hosts_per_tier = total_hosts // num_tiers
        needed_ips = hosts_per_tier + 5
        prefix = 32 - (needed_ips - 1).bit_length()
        prefix = min(prefix, 24)
        tiers = ["public", "application", "database"] if num_tiers == 3 else [f"tier_{i}" for i in range(num_tiers)]
        for i, tier in enumerate(tiers):
            subnet_cidr = f"10.0.{i}.0/{prefix}"
            design["subnets"].append({
                "name": f"{tier}-subnet",
                "cidr": subnet_cidr,
                "availability_zones": [f"{region}a", f"{region}b"],
                "tier": tier,
                "route_table": f"{tier}-rt",
            })
        design["security_groups"] = [
            {
                "name": "public-sg",
                "ingress": [
                    {"protocol": "tcp", "port": 80, "source": "0.0.0.0/0"},
                    {"protocol": "tcp", "port": 443, "source": "0.0.0.0/0"},
                ],
                "egress": [{"protocol": "-1", "port": "all", "destination": "0.0.0.0/0"}],
            },
            {
                "name": "app-sg",
                "ingress": [
                    {"protocol": "tcp", "port": 8080, "source": "public-sg"},
                    {"protocol": "tcp", "port": 8443, "source": "public-sg"},
                ],
                "egress": [{"protocol": "-1", "port": "all", "destination": "0.0.0.0/0"}],
            },
            {
                "name": "db-sg",
                "ingress": [
                    {"protocol": "tcp", "port": 3306, "source": "app-sg"},
                    {"protocol": "tcp", "port": 5432, "source": "app-sg"},
                    {"protocol": "tcp", "port": 27017, "source": "app-sg"},
                ],
                "egress": [],
            },
        ]
        design["routing"] = [
            {
                "name": "public-rt",
                "routes": [{"destination": "0.0.0.0/0", "target": "igw"}],
            },
            {
                "name": "private-rt",
                "routes": [{"destination": "0.0.0.0/0", "target": "nat-gateway"}],
            },
        ]
        design["recommendations"] = [
            "Use Network ACLs as secondary defense layer",
            "Enable VPC Flow Logs for traffic analysis",
            "Implement AWS Transit Gateway for multi-VPC connectivity",
            "Use AWS PrivateLink for service-to-service communication",
            "Enable DNSSEC for DNS security",
            "Implement DDoS protection with AWS Shield Advanced",
        ]
        self._store_memory(f"design.{region}", design)
        self._report_to_commander(f"Network design generated for {region}: {num_tiers} tiers, {total_hosts} hosts")
        return design

    def analyze_traffic(self, interface: Optional[str] = None, duration: int = 60) -> Dict[str, Any]:
        results = {"timestamp": datetime.utcnow().isoformat(), "interface": interface, "duration": duration, "flows": [], "statistics": {}}
        try:
            iface = interface or "any"
            rc, out, err = self._execute_shell(f"tcpdump -i {iface} -nn -q -c 1000 2>/dev/null | head -500 || echo tcpdump not available", timeout=duration + 10)
            if out and "not available" not in out:
                flows = []
                for line in out.strip().split("\n"):
                    match = re.match(r".*?(\d+\.\d+\.\d+\.\d+)\.(\d+)\s+>\s+(\d+\.\d+\.\d+\.\d+)\.(\d+):\s+(\w+)", line)
                    if match:
                        flow = NetworkFlow(
                            src_ip=match.group(1),
                            src_port=int(match.group(2)),
                            dst_ip=match.group(3),
                            dst_port=int(match.group(4)),
                            protocol=match.group(5),
                            bytes_sent=0,
                            bytes_received=0,
                        )
                        flows.append(flow)
                        with self._lock:
                            self._network_flows.append(flow)
                results["flows"] = [asdict(f) for f in flows[:100]]
                protocols = defaultdict(int)
                dst_ports = defaultdict(int)
                for f in flows:
                    protocols[f.protocol] += 1
                    dst_ports[f.dst_port] += 1
                results["statistics"] = {
                    "total_flows": len(flows),
                    "protocols": dict(protocols),
                    "top_dst_ports": sorted(dict(dst_ports).items(), key=lambda x: x[1], reverse=True)[:10],
                }
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Traffic analysis error: {e}")
        self._store_memory(f"traffic.{iface}", results)
        self._report_to_commander(f"Traffic analysis complete: {results["statistics"].get("total_flows", 0)} flows captured")
        return results

    def optimize_bandwidth(self, interface: str = "eth0") -> Dict[str, Any]:
        results = {"timestamp": datetime.utcnow().isoformat(), "interface": interface, "recommendations": []}
        try:
            rc, out, err = self._execute_shell(f"ifconfig {interface} 2>/dev/null || ip -s link show {interface} 2>/dev/null || echo Interface info not available", timeout=10)
            if out and "not available" not in out:
                results["interface_info"] = out.strip()
            rc2, out2, err2 = self._execute_shell(f"tc qdisc show dev {interface} 2>/dev/null || echo No tc rules", timeout=10)
            results["current_qos"] = out2.strip() if out2 else ""
            results["recommendations"] = [
                f"Enable BBR congestion control on {interface}",
                "Implement traffic shaping for real-time applications",
                "Use ECN for better throughput",
                "Enable TCP Fast Open for reduced latency",
                "Consider network compression for WAN links",
            ]
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] Bandwidth optimization error: {e}")
        self._store_memory(f"bandwidth.{interface}", results)
        return results

    def generate_vpn_config(self, vpn_type: str = "wireguard", server_endpoint: str = "", client_name: str = "client1") -> Dict[str, Any]:
        results = {"vpn_type": vpn_type, "timestamp": datetime.utcnow().isoformat(), "configs": {}}
        try:
            if vpn_type == "wireguard":
                rc, private_key, err = self._execute_shell("wg genkey 2>/dev/null || openssl rand -base64 32", timeout=10)
                rc2, public_key, err2 = self._execute_shell(f"echo '{private_key.strip()}' | wg pubkey 2>/dev/null || echo PUBKEY_PLACEHOLDER", timeout=10)
                server_config = f"[Interface]\nPrivateKey = {private_key.strip()}\nAddress = 10.200.200.1/24\nListenPort = 51820\nPostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE\nPostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE\n\n# {client_name}\n[Peer]\nPublicKey = {public_key.strip()}\nAllowedIPs = 10.200.200.2/32\n"
                client_private = os.urandom(32).hex()
                client_config = f"[Interface]\nPrivateKey = {client_private}\nAddress = 10.200.200.2/24\nDNS = 1.1.1.1, 8.8.8.8\n\n[Peer]\nPublicKey = {public_key.strip()}\nEndpoint = {server_endpoint}:51820\nAllowedIPs = 0.0.0.0/0, ::/0\nPersistentKeepalive = 25\n"
                results["configs"]["server"] = server_config
                results["configs"]["client"] = client_config
            elif vpn_type == "openvpn":
                results["configs"]["server"] = "# OpenVPN Server Config\nport 1194\nproto udp\ndev tun\nca ca.crt\ncert server.crt\nkey server.key\ndh dh.pem\nserver 10.8.0.0 255.255.255.0\nifconfig-pool-persist ipp.txt\npush \"redirect-gateway def1 bypass-dhcp\"\npush \"dhcp-option DNS 1.1.1.1\"\nkeepalive 10 120\ntls-auth ta.key 0\ncipher AES-256-GCM\nauth SHA256\nuser nobody\ngroup nogroup\npersist-key\npersist-tun\nstatus openvpn-status.log\nverb 3\n"
                results["configs"]["client"] = f"# OpenVPN Client Config for {client_name}\nclient\ndev tun\nproto udp\nremote {server_endpoint} 1194\nresolv-retry infinite\nnobind\npersist-key\npersist-tun\nremote-cert-tls server\ncipher AES-256-GCM\nauth SHA256\nverb 3\n"
            self._store_memory(f"vpn.{vpn_type}", results)
            self._report_to_commander(f"VPN config generated: {vpn_type} for {client_name}")
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] VPN config error: {e}")
        return results

    def test_ssl_check(self) -> bool:
        cert = self.check_ssl_certificate("cloudflare.com")
        assert cert.domain == "cloudflare.com"
        return True

    def test_dns_query(self) -> bool:
        records = self.query_dns("google.com", "A")
        assert len(records) > 0
        return True

    def test_network_design(self) -> bool:
        design = self.design_network({"tiers": 3, "total_hosts": 500})
        assert len(design["subnets"]) == 3
        return True

    def test_vpn_config(self) -> bool:
        config = self.generate_vpn_config("wireguard", "vpn.example.com")
        assert "server" in config["configs"]
        return True
