"""IRIS v1 Voice Routes"""
import asyncio
from flask import Blueprint, request, jsonify
from api.utils.rate_limiter import rate_limit
from modules.wake_word import wake_word_detector
from modules.voice_system import voice_system

voice_bp = Blueprint('voice', __name__, url_prefix='/api/voice')

@voice_bp.route('/speak', methods=['POST'])
@rate_limit
def voice_speak():
    data = request.get_json() or {}
    text = data.get('text', '')
    emotion = data.get('emotion', 'neutral')
    if not text:
        return jsonify({"success": False, "error": "No text provided"}), 400
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(voice_system.speak(text, emotion))
        loop.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@voice_bp.route('/listen', methods=['POST'])
def voice_listen():
    return jsonify(voice_system.listen())

@voice_bp.route('/wake-word/start', methods=['POST'])
def start_wake_word():
    wake_word_detector.start_listening()
    return jsonify({"success": True, "message": "Wake word listener started"})

@voice_bp.route('/wake-word/stop', methods=['POST'])
def stop_wake_word():
    wake_word_detector.stop_listening()
    return jsonify({"success": True, "message": "Wake word listener stopped"})
