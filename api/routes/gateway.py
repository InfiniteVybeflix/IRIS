"""IRIS v1 Gateway Routes"""
from flask import Blueprint, jsonify
from core.aevibron_client import aevibron

gateway_bp = Blueprint('gateway', __name__, url_prefix='/api/gateway')

@gateway_bp.route('/models', methods=['GET'])
def gateway_models():
    return jsonify(aevibron.get_models())

@gateway_bp.route('/health', methods=['GET'])
def gateway_health():
    return jsonify(aevibron.health_check())

@gateway_bp.route('/stats', methods=['GET'])
def gateway_stats():
    return jsonify(aevibron.get_stats())
