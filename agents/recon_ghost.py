
"""
Aevibron Agent Corps -- SHADOW (Reconnaissance Ghost)
Codename: SHADOW
Domain: cyber_security
Role: Subdomain enumeration, technology fingerprinting, DNS enumeration, WHOIS analysis,
      OSINT, Google dorking, directory brute-forcing, port scanning (nmap integration),
      service detection.

Author: IRIS v1.0
"""

import json
import logging
import os
import re
import socket
import ssl
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from base_agent import BaseAgent, Task, TaskResult


class SHADOW(BaseAgent):
    """
    SHADOW -- The Reconnaissance Ghost. I see what others miss. I find what others hide.

    Capabilities:
    - Subdomain enumeration (passive + active)
    - Technology fingerprinting
    - DNS enumeration
    - WHOIS analysis
    - Social media intelligence (OSINT)
    - Google dorking
    - Directory brute-forcing
    - Port scanning (nmap integration)
    - Service detection and version identification
    """

    def __init__(self):
        super().__init__(
            name="SHADOW",
            domain="cyber_security",
            personality="Silent, methodical, and omniscient. I map the unseen terrain before the battle begins.",
            capabilities=[
                "subdomain_enumeration", "technology_fingerprinting", "dns_enumeration",
                "whois_analysis", "osint", "google_dorking", "directory_bruteforce",
                "port_scanning", "service_detection", "ssl_analysis", "banner_grabbing",
            ],
        )

    def _execute_impl(self, task: Task) -> Any:
        payload = task.payload
        request = payload.get("original_request", task.description).lower()
        target = payload.get("target", "")

        if not target:
            # Extract target from request
            target_match = re.search(r'(?:scan|enumerate|recon|target)\s+(?:of|for|on)?\s*([a-zA-Z0-9][-a-zA-Z0-9]*\.[-a-zA-Z0-9.]+)', request)
            if target_match:
                target = target_match.group(1)
            else:
                target = "example.com"

        if any(kw in request for kw in ["subdomain", "subdomains", "sub-domain"]):
            return self.enumerate_subdomains(target)
        elif any(kw in request for kw in ["fingerprint", "tech", "technology", "stack", "what runs"]):
            return self.fingerprint_technology(target)
        elif any(kw in request for kw in ["dns", "record", "mx", "txt", "ns"]):
            return self.enumerate_dns(target)
        elif any(kw in request for kw in ["whois", "domain info", "registrar"]):
            return self.analyze_whois(target)
        elif any(kw in request for kw in ["osint", "social", "intelligence", "people"]):
            return self.gather_osint(target)
        elif any(kw in request for kw in ["google dork", "dork", "search operator"]):
            return self.google_dork(target)
        elif any(kw in request for kw in ["directory", "brute force", "bruteforce", "path", "hidden"]):
            return self.bruteforce_directories(target)
        elif any(kw in request for kw in ["port scan", "nmap", "open port", "service scan"]):
            return self.scan_ports(target, payload)
        elif any(kw in request for kw in ["ssl", "certificate", "tls", "cert"]):
            return self.analyze_ssl(target)
        elif any(kw in request for kw in ["banner", "grab", "service version"]):
            return self.grab_banner(target, payload)
        else:
            # Full reconnaissance
            return self.full_reconnaissance(target)

    def enumerate_subdomains(self, target: str) -> Dict[str, Any]:
        """Enumerate subdomains using multiple techniques."""
        subdomains = set()

        # Common subdomain wordlist
        wordlist = [
            "www", "mail", "ftp", "localhost", "admin", "portal", "test", "dev",
            "api", "app", "blog", "shop", "store", "cdn", "static", "assets",
            "media", "img", "images", "video", "docs", "wiki", "support",
            "help", "status", "monitor", "grafana", "prometheus", "kibana",
            "jenkins", "gitlab", "github", "bitbucket", "jira", "confluence",
            "staging", "prod", "production", "beta", "alpha", "demo", "sandbox",
            "vpn", "remote", "ssh", "sftp", "db", "database", "mysql", "postgres",
            "redis", "elastic", "search", "es", "mongo", "mongodb",
            "webmail", "email", "smtp", "mx", "ns1", "ns2", "dns",
            "git", "svn", "cvs", "backup", "bak", "old", "archive",
            "internal", "intranet", "extranet", "private", "secure",
            "api-v1", "api-v2", "api-v3", "graphql", "rest", "ws", "websocket",
            "mobile", "m", "app", "ios", "android", "web", "www2", "www3",
            "ftp", "sftp", "files", "upload", "download", "share",
            "auth", "login", "sso", "oauth", "idp", "accounts",
            "pay", "payment", "billing", "invoice", "cart", "checkout",
            "analytics", "tracking", "metrics", "stats", "data",
        ]

        # DNS resolution check
        for word in wordlist:
            subdomain = f"{word}.{target}"
            try:
                socket.gethostbyname(subdomain)
                subdomains.add(subdomain)
                self._logger.info(f"[SHADOW] Found subdomain: {subdomain}")
            except socket.gaierror:
                pass
            except Exception as e:
                self._logger.debug(f"[SHADOW] Error checking {subdomain}: {e}")

        # Check certificate transparency logs (simulated)
        ct_subdomains = self._check_certificate_transparency(target)
        subdomains.update(ct_subdomains)

        # Check DNS zone transfer (simulated)
        zone_subdomains = self._attempt_zone_transfer(target)
        subdomains.update(zone_subdomains)

        return {
            "target": target,
            "total_found": len(subdomains),
            "subdomains": sorted(list(subdomains)),
            "methods_used": ["dns_resolution", "wordlist", "certificate_transparency", "zone_transfer_attempt"],
            "recommendations": [
                "Verify each subdomain is intentional and necessary",
                "Remove unused subdomains to reduce attack surface",
                "Ensure all subdomains have proper SSL certificates",
                "Monitor for new subdomain registrations",
            ],
        }

    def _check_certificate_transparency(self, target: str) -> set:
        """Check certificate transparency logs for subdomains."""
        # In production, this would query crt.sh or similar CT log aggregators
        # For now, return common patterns
        common = [f"www.{target}", f"mail.{target}", f"api.{target}"]
        found = set()
        for sub in common:
            try:
                socket.gethostbyname(sub)
                found.add(sub)
            except:
                pass
        return found

    def _attempt_zone_transfer(self, target: str) -> set:
        """Attempt DNS zone transfer (AXFR)."""
        found = set()
        try:
            # Try to get NS records first
            import dns.resolver
            ns_records = dns.resolver.resolve(target, 'NS')
            for ns in ns_records:
                try:
                    zone = dns.zone.from_xfr(dns.query.xfr(str(ns), target))
                    for name, node in zone.nodes.items():
                        found.add(f"{name}.{target}")
                except Exception:
                    pass
        except ImportError:
            self._logger.warning("[SHADOW] dnspython not installed, skipping zone transfer")
        except Exception as e:
            self._logger.debug(f"[SHADOW] Zone transfer failed: {e}")
        return found

    def fingerprint_technology(self, target: str) -> Dict[str, Any]:
        """Fingerprint technologies used by target."""
        technologies = []
        headers = {}

        try:
            # HTTP request to get headers
            url = f"http://{target}"
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response = urllib.request.urlopen(req, timeout=10)
            headers = dict(response.headers)

            # Analyze headers for technology fingerprints
            server = headers.get('Server', '')
            if 'nginx' in server.lower():
                technologies.append({"name": "nginx", "category": "web_server", "version": server})
            elif 'apache' in server.lower():
                technologies.append({"name": "Apache", "category": "web_server", "version": server})
            elif 'cloudflare' in server.lower():
                technologies.append({"name": "Cloudflare", "category": "cdn/waf", "version": "unknown"})

            x_powered = headers.get('X-Powered-By', '')
            if 'php' in x_powered.lower():
                technologies.append({"name": "PHP", "category": "language", "version": x_powered})
            elif 'asp.net' in x_powered.lower():
                technologies.append({"name": "ASP.NET", "category": "framework", "version": x_powered})

            # Check for common frameworks via cookies
            set_cookie = headers.get('Set-Cookie', '')
            if 'laravel' in set_cookie.lower():
                technologies.append({"name": "Laravel", "category": "framework", "version": "unknown"})
            if 'django' in set_cookie.lower():
                technologies.append({"name": "Django", "category": "framework", "version": "unknown"})

            # Check for WAF
            if 'cf-ray' in headers:
                technologies.append({"name": "Cloudflare WAF", "category": "waf", "version": "unknown"})
            if 'akamai' in str(headers).lower():
                technologies.append({"name": "Akamai", "category": "cdn/waf", "version": "unknown"})

            # Read HTML content for more fingerprints
            content = response.read().decode('utf-8', errors='ignore')

            if 'react' in content.lower() or 'reactroot' in content.lower():
                technologies.append({"name": "React", "category": "frontend", "version": "unknown"})
            if 'vue' in content.lower():
                technologies.append({"name": "Vue.js", "category": "frontend", "version": "unknown"})
            if 'angular' in content.lower():
                technologies.append({"name": "Angular", "category": "frontend", "version": "unknown"})
            if 'jquery' in content.lower():
                technologies.append({"name": "jQuery", "category": "frontend", "version": "unknown"})
            if 'bootstrap' in content.lower():
                technologies.append({"name": "Bootstrap", "category": "frontend", "version": "unknown"})
            if 'wordpress' in content.lower() or '/wp-content/' in content.lower():
                technologies.append({"name": "WordPress", "category": "cms", "version": "unknown"})
            if 'drupal' in content.lower():
                technologies.append({"name": "Drupal", "category": "cms", "version": "unknown"})

        except Exception as e:
            self._logger.warning(f"[SHADOW] Could not fingerprint {target}: {e}")

        return {
            "target": target,
            "technologies_found": len(technologies),
            "technologies": technologies,
            "headers": headers,
            "recommendations": [
                "Remove or obfuscate Server and X-Powered-By headers",
                "Keep all software up to date with security patches",
                "Consider using a CDN/WAF for additional protection",
            ],
        }

    def enumerate_dns(self, target: str) -> Dict[str, Any]:
        """Enumerate DNS records."""
        records = {}

        record_types = ['A', 'AAAA', 'MX', 'NS', 'TXT', 'SOA', 'CNAME', 'PTR', 'SRV', 'CAA']

        for record_type in record_types:
            try:
                import dns.resolver
                answers = dns.resolver.resolve(target, record_type)
                records[record_type] = [str(rdata) for rdata in answers]
            except ImportError:
                self._logger.warning("[SHADOW] dnspython not installed")
                break
            except Exception as e:
                records[record_type] = [f"Error: {e}"]

        # Fallback to socket for basic A records
        if 'A' not in records or not records['A']:
            try:
                ip = socket.gethostbyname(target)
                records['A'] = [ip]
            except:
                pass

        return {
            "target": target,
            "records": records,
            "recommendations": [
                "Ensure SPF records are properly configured",
                "Implement DMARC and DKIM for email security",
                "Use DNSSEC to prevent DNS spoofing",
                "Regularly audit DNS records for unauthorized changes",
            ],
        }

    def analyze_whois(self, target: str) -> Dict[str, Any]:
        """Perform WHOIS analysis."""
        whois_data = {}

        try:
            import whois
            domain_info = whois.whois(target)
            whois_data = {
                "domain_name": domain_info.domain_name,
                "registrar": domain_info.registrar,
                "creation_date": str(domain_info.creation_date),
                "expiration_date": str(domain_info.expiration_date),
                "name_servers": domain_info.name_servers,
                "status": domain_info.status,
                "emails": domain_info.emails,
                "dnssec": domain_info.dnssec,
            }
        except ImportError:
            self._logger.warning("[SHADOW] python-whois not installed")
            whois_data = {"error": "python-whois library not installed. Install with: pip install python-whois"}
        except Exception as e:
            whois_data = {"error": str(e)}

        return {
            "target": target,
            "whois_data": whois_data,
            "recommendations": [
                "Enable domain privacy protection if not already enabled",
                "Monitor domain expiration dates",
                "Ensure WHOIS data is accurate and up to date",
                "Enable DNSSEC for the domain",
            ],
        }

    def gather_osint(self, target: str) -> Dict[str, Any]:
        """Gather OSINT on target."""
        findings = {
            "target": target,
            "sources_checked": [],
            "findings": [],
            "recommendations": [],
        }

        # Check for exposed files
        exposed_files = [
            "/robots.txt", "/sitemap.xml", "/.git/config",
            "/.env", "/.htaccess", "/crossdomain.xml",
            "/security.txt", "/.well-known/security.txt",
        ]

        for file_path in exposed_files:
            try:
                url = f"http://{target}{file_path}"
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                })
                response = urllib.request.urlopen(req, timeout=5)
                if response.status == 200:
                    content = response.read().decode('utf-8', errors='ignore')[:500]
                    findings["findings"].append({
                        "type": "exposed_file",
                        "path": file_path,
                        "content_preview": content,
                        "severity": "medium" if file_path in ['/.env', '/.git/config'] else "low",
                    })
            except:
                pass

        findings["sources_checked"] = ["robots.txt", "sitemap.xml", "exposed_config_files"]
        findings["recommendations"] = [
            "Remove .env and .git/config from public access",
            "Review robots.txt for information disclosure",
            "Implement proper access controls on sensitive files",
        ]

        return findings

    def google_dork(self, target: str) -> Dict[str, Any]:
        """Generate Google dork queries for target."""
        dorks = [
            f"site:{target} filetype:pdf",
            f"site:{target} filetype:doc OR filetype:docx",
            f"site:{target} filetype:xls OR filetype:xlsx",
            f"site:{target} inurl:admin",
            f"site:{target} inurl:login",
            f"site:{target} intitle:"index of"",
            f"site:{target} ext:sql OR ext:dump OR ext:backup",
            f"site:{target} intext:"password" OR intext:"secret" OR intext:"api_key"",
            f"site:{target} inurl:api OR inurl:swagger OR inurl:graphql",
            f"site:{target} filetype:log",
            f"site:pastebin.com {target}",
            f"site:github.com {target}",
            f"site:{target} intext:"confidential" OR intext:"internal use only"",
        ]

        return {
            "target": target,
            "dorks": dorks,
            "usage": "Use these queries in Google search to find exposed information",
            "recommendations": [
                "Regularly monitor for leaked documents and credentials",
                "Implement DLP (Data Loss Prevention) policies",
                "Use Google Alerts for brand monitoring",
            ],
        }

    def bruteforce_directories(self, target: str) -> Dict[str, Any]:
        """Brute force common directories and files."""
        wordlist = [
            "admin", "administrator", "api", "backup", "bak", "config",
            "console", "dashboard", "db", "debug", "dev", "env",
            "git", "graphql", "install", "login", "manage", "panel",
            "phpmyadmin", "robots.txt", "server-status", "setup", "sitemap.xml",
            "swagger", "test", "tmp", "upload", "wp-admin", "wp-login",
            ".env", ".git", ".htaccess", ".svn", ".DS_Store",
            "api/v1", "api/v2", "api/docs", "v1", "v2",
            "actuator", "health", "metrics", "prometheus", "swagger-ui.html",
        ]

        found = []

        for word in wordlist:
            url = f"http://{target}/{word}"
            try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                })
                response = urllib.request.urlopen(req, timeout=5)
                if response.status in [200, 301, 302, 401, 403]:
                    found.append({
                        "path": f"/{word}",
                        "status": response.status,
                        "size": len(response.read()),
                    })
            except urllib.error.HTTPError as e:
                if e.code in [200, 301, 302, 401, 403]:
                    found.append({
                        "path": f"/{word}",
                        "status": e.code,
                        "size": 0,
                    })
            except:
                pass

        return {
            "target": target,
            "total_tested": len(wordlist),
            "found": len(found),
            "results": found,
            "recommendations": [
                "Remove or protect sensitive directories",
                "Implement proper authentication on admin panels",
                "Use non-standard paths for admin interfaces",
                "Implement rate limiting to prevent brute force",
            ],
        }

    def scan_ports(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Scan ports using nmap or fallback to socket scanning."""
        ports = payload.get("ports", "top1000")
        scan_type = payload.get("scan_type", "tcp_syn")

        results = {
            "target": target,
            "scan_type": scan_type,
            "ports_scanned": 0,
            "open_ports": [],
            "method": "",
        }

        # Try nmap first
        try:
            nmap_cmd = ["nmap", "-sV", "-sC", "--open", "-T4", target]
            if ports != "top1000":
                nmap_cmd.insert(1, f"-p{ports}")

            self._logger.info(f"[SHADOW] Running nmap: {' '.join(nmap_cmd)}")

            process = subprocess.run(
                nmap_cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            results["nmap_output"] = process.stdout
            results["method"] = "nmap"
            results["open_ports"] = self._parse_nmap_output(process.stdout)
            results["ports_scanned"] = len(results["open_ports"])

        except FileNotFoundError:
            self._logger.warning("[SHADOW] nmap not found, falling back to socket scanning")
            results = self._socket_port_scan(target, ports)
        except subprocess.TimeoutExpired:
            self._logger.warning("[SHADOW] nmap timed out, falling back to socket scanning")
            results = self._socket_port_scan(target, ports)
        except Exception as e:
            self._logger.warning(f"[SHADOW] nmap failed: {e}, falling back to socket scanning")
            results = self._socket_port_scan(target, ports)

        return results

    def _parse_nmap_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse nmap output to extract port information."""
        open_ports = []

        for line in output.split('\n'):
            # Match lines like: 80/tcp  open  http    nginx 1.18.0
            match = re.match(r'(\d+)/(tcp|udp)\s+(\w+)\s+(\S+)\s*(.*)', line)
            if match:
                port, protocol, state, service, version = match.groups()
                if state.lower() == 'open':
                    open_ports.append({
                        "port": int(port),
                        "protocol": protocol,
                        "state": state,
                        "service": service,
                        "version": version.strip(),
                    })

        return open_ports

    def _socket_port_scan(self, target: str, ports: str) -> Dict[str, Any]:
        """Fallback port scan using Python sockets."""
        open_ports = []

        if ports == "top1000":
            port_list = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995, 1723, 3306, 3389, 5432, 5900, 8080, 8443, 8888, 9200, 27017]
        else:
            port_list = [int(p.strip()) for p in ports.split(",")]

        for port in port_list:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((target, port))
                if result == 0:
                    try:
                        service = socket.getservbyport(port, 'tcp')
                    except:
                        service = "unknown"
                    open_ports.append({
                        "port": port,
                        "protocol": "tcp",
                        "state": "open",
                        "service": service,
                        "version": "",
                    })
                sock.close()
            except Exception as e:
                self._logger.debug(f"[SHADOW] Error scanning port {port}: {e}")

        return {
            "target": target,
            "scan_type": "tcp_connect",
            "ports_scanned": len(port_list),
            "open_ports": open_ports,
            "method": "python_socket",
        }

    def analyze_ssl(self, target: str) -> Dict[str, Any]:
        """Analyze SSL/TLS configuration."""
        findings = {
            "target": target,
            "certificate_info": {},
            "vulnerabilities": [],
            "recommendations": [],
        }

        try:
            context = ssl.create_default_context()
            with socket.create_connection((target, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=target) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()

                    findings["certificate_info"] = {
                        "subject": cert.get('subject'),
                        "issuer": cert.get('issuer'),
                        "not_before": cert.get('notBefore'),
                        "not_after": cert.get('notAfter'),
                        "serial_number": cert.get('serialNumber'),
                        "subject_alt_names": cert.get('subjectAltName', []),
                        "cipher": cipher,
                        "tls_version": version,
                    }

                    # Check TLS version
                    if version in ['TLSv1', 'TLSv1.1']:
                        findings["vulnerabilities"].append({
                            "name": "Weak TLS Version",
                            "severity": "high",
                            "details": f"Using {version}, which is deprecated. Upgrade to TLS 1.2 or 1.3.",
                        })

                    # Check certificate expiry
                    from datetime import datetime
                    not_after = cert.get('notAfter')
                    if not_after:
                        expiry = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                        days_until_expiry = (expiry - datetime.utcnow()).days
                        if days_until_expiry < 30:
                            findings["vulnerabilities"].append({
                                "name": "Certificate Expiring Soon",
                                "severity": "medium",
                                "details": f"Certificate expires in {days_until_expiry} days.",
                            })

        except Exception as e:
            findings["error"] = str(e)

        findings["recommendations"] = [
            "Use TLS 1.2 or 1.3 only",
            "Disable weak cipher suites (RC4, DES, 3DES)",
            "Enable HSTS with long max-age",
            "Use strong certificate key lengths (RSA 2048+ or ECC)",
            "Monitor certificate expiration",
        ]

        return findings

    def grab_banner(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Grab service banners."""
        port = payload.get("port", 80)

        banners = []

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((target, port))

            # Send a generic probe
            sock.send(b"\r\n")
            banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()

            if banner:
                banners.append({
                    "port": port,
                    "banner": banner,
                    "service_guess": self._guess_service_from_banner(banner),
                })

            sock.close()
        except Exception as e:
            banners.append({
                "port": port,
                "error": str(e),
            })

        return {
            "target": target,
            "banners": banners,
        }

    def _guess_service_from_banner(self, banner: str) -> str:
        """Guess service from banner."""
        banner_lower = banner.lower()
        if 'ssh' in banner_lower:
            return "SSH"
        elif 'ftp' in banner_lower:
            return "FTP"
        elif 'smtp' in banner_lower:
            return "SMTP"
        elif 'http' in banner_lower:
            return "HTTP"
        elif 'mysql' in banner_lower:
            return "MySQL"
        elif 'postgres' in banner_lower:
            return "PostgreSQL"
        elif 'redis' in banner_lower:
            return "Redis"
        elif 'mongodb' in banner_lower:
            return "MongoDB"
        return "Unknown"

    def full_reconnaissance(self, target: str) -> Dict[str, Any]:
        """Perform full reconnaissance on target."""
        self._logger.info(f"[SHADOW] Starting full reconnaissance on {target}")

        results = {
            "target": target,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "subdomains": self.enumerate_subdomains(target),
            "dns_records": self.enumerate_dns(target),
            "whois": self.analyze_whois(target),
            "technology": self.fingerprint_technology(target),
            "osint": self.gather_osint(target),
            "port_scan": self.scan_ports(target, {}),
            "ssl_analysis": self.analyze_ssl(target),
            "directories": self.bruteforce_directories(target),
        }

        self._logger.info(f"[SHADOW] Full reconnaissance complete for {target}")

        return results


__all__ = ["SHADOW"]
