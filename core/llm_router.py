"""IRIS LLM Router — multi-provider LLM gateway.

Supports FOUR LLM providers, switchable via IRIS_LLM_BACKEND env var:
  1. aevibron — Aevibron-gateway (OpenAI-compat proxy)
  2. ollama   — Local Ollama (http://localhost:11434/v1)
  3. groq     — Groq Cloud (uses groq package)
  4. openai   — Any OpenAI-compatible cloud endpoint

Maintains the same interface as AevibronClient so existing callers work.
"""
from __future__ import annotations
import json, logging, os, time
from typing import Any, Dict, List, Optional, Iterator

logger = logging.getLogger(__name__)


class LLMResponse:
    def __init__(self, content: str, model: str = "", raw: Any = None,
                 usage: Optional[Dict[str, int]] = None, finish_reason: str = ""):
        self.content = content
        self.model = model
        self.raw = raw
        self.usage = usage or {}
        self.finish_reason = finish_reason


class LLMBackend:
    name = "base"
    def __init__(self, **kwargs): self.config = kwargs
    def chat(self, messages, model=None, **kw): raise NotImplementedError
    def stream_chat(self, messages, model=None, **kw): raise NotImplementedError
    def chat_with_tools(self, messages, tools, model=None, **kw):
        resp = self.chat(messages, model=model, **kw)
        if isinstance(resp, LLMResponse):
            return {"content": resp.content, "tool_calls": []}
        return {"content": str(resp), "tool_calls": []}
    def get_models(self): return []
    def health_check(self): return False


