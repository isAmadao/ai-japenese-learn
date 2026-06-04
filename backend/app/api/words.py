"""Word API endpoints — random words, detail, favorites toggle."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.word import (
    WordResponse,
    WordDetailResponse,
    RandomWordsResponse,
    FavoriteToggleResponse,
)
from app.services.word_service import word_service

router = APIRouter(prefix="/api/words", tags=["words"])


@router.get("/random", response_model=RandomWordsResponse)
def get_random_words(count: int = 5, db: Session = Depends(get_db)):
    """Get random Japanese words (excluding favorited ones)."""
    words = word_service.get_random_words(db, count=count)
    word_responses = [
        WordResponse(
            id=w.id,
            japanese=w.japanese,
            kana=w.kana,
            chinese_meaning=w.chinese_meaning,
            example_sentences=w.example_sentences or [],
            created_at=w.created_at.isoformat() if w.created_at else None,
        )
        for w in words
    ]
    return RandomWordsResponse(words=word_responses)


@router.get("/{word_id}", response_model=WordDetailResponse)
def get_word_detail(word_id: int, db: Session = Depends(get_db)):
    """Get detailed information about a specific word."""
    detail = word_service.get_word_detail(db, word_id)
    if not detail:
        raise HTTPException(status_code=404, detail="单词未找到")
    return WordDetailResponse(**detail)


@router.post("/{word_id}/favorite", response_model=FavoriteToggleResponse)
def toggle_favorite(word_id: int, db: Session = Depends(get_db)):
    """Toggle favorite status for a word."""
    # Verify word exists
    from app.models.word import Word
    word = db.query(Word).filter(Word.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="单词未找到")
    result = word_service.toggle_favorite(db, word_id)
    return FavoriteToggleResponse(**result)
