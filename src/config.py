"""Application configuration, read from environment variables (.env)."""
import logging
import os
import secrets

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _list(name: str, default: str = "") -> list[str]:
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


def _secret_key() -> str:
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    log.warning(
        "SECRET_KEY is not set. Using a random key: sessions (and chat history "
        "ownership) will reset on every restart. Set SECRET_KEY in .env."
    )
    return secrets.token_hex(32)


class Config:
    # --- Core -------------------------------------------------------------
    SECRET_KEY = _secret_key()
    DEBUG = _bool("FLASK_DEBUG", False)
    HOST = os.environ.get("HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORT", "8080"))
    THREADS = int(os.environ.get("THREADS", "8"))
    SITE_NAME = "MediBot"

    # --- Database ---------------------------------------------------------
    # SQLite by default; set DATABASE_URL (e.g. postgresql+psycopg://...) to scale out.
    # On Vercel the project folder is read-only, so the fallback SQLite file goes to /tmp
    # (temporary: it is wiped between cold starts, so use a hosted DATABASE_URL there).
    DATABASE_URL = os.environ.get(
        "DATABASE_URL",
        "sqlite:////tmp/chat.db" if os.environ.get("VERCEL")
        else "sqlite:///" + os.path.join(BASE_DIR, "instance", "chat.db").replace("\\", "/"),
    )

    # --- Session cookie hardening ------------------------------------------
    SESSION_COOKIE_NAME = "medibot_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)  # true behind HTTPS
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 30  # 30 days
    TRUSTED_PROXIES = int(os.environ.get("TRUSTED_PROXIES", "0"))

    # --- Accounts ---------------------------------------------------------
    ADMIN_EMAILS = [e.lower() for e in _list("ADMIN_EMAILS")]
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    # Public base URL used for OAuth redirects, e.g. https://medibot.example.com
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

    # --- Request limits ---------------------------------------------------
    MAX_CONTENT_LENGTH = 16 * 1024          # JSON requests
    MAX_UPLOAD_BYTES = 5 * 1024 * 1024      # lab report uploads
    MAX_MESSAGE_CHARS = int(os.environ.get("MAX_MESSAGE_CHARS", "1000"))
    MAX_CONVERSATIONS_PER_USER = int(os.environ.get("MAX_CONVERSATIONS_PER_USER", "200"))
    HISTORY_TURNS_FOR_CONTEXT = int(os.environ.get("HISTORY_TURNS_FOR_CONTEXT", "6"))

    # --- Rate limiting (Flask-Limiter) -------------------------------------
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "600 per hour")
    RATELIMIT_CHAT = os.environ.get("RATELIMIT_CHAT", "10 per minute;100 per day")
    RATELIMIT_UPLOAD = os.environ.get("RATELIMIT_UPLOAD", "3 per minute;20 per day")
    RATELIMIT_AUTH = os.environ.get("RATELIMIT_AUTH", "10 per minute;50 per hour")
    RATELIMIT_HEADERS_ENABLED = True

    # --- AI / retrieval ---------------------------------------------------
    PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    PINECONE_INDEX = os.environ.get("PINECONE_INDEX", "medical-chatbot-v2")
    EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
    # Cheaper model for rewriting follow-up questions into stand-alone search queries.
    REWRITE_MODEL = os.environ.get("REWRITE_MODEL", "gpt-4o-mini")
    RETRIEVER_K = int(os.environ.get("RETRIEVER_K", "4"))
    # Hybrid search: blend keyword (BM25) results with vector results when chunks.jsonl exists.
    HYBRID_SEARCH = _bool("HYBRID_SEARCH", True)
    CHUNKS_FILE = os.path.join(BASE_DIR, "instance", "chunks.jsonl")
    # Run the OpenAI moderation check on user input.
    MODERATION_ENABLED = _bool("MODERATION_ENABLED", True)
    # Cache answers to first questions of a chat (no history) for this many hours (0 = off).
    ANSWER_CACHE_HOURS = int(os.environ.get("ANSWER_CACHE_HOURS", "168"))
    # USD per 1M tokens, used for the estimated-cost card in the admin dashboard.
    PRICE_INPUT_PER_M = float(os.environ.get("PRICE_INPUT_PER_M", "2.50"))
    PRICE_OUTPUT_PER_M = float(os.environ.get("PRICE_OUTPUT_PER_M", "10.00"))

    # --- Safety -----------------------------------------------------------
    # Shown in the emergency banner. Format: "Label:number,Label:number"
    EMERGENCY_NUMBERS = [
        tuple(item.split(":", 1))
        for item in _list(
            "EMERGENCY_NUMBERS",
            "Rescue (Pakistan):1122,Edhi Ambulance:115,Umang mental-health helpline:0311-7786264,International:112",
        )
        if ":" in item
    ]

    # --- Monitoring -------------------------------------------------------
    SENTRY_DSN = os.environ.get("SENTRY_DSN")
