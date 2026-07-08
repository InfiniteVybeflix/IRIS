"""
IRIS v7.0 — Base Tool & IRISConnectable Interface

Defines the contract every tool must fulfill. All tools inherit from BaseTool.
Uniform health checks, execution patterns, result formatting, reporting.

Design Principles:
    - Real execution only. No stubs, no mocks, no TODOs.
    - Thread-safe shared state via threading.Lock.
    - Input sanitization to prevent command injection.
    - Graceful degradation when dependencies are missing.
    - Standardized result dictionaries for downstream consumption.
"""

from __future__ import annotations

import abc
import logging
import re
import shlex
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class IRISConnectable(abc.ABC):
    """
    Abstract interface for any component that connects to the IRIS core.

    Provides the contract for health checks, execution, and reporting.
    All tools and senses implement this interface.
    """

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        self.iris_core: Optional[Any] = iris_core
        self.status: str = "idle"
        self.last_result: Optional[Dict[str, Any]] = None
        self._lock: threading.Lock = threading.Lock()
        self._start_time: Optional[float] = None

    @abc.abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Return health status: available, missing_deps, or error."""
        raise NotImplementedError

    @abc.abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Main execution. Returns standardized result dict."""
        raise NotImplementedError

    def report(self, finding: Dict[str, Any]) -> None:
        """Send finding to IRIS core or log if core unavailable."""
        finding["reported_by"] = self.__class__.__name__
        finding["reported_at"] = datetime.now(timezone.utc).isoformat()
        if self.iris_core is not None and hasattr(self.iris_core, "receive_finding"):
            try:
                self.iris_core.receive_finding(finding)
            except Exception as exc:
                logger.error(f"Failed to report finding to IRIS core: {exc}")
                logger.info(f"[{self.__class__.__name__}] {finding}")
        else:
            logger.info(f"[{self.__class__.__name__}] {finding}")

    def _build_result(
        self, success: bool, action: str, output: Any = None,
        parsed: Optional[Dict[str, Any]] = None,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        duration_ms = int((time.perf_counter() - self._start_time) * 1000) if self._start_time else 0
        return {
            "success": success, "tool": self.__class__.__name__, "action": action,
            "output": output, "parsed": parsed or {}, "errors": errors or [],
            "warnings": warnings or [], "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _begin_execution(self) -> None:
        self._start_time = time.perf_counter()
        with self._lock:
            self.status = "active"

    def _end_execution(self, success: bool) -> None:
        with self._lock:
            self.status = "idle" if success else "error"


class BaseTool(IRISConnectable, abc.ABC):
    """
    Abstract base class for all IRIS tools.

    Every concrete tool must define name, category, dependencies.
    Provides dependency checking, input sanitization, output parsing,
    and subprocess execution with timeouts and injection protection.
    """

    name: str = "base_tool"
    category: str = "unknown"
    dependencies: List[str] = []

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._dependency_cache: Optional[bool] = None

    def health_check(self) -> Dict[str, Any]:
        try:
            available = self.check_dependencies()
            if available:
                return {"status": "available", "message": f"{self.name} is ready.", "details": {"dependencies": self.dependencies}}
            return {"status": "missing_deps", "message": f"{self.name} missing dependencies.", "details": {"dependencies": self.dependencies}}
        except Exception as exc:
            logger.exception(f"Health check failed for {self.name}")
            return {"status": "error", "message": str(exc), "details": {}}

    def check_dependencies(self) -> bool:
        if self._dependency_cache is not None:
            return self._dependency_cache
        import shutil
        missing: List[str] = []
        for dep in self.dependencies:
            if shutil.which(dep) is not None:
                continue
            try:
                __import__(dep)
            except ImportError:
                missing.append(dep)
        self._dependency_cache = len(missing) == 0
        if not self._dependency_cache:
            logger.warning(f"{self.name} missing dependencies: {missing}")
        return self._dependency_cache

    def execute(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        self._begin_execution()
        try:
            if not self.check_dependencies():
                result = self._build_result(
                    success=False, action="dependency_check",
                    errors=[f"Missing dependencies: {self.dependencies}"],
                )
                self.last_result = result
                return result
            output = self._run(*args, **kwargs)
            result = self._build_result(success=True, action="execute", output=output)
            self.last_result = result
            self._end_execution(success=True)
            return result
        except Exception as exc:
            logger.exception(f"Execution failed in {self.name}")
            result = self._build_result(success=False, action="execute", errors=[str(exc)])
            self.last_result = result
            self._end_execution(success=False)
            return result

    @abc.abstractmethod
    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Concrete tool logic. Subclasses MUST implement this."""
        raise NotImplementedError

    def sanitize_input(self, value: Union[str, List[str], None]) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return " ".join(self.sanitize_input(v) for v in value)
        if "\x00" in value:
            raise ValueError("Null bytes not permitted in tool input.")
        dangerous = re.compile(r"[;&|\$`<>\n\r\x00\x80-\x9f]")
        if dangerous.search(value):
            raise ValueError(f"Dangerous characters detected: {value!r}")
        allowed = re.compile(r"^[a-zA-Z0-9._~:/=\-@%]+$")
        if not allowed.match(value):
            return shlex.quote(value)
        return value

    def parse_output(self, raw_output: Union[str, bytes]) -> Dict[str, Any]:
        if isinstance(raw_output, bytes):
            raw_output = raw_output.decode("utf-8", errors="replace")
        return {"raw": raw_output}

    def _run_subprocess(
        self, command: List[str], timeout: int = 300,
        cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None, capture: bool = True,
    ) -> subprocess.CompletedProcess:
        logger.debug(f"Running: {' '.join(command)}")
        return subprocess.run(
            command, capture_output=capture, text=True, timeout=timeout,
            cwd=cwd, env=env, check=False,
        )


__all__ = ["IRISConnectable", "BaseTool"]
