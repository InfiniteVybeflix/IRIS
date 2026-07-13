"""
IRIS v1.0 — Burp Suite Bridge

Burp Suite Enterprise/Professional REST API integration.
Scan initiation, status monitoring, issue extraction, report generation.

Dependencies: requests
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class BurpBridge(BaseTool):
    """Burp Suite Enterprise/Professional REST API client."""

    name: str = "burp_bridge"
    category: str = "network"
    dependencies: List[str] = ["requests"]

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self.base_url = (base_url or os.environ.get("IRIS_BURP_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("IRIS_BURP_API_KEY", "")
        self._session = requests.Session()
        self._session.headers.update({"Authorization": self.api_key, "Content-Type": "application/json"})
        self._session.verify = True

    def _request(self, method: str, endpoint: str, json_data: Optional[Dict[str, Any]] = None,
                 params: Optional[Dict[str, str]] = None, timeout: int = 60) -> requests.Response:
        return self._session.request(method=method, url=f"{self.base_url}{endpoint}",
            json=json_data, params=params, timeout=timeout)

    def _run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {}

    def start_scan(self, target: str, config: Optional[str] = None, config_id: Optional[str] = None) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_target = self.sanitize_input(target)
            payload: Dict[str, Any] = {"urls": [safe_target]}
            if config_id:
                payload["scan_configurations"] = [{"id": config_id}]
            elif config:
                payload["scan_configurations"] = [{"name": config}]
            resp = self._request("POST", "/api/scans", json_data=payload)
            resp.raise_for_status()
            data = resp.json()
            res = self._build_result(success=True, action="start_scan", output=data,
                parsed={"scan_id": data.get("id"), "target": safe_target})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("start_scan failed")
            res = self._build_result(success=False, action="start_scan", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def get_scan_status(self, scan_id: str) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_id = self.sanitize_input(scan_id)
            resp = self._request("GET", f"/api/scans/{safe_id}")
            resp.raise_for_status()
            data = resp.json()
            res = self._build_result(success=True, action="get_scan_status", output=data,
                parsed={"scan_id": safe_id, "status": data.get("status"), "progress": data.get("progress", 0),
                    "issue_counts": data.get("issue_counts", {})})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("get_scan_status failed")
            res = self._build_result(success=False, action="get_scan_status", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def get_issues(self, scan_id: str) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_id = self.sanitize_input(scan_id)
            resp = self._request("GET", f"/api/scans/{safe_id}/issues")
            resp.raise_for_status()
            data = resp.json()
            issues = data if isinstance(data, list) else data.get("issues", [])
            severity_counts: Dict[str, int] = {}
            for issue in issues:
                sev = issue.get("severity", "unknown")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
            res = self._build_result(success=True, action="get_issues", output=data,
                parsed={"scan_id": safe_id, "total_issues": len(issues), "severity_breakdown": severity_counts, "issues": issues})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("get_issues failed")
            res = self._build_result(success=False, action="get_issues", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def generate_report(self, scan_id: str, report_format: str = "html") -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_id = self.sanitize_input(scan_id)
            payload = {"format": report_format}
            resp = self._request("POST", f"/api/scans/{safe_id}/report", json_data=payload)
            resp.raise_for_status()
            data = resp.json()
            res = self._build_result(success=True, action="generate_report", output=data,
                parsed={"scan_id": safe_id, "format": report_format, "download_url": data.get("url")})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("generate_report failed")
            res = self._build_result(success=False, action="generate_report", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def health_check(self) -> Dict[str, Any]:
        base = super().health_check()
        if base["status"] == "available" and self.base_url:
            try:
                resp = self._request("GET", "/api", timeout=10)
                if resp.status_code < 500:
                    base["message"] = "Burp API reachable."
                else:
                    base["status"] = "error"
                    base["message"] = f"Burp API HTTP {resp.status_code}"
            except Exception as exc:
                base["status"] = "error"
                base["message"] = f"Burp API unreachable: {exc}"
        return base


__all__ = ["BurpBridge"]
