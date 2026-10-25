"""IRIS Settings API — provider configuration, key management, connection testing.

Endpoints:
  GET  /api/iris/settings          — get current settings (keys MASKED)
  POST /api/iris/settings          — save settings (keys encrypted client-side)
  POST /api/iris/settings/test     — test a provider connection (lists models)
  GET  /api/iris/settings/providers — list all supported providers + descriptions

Security:
  - Keys are encrypted client-side (AES-GCM via Web Crypto API) before being sent
  - Server stores encrypted keys, never logs them
  - GET returns masked keys (first 4 + last 4 chars)
  - No key is required for IRIS to work
"""
import json
import re
import logging
import unicodedata
import urllib.request
import urllib.error
from urllib.parse import urlsplit, urlunsplit, quote
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)
settings_bp = Blueprint("iris_settings", __name__)


# ─── Input sanitization ─────────────────────────────────────────────────
# RFC 2616 §4.2 mandates that HTTP header field-values must be encodable as
# latin-1 (codepoints 0–255). When users copy-paste a gateway URL or API key
# from a chat app, a website, a PDF, or a word processor, invisible Unicode
# characters frequently sneak in (WORD JOINER \u2060, ZERO WIDTH SPACE \u200b,
# BOM \ufeff, NO-BREAK SPACE \u00a0, IDEOGRAPHIC SPACE \u3000, etc.). These
# crash urllib's latin-1 header encoder with the cryptic error:
#   'latin-1' codec can't encode character '\u2060' in position N: ordinal
# not in range(256)
#
# We strip those characters BEFORE the request is built, and we surface a
# `sanitized` flag in the response so the user knows their pasted input
# contained hidden characters and which cleaned value to keep using.
_INVISIBLE_CHARS_RE = re.compile(
    "["
    "\u00ad"          # SOFT HYPHEN
    "\u02dd"          # DOUBLE ACUTE ACCENT (sometimes used as invis. marker)
    "\u115f"          # HANGUL CHOSEONG FILLER
    "\u180e"          # MONGOLIAN VOWEL SEPARATOR
    "\u2000-\u200f"   # EN QUAD..RIGHT-TO-LEFT MARK (incl. ZERO WIDTH SPACE \u200b)
    "\u2028-\u202f"   # LINE SEPARATOR..RIGHT-TO-LEFT EMBEDDING
    "\u205f-\u206f"   # various (incl. WORD JOINER \u2060, INVISIBLE TIMES \u2061..)
    "\u3164"          # HANGUL FILLER
    "\ufeff"          # ZERO WIDTH NO-BREAK SPACE / BOM
    "\uffa0"          # HALFWIDTH HANGUL FILLER
    "]"
)
_NBSP_AND_IDEOGRAPHIC_SPACE_RE = re.compile("[\u00a0\u2007\u202f\u3000]")


def _strip_invisibles(value: str) -> str:
    """NFKC-normalize and strip invisible Unicode characters from a string.

    Returns the cleaned string. The original characters are removed (NBSP
    and IDEOGRAPHIC SPACE are converted to regular ASCII spaces first so
    spacing is preserved).
    """
    if not value:
        return value
    # NFKC first — collapses ligatures and compatibility chars into their
    # canonical parts so e.g. "ﬁ" becomes "fi" and fullwidth digits become
    # ASCII digits.
    s = unicodedata.normalize("NFKC", value)
    # Convert no-break / ideographic spaces to ASCII spaces before stripping.
    s = _NBSP_AND_IDEOGRAPHIC_SPACE_RE.sub(" ", s)
    # Now strip the truly invisible characters.
    s = _INVISIBLE_CHARS_RE.sub("", s)
    return s


