"""IRIS v1 Configuration — Infinite Reactive Intelligence System
Jarvis Edition: Vercel-ready, Postgres-backed, Proactive AI
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ─── Aevibron Gateway ───
    # Primary: the custom domain. The vercel.app mirror is used as an
    # automatic fallback in core/llm_router.py when the primary is unreachable.
    AEVIBRON_BASE_URL = os.getenv("AEVIBRON_BASE_URL", "https://aevibron-gateway.veecel.app/api/v1")
    AEVIBRON_FALLBACK_URL = os.getenv("AEVIBRON_FALLBACK_URL", "https://aevibron-gateway.vercel.app/api/v1")
    AEVIBRON_API_KEY = os.getenv("AEVIBRON_API_KEY", "")
    AEVIBRON_ACCESS_TOKEN = os.getenv("AEVIBRON_ACCESS_TOKEN", "")

    # ─── GitHub / Vercel ───
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")
    VERCEL_TOKEN = os.getenv("VERCEL_TOKEN", "")
    VERCEL_TEAM_ID = os.getenv("VERCEL_TEAM_ID", "")

    # ─── Security ───
    IRIS_PASSWORD_HASH = os.getenv("IRIS_PASSWORD_HASH", "")
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "iris-v9-jarvis-secret-change-me")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # ─── Database ───
    # DATABASE_URL: set this to your Supabase/PostgreSQL URL for cloud (Vercel).
    # Leave empty for local SQLite (uses /tmp/iris.db on serverless, data/iris_v9.db locally).
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    # Use Postgres ONLY if DATABASE_URL is explicitly set AND starts with postgres
    USE_POSTGRES = bool(DATABASE_URL) and DATABASE_URL.lower().startswith("postgres")
    # SQLite path: /tmp/ is writable on Vercel serverless; data/ for local dev
    LOCAL_DB_PATH = os.getenv("LOCAL_DB_PATH", "/tmp/iris.db" if not USE_POSTGRES else "")

    # ─── Redis ───
    REDIS_URL = os.getenv("REDIS_URL", os.getenv("SWARM_REDIS_URL", ""))
    SWARM_ENABLED = os.getenv("SWARM_ENABLED", "False").lower() == "true"

    # ─── Voice & Audio ───
    EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "en-US-AriaNeural")
    WAKE_WORD = os.getenv("WAKE_WORD", "hey iris")
    WAKE_WORD_SENSITIVITY = float(os.getenv("WAKE_WORD_SENSITIVITY", "0.7"))
    VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "")

    # ─── Email ───
    IRIS_EMAIL_SENDER = os.getenv("IRIS_EMAIL_SENDER", "")
    IRIS_EMAIL_APP_PASSWORD = os.getenv("IRIS_EMAIL_APP_PASSWORD", "")
    IRIS_EMAIL_RECIPIENT = os.getenv("IRIS_EMAIL_RECIPIENT", "")
    IRIS_RESEND_API_KEY = os.getenv("IRIS_RESEND_API_KEY", "")

    # ─── News / Sports / Images ───
    IRIS_FREENEWS_API_KEY = os.getenv("IRIS_FREENEWS_API_KEY", "")
    IRIS_APISPORTS_KEY = os.getenv("IRIS_APISPORTS_KEY", "")
    IRIS_ODDS_API_KEY = os.getenv("IRIS_ODDS_API_KEY", "")
    IRIS_REMOVEBG_API_KEY = os.getenv("IRIS_REMOVEBG_API_KEY", "")
    IRIS_VOICERSS_API_KEY = os.getenv("IRIS_VOICERSS_API_KEY", "")

    # ─── Paths ───
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    _IS_VERCEL = os.environ.get("VERCEL") is not None

    # PROPER ARCHITECTURE:
    # - Persistent data → PostgreSQL (Supabase) when DATABASE_URL is set
    # - Temp files (voice, sandbox, backups) → /tmp/ on serverless, data/ locally
    # - DATA_DIR is ONLY used for local dev (SQLite + JSON files)
    # - On Vercel: persistent goes to PostgreSQL, temp goes to TMP_DIR
    DATA_DIR = "/tmp/iris-data" if _IS_VERCEL else os.path.join(BASE_DIR, "data")
    TMP_DIR = "/tmp/iris-temp" if _IS_VERCEL else os.path.join(BASE_DIR, "data", "temp")
    UPLOADS_DIR = os.path.join(TMP_DIR, "uploads")
    LEARNINGS_DIR = os.path.join(DATA_DIR, "iris_learnings")
    KNOWLEDGE_DIR = os.path.join(DATA_DIR, "iris_knowledge")
    SELF_DIR = os.path.join(DATA_DIR, "iris_self")
    VECTOR_DIR = os.path.join(DATA_DIR, "vector_db")
    BACKUPS_DIR = os.path.join(TMP_DIR, "backups")
    SANDBOX_DIR = os.path.join(TMP_DIR, "sandbox")
    CALENDAR_DIR = os.path.join(DATA_DIR, "calendar")
    NOTES_DIR = os.path.join(DATA_DIR, "notes")
    PROJECTS_DIR = os.path.join(TMP_DIR, "projects")
    AUDIO_DIR = os.path.join(TMP_DIR, "audio")
    SCREENSHOTS_DIR = os.path.join(TMP_DIR, "screenshots")

    # ─── Agent Limits ───
    MAX_TOOL_ITERATIONS = int(os.getenv("MAX_TOOL_ITERATIONS", "25"))
    MAX_RECOVERY_ATTEMPTS = int(os.getenv("MAX_RECOVERY_ATTEMPTS", "3"))
    MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", "50"))

    # ─── Aevibron Text Models ───
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "Aevibron Core")
    FAST_MODEL = os.getenv("FAST_MODEL", "Aevibron Flash")
    DEEP_MODEL = os.getenv("DEEP_MODEL", "Aevibron Prime")
    LIGHTNING_MODEL = os.getenv("LIGHTNING_MODEL", "Aevibron Swift")
    VISION_MODEL = os.getenv("VISION_MODEL", "Aevibron Vision")
    SPEECH_MODEL = os.getenv("SPEECH_MODEL", "Aevibron Speech")
    AUDIO_MODEL = os.getenv("AUDIO_MODEL", "Aevibron Audio")
    MULTILINGUAL_MODEL = os.getenv("MULTILINGUAL_MODEL", "Aevibron Quantum")
    AGENTIC_MODEL = os.getenv("AGENTIC_MODEL", "Aevibron Compound")
    OSS_MODEL = os.getenv("OSS_MODEL", "Aevibron OSS")

    # ─── Aevibron Image Models ───
    IMAGINE_V1_MODEL = os.getenv("IMAGINE_V1_MODEL", "Aevibron Imagine V1")
    IMAGINE_FLASH_MODEL = os.getenv("IMAGINE_FLASH_MODEL", "Aevibron Imagine Flash")

    # ─── Jarvis-Level Proactive Features ───
    PROACTIVE_MODE = os.getenv("PROACTIVE_MODE", "True").lower() == "true"
    PROACTIVE_CHECK_INTERVAL = int(os.getenv("PROACTIVE_CHECK_INTERVAL", "300"))
    CONTEXT_AWARENESS = os.getenv("CONTEXT_AWARENESS", "True").lower() == "true"
    CONTINUOUS_LEARNING = os.getenv("CONTINUOUS_LEARNING", "True").lower() == "true"
    EMOTIONAL_INTELLIGENCE = os.getenv("EMOTIONAL_INTELLIGENCE", "True").lower() == "true"

    # ─── Owner ───
    OWNER_NAME = os.getenv("OWNER_NAME", "Infinite Vybeflix")
    OWNER_ALIAS = os.getenv("OWNER_ALIAS", "Infinite")
    OWNER_EMAIL = os.getenv("OWNER_EMAIL", "aevibron@gmail.com")

    # ─── Phone Bridge ───
    # Enabled by default: the bridge only ever works when the adb binary
    # exists on the host AND a device is attached, so there is nothing to
    # "enable" ahead of time. Set PHONE_BRIDGE_ENABLED=false to hard-disable.
    PHONE_BRIDGE_ENABLED = os.getenv("PHONE_BRIDGE_ENABLED", "True").lower() == "true"
    ADB_DEVICE_ID = os.getenv("ADB_DEVICE_ID", "")

    # ─── Rate Limiting ───
    RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
    RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

    # ─── Logging ───
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_TO_FILE = os.getenv("LOG_TO_FILE", "True").lower() == "true"

config = Config()
