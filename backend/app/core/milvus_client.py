"""Local vector store — numpy-based, file-persisted, no external service needed.

API mirrors pymilvus so the rest of the app is insulated.
Swap for real Milvus/Chroma later by replacing just this module.

Data stored as JSON in ./data/vectors.json (human-readable, easy to debug).
For < 10K vectors brute-force cosine similarity is perfectly adequate.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

_VECTOR_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_VECTOR_FILE = str(_VECTOR_DIR / "vectors.json")
EMBEDDING_DIM = 1024


class MilvusClient:
    """Lightweight local vector store (stand-in for real Milvus).

    Collections are stored as in-memory lists and persisted to JSON.
    Search uses brute-force cosine similarity.
    """

    WORD_COLLECTION = "word_vectors"
    ARTICLE_COLLECTION = "article_vectors"

    def __init__(self):
        self._data: dict[str, list[dict]] = {}
        self.connected = False
        self.collections: dict[str, bool] = {}

    # ── Lifecycle ──────────────────────────────────────────

    def setup(self):
        """Load persisted vectors from disk (or start fresh)."""
        os.makedirs(str(_VECTOR_DIR), exist_ok=True)
        try:
            if os.path.exists(_VECTOR_FILE):
                with open(_VECTOR_FILE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.info(f"✓ Vector store loaded ({_VECTOR_FILE})")
            else:
                self._data = {}
                self._save()
                logger.info(f"✓ Vector store created ({_VECTOR_FILE})")
            self.connected = True
            # Register known collections
            for name in [self.WORD_COLLECTION, self.ARTICLE_COLLECTION]:
                if name not in self._data:
                    self._data[name] = []
                self.collections[name] = True
            self._save()
        except Exception as e:
            logger.warning(f"⚠ Vector store init failed: {e}")
            self.connected = False

    def disconnect(self):
        self._save()
        logger.info("Vector store saved & closed")

    def _save(self):
        try:
            with open(_VECTOR_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Vector store save failed: {e}")

    # ── CRUD ───────────────────────────────────────────────

    def insert(self, collection_name: str, vector: list[float], metadata: dict) -> bool:
        """Append a vector + metadata entry."""
        if collection_name not in self.collections:
            logger.warning(f"Unknown collection '{collection_name}'")
            return False
        try:
            entry = {
                "id": metadata.get("id", 0),
                "vector": vector,
                **{k: v for k, v in metadata.items() if k != "vector"},
            }
            self._data.setdefault(collection_name, []).append(entry)
            self._save()
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
        """Brute-force cosine similarity search."""
        if collection_name not in self.collections:
            return []

        items = self._data.get(collection_name, [])
        if not items:
            return []

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
        top = scored[:top_k]

        return [
            {
                "id": item["id"],
                "distance": score,
                "entity": {k: v for k, v in item.items() if k != "vector"},
            }
            for score, item in top
        ]

    def delete_by_entity_id(self, collection_name: str, entity_id: int):
        """Remove entry where 'id' matches."""
        if collection_name not in self.collections:
            return
        items = self._data.get(collection_name, [])
        self._data[collection_name] = [i for i in items if i.get("id") != entity_id]
        self._save()


milvus_client = MilvusClient()
