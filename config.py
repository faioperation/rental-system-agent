import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_FALLBACK_MODEL: str = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")

    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

    APP_SECRET: str = os.getenv("APP_SECRET", "dev-secret")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"  # 384-dim, via fastembed
    EMBEDDING_DIM: int = 384

    MAX_HISTORY_MESSAGES: int = 12  # how many past turns to feed back as context


settings = Settings()
