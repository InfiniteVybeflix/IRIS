"""
IRIS v1.0 — Metasploit Bridge

Metasploit Framework RPC integration. Exploit search, session management,
payload generation. Safe-environment enforcement only.

Dependencies: pymetasploit3
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class MetasploitBridge(BaseTool):
    """Metasploit Framework RPC bridge. Safe-environment only execution."""

    name: str = "metasploit_bridge"
    category: str = "network"
    dependencies: List[str] = ["pymetasploit3"]

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._client: Optional[Any] = None
        self._connected: bool = False

    def _is_safe_environment(self) -> bool:
        return os.environ.get("IRIS_SAFE_ENV", "").lower() in ("true", "1", "yes")

    def _require_safe(self) -> None:
        if not self._is_safe_environment():
            raise RuntimeError("Not in safe environment. Set IRIS_SAFE_ENV=true.")

    def connect(self, host: str, port: int = 55553, username: str = "msf", password: str = "", ssl: bool = True) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_host = self.sanitize_input(host)
            safe_pass = password or os.environ.get("IRIS_MSFRPCD_PASS", "")
            try:
                from pymetasploit3.msfrpc import MsfRpcClient
            except ImportError:
                res = self._build_result(success=False, action="connect", errors=["pymetasploit3 not installed."])
                self.last_result = res
                self._end_execution(False)
                return res
            self._client = MsfRpcClient(password=safe_pass, server=safe_host, port=port, username=username, ssl=ssl)
            self._connected = True
            res = self._build_result(success=True, action="connect",
                output=f"Connected to {safe_host}:{port}", parsed={"host": safe_host, "port": port, "ssl": ssl})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("Metasploit connect failed")
            self._connected = False
            res = self._build_result(success=False, action="connect", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def search_exploits(self, keyword: str) -> Dict[str, Any]:
        self._begin_execution()
        try:
            if not self._connected or self._client is None:
                return self._build_result(success=False, action="search_exploits", errors=["Not connected."])
            safe_kw = self.sanitize_input(keyword)
            modules = self._client.modules.search(safe_kw)
            exploits = [m for m in modules if m.get("type") == "exploit"]
            res = self._build_result(success=True, action="search_exploits", output=modules,
                parsed={"total": len(modules), "exploits": exploits, "keyword": safe_kw})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("search_exploits failed")
            res = self._build_result(success=False, action="search_exploits", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def run_exploit(self, module: str, options: Dict[str, str], payload: Optional[str] = None) -> Dict[str, Any]:
        self._begin_execution()
        try:
            self._require_safe()
            if not self._connected or self._client is None:
                return self._build_result(success=False, action="run_exploit", errors=["Not connected."])
            safe_module = self.sanitize_input(module)
            exploit = self._client.modules.use("exploit", safe_module)
            for k, v in options.items():
                exploit[k] = v
            if payload:
                exploit["PAYLOAD"] = payload
            job_id = exploit.execute()
            res = self._build_result(success=True, action="run_exploit", output={"job_id": job_id},
                parsed={"module": safe_module, "options": options, "payload": payload})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("run_exploit failed")
            res = self._build_result(success=False, action="run_exploit", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def get_sessions(self) -> Dict[str, Any]:
        self._begin_execution()
        try:
            if not self._connected or self._client is None:
                return self._build_result(success=False, action="get_sessions", errors=["Not connected."])
            sessions = self._client.sessions.list
            res = self._build_result(success=True, action="get_sessions", output=sessions,
                parsed={"session_count": len(sessions), "sessions": sessions})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("get_sessions failed")
            res = self._build_result(success=False, action="get_sessions", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def generate_payload(self, payload_type: str, lhost: str, lport: int, format_type: str = "python") -> Dict[str, Any]:
        self._begin_execution()
        try:
            if not self._connected or self._client is None:
                return self._build_result(success=False, action="generate_payload", errors=["Not connected."])
            safe_payload = self.sanitize_input(payload_type)
            safe_lhost = self.sanitize_input(lhost)
            payload = self._client.modules.use("payload", safe_payload)
            payload["LHOST"] = safe_lhost
            payload["LPORT"] = str(lport)
            raw = payload.execute()
            res = self._build_result(success=True, action="generate_payload", output=raw,
                parsed={"payload_type": safe_payload, "lhost": safe_lhost, "lport": lport, "format": format_type})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("generate_payload failed")
            res = self._build_result(success=False, action="generate_payload", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def health_check(self) -> Dict[str, Any]:
        base = super().health_check()
        if base["status"] == "available" and self._connected:
            try:
                _ = self._client.modules.search("test")
                base["message"] = "Connected to msfrpcd and responsive."
            except Exception as exc:
                base["status"] = "error"
                base["message"] = f"RPC connection lost: {exc}"
        return base


__all__ = ["MetasploitBridge"]
