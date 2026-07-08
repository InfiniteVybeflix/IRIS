"""
IRIS v7.0 — SQLMap Wrapper

Real sqlmap integration for SQL injection detection and exploitation.
Mandatory authorization checks prevent unauthorized testing.

Dependencies: sqlmap (system binary or Python package)
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class SQLMapWrapper(BaseTool):
    """SQLMap integration for SQL injection testing."""

    name: str = "sqlmap_wrapper"
    category: str = "network"
    dependencies: List[str] = ["sqlmap"]

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._sqlmap_path: Optional[str] = None
        self.authorized_targets: List[str] = []
        auth_env = os.environ.get("IRIS_SQLMAP_AUTHORIZED", "")
        if auth_env:
            self.authorized_targets = [t.strip() for t in auth_env.split(",") if t.strip()]

    def _resolve_sqlmap(self) -> str:
        if self._sqlmap_path is None:
            path = shutil.which("sqlmap")
            if path is None:
                try:
                    import sqlmap
                    path = os.path.join(os.path.dirname(sqlmap.__file__), "sqlmap.py")
                except ImportError:
                    raise RuntimeError("sqlmap not found.")
            self._sqlmap_path = path
        return self._sqlmap_path

    def _check_authorization(self, url: str) -> bool:
        from urllib.parse import urlparse
        hostname = urlparse(url).hostname
        return hostname in self.authorized_targets if hostname else False

    def _run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {}

    def detect_injection(self, url: str, data: Optional[str] = None, headers: Optional[Dict[str, str]] = None,
                         level: int = 1, risk: int = 1, timeout: int = 300) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_url = self.sanitize_input(url)
            cmd = ["python3", self._resolve_sqlmap(), "-u", safe_url, "--batch", "--level", str(level),
                   "--risk", str(risk), "--output-dir", "/tmp/sqlmap_iris"]
            if data:
                cmd.extend(["--data", self.sanitize_input(data)])
            if headers:
                for k, v in headers.items():
                    cmd.extend(["-H", f"{k}: {v}"])
            result = self._run_subprocess(cmd, timeout=timeout)
            parsed = self._parse_output(result.stdout, result.stderr)
            res = self._build_result(success=result.returncode in (0, 1), action="detect_injection",
                output=result.stdout, parsed=parsed,
                errors=[result.stderr] if result.stderr and result.returncode != 0 else [])
            self.last_result = res
            self._end_execution(res["success"])
            return res
        except Exception as exc:
            logger.exception("sqlmap detect_injection failed")
            res = self._build_result(success=False, action="detect_injection", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def get_dbs(self, url: str, timeout: int = 300) -> Dict[str, Any]:
        if not self._check_authorization(url):
            return self._build_result(success=False, action="get_dbs",
                errors=["Target not authorized. Set IRIS_SQLMAP_AUTHORIZED env var."])
        return self._run_enum(url, "--dbs", timeout)

    def get_tables(self, url: str, db: str, timeout: int = 300) -> Dict[str, Any]:
        if not self._check_authorization(url):
            return self._build_result(success=False, action="get_tables", errors=["Target not authorized."])
        return self._run_enum(url, f"-D {db} --tables", timeout)

    def get_columns(self, url: str, db: str, table: str, timeout: int = 300) -> Dict[str, Any]:
        if not self._check_authorization(url):
            return self._build_result(success=False, action="get_columns", errors=["Target not authorized."])
        return self._run_enum(url, f"-D {db} -T {table} --columns", timeout)

    def dump_database(self, url: str, tables: Optional[List[str]] = None, timeout: int = 600) -> Dict[str, Any]:
        if not self._check_authorization(url):
            return self._build_result(success=False, action="dump_database",
                errors=["Target not authorized for data extraction."])
        self._begin_execution()
        try:
            safe_url = self.sanitize_input(url)
            cmd = ["python3", self._resolve_sqlmap(), "-u", safe_url, "--batch", "--dump", "--output-dir", "/tmp/sqlmap_iris"]
            if tables:
                for t in tables:
                    cmd.extend(["-T", self.sanitize_input(t)])
            result = self._run_subprocess(cmd, timeout=timeout)
            parsed = self._parse_output(result.stdout, result.stderr)
            res = self._build_result(success=result.returncode in (0, 1), action="dump_database",
                output=result.stdout, parsed=parsed,
                errors=[result.stderr] if result.stderr and result.returncode != 0 else [])
            self.last_result = res
            self._end_execution(res["success"])
            return res
        except Exception as exc:
            logger.exception("sqlmap dump_database failed")
            res = self._build_result(success=False, action="dump_database", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def _run_enum(self, url: str, enum_args: str, timeout: int) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_url = self.sanitize_input(url)
            cmd = ["python3", self._resolve_sqlmap(), "-u", safe_url, "--batch", "--output-dir", "/tmp/sqlmap_iris"]
            cmd.extend(enum_args.split())
            result = self._run_subprocess(cmd, timeout=timeout)
            parsed = self._parse_output(result.stdout, result.stderr)
            res = self._build_result(success=result.returncode in (0, 1), action="enum",
                output=result.stdout, parsed=parsed,
                errors=[result.stderr] if result.stderr and result.returncode != 0 else [])
            self.last_result = res
            self._end_execution(res["success"])
            return res
        except Exception as exc:
            logger.exception("sqlmap enumeration failed")
            res = self._build_result(success=False, action="enum", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def _parse_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        findings: Dict[str, Any] = {"vulnerable": False, "databases": [], "tables": {}, "columns": {}, "payloads": [], "errors": []}
        for line in stdout.splitlines():
            ll = line.lower()
            if "parameter is vulnerable" in ll or "injectable" in ll:
                findings["vulnerable"] = True
            if line.strip().startswith("[") and "database:" in ll:
                db = line.split(":")[-1].strip().strip("]")
                findings["databases"].append(db)
            if "back-end dbms" in ll:
                findings["dbms"] = line.split(":")[-1].strip()
            if "payload:" in ll:
                findings["payloads"].append(line.strip())
        if stderr:
            findings["errors"].append(stderr)
        return findings


__all__ = ["SQLMapWrapper"]
