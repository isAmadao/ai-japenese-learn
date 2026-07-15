"""Word model — persisted only when user favorites a word."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from app.core.database import Base


class Word(Base):
    __tablename__ = "words"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, index=True, comment="日语表记（例: 食べる）")
    kana = Column(String(200), nullable=False, comment="假名读音（例: たべる）")
    translation = Column(String(300), nullable=False, comment="中文释义（例: 吃）")
    description = Column(Text, nullable=True, comment="详细说明 / 用法备注")
    type = Column(String(10), nullable=True, comment="难度级别 N1-N5")
    example_sentences = Column(JSON, nullable=True, comment="例句 [{'japanese':'','chinese':''}]")
    image_url = Column(String(500), nullable=True, comment="Pexels 配图 URL")
    scene = Column(JSON, nullable=True, comment="场景标签列表，如 ['日常生活','旅游']")
    ext = Column(JSON, nullable=True, comment="备用扩展字段（生产环境使用）")
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "kana": self.kana,
            "translation": self.translation,
            "description": self.description,
            "type": self.type,
            "example_sentences": self.example_sentences or [],
            "image_url": self.image_url,
            "scene": self.scene or [],
            "ext": self.ext or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
