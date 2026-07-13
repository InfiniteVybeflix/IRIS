"""IRIS v1 Proactive (Jarvis) Routes"""
from flask import Blueprint, request, jsonify
from modules.proactive_engine import proactive_engine

proactive_bp = Blueprint('proactive', __name__, url_prefix='/api/proactive')

@proactive_bp.route('/status', methods=['GET'])
def proactive_status():
    return jsonify({
        "enabled": proactive_engine.enabled,
        "running": proactive_engine.running,
        "last_check": proactive_engine.last_check.isoformat() if proactive_engine.last_check else None,
        "context_history_count": len(proactive_engine.context_history),
        "patterns_learned": len(proactive_engine.owner_patterns)
    })

@proactive_bp.route('/toggle', methods=['POST'])
def proactive_toggle():
    enabled = request.get_json().get('enabled', not proactive_engine.enabled)
    if enabled:
        proactive_engine.start()
    else:
        proactive_engine.stop()
    return jsonify({"success": True, "enabled": enabled})

@proactive_bp.route('/suggest', methods=['GET'])
def proactive_suggest():
    return jsonify({"success": True, "suggestion": proactive_engine.suggest_action()})

@proactive_bp.route('/context', methods=['GET'])
def proactive_context():
    return jsonify({"success": True, "context": proactive_engine.get_context_summary()})
