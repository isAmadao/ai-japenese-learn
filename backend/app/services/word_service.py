"""Word service — data-flow v4 (dict-based).

Data flow:
  1. Dictionary words are pre-loaded into the Word table on startup
  2. "换一批" → randomly select unseen dict words → show → save as "mastered"
  3. User favorites a mastered word → status becomes "favorite"
  4. User marks favorited as learned → status becomes "learned"
  5. User marks learned as mastered → status becomes "mastered"
  6. "句子换新" → LLM regenerates example sentences for a word
"""

import json
import logging
import random
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.word import Word
from app.models.favorite import Favorite
from app.models.article import Article, article_words
from app.agent.word_agent import word_agent
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)

# Redis key prefix for session-cached words
_SESSION_CACHE_PREFIX = "session_words:"


def _session_cache_key(session_id: str) -> str:
    return f"{_SESSION_CACHE_PREFIX}{session_id}"


def _word_to_cached(wd: Word, idx: int) -> dict:
    """Convert a Word DB record to CachedWord format."""
    return {
        "id": idx if idx else wd.id,
        "db_id": wd.id,
        "name": wd.name,
        "kana": wd.kana,
        "translation": wd.translation,
        "description": wd.description,
        "type": wd.type,
        "example_sentences": wd.example_sentences or [],
        "scene": wd.scene or [],
    }


# ── Service ────────────────────────────────────────────────

