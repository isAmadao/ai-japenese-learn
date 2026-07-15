"""Vector service — embedding generation + Milvus storage.

Strategies (tried in order):
  1. Local sentence-transformers model (offline, free, real semantics)
  2. DashScope embedding API (if API key is configured)
  3. Deterministic hash (always works, low semantic quality)
"""

import hashlib
import json
import logging
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.core.milvus_client import milvus_client, EMBEDDING_DIM

logger = logging.getLogger(__name__)


class VectorService:
    """Embedding generation + Milvus vector storage."""

    _LOCAL_MODEL: Optional[Any] = None

    # ── DashScope embedding API ──────────────────────────────

    DASHSCOPE_EMBEDDING_URL = (
        settings.LLM_API_BASE.rstrip("/") + "/embeddings"
    )
    EMBEDDING_TIMEOUT = 30

    def embed_via_api(self, text: str, api_key: Optional[str] = None) -> list[float] | None:
        """Call text-embedding-v3 via DashScope OpenAI-compatible endpoint.

        Returns None on any error — caller falls back to deterministic hash.
        """
        key = api_key or settings.LLM_API_KEY
        if not key:
            logger.warning("No API key available for embedding")
            return None
        try:
            with httpx.Client(timeout=self.EMBEDDING_TIMEOUT) as client:
                resp = client.post(
                    self.DASHSCOPE_EMBEDDING_URL,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.LLM_EMBEDDING_MODEL,
                        "input": text,
                        "dimensions": 1024,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                vector = data["data"][0]["embedding"]
                logger.debug(
                    f"DashScope embedding OK, dim={len(vector)}, "
                    f"tokens={data.get('usage', {}).get('total_tokens', '?')}"
                )
                return vector
        except httpx.TimeoutException:
            logger.warning("DashScope embedding timed out (30s)")
        except httpx.HTTPStatusError as e:
            logger.warning(f"DashScope embedding HTTP {e.response.status_code}: {e.response.text[:200]}")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.warning(f"DashScope embedding parse error: {e}")
        except Exception as e:
            logger.warning(f"DashScope embedding failed: {e}")
        return None

    # ── Local embedding (sentence-transformers / fastembed) ──

    @classmethod
    def warm_local_model(cls) -> bool:
        """Pre-load the local embedding model (call at startup).

        Tries ``sentence-transformers`` first (PyTorch, ~2GB), then
        ``fastembed`` (ONNX, ~300MB).  If neither is available the
        search gracefully degrades to BM25-only.
        """
        if cls._LOCAL_MODEL is not None:
            return True

        # 1. Try sentence-transformers (PyTorch — full quality)
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading local embedding model (sentence-transformers)...")
            cls._LOCAL_MODEL = SentenceTransformer(
                "paraphrase-multilingual-MiniLM-L12-v2",
            )
            logger.info("Local embedding model ready (sentence-transformers)")
            return True
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"sentence-transformers init failed: {e}")

        # 2. Try fastembed (ONNX — lightweight)
        try:
            from fastembed import TextEmbedding
            logger.info("Loading local embedding model (fastembed)...")
            cls._LOCAL_MODEL = TextEmbedding(
                model_name="jinaai/jina-embeddings-v3",
                max_length=128,
            )
            logger.info("Local embedding model ready (fastembed)")
            return True
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"fastembed init failed: {e}")

        logger.info("No local embedding model available — vector search disabled")
        return False

    def embed_local(self, text: str) -> list[float] | None:
        """Embed text using local model.

        Supports both sentence-transformers and fastembed.
        """
        try:
            if self._LOCAL_MODEL is None:
                self.warm_local_model()
            if self._LOCAL_MODEL is None:
                return None

            vec = self._LOCAL_MODEL.encode(text)
            if hasattr(vec, 'tolist'):
                return vec.tolist()
            if isinstance(vec, list):
                return vec
            return list(vec)
        except Exception as e:
            logger.warning(f"Local embedding failed: {e}")
            return None

    # ── Deterministic fallback ─────────────────────────────

    @staticmethod
    def make_deterministic_vector(text: str, dim: int = 1024) -> list[float]:
        """Generate a deterministic unit vector from text hash.

        Used as fallback when the external embedding API is unavailable.
        Produces the same vector for the same text (deterministic).
        """
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = []
        for i in range(dim):
            b = h[i % len(h)] ^ h[(i + 1) % len(h)] ^ h[(i * 7) % len(h)]
            vec.append((b - 127) / 128.0)
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    # ── Embed and store ─────────────────────────────────────

    def embed_and_store(
        self,
        collection_name: str,
        text: str,
        metadata: dict,
    ) -> bool:
        """Embed *text* and store the vector.

        Strategy (tried in order):
          1. Local sentence-transformers model (offline, free, real semantics)
          2. DashScope embedding API (if API key is configured)
          3. Deterministic hash (always works, low semantic quality)
        """
        vector: Optional[list[float]] = None

        # 1. Try local model
        if vector is None:
            vector = self.embed_local(text)
            if vector is not None:
                logger.debug("Using local model embedding")

        # 2. Try DashScope embedding API
        if vector is None:
            api_vector = self.embed_via_api(text)
            if api_vector is not None:
                vector = api_vector

        # 3. Fallback to deterministic hash
        if vector is None:
            vector = self.make_deterministic_vector(text, dim=EMBEDDING_DIM)
            logger.info("Using deterministic hash vector (fallback)")

        try:
            ok = milvus_client.insert(collection_name, vector, metadata)
            if not ok:
                logger.warning("Insert returned False (collection not ready?)")
            return ok
        except Exception as e:
            logger.warning(f"Failed to store vector: {e}")
            return False


vector_service = VectorService()
