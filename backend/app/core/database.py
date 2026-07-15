"""Database engine and session management."""

import json
import logging
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_columns():
    """Add columns that may be missing from tables created by an older schema."""
    try:
        with engine.connect() as conn:
            columns = _get_table_columns(conn, "users")
            indexes = _get_indexes(conn, "users")

            # role column
            if "role" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"))
                conn.commit()
                logger.info("Added 'role' column to 'users' table")

            # email column
            if "email" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(120) DEFAULT ''"))
                conn.commit()
                logger.info("Added 'email' column to 'users' table")

            # Drop email unique index (dev: allow duplicate emails)
            for idx in list(indexes):
                if "email" in idx.lower() or idx.startswith("ix_users_email"):
                    conn.execute(text(f"DROP INDEX {idx}"))
                    conn.commit()
                    logger.info(f"Dropped unique index {idx} on email column")

            # is_verified column
            if "is_verified" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN NOT NULL DEFAULT 0"))
                conn.commit()
                logger.info("Added 'is_verified' column to 'users' table")

            # deleted column (soft delete)
            if "deleted" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN deleted BOOLEAN NOT NULL DEFAULT 0"))
                conn.commit()
                logger.info("Added 'deleted' column to 'users' table")

            # ── Articles table ──────────────────────────────────
            art_columns = _get_table_columns(conn, "articles")
            if "image_url" not in art_columns:
                conn.execute(text("ALTER TABLE articles ADD COLUMN image_url VARCHAR(500)"))
                conn.commit()
                logger.info("Added 'image_url' column to 'articles' table")

            # ── Words table ─────────────────────────────────────
            word_columns = _get_table_columns(conn, "words")
            if "image_url" not in word_columns:
                conn.execute(text("ALTER TABLE words ADD COLUMN image_url VARCHAR(500)"))
                conn.commit()
                logger.info("Added 'image_url' column to 'words' table")
            if "scene" not in word_columns:
                conn.execute(text("ALTER TABLE words ADD COLUMN scene JSON DEFAULT NULL"))
                conn.commit()
                logger.info("Added 'scene' column to 'words' table")
    except Exception as e:
        logger.warning(f"Could not check/add columns: {e}")


def _get_indexes(conn, table_name: str) -> set:
    """Get the set of index names for a table, engine-agnostic."""
    if settings.USE_SQLITE:
        result = conn.execute(text(f"PRAGMA index_list({table_name})")).fetchall()
        return {row[1] for row in result}
    else:
        result = conn.execute(text(f"SHOW INDEX FROM {table_name}")).fetchall()
        return {row[2] for row in result}


def _get_table_columns(conn, table_name: str) -> set:
    """Get the set of column names for a table, engine-agnostic."""
    if settings.USE_SQLITE:
        result = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return {row[1] for row in result}
    else:
        result = conn.execute(text(f"SHOW COLUMNS FROM {table_name}")).fetchall()
        return {row[0] for row in result}


def _load_dict(db):
    """Load JLPT dictionary into Word table if not already loaded."""
    dict_path = os.path.join(os.path.dirname(__file__), "dictionary", "jlpt_words.json")
    dict_path = os.path.normpath(dict_path)
    if not os.path.isfile(dict_path):
        logger.warning(f"Dictionary file not found: {dict_path}")
        return

    # Check if dict data is already loaded (count should be ~14K)
    from app.models.word import Word
    count = db.query(Word).count()
    if count > 1000:
        logger.info(f"Dictionary already loaded: {count} words")
        return
    logger.info(f"Only {count} words found — loading dictionary...")

    try:
        with open(dict_path, "r", encoding="utf-8") as f:
            words = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load dictionary JSON: {e}")
        return

    count = 0
    for entry in words:
        word = Word(
            name=entry["name"],
            kana=entry["kana"],
            translation=entry["translation"],
            description=entry.get("description", ""),
            type=entry.get("type"),
            example_sentences=entry.get("example_sentences", []),
        )
        db.add(word)
        count += 1

    db.commit()
    logger.info(f"✅ Loaded {count} dictionary words into Word table")


def init_db():
    """Create all tables if they don't exist, then apply migrations and seed."""
    import app.models.word  # noqa
    import app.models.favorite  # noqa
    import app.models.article  # noqa
    import app.models.user  # noqa
    Base.metadata.create_all(bind=engine)

    # Ensure columns that may be missing on existing tables
    _ensure_columns()

    # Load dictionary (runs once)
    db = SessionLocal()
    try:
        _load_dict(db)
    finally:
        db.close()
