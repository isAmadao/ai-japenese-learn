"""Milvus vector database — stores embeddings for words and articles.

Collections:
  - word_vectors: word embeddings for semantic similarity search
  - article_vectors: article embeddings for content-based retrieval
"""

import logging
from typing import Any, Optional

from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
from app.core.config import settings

logger = logging.getLogger(__name__)

# Embedding dimension for text-embedding-v3 (DashScope / Qwen)
EMBEDDING_DIM = 1024


class MilvusClient:
    """Milvus wrapper — creates collections on startup, provides insert/search."""

    def __init__(self):
        self.connected = False
        self.collections: dict[str, Collection] = {}

    # ── Connection ──────────────────────────────────────────

    def connect(self):
        try:
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT,
            )
            self.connected = True
            logger.info("Milvus connected")
        except Exception as e:
            logger.warning(f"Milvus connection failed (non-fatal): {e}")
            self.connected = False

    def disconnect(self):
        if self.connected:
            connections.disconnect("default")
            self.connected = False

    # ── Collection management ───────────────────────────────

    WORD_COLLECTION = "word_vectors"
    ARTICLE_COLLECTION = "article_vectors"

    def _word_schema(self) -> CollectionSchema:
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
            FieldSchema(name="word_id", dtype=DataType.INT64),
            FieldSchema(name="japanese", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="kana", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="chinese_meaning", dtype=DataType.VARCHAR, max_length=300),
        ]
        return CollectionSchema(fields, description="Japanese word vectors")

    def _article_schema(self) -> CollectionSchema:
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
            FieldSchema(name="article_id", dtype=DataType.INT64),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="level", dtype=DataType.VARCHAR, max_length=10),
        ]
        return CollectionSchema(fields, description="Article vectors")

    def setup_collections(self):
        """Ensure word and article collections exist."""
        if not self.connected:
            logger.info("Milvus not connected — skipping collection setup")
            return

        for name, schema, desc in [
            (self.WORD_COLLECTION, self._word_schema(), "words"),
            (self.ARTICLE_COLLECTION, self._article_schema(), "articles"),
        ]:
            if utility.has_collection(name):
                col = Collection(name)
                col.load()
                logger.info(f"  Milvus collection '{name}' ({desc}) loaded")
            else:
                col = Collection(name=name, schema=schema)
                # Create IVF_FLAT index for search
                index_params = {
                    "metric_type": "IP",  # inner product
                    "index_type": "IVF_FLAT",
                    "params": {"nlist": 128},
                }
                col.create_index(field_name="vector", index_params=index_params)
                col.load()
                logger.info(f"  Milvus collection '{name}' ({desc}) created")
            self.collections[name] = col

    # ── CRUD ────────────────────────────────────────────────

    def insert(self, collection_name: str, vector: list[float], metadata: dict) -> bool:
        """Insert a vector + metadata into the specified collection."""
        if collection_name not in self.collections:
            logger.warning(f"Collection '{collection_name}' not loaded")
            return False
        try:
            col = self.collections[collection_name]
            if collection_name == self.WORD_COLLECTION:
                data = [
                    [metadata.get("id", 0)],
                    [vector],
                    [metadata.get("word_id", 0)],
                    [metadata.get("japanese", "")],
                    [metadata.get("kana", "")],
                    [metadata.get("chinese_meaning", "")],
                ]
            elif collection_name == self.ARTICLE_COLLECTION:
                data = [
                    [metadata.get("id", 0)],
                    [vector],
                    [metadata.get("article_id", 0)],
                    [metadata.get("title", "")],
                    [metadata.get("level", "")],
                ]
            else:
                return False
            col.insert(data)
            col.flush()
            return True
        except Exception as e:
            logger.warning(f"Milvus insert failed: {e}")
            return False

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for similar vectors. Returns list of hit dicts."""
        if collection_name not in self.collections:
            return []
        try:
            col = self.collections[collection_name]
            col.load()
            results = col.search(
                data=[query_vector],
                anns_field="vector",
                param={"metric_type": "IP", "params": {"nprobe": 10}},
                limit=top_k,
                output_fields=["*"],
            )
            hits = []
            for hits_group in results:
                for hit in hits_group:
                    hits.append({
                        "id": hit.id,
                        "distance": hit.distance,
                        "entity": hit.entity.to_dict() if hasattr(hit, "entity") else {},
                    })
            return hits
        except Exception as e:
            logger.warning(f"Milvus search failed: {e}")
            return []

    def delete_by_id(self, collection_name: str, pk: int):
        """Delete a vector by primary key."""
        if collection_name not in self.collections:
            return
        try:
            col = self.collections[collection_name]
            col.delete(f"id in [{pk}]")
            col.flush()
        except Exception as e:
            logger.warning(f"Milvus delete failed: {e}")


milvus_client = MilvusClient()
