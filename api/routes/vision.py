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

@vision_bp.route('/frame', methods=['GET'])
def vision_frame():
    """Return the most recent frame captured by the running stream.

    The frontend polls this endpoint while a stream is active, so the
    vision feed shows real frames captured by the IRIS vision module
    (no client-side simulation).
    """
    frame = vision_stream.get_last_frame_base64()
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
