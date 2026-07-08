"""
IRIS v7.0 — API Client

Universal REST, GraphQL, and WebSocket client with retry logic,
exponential backoff, rate limiting, and authentication.

Dependencies: requests, websocket-client
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Union

import requests

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class APIClient(BaseTool):
    """Universal HTTP/WebSocket client with resilience patterns."""

    name: str = "api_client"
    category: str = "web"
    dependencies: List[str] = ["requests", "websocket-client"]

    def __init__(self, base_url: Optional[str] = None, default_headers: Optional[Dict[str, str]] = None,
                 timeout: int = 30, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self.base_url = base_url or ""
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(default_headers or {})
        self._session.headers.update({"User-Agent": "IRIS-v7.0/Operational-Layer", "Accept": "application/json"})
        self._session.verify = True
        self._last_request_time: float = 0.0

    def _run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {}

    def request(self, method: str, url: str, headers: Optional[Dict[str, str]] = None,
                data: Optional[Union[Dict[str, Any], str]] = None, auth: Optional[tuple] = None,
                json_data: Optional[Dict[str, Any]] = None, timeout: Optional[int] = None) -> Dict[str, Any]:
        self._begin_execution()
        try:
            safe_method = self.sanitize_input(method).upper()
            full_url = url if url.startswith("http") else f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
            safe_url = self.sanitize_input(full_url)
            req_headers = dict(self._session.headers)
            if headers:
                req_headers.update(headers)
            resp = self._session.request(method=safe_method, url=safe_url, headers=req_headers, data=data, auth=auth,
                json=json_data, timeout=timeout or self.timeout)
            parsed_body = None
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                try:
                    parsed_body = resp.json()
                except Exception:
                    parsed_body = resp.text
            else:
                parsed_body = resp.text
            res = self._build_result(success=resp.status_code < 400, action=f"http_{safe_method}", output=resp.text,
                parsed={"status_code": resp.status_code, "headers": dict(resp.headers), "body": parsed_body,
                    "url": resp.url, "elapsed_ms": int(resp.elapsed.total_seconds() * 1000)},
                errors=[f"HTTP {resp.status_code}"] if resp.status_code >= 400 else [])
            self.last_result = res
            self._end_execution(resp.status_code < 400)
            return res
        except Exception as exc:
            logger.exception("API request failed")
            res = self._build_result(success=False, action="http_request", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def graphql_query(self, endpoint: str, query: str, variables: Optional[Dict[str, Any]] = None,
                      headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        self._begin_execution()
        try:
            payload = {"query": query}
            if variables:
                payload["variables"] = variables
            req_headers = {"Content-Type": "application/json"}
            if headers:
                req_headers.update(headers)
            resp = self._session.post(endpoint, json=payload, headers=req_headers, timeout=self.timeout)
            data = resp.json() if resp.status_code < 400 else {}
            errors = data.get("errors", [])
            res = self._build_result(success=resp.status_code < 400 and not errors, action="graphql_query", output=data,
                parsed={"data": data.get("data"), "errors": errors, "status_code": resp.status_code},
                errors=[e.get("message", str(e)) for e in errors] if errors else [])
            self.last_result = res
            self._end_execution(res["success"])
            return res
        except Exception as exc:
            logger.exception("GraphQL query failed")
            res = self._build_result(success=False, action="graphql_query", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def websocket_connect(self, url: str, on_message: Optional[Callable[[Any, str], None]] = None,
                          on_error: Optional[Callable[[Any, Exception], None]] = None,
                          on_close: Optional[Callable[[Any, int, str], None]] = None, timeout: int = 30) -> Dict[str, Any]:
        self._begin_execution()
        try:
            import websocket
            safe_url = self.sanitize_input(url)
            ws = websocket.WebSocket()
            ws.connect(safe_url, timeout=timeout)
            messages: List[str] = []
            try:
                ws.settimeout(5.0)
                msg = ws.recv()
                if msg:
                    messages.append(str(msg))
            except Exception:
                pass
            ws.close()
            res = self._build_result(success=True, action="websocket_connect", output=messages,
                parsed={"url": safe_url, "messages_received": len(messages), "messages": messages})
            self.last_result = res
            self._end_execution(True)
            return res
        except Exception as exc:
            logger.exception("WebSocket connection failed")
            res = self._build_result(success=False, action="websocket_connect", errors=[str(exc)])
            self.last_result = res
            self._end_execution(False)
            return res

    def retry_with_backoff(self, func: Callable[..., Any], max_retries: int = 3, base_delay: float = 1.0,
                           max_delay: float = 60.0, *args: Any, **kwargs: Any) -> Any:
        last_exception: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                last_exception = exc
                if attempt < max_retries:
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay}s: {exc}")
                    time.sleep(delay)
                else:
                    break
        raise last_exception if last_exception else RuntimeError("Retry exhausted")

    def rate_limit(self, requests_per_second: float) -> None:
        if requests_per_second <= 0:
            return
        min_interval = 1.0 / requests_per_second
        elapsed = time.perf_counter() - self._last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.perf_counter()


__all__ = ["APIClient"]
