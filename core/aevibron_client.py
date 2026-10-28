"""IRIS Aevibron Client — gateway access, 100% server-side configuration.

COMPATIBILITY LAYER: many modules (`nl2code`, `vision_ai`, `auto_debug`,
`self_improve`, `smart_memory`, `proactive_engine`, `autonomous`,
`copilot_bridge`, `api/routes/gateway.py`) import `aevibron` from this file.
The public surface is preserved exactly; only the configuration model
changed:

  - Base URL and key come ONLY from environment variables
    (AEVIBRON_BASE_URL, AEVIBRON_API_KEY). No hardcoded URLs, no fallback
    hosts, no client-supplied values, ever.
  - The credential is sent ONLY in the `X-Aevibron-Key` header.
  - When the environment is not configured, calls return
    {"error": True, "message": "<generic>"} and the server log states the
    exact missing variable. The frontend never learns anything about the
    configuration.
"""
import json
import logging
import os
import time
from typing import Dict, List

import requests

from config import config

logger = logging.getLogger(__name__)

NOT_CONFIGURED_MESSAGE = ("The AI service is not configured on this server. "
                          "Please contact your administrator.")


class CircuitBreaker:
    """Circuit breaker pattern to prevent cascading failures."""

    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"

    def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                logger.info("Circuit breaker: entering half-open state")
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failures = 0
                logger.info("Circuit breaker: closed")
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.failure_threshold:
                self.state = "open"
                logger.error(f"Circuit breaker: OPEN after {self.failures} failures")
            raise e


def _base_url() -> str:
    """Gateway base URL from the environment, normalized to the /api/v1 root.

    Appending /api/v1 to a bare host is a documented path convention of the
    gateway — NOT a hardcoded host. No fallback URLs exist.
    """
    u = (os.environ.get("AEVIBRON_BASE_URL", "") or "").strip().strip("<>").rstrip("/")
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    if "/api/v1" not in u and not u.endswith("/v1"):
        u = f"{u}/api/v1"
    return u


def _api_key() -> str:
    return (os.environ.get("AEVIBRON_API_KEY", "") or "").strip()


def _configured() -> bool:
    return bool(_base_url() and _api_key())