def _sanitize_header_value(value) -> str:
    """Sanitize an HTTP header value: strip invisibles, then make latin-1-safe.

    Per RFC 2616 §4.2, header field-values MUST be encodable as latin-1.
    Returns a string guaranteed to encode as latin-1 (any residual non-
    latin-1 char is replaced with '?').
    """
    s = _strip_invisibles(value or "")
    if not isinstance(s, str):
        s = str(s)
    # Final safety net — replace any remaining non-latin-1 char with '?'.
    return s.encode("latin-1", errors="replace").decode("latin-1")


def _sanitize_url(url) -> str:
    """Sanitize a URL: strip invisibles + ALL whitespace, then percent-encode
    any non-ASCII in the path / query / fragment per RFC 3986.

    URLs can never legitimately contain whitespace (a NO-BREAK SPACE inside
    a hostname like ``aevibron-gateway\\u00a0.vercel.app`` must be removed,
    not turned into ``%20``). So unlike header values, here we strip all
    whitespace characters entirely.
    """
    s = _strip_invisibles(url or "")
    if not s:
        return s
    # Strip ALL whitespace (regular space, tab, newline, CR, and any
    # residual Unicode whitespace that survived NFKC normalization).
    # Whitespace inside a URL is always the result of a paste artifact.
    s = "".join(ch for ch in s if not unicodedata.category(ch).startswith("Z"))
    parts = urlsplit(s)
    # Path-safe chars per RFC 3986 §2.2 + §3.3. NOTE: do NOT default an
    # empty path to '/' — that would add a trailing slash to bare-host
    # URLs like "https://example.com", which then produces double slashes
    # when the caller appends "/api/v1" (got "https://example.com//api/v1").
    safe_path = quote(parts.path or "", safe="/%:@!$&'()*+,;=~")
    safe_query = quote(parts.query or "", safe="/%:@!$&'()*+,;=~=?")
    safe_frag = quote(parts.fragment or "", safe="/%:@!$&'()*+,;=~=?")
    return urlunsplit((parts.scheme, parts.netloc, safe_path, safe_query, safe_frag))


# ─── Provider definitions ──────────────────────────────────────────────
# The list of supported providers, their fields, and whether they need a key
PROVIDERS = {
    "aevibron": {
        "label": "Aevibron Gateway",
        "recommended": True,
        "description": "Aevibron's AI gateway — OpenAI-compatible proxy. Recommended for best results.",
        "fields": [
            {"name": "url", "label": "Gateway URL", "type": "url", "placeholder": "https://aevibron-gateway.vercel.app/api/v1", "required": True,
             "hint": "Include the /api/v1 path. If you paste the bare host, IRIS adds /api/v1 for you."},
            {"name": "key", "label": "API Key", "type": "password", "placeholder": "Your Aevibron API key", "required": False,
             "hint": "Sent as the Bearer token — this is the credential the gateway checks."},
            {"name": "x_aevibron_key", "label": "X-Aevibron-Key (leave blank)", "type": "password", "placeholder": "Optional — only if your gateway uses a separate access key", "required": False,
             "hint": "LEAVE BLANK unless Aevibron gave you a separate X-Aevibron-Key value. Your API key is already sent in this header automatically. A wrong value here causes HTTP 401."},
        ],
        "test_method": "openai_compat",
    },
    "ollama_local": {
        "label": "Ollama (Local)",
        "recommended": False,
        "description": "Run models locally with Ollama. Free, private, no API key needed. Requires Ollama installed.",
        "fields": [
            {"name": "host", "label": "Ollama Host", "type": "url", "placeholder": "http://localhost:11434", "required": True},
        ],
        "test_method": "openai_compat",
    },
    "ollama_cloud": {
        "label": "Ollama (Cloud)",
        "recommended": False,
        "description": "Ollama running on a remote server. Same as local but over the network.",
        "fields": [
            {"name": "url", "label": "Ollama URL", "type": "url", "placeholder": "https://your-server:11434/v1", "required": True},
            {"name": "key", "label": "API Key (if auth)", "type": "password", "placeholder": "Optional", "required": False},
        ],
        "test_method": "openai_compat",
    },
    "groq": {
        "label": "Groq",
        "recommended": False,
        "description": "Groq Cloud — blazing fast inference. Free tier at console.groq.com.",
        "fields": [
            {"name": "key", "label": "Groq API Key", "type": "password", "placeholder": "gsk_...", "required": True},
        ],
        "test_method": "groq",
    },
    "openai": {
        "label": "OpenAI",
        "recommended": False,
        "description": "OpenAI API or any OpenAI-compatible cloud (OpenRouter, Together, Anyscale, vLLM, etc.).",
        "fields": [
            {"name": "url", "label": "Base URL", "type": "url", "placeholder": "https://api.openai.com/v1", "required": True},
            {"name": "key", "label": "API Key", "type": "password", "placeholder": "sk-...", "required": True},
        ],
        "test_method": "openai_compat",
    },
    "custom": {
        "label": "Custom Provider",
        "recommended": False,
        "description": "Any OpenAI-compatible endpoint with a custom URL + key + model name.",
        "fields": [
            {"name": "url", "label": "API Base URL", "type": "url", "placeholder": "https://your-api.com/v1", "required": True},
            {"name": "key", "label": "API Key", "type": "password", "placeholder": "Your key", "required": False},
            {"name": "model", "label": "Model Name", "type": "text", "placeholder": "model-name", "required": True},
        ],
        "test_method": "openai_compat",
    },
}

