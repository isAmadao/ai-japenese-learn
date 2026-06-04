"""Word API endpoints — random words (session-cached), detail, favorite toggle."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.word import (
    CachedWord,
    WordDetailResponse,
    RandomWordsResponse,
    FavoriteToggleRequest,
    FavoriteToggleResponse,
)
from app.services.word_service import word_service

router = APIRouter(prefix="/api/words", tags=["words"])


@router.get("/random", response_model=RandomWordsResponse)
def get_random_words(
    count: int = Query(5, ge=1, le=20),
    session_id: str = Query("default", description="Browser session UUID"),
    db: Session = Depends(get_db),
):
    """Get random Japanese words (session-cached via Redis).

    Same *session_id* on browser refresh returns the same cached batch.
    """
    try:
        words = word_service.get_random_words(db, count=count, session_id=session_id)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return RandomWordsResponse(words=[CachedWord(**w) for w in words])


@router.get("/{word_id}", response_model=WordDetailResponse)
def get_word_detail(word_id: int, db: Session = Depends(get_db)):
    """Get detailed information about a favorited word (from DB)."""
    detail = word_service.get_word_detail(db, word_id)
    if not detail:
        raise HTTPException(status_code=404, detail="单词未找到")
    return WordDetailResponse(**detail)


@router.post("/{word_id}/favorite", response_model=FavoriteToggleResponse)
def toggle_favorite(
    word_id: int,
    body: FavoriteToggleRequest = None,
    db: Session = Depends(get_db),
):
    """Toggle favorite status for a word.

    When favoriting, *ext* should contain the cached word data so the
    backend can persist it to the Word table:
      {"name":"...", "kana":"...", "translation":"...", "type":"...", ...}
    """
    ext = body.ext if body else None
    result = word_service.toggle_favorite(db, word_id, ext=ext)
    return FavoriteToggleResponse(**result)
