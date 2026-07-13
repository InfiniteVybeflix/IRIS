"""IRIS v1 Consciousness Routes"""
from flask import Blueprint, request, jsonify
from modules.consciousness import consciousness

consciousness_bp = Blueprint('consciousness', __name__, url_prefix='/api/consciousness')

@consciousness_bp.route('/state', methods=['GET'])
def consciousness_state():
    return jsonify(consciousness.get_emotional_state())

@consciousness_bp.route('/think', methods=['GET'])
def consciousness_think():
    return jsonify({"success": True, "thought": consciousness.think(request.args.get('trigger'))})

@consciousness_bp.route('/reflect', methods=['GET'])
def consciousness_reflect():
    return jsonify({"success": True, "reflection": consciousness.reflect()})

@consciousness_bp.route('/identity', methods=['GET'])
def consciousness_identity():
    return jsonify({"success": True, "identity": consciousness.get_identity_statement()})

@consciousness_bp.route('/thoughts', methods=['GET'])
def consciousness_thoughts():
    return jsonify({"success": True, "thoughts": consciousness.get_recent_thoughts(request.args.get('limit', 10, type=int))})
