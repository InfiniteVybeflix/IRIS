"""IRIS v1 Vision Routes"""
from flask import Blueprint, request, jsonify
from modules.vision_stream import vision_stream

vision_bp = Blueprint('vision', __name__, url_prefix='/api/vision')

@vision_bp.route('/capture', methods=['POST'])
def vision_capture():
    data = request.get_json() or {}
    source = data.get('source', 'screen')
    frame = vision_stream.capture_screen() if source == 'screen' else vision_stream.capture_camera()
    return jsonify({"success": frame is not None, "frame": frame})

@vision_bp.route('/stream/start', methods=['POST'])
def vision_stream_start():
    data = request.get_json() or {}
    vision_stream.start_stream(data.get('source', 'screen'), data.get('interval', 2.0))
    return jsonify({"success": True, "message": f"Vision stream started: {data.get('source', 'screen')}"})

@vision_bp.route('/stream/stop', methods=['POST'])
def vision_stream_stop():
    vision_stream.stop_stream()
    return jsonify({"success": True, "message": "Vision stream stopped"})

@vision_bp.route('/analyze', methods=['POST'])
def vision_analyze():
    data = request.get_json() or {}
    return jsonify(vision_stream.analyze_current_view(data.get('question', 'What do you see?')))
