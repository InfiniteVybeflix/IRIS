"""IRIS v1 Auth Routes"""
from flask import Blueprint, request, jsonify, session
from modules.security import security_manager

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    password = data.get('password', '')
    device_fingerprint = data.get('device_fingerprint')
    device_info = data.get('device_info', '')

    if security_manager.verify_password(password):
        session_id = security_manager.create_session(device_info=device_info)
        return jsonify({"success": True, "session_id": session_id, "message": "Welcome back, Infinite"})
    elif device_fingerprint and security_manager.verify_device_fingerprint(device_fingerprint):
        session_id = security_manager.create_session(device_info=device_info)
        return jsonify({"success": True, "session_id": session_id, "message": "Welcome back, Infinite"})
    return jsonify({"success": False, "error": "Invalid credentials"}), 401

@auth_bp.route('/verify', methods=['POST'])
def verify_session():
    data = request.get_json() or {}
    session_id = data.get('session_id')
    if security_manager.validate_session(session_id):
        return jsonify({"success": True, "valid": True})
    return jsonify({"success": False, "valid": False}), 401

@auth_bp.route('/logout', methods=['POST'])
def logout():
    data = request.get_json() or {}
    session_id = data.get('session_id')
    return jsonify({"success": True, "message": "Logged out"})