# Integration definitions (GitHub, Vercel, Cloudflare — all optional)
INTEGRATIONS = {
    "github": {
        "label": "GitHub",
        "description": "For autonomous git operations (clone, commit, push, create repos, issues, PRs).",
        "fields": [
            {"name": "token", "label": "GitHub Token", "type": "password", "placeholder": "ghp_...", "required": True},
        ],
    },
    "vercel": {
        "label": "Vercel",
        "description": "For autonomous deployment to Vercel.",
        "fields": [
            {"name": "token", "label": "Vercel Token", "type": "password", "placeholder": "vercel_...", "required": True},
        ],
    },
    "cloudflare": {
        "label": "Cloudflare",
        "description": "For Cloudflare Pages deployment.",
        "fields": [
            {"name": "token", "label": "Cloudflare API Token", "type": "password", "placeholder": "", "required": True},
            {"name": "account_id", "label": "Account ID", "type": "text", "placeholder": "", "required": True},
        ],
    },
}


@settings_bp.route("/api/iris/settings", methods=["GET"])
def get_settings():
    """Get current settings — keys are MASKED (first 4 + last 4 chars)."""
    from modules.settings_manager import get_settings as _get
    return jsonify(_get())


@settings_bp.route("/api/iris/settings", methods=["POST"])
def save_settings():
    """Save settings — keys are encrypted client-side before being sent.

    The client encrypts keys using AES-GCM (Web Crypto API) with a key
    derived from the user's session. The server stores the encrypted
    values and decrypts them only at LLM call time.

    If a key field is empty or null, the existing key is preserved (not
    cleared). To explicitly clear a key, send null.
    """
    from modules.settings_manager import save_settings as _save
    data = request.get_json() or {}
    result = _save(data)
    return jsonify(result)


@settings_bp.route("/api/iris/settings/providers", methods=["GET"])
def list_providers():
    """List all supported providers with their field definitions."""
    return jsonify({
        "providers": PROVIDERS,
        "integrations": INTEGRATIONS,
    })


