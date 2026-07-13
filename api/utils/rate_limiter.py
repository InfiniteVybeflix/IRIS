"""IRIS v1 Rate Limiter — Simple in-memory throttling"""
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from config import config

rate_limit_store = {}

def rate_limit(f):
    """Rate limiter: 60 requests per minute per IP."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not config.RATE_LIMIT_ENABLED:
            return f(*args, **kwargs)
        ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        now = datetime.now()
        window_start = now - timedelta(seconds=config.RATE_LIMIT_WINDOW)
        rate_limit_store[ip] = [t for t in rate_limit_store.get(ip, []) if t > window_start]
        if len(rate_limit_store[ip]) >= config.RATE_LIMIT_REQUESTS:
            return jsonify({"success": False, "error": "Rate limit exceeded. Try again in a minute."}), 429
        rate_limit_store[ip].append(now)
        return f(*args, **kwargs)
    return decorated
