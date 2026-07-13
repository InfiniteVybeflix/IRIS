"""IRIS v1 Self-Improvement Routes"""
from flask import Blueprint, request, jsonify
from modules.self_improve import self_improvement

self_improve_bp = Blueprint('self_improve', __name__, url_prefix='/api/self')

@self_improve_bp.route('/analyze', methods=['GET'])
def self_analyze():
    return jsonify(self_improvement.analyze_self())

@self_improve_bp.route('/fix', methods=['POST'])
def self_fix():
    data = request.get_json() or {}
    result = self_improvement.apply_fix(data.get('file_path', ''), data.get('old_text', ''), data.get('new_text', ''))
    return jsonify(result.dict())

@self_improve_bp.route('/codebase', methods=['GET'])
def self_codebase():
    return jsonify(self_improvement.get_own_codebase_map())

@self_improve_bp.route('/history', methods=['GET'])
def self_history():
    return jsonify({"success": True, "changes": self_improvement.get_change_history()})
