"""IRIS LLM Router v2 — true multi-provider LLM gateway.

EVERY provider is first-class and routed per-request:
  1. aevibron  — Aevibron gateway (POST /chat, X-Aevibron-Key auth, /api/v1 root)
                 Primary host: https://aevibron-gateway.vercel.app (custom domain)
                 Fallback host: https://aevibron-gateway.vercel.app (always live)
  2. groq      — Groq Cloud (https://api.groq.com/openai/v1) — pure HTTPS, no SDK needed
  3. openai    — OpenAI or any OpenAI-compatible cloud (OpenRouter, Together, ...)
  4. ollama_local / ollama_cloud — Ollama over HTTP
  5. custom    — any endpoint with url + key + model

Design rules (fixing the round-3 bugs):
  - NO import-time snapshots. Backends are built per-request from
    settings_manager (Postgres kv_store → JSON → memory cache) merged with
    env vars and an optional per-request `provider_override` (the frontend's
    localStorage bridge). Saving Groq in Settings takes effect on the very
    next chat message.
  - The chat path lives HERE — the orchestrator calls this router for every
    LLM request, so provider selection is honored everywhere.
  - Failures are loud: every error returns a structured message that says
    WHICH provider failed, the URL, the HTTP status and the response body.
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
# Input sanitization — invisible Unicode crashes urllib's latin-1 header
# encoder (RFC 2616 §4.2). Kept from round 2/3 (verified fix).
# ─────────────────────────────────────────────────────────────────────────────
_INVISIBLE_CHARS_RE = re.compile(
    "["
    "\u00ad\u02dd\u115f\u180e"
    "\u2000-\u200f"
    "\u2028-\u202f"
    "\u205f-\u206f"
    "\u3164\ufeff\uffa0"
    "]"
)
_NBSP_RE = re.compile("[\u00a0\u2007\u202f\u3000]")


def strip_invisibles(value: str) -> str:
    if not value:
        return value
    s = unicodedata.normalize("NFKC", value)
    s = _NBSP_RE.sub(" ", s)
    return _INVISIBLE_CHARS_RE.sub("", s)


def sanitize_header_value(value) -> str:
    """RFC 2616 §4.2 — header values must be latin-1 encodable."""
    s = strip_invisibles(value or "")
    if not isinstance(s, str):
        s = str(s)
    return s.encode("latin-1", errors="replace").decode("latin-1")


def sanitize_url(url) -> str:
    """Strip invisibles + ALL whitespace (a space inside a hostname is always
    a paste artifact — removing it, not percent-encoding it, is the fix)."""
    s = strip_invisibles(url or "")
    if not s:
        return s
    s = "".join(ch for ch in s if not unicodedata.category(ch).startswith("Z"))
    return s.strip().strip("<>").rstrip("/")


# ─────────────────────────────────────────────────────────────────────────────
# Provider definitions
# ─────────────────────────────────────────────────────────────────────────────
AEVIBRON_PRIMARY_URL = os.environ.get(
    "AEVIBRON_BASE_URL", "https://aevibron-gateway.vercel.app/api/v1"
)
AEVIBRON_FALLBACK_URLS = [
    "https://aevibron-gateway.vercel.app/api/v1",
]

PROVIDER_ORDER = ["aevibron", "groq", "openai", "custom", "ollama_cloud", "ollama_local"]

PROVIDER_INFO = {
    "aevibron": {
        "label": "Aevibron Gateway",
        "default_url": AEVIBRON_PRIMARY_URL,
        "chat_path": "/chat",          # verified: /chat/completions 404s
        "force_v1": True,              # bare host → append /api/v1
        "env_key": "AEVIBRON_API_KEY",
        "default_model": "Aevibron Core",
    },
    "groq": {
        "label": "Groq Cloud",
        "default_url": "https://api.groq.com/openai/v1",
        "chat_path": "/chat/completions",
        "force_v1": False,
        "env_key": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
    },
    "openai": {
        "label": "OpenAI",
        "default_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "chat_path": "/chat/completions",
        "force_v1": False,
        "env_key": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
    },
    "ollama_local": {
        "label": "Ollama (Local)",
        "default_url": os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/v1",
        "chat_path": "/chat/completions",
        "force_v1": False,
        "env_key": "",
        "default_model": "llama3.1",
    },
    "ollama_cloud": {
        "label": "Ollama (Cloud)",
        "default_url": "",
        "chat_path": "/chat/completions",
        "force_v1": False,
        "env_key": "",
        "default_model": "",
    },
    "custom": {
        "label": "Custom Provider",
        "default_url": "",
        "chat_path": "/chat/completions",
        "force_v1": False,
        "env_key": "",
        "default_model": "",
    },
}


class LLMResponse:
    """Unified response object for every provider."""

    def __init__(self, content: str = "", model: str = "", raw: Any = None,
                 usage: Optional[Dict[str, int]] = None, finish_reason: str = "",
                 tool_calls: Optional[List[Dict[str, Any]]] = None,
                 error: Optional[str] = None, provider: str = ""):
        self.content = content
        self.model = model
        self.raw = raw
        self.usage = usage or {}
        self.finish_reason = finish_reason
        self.tool_calls = tool_calls or []
        self.error = error
        self.provider = provider

    @property
    def ok(self) -> bool:
        return not self.error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content, "model": self.model, "usage": self.usage,
            "finish_reason": self.finish_reason, "tool_calls": self.tool_calls,
            "error": self.error, "provider": self.provider,
        }


def extract_content(data: Any) -> str:
    """Pull assistant text out of any common chat-response shape."""
    if not isinstance(data, dict):
        return str(data) if data is not None else ""
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        ch = choices[0] or {}
        msg = ch.get("message") or {}
        if isinstance(msg, dict):
            c = msg.get("content")
            if isinstance(c, str) and c:
                return c
            if isinstance(c, list):
                txt = "".join(p.get("text", "") for p in c if isinstance(p, dict))
                if txt:
                    return txt
        if isinstance(ch.get("text"), str) and ch["text"]:
            return ch["text"]
        delta = ch.get("delta") or {}
        if isinstance(delta, dict) and delta.get("content"):
            return delta["content"]
    content = data.get("content")
    if isinstance(content, str) and content:
        return content
    if isinstance(content, list):
        txt = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if txt:
            return txt
    for key in ("response", "text", "output", "result"):
        v = data.get(key)
        if isinstance(v, str) and v:
            return v
    msg = data.get("message")
    if isinstance(msg, str) and msg:
        return msg
    if isinstance(msg, dict) and isinstance(msg.get("content"), str):
        return msg["content"]
    return ""


def extract_tool_calls(data: Any) -> List[Dict[str, Any]]:
    """Extract OpenAI-shaped tool_calls from a chat response."""
    if not isinstance(data, dict):
        return []
    choices = data.get("choices")
    if not (isinstance(choices, list) and choices):
        return []
    ch = choices[0] or {}
    msg = ch.get("message") or {}
    if not isinstance(msg, dict):
        return []
    calls = msg.get("tool_calls")
    out: List[Dict[str, Any]] = []
    if isinstance(calls, list):
        for tc in calls:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") or {}
            cid = tc.get("id") or f"call_{int(time.time()*1000)}"
            name = fn.get("name") or ""
            args = fn.get("arguments") or "{}"
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_raw": args}
            out.append({"id": cid, "name": name, "arguments": args})
    return out


def _friendly_http_error(provider: str, url: str, code: int, body: str) -> str:
    body_head = (body or "")[:300].replace("\n", " ")
    is_html = "<!doctype" in body_head.lower() or "<html" in body_head.lower()
    if code == 404 and is_html:
        return (f"[{provider}] HTTP 404 at {url} — the server returned an HTML page, not JSON. "
                f"The URL path is wrong. For the Aevibron gateway the base URL must end with /api/v1 "
                f"and chat lives at POST /chat (not /chat/completions).")
    if code == 401:
        return (f"[{provider}] HTTP 401 Unauthorized at {url} — the API key was rejected. "
                f"Check the key in Settings → Provider. Detail: {body_head}")
    if code == 403:
        return f"[{provider}] HTTP 403 Forbidden at {url} — the key lacks access to this endpoint/model. Detail: {body_head}"
    if code == 404:
        return f"[{provider}] HTTP 404 — {url} was not found. Check the model name and URL path. Detail: {body_head}"
    if code == 429:
        return f"[{provider}] HTTP 429 — rate limited. Wait a moment and try again. Detail: {body_head}"
    if code >= 500:
        return f"[{provider}] HTTP {code} — the provider failed server-side. It said: {body_head}"
    return f"[{provider}] HTTP {code} at {url}: {body_head}"


# ─────────────────────────────────────────────────────────────────────────────
# Provider config resolution
# ─────────────────────────────────────────────────────────────────────────────
def _import_settings_manager():
    """Import modules.settings_manager robustly.

    The modules package __init__ imports every module (web_search pulls
    duckduckgo_search, etc.) — if ANY of those optional deps is missing,
    the whole package import fails and settings would silently fall back
    to env vars. Loading the settings_manager file directly avoids that
    chain, so provider settings keep working even with a broken sibling.
    """
    import importlib.util
    try:
        from modules import settings_manager as sm
        return sm
    except Exception:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "modules", "settings_manager.py")
        spec = importlib.util.spec_from_file_location("_iris_settings_manager", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def _load_saved_providers() -> Dict[str, Dict[str, str]]:
    """Read saved provider configs from settings_manager (Postgres → JSON →
    memory cache). Never raises — falls back to {}."""
    try:
        sm = _import_settings_manager()
        cfg = sm.get_all_config() or {}
        providers = cfg.get("providers", {})
        return providers if isinstance(providers, dict) else {}
    except Exception as e:
        logger.debug("[llm_router] settings_manager unavailable: %s", e)
        return {}


def _load_saved_backend() -> str:
    try:
        sm = _import_settings_manager()
        return (sm.get_llm_backend() or "auto").lower()
    except Exception:
        return os.environ.get("IRIS_LLM_BACKEND", "auto").lower()


class ProviderConfig:
    """Resolved per-request config for ONE provider.

    Priority: provider_override (frontend localStorage bridge) → saved
    settings → environment variables → provider defaults.
    """

    def __init__(self, name: str, url: str, key: str, model: str,
                 x_aevibron_key: str = "", host: str = ""):
        self.name = name
        self.url = sanitize_url(url)
        self.key = sanitize_header_value(key)
        self.model = model or ""
        self.x_aevibron_key = sanitize_header_value(x_aevibron_key)
        self.host = sanitize_url(host)  # ollama_local host

    def normalized_url(self) -> str:
        info = PROVIDER_INFO.get(self.name, {})
        u = self.url or self.host
        if not u:
            return ""
        if info.get("force_v1") and "/api/v1" not in u and not u.endswith("/v1"):
            u = f"{u}/api/v1"
        return u

    def chat_url(self) -> str:
        info = PROVIDER_INFO.get(self.name, {})
        base = self.normalized_url()
        if not base:
            return ""
        return f"{base}{info.get('chat_path', '/chat/completions')}"

    def headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.key:
            h["Authorization"] = f"Bearer {self.key}"
        if self.name == "aevibron":
            x = self.x_aevibron_key or self.key
            if x:
                h["X-Aevibron-Key"] = x
        return h


def resolve_provider(name: Optional[str], override: Optional[Dict[str, Any]] = None) -> Tuple[Optional[ProviderConfig], Optional[str]]:
    """Resolve the config for `name` (or the saved/auto selection when None).

    Returns (config, error). error is a human message when the provider
    cannot be used at all (unknown name / nothing configured).
    """
    name = (name or "").lower()
    saved = _load_saved_providers()
    ov = override if isinstance(override, dict) else {}

    if not name or name == "auto":
        # Auto-select: first provider with a key/url configured (saved → env).
        for cand in PROVIDER_ORDER:
            cfg, err = resolve_provider(cand, override)
            if cfg is None:
                continue
            if cand == "ollama_local":
                return cfg, None  # host-based, no key needed
            if cfg.key or (cfg.url and cand in ("custom", "ollama_cloud")):
                return cfg, None
        # Nothing configured — default to aevibron and let the error surface
        return resolve_provider("aevibron", override)

    if name not in PROVIDER_INFO:
        return None, (f"Unknown provider '{name}'. Supported: {', '.join(PROVIDER_ORDER)}")

    info = PROVIDER_INFO[name]
    saved_p = saved.get(name, {}) if isinstance(saved.get(name, {}), dict) else {}

    if name == "aevibron":
        url = (ov.get("url") or saved_p.get("url") or info["default_url"])
        key = (ov.get("key") or saved_p.get("key")
               or os.environ.get("AEVIBRON_API_KEY", config_env("AEVIBRON_API_KEY")))
        xk = (ov.get("x_aevibron_key") or saved_p.get("x_aevibron_key")
              or os.environ.get("AEVIBRON_ACCESS_TOKEN", config_env("AEVIBRON_ACCESS_TOKEN")))
        model = ov.get("model") or saved_p.get("model") or ""
        return ProviderConfig(name, url, key, model, x_aevibron_key=xk), None

    if name == "groq":
        key = (ov.get("key") or saved_p.get("key")
               or os.environ.get("GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY_1", ""))
        model = ov.get("model") or saved_p.get("model") or info["default_model"]
        if not key:
            return None, ("Groq is selected but no API key is configured. "
                          "Add your gsk_... key in Settings → Provider → Groq, or pick another provider.")
        return ProviderConfig(name, info["default_url"], key, model), None

    if name == "openai":
        url = ov.get("url") or saved_p.get("url") or info["default_url"]
        key = ov.get("key") or saved_p.get("key") or os.environ.get("OPENAI_API_KEY", "")
        model = ov.get("model") or saved_p.get("model") or info["default_model"]
        if not key:
            return None, ("OpenAI is selected but no API key is configured. "
                          "Add your sk-... key in Settings → Provider → OpenAI.")
        return ProviderConfig(name, url, key, model), None

    if name == "ollama_local":
        host = ov.get("host") or saved_p.get("host") or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        model = ov.get("model") or saved_p.get("model") or info["default_model"]
        return ProviderConfig(name, f"{host.rstrip('/')}/v1", "ollama", model), None

    if name == "ollama_cloud":
        url = ov.get("url") or saved_p.get("url") or ""
        key = ov.get("key") or saved_p.get("key") or "ollama"
        model = ov.get("model") or saved_p.get("model") or ""
        if not url:
            return None, "Ollama Cloud is selected but no URL is configured. Set it in Settings → Provider."
        return ProviderConfig(name, url, key, model), None

    if name == "custom":
        url = ov.get("url") or saved_p.get("url") or ""
        key = ov.get("key") or saved_p.get("key") or ""
        model = ov.get("model") or saved_p.get("model") or ""
        if not url:
            return None, "Custom provider is selected but no URL is configured. Set it in Settings → Provider."
        return ProviderConfig(name, url, key, model), None

    return None, f"Provider '{name}' is not implemented."


def config_env(name: str, default: str = "") -> str:
    """Read an env var from the process environment OR the config module."""
    v = os.environ.get(name)
    if v:
        return v
    try:
        from config import config as _c
        return getattr(_c, name, default) or default
    except Exception:
        return default


# ─────────────────────────────────────────────────────────────────────────────
# The router
# ─────────────────────────────────────────────────────────────────────────────
class LLMRouter:
    """Multi-provider router. One instance, per-request resolution."""

    def __init__(self):
        self._last_provider: Dict[str, str] = {}

    # ── public API ────────────────────────────────────────────────────────
    def selected_backend_name(self) -> str:
        return _load_saved_backend()

    def list_backends(self) -> Dict[str, Dict[str, Any]]:
        saved = _load_saved_providers()
        out = {}
        for name in PROVIDER_ORDER:
            p = saved.get(name, {}) if isinstance(saved.get(name, {}), dict) else {}
            if name == "groq":
                configured = bool(p.get("key") or os.environ.get("GROQ_API_KEY"))
            elif name == "aevibron":
                configured = True  # gateway is always reachable (may need key)
            elif name == "ollama_local":
                configured = True
            elif name in ("openai",):
                configured = bool(p.get("key") or os.environ.get("OPENAI_API_KEY"))
            else:
                configured = bool(p.get("url"))
            out[name] = {
                "name": name,
                "label": PROVIDER_INFO[name]["label"],
                "configured": configured,
                "model": p.get("model", "") or PROVIDER_INFO[name]["default_model"],
            }
        return out

    def get_models(self, backend: Optional[str] = None,
                   override: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        cfg, err = resolve_provider(backend, override)
        if cfg is None:
            raise RuntimeError(err or "no provider configured")
        urls = self._candidate_urls(cfg)
        last_err: Optional[Exception] = None
        for base in urls:
            try:
                req = urllib.request.Request(f"{base}/models", headers=cfg.headers())
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list):
                    return data
                if isinstance(data.get("data"), list):
                    return data["data"]
                if isinstance(data.get("models"), list):
                    return data["models"]
                return []
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"[{cfg.name}] could not list models: {last_err}")

    def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None,
             backend: Optional[str] = None, temperature: float = 0.7,
             max_tokens: int = 4096, tools: Optional[List[Dict]] = None,
             provider_override: Optional[Dict[str, Any]] = None) -> LLMResponse:
        """Non-streaming chat through the selected provider."""
        cfg, err = resolve_provider(backend, provider_override)
        if cfg is None:
            return LLMResponse(error=err or "no provider configured", provider=backend or "auto")

        payload: Dict[str, Any] = {
            "model": model or cfg.model or PROVIDER_INFO[cfg.name]["default_model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        body = json.dumps(payload).encode("utf-8")
        urls = self._candidate_chat_urls(cfg)
        last_error = "no URL"
        for url in urls:
            try:
                req = urllib.request.Request(url, data=body, headers=cfg.headers(), method="POST")
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                # Normalize flat gateway shapes into the OpenAI shape.
                if isinstance(data, dict) and "choices" not in data:
                    content = extract_content(data)
                    data = {"choices": [{"message": {"role": "assistant", "content": content},
                                         "finish_reason": "stop"}],
                            "model": data.get("model", payload["model"]), "usage": data.get("usage", {})}
                content = extract_content(data)
                tool_calls = extract_tool_calls(data)
                finish = ""
                ch = (data.get("choices") or [{}])[0]
                if isinstance(ch, dict):
                    finish = ch.get("finish_reason", "") or ""
                self._last_provider["chat"] = cfg.name
                return LLMResponse(content=content, model=data.get("model", payload["model"]),
                                   raw=data, usage=data.get("usage") or {},
                                   finish_reason=finish, tool_calls=tool_calls, provider=cfg.name)
            except urllib.error.HTTPError as e:
                try:
                    err_body = e.read().decode("utf-8", errors="replace")
                except Exception:
                    err_body = ""
                last_error = _friendly_http_error(cfg.name, url, e.code, err_body)
                # 401/403/404 = wrong URL or key → trying the fallback host is
                # worthwhile for aevibron (custom domain may be down); for
                # others, surface immediately.
                if cfg.name != "aevibron" or e.code in (401, 403):
                    return LLMResponse(error=last_error, provider=cfg.name)
                continue
            except urllib.error.URLError as e:
                reason = e.reason
                if isinstance(reason, UnicodeEncodeError):
                    return LLMResponse(error=(
                        f"[{cfg.name}] Header encoding failed: {reason}. A URL or API key you "
                        f"pasted contains a non-ASCII character (RFC 2616 §4.2). Re-paste as plain ASCII."),
                        provider=cfg.name)
                last_error = f"[{cfg.name}] Connection failed: {reason}"
                continue  # try next candidate URL
            except Exception as e:
                last_error = f"[{cfg.name}] {e}"
                continue
        return LLMResponse(error=last_error, provider=cfg.name)

    def stream_chat(self, messages: List[Dict[str, str]], model: Optional[str] = None,
                    backend: Optional[str] = None, temperature: float = 0.7,
                    max_tokens: int = 4096,
                    provider_override: Optional[Dict[str, Any]] = None) -> Iterator[str]:
        """Streaming chat — yields text deltas."""
        for kind, value in self.stream_chat_events(messages, model=model, backend=backend,
                                                   temperature=temperature, max_tokens=max_tokens,
                                                   provider_override=provider_override):
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

        Yields tuples:
          ("delta", str)          — a text chunk
          ("tool_calls", [..])    — parsed tool calls (OpenAI shape), then the
                                    generator ENDS (caller must re-enter with results)
          ("usage", {..})         — token usage (when the provider sends it)
          ("error", str)          — fatal error message
        """
        cfg, err = resolve_provider(backend, provider_override)
        if cfg is None:
            yield "error", err or "no provider configured"
            return

        payload: Dict[str, Any] = {
            "model": model or cfg.model or PROVIDER_INFO[cfg.name]["default_model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": bool(stream and cfg.name != "aevibron"),
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        body = json.dumps(payload).encode("utf-8")

        # Aevibron: the gateway's /chat does not honor SSE reliably — do a
        # normal request and emit the content as one delta (+ tool calls).
        if not payload["stream"]:
            resp = self.chat(messages, model=model, backend=backend, temperature=temperature,
                             max_tokens=max_tokens, tools=tools, provider_override=provider_override)
            if not resp.ok:
                yield "error", resp.error or "unknown error"
                return
            if resp.content:
                yield "delta", resp.content
            if resp.tool_calls:
                yield "tool_calls", resp.tool_calls
            if resp.usage:
                yield "usage", resp.usage
            return

        urls = self._candidate_chat_urls(cfg)
        last_error = "no URL"
        for url in urls:
            try:
                req = urllib.request.Request(url, data=body, headers=cfg.headers(), method="POST")
                tool_calls_acc: Dict[int, Dict[str, Any]] = {}
                got_any = False
                with urllib.request.urlopen(req, timeout=300) as resp:
                    buffer = ""
                    while True:
                        chunk = resp.read(1024)
                        if not chunk:
                            break
                        buffer += chunk.decode("utf-8", errors="replace")
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if not line or not line.startswith("data:"):
                                continue
                            data_str = line[5:].strip()
                            if data_str == "[DONE]":
                                if tool_calls_acc:
                                    yield "tool_calls", self._collect_tool_calls(tool_calls_acc)
                                return
                            try:
                                data = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue
                            choices = data.get("choices") or []
                            if not choices:
                                continue
                            ch = choices[0] or {}
                            delta = ch.get("delta") or {}
                            if isinstance(delta, dict):
                                d = delta.get("content")
                                if d:
                                    got_any = True
                                    yield "delta", d
                                for tc in delta.get("tool_calls") or []:
                                    if not isinstance(tc, dict):
                                        continue
                                    idx = tc.get("index", 0)
                                    slot = tool_calls_acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                                    if tc.get("id"):
                                        slot["id"] = tc["id"]
                                    fn = tc.get("function") or {}
                                    if fn.get("name"):
                                        slot["name"] += fn["name"]
                                    if fn.get("arguments"):
                                        slot["arguments"] += fn["arguments"]
                            if data.get("usage"):
                                yield "usage", data["usage"]
                # Stream ended without [DONE]
                if tool_calls_acc:
                    yield "tool_calls", self._collect_tool_calls(tool_calls_acc)
                elif not got_any:
                    # Some gateways ignore stream=true and return a full JSON
                    # body in one shot — parse it instead of yielding nothing.
                    try:
                        data = json.loads(buffer)
                        content = extract_content(data)
                        if content:
                            yield "delta", content
                        tcs = extract_tool_calls(data)
                        if tcs:
                            yield "tool_calls", tcs
                    except Exception:
                        yield "error", f"[{cfg.name}] empty stream from {url}"
                self._last_provider["chat"] = cfg.name
                return
            except urllib.error.HTTPError as e:
                try:
                    err_body = e.read().decode("utf-8", errors="replace")
                except Exception:
                    err_body = ""
                last_error = _friendly_http_error(cfg.name, url, e.code, err_body)
                if cfg.name != "aevibron" or e.code in (401, 403):
                    yield "error", last_error
                    return
                continue
            except Exception as e:
                last_error = f"[{cfg.name}] {e}"
                continue
        yield "error", last_error

    @staticmethod
    def _collect_tool_calls(acc: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for idx in sorted(acc.keys()):
            slot = acc[idx]
            args = slot.get("arguments") or "{}"
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {"_raw": args}
            out.append({"id": slot.get("id") or f"call_{idx}", "name": slot.get("name", ""),
                        "arguments": args})
        return out

    def chat_with_tools(self, messages: List[Dict[str, str]], tools: List[Dict],
                        model: Optional[str] = None, backend: Optional[str] = None,
                        provider_override: Optional[Dict[str, Any]] = None, **kw) -> Dict[str, Any]:
        resp = self.chat(messages, model=model, backend=backend, tools=tools,
                         provider_override=provider_override, **kw)
        return {"content": resp.content, "tool_calls": resp.tool_calls, "model": resp.model,
                "error": resp.error, "provider": resp.provider}

    def think(self, prompt: str, backend: Optional[str] = None, **kw) -> Dict[str, Any]:
        resp = self.chat([{"role": "user", "content": prompt}], backend=backend, **kw)
        try:
            return json.loads(resp.content)
        except Exception:
            return {"raw": resp.content, "parsed": False}

    def fast_response(self, prompt: str, backend: Optional[str] = None, **kw) -> str:
        resp = self.chat([{"role": "user", "content": prompt}], backend=backend, **kw)
        return resp.content

    def health_check(self, backend: Optional[str] = None) -> bool:
        try:
            self.get_models(backend)
            return True
        except Exception:
            return False

    # ── internals ─────────────────────────────────────────────────────────
    def _candidate_urls(self, cfg: ProviderConfig) -> List[str]:
        """URLs to try, in order. Aevibron gets the fallback host appended
        (the custom domain may be down while the .vercel.app host is live)."""
        base = cfg.normalized_url()
        if not base:
            return []
        out = [base]
        if cfg.name == "aevibron":
            for fb in AEVIBRON_FALLBACK_URLS:
                fb_clean = sanitize_url(fb)
                if fb_clean and fb_clean.rstrip("/") != base.rstrip("/"):
                    out.append(fb_clean)
        return out

    def _candidate_chat_urls(self, cfg: ProviderConfig) -> List[str]:
        info = PROVIDER_INFO.get(cfg.name, {})
        path = info.get("chat_path", "/chat/completions")
        return [f"{u}{path}" for u in self._candidate_urls(cfg)]


llm_router = LLMRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Backward-compat shim — `from core.aevibron_client import aevibron` callers
# (api/routes/gateway.py) keep working and now route through the real router.
# ─────────────────────────────────────────────────────────────────────────────
class _AevibronCompatShim:
    def __init__(self):
        self._router = llm_router

    def chat(self, messages, model=None, **kw):
        return self._router.chat(messages, model=model, backend="aevibron", **kw)

    def stream_chat(self, messages, model=None, **kw):
        return self._router.stream_chat(messages, model=model, backend="aevibron", **kw)

    def chat_with_tools(self, messages, tools, model=None, **kw):
        return self._router.chat_with_tools(messages, tools, model=model, backend="aevibron", **kw)

    def get_models(self, **kw):
        try:
            return self._router.get_models(backend="aevibron")
        except Exception as e:
            return {"success": False, "error": str(e)}

    def health_check(self, **kw):
        return self._router.health_check(backend="aevibron")

    def get_stats(self, **kw):
        return {
            "success": True,
            "provider": "aevibron",
            "last_provider_used": self._router._last_provider.get("chat"),
            "primary_url": AEVIBRON_PRIMARY_URL,
            "fallback_urls": AEVIBRON_FALLBACK_URLS,
        }


aevibron = _AevibronCompatShim()
