"""Image service — Pexels API integration for illustrations.

Searches for relevant images. Pexels API is free at 200 requests/hour.
All image searches run in a background thread so they never block the main flow.
"""

import logging
import threading
from typing import Optional

import httpx

from app.core.config import settings
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
PEXELS_TIMEOUT = 30  # seconds


def _search_pexels(keywords: str, api_key: str, exclude_url: Optional[str] = None) -> Optional[str]:
    """Call Pexels API and return a medium image URL, or None.

    Picks a random photo from the top results so repeated calls for the
    same keyword can return different images.  *exclude_url* — if set,
    skips photos matching that URL (for "换一张" to get something new).
    """
    import random
    try:
        with httpx.Client(timeout=PEXELS_TIMEOUT) as client:
            resp = client.get(
                PEXELS_SEARCH_URL,
                headers={"Authorization": api_key},
                params={"query": keywords, "per_page": 8, "locale": "ja-JP", "size": "medium"},
            )
            resp.raise_for_status()
            data = resp.json()
            photos = data.get("photos", [])
            # Filter out the current image if provided
            candidates = [
                p.get("src", {}).get("medium")
                for p in photos
                if p.get("src", {}).get("medium") != exclude_url
            ]
            if candidates:
                url = random.choice(candidates)
                logger.info("Pexels image found for '%s': %s", keywords[:30], url)
                return url
            # Fallback to first if all filtered out
            if photos:
                url = photos[0].get("src", {}).get("medium")
                if url:
                    return url
            logger.info("No Pexels results for '%s'", keywords[:30])
    except httpx.TimeoutException:
        logger.warning("Pexels timed out for '%s'", keywords[:30])
    except httpx.HTTPStatusError as e:
        logger.warning("Pexels HTTP %d: %s", e.response.status_code, e.response.text[:200])
    except Exception as e:
        logger.warning("Pexels search failed: %s", e)
    return None


def search_and_save_word_image(word_id: int, api_key: Optional[str] = None) -> Optional[str]:
    """Synchronously search Pexels for a word, save image_url, return the URL.

    Used by the manual '生成配图' button.  Returns None on failure.
    Skips the current image (if any) so repeated calls yield different results.
    """
    key = _resolve_key(api_key)
    if not key:
        return None
    db = SessionLocal()
    try:
        from app.models.word import Word
        word = db.query(Word).filter(Word.id == word_id).first()
        if not word:
            return None
        url = _search_pexels(word.name, key, exclude_url=word.image_url)
        if url:
            word.image_url = url
            db.commit()
            return url
        return None
    except Exception as e:
        logger.warning("[Pexels] sync save word %d failed: %s", word_id, e)
        db.rollback()
        return None
    finally:
        db.close()


def search_and_save_article_image(article_id: int, api_key: Optional[str] = None) -> Optional[str]:
    """Synchronously search Pexels for an article, save image_url, return the URL.

    Used by the manual '换一个' button.  Returns None on failure.
    Skips the current image so repeated calls yield different results.
    """
    key = _resolve_key(api_key)
    if not key:
        return None
    db = SessionLocal()
    try:
        from app.models.article import Article
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            return None
        title = article.title or ""
        url = _search_pexels(title, key, exclude_url=article.image_url)
        if url:
            article.image_url = url
            db.commit()
            return url
        return None
    except Exception as e:
        logger.warning("[Pexels] sync save article %d failed: %s", article_id, e)
        db.rollback()
        return None
    finally:
        db.close()


def _resolve_key(per_call: Optional[str]) -> Optional[str]:
    """Resolve which API key to use: per-call > settings > None."""
    key = per_call or settings.PEXELS_API_KEY or None
    if not key:
        logger.warning("[Pexels] no API key available (per_call=%s, settings=%s)",
                       bool(per_call), bool(settings.PEXELS_API_KEY))
    return key


def set_article_image_async(article_id: int, keywords: str, api_key: Optional[str] = None):
    """Search Pexels in a background thread and save image_url to the article."""
    key = _resolve_key(api_key)
    if not key:
        return

    def _work():
        db = SessionLocal()
        try:
            from app.models.article import Article
            article = db.query(Article).filter(Article.id == article_id).first()
            if not article or article.image_url:
                return
            url = _search_pexels(keywords, key)
            if url:
                article.image_url = url
                db.commit()
                logger.info("Pexels image saved to article %d", article_id)
        except Exception:
            db.rollback()
        finally:
            db.close()

    threading.Thread(target=_work, daemon=True).start()


