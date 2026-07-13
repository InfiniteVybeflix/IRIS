"""IRIS v1 Autonomous Routes"""
from datetime import datetime
from flask import Blueprint, request, jsonify
from modules.autonomous import autonomous_engine

autonomous_bp = Blueprint('autonomous', __name__, url_prefix='/api/autonomous')

@autonomous_bp.route('/status', methods=['GET'])
def autonomous_status():
    return jsonify(autonomous_engine.get_status())

@autonomous_bp.route('/queue', methods=['POST'])
def autonomous_queue():
    data = request.get_json() or {}
    if not data.get('description'):
        return jsonify({"success": False, "error": "Description required"}), 400
    return jsonify({"success": True, "task_id": autonomous_engine.queue_task(data['description'], data.get('priority', 5), data.get('type', 'general'))})

@autonomous_bp.route('/schedule', methods=['POST'])
def autonomous_schedule():
    data = request.get_json() or {}
    if not data.get('description') or not data.get('run_at'):
        return jsonify({"success": False, "error": "Description and run_at required"}), 400
    try:
        task_id = autonomous_engine.schedule_task(data['description'], datetime.fromisoformat(data['run_at']))
        return jsonify({"success": True, "task_id": task_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
