"""IRIS v1 Mobile API Routes"""
from flask import Blueprint, request, jsonify
from modules.mobile_api import mobile_api

mobile_bp = Blueprint('mobile', __name__, url_prefix='/api/mobile')

@mobile_bp.route('/register', methods=['POST'])
def mobile_register():
    data = request.get_json() or {}
    if not data.get('device_id'):
        return jsonify({"success": False, "error": "device_id required"}), 400
    return jsonify(mobile_api.register_device(data['device_id'], data.get('device_type', 'android'), data.get('push_token')))

@mobile_bp.route('/status', methods=['POST'])
def mobile_status():
    data = request.get_json() or {}
    return jsonify(mobile_api.update_device_status(data.get('device_id', ''), data.get('battery_level'), data.get('location')))

@mobile_bp.route('/devices', methods=['GET'])
def mobile_devices():
    return jsonify({"success": True, "devices": mobile_api.get_all_devices()})

@mobile_bp.route('/notify', methods=['POST'])
def mobile_notify():
    data = request.get_json() or {}
    return jsonify(mobile_api.send_push_notification(data.get('device_id', ''), data.get('title', ''), data.get('body', '')))
