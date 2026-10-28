"""IRIS Settings Manager — integrations persistence (PostgreSQL-backed).

SCOPE (v2): provider/LLM configuration is GONE from user settings — the AI
service is configured 100% server-side via environment variables and is
never mentioned in the frontend. What remains here is the optional
integrations layer (GitHub / Vercel / Cloudflare tokens) used by agents for
real git and deploy work.

Storage:
  - PostgreSQL (kv_store, namespace="settings") when available — persistent
    across cold starts, shared across instances.
  - JSON file for local dev.
  - Process-local memory as a last-resort fallback (reported honestly).

All values are OPTIONAL — IRIS works without any of them.
"""
import json
import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)

_MEM_CACHE: Dict[str, Any] = {}
_MEM_CACHE_LOCK = threading.Lock()


def _is_vercel_env() -> bool:
    return os.environ.get("VERCEL") is not None or os.environ.get("VERCEL_ENV") is not None


def _postgres_active() -> bool:
    try:
        from core.db import db
        return bool(db._db_available and db.use_postgres)
    except Exception:
        return False


def _postgres_configured() -> bool:
    return (os.getenv("DATABASE_URL") or "").lower().startswith("postgres")


def _ephemeral_backend_in_use() -> bool:
    if _postgres_configured() and not _postgres_active():
        return True
    if _is_vercel_env() and not _postgres_active():
        return True
    return False


_USE_POSTGRES = _postgres_active()

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
    """Load settings — PostgreSQL if available, JSON file, then memory."""
    if _postgres_active():
        try:
            from core.db import db
            data = db.get_json("settings", "config")
            if isinstance(data, dict):
                with _MEM_CACHE_LOCK:
                    _MEM_CACHE.clear()
                    _MEM_CACHE.update(data)
                return data
        except Exception as e:
            logger.warning(f"PostgreSQL settings load failed: {e}")
    if _CONFIG_FILE:
        try:
            with open(_CONFIG_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, dict):
                with _MEM_CACHE_LOCK:
                    _MEM_CACHE.clear()
                    _MEM_CACHE.update(data)
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        except Exception as e:
            logger.warning(f"JSON settings load failed: {e}")
    with _MEM_CACHE_LOCK:
        if _MEM_CACHE:
            return dict(_MEM_CACHE)
    return {}


def _save_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Save settings. Returns {"ok": True, "backend": "..."} or an error."""
    errors = []
    with _MEM_CACHE_LOCK:
        _MEM_CACHE.clear()
        _MEM_CACHE.update(cfg)

    if _postgres_active():
        try:
            from core.db import db
            db.store_json("settings", "config", cfg)
            return {"ok": True, "backend": "postgresql"}
        except Exception as e:
            errors.append(f"postgresql: {e}")
            logger.warning(f"PostgreSQL settings save failed: {e}")
    if _CONFIG_FILE:
        try:
            os.makedirs(os.path.dirname(_CONFIG_FILE), exist_ok=True)
            with open(_CONFIG_FILE, "w") as f:
                json.dump(cfg, f, indent=2, default=str)
            return {"ok": True, "backend": "json_file"}
        except Exception as e:
            errors.append(f"json_file: {e}")
            logger.warning(f"JSON settings save failed: {e}")
    if _MEM_CACHE:
        return {"ok": True, "backend": "memory"}
    return {"ok": False, "error": "; ".join(errors) or "no storage backend available"}


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) < 12:
        return "••••"
    return key[:4] + "••••••••" + key[-4:]


def get_settings() -> Dict[str, Any]:
    """Current integrations (masked). No provider data exists anymore —
    the AI service is server-side configuration, invisible to clients."""
    cfg = _load_config()
    integrations = cfg.get("integrations", {})
    postgres_on = _postgres_active()
    ephemeral = _ephemeral_backend_in_use()
    if postgres_on:
        storage_label = "postgresql"
    elif _CONFIG_FILE and not ephemeral:
        storage_label = "json_file"
    elif ephemeral:
        storage_label = "memory"
    else:
        storage_label = "json_file"
    result = {
        "integrations": {},
        "updated_at": cfg.get("updated_at", None),
        "storage": storage_label,
        "persistent": postgres_on or (not ephemeral and not _is_vercel_env()),
    }
    if ephemeral and not postgres_on:
        result["storage_warning"] = (
            "Server-side storage is ephemeral on this deployment — integration "
            "tokens will not survive a cold start. Set DATABASE_URL for persistence."
        )
    for name in ["github", "vercel", "cloudflare"]:
        i = integrations.get(name, {})
        token = i.get("token", "")
        result["integrations"][name] = {
            "token_masked": mask_key(token),
            "configured": bool(token),
        }
    return result


def save_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Save integrations. Provider fields are ignored — they no longer exist."""
    cfg = _load_config()
    if "integrations" in data and isinstance(data["integrations"], dict):
        current = cfg.get("integrations", {})
        for name, values in data["integrations"].items():
            if not isinstance(values, dict):
                continue
            entry = current.get(name, {})
            for k, v in values.items():
                if v:
                    entry[k] = v
                elif k in entry and v is None:
                    del entry[k]
            current[name] = entry
        cfg["integrations"] = current
    cfg["updated_at"] = datetime.utcnow().isoformat()

    saved = _save_config(cfg)
    if not saved.get("ok"):
        logger.error("[settings] SAVE FAILED — %s", saved.get("error"))
        return {"success": False,
                "error": f"Settings could NOT be saved: {saved.get('error')}"}

    backend = saved.get("backend", "json_file")
    ephemeral = _ephemeral_backend_in_use()
    if backend == "json_file" and ephemeral:
        return {"success": False, "ephemeral": True, "storage": "memory",
                "error": ("Storage on this deployment is temporary — integrations "
                          "will not survive a cold start. Set DATABASE_URL for "
                          "persistent storage.")}
    return {"success": True, "message": "Settings saved",
            "updated_at": cfg["updated_at"],
            "storage": backend, "persistent": not ephemeral}


def get_integration_config(name: str) -> Dict[str, Any]:
    return _load_config().get("integrations", {}).get(name, {})


def get_all_config() -> Dict[str, Any]:
    """Full raw settings dict (internal use only)."""
    return _load_config()
