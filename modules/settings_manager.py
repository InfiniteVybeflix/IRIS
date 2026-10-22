"""IRIS Settings Manager — encrypted key storage + provider configuration.

Users configure LLM providers + API keys from the Settings UI (not .env).
Keys are encrypted client-side (AES-GCM via Web Crypto API) before being
sent to the server. The server stores them encrypted in a JSON file and
decrypts only at LLM call time (in memory, never logged).

All keys are OPTIONAL — IRIS works without any keys. Adding a key
enables that provider. Removing a key disables it. No provider is
required for IRIS to boot.
"""
import json
import os
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Config file path — stored in IRIS data dir
DATA_DIR = os.environ.get("IRIS_DATA_DIR",
                           os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
CONFIG_FILE = os.path.join(DATA_DIR, "settings.json")

# Ensure data dir exists
os.makedirs(DATA_DIR, exist_ok=True)


def _load_config() -> Dict[str, Any]:
    """Load the settings JSON file. Returns empty dict if not found."""
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_config(config: Dict[str, Any]) -> None:
    """Save the settings JSON file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2, default=str)


def mask_key(key: str) -> str:
    """Mask a key for display — show first 4 + last 4 chars."""
    if not key or len(key) < 12:
        return ""
    return key[:4] + "••••••••" + key[-4:]


def get_settings() -> Dict[str, Any]:
    """Get current settings — keys are MASKED for security.

    Returns:
        {
            "llm_backend": "auto" | "aevibron" | "ollama_local" | "ollama_cloud" | "groq" | "openai" | "custom",
            "providers": {
                "aevibron": {"url": "...", "key_masked": "gsk_••••1234", "configured": true},
                "ollama_local": {"host": "http://localhost:11434", "configured": true},
                "groq": {"key_masked": "gsk_••••5678", "configured": true},
                ...
            },
            "integrations": {
                "github": {"token_masked": "ghp_••••9012", "configured": true},
                "vercel": {"token_masked": "", "configured": false},
                ...
            },
            "auto_select": true,
            "updated_at": "2026-10-21T..."
        }
    """
    config = _load_config()
    providers = config.get("providers", {})
    integrations = config.get("integrations", {})

    # Build masked response
    result = {
        "llm_backend": config.get("llm_backend", "auto"),
        "auto_select": config.get("auto_select", True),
        "providers": {},
        "integrations": {},
        "updated_at": config.get("updated_at", None),
    }

    # Mask provider keys
    provider_fields = {
        "aevibron": [("url", "url"), ("key", "key_masked"), ("x_aevibron_key", "x_aevibron_key_masked")],
        "ollama_local": [("host", "host")],
        "ollama_cloud": [("url", "url"), ("key", "key_masked")],
        "groq": [("key", "key_masked")],
        "openai": [("url", "url"), ("key", "key_masked")],
        "custom": [("url", "url"), ("key", "key_masked"), ("model", "model")],
    }
    for name, fields in provider_fields.items():
        p = providers.get(name, {})
        masked_p = {}
        for raw_field, masked_field in fields:
            val = p.get(raw_field, "")
            if "masked" in masked_field:
                masked_p[mask_field_name(masked_field)] = mask_key(val)
                masked_p["configured"] = bool(val)
            elif raw_field == "model":
                masked_p[masked_field] = val
            else:
                masked_p[masked_field] = val
        result["providers"][name] = masked_p

    # Mask integration keys
    for name in ["github", "vercel", "cloudflare"]:
        i = integrations.get(name, {})
        token = i.get("token", "")
        result["integrations"][name] = {
            "token_masked": mask_key(token),
            "configured": bool(token),
        }

    return result


def mask_field_name(field: str) -> str:
    return field


def save_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Save settings from the UI. Keys should be encrypted client-side.

    The client sends:
        {
            "llm_backend": "groq",
            "auto_select": false,
            "providers": {
                "groq": {"key": "gsk_xxx_encrypted_base64", ...},
                ...
            },
            "integrations": {
                "github": {"token": "ghp_xxx_encrypted_base64"},
                ...
            }
        }

    The server stores the encrypted values as-is. Decryption happens
    at LLM call time using the server-side decryption key.
    """
    config = _load_config()

    # Update top-level settings
    if "llm_backend" in data:
        config["llm_backend"] = data["llm_backend"]
    if "auto_select" in data:
        config["auto_select"] = data["auto_select"]

    # Update providers (merge — only update fields that are provided)
    if "providers" in data:
        current_providers = config.get("providers", {})
        for name, values in data["providers"].items():
            current = current_providers.get(name, {})
            for k, v in values.items():
                if v:  # Only update if value is non-empty
                    current[k] = v
                elif k in current and v is None:
                    # Clear the field
                    del current[k]
            current_providers[name] = current
        config["providers"] = current_providers

    # Update integrations
    if "integrations" in data:
        current_integrations = config.get("integrations", {})
        for name, values in data["integrations"].items():
            current = current_integrations.get(name, {})
            for k, v in values.items():
                if v:
                    current[k] = v
                elif k in current and v is None:
                    del current[k]
            current_integrations[name] = current
        config["integrations"] = current_integrations

    config["updated_at"] = datetime.utcnow().isoformat()

    _save_config(config)
    logger.info("[settings] saved — backend=%s, auto=%s", config.get("llm_backend"), config.get("auto_select"))

    return {"success": True, "message": "Settings saved", "updated_at": config["updated_at"]}


def get_provider_config(provider: str) -> Dict[str, Any]:
    """Get the decrypted config for a specific provider (for internal use).

    This is called by llm_router when it needs to make an LLM call.
    Keys are returned as-is (still encrypted from the client) — the
    router decrypts them at call time.

    If the provider isn't configured, returns empty dict.
    """
    config = _load_config()
    providers = config.get("providers", {})
    return providers.get(provider, {})


def get_integration_config(name: str) -> Dict[str, Any]:
    """Get the config for a specific integration (github, vercel, etc.)."""
    config = _load_config()
    integrations = config.get("integrations", {})
    return integrations.get(name, {})


def get_llm_backend() -> str:
    """Get the currently selected LLM backend."""
    config = _load_config()
    return config.get("llm_backend", "auto")


def is_auto_select() -> bool:
    """Check if auto-select mode is enabled."""
    config = _load_config()
    return config.get("auto_select", True)


def get_all_config() -> Dict[str, Any]:
    """Get the full unmasked config (for internal use only)."""
    return _load_config()