@settings_bp.route("/api/iris/settings/test", methods=["POST"])
def test_connection():
    """Test a provider connection — sends a minimal request and returns
    the list of available models.

    Body: {
        "provider": "groq" | "aevibron" | "ollama_local" | ...,
        "config": {"key": "...", "url": "...", ...},
        "test_prompt": "Hello" (optional)
    }

    Returns: {
        "success": true/false,
        "models": [{"id": "..."}, ...],
        "test_response": "..." (if test_prompt provided),
        "error": "..." (if failed),
        "sanitized": true (if invisible chars were stripped from input)
    }
    """
    data = request.get_json() or {}
    provider = data.get("provider", "")
    config = data.get("config", {})
    test_prompt = data.get("test_prompt", "Hi")

    if provider not in PROVIDERS:
        return jsonify({"success": False, "error": f"Unknown provider: {provider}"}), 400

    provider_info = PROVIDERS[provider]
    test_method = provider_info.get("test_method", "openai_compat")

    try:
        if test_method == "openai_compat":
            return _test_openai_compat(provider, config, test_prompt)
        elif test_method == "groq":
            return _test_groq(config, test_prompt)
        else:
            return jsonify({"success": False, "error": f"Unknown test method: {test_method}"}), 400
    except Exception as e:
        logger.exception("[settings] test failed for %s", provider)
        return jsonify({"success": False, "error": str(e)}), 500


def _friendly_http_error(url: str, e: urllib.error.HTTPError) -> str:
    """Turn raw HTTP failures into actionable messages (never dump HTML)."""
    body = ""
    try:
        body = e.read().decode("utf-8", errors="replace")
    except Exception:
        pass
    body_head = body[:200].replace("\n", " ")
    is_html = "<!doctype" in body_head.lower() or "<html" in body_head.lower()

    if e.code == 404 and is_html:
        return (f"HTTP 404 — the endpoint {url} does not exist (the server answered with an "
                f"HTML page, not JSON). For the Aevibron gateway the URL must be "
                f"https://aevibron-gateway.vercel.app/api/v1 — check that the path is complete.")
    if e.code == 404:
        return f"HTTP 404 — {url} was not found on this server."
    if e.code == 401:
        try:
            data = json.loads(body)
            detail = data.get("error") or data.get("message") or ""
        except Exception:
            detail = body_head
        return (f"HTTP 401 Unauthorized — the gateway rejected the credentials ({detail or 'none provided'}). "
                f"Most common causes: (1) the API Key field is empty or wrong — that is the credential "
                f"the gateway checks; (2) you filled the X-Aevibron-Key field with something that is not "
                f"exactly the gateway's access key — CLEAR that field and leave it blank, because IRIS "
                f"already sends your API key in that header automatically.")
    if e.code == 403:
        return f"HTTP 403 Forbidden — the key was accepted but lacks access to {url}."
    if e.code == 429:
        return "HTTP 429 — rate limited by the provider. Wait a moment and test again."
    if e.code >= 500:
        return f"HTTP {e.code} — the provider failed server-side. It said: {body_head}"
    return f"HTTP {e.code} — {body_head or url}"


