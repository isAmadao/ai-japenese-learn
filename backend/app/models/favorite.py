"""Favorite model — tracks user's saved words with status machine.

Status machine:
  favorite  →  learned  (one-way, never goes back)
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(50), default="default", comment="用户标识（后续可扩展为真实用户系统）")
    status = Column(String(20), default="favorite", comment="favorite | learned")
    learned_at = Column(DateTime, nullable=True, comment="标记为 learned 的时间")
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
            "status": self.status,
            "learned_at": self.learned_at.isoformat() if self.learned_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "word": self.word.to_dict() if self.word else None,
        }
