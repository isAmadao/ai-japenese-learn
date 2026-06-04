"""Milvus vector database client — for future semantic search of words/articles.

Placeholder for v1. Will be used for:
- Word embedding storage & similarity search
- Article semantic retrieval
- RAG-based learning features
"""

import logging
from typing import Optional

from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType
from app.core.config import settings

logger = logging.getLogger(__name__)


class MilvusClient:
    """Milvus vector store wrapper (singleton pattern)."""

    def __init__(self):
        self.connected = False
        self.collections: dict[str, Collection] = {}

    def connect(self):
        """Connect to Milvus server."""
        try:
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT,
            )
            self.connected = True
            logger.info("Milvus connected successfully")
        except Exception as e:
            logger.warning(f"Milvus connection failed (non-fatal for v1): {e}")
            self.connected = False

    def disconnect(self):
        if self.connected:
            connections.disconnect("default")
            self.connected = False

    def create_collection(self, name: str, schema: CollectionSchema):
        if self.connected:
            col = Collection(name=name, schema=schema)
            self.collections[name] = col
            return col
        return None


milvus_client = MilvusClient()
