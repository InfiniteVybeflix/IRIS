"""IRIS Auth — Google Sign-In + stateless session tokens.

HOW IT WORKS
  1. The frontend loads Google Identity Services (GIS) and renders the
     "Sign in with Google" button using the client id from
     GET /api/auth/config (a client id is PUBLIC by design — it is not a
     secret; Google's own docs require shipping it in the page).
  2. Google returns an ID token (JWT) to the browser, which POSTs it to
     /api/auth/google. The server VERIFIES the cryptographically (RS256
     against Google's published JWKS, plus iss / aud / exp checks) — the
     token is never trusted just because the client sent it.
  3. The user is upserted into the database (users table) — this is the
     "rest of the necessary data" that makes accounts portable: sign in
     from any device and your chats are there.
  4. The server issues its own HMAC-SHA256 signed session token. The
     browser stores it and sends it as `Authorization: Bearer <token>` on
     every API call. Tokens are stateless (no session table), expire after
     30 days, and are signed with IRIS_SESSION_SECRET.

ENVIRONMENT VARIABLES (all server-side, never exposed):
  GOOGLE_CLIENT_ID        — required for sign-in to be enabled
  IRIS_SESSION_SECRET     — required; HMAC key for session tokens
  ALLOWED_EMAIL_DOMAINS   — optional, comma-separated (e.g. "aevibron.com")
                            empty = any Google account may sign in
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.request
from functools import wraps
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

TOKEN_TTL_SECONDS = 30 * 24 * 3600  # 30 days
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"

# JWKS cache (fetched at most once per hour per cold instance)
_jwks_cache: Dict[str, Any] = {"keys": None, "fetched": 0.0}


# ─────────────────────────────────────────────────────────────────────────────
# Config helpers
# ─────────────────────────────────────────────────────────────────────────────
def _client_id() -> str:
    return (os.environ.get("GOOGLE_CLIENT_ID", "") or "").strip()


def _session_secret() -> str:
    return (os.environ.get("IRIS_SESSION_SECRET", "") or "").strip()


def _allowed_domains():
    raw = (os.environ.get("ALLOWED_EMAIL_DOMAINS", "") or "")
    return [d.strip().lower().lstrip("@") for d in raw.split(",") if d.strip()]


def sign_in_enabled() -> bool:
    """True when both GOOGLE_CLIENT_ID and IRIS_SESSION_SECRET are set."""
    return bool(_client_id() and _session_secret())


# ─────────────────────────────────────────────────────────────────────────────
# Session tokens (stateless, HMAC-SHA256, stdlib only)
# ─────────────────────────────────────────────────────────────────────────────
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def issue_token(user: Dict[str, Any]) -> str:
    payload = {
        "uid": user.get("user_id") or user.get("sub") or "",
        "email": user.get("email") or "",
        "name": user.get("name") or "",
        "picture": user.get("picture") or "",
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _b64url(hmac.new(_session_secret().encode("utf-8"),
                           body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Return the token payload if the signature is valid and unexpired."""
    if not token or "." not in token or not _session_secret():
        return None
    try:
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(_session_secret().encode("utf-8"),
                            body.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url_decode(sig), expected):
            return None
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def current_user() -> Optional[Dict[str, Any]]:
    """The signed-in user for THIS request (from the Authorization header),
    or None. Used by other blueprints to scope data per user."""
    header = request.headers.get("Authorization", "") or ""
    if header.lower().startswith("bearer "):
        payload = verify_token(header[7:].strip())
        if payload:
            return {"user_id": payload.get("uid"), "email": payload.get("email"),
                    "name": payload.get("name"), "picture": payload.get("picture")}
    return None


