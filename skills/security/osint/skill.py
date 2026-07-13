"""OSINT Skill — Open-source intelligence gathering and correlation."""

import re
import socket
import urllib.request
import urllib.parse
import logging
from typing import Dict, Any, List
from skills import BaseSkill

logger = logging.getLogger(__name__)


class OsintSkill(BaseSkill):
    """Open-source intelligence gathering, correlation, and enrichment."""

    def __init__(self):
        super().__init__(name="osint", category="security", capabilities=["osint"])

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "gather")
        if method == "gather":
            return self.gather(params)
        elif method == "correlate":
            return self.correlate(params)
        elif method == "enrich":
            return self.enrich(params)
        elif method == "footprint":
            return self.footprint(params)
        return {"error": f"Unknown method: {method}"}

    def gather(self, params: Dict[str, Any]) -> Dict[str, Any]:
        target = params.get("target", "")
        sources = params.get("sources", ["web", "dns", "whois"])
        if not target:
            return {"success": False, "error": "No target provided"}
        data = {"target": target, "sources_used": sources}
        if "dns" in sources:
            try:
                ip = socket.gethostbyname(target)
                data["dns"] = {"a_record": ip}
                try:
                    hostname, aliases, addresses = socket.gethostbyaddr(ip)
                    data["dns"]["ptr_record"] = hostname
                except socket.herror:
                    pass
            except socket.gaierror as e:
                data["dns"] = {"error": str(e)}
        if "whois" in sources:
            try:
                import subprocess
                result = subprocess.run(["whois", target], capture_output=True, text=True, timeout=15)
                whois_data = result.stdout[:5000] if result.stdout else ""
                registrar = re.search(r'Registrar:\s*(.+)', whois_data)
                created = re.search(r'Creation Date:\s*(.+)', whois_data) or re.search(r'created:\s*(.+)', whois_data)
                expires = re.search(r'Registry Expiry Date:\s*(.+)', whois_data) or re.search(r'expires:\s*(.+)', whois_data)
                data["whois"] = {"raw": whois_data[:2000], "registrar": registrar.group(1).strip() if registrar else "", "created": created.group(1).strip() if created else "", "expires": expires.group(1).strip() if expires else ""}
            except Exception as e:
                data["whois"] = {"error": str(e)}
        if "web" in sources:
            try:
                url = f"https://{target}" if not target.startswith("http") else target
                req = urllib.request.Request(url, headers={"User-Agent": "IRIS-OMNIS/1.0"}, method="HEAD")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data["web"] = {"status": resp.status, "server": resp.headers.get("Server", ""), "headers": dict(resp.headers)}
            except Exception as e:
                data["web"] = {"error": str(e)}
        return {"success": True, **data}

    def correlate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        data_points = params.get("data_points", [])
        correlations = []
        # Find shared IPs, domains, emails across data points
        ips_found = set()
        domains_found = set()
        for dp in data_points:
            if "ip" in dp:
                ips_found.add(dp["ip"])
            if "domain" in dp:
                domains_found.add(dp["domain"])
        shared = {"ips": list(ips_found), "domains": list(domains_found), "data_points": len(data_points)}
        if len(ips_found) == 1 and len(data_points) > 1:
            correlations.append({"type": "shared_ip", "value": list(ips_found)[0], "confidence": "high"})
        return {"success": True, "correlations_found": len(correlations), "correlations": correlations, "shared_indicators": shared}

    def enrich(self, params: Dict[str, Any]) -> Dict[str, Any]:
        indicator = params.get("indicator", "")
        if not indicator:
            return {"success": False, "error": "No indicator provided"}
        ioc_type = "unknown"
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', indicator):
            ioc_type = "ip"
        elif re.match(r'^[a-f0-9]{32,64}$', indicator, re.IGNORECASE):
            ioc_type = "hash"
        elif '.' in indicator and not indicator.startswith("http"):
            ioc_type = "domain"
        enrichment = {"indicator": indicator, "type": ioc_type, "reputation": "unknown"}
        if ioc_type == "ip":
            try:
                import urllib.request
                req = urllib.request.Request(f"https://ipinfo.io/{indicator}/json", headers={"User-Agent": "IRIS-OMNIS/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    import json
                    ip_data = json.loads(resp.read().decode())
                    enrichment["geolocation"] = {"city": ip_data.get("city", ""), "region": ip_data.get("region", ""), "country": ip_data.get("country", ""), "org": ip_data.get("org", ""), "asn": ip_data.get("asn", {})}
            except Exception:
                pass
        return {"success": True, **enrichment}

    def footprint(self, params: Dict[str, Any]) -> Dict[str, Any]:
        domain = params.get("domain", "")
        if not domain:
            return {"success": False, "error": "No domain provided"}
        footprint = {"domain": domain, "subdomains": [], "technologies": []}
        # Common subdomain enumeration
        common_subs = ["www", "mail", "ftp", "api", "admin", "blog", "shop", "cdn", "dev", "staging", "test", "vpn", "portal", "support"]
        found_subs = []
        for sub in common_subs:
            try:
                full = f"{sub}.{domain}"
                ip = socket.gethostbyname(full)
                found_subs.append({"subdomain": full, "ip": ip})
            except socket.gaierror:
                pass
        footprint["subdomains"] = found_subs
        # Try to detect technologies
        try:
            url = f"https://{domain}"
            req = urllib.request.Request(url, headers={"User-Agent": "IRIS-OMNIS/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                headers = dict(resp.headers)
                techs = []
                if "X-Powered-By" in headers:
                    techs.append(headers["X-Powered-By"])
                if "Server" in headers:
                    techs.append(headers["Server"])
                footprint["technologies"] = techs
        except Exception:
            pass
        return {"success": True, **footprint}
