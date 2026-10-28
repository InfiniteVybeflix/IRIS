"""IRIS Gateway Routes — generic AI-service status (authed).

Reveals nothing about the AI backend: no URLs, no keys, no provider names —
just "is the service healthy" and the model list for signed-in users.
"""
from flask import Blueprint, jsonify

from core.aevibron_client import aevibron
from api.routes.auth import require_auth

gateway_bp = Blueprint('gateway', __name__, url_prefix='/api/gateway')


@gateway_bp.route('/models', methods=['GET'])
@require_auth
def gateway_models(user):
    result = aevibron.get_models()
    if isinstance(result, dict) and result.get("error"):
        return jsonify({"success": False, "error": result.get("message", "AI service error")}), 502
    return jsonify({"success": True, "models": result or []})


@gateway_bp.route('/health', methods=['GET'])
def gateway_health():
    """Public, generic health probe — used by the system status indicator."""
    result = aevibron.health_check()
    return jsonify({"healthy": bool(result.get("healthy")),
                    "status_code": result.get("status_code"),
                    "error": result.get("error")})
