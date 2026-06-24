try:
    # Try to import from pydantic-settings (newer versions)
    from pydantic_settings import BaseSettings
except ImportError:
    # Fall back to pydantic (older versions)
    from pydantic import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "NovaMind AI"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    # SECURITY: override this in production via the SECRET_KEY env var.
    SECRET_KEY: str = "dev-only-change-me-in-production-9f8e7d6c5b4a3210"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    # SQLite is the default for free-tier single-user deployments.
    # Switch to a postgresql:// URL when you have Postgres available.
    DATABASE_URL: str = "sqlite:///./novamind.db"
    # Redis URL — the app falls back to an in-memory shim if unreachable.
    # Set REDIS_REQUIRED=1 to fail fast instead.
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_REQUIRED: bool = False
    # ChromaDB (long-term vector memory) — optional; memory.py handles absence.
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    # Google OAuth (optional — auth still works without these)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    class Config:
        case_sensitive = True

settings = Settings()