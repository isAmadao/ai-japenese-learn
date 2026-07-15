"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (parent of backend/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
PROJECT_ROOT = BASE_DIR.parent  # project root (where .env lives)
dotenv_path = PROJECT_ROOT / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)
else:
    load_dotenv()  # fallback to CWD


class Settings:
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Database
    USE_SQLITE: bool = os.getenv("USE_SQLITE", "true").lower() == "true"
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", str(BASE_DIR / "data" / "app.db"))

    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "ai_japanese_learn")

    @property
    def DATABASE_URL(self) -> str:
        if self.USE_SQLITE:
            db_dir = os.path.dirname(self.SQLITE_PATH)
            os.makedirs(db_dir, exist_ok=True)
            return f"sqlite:///{self.SQLITE_PATH}"
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # Milvus
    MILVUS_HOST: str = os.getenv("MILVUS_HOST", "localhost")
    MILVUS_PORT: int = int(os.getenv("MILVUS_PORT", "19530"))

    # LLM (Qwen)
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_API_BASE: str = os.getenv("LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen-plus")
    LLM_EMBEDDING_MODEL: str = os.getenv("LLM_EMBEDDING_MODEL", "text-embedding-v3")

    # Auth — self-contained dev mode vs central auth-service
    # When AUTH_DISABLED=True, the backend creates a default admin user
    # and skips JWT verification so no external auth-service is needed.
    AUTH_DISABLED: bool = os.getenv("AUTH_DISABLED", "true").lower() == "true"

    # Auth service (central JWT issuer) — only used when AUTH_DISABLED=False
    AUTH_SERVICE_URL: str = os.getenv("AUTH_SERVICE_URL", "http://localhost:8080")
    # Fallback: explicit RSA public key PEM (used when AUTH_SERVICE_URL is empty)
    JWT_PUBLIC_KEY: str = os.getenv("JWT_PUBLIC_KEY", "")

    # Redis cache TTL (seconds)
    CACHE_TTL_WORDS: int = int(os.getenv("CACHE_TTL_WORDS", "3600"))
    CACHE_TTL_ARTICLE: int = int(os.getenv("CACHE_TTL_ARTICLE", "7200"))

    # External API keys (MCP-style integrations)
    PEXELS_API_KEY: str = os.getenv("PEXELS_API_KEY", "")


settings = Settings()
