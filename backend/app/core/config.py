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
    SECRET_KEY: str = "your-secret-key-here"  # Change in production
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    DATABASE_URL: str = "sqlite:///./novamind.db"
    REDIS_URL: str = "redis://redis:6379"
    CHROMA_HOST: str = "chroma"
    CHROMA_PORT: int = 8000
    # Google OAuth
    GOOGLE_CLIENT_ID: str = "your-google-client-id"
    GOOGLE_CLIENT_SECRET: str = "your-google-client-secret"
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    class Config:
        case_sensitive = True

settings = Settings()