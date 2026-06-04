"""Milvus Lite — embedded vector database using pymilvus native local client.

Single file database stored at ./data/milvus.db (auto-created, no server needed).

Collections:
  word_vectors    — 1024-d word embeddings
  article_vectors — 1024-d article embeddings
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_MILVUS_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_MILVUS_FILE = str(_MILVUS_DIR / "milvus.db")
EMBEDDING_DIM = 1024

# Import Milvus Lite's local client (available after pip install milvus-lite)
_NATIVE_CLIENT = None
try:
    from pymilvus import MilvusClient as _NativeMilvusClient
    _NATIVE_CLIENT = _NativeMilvusClient
    logger.info("Milvus Lite native client available")
except ImportError:
    logger.warning("milvus-lite not installed — falling back to numpy vector store")


class MilvusClient:
    """Vector store — backed by Milvus Lite when available, else numpy/JSON fallback."""

    WORD_COLLECTION = "word_vectors"
    ARTICLE_COLLECTION = "article_vectors"

    def __init__(self):
        self._client: Any = None
        self._fallback_data: dict[str, list[dict]] = {}
        self.connected = False
        self.collections: dict[str, bool] = {}
        self._using_fallback = _NATIVE_CLIENT is None

    # ── Lifecycle ──────────────────────────────────────────

    def setup(self):
        os.makedirs(str(_MILVUS_DIR), exist_ok=True)

        if _NATIVE_CLIENT is not None:
            self._setup_milvus_lite()
        else:
            self._setup_fallback()

    def _setup_milvus_lite(self):
        """Initialize Milvus Lite local database."""
        try:
            self._client = _NATIVE_CLIENT(_MILVUS_FILE)  # type: ignore
            self.connected = True
            self._using_fallback = False
            logger.info(f"✓ Milvus Lite ready ({_MILVUS_FILE})")
        except Exception as e:
            logger.warning(f"Milvus Lite init failed: {e} — using fallback")
            self._setup_fallback()
            return

        for name, dim in [
            (self.WORD_COLLECTION, EMBEDDING_DIM),
            (self.ARTICLE_COLLECTION, EMBEDDING_DIM),
        ]:
            try:
                if not self._client.has_collection(name):
                    self._client.create_collection(
                        collection_name=name,
                        dimension=dim,
                        auto_id=False,
                        metric_type="IP",
                    )
                    logger.info(f"  Collection '{name}' created (dim={dim})")
                else:
                    logger.info(f"  Collection '{name}' loaded")
                self.collections[name] = True
            except Exception as e:
                logger.warning(f"  Collection '{name}' setup failed: {e}")

    def _setup_fallback(self):
        """Fallback numpy/JSON store when Milvus Lite unavailable."""
        _fallback_file = str(_MILVUS_DIR / "vectors_fallback.json")
        try:
            import json
            if os.path.exists(_fallback_file):
                with open(_fallback_file, "r", encoding="utf-8") as f:
                    self._fallback_data = json.load(f)
            else:
                self._fallback_data = {}
            for name in [self.WORD_COLLECTION, self.ARTICLE_COLLECTION]:
                if name not in self._fallback_data:
                    self._fallback_data[name] = []
                self.collections[name] = True
            self._save_fallback(_fallback_file)
            self.connected = True
            self._using_fallback = True
            logger.info(f"✓ Numpy fallback store ready ({_fallback_file})")
        except Exception as e:
            logger.warning(f"Fallback store init failed: {e}")

    def _save_fallback(self, path=None):
        if not self._using_fallback:
            return
        import json
        try:
            with open(path or str(_MILVUS_DIR / "vectors_fallback.json"), "w", encoding="utf-8") as f:
                json.dump(self._fallback_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Fallback save failed: {e}")

    def disconnect(self):
        if self._client and not self._using_fallback:
            self._client.close()
            logger.info("Milvus Lite closed")
        elif self._using_fallback:
            self._save_fallback()
        self._client = None
        self.connected = False

    # ── CRUD ───────────────────────────────────────────────

    def insert(self, collection_name: str, vector: list[float], metadata: dict) -> bool:
        """Insert vector + metadata into the collection."""
        if collection_name not in self.collections:
            return False
        try:
            data = {**metadata, "vector": vector}
            if self._using_fallback:
                self._fallback_data[collection_name].append(data)
                self._save_fallback()
            else:
                self._client.insert(collection_name, data)
            return True
        except Exception as e:
            logger.warning(f"Vector insert failed: {e}")
            return False

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for similar vectors via cosine similarity."""
        if collection_name not in self.collections:
            return []
        try:
            if self._using_fallback:
                return self._fallback_search(collection_name, query_vector, top_k)
            results = self._client.search(
                collection_name=collection_name,
                data=[query_vector],
                limit=top_k,
                output_fields=["*"],
            )
            hits = []
            if results:
                for hit in results[0]:
                    hits.append({
                        "id": hit.get("id"),
                        "distance": hit.get("distance"),
                        "entity": hit.get("entity", {}),
                    })
            return hits
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

    def _fallback_search(self, collection_name, query_vector, top_k):
        import numpy as np
        items = self._fallback_data.get(collection_name, [])
        q = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []
        q = q / q_norm
        scored = []
        for item in items:
            v = np.array(item.get("vector", []), dtype=np.float32)
            v_norm = np.linalg.norm(v)
            if v_norm == 0:
                continue
            similarity = float(np.dot(q, v / v_norm))
            scored.append((similarity, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"id": item.get("id"), "distance": score,
             "entity": {k: v for k, v in item.items() if k != "vector"}}
            for score, item in scored[:top_k]
        ]

    def delete_by_entity_id(self, collection_name: str, entity_id: int):
        """Delete vector(s) where 'id' matches."""
        if collection_name not in self.collections:
            return
        try:
            if self._using_fallback:
                items = self._fallback_data.get(collection_name, [])
                self._fallback_data[collection_name] = [
                    i for i in items if i.get("id") != entity_id
                ]
                self._save_fallback()
            else:
                self._client.delete(collection_name, f"id in [{entity_id}]")
        except Exception as e:
            logger.warning(f"Vector delete failed: {e}")


milvus_client = MilvusClient()
