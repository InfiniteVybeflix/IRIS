"""IRIS LLM Router — single AI gateway, configured 100% server-side.

ARCHITECTURE (company-key model — the "magic" 🪄):
  - The AI gateway URL and key come ONLY from environment variables:
        AEVIBRON_BASE_URL   e.g. https://<your-gateway-host>/api/v1
        AEVIBRON_API_KEY    the credential (sent as the X-Aevibron-Key header)
        AEVIBRON_MODEL      optional model pin (empty = gateway default)
  - NO hardcoded URLs, NO fallback hosts, NO second provider, NO client-side
    keys. Nothing about the key or endpoint is ever exposed to the frontend —
    users just open IRIS and it works.
  - If the environment is not configured, every call fails LOUDLY in the
    server logs with the exact missing variable, while clients receive a
    generic message that reveals nothing.

Auth: the single header `X-Aevibron-Key: <key>` (per gateway spec).

Backward compatibility: the public method signatures keep accepting (and
ignoring) `backend` / `provider_override` arguments so older callers —
orchestrator, app.py routes, skills — keep working unmodified.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Server-side configuration (env vars only — read at CALL time, never cached
# from import time, so a redeploy with new env vars takes effect immediately).
# ─────────────────────────────────────────────────────────────────────────────

# Generic client-facing message — reveals nothing about the configuration.
NOT_CONFIGURED_MESSAGE = (
    "The AI service is not configured on this server. "
    "Please contact your administrator."
)


def _env(name: str) -> str:
    v = os.environ.get(name, "")
    return v.strip() if isinstance(v, str) else ""


def _base_url() -> str:
    """Gateway base URL from AEVIBRON_BASE_URL, normalized to end with /api/v1.

    The /api/v1 suffix is the gateway's documented API root — appending it to
    a bare host is a path convention, NOT a hardcoded host. If the operator
    already included it (or /v1), the URL is used untouched.
    """
    u = _strip_invisibles(_env("AEVIBRON_BASE_URL")).strip().strip("<>").rstrip("/")
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    if "/api/v1" not in u and not u.endswith("/v1"):
        u = f"{u}/api/v1"
    return u


def _api_key() -> str:
    return _sanitize_header_value(_env("AEVIBRON_API_KEY"))


def _default_model() -> str:
    return _env("AEVIBRON_MODEL") or _env("DEFAULT_MODEL")


def is_configured() -> bool:
    return bool(_base_url() and _api_key())


def _missing() -> str:
    missing = [n for n, v in (("AEVIBRON_BASE_URL", _base_url()),
                              ("AEVIBRON_API_KEY", _api_key())) if not v]
    return ", ".join(missing)


# ─────────────────────────────────────────────────────────────────────────────
# Input sanitization — invisible Unicode crashes urllib's latin-1 header
# encoder (RFC 2616 §4.2). Even env vars set by copy-paste can carry these.
# ─────────────────────────────────────────────────────────────────────────────
_INVISIBLE_CHARS_RE = re.compile(
    "[\u00ad\u02dd\u115f\u180e\u2000-\u200f\u2028-\u202f\u205f-\u206f"
    "\u3164\ufeff\uffa0]"
)
_NBSP_RE = re.compile("[\u00a0\u2007\u202f\u3000]")


def _strip_invisibles(value: str) -> str:
    if not value:
        return value
    s = unicodedata.normalize("NFKC", value)
    s = _NBSP_RE.sub(" ", s)
    s = _INVISIBLE_CHARS_RE.sub("", s)
    return s


def _sanitize_header_value(value) -> str:
    s = _strip_invisibles(value or "")
    if not isinstance(s, str):
        s = str(s)
    return s.encode("latin-1", errors="replace").decode("latin-1")


def _sanitize_url(url: str) -> str:
    s = _strip_invisibles(url or "")
    if not s:
        return s
    s = "".join(ch for ch in s if not unicodedata.category(ch).startswith("Z"))
    return s


# ─────────────────────────────────────────────────────────────────────────────
# Response helpers
# ─────────────────────────────────────────────────────────────────────────────
class LLMResponse:
    """Uniform response object for every gateway call."""

    def __init__(self, content: str = "", model: str = "", raw: Any = None,
                 usage: Optional[Dict] = None, finish_reason: str = "",
                 tool_calls: Optional[List[Dict]] = None, error: str = "",
                 provider: str = ""):
        self.content = content or ""
        self.model = model or ""
        self.raw = raw
        self.usage = usage or {}
        self.finish_reason = finish_reason or ""
        self.tool_calls = tool_calls or []
        self.error = error or ""
        self.provider = provider

    @property
    def ok(self) -> bool:
        return not self.error


def extract_content(data: Any) -> str:
    """Pull the assistant text out of any of the gateway's response shapes."""
    if not isinstance(data, dict):
        return data if isinstance(data, str) else ""
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        ch = choices[0] or {}
        if isinstance(ch, dict):
            msg = ch.get("message") or {}
            if isinstance(msg, dict) and msg.get("content"):
                return msg["content"]
            delta = ch.get("delta") or {}
            if isinstance(delta, dict) and delta.get("content"):
                return delta["content"]
            if ch.get("text"):
                return ch["text"]
    for k in ("content", "response", "answer", "output", "message"):
        v = data.get(k)
        if isinstance(v, str) and v:
            return v
        if isinstance(v, dict) and isinstance(v.get("content"), str):
            return v["content"]
    return ""


