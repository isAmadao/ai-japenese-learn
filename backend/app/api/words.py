"""Word API endpoints — random words (session-cached, SSE streaming), detail, favorite toggle."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.word import Word
from app.schemas.word import (
    CachedWord,
    WordDetailResponse,
    RandomWordsResponse,
    FavoriteToggleRequest,
    FavoriteToggleResponse,
    SearchResponse,
    SearchResultItem,
    AiAddRequest,
    AiAddResponse,
)
from app.services.word_service import word_service

router = APIRouter(prefix="/api/words", tags=["words"])


SCENES = ["日常生活", "工作", "商务", "影视剧", "动漫", "旅游"]


@router.get("/random", response_model=RandomWordsResponse)
def get_random_words(
    count: int = Query(5, ge=1, le=20),
    session_id: str = Query("default", description="Browser session UUID"),
    scene: Optional[str] = Query(None, description="场景过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get random Japanese words (session-cached via Redis).

    Same *session_id* on browser refresh returns the same cached batch.
    Optional *scene* filters words by scene tag.
    """
    try:
        words = word_service.get_random_words(
            db, count=count, session_id=session_id,
            user_id=str(current_user.id), scene=scene,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return RandomWordsResponse(words=[CachedWord(**w) for w in words])


@router.get("/random/stream")
def stream_random_words(
    count: int = Query(5, ge=1, le=20),
    session_id: str = Query("default", description="Browser session UUID"),
    scene: Optional[str] = Query(None, description="场景过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream random Japanese words via SSE (row-level streaming).

    Each word is yielded as it's parsed from the LLM response, so the
    frontend can display words progressively.
    Optional *scene* filters words by scene tag.

    SSE events:
      data: {"type":"word","word":{...}}   — one per word
      data: {"type":"done","count":N}      — all done
      data: {"type":"error","message":""}  — error
    """
    def event_stream():
        for event in word_service.stream_random_words(
            db, count=count, session_id=session_id,
            user_id=str(current_user.id), scene=scene,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/search", response_model=SearchResponse)
def search_words(
    q: str = Query("", description="搜索关键词（日语/假名/中文）"),
    top_k: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search words via Elasticsearch.

    Uses BM25 full-text search on ``name``, ``kana``, and ``translation``
    (keyword matching).  Also runs vector KNN search via the local
    sentence-transformers model (offline, no API key needed).

    Results are ranked by ES relevance scoring.
    """
    result = word_service.search_words(db, q=q, top_k=top_k)
    return SearchResponse(
        results=[SearchResultItem(**r) for r in result["results"]],
        total=result["total"],
        query=result["query"],
    )


@router.post("/ai-add", response_model=AiAddResponse)
def ai_add_word(
    body: AiAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 补词 — 判断 query 是否为日语单词，若是则补充词条入库 + ES 索引。

    必须放在 /{word_id} 路由之前注册，避免路径歧义。
    """
    try:
        result = word_service.add_missing_word(
            db, body.query, user_id=str(current_user.id), api_key=body.api_key,
        )
    except RuntimeError as e:
        # LLM 解析/词条字段异常 → 502 而非裸 500
        raise HTTPException(status_code=502, detail=str(e))
    if result.get("status") == "rate_limited":
        raise HTTPException(status_code=429, detail="操作太频繁，请稍后再试")
    if result.get("status") == "invalid":
        raise HTTPException(status_code=400, detail=result.get("reason", "参数无效"))
    return AiAddResponse(**result)


@router.get("/{word_id}", response_model=WordDetailResponse)
def get_word_detail(
    word_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed information about a favorited word (from DB)."""
    detail = word_service.get_word_detail(db, word_id, user_id=str(current_user.id))
    if not detail:
        raise HTTPException(status_code=404, detail="单词未找到")
    return WordDetailResponse(**detail)


@router.post("/{word_id}/favorite", response_model=FavoriteToggleResponse)
def toggle_favorite(
    word_id: int,
    body: FavoriteToggleRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle favorite status for a word.

    When favoriting, *ext* should contain the cached word data so the
    backend can persist it to the Word table:
      {"name":"...", "kana":"...", "translation":"...", "type":"...", ...}
    """
    ext = body.ext if body else None
    result = word_service.toggle_favorite(db, word_id, user_id=str(current_user.id), ext=ext)
    return FavoriteToggleResponse(**result)


@router.post("/{word_id}/image")
def generate_word_image(
    word_id: int,
    body: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate / replace the Pexels illustration for this word.

    Accepts optional {"pexels_key": "..."} in the body.
    Returns {"image_url": "...", "success": true} or an error.
    """
    word = db.query(Word).filter(Word.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="单词未找到")

    b = body or {}
    pexels_key = b.get("pexels_key")
    from app.services.image_service import search_and_save_word_image

    url = search_and_save_word_image(word_id, api_key=pexels_key)
    if url:
        return {"success": True, "image_url": url}
    return {"success": False, "message": "未找到合适的图片"}


@router.post("/{word_id}/smart-image")
def smart_word_image(
    word_id: int,
    body: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """CLIP 智能配图 — 语义匹配最佳图片。

    先用 CLIP 文本编码搜索已有图库，没找到再从 Pexels 搜索。
    找到的图片会自动索引到 CLIP 图库，越用越精准。

    可选 body: {"pexels_key": "..."}
    """
    word = db.query(Word).filter(Word.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="单词未找到")

    b = body or {}
    pexels_key = b.get("pexels_key")
    from app.services.image_service import smart_search_word_image

    url = smart_search_word_image(word_id, api_key=pexels_key)
    if url:
        return {"success": True, "image_url": url, "method": "clip"}
    return {"success": False, "message": "未找到合适的图片"}


@router.post("/{word_id}/refresh-sentences")
def refresh_word_sentences(
    word_id: int,
    body: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """「句子换新」— 用 AI 重新生成单词的例句。

    The word_id here is the real DB primary key (not session-relative).
    Optionally accepts in the request body:
      api_key — user-provided API key
      content_type — anime / drama / music / daily / ""
      style — emotional / funny / adventure / epic / plain / ...
      source — specific anime / drama / song name
    """
    b = body or {}
    result = word_service.refresh_word_sentences(
        db, word_id,
        api_key=b.get("api_key"),
        content_type=b.get("content_type", ""),
        style=b.get("style", ""),
        source=b.get("source", ""),
    )
    return result
