"""
threat_prophet.py — OMEN
Threat intelligence agent. CVE monitoring, threat feed aggregation (MISP,
AlienVault OTX, Abuse.ch), dark web monitoring, IOC matching, MITRE ATT&CK
mapping, predictive threat analysis.
"""

import logging
import os
import re
import json
import hashlib
import subprocess
import threading
import time
import urllib.request
import urllib.error
import socket
from typing import Any, Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque

logger = logging.getLogger("OMEN")


@dataclass
class ThreatIndicator:
    """A threat indicator of compromise (IOC)."""
    ioc_id: str
    ioc_type: str  # ip, domain, hash, url, email
    value: str
    source: str
    confidence: str  # high, medium, low
    first_seen: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_seen: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    tags: List[str] = field(default_factory=list)
    mitre_techniques: List[str] = field(default_factory=list)


@dataclass
class CVEEntry:
    """A CVE vulnerability entry."""
    cve_id: str
    description: str
    severity: str  # critical, high, medium, low
    cvss_score: float
    published_date: str
    modified_date: str
    references: List[str] = field(default_factory=list)
    affected_products: List[str] = field(default_factory=list)
    exploit_available: bool = False


class ThreatProphet:
    """
    OMEN — Threat Intelligence Agent.

    Real capabilities:
    - CVE monitoring via NVD API (real HTTP requests)
    - Threat feed aggregation (MISP, AlienVault OTX, Abuse.ch URLhaus/Feodo)
    - Dark web monitoring via Tor SOCKS proxy (if available)
    - IOC matching against collected feeds
    - MITRE ATT&CK technique mapping
    - Predictive threat scoring based on correlation
    """

    CODENAME = "OMEN"

    # Real API endpoints
    NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    OTX_API_URL = "https://otx.alienvault.com/api/v1"
    URLHAUS_API_URL = "https://urlhaus-api.abuse.ch/v1"
    FEODO_API_URL = "https://feodotracker.abuse.ch/downloads/ipblocklist.json"
    MISP_API_URL = os.environ.get("MISP_URL", "")

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._iocs: Dict[str, ThreatIndicator] = {}
        self._cves: Dict[str, CVEEntry] = {}
        self._threat_feeds: deque = deque(maxlen=5000)
        self._monitor_thread: Optional[threading.Thread] = None
        self._session_id = hashlib.sha256(
            f"omen_{time.time()}_{os.urandom(8).hex()}".encode()
        ).hexdigest()[:16]
        self._api_keys = {
            "otx": os.environ.get("OTX_API_KEY", ""),
            "misp": os.environ.get("MISP_API_KEY", ""),
        }
        logger.info(f"[{self.CODENAME}] Initialized session {self._session_id}")

    def start(self) -> bool:
        with self._lock:
            self._running = True
            self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self._monitor_thread.start()
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
                "iocs_stored": len(self._iocs),
                "cves_stored": len(self._cves),
                "feed_entries": len(self._threat_feeds),
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

    def _http_request(self, url: str, headers: Optional[Dict] = None, 
                      timeout: int = 30, method: str = "GET",
                      data: Optional[bytes] = None) -> Tuple[int, Dict, str]:
        """Make real HTTP request and return (status, headers, body)."""
        try:
            req = urllib.request.Request(url, method=method, data=data)
            req.add_header("User-Agent", "Aevibron-OMEN/1.0 Threat Intelligence Agent")
            if headers:
                for k, v in headers.items():
                    req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                return resp.status, dict(resp.headers), body
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read().decode("utf-8", errors="ignore")
        except urllib.error.URLError as e:
            return 0, {}, str(e.reason)
        except socket.timeout:
            return 0, {}, "Request timed out"
        except Exception as e:
            return -1, {}, str(e)

    # -------------------------------------------------------------------------
    # CVE Monitoring
    # -------------------------------------------------------------------------
    def fetch_cves(self, start_date: Optional[str] = None, 
                   end_date: Optional[str] = None,
                   severity_filter: Optional[str] = None,
                   keyword: Optional[str] = None) -> List[CVEEntry]:
        """
        Fetch CVEs from NVD API.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            severity_filter: Filter by severity (critical, high, medium, low)
            keyword: Search keyword

        Returns:
            List of CVEEntry objects
        """
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.utcnow().strftime("%Y-%m-%d")

        url = f"{self.NVD_API_URL}?pubStartDate={start_date}T00:00:00.000&pubEndDate={end_date}T23:59:59.999&resultsPerPage=100"
        if keyword:
            url += f"&keywordSearch={urllib.request.quote(keyword)}"

        logger.info(f"[{self.CODENAME}] Fetching CVEs from NVD: {start_date} to {end_date}")
        status, headers, body = self._http_request(url, timeout=60)

        entries = []
        if status == 200:
            try:
                data = json.loads(body)
                vulnerabilities = data.get("vulnerabilities", [])
                for vuln in vulnerabilities:
                    cve = vuln.get("cve", {})
                    cve_id = cve.get("id", "")
                    descriptions = cve.get("descriptions", [])
                    description = next((d.get("value", "") for d in descriptions if d.get("lang") == "en"), "")

                    metrics = cve.get("metrics", {})
                    cvss_data = metrics.get("cvssMetricV31", [{}])[0] if metrics.get("cvssMetricV31") else {}
                    if not cvss_data:
                        cvss_data = metrics.get("cvssMetricV30", [{}])[0] if metrics.get("cvssMetricV30") else {}

                    cvss_score = cvss_data.get("cvssData", {}).get("baseScore", 0.0) if cvss_data else 0.0
                    severity = cvss_data.get("cvssData", {}).get("baseSeverity", "unknown") if cvss_data else "unknown"

                    references = [ref.get("url", "") for ref in cve.get("references", [])]

                    entry = CVEEntry(
                        cve_id=cve_id,
                        description=description,
                        severity=severity.lower(),
                        cvss_score=cvss_score,
                        published_date=cve.get("published", ""),
                        modified_date=cve.get("lastModified", ""),
                        references=references,
                    )

                    if severity_filter and entry.severity != severity_filter.lower():
                        continue

                    with self._lock:
                        self._cves[cve_id] = entry
                    entries.append(entry)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] CVE parsing error: {e}")
        else:
            logger.warning(f"[{self.CODENAME}] NVD API returned status {status}: {body[:200]}")

        self._store_memory("cves.latest", [asdict(e) for e in entries])
        self._report_to_commander(f"Fetched {len(entries)} CVEs from NVD")
        return entries

    def search_cve(self, cve_id: str) -> Optional[CVEEntry]:
        """Search for a specific CVE by ID."""
        if cve_id in self._cves:
            return self._cves[cve_id]

        url = f"{self.NVD_API_URL}?cveId={cve_id}"
        status, headers, body = self._http_request(url, timeout=30)

        if status == 200:
            try:
                data = json.loads(body)
                vuln = data.get("vulnerabilities", [{}])[0]
                cve = vuln.get("cve", {})
                descriptions = cve.get("descriptions", [])
                description = next((d.get("value", "") for d in descriptions if d.get("lang") == "en"), "")

                metrics = cve.get("metrics", {})
                cvss_data = metrics.get("cvssMetricV31", [{}])[0] if metrics.get("cvssMetricV31") else {}
                if not cvss_data:
                    cvss_data = metrics.get("cvssMetricV30", [{}])[0] if metrics.get("cvssMetricV30") else {}

                cvss_score = cvss_data.get("cvssData", {}).get("baseScore", 0.0) if cvss_data else 0.0
                severity = cvss_data.get("cvssData", {}).get("baseSeverity", "unknown") if cvss_data else "unknown"
                references = [ref.get("url", "") for ref in cve.get("references", [])]

                entry = CVEEntry(
                    cve_id=cve_id,
                    description=description,
                    severity=severity.lower(),
                    cvss_score=cvss_score,
                    published_date=cve.get("published", ""),
                    modified_date=cve.get("lastModified", ""),
                    references=references,
                )
                with self._lock:
                    self._cves[cve_id] = entry
                return entry
            except Exception as e:
                logger.error(f"[{self.CODENAME}] CVE search error: {e}")
        return None

    def get_cves_by_severity(self, severity: str) -> List[CVEEntry]:
        """Get all stored CVEs filtered by severity."""
        with self._lock:
            return [cve for cve in self._cves.values() if cve.severity == severity.lower()]

    # -------------------------------------------------------------------------
    # Threat Feed Aggregation
    # -------------------------------------------------------------------------
    def fetch_otx_pulses(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Fetch threat pulses from AlienVault OTX.

        Args:
            limit: Number of pulses to fetch

        Returns:
            List of pulse data
        """
        if not self._api_keys["otx"]:
            logger.warning(f"[{self.CODENAME}] OTX API key not configured")
            return []

        url = f"{self.OTX_API_URL}/pulses/subscribed?limit={limit}"
        headers = {"X-OTX-API-KEY": self._api_keys["otx"]}

        status, resp_headers, body = self._http_request(url, headers=headers, timeout=30)

        pulses = []
        if status == 200:
            try:
                data = json.loads(body)
                pulses = data.get("results", [])
                for pulse in pulses:
                    self._process_pulse_iocs(pulse)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] OTX parsing error: {e}")
        else:
            logger.warning(f"[{self.CODENAME}] OTX API returned {status}")

        self._store_memory("feeds.otx", pulses)
        self._report_to_commander(f"Fetched {len(pulses)} pulses from OTX")
        return pulses

    def _process_pulse_iocs(self, pulse: Dict[str, Any]) -> None:
        """Extract IOCs from an OTX pulse."""
        indicators = pulse.get("indicators", [])
        for ind in indicators:
            ioc_type = ind.get("type", "")
            value = ind.get("indicator", "")
            if not value:
                continue

            ioc_id = f"ioc_{hashlib.md5(f'{ioc_type}_{value}'.encode()).hexdigest()[:16]}"
            indicator = ThreatIndicator(
                ioc_id=ioc_id,
                ioc_type=ioc_type,
                value=value,
                source=f"OTX:{pulse.get('name', 'unknown')}",
                confidence="medium",
                tags=pulse.get("tags", []),
            )
            with self._lock:
                self._iocs[ioc_id] = indicator

    def fetch_urlhaus(self, query_type: str = "recent", 
                      limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch malicious URL data from Abuse.ch URLhaus.

        Args:
            query_type: recent, online, or specific URL query
            limit: Maximum entries

        Returns:
            List of URLhaus entries
        """
        url = f"{self.URLHAUS_API_URL}/urls/recent/"
        if query_type == "online":
            url = f"{self.URLHAUS_API_URL}/urls/recent/limit/{limit}/"

        status, headers, body = self._http_request(url, timeout=30)

        entries = []
        if status == 200:
            try:
                data = json.loads(body)
                urls = data.get("urls", [])
                for entry in urls[:limit]:
                    url_value = entry.get("url", "")
                    threat = entry.get("threat", "")
                    tags = entry.get("tags", [])

                    ioc_id = f"ioc_{hashlib.md5(url_value.encode()).hexdigest()[:16]}"
                    indicator = ThreatIndicator(
                        ioc_id=ioc_id,
                        ioc_type="url",
                        value=url_value,
                        source="URLhaus",
                        confidence="high",
                        tags=tags,
                    )
                    with self._lock:
                        self._iocs[ioc_id] = indicator
                    entries.append(entry)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] URLhaus parsing error: {e}")
        else:
            logger.warning(f"[{self.CODENAME}] URLhaus API returned {status}")

        self._store_memory("feeds.urlhaus", entries)
        self._report_to_commander(f"Fetched {len(entries)} URLs from URLhaus")
        return entries

    def fetch_feodo_tracker(self) -> List[Dict[str, Any]]:
        """Fetch FeodoTracker C2 IP blocklist."""
        status, headers, body = self._http_request(self.FEODO_API_URL, timeout=30)

        entries = []
        if status == 200:
            try:
                data = json.loads(body)
                for entry in data:
                    ip = entry.get("ip_address", "")
                    if ip:
                        ioc_id = f"ioc_{hashlib.md5(ip.encode()).hexdigest()[:16]}"
                        indicator = ThreatIndicator(
                            ioc_id=ioc_id,
                            ioc_type="ip",
                            value=ip,
                            source="FeodoTracker",
                            confidence="high",
                            tags=["c2", "botnet"],
                        )
                        with self._lock:
                            self._iocs[ioc_id] = indicator
                        entries.append(entry)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Feodo parsing error: {e}")
        else:
            logger.warning(f"[{self.CODENAME}] FeodoTracker returned {status}")

        self._store_memory("feeds.feodo", entries)
        self._report_to_commander(f"Fetched {len(entries)} C2 IPs from FeodoTracker")
        return entries

    def fetch_misp_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch events from MISP instance."""
        if not self._api_keys["misp"] or not self.MISP_API_URL:
            logger.warning(f"[{self.CODENAME}] MISP not configured")
            return []

        url = f"{self.MISP_API_URL}/events/restSearch"
        headers = {
            "Authorization": self._api_keys["misp"],
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = json.dumps({"limit": limit, "page": 1}).encode()

        status, resp_headers, body = self._http_request(url, headers=headers, timeout=30, method="POST", data=payload)

        events = []
        if status == 200:
            try:
                data = json.loads(body)
                events = data.get("response", []) if isinstance(data.get("response"), list) else []
                for event in events:
                    for attr in event.get("Event", {}).get("Attribute", []):
                        ioc_type = attr.get("type", "")
                        value = attr.get("value", "")
                        if value:
                            ioc_id = f"ioc_{hashlib.md5(value.encode()).hexdigest()[:16]}"
                            indicator = ThreatIndicator(
                                ioc_id=ioc_id,
                                ioc_type=ioc_type,
                                value=value,
                                source="MISP",
                                confidence="medium",
                            )
                            with self._lock:
                                self._iocs[ioc_id] = indicator
            except Exception as e:
                logger.error(f"[{self.CODENAME}] MISP parsing error: {e}")
        else:
            logger.warning(f"[{self.CODENAME}] MISP returned {status}")

        self._store_memory("feeds.misp", events)
        self._report_to_commander(f"Fetched {len(events)} events from MISP")
        return events

    def aggregate_all_feeds(self) -> Dict[str, Any]:
        """Fetch and aggregate all configured threat feeds."""
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "feeds": {},
            "total_iocs": 0,
        }

        results["feeds"]["nvd_cves"] = len(self.fetch_cves())
        results["feeds"]["otx_pulses"] = len(self.fetch_otx_pulses())
        results["feeds"]["urlhaus"] = len(self.fetch_urlhaus())
        results["feeds"]["feodo_tracker"] = len(self.fetch_feodo_tracker())
        results["feeds"]["misp"] = len(self.fetch_misp_events())

        with self._lock:
            results["total_iocs"] = len(self._iocs)
            results["total_cves"] = len(self._cves)

        self._store_memory("feeds.aggregate", results)
        self._report_to_commander("All threat feeds aggregated", data=results)
        return results

    # -------------------------------------------------------------------------
    # Dark Web Monitoring
    # -------------------------------------------------------------------------
    def monitor_dark_web(self, keywords: List[str], 
                         onion_sources: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Monitor dark web sources for keywords.

        Args:
            keywords: Keywords to search for
            onion_sources: List of .onion URLs to check

        Returns:
            Dark web monitoring results
        """
        onion_sources = onion_sources or []
        results = {
            "keywords": keywords,
            "sources_checked": len(onion_sources),
            "findings": [],
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Check if Tor proxy is available
        tor_proxy = os.environ.get("TOR_PROXY", "socks5h://127.0.0.1:9050")

        for source in onion_sources:
            if not self._running:
                break
            try:
                # Attempt via Tor proxy if available
                # Note: urllib doesn't support SOCKS natively, so we use a subprocess curl approach
                rc, out, err = self._execute_shell(
                    f'curl --socks5-hostname {tor_proxy.replace("socks5h://", "")} --max-time 30 -s "{source}" 2>&1 | head -500',
                    timeout=40
                )
                if out:
                    for keyword in keywords:
                        if keyword.lower() in out.lower():
                            results["findings"].append({
                                "source": source,
                                "keyword": keyword,
                                "context": out[max(0, out.lower().find(keyword.lower()) - 100):out.lower().find(keyword.lower()) + 200],
                                "timestamp": datetime.utcnow().isoformat(),
                            })
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Dark web monitoring error for {source}: {e}")

        # Also check public dark web monitoring APIs
        results["findings"].extend(self._check_dark_web_apis(keywords))

        self._store_memory("darkweb.latest", results)
        self._report_to_commander(f"Dark web monitoring complete: {len(results['findings'])} findings")
        return results

    def _execute_shell(self, command: str, timeout: int = 30) -> Tuple[int, str, str]:
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout, cwd=os.getcwd())
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    def _check_dark_web_apis(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """Check public APIs for dark web mentions."""
        findings = []
        # Use Have I Been Pwned API for breach data
        for keyword in keywords:
            if "@" in keyword:  # Email check
                url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{urllib.request.quote(keyword)}"
                headers = {"hibp-api-key": os.environ.get("HIBP_API_KEY", "")}
                status, resp_headers, body = self._http_request(url, headers=headers, timeout=15)
                if status == 200:
                    try:
                        breaches = json.loads(body)
                        findings.append({
                            "source": "HaveIBeenPwned",
                            "keyword": keyword,
                            "breach_count": len(breaches),
                            "breaches": [b.get("Name", "") for b in breaches[:5]],
                        })
                    except Exception:
                        pass
        return findings

    # -------------------------------------------------------------------------
    # IOC Matching
    # -------------------------------------------------------------------------
    def match_ioc(self, value: str, ioc_type: Optional[str] = None) -> List[ThreatIndicator]:
        """
        Match a value against stored IOCs.

        Args:
            value: Value to match
            ioc_type: Optional type filter

        Returns:
            Matching indicators
        """
        matches = []
        with self._lock:
            for ioc in self._iocs.values():
                if ioc_type and ioc.ioc_type != ioc_type:
                    continue
                if value == ioc.value or value in ioc.value or ioc.value in value:
                    matches.append(ioc)
        return matches

    def scan_file_for_iocs(self, file_path: str) -> Dict[str, Any]:
        """
        Scan a file for known IOCs.

        Args:
            file_path: Path to file to scan

        Returns:
            Scan results with matches
        """
        results = {"file_path": file_path, "matches": [], "scanned_at": datetime.utcnow().isoformat()}

        if not os.path.exists(file_path):
            results["error"] = f"File not found: {file_path}"
            return results

        try:
            with open(file_path, "rb") as f:
                content = f.read().decode("utf-8", errors="ignore")

            # Hash-based matching
            md5_hash = hashlib.md5(content.encode()).hexdigest()
            sha256_hash = hashlib.sha256(content.encode()).hexdigest()

            for hash_val in [md5_hash, sha256_hash]:
                matches = self.match_ioc(hash_val, "hash")
                for match in matches:
                    results["matches"].append(asdict(match))

            # Content-based matching (IPs, domains, URLs)
            ip_pattern = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b")
            domain_pattern = re.compile(r"\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
            url_pattern = re.compile(r'''https?://[^\s"'<>]+''')

            for ip in set(ip_pattern.findall(content)):
                matches = self.match_ioc(ip, "ip")
                for match in matches:
                    results["matches"].append(asdict(match))

            for domain in set(domain_pattern.findall(content)):
                matches = self.match_ioc(domain, "domain")
                for match in matches:
                    results["matches"].append(asdict(match))

            for url in set(url_pattern.findall(content)):
                matches = self.match_ioc(url, "url")
                for match in matches:
                    results["matches"].append(asdict(match))

        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[{self.CODENAME}] IOC scan error: {e}")

        self._store_memory(f"ioc_scan.{file_path}", results)
        self._report_to_commander(f"IOC scan complete for {file_path}: {len(results['matches'])} matches")
        return results

    # -------------------------------------------------------------------------
    # MITRE ATT&CK Mapping
    # -------------------------------------------------------------------------
    def map_to_mitre(self, cve_id: Optional[str] = None,
                     ioc_value: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Map CVEs or IOCs to MITRE ATT&CK techniques.

        Args:
            cve_id: CVE to map
            ioc_value: IOC to map

        Returns:
            MITRE technique mappings
        """
        mappings = []

        # Known CVE-to-technique mappings (expanded subset)
        cve_to_technique = {
            "CVE-2021-44228": ["T1190", "T1059", "T1071"],  # Log4j
            "CVE-2023-38408": ["T1190", "T1059"],  # libssh
            "CVE-2023-34362": ["T1190", "T1071"],  # MOVEit
            "CVE-2023-36884": ["T1566", "T1059"],  # Office RCE
        }

        if cve_id and cve_id.upper() in cve_to_technique:
            for tid in cve_to_technique[cve_id.upper()]:
                mappings.append({
                    "cve_id": cve_id,
                    "technique_id": tid,
                    "technique_name": self._get_technique_name(tid),
                    "tactic": self._get_technique_tactic(tid),
                    "confidence": "high",
                })

        # IOC-based mapping (heuristic)
        if ioc_value:
            if any(t in ioc_value.lower() for t in ["powershell", "cmd.exe", "bash"]):
                mappings.append({"ioc": ioc_value, "technique_id": "T1059", "technique_name": "Command and Scripting Interpreter", "tactic": "Execution", "confidence": "medium"})
            if ".onion" in ioc_value:
                mappings.append({"ioc": ioc_value, "technique_id": "T1090", "technique_name": "Proxy", "tactic": "Command and Control", "confidence": "medium"})

        return mappings

    def _get_technique_name(self, technique_id: str) -> str:
        names = {
            "T1190": "Exploit Public-Facing Application",
            "T1059": "Command and Scripting Interpreter",
            "T1071": "Application Layer Protocol",
            "T1566": "Phishing",
            "T1090": "Proxy",
        }
        return names.get(technique_id, "Unknown")

    def _get_technique_tactic(self, technique_id: str) -> str:
        tactics = {
            "T1190": "Initial Access",
            "T1059": "Execution",
            "T1071": "Command and Control",
            "T1566": "Initial Access",
            "T1090": "Command and Control",
        }
        return tactics.get(technique_id, "Unknown")

    # -------------------------------------------------------------------------
    # Predictive Analysis
    # -------------------------------------------------------------------------
    def predict_threat_likelihood(self, target_assets: List[str]) -> Dict[str, Any]:
        """
        Predict threat likelihood for target assets based on intelligence correlation.

        Args:
            target_assets: List of asset names/technologies to assess

        Returns:
            Predictive threat assessment
        """
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "asset_assessments": [],
            "overall_risk": "low",
        }

        with self._lock:
            cves = list(self._cves.values())
            iocs = list(self._iocs.values())

        for asset in target_assets:
            asset_lower = asset.lower()

            # Find relevant CVEs
            relevant_cves = [cve for cve in cves if asset_lower in cve.description.lower()]
            critical_cves = [cve for cve in relevant_cves if cve.severity == "critical"]
            high_cves = [cve for cve in relevant_cves if cve.severity == "high"]

            # Find relevant IOCs
            relevant_iocs = [ioc for ioc in iocs if asset_lower in ioc.value.lower() or any(asset_lower in t.lower() for t in ioc.tags)]

            # Calculate risk score
            risk_score = 0
            risk_score += len(critical_cves) * 10
            risk_score += len(high_cves) * 5
            risk_score += len(relevant_iocs) * 3

            if risk_score > 50:
                risk_level = "critical"
            elif risk_score > 25:
                risk_level = "high"
            elif risk_score > 10:
                risk_level = "medium"
            else:
                risk_level = "low"

            results["asset_assessments"].append({
                "asset": asset,
                "risk_level": risk_level,
                "risk_score": risk_score,
                "relevant_cves": len(relevant_cves),
                "critical_cves": len(critical_cves),
                "high_cves": len(high_cves),
                "relevant_iocs": len(relevant_iocs),
                "top_cves": [cve.cve_id for cve in sorted(relevant_cves, key=lambda x: x.cvss_score, reverse=True)[:5]],
                "recommendations": [
                    f"Patch {len(critical_cves)} critical CVEs immediately" if critical_cves else "No critical CVEs found",
                    f"Monitor {len(relevant_iocs)} related IOCs" if relevant_iocs else "No IOCs found for this asset",
                    "Review exposure to public internet" if risk_level in ["critical", "high"] else "Maintain current security posture",
                ],
            })

        # Overall risk
        max_risk = max((a["risk_level"] for a in results["asset_assessments"]), key=lambda x: {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(x, 0))
        results["overall_risk"] = max_risk

        self._store_memory("predictions.latest", results)
        self._report_to_commander(f"Threat prediction complete for {len(target_assets)} assets", data=results)
        return results

    # -------------------------------------------------------------------------
    # Monitoring Loop
    # -------------------------------------------------------------------------
    def _monitoring_loop(self) -> None:
        """Background monitoring loop for threat intelligence updates."""
        logger.info(f"[{self.CODENAME}] Monitoring loop started")
        while self._running:
            try:
                # Refresh CVEs daily
                self.fetch_cves()
                # Refresh feeds
                self.fetch_urlhaus(limit=50)
                self.fetch_feodo_tracker()
                if self._api_keys["otx"]:
                    self.fetch_otx_pulses(limit=10)
                if self._api_keys["misp"]:
                    self.fetch_misp_events(limit=20)

                # Sleep for 6 hours
                for _ in range(2160):  # 6 hours in 10-second intervals
                    if not self._running:
                        break
                    time.sleep(10)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Monitoring loop error: {e}")
                time.sleep(60)

    # -------------------------------------------------------------------------
    # Unit Test Stubs
    # -------------------------------------------------------------------------
    def test_cve_fetch(self) -> bool:
        cves = self.fetch_cves(start_date=(datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"))
        assert isinstance(cves, list)
        return True

    def test_ioc_matching(self) -> bool:
        # Add a test IOC
        ioc = ThreatIndicator(ioc_id="test_ioc", ioc_type="ip", value="192.168.1.1", source="test", confidence="high")
        with self._lock:
            self._iocs["test_ioc"] = ioc
        matches = self.match_ioc("192.168.1.1")
        assert len(matches) == 1
        return True

    def test_mitre_mapping(self) -> bool:
        mappings = self.map_to_mitre(cve_id="CVE-2021-44228")
        assert len(mappings) > 0
        return True

    def test_predictive_analysis(self) -> bool:
        results = self.predict_threat_likelihood(["apache", "windows", "linux"])
        assert "asset_assessments" in results
        return True
