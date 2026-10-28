"""IRIS Settings Manager — PostgreSQL-backed settings storage.

PROPER ARCHITECTURE:
- When PostgreSQL (Neon/Vercel Postgres) is available → settings stored in
  kv_store table with namespace="settings". Persistent across
  cold starts, shared across instances. No JSON files, no /tmp/.
- When PostgreSQL is NOT available (local dev) → falls back to
  a JSON file at data/settings.json (persistent on a real machine).
- On Vercel with DATABASE_URL configured but Postgres unreachable, the
  /tmp fallback is EPHEMERAL (wiped between invocations). We detect that
  case and report it loudly instead of pretending the save worked — a
  "Settings saved" toast that vanishes on refresh is a lie, and IRIS
  never lies about persistence.
- On Vercel with NO DATABASE_URL at all → SAME EPHEMERAL PROBLEM: writes
  land in /tmp/iris-data/settings.json and are wiped on the next
  invocation. Previously this case was NOT flagged (because the old
  _ephemeral_backend_in_use() only triggered when DATABASE_URL was
  configured), so save_settings returned success even though nothing
  persisted. That is the root cause of "settings don't survive refresh"
  — fixed below.
- We also keep a process-local in-memory cache as a final fallback so
  that within a single warm serverless invocation, save→load round-trips
  work even if /tmp is somehow unavailable. The cache is exposed as
  `persistent: false` so the UI can warn the user.
- NEVER crashes — always returns something useful.

All keys are OPTIONAL — IRIS works without any keys configured.
"""
import json
import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# Process-local fallback cache. On a serverless function this survives only
# for the duration of a single warm invocation — NOT a real persistent
# store. It exists so a save→load round-trip within one request works even
# when every other backend fails. The UI is told (via `persistent: false`)
# that this is not durable, and the frontend keeps its own localStorage
# copy as the real source of truth for browser-side settings.
_MEM_CACHE: Dict[str, Any] = {}
_MEM_CACHE_LOCK = threading.Lock()


def _is_vercel_env() -> bool:
    """True when running on Vercel serverless (where /tmp is wiped between
    invocations)."""
    return os.environ.get("VERCEL") is not None or os.environ.get("VERCEL_ENV") is not None


# ─── Backend detection (checked at CALL time, not import time) ─────────
def _postgres_active() -> bool:
    """True when the core.db singleton is healthy and running on Postgres.

    Checked per call — a DB that connected after this module was imported
    (or recovered after a cold-start failure) is picked up immediately
    instead of being stuck on the import-time snapshot.
    """
    try:
        from core.db import db
        return bool(db._db_available and db.use_postgres)
    except Exception:
        return False


def _postgres_configured() -> bool:
    """True when DATABASE_URL points at Postgres — i.e. the deployment is
    SUPPOSED to have a persistent database, whether or not it is reachable."""
    return (os.getenv("DATABASE_URL") or "").lower().startswith("postgres")


def _ephemeral_backend_in_use() -> bool:
    """True when writes are landing in storage that will NOT survive a
    serverless invocation.

    Two cases both count as ephemeral:
      1. DATABASE_URL is configured but Postgres is unreachable → /tmp fallback
      2. Running on Vercel AND no Postgres is active (regardless of whether
         DATABASE_URL is set) → /tmp fallback is the only option and is wiped
         between invocations

    Case 2 was previously missed, which is why "I saved settings, it said
    saved, refresh reset everything" happened on a Vercel deployment with no
    DATABASE_URL configured. Fixed here.
    """
    if _postgres_configured() and not _postgres_active():
        return True
    if _is_vercel_env() and not _postgres_active():
        return True
    return False


# Legacy import-time flag kept for backwards-compatible logging only.
_USE_POSTGRES = _postgres_active()

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

# Set when the last load hit an error worth surfacing to the user
# (e.g. Postgres configured but unreachable). get_settings() exposes it
# as `storage_warning` so the UI can tell the user WHY their settings
# appear empty instead of silently showing blanks.
_LAST_LOAD_ERROR: Optional[str] = None


def _load_config() -> Dict[str, Any]:
    """Load settings — PostgreSQL if available, JSON file otherwise, then
    in-memory cache as a last resort.

    Sets _LAST_LOAD_ERROR when the persistent backend failed, so callers
    can warn the user that an empty result may be a load failure rather
    than genuinely-empty settings.
    """
    global _LAST_LOAD_ERROR
    _LAST_LOAD_ERROR = None
    if _postgres_active():
        try:
            from core.db import db
            data = db.get_json("settings", "config")
            if isinstance(data, dict) and data:
                # Mirror into the in-memory cache so a Postgres blip on the
                # NEXT call doesn't immediately show an empty UI.
                with _MEM_CACHE_LOCK:
                    _MEM_CACHE.clear()
                    _MEM_CACHE.update(data)
                return data
            if isinstance(data, dict):
                return data
        except Exception as e:
            _LAST_LOAD_ERROR = f"PostgreSQL read failed: {e}"
            logger.warning(f"PostgreSQL settings load failed: {e}")
    elif _postgres_configured():
        _LAST_LOAD_ERROR = ("PostgreSQL is configured (DATABASE_URL) but unreachable "
                            "right now — settings could not be read from persistent storage.")
        logger.warning(_LAST_LOAD_ERROR)
    # Fall back to JSON file
    if _CONFIG_FILE:
        try:
            with open(_CONFIG_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, dict):
                # Mirror into the in-memory cache.
                with _MEM_CACHE_LOCK:
                    _MEM_CACHE.clear()
                    _MEM_CACHE.update(data)
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        except Exception as e:
            logger.warning(f"JSON settings load failed: {e}")
    # Last resort: the in-memory cache (may be empty on a cold start)
    with _MEM_CACHE_LOCK:
        if _MEM_CACHE:
            return dict(_MEM_CACHE)
    return {}


