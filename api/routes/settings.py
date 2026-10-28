"""IRIS Settings API — optional integrations only.

The LLM/provider configuration that used to live here is GONE: the AI
service is configured 100% server-side via environment variables and is
never mentioned in, or accepted from, the frontend. Employees open IRIS
and it works — no keys, no setup.

Endpoints (all authed):
  GET  /api/iris/settings   — current integrations (tokens MASKED)
  POST /api/iris/settings   — save integrations (empty token = keep existing)

Security:
  - Tokens are stored server-side, returned masked (first 4 + last 4 chars)
  - Never logged
"""
import importlib.util
import logging
import os

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
settings_bp = Blueprint("iris_settings", __name__)


def _settings_manager():
    """Import modules.settings_manager robustly."""
    try:
        from modules import settings_manager as sm
        return sm
    except Exception:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "modules", "settings_manager.py")
        spec = importlib.util.spec_from_file_location("_iris_settings_manager", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


# Integration definitions (GitHub, Vercel, Cloudflare — all optional).
# These unlock agent features (git ops, deploys); they are NOT required.
INTEGRATIONS = {
    "github": {
        "label": "GitHub",
        "description": "For autonomous git operations (clone, commit, push, create repos, issues, PRs).",
        "fields": [
            {"name": "token", "label": "GitHub Token", "type": "password",
             "placeholder": "ghp_...", "required": True},
        ],
    },
    "vercel": {
        "label": "Vercel",
        "description": "For autonomous deployment to Vercel.",
        "fields": [
            {"name": "token", "label": "Vercel Token", "type": "password",
             "placeholder": "vercel_...", "required": True},
        ],
    },
    "cloudflare": {
        "label": "Cloudflare",
        "description": "For Cloudflare Pages deployment.",
        "fields": [
            {"name": "token", "label": "Cloudflare API Token", "type": "password",
             "placeholder": "", "required": True},
            {"name": "account_id", "label": "Account ID", "type": "text",
             "placeholder": "", "required": True},
        ],
    },
}


@settings_bp.route("/api/iris/settings", methods=["GET"])
def get_settings():
    """Current settings — tokens are MASKED (first 4 + last 4 chars)."""
    sm = _settings_manager()
    out = sm.get_settings()
    out["integrations_schema"] = INTEGRATIONS
    return jsonify(out)


@settings_bp.route("/api/iris/settings", methods=["POST"])
def save_settings():
    """Save integration tokens. If a token field is empty, the existing
    value is preserved. Send null to explicitly clear one."""
    from api.routes.auth import require_auth, current_user
    if not current_user():
        return jsonify({"success": False, "error": "Sign in required.",
                        "auth_required": True}), 401

    sm = _settings_manager()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    result = sm.save_settings(data)
    return jsonify(result)
