"""Pydantic schemas for word-related API requests/responses."""

from typing import Optional, Any
from pydantic import BaseModel


class ExampleSentence(BaseModel):
    japanese: str
    chinese: str


class CachedWord(BaseModel):
    """Word as returned from Redis cache (not persisted to DB yet)."""
    id: int
    name: str
    kana: str
    translation: str
    description: Optional[str] = None
    type: Optional[str] = None
    example_sentences: list[ExampleSentence] = []


class RandomWordsResponse(BaseModel):
    words: list[CachedWord]


class FavoriteToggleRequest(BaseModel):
    ext: Optional[dict[str, Any]] = None


class FavoriteToggleResponse(BaseModel):
    is_favorited: bool
    message: str


class WordResponse(BaseModel):
    """Word as stored in DB (after favoriting)."""
    id: int
    name: str
    kana: str
    translation: str
    description: Optional[str] = None
    type: Optional[str] = None
    example_sentences: list[ExampleSentence] = []
    ext: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class WordDetailResponse(WordResponse):
    is_favorited: bool = False
    favorited_at: Optional[str] = None
    articles: list[dict] = []


class FavoriteListResponse(BaseModel):
    words: list[WordResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
