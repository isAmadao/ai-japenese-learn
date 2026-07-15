"""User model — authentication for multi-user support."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True, comment="用户名/昵称")
    email = Column(String(120), nullable=False, default="", comment="邮箱")
    password_hash = Column(String(128), nullable=False, comment="bcrypt 密码哈希")
    role = Column(String(20), nullable=False, default="user", comment="角色: user / admin")
    is_verified = Column(Boolean, nullable=False, default=False, comment="邮箱已验证")
    deleted = Column(Boolean, nullable=False, default=False, comment="逻辑删除")
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_verified": self.is_verified,
            "deleted": self.deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