def extract_tool_calls(data: Any) -> List[Dict]:
    """Pull tool_calls out of an OpenAI-shaped response."""
    if not isinstance(data, dict):
        return []
    choices = data.get("choices")
    if not (isinstance(choices, list) and choices):
        return []
    ch = choices[0] or {}
    if not isinstance(ch, dict):
        return []
    msg = ch.get("message") or {}
    tcs = msg.get("tool_calls") if isinstance(msg, dict) else None
    out: List[Dict] = []
    if isinstance(tcs, list):
        for i, tc in enumerate(tcs):
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") or {}
            args = fn.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_raw": args}
            out.append({"id": tc.get("id") or f"call_{i}",
                        "name": fn.get("name", ""), "arguments": args})
    return out


def _friendly_http_error(code: int, body: str) -> str:
    """Turn raw HTTP failures into actionable messages without leaking
    the endpoint URL or configuration details."""
    head = (body or "")[:180].replace("\n", " ")
    is_html = "<!doctype" in head.lower() or "<html" in head.lower()
    if code == 401:
        return ("The AI service rejected the server credentials. "
                "Administrators: check the gateway key environment variable.")
    if code == 403:
        return "The AI service refused access with the current credentials."
    if code == 404:
        if is_html:
            return ("The AI service endpoint path is wrong — the gateway "
                    "answered with an HTML page instead of JSON. Administrators: "
                    "the base URL must include the /api/v1 path.")
        return "The AI service endpoint was not found."
    if code == 429:
        return "The AI service is rate limiting requests — wait a moment and retry."
    if code >= 500:
        return f"The AI service failed server-side (HTTP {code}). {head}"
    return f"The AI service returned HTTP {code}. {head}"


