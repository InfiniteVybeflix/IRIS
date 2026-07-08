"""
IRIS v7.0 — Nmap Wrapper

Real nmap integration for port scanning, service detection, OS fingerprinting,
and network discovery. Parses XML and grepable output into structured dicts.

Dependencies: nmap (system binary)
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class NmapWrapper(BaseTool):
    """Nmap port scanner and network reconnaissance tool."""

    name: str = "nmap_wrapper"
    category: str = "network"
    dependencies: List[str] = ["nmap"]

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._nmap_path: Optional[str] = None

    def _resolve_nmap(self) -> str:
        if self._nmap_path is None:
            path = shutil.which("nmap")
            if path is None:
                raise RuntimeError("nmap binary not found in PATH.")
            self._nmap_path = path
        return self._nmap_path

    def _run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {}

    def scan_ports(self, target: str, ports: Optional[str] = None, args: str = "-sV -sC", timeout: int = 300) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_target = self.sanitize_input(target)
            cmd = [self._resolve_nmap(), "-oX", "-"]
            if ports:
                cmd.extend(["-p", self.sanitize_input(ports)])
            cmd.extend(self.sanitize_input(args).split())
            cmd.append(safe_target)
            result = self._run_subprocess(cmd, timeout=timeout)
            if result.returncode != 0:
                res = self._build_result(success=False, action="scan_ports", output=result.stderr,
                    parsed=self._parse_error(result.stderr), errors=[f"nmap exited {result.returncode}"])
                self.last_result = res
                self._end_execution(False)
                return res
            parsed = self._parse_xml(result.stdout)
            res = self._build_result(success=True, action="scan_ports", output=result.stdout, parsed=parsed)
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("nmap scan_ports failed")
            res = self._build_result(success=False, action="scan_ports", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def scan_subnet(self, subnet: str, args: str = "-sn", timeout: int = 300) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_subnet = self.sanitize_input(subnet)
            cmd = [self._resolve_nmap(), "-oX", "-"] + self.sanitize_input(args).split() + [safe_subnet]
            result = self._run_subprocess(cmd, timeout=timeout)
            parsed = self._parse_xml(result.stdout)
            hosts = [h for h in parsed.get("hosts", []) if h.get("status") == "up"]
            res = self._build_result(success=result.returncode == 0, action="scan_subnet", output=result.stdout,
                parsed={"live_hosts": hosts, "total_scanned": len(parsed.get("hosts", []))},
                errors=[result.stderr] if result.returncode != 0 else [])
            self.last_result = res
            self._end_execution(result.returncode == 0)
            return res
        except Exception as exc:
            logger.exception("nmap scan_subnet failed")
            res = self._build_result(success=False, action="scan_subnet", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def os_detect(self, target: str, timeout: int = 300) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_target = self.sanitize_input(target)
            cmd = [self._resolve_nmap(), "-O", "-oX", "-", safe_target]
            result = self._run_subprocess(cmd, timeout=timeout)
            parsed = self._parse_xml(result.stdout)
            os_matches = []
            for host in parsed.get("hosts", []):
                os_matches.extend(host.get("osmatches", []))
            res = self._build_result(success=result.returncode == 0, action="os_detect", output=result.stdout,
                parsed={"os_matches": os_matches}, errors=[result.stderr] if result.returncode != 0 else [])
            self.last_result = res
            self._end_execution(result.returncode == 0)
            return res
        except Exception as exc:
            logger.exception("nmap os_detect failed")
            res = self._build_result(success=False, action="os_detect", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def service_scan(self, target: str, ports: Optional[str] = None, timeout: int = 300) -> Dict[str, Any]:
        return self.scan_ports(target, ports=ports, args="-sV -sC", timeout=timeout)

    def stealth_scan(self, target: str, ports: Optional[str] = None, rate: int = 100, timeout: int = 600) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_target = self.sanitize_input(target)
            cmd = [self._resolve_nmap(), "-sS", "-oX", "-", "--max-rate", str(rate)]
            if ports:
                cmd.extend(["-p", self.sanitize_input(ports)])
            cmd.append(safe_target)
            result = self._run_subprocess(cmd, timeout=timeout)
            parsed = self._parse_xml(result.stdout)
            res = self._build_result(success=result.returncode == 0, action="stealth_scan", output=result.stdout,
                parsed=parsed, errors=[result.stderr] if result.returncode != 0 else [])
            self.last_result = res
            self._end_execution(result.returncode == 0)
            return res
        except Exception as exc:
            logger.exception("nmap stealth_scan failed")
            res = self._build_result(success=False, action="stealth_scan", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def _parse_xml(self, xml_data: str) -> Dict[str, Any]:
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as exc:
            logger.error(f"XML parse error: {exc}")
            return {"hosts": [], "scan_info": {}, "error": str(exc)}
        parsed: Dict[str, Any] = {"hosts": [], "scan_info": {}}
        si = root.find("scaninfo")
        if si is not None:
            parsed["scan_info"] = dict(si.attrib)
        for host in root.findall("host"):
            hd: Dict[str, Any] = {"status": None, "addresses": {}, "hostnames": [], "ports": [], "osmatches": []}
            status = host.find("status")
            if status is not None:
                hd["status"] = status.get("state")
            for addr in host.findall("address"):
                hd["addresses"][addr.get("addrtype", "unknown")] = addr.get("addr")
            he = host.find("hostnames")
            if he is not None:
                for hn in he.findall("hostname"):
                    hd["hostnames"].append(hn.get("name"))
            pe = host.find("ports")
            if pe is not None:
                for port in pe.findall("port"):
                    pd = {"protocol": port.get("protocol"), "portid": port.get("portid"), "state": None, "service": {}}
                    st = port.find("state")
                    if st is not None:
                        pd["state"] = st.get("state")
                    sv = port.find("service")
                    if sv is not None:
                        pd["service"] = dict(sv.attrib)
                    hd["ports"].append(pd)
            oe = host.find("os")
            if oe is not None:
                for om in oe.findall("osmatch"):
                    hd["osmatches"].append({
                        "name": om.get("name"), "accuracy": om.get("accuracy"),
                        "osclass": [dict(cls.attrib) for cls in om.findall("osclass")],
                    })
            parsed["hosts"].append(hd)
        return parsed

    def _parse_error(self, stderr: str) -> Dict[str, Any]:
        return {"error_raw": stderr, "error_type": "nmap_execution_error"}


__all__ = ["NmapWrapper"]
