"""IRIS v1 API Routes — All endpoint blueprints registered here."""
from flask import Blueprint

from api.routes.auth import auth_bp
from api.routes.chat import chat_bp
from api.routes.voice import voice_bp
from api.routes.vision import vision_bp
from api.routes.phone import phone_bp
from api.routes.calendar import calendar_bp
from api.routes.notes import notes_bp
from api.routes.math import math_bp
from api.routes.projects import projects_bp
from api.routes.self_improve import self_improve_bp
from api.routes.consciousness import consciousness_bp
from api.routes.memory import memory_bp
from api.routes.autonomous import autonomous_bp
from api.routes.proactive import proactive_bp
from api.routes.mobile import mobile_bp
from api.routes.tools import tools_bp
from api.routes.email import email_bp
from api.routes.news import news_bp
from api.routes.sports import sports_bp
from api.routes.image import image_bp
from api.routes.gateway import gateway_bp
from api.routes.system import system_bp
from api.routes.intelligence import intelligence_bp

__all__ = [
    "auth_bp", "chat_bp", "voice_bp", "vision_bp", "phone_bp",
    "calendar_bp", "notes_bp", "math_bp", "projects_bp",
    "self_improve_bp", "consciousness_bp", "memory_bp",
    "autonomous_bp", "proactive_bp", "mobile_bp", "tools_bp",
    "email_bp", "news_bp", "sports_bp", "image_bp",
    "gateway_bp", "system_bp", "intelligence_bp",
]
