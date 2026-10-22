"""IRIS Settings Manager — PostgreSQL-backed settings storage.

PROPER ARCHITECTURE:
- When PostgreSQL (Supabase) is available → settings stored in
  kv_store table with namespace="settings". Persistent across
  cold starts, shared across instances. No JSON files, no /tmp/.
- When PostgreSQL is NOT available (local dev) → falls back to
  a JSON file at data/settings.json.
- NEVER crashes — always returns something useful.

All keys are OPTIONAL — IRIS works without any keys configured.
"""
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Try to use core/db (PostgreSQL) for persistent settings
_USE_POSTGRES = False
try:
    from core.db import db
    if db._db_available and db.use_postgres:
        _USE_POSTGRES = True
except Exception:
    pass

# Fallback: JSON file for local dev
if not _USE_POSTGRES:
    try:
        from config import config
        _DATA_DIR = config.DATA_DIR
    except ImportError:
        _DATA_DIR = os.environ.get("IRIS_DATA_DIR", "/tmp/iris-data")
else:
    _DATA_DIR = None

_CONFIG_FILE = os.path.join(_DATA_DIR, "settings.json") if _DATA_DIR else None


def _load_config() -> Dict[str, Any]:
    """Load settings — PostgreSQL if available, JSON file otherwise."""
    if _USE_POSTGRES:
        try:
            data = db.get_json("settings", "config")
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"PostgreSQL settings load failed: {e}")
    # Fall back to JSON file
    if _CONFIG_FILE:
        try:
            with open(_CONFIG_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    return {}


def _save_config(config: Dict[str, Any]) -> None:
    """Save settings — PostgreSQL if available, JSON file otherwise."""
    if _USE_POSTGRES:
        try:
            db.store_json("settings", "config", config)
            return
        except Exception as e:
            logger.warning(f"PostgreSQL settings save failed: {e}")
    # Fall back to JSON file
    if _CONFIG_FILE:
        try:
            os.makedirs(os.path.dirname(_CONFIG_FILE), exist_ok=True)
            with open(_CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"JSON settings save failed: {e}")


def mask_key(key: str) -> str:
    if not key or len(key) < 12:
        return ""
    return key[:4] + "••••••••" + key[-4:]


def get_settings() -> Dict[str, Any]:
    config = _load_config()
    providers = config.get("providers", {})
    integrations = config.get("integrations", {})
    result = {
        "llm_backend": config.get("llm_backend", "auto"),
        "auto_select": config.get("auto_select", True),
        "providers": {},
        "integrations": {},
        "updated_at": config.get("updated_at", None),
        "storage": "postgresql" if _USE_POSTGRES else "json_file",
    }
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
                masked_p[masked_field] = mask_key(val)
                masked_p["configured"] = bool(val)
            else:
                masked_p[masked_field] = val
        result["providers"][name] = masked_p
    for name in ["github", "vercel", "cloudflare"]:
        i = integrations.get(name, {})
        token = i.get("token", "")
        result["integrations"][name] = {
            "token_masked": mask_key(token),
            "configured": bool(token),
        }
    return result


def save_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    config = _load_config()
    if "llm_backend" in data:
        config["llm_backend"] = data["llm_backend"]
    if "auto_select" in data:
        config["auto_select"] = data["auto_select"]
    if "providers" in data:
        current_providers = config.get("providers", {})
        for name, values in data["providers"].items():
            current = current_providers.get(name, {})
            for k, v in values.items():
                if v:
                    current[k] = v
                elif k in current and v is None:
                    del current[k]
            current_providers[name] = current
        config["providers"] = current_providers
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
    logger.info("[settings] saved — backend=%s, llm=%s", "postgresql" if _USE_POSTGRES else "json", config.get("llm_backend"))
    return {"success": True, "message": "Settings saved", "updated_at": config["updated_at"],
            "storage": "postgresql" if _USE_POSTGRES else "json_file"}


def get_provider_config(provider: str) -> Dict[str, Any]:
    config = _load_config()
    return config.get("providers", {}).get(provider, {})


def get_integration_config(name: str) -> Dict[str, Any]:
    config = _load_config()
    return config.get("integrations", {}).get(name, {})


def get_llm_backend() -> str:
    return _load_config().get("llm_backend", "auto")


def is_auto_select() -> bool:
    return _load_config().get("auto_select", True)
