"""Batch-embed all dictionary words into Milvus.

Usage::

    conda activate ai-japanese-learn
    cd backend
    python scripts/embed_all_words.py
    python scripts/embed_all_words.py --api-key "sk-..."   # with your DashScope key

Without ``--api-key``, uses deterministic hash vectors (low semantic
quality but structure still works).
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from app.core.database import SessionLocal, init_db
from app.models.word import Word
from app.agent.word_agent import word_agent

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("embed_all_words")


def main():
    parser = argparse.ArgumentParser(description="Batch-embed all words into Milvus")
    parser.add_argument("--api-key", help="DashScope API key for real embeddings")
    args = parser.parse_args()

    # Inject API key into environment so the embedding client picks it up
    if args.api_key:
        os.environ["LLM_API_KEY"] = args.api_key
        logger.info("Using provided DashScope API key for real embeddings")
    else:
        # Clear any key from .env so _embed_via_api skips the API call entirely
        os.environ.pop("LLM_API_KEY", None)
        logger.info("No API key — using deterministic hash vectors (fast, local)")

    # Ensure Milvus is initialized before embedding
    from app.core.milvus_client import milvus_client
    milvus_client.setup()
    logger.info(f"Milvus ready (connected={milvus_client.connected})")

    init_db()
    db = SessionLocal()

    try:
        total = db.query(Word).count()
        logger.info(f"Total words in DB: {total}")

        words = db.query(Word).order_by(Word.id).all()
        success = 0
        failed = 0

        for i, word in enumerate(words):
            logger.info(f"[{i+1}/{total}] {word.name} ({word.kana})")

            word_dict = word.to_dict()
            try:
                ok = word_agent.store_vector(word.id, word_dict)
                if ok:
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                logger.warning(f"  ✗ Failed: {e}")
                failed += 1

            if (i + 1) % 100 == 0:
                logger.info(f"Progress: {i+1}/{total} (OK={success}, fail={failed})")

        logger.info(f"Done. Embedded: {success}, Failed: {failed}, Total: {total}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
