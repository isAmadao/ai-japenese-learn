"""Mastered words API — status machine: learned → mastered.

Mastered words = words the user already knows (from LLM generation or
marked as mastered from the learned page).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.word_service import word_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mastered", tags=["mastered"])


@router.get("")
def list_mastered(
    type: str = Query(None, description="Filter by N5-N1"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get paginated mastered words, optionally filtered by type."""
    try:
        result = word_service.get_mastered_words(
            db, user_id=str(current_user.id), type_filter=type, page=page, page_size=page_size,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to list mastered words: {e}")
        raise HTTPException(status_code=500, detail="获取已熟练单词失败")


@router.get("/types")
def mastered_type_counts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get count of mastered words per type (N5-N1)."""
    try:
        return word_service.get_mastered_type_counts(db, user_id=str(current_user.id))
    except Exception as e:
        logger.error(f"Failed to get mastered type counts: {e}")
        raise HTTPException(status_code=500, detail="获取级别统计失败")
