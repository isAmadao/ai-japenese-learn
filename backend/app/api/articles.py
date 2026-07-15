"""Article API endpoints — SSE streaming generation and retrieve articles."""

import json
import logging

logger = logging.getLogger(__name__)

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.article import (
    ArticleGenerateRequest,
    ArticleResponse,
)
from app.agent.article_agent import article_agent
from app.utils.json_utils import extract_json
from app.models.word import Word
from app.models.article import Article, article_words

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.post("/generate-stream")
def generate_article_stream(
    request: ArticleGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a short essay using selected vocabulary via SSE streaming.

    Streams LLM output token-by-token so the frontend shows real-time progress.
    Requires authentication. Pass {"api_key": "..."} in the body for a
    user-provided API key.
    SSE events:
      data: {"type":"token","content":"..."}     — partial LLM output
      data: {"type":"done","article_id":1}       — generation complete, article saved
      data: {"type":"error","message":"..."}     — error occurred
    """
    if not request.word_ids:
        raise HTTPException(status_code=400, detail="请至少选择一个单词")
    if request.level not in ("N5", "N4", "N3", "N2", "N1"):
        raise HTTPException(status_code=400, detail="级别无效，请选择 N5-N1")

    def event_stream(api_key: Optional[str] = None, pexels_key: Optional[str] = None):
        """Sync generator that yields SSE-formatted events."""
        db = SessionLocal()
        try:
            words = db.query(Word).filter(Word.id.in_(request.word_ids)).all()
            if not words:
                yield f"data: {json.dumps({'type': 'error', 'message': '未找到指定的单词'})}\n\n"
                return

            word_dicts = [w.to_dict() for w in words]
            buffer = ""

            # Stream each token from ArticleAgent
            for text_chunk in article_agent.generate_article_stream(
                word_dicts, request.level, api_key=api_key,
                content_type=request.content_type or "",
                style=request.style or "",
                source=request.source or "",
            ):
                buffer += text_chunk
                yield f"data: {json.dumps({'type': 'token', 'content': text_chunk})}\n\n"

            # Parse the accumulated JSON response
            result = extract_json(buffer)
            if isinstance(result, list):
                result = result[0]

            # Save article to DB
            article = Article(
                title=result.get("title", ""),
                content_japanese=result.get("content_japanese", ""),
                content_chinese=result.get("content_chinese", ""),
                level=request.level,
            )
            db.add(article)
            db.flush()

            for word in words:
                db.execute(
                    article_words.insert().values(
                        article_id=article.id,
                        word_id=word.id,
                    )
                )

            db.commit()
            db.refresh(article)

            # ── 后台 Pexels 配图（不阻塞 SSE） ────────────────
            logger.warning("[Article] pexels_key provided=%s title=%s",
                           bool(pexels_key), (result.get("title") or "")[:30])
            from app.services.image_service import set_article_image_async
            set_article_image_async(article.id, result.get("title", ""), api_key=pexels_key)

            # 后台线程做向量存储（不影响前端展示）
            import threading
            def _store_vec():
                try:
                    from app.agent.article_agent import article_agent as _aa
                    _aa.store_vector(article.id, {
                        "title": result.get("title", ""),
                        "content_japanese": result.get("content_japanese", ""),
                        "level": request.level,
                    })
                except Exception:
                    pass
            threading.Thread(target=_store_vec, daemon=True).start()

            # Done — return to frontend immediately
            yield f"data: {json.dumps({'type': 'done', 'article_id': article.id})}\n\n"

        except Exception as e:
            db.rollback()
            yield f"data: {json.dumps({'type': 'error', 'message': f'生成失败: {str(e)}'})}\n\n"
        finally:
            db.close()

    return StreamingResponse(event_stream(api_key=request.api_key, pexels_key=request.pexels_key), media_type="text/event-stream")


@router.post("/{article_id}/image")
def generate_article_image(
    article_id: int,
    body: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Replace the Pexels illustration for this article.

    Accepts optional {"pexels_key": "..."} in the body.
    Returns {"image_url": "...", "success": true} or an error.
    """
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章未找到")

    b = body or {}
    pexels_key = b.get("pexels_key")
    from app.services.image_service import search_and_save_article_image

    url = search_and_save_article_image(article_id, api_key=pexels_key)
    if url:
        return {"success": True, "image_url": url}
    return {"success": False, "message": "未找到合适的图片"}


@router.get("/{article_id}", response_model=ArticleResponse)
def get_article(article_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    """Get article details by ID."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章未找到")

    words_data = [
        {"id": w.id, "name": w.name, "kana": w.kana, "translation": w.translation, "type": w.type}
        for w in article.words
    ]
    return ArticleResponse(
        id=article.id,
        title=article.title,
        content_japanese=article.content_japanese,
        content_chinese=article.content_chinese,
        level=article.level,
        image_url=article.image_url,
        created_at=article.created_at.isoformat() if article.created_at else None,
        words=words_data,
    )
