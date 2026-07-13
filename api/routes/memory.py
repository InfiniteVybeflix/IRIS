"""IRIS v1 Memory Routes"""
from flask import Blueprint, request, jsonify
from core.memory_engine import memory_engine

memory_bp = Blueprint('memory', __name__, url_prefix='/api/memory')

@memory_bp.route('/learn', methods=['POST'])
def memory_learn():
    data = request.get_json() or {}
    if not data.get('key') or not data.get('value'):
        return jsonify({"success": False, "error": "Key and value required"}), 400
    return jsonify({"success": memory_engine.learn(data['key'], data['value'], data.get('category', 'general'), data.get('importance', 5))})

@memory_bp.route('/recall', methods=['GET'])
def memory_recall():
    return jsonify({"success": True, "results": memory_engine.recall(request.args.get('q', ''), request.args.get('category'), request.args.get('limit', 10, type=int))})