class AevibronClient:
    """Production-grade client for the AI gateway (server-side config only).

    Gateway protocol:
      - Chat:        POST {base}/chat
      - Models:      GET  {base}/models
      - Auth header: X-Aevibron-Key: <key>
    """

    def __init__(self):
        # Kept as attributes for backwards compatibility with modules that
        # read them — resolved from the environment at CALL time elsewhere.
        self.base_url = _base_url()
        self.api_key = _api_key()
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        self.request_count = 0
        self.error_count = 0

    # ── request plumbing ──────────────────────────────────────────────────
    def _headers(self) -> Dict[str, str]:
        """Credential travels ONLY in the X-Aevibron-Key header."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Aevibron-Key": _api_key(),
        }

    def _not_configured(self) -> Dict:
        missing = []
        if not _base_url():
            missing.append("AEVIBRON_BASE_URL")
        if not _api_key():
            missing.append("AEVIBRON_API_KEY")
        logger.error("[aevibron] NOT CONFIGURED — missing env: %s", ", ".join(missing))
        return {"error": True, "message": NOT_CONFIGURED_MESSAGE}

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        base = _base_url()
        if not _configured():
            return self._not_configured()
        url = f"{base}{endpoint}"
        max_retries = 2
        base_delay = 0.5

        for attempt in range(max_retries):
            try:
                self.request_count += 1
                response = requests.request(
                    method, url, headers=self._headers(),
                    timeout=(10, 55), **kwargs)

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", str(base_delay * (2 ** attempt))))
                    logger.warning("Rate limited. Waiting %ss...", retry_after)
                    time.sleep(min(retry_after, 5))
                    continue

                if response.status_code == 401:
                    self.error_count += 1
                    logger.error("401 Unauthorized from the AI gateway — check the server-side key variable")
                    return {"error": True, "status_code": 401,
                            "message": "The AI service rejected the server credentials. "
                                       "Administrators: check the gateway key environment variable."}

                if response.status_code == 404:
                    self.error_count += 1
                    body = response.text[:200]
                    if "<!DOCTYPE" in body or "<html" in body.lower():
                        logger.error("404 HTML page from gateway — base URL is missing the /api/v1 path")
                        return {"error": True, "status_code": 404,
                                "message": "The AI service endpoint path is wrong — the gateway answered "
                                           "with an HTML page instead of JSON. Administrators: the base URL "
                                           "must include the /api/v1 path."}
                    return {"error": True, "status_code": 404, "message": f"Not found: {endpoint}"}

                response.raise_for_status()
                try:
                    return response.json()
                except ValueError:
                    self.error_count += 1
                    return {"error": True, "message": "The AI service returned a non-JSON response."}

            except requests.exceptions.Timeout:
                wait = base_delay * (2 ** attempt)
                logger.warning("Timeout on attempt %d. Retrying in %ss...", attempt + 1, wait)
                time.sleep(wait)
            except requests.exceptions.ConnectionError as e:
                wait = base_delay * (2 ** attempt)
                logger.warning("Connection error: %s. Retrying in %ss...", e, wait)
                time.sleep(wait)
            except requests.exceptions.HTTPError as e:
                self.error_count += 1
                if attempt == max_retries - 1:
                    return {"error": True, "status_code": response.status_code, "message": str(e)}
                time.sleep(base_delay * (2 ** attempt))
            except Exception as e:
                self.error_count += 1
                if attempt == max_retries - 1:
                    return {"error": True, "message": str(e)}
                time.sleep(base_delay * (2 ** attempt))

        return {"error": True, "message": "The AI service did not respond after retries."}

    # ── public API (surface unchanged) ────────────────────────────────────
    def chat(self, messages: List[Dict], model: str = None, temperature: float = 0.7,
             max_tokens: int = 4000, tools: List[Dict] = None, tool_choice: str = "auto",
             stream: bool = False) -> Dict:
        if not _configured():
            return self._not_configured()
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": bool(stream),
        }
        model = model or os.environ.get("AEVIBRON_MODEL", "") or os.environ.get("DEFAULT_MODEL", "")
        if model:
            payload["model"] = model
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        try:
            return self.circuit_breaker.call(self._make_request, "POST", "/chat", json=payload)
        except Exception as e:
            return {"error": True, "message": str(e)}

    def think(self, prompt: str, context: str = "", model: str = None) -> Dict:
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": f"Context: {context}\n\nTask: {prompt}\n\nThink deeply. Consider all options. Evaluate pros and cons. Then decide the best approach."}
        ]
        return self.chat(messages, model=model or config.DEEP_MODEL or None,
                         temperature=0.8, max_tokens=4000)

    def fast_response(self, prompt: str) -> Dict:
        return self.chat(
            messages=[{"role": "user", "content": prompt}],
            model=config.FAST_MODEL or None, temperature=0.5, max_tokens=1000
        )

    def chat_with_tools(self, messages: List[Dict], model: str = None) -> Dict:
        try:
            from core.tool_registry import tool_registry
            tools = tool_registry.schemas
        except Exception:
            tools = None
        return self.chat(messages, model=model or config.AGENTIC_MODEL or None,
                         tools=tools, tool_choice="auto")

    def stream_chat(self, messages: List[Dict], model: str = None):
        """Yield content deltas. The gateway answers /chat with a complete
        JSON body, so the whole reply is emitted as one chunk."""
        result = self.chat(messages, model=model, stream=False)
        if isinstance(result, dict) and result.get("error"):
            yield f"[Error: {result.get('message', 'AI service error')}]"
            return
        # Reuse the router's robust content extraction for flat shapes.
        from core.llm_router import extract_content
        content = extract_content(result)
        if content:
            yield content

    def get_models(self) -> Dict:
        return self._make_request("GET", "/models")

    def health_check(self) -> Dict:
        """Probe the gateway via /models: a 200 with a model list means the
        gateway is up and the key is accepted. Reveals no configuration."""
        if not _configured():
            return {"healthy": False, "error": NOT_CONFIGURED_MESSAGE}
        base = _base_url()
        try:
            response = requests.get(f"{base}/models", headers=self._headers(), timeout=10)
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError:
                    return {"healthy": False, "status_code": 200,
                            "error": "Non-JSON response from the AI service"}
                models = data if isinstance(data, list) else data.get("data") or data.get("models") or []
                return {"healthy": True, "status_code": 200, "models": len(models)}
            if response.status_code == 401:
                return {"healthy": False, "status_code": 401,
                        "error": "The AI service is reachable but the server key is missing or invalid"}
            return {"healthy": False, "status_code": response.status_code,
                    "error": response.text[:200]}
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    def get_stats(self) -> Dict:
        return {
            "total_requests": self.request_count,
            "errors": self.error_count,
            "error_rate": self.error_count / max(self.request_count, 1),
            "circuit_state": self.circuit_breaker.state,
        }

    def _get_system_prompt(self) -> str:
        return f"""You are IRIS — an advanced AI software engineering partner.
You are a senior software engineer and creative collaborator.

IDENTITY:
- Name: IRIS
- Owner: {config.OWNER_NAME}
- Role: Senior Software Engineer & Creative Partner
- Personality: Direct, honest, intelligent, occasionally sarcastic but warm.

CAPABILITIES:
- Read, write, edit, and execute code
- Search the web for best practices
- Create GitHub repos, commit, push
- Deploy to Vercel
- Process documents (PDF, DOCX, images, code)
- Analyze codebases, find bugs, suggest optimizations
- Self-improve by editing your own code
- Manage calendar, notes, and reminders
- Proactive suggestions based on context

BEHAVIOR RULES:
1. THINK before acting. Never rush.
2. When asked to build something, estimate time.
3. After completing work, verify it: test, lint, check.
4. If you find a better approach than what the user suggested, SAY SO.
5. When you make a mistake, admit it, fix it, learn from it.
6. You can read your own code files. You know you are an AI agent.
7. You write to files to store what you learn.
8. You are proactive — suggest improvements before being asked.

When you need to use tools, you will receive tool definitions and respond with tool_calls."""


aevibron = AevibronClient()
