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
import logging
import urllib.request
import urllib.error
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)
settings_bp = Blueprint("iris_settings", __name__)

# ─── Provider definitions ──────────────────────────────────────────────
# The list of supported providers, their fields, and whether they need a key
PROVIDERS = {
    "aevibron": {
        "label": "Aevibron Gateway",
        "recommended": True,
        "description": "Aevibron's AI gateway — OpenAI-compatible proxy. Recommended for best results.",
        "fields": [
            {"name": "url", "label": "Gateway URL", "type": "url", "placeholder": "https://aevibron-gateway.vercel.app/api/v1", "required": True},
            {"name": "key", "label": "API Key", "type": "password", "placeholder": "Your Aevibron API key", "required": False},
            {"name": "x_aevibron_key", "label": "X-Aevibron-Key (optional)", "type": "password", "placeholder": "X-Aevibron-Key header value", "required": False},
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
        "error": "..." (if failed)
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


def _test_openai_compat(provider: str, config: dict, test_prompt: str) -> dict:
    """Test an OpenAI-compatible endpoint (Aevibron, Ollama, OpenAI, custom)."""
    # Build URL + headers
    if provider == "aevibron":
        url = (config.get("url") or "https://aevibron-gateway.vercel.app/api/v1").rstrip("/")
        key = config.get("key", "")
        x_key = config.get("x_aevibron_key", "")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        if x_key:
            headers["X-Aevibron-Key"] = x_key
    elif provider == "ollama_local":
        host = config.get("host", "http://localhost:11434").rstrip("/")
        url = f"{host}/v1"
        headers = {"Content-Type": "application/json"}
    elif provider == "ollama_cloud":
        url = config.get("url", "").rstrip("/")
        key = config.get("key", "")
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
    elif provider == "openai":
        url = config.get("url", "https://api.openai.com/v1").rstrip("/")
        key = config.get("key", "")
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    elif provider == "custom":
        url = config.get("url", "").rstrip("/")
        key = config.get("key", "")
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
    else:
        return {"success": False, "error": f"Unknown provider: {provider}"}

    if not url:
        return {"success": False, "error": "URL is required"}

    # Step 1: List models
    models = []
    try:
        models_url = f"{url}/models"
        req = urllib.request.Request(models_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("data", [])
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:300]
        return {"success": False, "error": f"HTTP {e.code}: {err_body}", "models": []}
    except urllib.error.URLError as e:
        return {"success": False, "error": f"Connection failed: {e.reason}", "models": []}
    except Exception as e:
        return {"success": False, "error": str(e), "models": []}

    if not models:
        return {"success": False, "error": "Connected but no models returned", "models": []}

    # Step 2: If test_prompt provided, send a minimal chat request
    test_response = ""
    model_id = models[0].get("id", "") if models else ""
    if test_prompt and model_id:
        try:
            chat_url = f"{url}/chat/completions"
            body = json.dumps({
                "model": model_id,
                "messages": [{"role": "user", "content": test_prompt}],
                "max_tokens": 50,
            }).encode("utf-8")
            req = urllib.request.Request(chat_url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                test_response = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            test_response = f"(chat test failed: {e})"

    return {
        "success": True,
        "models": models,
        "model_count": len(models),
        "test_model": model_id,
        "test_response": test_response[:200] if test_response else "",
    }


def _test_groq(config: dict, test_prompt: str) -> dict:
    """Test a Groq connection using the groq package."""
    key = config.get("key", "")
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

        return {
            "success": True,
            "models": model_list,
            "model_count": len(model_list),
            "test_model": model_id,
            "test_response": test_response[:200] if test_response else "",
        }
    except ImportError:
        return {"success": False, "error": "groq package not installed (pip install groq)"}
    except Exception as e:
        return {"success": False, "error": str(e)}