def _test_openai_compat(provider: str, config: dict, test_prompt: str) -> dict:
    """Test an OpenAI-compatible endpoint (Aevibron, Ollama, OpenAI, custom).

    Provider notes (verified against the live Aevibron gateway):
      - Aevibron serves chat at POST /chat (not /chat/completions) and
        authenticates via the X-Aevibron-Key header.

    All URL and header inputs are sanitized to strip invisible Unicode
    characters (e.g. WORD JOINER \u2060) that crash urllib's latin-1
    header encoder per RFC 2616 §4.2.
    """
    chat_path = "/chat/completions"
    sanitized = False  # set True if we strip any invisible chars from input

    if provider == "aevibron":
        raw_url = (config.get("url") or "https://aevibron-gateway.vercel.app/api/v1").strip().strip("<>").rstrip("/")
        url = _sanitize_url(raw_url)
        # Users often paste the bare host — the gateway only serves /api/v1.
        if "/api/v1" not in url and not url.endswith("/v1"):
            url = f"{url}/api/v1"
        raw_key = config.get("key", "") or ""
        key = _sanitize_header_value(raw_key)
        raw_x_key = config.get("x_aevibron_key", "") or raw_key
        x_key = _sanitize_header_value(raw_x_key)
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        if x_key:
            headers["X-Aevibron-Key"] = x_key
        chat_path = "/chat"
        if url != _sanitize_url_keep_path(raw_url, provider) or key != raw_key or x_key != raw_x_key:
            sanitized = True
    elif provider == "ollama_local":
        raw_host = config.get("host", "http://localhost:11434").rstrip("/")
        host = _sanitize_url(raw_host)
        url = f"{host}/v1"
        headers = {"Content-Type": "application/json"}
        if host != raw_host.rstrip("/"):
            sanitized = True
    elif provider == "ollama_cloud":
        raw_url = config.get("url", "").rstrip("/")
        url = _sanitize_url(raw_url)
        raw_key = config.get("key", "") or ""
        key = _sanitize_header_value(raw_key)
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        if url != raw_url.rstrip("/") or key != raw_key:
            sanitized = True
    elif provider == "openai":
        raw_url = config.get("url", "https://api.openai.com/v1").rstrip("/")
        url = _sanitize_url(raw_url)
        raw_key = config.get("key", "") or ""
        key = _sanitize_header_value(raw_key)
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
        if url != raw_url.rstrip("/") or key != raw_key:
            sanitized = True
    elif provider == "custom":
        raw_url = config.get("url", "").rstrip("/")
        url = _sanitize_url(raw_url)
        raw_key = config.get("key", "") or ""
        key = _sanitize_header_value(raw_key)
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        if url != raw_url.rstrip("/") or key != raw_key:
            sanitized = True
    else:
        return {"success": False, "error": f"Unknown provider: {provider}"}

    if not url:
        return {"success": False, "error": "URL is required"}

    result_extras = {}
    if sanitized:
        result_extras["sanitized"] = True
        result_extras["sanitized_url"] = url
        result_extras["sanitized_message"] = (
            "Stripped invisible Unicode characters (e.g. WORD JOINER \\u2060, ZERO WIDTH SPACE, "
            "BOM, NBSP) from your input before sending — these characters crash Python's "
            "latin-1 header encoder (RFC 2616 §4.2). Save the cleaned URL shown in "
            "'sanitized_url' and use it as the canonical value in Settings."
        )

    # Step 1: List models
    models = []
    models_url = f"{url}/models"
    try:
        req = urllib.request.Request(models_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, list):
            models = data
        elif isinstance(data.get("data"), list):
            models = data["data"]
        elif isinstance(data.get("models"), list):
            models = data["models"]
    except urllib.error.HTTPError as e:
        result = {"success": False, "error": _friendly_http_error(models_url, e), "models": []}
        result.update(result_extras)
        return result
    except urllib.error.URLError as e:
        # The latin-1 encoder error (e.g. WORD JOINER in a header) surfaces
        # here as a URLError whose .reason is a UnicodeEncodeError. Catch
        # it explicitly so the user gets an actionable message instead of
        # the raw codec traceback.
        reason = e.reason
        if isinstance(reason, UnicodeEncodeError):
            result = {
                "success": False,
                "error": (
                    f"Header encoding failed: {reason.__class__.__name__}: {reason}. "
                    f"This means a URL or API key you pasted contains a non-ASCII "
                    f"character that Python's latin-1 HTTP header encoder (RFC 2616 "
                    f"§4.2) cannot send. Re-paste the URL/key as plain ASCII, or save "
                    f"the 'sanitized_url' value shown here and use it in Settings."
                ),
                "models": [],
            }
        else:
            result = {"success": False, "error": f"Connection failed: {reason}", "models": []}
        result.update(result_extras)
        return result
    except UnicodeEncodeError as e:
        # Belt-and-suspenders: if a non-latin-1 char somehow slipped past
        # _sanitize_header_value (e.g. inside the request body), catch it
        # here with an actionable message.
        result = {
            "success": False,
            "error": (
                f"Header encoding failed: {e}. A URL or API key you pasted "
                f"contains a non-ASCII character. Re-paste as plain ASCII."
            ),
            "models": [],
        }
        result.update(result_extras)
        return result
    except Exception as e:
        result = {"success": False, "error": str(e), "models": []}
        result.update(result_extras)
        return result

    if not models:
        result = {"success": False, "error": "Connected, but no models were returned — check the key's model access.", "models": []}
        result.update(result_extras)
        return result

    # Step 2: If test_prompt provided, send a minimal chat request
    test_response = ""
    model_id = models[0].get("id", "") if isinstance(models[0], dict) else str(models[0])
    if test_prompt and model_id:
        chat_url = f"{url}{chat_path}"
        try:
            body = json.dumps({
                "model": model_id,
                "messages": [{"role": "user", "content": test_prompt}],
                "max_tokens": 50,
            }).encode("utf-8")
            req = urllib.request.Request(chat_url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            test_response = _extract_reply(data)
            if not test_response:
                test_response = f"(unrecognized response shape: {str(data)[:150]})"
        except urllib.error.HTTPError as e:
            test_response = f"(chat test failed on {chat_url}: {_friendly_http_error(chat_url, e)})"
        except Exception as e:
            test_response = f"(chat test failed: {e})"

    result = {
        "success": True,
        "models": models if isinstance(models[0], dict) else [{"id": m} for m in models],
        "model_count": len(models),
        "test_model": model_id,
        "test_response": test_response[:200] if test_response else "",
    }
    result.update(result_extras)
    return result


def _sanitize_url_keep_path(original_url: str, provider: str) -> str:
    """Reproduce the URL normalization (without invisibles stripping) so we
    can detect whether sanitization alone changed the value. Used only for
    the Aevibron branch where the URL is augmented with /api/v1."""
    if provider == "aevibron":
        u = (original_url or "").strip().strip("<>").rstrip("/")
        if u and "/api/v1" not in u and not u.endswith("/v1"):
            u = f"{u}/api/v1"
        return u
    return (original_url or "").rstrip("/")


def _extract_reply(data: dict) -> str:
    """Pull the assistant text out of any common response shape."""
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        ch = choices[0] or {}
        msg = ch.get("message") or {}
        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
            return msg["content"]
        if isinstance(ch.get("text"), str):
            return ch["text"]
    for key in ("content", "response", "text", "output"):
        v = data.get(key)
        if isinstance(v, str) and v:
            return v
    msg = data.get("message")
    if isinstance(msg, str):
        return msg
    if isinstance(msg, dict) and isinstance(msg.get("content"), str):
        return msg["content"]
    return ""


def _test_groq(config: dict, test_prompt: str) -> dict:
    """Test a Groq connection using the groq package."""
    raw_key = config.get("key", "") or ""
    key = _sanitize_header_value(raw_key)
    if not key:
        return {"success": False, "error": "Groq API key is required"}

    try:
        from groq import Groq
        client = Groq(api_key=key)

        # List models
        models = client.models.list()
        model_list = [{"id": m.id, "object": "model"} for m in models.data]

        if not model_list:
            return {"success": False, "error": "No models available", "models": []}

        # Test chat
        test_response = ""
        model_id = model_list[0]["id"]
        if test_prompt:
            resp = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": test_prompt}],
                max_tokens=50,
            )
            test_response = resp.choices[0].message.content or ""

        result = {
            "success": True,
            "models": model_list,
            "model_count": len(model_list),
            "test_model": model_id,
            "test_response": test_response[:200] if test_response else "",
        }
        if key != raw_key:
            result["sanitized"] = True
            result["sanitized_message"] = (
                "Stripped invisible Unicode characters from your Groq API key before "
                "sending (RFC 2616 §4.2 mandates latin-1 header encoding)."
            )
        return result
    except ImportError:
        return {"success": False, "error": "groq package not installed (pip install groq)"}
    except Exception as e:
        return {"success": False, "error": str(e)}
