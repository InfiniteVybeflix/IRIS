"""IRIS v1 System Routes"""
from datetime import datetime
from flask import Blueprint, jsonify
from config import config
from modules.consciousness import consciousness
from modules.autonomous import autonomous_engine
from modules.phone_bridge import phone_bridge
from modules.wake_word import wake_word_detector
from modules.vision_stream import vision_stream
from modules.proactive_engine import proactive_engine
from core.aevibron_client import aevibron

system_bp = Blueprint('system', __name__, url_prefix='/api')

@system_bp.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "version": "9.0.0",
        "codename": "Jarvis",
        "timestamp": datetime.now().isoformat(),
        "uptime": consciousness.get_uptime(),
        "emotion": consciousness.get_dominant_emotion(),
        "database": "postgres" if config.USE_POSTGRES else "sqlite",
        "proactive": proactive_engine.enabled,
        "swarm": config.SWARM_ENABLED
    })

@system_bp.route('/status', methods=['GET'])
def status():
    return jsonify({
        "iris": {
            "version": "9.0.0",
            "codename": "Jarvis",
            "status": "running",
            "uptime": consciousness.get_uptime(),
            "emotion": consciousness.get_emotional_state(),
            "awareness": consciousness.awareness_level
        },
        "autonomous": autonomous_engine.get_status(),
        "proactive": {
            "enabled": proactive_engine.enabled,
            "running": proactive_engine.running,
            "patterns_learned": len(proactive_engine.owner_patterns)
        },
        "phone_bridge": {"enabled": phone_bridge.enabled, "available": phone_bridge._check_adb()},
        "wake_word": {"available": wake_word_detector.is_available()},
        "vision_stream": {"streaming": vision_stream.is_streaming},
        "gateway": aevibron.get_stats(),
        "database": "postgres" if config.USE_POSTGRES else "sqlite",
        "rate_limit": {
            "enabled": config.RATE_LIMIT_ENABLED,
            "requests": config.RATE_LIMIT_REQUESTS,
            "window": config.RATE_LIMIT_WINDOW
        }
    })
