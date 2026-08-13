"""FastAPI application entry point for ai-japanese-learn backend.

When FRONTEND_DIST env var is set (Docker mode), serves the built
Vue frontend as static files.  Otherwise runs as API-only for development.
"""

import logging
import os
import traceback as _traceback
from contextlib import asynccontextmanager

# Show all app logs from INFO level
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings as core_settings
from app.core.database import init_db
from app.core.redis_client import redis_client
from app.core.milvus_client import milvus_client
from app.api import words, favorites, articles, learned, mastered, settings, tts, admin, image_search

logger = logging.getLogger(__name__)

FRONTEND_DIST = os.getenv("FRONTEND_DIST", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    init_db()
    print(f"✓ Database initialized ({'SQLite' if core_settings.USE_SQLITE else 'MySQL'})")

    try:
        await redis_client.connect()
        print("✓ Redis connected")
    except Exception as e:
        print(f"⚠ Redis unavailable: {e}")

    try:
        milvus_client.setup()
    except Exception as e:
        print(f"⚠ Milvus Lite unavailable: {e}")

    # Pre-load local embedding model in background (won't block startup)
    def _warm_model():
        try:
            from app.services.vector_service import vector_service
            if vector_service.warm_local_model():
                print("✓ Local embedding model loaded")
            else:
                print("⚠ Local embedding model unavailable — BM25 search only")
        except Exception as e:
            print(f"⚠ Local embedding model error: {e}")

    import threading
    threading.Thread(target=_warm_model, daemon=True).start()

    yield

    await redis_client.disconnect()
    milvus_client.disconnect()


app = FastAPI(
    title="AI 日本語学習",
    description="AI-powered Japanese language learning assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────
# In Docker / production mode (FRONTEND_DIST set), the frontend
# is served as static files from the same origin, so no CORS
# preflight is needed.  Allow all origins for flexibility.
# (allow_credentials must be False when allow_origins=["*"])
cors_origins = ["*"] if FRONTEND_DIST else [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]

# ── CORS ────────────────────────────────────────────────────
# Behind nginx (same origin), CORS is not triggered.
# In dev mode (Vite proxy), the Vite dev server handles it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False if FRONTEND_DIST else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth — handled by central auth-service via auth-client ──
# (login, register, CAPTCHA, email verification are at auth-service:8080)

app.include_router(admin.router)
app.include_router(words.router)
app.include_router(favorites.router)
app.include_router(articles.router)
app.include_router(learned.router)
app.include_router(mastered.router)
app.include_router(settings.router)
app.include_router(tts.router)
app.include_router(image_search.router)


# ── Global exception handler ──────────────────────────────────
# Catches all unhandled exceptions and returns a consistent
# Chinese error response.  HTTPException is passed through so
# each endpoint's custom status/message is preserved.

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Pass through — preserves per-endpoint custom status/detail."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return validation errors in Chinese."""
    errors = exc.errors()
    first = errors[0] if errors else {}
    msg = first.get("msg", "请求参数有误")
    return JSONResponse(status_code=422, content={"detail": f"参数错误: {msg}"})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all: return 500 with Chinese message."""
    logger.error(f"Unhandled exception: {exc}\n{''.join(_traceback.format_tb(exc.__traceback__))}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器内部错误: {str(exc)[:200]}"},
    )


@app.get("/api/health")
def health_check():
    return {"status": "ok", "llm_configured": bool(core_settings.LLM_API_KEY)}


# ── Docker mode: serve built frontend (SPA compatible) ────────
if FRONTEND_DIST and os.path.isdir(FRONTEND_DIST):

    class SPAStaticFiles(StaticFiles):
        """Serve Vue SPA — catch-all returns index.html for non-file routes."""

        async def get_response(self, path: str, scope):
            try:
                return await super().get_response(path, scope)
            except StarletteHTTPException as exc:
                if exc.status_code == 404:
                    # SPA fallback: serve index.html for unmatched routes
                    return await super().get_response("index.html", scope)
                raise

    app.mount("/", SPAStaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    print(f"✓ Serving frontend from {FRONTEND_DIST} (SPA mode)")
else:
    @app.get("/")
    def root():
        return {
            "app": "AI 日本語学習",
            "version": "1.0.0",
            "docs": "/docs",
        }
    print("⚠ FRONTEND_DIST not set; API-only mode")
