"""Import all dictionary words into Elasticsearch with local embeddings.

Usage::

    conda activate ai-japanese-learn
    cd backend
    python scripts/import_words_to_es.py

This creates the ``jp_words`` index in ES with:
  - Full-text fields: name, kana, translation (with appropriate analyzers)
  - Dense vector field: 384-dim embedding (via local sentence-transformers)

Import strategy (RAG-inspired):
  - Batch inserts via ES bulk API (500 per batch)
  - Refresh disabled during import, re-enabled at end
  - Local embedding model, no API calls
"""

import sys
import os
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from elasticsearch import Elasticsearch, helpers

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
logger = logging.getLogger("import_words_to_es")

# ── ES client ────────────────────────────────────────────
es = Elasticsearch(["http://localhost:9200"], request_timeout=60)

INDEX_NAME = "jp_words"


def main():
    # ── 1. Init local embedding model (load once) ────────
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    from sentence_transformers import SentenceTransformer
    logger.info("Loading local embedding model...")
    t0 = time.time()
    model = SentenceTransformer("jinaai/jina-embeddings-v3")
    logger.info(f"Model loaded in {time.time()-t0:.1f}s")

    # ── 2. Load all words from SQLite ────────────────────
    from app.core.database import SessionLocal
    from app.models.word import Word

    db = SessionLocal()
    words = db.query(Word).order_by(Word.id).all()
    db.close()
    logger.info(f"Loaded {len(words)} words from SQLite")

    # ── 3. Ensure index exists ───────────────────────────
    if not es.indices.exists(index=INDEX_NAME):
        logger.error("Index jp_words does not exist — create it first")
        return

    # Close refresh during bulk import (huge speedup)
    es.indices.put_settings(
        index=INDEX_NAME,
        body={"index": {"refresh_interval": "-1"}},
    )
    logger.info("Refresh disabled for bulk import")

    # ── 4. Embed + batch import ──────────────────────────
    BATCH_SIZE = 500
    batch = []
    total = len(words)
    t_start = time.time()

    for i, word in enumerate(words):
        text = f"{word.name} {word.kana} {word.translation}"
        vec = model.encode(text).tolist()

        action = {
            "_index": INDEX_NAME,
            "_id": word.id,
            "_source": {
                "name": word.name,
                "kana": word.kana,
                "translation": word.translation,
                "type": word.type or "",
                "description": word.description or "",
                "embedding": vec,
            },
        }
        batch.append(action)

        if len(batch) >= BATCH_SIZE or i == total - 1:
            success, errors = helpers.bulk(
                es, batch, chunk_size=BATCH_SIZE,
                raise_on_error=False,
                request_timeout=120,
            )
            batch = []

            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            logger.info(
                f"[{i+1}/{total}] {success} ok, {len(errors)} errors "
                f"({rate:.0f} docs/s, {elapsed:.1f}s)"
            )

    # ── 5. Re-enable refresh ─────────────────────────────
    es.indices.put_settings(
        index=INDEX_NAME,
        body={"index": {"refresh_interval": "30s"}},
    )
    es.indices.refresh(index=INDEX_NAME)

    total_time = time.time() - t_start
    logger.info(
        f"Done. {total} words indexed in {total_time:.1f}s "
        f"({total/total_time:.0f} docs/s)"
    )


if __name__ == "__main__":
    main()
