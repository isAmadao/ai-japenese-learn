"""Milvus Lite — embedded vector database using pymilvus native local client.

Single file database stored at ./data/milvus.db (auto-created, no server needed).

Collections:
  word_vectors    — 1024-d word embeddings
  article_vectors — 1024-d article embeddings
"""

import atexit
import logging
import os
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Fix "too_many_pings" and "Invalid HTTP request" warnings ──
# pymilvus default gRPC keepalive interval is 10ms (!), which causes
# the embedded Milvus Lite server to send GOAWAY.  After the GOAWAY,
# broken connections generate traffic that uvicorn logs as "Invalid
# HTTP request received".  Set a sane interval to avoid this.
os.environ.setdefault("GRPC_ARG_KEEPALIVE_TIME_MS", "300000")            # 5 min
os.environ.setdefault("GRPC_ARG_HTTP2_MIN_SENT_PING_INTERVAL_WITHOUT_DATA_MS", "300000")
os.environ.setdefault("GRPC_ARG_KEEPALIVE_TIMEOUT_MS", "20000")          # 20 sec
os.environ.setdefault("GRPC_ARG_HTTP2_MAX_PINGS_WITHOUT_DATA", "0")      # no limit

_MILVUS_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_MILVUS_FILE = str(_MILVUS_DIR / "milvus.db")
EMBEDDING_DIM = 384

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
    SENTENCE_COLLECTION = "sentence_vectors"
    CLIP_IMAGE_COLLECTION = "clip_image_vectors"   # 512-dim CLIP image embeddings

    def __init__(self):
        self._client: Any = None
        self._fallback_data: dict[str, list[dict]] = {}
        self.connected = False
        self.collections: dict[str, bool] = {}
        self._using_fallback = _NATIVE_CLIENT is None
        self._atexit_registered = False

    # ── Lifecycle ──────────────────────────────────────────

    def setup(self):
        os.makedirs(str(_MILVUS_DIR), exist_ok=True)

        if _NATIVE_CLIENT is not None:
            self._setup_milvus_lite()
        else:
            self._setup_fallback()

        # Register atexit cleanup once (guarantees disconnect on crash/exit)
        if not self._atexit_registered:
            atexit.register(self.disconnect)
            self._atexit_registered = True

    def _setup_milvus_lite(self):
        """Initialize Milvus Lite local database.

        Cleans up stale LOCK file first (left behind after process crashes).
        """
        # ── Clear stale LOCK file ────────────────────────
        # When the Python process exits (normally or by crash), the OS
        # releases the file lock automatically.  But the LOCK file itself
        # remains on disk, and Milvus Lite may refuse to start if it sees
        # one.  Delete it before init to avoid manual cleanup.
        lock_file = _MILVUS_DIR / "milvus.db" / "LOCK"
        if lock_file.exists():
            try:
                lock_file.unlink()
                logger.info("Cleared stale Milvus Lite LOCK file")
            except OSError as e:
                logger.warning(f"Could not remove stale lock: {e}")

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
            (self.SENTENCE_COLLECTION, EMBEDDING_DIM),
            (self.CLIP_IMAGE_COLLECTION, 512),
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
                self._client.load_collection(name)
                self.collections[name] = True
            except Exception as e:
                # Milvus Lite bug: stale collection dirs from a previous run
                # cause FileExistsError even when has_collection returns False.
                err_msg = str(e)
                if '文件已存在' in err_msg or 'File exists' in err_msg:
                    col_dir = _MILVUS_DIR / "milvus.db" / "collections" / name
                    if col_dir.exists():
                        import shutil
                        try:
                            shutil.rmtree(str(col_dir))
                            logger.info(f"  Removed stale dir '{name}', retrying...")
                            self._client.create_collection(
                                collection_name=name,
                                dimension=dim,
                                auto_id=False,
                                metric_type="IP",
                            )
                            logger.info(f"  Collection '{name}' created after cleanup")
                            self._client.load_collection(name)
                            self.collections[name] = True
                            continue
                        except Exception as e2:
                            logger.warning(f"  Collection '{name}' retry failed: {e2}")
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
            for name in [self.WORD_COLLECTION, self.ARTICLE_COLLECTION, self.CLIP_IMAGE_COLLECTION]:
                if name not in self._fallback_data:
                    self._fallback_data[name] = []
                self.collections[name] = True
            self.connected = True
            self._using_fallback = True
            self._save_fallback(_fallback_file)
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
        """Insert vector + metadata into the collection.

        Falls back to numpy/JSON store if Milvus Lite insert fails
        (dynamic degradation, not just at startup).
        """
        if collection_name not in self.collections:
            return False
        data = {**metadata, "vector": vector}
        try:
            if self._using_fallback:
                self._fallback_data[collection_name].append(data)
                self._save_fallback()
                return True
            self._client.insert(collection_name, data)
            return True
        except Exception as e:
            logger.warning(f"Milvus insert failed, falling back: {e}")
            # Dynamic fallback — store in numpy/JSON instead
            self._using_fallback = True
            self._fallback_data.setdefault(collection_name, []).append(data)
            self._save_fallback()
            return True

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

    def get(self, collection_name: str, entity_id: int) -> Optional[dict[str, Any]]:
        """Retrieve a vector record by its 'id' field.

        Returns the record dict (including 'vector') if found, None otherwise.
        Supports both Milvus Lite and fallback modes.
        """
        if collection_name not in self.collections:
            return None
        try:
            if self._using_fallback:
                for item in self._fallback_data.get(collection_name, []):
                    if item.get("id") == entity_id:
                        return item
                return None
            # Milvus Lite: query by id
            result = self._client.query(
                collection_name,
                filter=f"id in [{entity_id}]",
            )
            if result:
                return result[0]
            return None
        except Exception as e:
            logger.warning(f"Vector get failed: {e}")
            return None

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
