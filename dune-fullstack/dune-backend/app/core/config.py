import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pydantic import BaseModel

class Settings(BaseModel):
    PROJECT_NAME: str = "DUNE AI Assistant"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dune-super-secret-jwt-key-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "dune_ai")

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:8000")
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/connections/oauth/callback")

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

settings = Settings()