class OpenAICompatBackend(LLMBackend):
    """OpenAI-compat endpoint: Aevibron, Ollama, OpenAI, OpenRouter, Together."""
    def __init__(self, base_url: str, api_key: str = "", model: str = "",
                 name: str = "openai-compat", headers: Optional[Dict[str, str]] = None):
        super().__init__(base_url=base_url, api_key=api_key, model=model)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = model
        self.name = name
        self.extra_headers = headers or {}

    def _headers(self):
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key: h["Authorization"] = f"Bearer {self.api_key}"
        h.update(self.extra_headers)
        return h

    def chat(self, messages, model=None, temperature=0.7, max_tokens=4096, stream=False, **kw):
        import urllib.request, urllib.error
        model = model or self.default_model
        if not model: return LLMResponse(content="[error] no model configured", model="")
        body = json.dumps({"model": model, "messages": messages,
                           "temperature": temperature, "max_tokens": max_tokens,
                           "stream": False}).encode("utf-8")
        url = f"{self.base_url}/chat/completions"
        req = urllib.request.Request(url, data=body, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choice = data.get("choices", [{}])[0]
            return LLMResponse(
                content=choice.get("message", {}).get("content", ""),
                model=data.get("model", model), raw=data,
                usage=data.get("usage"),
                finish_reason=choice.get("finish_reason", ""))
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")[:500]
            logger.error("[%s] HTTP %d: %s", self.name, e.code, err)
            return LLMResponse(content=f"[{self.name} error HTTP {e.code}] {err}", model=model)
        except Exception as e:
            logger.error("[%s] chat failed: %s", self.name, e)
            return LLMResponse(content=f"[{self.name} error] {e}", model=model)

    def stream_chat(self, messages, model=None, temperature=0.7, max_tokens=4096, **kw):
        import urllib.request, urllib.error
        model = model or self.default_model
        if not model:
            yield "[error] no model configured"; return
        body = json.dumps({"model": model, "messages": messages,
                           "temperature": temperature, "max_tokens": max_tokens,
                           "stream": True}).encode("utf-8")
        url = f"{self.base_url}/chat/completions"
        req = urllib.request.Request(url, data=body, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                buffer = ""
                for chunk in iter(lambda: resp.read(1024), b""):
                    buffer += chunk.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line or not line.startswith("data:"): continue
                        payload = line[5:].strip()
                        if payload == "[DONE]": return
                        try:
                            data = json.loads(payload)
                            delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if delta: yield delta
                        except json.JSONDecodeError: pass
        except Exception as e:
            yield f"\n[{self.name} stream error] {e}\n"

    def get_models(self):
        import urllib.request
        url = f"{self.base_url}/models"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8")).get("data", [])
        except Exception as e:
            logger.warning("[%s] get_models failed: %s", self.name, e)
            return []

    def health_check(self):
        try: return len(self.get_models()) > 0
        except: return False


class GroqBackend(LLMBackend):
    name = "groq"
    def __init__(self, api_key="", model="llama-3.3-70b-versatile",
                 fast_model="llama-3.1-8b-instant"):
        super().__init__(api_key=api_key, model=model, fast_model=fast_model)
        self.api_key = api_key
        self.default_model = model
        self.fast_model = fast_model
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from groq import Groq
                self._client = Groq(api_key=self.api_key)
            except ImportError:
                raise RuntimeError("groq package not installed (pip install groq)")
        return self._client

    def chat(self, messages, model=None, temperature=0.7, max_tokens=4096, stream=False, **kw):
        try:
            client = self._get_client()
            model = model or self.default_model
            tools = kw.get("tools")
            req_kw = {"model": model, "messages": messages,
                      "temperature": temperature, "max_tokens": max_tokens, "stream": False}
            if tools:
                req_kw["tools"] = tools
                req_kw["tool_choice"] = kw.get("tool_choice", "auto")
            resp = client.chat.completions.create(**req_kw)
            choice = resp.choices[0]
            content = choice.message.content or ""
            tool_calls = []
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    tool_calls.append({"id": tc.id, "name": tc.function.name,
                                       "arguments": tc.function.arguments})
            return LLMResponse(content=content, model=resp.model, raw=resp,
                usage={"prompt_tokens": resp.usage.prompt_tokens,
                       "completion_tokens": resp.usage.completion_tokens,
                       "total_tokens": resp.usage.total_tokens} if resp.usage else {},
                finish_reason=choice.finish_reason or ""), tool_calls
        except Exception as e:
            logger.error("[groq] chat failed: %s", e)
            return LLMResponse(content=f"[groq error] {e}", model=model or self.default_model), []

    def stream_chat(self, messages, model=None, temperature=0.7, max_tokens=4096, **kw):
        try:
            client = self._get_client()
            model = model or self.default_model
            stream = client.chat.completions.create(
                model=model, messages=messages,
                temperature=temperature, max_tokens=max_tokens, stream=True)
            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else ""
                if delta: yield delta
        except Exception as e:
            yield f"\n[groq stream error] {e}\n"

    def chat_with_tools(self, messages, tools, model=None, **kw):
        result = self.chat(messages, model=model, tools=tools, **kw)
        if isinstance(result, tuple):
            resp, tool_calls = result
            return {"content": resp.content, "tool_calls": tool_calls, "model": resp.model}
        return {"content": str(result), "tool_calls": []}

    def get_models(self):
        try:
            client = self._get_client()
            return [{"id": m.id, "object": "model"} for m in client.models.list().data]
        except Exception as e:
            logger.warning("[groq] get_models failed: %s", e)
            return []

    def health_check(self):
        return bool(self.api_key) and len(self.get_models()) > 0


class LLMRouter:
    """Multi-provider LLM router.

    Reads configuration from BOTH:
    1. Environment variables (for serverless / CI / Docker)
    2. Settings JSON file (for UI-configured keys)

    Settings file takes priority over env vars. All keys are OPTIONAL —
    IRIS works without any keys configured. The 'auto' backend probes
    all configured backends and picks the first working one.
    """

    def __init__(self):
        self._backends = {}
        self._init_backends()
        self._default_model = os.environ.get("IRIS_LLM_MODEL", "")
        self._fast_model = os.environ.get("IRIS_LLM_FAST_MODEL", "")
        self._deep_model = os.environ.get("IRIS_LLM_DEEP_MODEL", "")

    def _init_backends(self):
        # Try to read from settings_manager first, fall back to env vars
        try:
            from modules.settings_manager import get_all_config, get_llm_backend
            self._settings = get_all_config()
            self._default_backend_name = get_llm_backend() or "auto"
        except ImportError:
            self._settings = {}
            self._default_backend_name = os.environ.get("IRIS_LLM_BACKEND", "auto").lower()

        providers = self._settings.get("providers", {})

        # ─── Aevibron ─────────────────────────────────────────────
        aev_cfg = providers.get("aevibron", {})
        aev_url = aev_cfg.get("url", "") or os.environ.get("AEVIBRON_BASE_URL", "https://aevibron-gateway.vercel.app/api/v1")
        aev_key = aev_cfg.get("key", "") or os.environ.get("AEVIBRON_API_KEY", "")
        aev_token = aev_cfg.get("x_aevibron_key", "") or os.environ.get("AEVIBRON_ACCESS_TOKEN", "")
        aev_headers = {}
        if aev_token:
            aev_headers["X-Aevibron-Key"] = aev_token
        self._backends["aevibron"] = OpenAICompatBackend(
            base_url=aev_url, api_key=aev_key, name="aevibron", headers=aev_headers)

        # ─── Ollama local ────────────────────────────────────────
        oll_local_cfg = providers.get("ollama_local", {})
        ollama_host = oll_local_cfg.get("host", "") or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self._backends["ollama_local"] = OpenAICompatBackend(
            base_url=f"{ollama_host}/v1", api_key="ollama", name="ollama_local")

        # ─── Ollama cloud ─────────────────────────────────────────
        oll_cloud_cfg = providers.get("ollama_cloud", {})
        if oll_cloud_cfg.get("url"):
            self._backends["ollama_cloud"] = OpenAICompatBackend(
                base_url=oll_cloud_cfg["url"], api_key=oll_cloud_cfg.get("key", "ollama"), name="ollama_cloud")

        # ─── Groq ─────────────────────────────────────────────────
        groq_cfg = providers.get("groq", {})
        groq_key = groq_cfg.get("key", "") or os.environ.get("GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY_1", "")
        self._backends["groq"] = GroqBackend(
            api_key=groq_key,
            model=os.environ.get("IRIS_LLM_MODEL", "llama-3.3-70b-versatile"),
            fast_model=os.environ.get("IRIS_LLM_FAST_MODEL", "llama-3.1-8b-instant"))

        # ─── OpenAI ──────────────────────────────────────────────
        oai_cfg = providers.get("openai", {})
        openai_url = oai_cfg.get("url", "") or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        openai_key = oai_cfg.get("key", "") or os.environ.get("OPENAI_API_KEY", "")
        self._backends["openai"] = OpenAICompatBackend(
            base_url=openai_url, api_key=openai_key, name="openai")

        # ─── Custom ──────────────────────────────────────────────
        custom_cfg = providers.get("custom", {})
        if custom_cfg.get("url"):
            self._backends["custom"] = OpenAICompatBackend(
                base_url=custom_cfg["url"],
                api_key=custom_cfg.get("key", ""),
                model=custom_cfg.get("model", ""),
                name="custom")

    def get_backend(self, name=None):
        """Get a specific backend by name. If 'auto', probe all and pick first working."""
        name = (name or self._default_backend_name).lower()
        if name == "auto":
            return self._auto_select()
        if name not in self._backends:
            raise ValueError(f"unknown backend: {name} (configured: {list(self._backends.keys())})")
        return self._backends[name]

    def _auto_select(self) -> LLMBackend:
        """Probe all configured backends and return the first working one.

        Priority order (first working wins):
        1. Aevibron (recommended)
        2. Groq
        3. OpenAI
        4. Ollama local
        5. Ollama cloud
        6. Custom
        """
        priority = ["aevibron", "groq", "openai", "ollama_local", "ollama_cloud", "custom"]
        for name in priority:
            if name not in self._backends:
                continue
            backend = self._backends[name]
            if self._is_configured(backend):
                logger.info("[auto] selected backend: %s", name)
                return backend
        # No backend configured — return aevibron as default (will fail gracefully)
        logger.warning("[auto] no configured backend found, defaulting to aevibron")
        return self._backends.get("aevibron", OpenAICompatBackend("http://localhost:1", "", "", "aevibron"))

    def _is_configured(self, backend: LLMBackend) -> bool:
        """Check if a backend has the minimum required config."""
        if isinstance(backend, GroqBackend):
            return bool(backend.api_key)
        if isinstance(backend, OpenAICompatBackend):
            # Ollama local doesn't need a key
            if backend.name in ("ollama_local",):
                return True
            return bool(backend.api_key) or bool(backend.default_model)
        return False

    def list_backends(self):
        result = {}
        for name, backend in self._backends.items():
            result[name] = {
                "name": name,
                "class": backend.__class__.__name__,
                "model": getattr(backend, "default_model", ""),
                "configured": bool(getattr(backend, "api_key", "") or getattr(backend, "default_model", "")),
            }
        return result

    def chat(self, messages, model=None, backend=None, **kw):
        b = self.get_backend(backend)
        result = b.chat(messages, model=model or self._default_model, **kw)
        if isinstance(result, tuple): return result[0]
        return result

    def fast_response(self, prompt, backend=None, **kw):
        b = self.get_backend(backend)
        model = self._fast_model or getattr(b, "default_model", "") or self._default_model
        messages = [{"role": "user", "content": prompt}]
        result = b.chat(messages, model=model, temperature=0.3, max_tokens=1024, **kw)
        if isinstance(result, tuple): return result[0].content
        return result.content

    def think(self, prompt, backend=None, **kw):
        b = self.get_backend(backend)
        model = self._deep_model or self._default_model
        messages = [
            {"role": "system", "content": "You are an expert reasoner. Respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ]
        result = b.chat(messages, model=model, temperature=0.2, max_tokens=2048, **kw)
        content = result[0].content if isinstance(result, tuple) else result.content
        try: return json.loads(content)
        except: return {"raw": content, "parsed": False}

    def stream_chat(self, messages, model=None, backend=None, **kw):
        b = self.get_backend(backend)
        return b.stream_chat(messages, model=model or self._default_model, **kw)

    def chat_with_tools(self, messages, tools, model=None, backend=None, **kw):
        b = self.get_backend(backend)
        if hasattr(b, "chat_with_tools"):
            return b.chat_with_tools(messages, tools, model=model or self._default_model, **kw)
        resp = b.chat(messages, model=model or self._default_model, **kw)
        if isinstance(resp, tuple):
            return {"content": resp[0].content, "tool_calls": resp[1], "model": resp[0].model}
        return {"content": resp.content, "tool_calls": [], "model": resp.model}

    def get_models(self, backend=None):
        return self.get_backend(backend).get_models()

    def health_check(self, backend=None):
        return self.get_backend(backend).health_check()


llm_router = LLMRouter()


# Backward-compat shim — `from core.aevibron_client import aevibron` still works.
class _AevibronCompatShim:
    def __init__(self): self._router = llm_router
    def chat(self, messages, model=None, **kw):
        return self._router.chat(messages, model=model, backend="aevibron", **kw)
    def think(self, prompt, **kw):
        return self._router.think(prompt, backend="aevibron", **kw)
    def fast_response(self, prompt, **kw):
        return self._router.fast_response(prompt, backend="aevibron", **kw)
    def chat_with_tools(self, messages, tools, model=None, **kw):
        return self._router.chat_with_tools(messages, tools, model=model, backend="aevibron", **kw)
    def stream_chat(self, messages, model=None, **kw):
        return self._router.stream_chat(messages, model=model, backend="aevibron", **kw)
    def get_models(self, **kw):
        return self._router.get_models(backend="aevibron")
    def health_check(self, **kw):
        return self._router.health_check(backend="aevibron")

aevibron = _AevibronCompatShim()