def require_auth(fn):
    """Route decorator: 401 with a clean JSON body when not signed in."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"success": False,
                            "error": "Sign in required.",
                            "auth_required": True}), 401
        return fn(user, *args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# Google ID token verification
# ─────────────────────────────────────────────────────────────────────────────
def _fetch_jwks() -> list:
    now = time.time()
    if _jwks_cache["keys"] is None or now - _jwks_cache["fetched"] > 3600:
        with urllib.request.urlopen(GOOGLE_JWKS_URL, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        _jwks_cache["keys"] = data.get("keys", [])
        _jwks_cache["fetched"] = now
    return _jwks_cache["keys"] or []


def _verify_google_token_local(credential: str) -> Dict[str, Any]:
    """Verify the JWT locally: RS256 signature against Google's JWKS +
    issuer + audience + expiry. Requires python-jose (in requirements)."""
    from jose import jwk as jose_jwk, jwt as jose_jwt

    header = jose_jwt.get_unverified_header(credential)
    if header.get("alg") != "RS256":
        raise ValueError("Unsupported token algorithm")
    kid = header.get("kid")
    key_data = next((k for k in _fetch_jwks() if k.get("kid") == kid), None)
    if key_data is None:
        # JWKS may have rotated — refetch once, hard-fail if still absent.
        _jwks_cache["keys"] = None
        key_data = next((k for k in _fetch_jwks() if k.get("kid") == kid), None)
    if key_data is None:
        raise ValueError("Signing key not found in Google's JWKS")

    key = jose_jwk.construct(key_data, algorithm="RS256")
    payload = jose_jwt.decode(
        credential, key, algorithms=["RS256"],
        audience=_client_id(),
        issuer=["accounts.google.com", "https://accounts.google.com"],
    )
    return payload


def _verify_google_token_remote(credential: str) -> Dict[str, Any]:
    """Fallback verification via Google's tokeninfo endpoint (Google itself
    validates the token). Used when python-jose is unavailable."""
    url = f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("aud") != _client_id():
        raise ValueError("Token audience mismatch")
    if payload.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise ValueError("Token issuer mismatch")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Token expired")
    return payload


def verify_google_credential(credential: str) -> Dict[str, Any]:
    """Verify a Google ID token and return the normalized profile.
    Raises ValueError with a safe message on any failure."""
    try:
        payload = _verify_google_token_local(credential)
    except ImportError:
        payload = _verify_google_token_remote(credential)

    if payload.get("email_verified") in ("false", False, None):
        raise ValueError("Google account email is not verified")
    email = (payload.get("email") or "").lower()
    if not email:
        raise ValueError("Token contains no email")

    domains = _allowed_domains()
    if domains:
        domain = email.rsplit("@", 1)[-1]
        if domain not in domains:
            raise ValueError("This account's domain is not allowed on this deployment")

    return {
        "sub": payload.get("sub") or "",
        "email": email,
        "name": payload.get("name") or email.split("@")[0],
        "picture": payload.get("picture") or "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Database helpers (users table — see core/db.py)
# ─────────────────────────────────────────────────────────────────────────────
def _upsert_user(profile: Dict[str, Any]) -> Dict[str, Any]:
    from core.db import db
    return db.upsert_user(profile)


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route("/config", methods=["GET"])
def auth_config():
    """What the frontend needs to render the sign-in screen.
    Reveals nothing beyond the public Google client id."""
    enabled = sign_in_enabled()
    out = {"sign_in_enabled": enabled,
           "google_enabled": enabled,
           "google_client_id": _client_id() if enabled else None}
    if not enabled:
        # Operator-facing hint (the person who sets env vars); safe for end
        # users too — names no secrets, no endpoints.
        out["reason"] = ("Sign-in is not configured on the server yet. Administrators: "
                         "set GOOGLE_CLIENT_ID and IRIS_SESSION_SECRET.")
    return jsonify(out)


@auth_bp.route("/google", methods=["POST"])
def google_sign_in():
    """Verify a Google ID token, upsert the user, issue a session token."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid request body"}), 400
    credential = (data.get("credential") or "").strip()
    if not credential:
        return jsonify({"success": False, "error": "Missing Google credential"}), 400
    if not sign_in_enabled():
        logger.error("[auth] sign-in attempted but server env is missing "
                     "GOOGLE_CLIENT_ID / IRIS_SESSION_SECRET")
        return jsonify({"success": False,
                        "error": "Sign-in is not configured on the server."}), 503

    try:
        profile = verify_google_credential(credential)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 401
    except Exception as e:
        logger.exception("[auth] Google token verification failed")
        return jsonify({"success": False,
                        "error": "Could not verify the Google sign-in. Try again."}), 401

    try:
        user = _upsert_user(profile)
    except Exception as e:
        logger.exception("[auth] user upsert failed")
        return jsonify({"success": False,
                        "error": f"Could not save your account: {e}"}), 500

    token = issue_token(user)
    return jsonify({"success": True, "token": token,
                    "user": {"user_id": user.get("user_id"),
                             "email": user.get("email"),
                             "name": user.get("name"),
                             "picture": user.get("picture")}})


@auth_bp.route("/me", methods=["GET"])
def me():
    user = current_user()
    if not user:
        return jsonify({"success": False, "signed_in": False}), 401
    return jsonify({"success": True, "signed_in": True, "user": user})


@auth_bp.route("/logout", methods=["POST"])
def logout():
    # Stateless tokens: the client discards the token. Nothing to revoke
    # server-side; the token simply expires.
    return jsonify({"success": True, "message": "Signed out"})