def set_word_image_async(word_id: int, keywords: str, api_key: Optional[str] = None):
    """Search Pexels in a background thread and save image_url to the word."""
    key = _resolve_key(api_key)
    if not key:
        return

    def _work():
        logger.warning("[Pexels] bg thread started for word %d key=%s", word_id, "SET" if key else "NONE")
        db = SessionLocal()
        try:
            from app.models.word import Word
            word = db.query(Word).filter(Word.id == word_id).first()
            if not word:
                logger.warning("[Pexels] word %d not found", word_id)
                return
            if word.image_url:
                logger.info("[Pexels] word %d already has image, skipping", word_id)
                return
            logger.info("[Pexels] searching for '%s'", keywords[:30])
            url = _search_pexels(keywords, key)
            if url:
                word.image_url = url
                db.commit()
                logger.info("[Pexels] image saved to word %d (%s)", word_id, keywords[:20])
            else:
                logger.info("[Pexels] no image found for word %d", word_id)
        except Exception as e:
            logger.warning("[Pexels] bg error for word %d: %s", word_id, e)
            db.rollback()
        finally:
            db.close()

    threading.Thread(target=_work, daemon=True).start()


# ── CLIP cross-modal image search ───────────────────────────


def store_image_clip_embedding(
    entity_type: str,
    entity_id: int,
    image_url: str,
    text_context: str = "",
) -> bool:
    """Encode an image with CLIP and store the embedding in Milvus."""
    from app.services.clip_service import clip
    from app.core.milvus_client import milvus_client

    embedding = clip.encode_image_url(image_url)
    if embedding is None:
        logger.warning("[CLIP] embedding failed for %s=%d: %s",
                       entity_type, entity_id, image_url[:50])
        return False

    ok = milvus_client.insert(
        milvus_client.CLIP_IMAGE_COLLECTION,
        embedding,
        {
            "id": entity_id,
            "entity_type": entity_type,
            "image_url": image_url,
            "text": text_context[:200],
        },
    )
    if ok:
        logger.info("[CLIP] stored %s=%d embedding: %s",
                    entity_type, entity_id, image_url[:40])
    return ok


def store_image_clip_embedding_from_bytes(
    entity_type: str,
    entity_id: int,
    image_bytes: bytes,
    text_context: str = "",
) -> bool:
    """Encode uploaded image bytes with CLIP and store the embedding in Milvus."""
    from app.services.clip_service import clip
    from app.core.milvus_client import milvus_client

    embedding = clip.encode_image_bytes(image_bytes)
    if embedding is None:
        logger.warning("[CLIP] embedding failed for %s=%d from bytes",
                       entity_type, entity_id)
        return False

    ok = milvus_client.insert(
        milvus_client.CLIP_IMAGE_COLLECTION,
        embedding,
        {
            "id": entity_id,
            "entity_type": entity_type,
            "image_url": f"upload://{entity_type}_{entity_id}",
            "text": text_context[:500],
        },
    )
    if ok:
        logger.info("[CLIP] stored %s=%d embedding from upload",
                    entity_type, entity_id)
    return ok


def search_images_by_clip(
    query_text: str,
    top_k: int = 5,
    entity_type: str = None,
) -> list[dict]:
    """Search images by text query using CLIP cross-modal retrieval."""
    from app.services.clip_service import clip
    from app.core.milvus_client import milvus_client

    query_vec = clip.encode_text(query_text)
    if query_vec is None:
        logger.warning("[CLIP] text encoding failed: %s", query_text[:30])
        return []

    results = milvus_client.search(
        milvus_client.CLIP_IMAGE_COLLECTION,
        query_vec,
        top_k=top_k * 2,
    )

    hits = []
    for hit in results:
        entity = hit.get("entity", {})
        if entity_type and entity.get("entity_type") != entity_type:
            continue
        hits.append({
            "id": entity.get("id"),
            "entity_type": entity.get("entity_type"),
            "image_url": entity.get("image_url"),
            "text": entity.get("text"),
            "distance": hit.get("distance", 0),
        })
        if len(hits) >= top_k:
            break

    return hits


def smart_search_word_image(word_id: int, api_key: str = None) -> str | None:
    """CLIP-enhanced image search for a word (CLIP → Pexels fallback)."""
    from app.core.database import SessionLocal
    from app.models.word import Word

    db = SessionLocal()
    try:
        word = db.query(Word).filter(Word.id == word_id).first()
        if not word:
            return None

        search_text = f"{word.name} {word.kana} {word.translation or ''}"

        # Strategy 1: CLIP search existing image library
        results = search_images_by_clip(search_text, top_k=3)
        if results:
            best = results[0]
            if best.get("distance", 0) > 0.5:
                logger.info("[CLIP] smart match for word %d: dist=%.3f",
                           word_id, best["distance"])
                word.image_url = best["image_url"]
                db.commit()
                return best["image_url"]

        # Strategy 2: Pexels fallback
        key = _resolve_key(api_key)
        if not key:
            return None

        image_url = _search_pexels(search_text, key, exclude_url=word.image_url)
        if image_url:
            word.image_url = image_url
            db.commit()
            threading.Thread(
                target=store_image_clip_embedding,
                args=("word", word_id, image_url, search_text),
                daemon=True,
            ).start()
            return image_url

        return None
    finally:
        db.close()