class WordService:
    """Word operations — dict-based random selection + on-favorite persistence."""

    # ═══════════════════════════════════════════════════════
    #  "换一批" — random from dict, no LLM cost
    # ═══════════════════════════════════════════════════════

    def _pick_random_dict_words(
        self, db: Session, count: int = 5, user_id: str = "default",
        scene: Optional[str] = None,
    ) -> list[dict]:
        """Randomly pick *count* dict words the user hasn't seen yet, optionally filtered by *scene*."""
        # Get IDs of words already seen by this user
        seen_subq = (
            db.query(Favorite.word_id)
            .filter(Favorite.user_id == user_id)
            .subquery()
        )

        unseen = (
            db.query(Word)
            .filter(~Word.id.in_(seen_subq))
            .all()
        )

        # Filter by scene if specified (JSON list — filter in Python)
        if scene:
            unseen = [w for w in unseen if w.scene and scene in w.scene]

        if not unseen:
            # All words have been seen — start over (with scene filter if applicable)
            logger.info("[Dict] %s all words seen, allowing repeats",
                        f"scene={scene}" if scene else "")
            unseen = db.query(Word).all()
            if scene:
                unseen = [w for w in unseen if w.scene and scene in w.scene]
            if not unseen:
                return []

        pick = random.sample(unseen, min(count, len(unseen)))
        return [_word_to_cached(w, i + 1) for i, w in enumerate(pick)]

    def _save_words_as_mastered(self, db: Session, words: list[dict], user_id: str = "default"):
        """Create Favorite(status=mastered) for words shown to user."""
        for wd in words:
            name = wd.get("name", "")
            db_id = wd.get("db_id") or wd.get("id")
            if not name and not db_id:
                continue

            # Find the Word record by db_id or name
            word = None
            if db_id:
                word = db.query(Word).filter(Word.id == db_id).first()
            if not word:
                word = db.query(Word).filter(Word.name == name).first()
            if not word:
                continue

            existing = (
                db.query(Favorite)
                .filter(Favorite.word_id == word.id, Favorite.user_id == user_id)
                .first()
            )
            if not existing:
                db.add(Favorite(word_id=word.id, user_id=user_id, status="mastered"))
        db.commit()
        logger.info(f"[Mastered] saved {len(words)} words to DB")

    def get_random_words(
        self, db: Session, count: int = 5,
        session_id: Optional[str] = None,
        user_id: str = "default",
        scene: Optional[str] = None,
    ) -> list[dict]:
        """Return random dictionary words for the current session (zero LLM cost).

        If *scene* is provided, only words tagged with that scene are returned.
        """
        sid = session_id or "default"
        cache_key = _session_cache_key(sid) + (f":scene={scene}" if scene else "")

        # ── 1. Check Redis session cache ────────────────
        cached = redis_client._sync_get(cache_key)
        if cached is not None:
            try:
                words = json.loads(cached)
                logger.info(f"[Session cache HIT] {sid} — {len(words)} words")
                return words[:count]
            except (json.JSONDecodeError, TypeError):
                pass

        # ── 2. Pick random words from dict ──────────────
        words = self._pick_random_dict_words(db, count=count, user_id=user_id, scene=scene)
        if not words:
            raise RuntimeError("词库为空，请联系管理员")

        # ── 3. Save as mastered + cache in Redis ────────
        self._save_words_as_mastered(db, words, user_id=user_id)
        redis_client._sync_set(
            cache_key,
            json.dumps(words, ensure_ascii=False),
            ttl=3600,
        )
        return words[:count]

    def stream_random_words(
        self, db: Session, count: int = 5,
        session_id: Optional[str] = None,
        user_id: str = "default",
        scene: Optional[str] = None,
    ):
        """Stream random dictionary words via SSE (zero LLM cost).

        If *scene* is provided, only words tagged with that scene are returned.

        Yields dicts suitable for SSE JSON events:
          {"type":"word", "word":{...}}  — one per word
          {"type":"done", "count":N}     — all done
        """
        import json as _json

        sid = session_id or "default"
        cache_key = _session_cache_key(sid) + (f":scene={scene}" if scene else "")

        # ── 1. Check Redis session cache (F5 reuse) ────
        cached = redis_client._sync_get(cache_key)
        if cached is not None:
            try:
                words = _json.loads(cached)
                logger.info(f"[SSE Session cache HIT] {sid} — {len(words)} words")
                for w in words[:count]:
                    yield {"type": "word", "word": w}
                yield {"type": "done", "count": min(len(words), count)}
                return
            except (_json.JSONDecodeError, TypeError):
                pass

        # ── 2. Pick random words from dict ──────────────
        words = self._pick_random_dict_words(db, count=count, user_id=user_id, scene=scene)
        if not words:
            yield {"type": "error", "message": "词库为空，请联系管理员"}
            return

        # ── 3. Save as mastered + cache ────────────────
        self._save_words_as_mastered(db, words, user_id=user_id)
        redis_client._sync_set(
            cache_key,
            _json.dumps(words, ensure_ascii=False),
            ttl=3600,
        )

        for w in words[:count]:
            yield {"type": "word", "word": w}
        yield {"type": "done", "count": min(len(words), count)}

    # ═══════════════════════════════════════════════════════
    #  "句子换新" — LLM regenerates example sentences
    # ═══════════════════════════════════════════════════════

    def refresh_word_sentences(
        self, db: Session, word_id: int,
        api_key: Optional[str] = None,
        content_type: str = "",
        style: str = "",
        source: str = "",
    ) -> dict:
        """Use LLM to regenerate example sentences for a word.

        *content_type* — anime / drama / music / daily / ""
        *style* — emotional / funny / adventure / epic / plain / ...
        *source* — specific anime / drama / song name (optional)
        *api_key* overrides the instance/default API key for this call.
        Returns the updated word dict (or None on failure).
        """
        word = db.query(Word).filter(Word.id == word_id).first()
        if not word:
            return {"success": False, "message": "单词未找到"}

        try:
            new_sentences = word_agent.enrich_sentences(
                name=word.name,
                kana=word.kana,
                translation=word.translation,
                type=word.type or "N5",
                api_key=api_key,
                content_type=content_type,
                style=style,
                source=source,
            )
        except Exception as e:
            logger.warning(f"句子换新 LLM failed: {e}")
            return {"success": False, "message": f"AI 生成失败: {str(e)[:100]}"}

        if not new_sentences:
            return {"success": False, "message": "AI 返回结果为空"}

        # ── 去重：与现有例句做语义相似度检测 ────────
        existing = word.example_sentences or []
        existing_texts = [s.get("japanese", "") for s in existing if s.get("japanese")]
        new_texts = [s.get("japanese", "") for s in new_sentences if s.get("japanese")]

        try:
            unique_texts = self._dedup_by_text(
                existing_texts=existing_texts,
                new_texts=new_texts,
                threshold=0.99,
            )
        except Exception as e:
            logger.warning(f"dedup failed, using all: {e}")
            unique_texts = new_texts

        # 只保留未去重掉的句子（全部被去重则保留全部）
        deduped = [s for s in new_sentences if s.get("japanese", "") in unique_texts]
        if not deduped:
            deduped = new_sentences
            logger.info(f"[句子换新] all {len(new_sentences)} deduped, accepting anyway")

        word.example_sentences = existing + deduped

        db.commit()
        logger.info(f"[句子换新] {word.name} — 追加 {len(new_sentences)} 句，共 {len(word.example_sentences)} 句")
        return {
            "success": True,
            "message": "例句已更新",
            "example_sentences": word.example_sentences,
            "total": len(word.example_sentences),
        }

    # ═══════════════════════════════════════════════════════
    #  Favorite — toggle (mastered → favorite, or remove)
    # ═══════════════════════════════════════════════════════

    def toggle_favorite(
        self, db: Session, word_id: int,
        user_id: str,
        ext: Optional[dict] = None,
    ) -> dict:
        """Toggle favorite status.

        *word_id* here is the session-relative id (1-5), NOT a DB key.
        When favoriting, the full word data is in *ext*.  We look up / create
        the Word record by **name** (unique), then toggle the Favorite row
        on the real DB primary key.

        Status transitions:
          mastered → favorite (first time ★)
          favorite → mastered  (unfavorite)
          removed  → favorite (re-favorite)
        """
        name = (ext or {}).get("name", "").strip()
        if not name:
            return {"is_favorited": False, "message": "缺少单词数据"}

        # ── 1. Find or create Word record by name ──────────
        word = db.query(Word).filter(Word.name == name).first()
        if not word:
            word = Word(
                name=name,
                kana=(ext or {}).get("kana", ""),
                translation=(ext or {}).get("translation", ""),
                description=(ext or {}).get("description"),
                type=(ext or {}).get("type"),
                example_sentences=(ext or {}).get("example_sentences"),
            )
            db.add(word)
            db.flush()

        # ── 2. Find existing Favorite ──────────────────────
        fav = (
            db.query(Favorite)
            .filter(
                Favorite.word_id == word.id,
                Favorite.user_id == user_id,
            )
            .first()
        )

        if fav:
            if fav.status == "mastered":
                # mastered → favorite
                fav.status = "favorite"
                db.commit()
                return {"is_favorited": True, "message": "收藏成功", "word_id": word.id}
            else:
                # favorite → mastered (unfavorite)
                fav.status = "mastered"
                db.commit()
                return {"is_favorited": False, "message": "已取消收藏", "word_id": word.id}
        else:
            db.add(Favorite(word_id=word.id, user_id=user_id, status="favorite"))
            db.commit()
            return {"is_favorited": True, "message": "收藏成功", "word_id": word.id}

    # ═══════════════════════════════════════════════════════
    #  Mark as learned (status machine: favorite → learned)
    # ═══════════════════════════════════════════════════════

    def mark_as_learned(self, db: Session, word_id: int, user_id: str) -> dict:
        """Mark a favorited word as learned. One-way (never goes back)."""
        fav = (
            db.query(Favorite)
            .filter(
                Favorite.word_id == word_id,
                Favorite.user_id == user_id,
                Favorite.status == "favorite",
            )
            .first()
        )
        if not fav:
            return {"success": False, "message": "单词未收藏或已学习"}
        fav.status = "learned"
        fav.learned_at = datetime.utcnow()
        db.commit()
        return {"success": True, "message": "已标记为已学习"}

    # ═══════════════════════════════════════════════════════
    #  Learned words (paginated, filterable by type)
    # ═══════════════════════════════════════════════════════

    def get_learned_words(
        self, db: Session, user_id: str,
        type_filter: Optional[str] = None,
        page: int = 1, page_size: int = 30,
    ) -> dict:
        """Get learned words, optionally filtered by type (N5-N1)."""
        query = (
            db.query(Favorite)
            .filter(
                Favorite.user_id == user_id,
                Favorite.status == "learned",
            )
        )
        if type_filter and type_filter in ("N5", "N4", "N3", "N2", "N1"):
            query = query.join(Word).filter(Word.type == type_filter)

        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        favorites = (
            query.order_by(Favorite.learned_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        words = [fav.word.to_dict() for fav in favorites if fav.word]
        # Attach learned_at
        for i, fav in enumerate(favorites):
            if fav and i < len(words):
                words[i]["learned_at"] = fav.learned_at.isoformat() if fav.learned_at else None

        return {
            "words": words,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def get_learned_type_counts(self, db: Session, user_id: str) -> dict:
        """Get count of learned words per type (N5-N1)."""
        rows = (
            db.query(Word.type, func.count(Favorite.id))
            .join(Favorite, Word.id == Favorite.word_id)
            .filter(
                Favorite.user_id == user_id,
                Favorite.status == "learned",
            )
            .group_by(Word.type)
            .all()
        )
        counts = {t or "NONE": c for t, c in rows}
        for level in ("N5", "N4", "N3", "N2", "N1"):
            counts.setdefault(level, 0)
        return counts

    # ═══════════════════════════════════════════════════════
    #  Mastered words
    # ═══════════════════════════════════════════════════════

    def get_mastered_words(
        self, db: Session, user_id: str,
        type_filter: Optional[str] = None,
        page: int = 1, page_size: int = 30,
    ) -> dict:
        """Get mastered words (status = mastered), optionally filtered by type."""
        query = (
            db.query(Favorite)
            .filter(
                Favorite.user_id == user_id,
                Favorite.status == "mastered",
            )
        )
        if type_filter and type_filter in ("N5", "N4", "N3", "N2", "N1"):
            query = query.join(Word).filter(Word.type == type_filter)

        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        favorites = (
            query.order_by(Favorite.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        words = [fav.word.to_dict() for fav in favorites if fav.word]
        return {
            "words": words,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def get_mastered_type_counts(self, db: Session, user_id: str) -> dict:
        """Get count of mastered words per type (N5-N1)."""
        rows = (
            db.query(Word.type, func.count(Favorite.id))
            .join(Favorite, Word.id == Favorite.word_id)
            .filter(
                Favorite.user_id == user_id,
                Favorite.status == "mastered",
            )
            .group_by(Word.type)
            .all()
        )
        counts = {t or "NONE": c for t, c in rows}
        for level in ("N5", "N4", "N3", "N2", "N1"):
            counts.setdefault(level, 0)
        return counts

    def mark_as_mastered(self, db: Session, word_id: int, user_id: str) -> dict:
        """Mark a learned word as mastered (learned → mastered).

        The user already knows this word, so it moves from "learned" to "mastered".
        """
        fav = (
            db.query(Favorite)
            .filter(
                Favorite.word_id == word_id,
                Favorite.user_id == user_id,
                Favorite.status == "learned",
            )
            .first()
        )
        if not fav:
            return {"success": False, "message": "单词未学习或已掌握"}
        fav.status = "mastered"
        db.commit()
        return {"success": True, "message": "已标记为已熟练"}

    # ═══════════════════════════════════════════════════════
    #  Favorites list (paginated, status = favorite)
    # ═══════════════════════════════════════════════════════

    def get_favorites_paginated(
        self, db: Session, user_id: str,
        page: int = 1, page_size: int = 30,
        type_filter: Optional[str] = None,
    ) -> dict:
        """Get paginated list of favorited words (status = favorite), optionally filtered by type (N5-N1)."""
        query = (
            db.query(Favorite)
            .filter(
                Favorite.user_id == user_id,
                Favorite.status == "favorite",
            )
        )
        if type_filter and type_filter in ("N5", "N4", "N3", "N2", "N1"):
            query = query.join(Word).filter(Word.type == type_filter)

        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        favorites = (
            query.order_by(Favorite.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        words = [fav.word.to_dict() for fav in favorites if fav.word]
        return {
            "words": words,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    # ═══════════════════════════════════════════════════════
    #  Word detail (from DB, for favorited words)
    # ═══════════════════════════════════════════════════════

    def get_word_detail(self, db: Session, word_id: int, user_id: str) -> Optional[dict]:
        word = db.query(Word).filter(Word.id == word_id).first()
        if not word:
            return None

        fav = (
            db.query(Favorite)
            .filter(Favorite.word_id == word_id, Favorite.user_id == user_id)
            .first()
        )
        articles = (
            db.query(Article)
            .join(article_words, Article.id == article_words.c.article_id)
            .filter(article_words.c.word_id == word_id)
            .all()
        )

        result = word.to_dict()
        result["is_favorited"] = fav is not None and fav.status == "favorite"
        result["favorited_at"] = fav.created_at.isoformat() if fav and fav.created_at else None
        result["articles"] = [{"id": a.id, "title": a.title, "level": a.level} for a in articles]
        return result

    # ═══════════════════════════════════════════════════════
    #  Dedup — vector similarity dedup for sentences
    # ═══════════════════════════════════════════════════════

    def _dedup_by_text(
        self,
        existing_texts: list[str],
        new_texts: list[str],
        threshold: float = 0.85,
        collection: str = "sentence_vectors",
    ) -> list[str]:
        """Filter *new_texts* to only those not similar to *existing_texts*.

        Uses DashScope embedding + Milvus vector search.
        If embedding/Milvus is unavailable, falls back to exact string match.
        """
        import hashlib
        from app.core.milvus_client import milvus_client
        from app.services.vector_service import vector_service

        # ── 1. Ensure existing texts are indexed ─────────────
        for txt in existing_texts:
            if not txt or not txt.strip():
                continue
            vec = vector_service.embed_via_api(txt) or vector_service.make_deterministic_vector(txt)
            h = hashlib.sha256(txt.encode("utf-8")).hexdigest()[:16]
            milvus_client.insert(collection, vec, {
                "id": hash(txt) % (2**31 - 1),
                "text": txt,
                "text_hash": h,
            })

        # ── 2. Check each candidate ──────────────────────────
        passed = []
        for txt in new_texts:
            if not txt or not txt.strip():
                continue
            vec = vector_service.embed_via_api(txt) or vector_service.make_deterministic_vector(txt)
            results = milvus_client.search(collection, vec, top_k=5)
            is_dup = any(
                hit.get("distance", 0) >= threshold for hit in results
            )
            if not is_dup:
                h = hashlib.sha256(txt.encode("utf-8")).hexdigest()[:16]
                milvus_client.insert(collection, vec, {
                    "id": hash(txt) % (2**31 - 1),
                    "text": txt,
                    "text_hash": h,
                })
                passed.append(txt)

        return passed

    # ═══════════════════════════════════════════════════════
    #  Search — Elasticsearch (keyword + semantic hybrid)
    # ═══════════════════════════════════════════════════════

    def search_words(
        self, db: Session, q: str, top_k: int = 20,
        api_key: Optional[str] = None,
    ) -> dict:
        """Search words — two-channel recall: BM25 + vector KNN.

        1. BM25 full-text search on ``name`` (boosted 2x), ``kana``, ``translation``
        2. Vector KNN search via local sentence-transformers model (if loaded)
        3. Merge: interleave by score, deduplicate

        BM25 always runs.  Vector search is best-effort — silent skip if
        the model isn't available (e.g. during first startup).
        """
        if not q or not q.strip():
            return {"results": [], "total": 0, "query": q}

        q = q.strip()
        seen_ids: set[int] = set()
        scored: list[dict] = []

        try:
            from elasticsearch import Elasticsearch
            es = Elasticsearch(["http://localhost:9200"], request_timeout=5)

            # ── 1. BM25 full-text ──────────────────────────
            bm25_result = es.search(index="jp_words", size=top_k, body={
                "query": {
                    "multi_match": {
                        "query": q,
                        "fields": ["name^2", "kana", "translation"],
                        "type": "best_fields",
                    }
                },
            })

            for hit in bm25_result["hits"]["hits"]:
                src = hit["_source"]
                wid = int(hit["_id"])
                seen_ids.add(wid)
                scored.append({
                    "id": wid,
                    "name": src.get("name", ""),
                    "kana": src.get("kana", ""),
                    "translation": src.get("translation", ""),
                    "description": src.get("description"),
                    "type": src.get("type"),
                    "score": 1.0,  # BM25 match = top priority
                })

            # ── 2. Vector KNN (only if model is loaded) ────
            try:
                from app.services.vector_service import VectorService
                if VectorService._LOCAL_MODEL is not None:
                    vec = VectorService._LOCAL_MODEL.encode(q).tolist()
                    knn_result = es.search(index="jp_words", size=top_k, body={
                        "knn": {
                            "field": "embedding",
                            "query_vector": vec,
                            "k": top_k * 2,
                            "num_candidates": top_k * 5,
                        },
                    })

                    for hit in knn_result["hits"]["hits"]:
                        src = hit["_source"]
                        wid = int(hit["_id"])
                        if wid in seen_ids:
                            continue
                        seen_ids.add(wid)
                        scored.append({
                            "id": wid,
                            "name": src.get("name", ""),
                            "kana": src.get("kana", ""),
                            "translation": src.get("translation", ""),
                            "description": src.get("description"),
                            "type": src.get("type"),
                            "score": hit["_score"] * 0.85,  # semantic slightly lower than exact
                        })
            except Exception as e:
                logger.debug(f"Vector search unavailable, BM25 only: {e}")

        except Exception as e:
            logger.warning(f"ES search failed, falling back to SQL LIKE: {e}")
            # ── Graceful degradation: SQL LIKE ──────────────
            pattern = f"%{q}%"
            keyword_results = (
                db.query(Word)
                .filter(
                    Word.name.ilike(pattern)
                    | Word.kana.ilike(pattern)
                    | Word.translation.ilike(pattern)
                )
                .limit(top_k)
                .all()
            )
            for w in keyword_results:
                scored.append({
                    "id": w.id,
                    "name": w.name,
                    "kana": w.kana,
                    "translation": w.translation,
                    "description": w.description,
                    "type": w.type,
                    "score": 1.0,
                })

        return {
            "results": scored[:top_k],
            "total": len(scored),
            "query": q,
        }


word_service = WordService()