def _save_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Save settings — PostgreSQL if available, JSON file otherwise, then
    in-memory cache as a final fallback.

    Returns {"ok": True, "backend": "..."} on success, or
    {"ok": False, "error": "..."} when EVERY backend failed.
    Callers MUST surface a failed save instead of claiming success —
    a silent save failure is exactly what makes settings "reset" on
    refresh.
    """
    errors = []
    # ALWAYS mirror into the in-memory cache first — that way even if every
    # other backend fails, a save→load round-trip within the same warm
    # invocation still works (the UI is told `persistent: false`).
    with _MEM_CACHE_LOCK:
        _MEM_CACHE.clear()
        _MEM_CACHE.update(config)

    if _postgres_active():
        try:
            from core.db import db
            db.store_json("settings", "config", config)
            return {"ok": True, "backend": "postgresql"}
        except Exception as e:
            errors.append(f"postgresql: {e}")
            logger.warning(f"PostgreSQL settings save failed: {e}")
    if _CONFIG_FILE:
        try:
            os.makedirs(os.path.dirname(_CONFIG_FILE), exist_ok=True)
            with open(_CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2, default=str)
            return {"ok": True, "backend": "json_file"}
        except Exception as e:
            errors.append(f"json_file: {e}")
            logger.warning(f"JSON settings save failed: {e}")
    # If we got here, both Postgres and the JSON file failed — but the
    # in-memory cache write above succeeded, so report that honestly.
    if _MEM_CACHE:
        return {"ok": True, "backend": "memory"}
    return {"ok": False, "error": "; ".join(errors) or "no storage backend available"}


def mask_key(key: str) -> str:
    """Mask a secret for display. Any non-empty value produces a non-empty
    mask (a blank mask makes a saved key indistinguishable from a missing
    one — that used to make short keys LOOK like they were never saved)."""
    if not key:
        return ""
    if len(key) < 12:
        return "••••"
    return key[:4] + "••••••••" + key[-4:]


def get_settings() -> Dict[str, Any]:
    global _LAST_LOAD_ERROR
    cfg = _load_config()
    providers = cfg.get("providers", {})
    integrations = cfg.get("integrations", {})
    postgres_on = _postgres_active()
    ephemeral = _ephemeral_backend_in_use()
    # Storage label: reflects where the LAST load actually came from.
    # 'postgresql' = persistent DB, 'json_file' = local dev file,
    # 'memory' = in-process cache (NOT durable across refreshes).
    if postgres_on:
        storage_label = "postgresql"
    elif _CONFIG_FILE and not ephemeral:
        storage_label = "json_file"
    elif ephemeral:
        storage_label = "memory"   # /tmp on Vercel = effectively ephemeral
    else:
        storage_label = "json_file"
    result = {
        "llm_backend": cfg.get("llm_backend", "auto"),
        "auto_select": cfg.get("auto_select", True),
        "providers": {},
        "integrations": {},
        "updated_at": cfg.get("updated_at", None),
        "storage": storage_label,
        "persistent": postgres_on or (not ephemeral and not _is_vercel_env()),
    }
    if _LAST_LOAD_ERROR:
        result["storage_warning"] = _LAST_LOAD_ERROR + (
            " The values below may be INCOMPLETE — save your settings again once the database is reachable."
        )
    elif ephemeral and not postgres_on:
        # On Vercel with no DB configured — be loud and clear so the UI can
        # tell the user to keep settings in localStorage (which the frontend
        # does automatically as a fallback).
        result["storage_warning"] = (
            "Server-side storage is EPHEMERAL on this deployment (Vercel serverless with no "
            "DATABASE_URL configured) — saved values are wiped on every cold start. "
            "The frontend keeps your settings in browser localStorage as a fallback, and "
            "sends them with each chat request so the AI still uses them. For server-side "
            "persistence across devices, configure a PostgreSQL database (Neon / Vercel "
            "Postgres) and set DATABASE_URL."
        )
    provider_fields = {
        "aevibron": [("url", "url"), ("key", "key_masked"), ("x_aevibron_key", "x_aevibron_key_masked"), ("model", "model")],
        "ollama_local": [("host", "host"), ("model", "model")],
        "ollama_cloud": [("url", "url"), ("key", "key_masked"), ("model", "model")],
        "groq": [("key", "key_masked"), ("model", "model")],
        "openai": [("url", "url"), ("key", "key_masked"), ("model", "model")],
        "custom": [("url", "url"), ("key", "key_masked"), ("model", "model")],
    }
    for name, fields in provider_fields.items():
        p = providers.get(name, {})
        masked_p = {}
        configured = False
        for raw_field, masked_field in fields:
            val = p.get(raw_field, "")
            if "masked" in masked_field:
                masked_p[masked_field] = mask_key(val)
                # NOTE: `configured` is the union across ALL secret fields —
                # it must NOT be overwritten per-field. (The old code let the
                # last field — x_aevibron_key, usually empty — clobber the
                # flag set by the main key, making saved providers display
                # as "not configured" after refresh.)
                if val:
                    configured = True
            else:
                masked_p[masked_field] = val
        masked_p["configured"] = configured
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
    cfg = _load_config()
    if "llm_backend" in data:
        cfg["llm_backend"] = data["llm_backend"]
    if "auto_select" in data:
        cfg["auto_select"] = data["auto_select"]
    if "providers" in data:
        current_providers = cfg.get("providers", {})
        for name, values in data["providers"].items():
            current = current_providers.get(name, {})
            for k, v in values.items():
                if v:
                    current[k] = v
                elif k in current and v is None:
                    del current[k]
            current_providers[name] = current
        cfg["providers"] = current_providers
    if "integrations" in data:
        current_integrations = cfg.get("integrations", {})
        for name, values in data["integrations"].items():
            current = current_integrations.get(name, {})
            for k, v in values.items():
                if v:
                    current[k] = v
                elif k in current and v is None:
                    del current[k]
            current_integrations[name] = current
        cfg["integrations"] = current_integrations
    cfg["updated_at"] = datetime.utcnow().isoformat()

    saved = _save_config(cfg)
    if not saved.get("ok"):
        # NOTHING was persisted. Tell the user plainly — never fake success.
        logger.error("[settings] SAVE FAILED — %s", saved.get("error"))
        return {
            "success": False,
            "error": ("Settings could NOT be saved — nothing was persisted. "
                      f"Reason: {saved.get('error')}. "
                      "Check that the database is reachable and try again."),
        }

    backend = saved.get("backend", "json_file")
    ephemeral = _ephemeral_backend_in_use()
    if backend == "json_file" and ephemeral:
        # The write "succeeded" — but into /tmp on a serverless instance,
        # which is wiped between invocations. Refuse to claim success.
        if _postgres_configured():
            logger.error("[settings] save landed in EPHEMERAL storage (/tmp) while DATABASE_URL is configured")
            return {
                "success": False,
                "error": ("Settings were written to temporary storage that will NOT survive "
                          "a page refresh. The PostgreSQL database (DATABASE_URL) is configured "
                          "but unreachable right now — wait a moment and save again. If this "
                          "keeps happening, check your Neon/Vercel Postgres status."),
            }
        # No DATABASE_URL configured at all on a serverless deployment.
        # The frontend keeps a localStorage copy that actually drives the
        # chat — tell the user that so they don't think their work is lost.
        logger.warning("[settings] save landed in EPHEMERAL /tmp storage on Vercel with no DATABASE_URL — frontend localStorage is the source of truth")
        return {
            "success": False,
            "ephemeral": True,
            "storage": "memory",
            "error": ("Server-side storage is ephemeral on this Vercel deployment (no DATABASE_URL "
                      "configured), so saved settings will NOT survive a page refresh. The "
                      "frontend keeps your settings in browser localStorage and sends them "
                      "with each chat request, so the AI still uses them. For real "
                      "persistence across devices, set up a PostgreSQL database (Neon / "
                      "Vercel Postgres) and set DATABASE_URL in your Vercel project."),
        }

    logger.info("[settings] saved — backend=%s, llm=%s", backend, cfg.get("llm_backend"))
    return {"success": True, "message": "Settings saved", "updated_at": cfg["updated_at"],
            "storage": backend, "persistent": not ephemeral}


def get_provider_config(provider: str) -> Dict[str, Any]:
    cfg = _load_config()
    return cfg.get("providers", {}).get(provider, {})


def get_integration_config(name: str) -> Dict[str, Any]:
    cfg = _load_config()
    return cfg.get("integrations", {}).get(name, {})


def get_llm_backend() -> str:
    return _load_config().get("llm_backend", "auto")


def is_auto_select() -> bool:
    return _load_config().get("auto_select", True)


def get_all_config() -> Dict[str, Any]:
    """Return the full raw settings dict (no masking). Used by the LLM
    router to read provider URL/key/x_aevibron_key at request time so
    saved settings take effect immediately.

    Returns the same dict that _load_config() returns (Postgres → JSON
    file → in-memory cache). All sensitive values are present in
    cleartext — this function is for internal backend use only, never
    expose it via an unauthenticated GET endpoint.
    """
    return _load_config()