# ─────────────────────────────────────────────────────────────────────────────
# The router
# ─────────────────────────────────────────────────────────────────────────────
class LLMRouter:
    """Single-gateway router. One instance, env-driven per request.

    Legacy kwargs (`backend`, `provider_override`) are accepted and IGNORED —
    the provider is fixed by the server environment and can never be
    influenced by a client payload.
    """

    def __init__(self):
        self._last_provider: Dict[str, str] = {}
        # Compat attributes for older callers (app.py /api/llm/status)
        self._default_backend_name = "gateway"
        self._default_model = _default_model()
        self._fast_model = _env("FAST_MODEL")
        self._deep_model = _env("DEEP_MODEL")

    # ── public API ────────────────────────────────────────────────────────
    def selected_backend_name(self) -> str:
        return "gateway"

    def list_backends(self) -> Dict[str, Dict[str, Any]]:
        """Compat stub — there is exactly one backend and its details are
        private. Returns an anonymous health flag only."""
        return {"gateway": {"name": "gateway", "label": "AI Service",
                            "configured": is_configured(), "model": _default_model()}}

    def get_models(self, backend: Optional[str] = None,
                   override: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        base = _base_url()
        if not base or not _api_key():
            raise RuntimeError(NOT_CONFIGURED_MESSAGE)
        req = urllib.request.Request(
            f"{base}/models", headers=self._headers(), method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for k in ("data", "models"):
                if isinstance(data.get(k), list):
                    return data[k]
        return []

    def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None,
             backend: Optional[str] = None, temperature: float = 0.7,
             max_tokens: int = 4096, tools: Optional[List[Dict]] = None,
             provider_override: Optional[Dict[str, Any]] = None,
             **legacy_kw) -> LLMResponse:
        """Non-streaming chat through the gateway."""
        base = _base_url()
        key = _api_key()
        if not base or not key:
            logger.error("[llm_router] NOT CONFIGURED — missing env: %s", _missing())
            return LLMResponse(error=NOT_CONFIGURED_MESSAGE, provider="gateway")

        payload: Dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        model = model or _default_model()
        if model:
            payload["model"] = model
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        body = json.dumps(payload).encode("utf-8")
        url = f"{base}/chat"
        try:
            req = urllib.request.Request(url, data=body, headers=self._headers(), method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                err_body = ""
            logger.error("[llm_router] gateway HTTP %s at %s — %s",
                         e.code, base, err_body[:300])
            return LLMResponse(error=_friendly_http_error(e.code, err_body),
                               provider="gateway")
        except urllib.error.URLError as e:
            reason = e.reason
            if isinstance(reason, UnicodeEncodeError):
                logger.error("[llm_router] header encoding failed: %s", reason)
                return LLMResponse(error=(
                    "A server-side configuration value contains a non-ASCII "
                    "character (RFC 2616 §4.2). Administrators: re-enter the "
                    "gateway configuration as plain ASCII."), provider="gateway")
            logger.error("[llm_router] connection failed: %s", reason)
            return LLMResponse(error="The AI service is unreachable right now. "
                                     "Try again in a moment.", provider="gateway")
        except Exception as e:
            logger.error("[llm_router] chat failed: %s", e)
            return LLMResponse(error=f"The AI service call failed: {e}", provider="gateway")

        content = extract_content(data)
        tool_calls = extract_tool_calls(data)
        finish = ""
        ch = (data.get("choices") or [{}])[0] if isinstance(data, dict) else {}
        if isinstance(ch, dict):
            finish = ch.get("finish_reason", "") or ""
        self._last_provider["chat"] = "gateway"
        return LLMResponse(content=content,
                           model=(data.get("model", "") if isinstance(data, dict) else "") or (model or ""),
                           raw=data, usage=data.get("usage") or {} if isinstance(data, dict) else {},
                           finish_reason=finish, tool_calls=tool_calls, provider="gateway")

    def stream_chat(self, messages: List[Dict[str, str]], model: Optional[str] = None,
                    backend: Optional[str] = None, temperature: float = 0.7,
                    max_tokens: int = 4096,
                    provider_override: Optional[Dict[str, Any]] = None) -> Iterator[str]:
        """Streaming chat — yields text deltas."""
        for kind, value in self.stream_chat_events(messages, model=model,
                                                   temperature=temperature,
                                                   max_tokens=max_tokens):
            if kind == "delta":
                yield value
            elif kind == "error":
                yield f"\n{value}\n"

    def stream_chat_events(self, messages: List[Dict[str, str]], model: Optional[str] = None,
                           backend: Optional[str] = None, temperature: float = 0.7,
                           max_tokens: int = 4096, tools: Optional[List[Dict]] = None,
                           provider_override: Optional[Dict[str, Any]] = None,
                           stream: bool = True) -> Iterator[Tuple[str, Any]]:
        """Streaming chat with tool-call support.

        The gateway's /chat endpoint answers with one complete JSON body (not
        SSE), so we request non-streaming and emit the content as a single
        delta followed by parsed tool calls — the caller-visible behavior is
        identical to a stream.

        Yields:
          ("delta", str)        — text chunk
          ("tool_calls", [..])  — parsed tool calls (then the generator ENDS)
          ("usage", {..})       — token usage when provided
          ("error", str)        — fatal error message
        """
        resp = self.chat(messages, model=model, temperature=temperature,
                         max_tokens=max_tokens, tools=tools)
        if not resp.ok:
            yield "error", resp.error or "unknown error"
            return
        if resp.content:
            yield "delta", resp.content
        if resp.tool_calls:
            yield "tool_calls", resp.tool_calls
        if resp.usage:
            yield "usage", resp.usage

    def chat_with_tools(self, messages: List[Dict[str, str]], tools: List[Dict],
                        model: Optional[str] = None, backend: Optional[str] = None,
                        provider_override: Optional[Dict[str, Any]] = None, **kw) -> Dict[str, Any]:
        resp = self.chat(messages, model=model, tools=tools, **kw)
        return {"content": resp.content, "tool_calls": resp.tool_calls,
                "model": resp.model, "error": resp.error, "provider": resp.provider}

    def think(self, prompt: str, backend: Optional[str] = None, **kw) -> Dict[str, Any]:
        resp = self.chat([{"role": "user", "content": prompt}], **kw)
        try:
            return json.loads(resp.content)
        except Exception:
            return {"raw": resp.content, "parsed": False}

    def fast_response(self, prompt: str, backend: Optional[str] = None, **kw) -> str:
        return self.chat([{"role": "user", "content": prompt}], **kw).content

    def health_check(self, backend: Optional[str] = None) -> bool:
        try:
            self.get_models()
            return True
        except Exception:
            return False

    # ── internals ─────────────────────────────────────────────────────────
    @staticmethod
    def _headers() -> Dict[str, str]:
        """Headers for every gateway call. The credential travels ONLY in the
        X-Aevibron-Key header — no Bearer token, no query param."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Aevibron-Key": _api_key(),
        }


llm_router = LLMRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Legacy resolve_provider stub — older imports keep working. The provider is
# fixed by the server environment; client-supplied overrides are ignored.
# ─────────────────────────────────────────────────────────────────────────────
def resolve_provider(name: Optional[str] = None,
                     override: Optional[Dict[str, Any]] = None) -> Tuple[Optional[str], Optional[str]]:
    if is_configured():
        return "gateway", None
    return None, NOT_CONFIGURED_MESSAGE
