"""Favorite model — tracks user's saved words."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(50), default="default", comment="用户标识（后续可扩展为真实用户系统）")
    created_at = Column(DateTime, default=datetime.utcnow)

    word = relationship("Word", lazy="joined")

    __table_args__ = (
        UniqueConstraint("word_id", "user_id", name="uq_word_user"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "word_id": self.word_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "word": self.word.to_dict() if self.word else None,
        }
