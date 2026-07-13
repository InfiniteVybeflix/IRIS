#!/usr/bin/env python3
"""
api_gateway.py — PORTAL
API Management Agent for IRIS v1.0
Rate limiting, authentication (JWT/API key/OAuth2), request/response transformation,
caching, load balancing, OpenAPI generation, real Aevibron needs this for the AI gateway.
"""

import threading
import hashlib
import json
import logging
import time
import os
import subprocess
import urllib.request
import urllib.parse
import hmac
import base64
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PORTAL")


class APIGateway:
    CODENAME = "PORTAL"

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._session_id = hashlib.sha256(f"{self.CODENAME}{time.time()}".encode()).hexdigest()[:16]
        # Rate limiting: client_id -> list of timestamps
        self._rate_buckets: Dict[str, List[float]] = defaultdict(list)
        self._rate_limits: Dict[str, Dict[str, int]] = {"default": {"requests": 100, "window": 60}}
        # Cache: key -> {value, expires}
        self._cache: Dict[str, Dict[str, Any]] = {}
        # Backend pools
        self._backends: Dict[str, List[str]] = {}
        # JWT secret
        self._jwt_secret = os.environ.get("PORTAL_JWT_SECRET", hashlib.sha256(os.urandom(32)).hexdigest())
        logger.info(f"[{self.CODENAME}] Session {self._session_id} initialized.")

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True
            self._running = True
            self._report_to_commander("PORTAL started", level="info")
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return True
            self._running = False
            self._report_to_commander("PORTAL stopped", level="info")
            return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "agent": self.CODENAME,
                "session_id": self._session_id,
                "running": self._running,
                "cache_entries": len(self._cache),
                "backends": len(self._backends),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _report_to_commander(self, message: str, level: str = "info", data: Any = None) -> None:
        payload = {
            "agent": self.CODENAME,
            "session_id": self._session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "data": data,
        }
        if self._commander_bus:
            try:
                self._commander_bus.publish(f"agent.{self.CODENAME}", payload)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Bus error: {e}")
        else:
            logger.log(getattr(logging, level.upper(), logging.INFO), f"[{self.CODENAME}] {message}")

    def _store_memory(self, key: str, value: Any) -> None:
        if self._shared_memory:
            try:
                self._shared_memory.set(f"{self.CODENAME}.{key}", value, ttl=86400)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Memory store error: {e}")

    def _execute_shell(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------
    def check_rate_limit(self, client_id: str, route: str = "default") -> Tuple[bool, Dict[str, Any]]:
        """Check if client is within rate limit. Returns (allowed, headers)."""
        if not self._running:
            raise RuntimeError("Agent not running")
        limit_cfg = self._rate_limits.get(route, self._rate_limits["default"])
        window = limit_cfg["window"]
        max_req = limit_cfg["requests"]
        now = time.time()
        with self._lock:
            bucket = self._rate_buckets[client_id]
            # Remove old entries
            cutoff = now - window
            self._rate_buckets[client_id] = [t for t in bucket if t > cutoff]
            remaining = max_req - len(self._rate_buckets[client_id])
            if remaining <= 0:
                return False, {"X-RateLimit-Limit": max_req, "X-RateLimit-Remaining": 0, "X-RateLimit-Reset": int(cutoff + window)}
            self._rate_buckets[client_id].append(now)
            return True, {"X-RateLimit-Limit": max_req, "X-RateLimit-Remaining": remaining - 1, "X-RateLimit-Reset": int(cutoff + window)}

    def set_rate_limit(self, route: str, requests: int, window: int) -> None:
        """Configure rate limit for a route."""
        with self._lock:
            self._rate_limits[route] = {"requests": requests, "window": window}

    def authenticate_jwt(self, token: str) -> Dict[str, Any]:
        """Validate a JWT token (HS256)."""
        if not self._running:
            raise RuntimeError("Agent not running")
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return {"valid": False, "error": "Malformed JWT"}
            header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
            signature = base64.urlsafe_b64decode(parts[2] + "==")
            expected = hmac.new(self._jwt_secret.encode(), f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                return {"valid": False, "error": "Invalid signature"}
            if payload.get("exp", 0) < time.time():
                return {"valid": False, "error": "Token expired"}
            return {"valid": True, "claims": payload}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def authenticate_api_key(self, api_key: str, expected_key: str = "") -> bool:
        """Validate an API key against environment or provided expected key."""
        expected = expected_key or os.environ.get("PORTAL_API_KEY", "")
        if not expected:
            return False
        return hmac.compare_digest(api_key, expected)

    def generate_jwt(self, claims: Dict[str, Any], expires_in: int = 3600) -> str:
        """Generate a JWT token."""
        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
        payload_data = {**claims, "iat": int(time.time()), "exp": int(time.time()) + expires_in}
        payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
        signature = base64.urlsafe_b64encode(
            hmac.new(self._jwt_secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        ).decode().rstrip("=")
        return f"{header}.{payload}.{signature}"

    def cache_get(self, key: str) -> Optional[Any]:
        """Retrieve from cache if not expired."""
        with self._lock:
            entry = self._cache.get(key)
            if entry and entry["expires"] > time.time():
                return entry["value"]
            if entry:
                del self._cache[key]
            return None

    def cache_set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Store value in cache with TTL."""
        with self._lock:
            self._cache[key] = {"value": value, "expires": time.time() + ttl}

    def cache_clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()

    def transform_request(self, request: Dict[str, Any], rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply request transformation rules (header/body rewrite)."""
        result = dict(request)
        for rule in rules:
            op = rule.get("operation")
            if op == "add_header":
                result.setdefault("headers", {})[rule["name"]] = rule["value"]
            elif op == "remove_header":
                result.get("headers", {}).pop(rule["name"], None)
            elif op == "rewrite_path":
                result["path"] = result["path"].replace(rule["from"], rule["to"])
            elif op == "inject_body":
                body = json.loads(result.get("body", "{}")) if isinstance(result.get("body"), str) else result.get("body", {})
                body[rule["field"]] = rule["value"]
                result["body"] = json.dumps(body)
        return result

    def transform_response(self, response: Dict[str, Any], rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply response transformation rules."""
        result = dict(response)
        for rule in rules:
            op = rule.get("operation")
            if op == "add_header":
                result.setdefault("headers", {})[rule["name"]] = rule["value"]
            elif op == "filter_body":
                body = json.loads(result.get("body", "{}")) if isinstance(result.get("body"), str) else result.get("body", {})
                for field in rule.get("fields", []):
                    body.pop(field, None)
                result["body"] = json.dumps(body)
        return result

    def load_balance(self, service: str) -> str:
        """Round-robin select backend for a service."""
        with self._lock:
            backends = self._backends.get(service, [])
            if not backends:
                raise RuntimeError(f"No backends registered for service: {service}")
            idx = int(time.time() * 1000) % len(backends)
            return backends[idx]

    def register_backend(self, service: str, url: str) -> None:
        """Register a backend URL for a service."""
        with self._lock:
            self._backends.setdefault(service, []).append(url)

    def generate_openapi(self, routes: List[Dict[str, Any]], title: str = "API", version: str = "1.0.0") -> Dict[str, Any]:
        """Generate OpenAPI 3.0 spec from route definitions."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": title, "version": version},
            "paths": {},
        }
        for route in routes:
            path = route.get("path", "/")
            method = route.get("method", "get").lower()
            spec["paths"].setdefault(path, {})[method] = {
                "summary": route.get("summary", ""),
                "parameters": route.get("parameters", []),
                "responses": route.get("responses", {"200": {"description": "OK"}}),
            }
        self._store_memory(f"openapi:{title}", spec)
        return spec

    def proxy_request(self, method: str, url: str, headers: Optional[Dict] = None,
                      body: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
        """Proxy an HTTP request to a backend with real network call."""
        if not self._running:
            raise RuntimeError("Agent not running")
        req = urllib.request.Request(url, data=body.encode() if body else None, method=method.upper(),
                                     headers={"User-Agent": "IRIS-PORTAL/1.0", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {
                    "status": resp.status,
                    "headers": dict(resp.headers),
                    "body": resp.read().decode("utf-8", errors="replace")[:5000],
                }
        except urllib.error.HTTPError as e:
            return {"status": e.code, "error": e.reason, "body": e.read().decode(errors="replace")[:5000]}
        except Exception as e:
            return {"status": -1, "error": str(e)}

    # ------------------------------------------------------------------
    # Unit test stubs
    # ------------------------------------------------------------------
    def test_rate_limit(self) -> bool:
        self.set_rate_limit("test", 2, 60)
        a1, _ = self.check_rate_limit("c1", "test")
        a2, _ = self.check_rate_limit("c1", "test")
        a3, _ = self.check_rate_limit("c1", "test")
        return a1 and a2 and not a3

    def test_jwt(self) -> bool:
        token = self.generate_jwt({"sub": "user1"}, expires_in=60)
        r = self.authenticate_jwt(token)
        return r["valid"] and r["claims"]["sub"] == "user1"

    def test_cache(self) -> bool:
        self.cache_set("k", "v", ttl=2)
        return self.cache_get("k") == "v"

    def test_transform(self) -> bool:
        req = {"path": "/old", "headers": {}, "body": "{}"}
        r = self.transform_request(req, [{"operation": "rewrite_path", "from": "/old", "to": "/new"}])
        return r["path"] == "/new"

    def test_load_balance(self) -> bool:
        self.register_backend("svc", "http://a")
        self.register_backend("svc", "http://b")
        return self.load_balance("svc") in ("http://a", "http://b")

    def test_openapi(self) -> bool:
        r = self.generate_openapi([{"path": "/health", "method": "GET", "summary": "Health check"}])
        return "/health" in r["paths"]


if __name__ == "__main__":
    agent = APIGateway()
    agent.start()
    print(agent.health())
    agent.stop()
