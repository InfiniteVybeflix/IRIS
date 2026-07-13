"""
IRIS v1.0 — Threat Feeds

Live threat intelligence ingestion: CVE feeds, abuse.ch lists,
AlienVault OTX, IP reputation checks, hash reputation, and IOC matching.

Dependencies:
    - requests

Safety:
    - API keys from environment variables only.
    - Read-only threat data consumption.

Usage:
    from senses.threat_feeds import ThreatFeeds
    feeds = ThreatFeeds()
    cves = feeds.fetch_cve_feed()
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

from .base_sense import BaseSense

logger = logging.getLogger(__name__)


class ThreatFeeds(BaseSense):
    """
    Threat intelligence feed aggregator and IOC checker.

    Fetches live CVE data, abuse.ch threat lists, AlienVault OTX pulses,
    and performs IP/hash reputation lookups.

    Attributes:
        name: "threat_feeds"
        interval: 3600 seconds (1 hour)
        thresholds: Alert thresholds.
    """

    name: str = "threat_feeds"
    interval: int = 3600
    thresholds: Dict[str, Any] = {
        "cve_severity_threshold": 7.0,
        "reputation_min_confidence": 50,
    }

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "IRIS-v1.0/Threat-Intel", "Accept": "application/json"})
        self._session.verify = True
        self._otx_api_key = os.environ.get("IRIS_OTX_API_KEY", "")
        self._vt_api_key = os.environ.get("IRIS_VT_API_KEY", "")
        self._cached_cves: List[Dict[str, Any]] = []
        self._cached_threats: List[Dict[str, Any]] = []

    def _sense(self) -> Dict[str, Any]:
        """Fetch latest threat intelligence feeds."""
        findings: Dict[str, Any] = {"cves": [], "threats": [], "errors": []}
        try:
            cves = self.fetch_cve_feed()
            if cves.get("success"):
                findings["cves"] = cves.get("parsed", {}).get("cves", [])
        except Exception as exc:
            findings["errors"].append(f"CVE fetch failed: {exc}")
        try:
            threats = self.fetch_abuse_ch()
            if threats.get("success"):
                findings["threats"].extend(threats.get("parsed", {}).get("threats", []))
        except Exception as exc:
            findings["errors"].append(f"abuse.ch fetch failed: {exc}")
        return findings

    def fetch_cve_feed(self) -> Dict[str, Any]:
        """Fetch recent CVEs from the NVD API."""
        self._begin_check()
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=7)
            url = f"https://services.nvd.nist.gov/rest/json/cves/2.0/?pubStartDate={start_date.strftime('%Y-%m-%dT%H:%M:%S')}&pubEndDate={end_date.strftime('%Y-%m-%dT%H:%M:%S')}&resultsPerPage=100"
            resp = self._session.get(url, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            cves: List[Dict[str, Any]] = []
            for vuln in data.get("vulnerabilities", []):
                cve = vuln.get("cve", {})
                metrics = cve.get("metrics", {})
                cvss = metrics.get("cvssMetricV31", [{}])[0].get("cvssData", {})
                severity = cvss.get("baseScore", 0)
                if severity >= self.thresholds.get("cve_severity_threshold", 7.0):
                    cves.append({"id": cve.get("id"), "severity": severity, "description": cve.get("descriptions", [{}])[0].get("value", ""), "published": cve.get("published")})

            self._cached_cves = cves
            res = self._build_result(success=True, action="fetch_cve_feed", output=data, parsed={"cve_count": len(cves), "cves": cves})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("ThreatFeeds fetch_cve_feed failed")
            res = self._build_result(success=False, action="fetch_cve_feed", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def fetch_abuse_ch(self) -> Dict[str, Any]:
        """Fetch threat lists from abuse.ch."""
        self._begin_check()
        try:
            threats: List[Dict[str, Any]] = []
            try:
                resp = self._session.post("https://threatfox-api.abuse.ch/api/v1/", json={"query": "get_iocs", "days": 1}, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    for ioc in data.get("data", [])[:100]:
                        threats.append({"source": "threatfox", "ioc": ioc.get("ioc"), "type": ioc.get("ioc_type"), "malware": ioc.get("malware"), "confidence": ioc.get("confidence_level")})
            except Exception as exc:
                logger.warning(f"ThreatFox fetch failed: {exc}")

            self._cached_threats = threats
            res = self._build_result(success=True, action="fetch_abuse_ch", output=threats, parsed={"threat_count": len(threats), "threats": threats})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("ThreatFeeds fetch_abuse_ch failed")
            res = self._build_result(success=False, action="fetch_abuse_ch", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def fetch_alienvault(self) -> Dict[str, Any]:
        """Fetch recent AlienVault OTX pulses."""
        self._begin_check()
        try:
            if not self._otx_api_key:
                return self._build_result(success=False, action="fetch_alienvault", errors=["IRIS_OTX_API_KEY not set."])
            headers = {"X-OTX-API-KEY": self._otx_api_key}
            resp = self._session.get("https://otx.alienvault.com/api/v1/pulses/subscribed", headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            pulses = data.get("results", [])
            res = self._build_result(success=True, action="fetch_alienvault", output=data, parsed={"pulse_count": len(pulses), "pulses": pulses})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("ThreatFeeds fetch_alienvault failed")
            res = self._build_result(success=False, action="fetch_alienvault", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def check_ip_reputation(self, ip: str) -> Dict[str, Any]:
        """Check IP reputation across multiple threat intelligence sources."""
        self._begin_check()
        try:
            safe_ip = self.sanitize_input(ip)
            reputation: Dict[str, Any] = {"sources": []}
            abuse_key = os.environ.get("IRIS_ABUSEIPDB_KEY", "")
            if abuse_key:
                try:
                    resp = self._session.get("https://api.abuseipdb.com/api/v2/check", headers={"Key": abuse_key}, params={"ipAddress": safe_ip, "maxAgeInDays": 90}, timeout=30)
                    if resp.status_code == 200:
                        data = resp.json()
                        reputation["sources"].append({"source": "abuseipdb", "score": data.get("data", {}).get("abuseConfidenceScore", 0), "reports": data.get("data", {}).get("totalReports", 0)})
                except Exception:
                    pass
            for threat in self._cached_threats:
                if threat.get("ioc") == safe_ip:
                    reputation["sources"].append({"source": threat.get("source", "cached"), "type": threat.get("type"), "malware": threat.get("malware")})
            res = self._build_result(success=True, action="check_ip_reputation", output=reputation, parsed={"ip": safe_ip, "reputation": reputation})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("ThreatFeeds check_ip_reputation failed")
            res = self._build_result(success=False, action="check_ip_reputation", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def check_hash_reputation(self, file_hash: str) -> Dict[str, Any]:
        """Check file hash reputation (VirusTotal-style lookup)."""
        self._begin_check()
        try:
            safe_hash = self.sanitize_input(file_hash)
            reputation: Dict[str, Any] = {"sources": []}
            if self._vt_api_key:
                try:
                    resp = self._session.get(f"https://www.virustotal.com/api/v3/files/{safe_hash}", headers={"x-apikey": self._vt_api_key}, timeout=30)
                    if resp.status_code == 200:
                        data = resp.json()
                        attrs = data.get("data", {}).get("attributes", {})
                        reputation["sources"].append({"source": "virustotal", "malicious": attrs.get("last_analysis_stats", {}).get("malicious", 0), "suspicious": attrs.get("last_analysis_stats", {}).get("suspicious", 0), "harmless": attrs.get("last_analysis_stats", {}).get("harmless", 0)})
                except Exception:
                    pass
            try:
                resp = self._session.post("https://mb-api.abuse.ch/api/v1/", data={"query": "get_info", "hash": safe_hash}, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("query_status") == "ok":
                        reputation["sources"].append({"source": "malwarebazaar", "file_name": data.get("data", [{}])[0].get("file_name"), "signature": data.get("data", [{}])[0].get("signature")})
            except Exception:
                pass
            res = self._build_result(success=True, action="check_hash_reputation", output=reputation, parsed={"hash": safe_hash, "reputation": reputation})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("ThreatFeeds check_hash_reputation failed")
            res = self._build_result(success=False, action="check_hash_reputation", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def match_iocs(self, target_data: List[str]) -> Dict[str, Any]:
        """Match a list of IPs, hashes, or domains against cached IOCs."""
        self._begin_check()
        try:
            matches: List[Dict[str, Any]] = []
            all_iocs = self._cached_threats + [{"ioc": c.get("id"), "type": "cve"} for c in self._cached_cves]
            for target in target_data:
                safe_target = self.sanitize_input(target)
                for ioc in all_iocs:
                    if ioc.get("ioc") == safe_target:
                        matches.append({"target": safe_target, "match": ioc})
            res = self._build_result(success=True, action="match_iocs", output=matches, parsed={"match_count": len(matches), "matches": matches})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("ThreatFeeds match_iocs failed")
            res = self._build_result(success=False, action="match_iocs", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def _should_alert(self, result: Dict[str, Any]) -> bool:
        if not result.get("success"):
            return True
        output = result.get("output", {})
        if output.get("cves"):
            return True
        if output.get("threats"):
            return True
        return False

    def _emit_alert(self, result: Dict[str, Any]) -> None:
        alert = {"type": "threat_alert", "sense": self.name, "severity": "high", "message": "New threat intelligence detected", "data": result.get("output", {})}
        self.report(alert)


__all__ = ["ThreatFeeds"]
