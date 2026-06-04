"""Article API endpoints — generate (sync & SSE streaming) and retrieve articles."""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.schemas.article import (
    ArticleGenerateRequest,
    ArticleGenerateResponse,
    ArticleResponse,
)
from app.services.article_service import article_service
from app.agent.article_agent import article_agent
from app.models.word import Word
from app.models.article import Article, article_words

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.post("/generate", response_model=ArticleGenerateResponse)
def generate_article(
    request: ArticleGenerateRequest,
    db: Session = Depends(get_db),
):
    """Generate a short essay using selected vocabulary (synchronous, returns full article)."""
    if not request.word_ids:
        raise HTTPException(status_code=400, detail="请至少选择一个单词")
    if request.level not in ("N5", "N4", "N3", "N2", "N1"):
        raise HTTPException(status_code=400, detail="级别无效，请选择 N5-N1")

    try:
        article = article_service.generate_article(
            db, request.word_ids, request.level
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not article:
        raise HTTPException(status_code=404, detail="未找到指定的单词")

    words_data = [
        {"id": w.id, "name": w.name, "kana": w.kana, "translation": w.translation, "type": w.type}
        for w in article.words
    ]
    article_resp = ArticleResponse(
        id=article.id,
        title=article.title,
        content_japanese=article.content_japanese,
        content_chinese=article.content_chinese,
        level=article.level,
        created_at=article.created_at.isoformat() if article.created_at else None,
        words=words_data,
    )
    return ArticleGenerateResponse(article=article_resp)


@router.post("/generate-stream")
def generate_article_stream(request: ArticleGenerateRequest):
    """Generate a short essay using selected vocabulary via SSE streaming.

    Streams LLM output token-by-token so the frontend shows real-time progress.
    SSE events:
      data: {"type":"token","content":"..."}     — partial LLM output
      data: {"type":"done","article_id":1}       — generation complete, article saved
      data: {"type":"error","message":"..."}     — error occurred
    """
    if not request.word_ids:
        raise HTTPException(status_code=400, detail="请至少选择一个单词")
    if request.level not in ("N5", "N4", "N3", "N2", "N1"):
        raise HTTPException(status_code=400, detail="级别无效，请选择 N5-N1")

    def event_stream():
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
            for text_chunk in article_agent.generate_article_stream(word_dicts, request.level):
                buffer += text_chunk
                yield f"data: {json.dumps({'type': 'token', 'content': text_chunk})}\n\n"

            # Parse the accumulated JSON response
            result = article_agent._extract_json(buffer)
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

            # Store vector in Milvus
            article_agent.store_vector(article.id, {
                "title": result.get("title", ""),
                "content_japanese": result.get("content_japanese", ""),
                "level": request.level,
            })

            yield f"data: {json.dumps({'type': 'done', 'article_id': article.id})}\n\n"

        except Exception as e:
            db.rollback()
            yield f"data: {json.dumps({'type': 'error', 'message': f'生成失败: {str(e)}'})}\n\n"
        finally:
            db.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{article_id}", response_model=ArticleResponse)
def get_article(article_id: int, db: Session = Depends(get_db)):
    """Get article details by ID."""
    article = article_service.get_article(db, article_id)
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
        created_at=article.created_at.isoformat() if article.created_at else None,
        words=words_data,
    )
