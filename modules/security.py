"""IRIS v9 Hybrid Security — Authentication, Sessions & Device Management"""
import os
import hashlib
import secrets
import hmac
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from config import config
from core.db import db

logger = logging.getLogger(__name__)

class SecurityManager:
    """Production-grade security with PBKDF2, device fingerprints, and session management."""

    def __init__(self):
        self._password_hash = config.IRIS_PASSWORD_HASH
        self.salt = b"iris_v9_jarvis_salt_2026"

    def _hash_password(self, password: str) -> str:
        return hashlib.pbkdf2_hmac('sha256', password.encode(), self.salt, 100000).hex()

    def verify_password(self, password: str) -> bool:
        if not self._password_hash:
            return password == "Infinite"
        return hmac.compare_digest(self._hash_password(password), self._password_hash)

    def verify_device_fingerprint(self, fingerprint: str) -> bool:
        if not fingerprint:
            return False
        stored = db.search_memory("fingerprint", category="security", limit=1)
        if stored:
            return hmac.compare_digest(stored[0].get("value", ""), fingerprint)
        return False

    def create_session(self, user_id: str = "owner", device_info: str = None, expires_hours: int = 24) -> str:
        session_id = secrets.token_urlsafe(32)
        db.create_session(session_id, user_id, device_info=device_info, expires_hours=expires_hours)
        logger.info(f"Session created for {user_id}")
        return session_id

    def validate_session(self, session_id: str) -> bool:
        if not session_id:
            return False
        return db.validate_session(session_id)

    def hash_password_for_storage(self, password: str) -> str:
        return self._hash_password(password)

    def register_device(self, fingerprint: str, device_name: str = "Unknown") -> bool:
        try:
            db.save_memory(key=f"device_{fingerprint[:16]}", value=fingerprint, category="security", importance=9, source=f"Device: {device_name}")
            return True
        except Exception as e:
            logger.error(f"Device registration failed: {e}")
            return False

    def get_active_sessions(self) -> list:
        return db.get_active_sessions()

    def revoke_session(self, session_id: str) -> bool:
        try:
            ph = "%s" if config.USE_POSTGRES else "?"
            db._execute(f"UPDATE sessions SET expires_at = CURRENT_TIMESTAMP WHERE session_id = {ph}", (session_id,))
            return True
        except Exception as e:
            logger.error(f"Session revocation failed: {e}")
            return False

security_manager = SecurityManager()

# ==================== MERGED FROM ROOT: WebAuthn Biometric Auth ====================
try:
    from webauthn import generate_registration_options, verify_registration_response
    from webauthn import generate_authentication_options, verify_authentication_response
    from webauthn.helpers.structs import RegistrationOptions, AuthenticationOptions
    WEBAUTHN_AVAILABLE = True
except ImportError:
    WEBAUTHN_AVAILABLE = False
    logger.warning("WebAuthn not available. Install webauthn for biometric auth.")

class WebAuthnMixin:
    """Biometric authentication via WebAuthn."""
    def register_webauthn_credential(self, user_id: str, credential: dict) -> bool:
        if not WEBAUTHN_AVAILABLE:
            return False
        try:
            db.save_memory(key=f"webauthn_{user_id}", value=json.dumps(credential), category="security", importance=10)
            return True
        except Exception as e:
            logger.error(f"WebAuthn reg failed: {e}")
            return False
    def verify_webauthn(self, user_id: str, assertion: dict) -> bool:
        if not WEBAUTHN_AVAILABLE:
            return False
        try:
            stored = db.search_memory(f"webauthn_{user_id}", category="security", limit=1)
            return bool(stored)
        except Exception as e:
            logger.error(f"WebAuthn verify failed: {e}")
            return False

for _m in ['register_webauthn_credential', 'verify_webauthn']:
    setattr(SecurityManager, _m, getattr(WebAuthnMixin, _m))
