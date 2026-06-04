"""FastAPI application entry point for ai-japanese-learn backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.core.redis_client import redis_client
from app.core.milvus_client import milvus_client
from app.api import words, favorites, articles


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    init_db()
    print(f"✓ Database initialized ({'SQLite' if settings.USE_SQLITE else 'MySQL'})")

    # Try connecting Redis (non-fatal)
    try:
        await redis_client.connect()
        print("✓ Redis connected")
    except Exception as e:
        print(f"⚠ Redis unavailable: {e}")

    # Try starting Milvus Lite (non-fatal)
    try:
        milvus_client.setup()
    except Exception as e:
        print(f"⚠ Milvus Lite unavailable: {e}")

    yield

    # Shutdown
    await redis_client.disconnect()
    milvus_client.disconnect()


app = FastAPI(
    title="AI 日本語学習",
    description="AI-powered Japanese language learning assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server on common ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(words.router)
app.include_router(favorites.router)
app.include_router(articles.router)


@app.get("/")
def root():
    return {
        "app": "AI 日本語学習",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/api/health")
def health_check():
    return {"status": "ok", "llm_configured": bool(settings.LLM_API_KEY)}
