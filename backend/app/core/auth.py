"""Auth utilities — JWT verification via central auth-service (auth-client).

This module replaces the old self-contained auth-kit with lightweight
JWT verification using ``fastapi_auth_client.AuthClient``.

User records are auto-created in the local database on first login
(based on the JWT payload from auth-service), so existing business
logic (favorites, learned words, etc.) continues to work with local
foreign keys.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

# Path to auth-service — adjust in production
AUTH_SERVICE_URL = settings.AUTH_SERVICE_URL

logger = logging.getLogger(__name__)

# ── AuthClient instance (lazy-loaded) ──────────────────────────

_auth_client = None


def _get_auth_client():
    """Get or create the shared AuthClient instance."""
    global _auth_client
    if _auth_client is None:
        from fastapi_auth_client import AuthClient
        kwargs = {}
        if AUTH_SERVICE_URL:
            kwargs["jwks_url"] = f"{AUTH_SERVICE_URL.rstrip('/')}/.well-known/jwks.json"
        else:
            # Fallback: use the explicit public key from settings
            kwargs["jwt_public_key"] = settings.JWT_PUBLIC_KEY
        _auth_client = AuthClient(**kwargs)
    return _auth_client


# ── Bearer scheme ─────────────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=False)


# ── Dependency: get_current_user (returns User ORM) ───────────


def _ensure_dev_user(db: Session) -> User:
    """Create or return the default dev/admin user (AUTH_DISABLED mode)."""
    user = db.query(User).filter(User.id == 1).first()
    if user is None:
        user = User(
            id=1,
            username="dev",
            email="dev@localhost",
            password_hash="",
            role="admin",
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Auto-created dev user (AUTH_DISABLED mode)")
    return user


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: validates JWT via auth-service, returns local User ORM.

    If the user doesn't exist in the local database yet, a minimal local
    record is auto-created (id maps to auth-service's uid).

    When settings.AUTH_DISABLED is True (default), skips JWT verification
    and returns a default dev/admin user — no external auth-service needed.
    """
    # ── Dev mode: no external auth-service required ─────────────
    if settings.AUTH_DISABLED:
        return _ensure_dev_user(db)

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode JWT via auth-client (RS256, public key from JWKS)
    auth = _get_auth_client()
    payload = auth._decode_token(credentials.credentials)

    uid: int = payload.get("uid", 0)
    username: str = payload.get("sub", "")
    role: str = payload.get("role", "user")

    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效",
        )

    # Auto-create local user record if not exists
    user = db.query(User).filter(User.id == uid).first()
    if user is None:
        user = User(
            id=uid,
            username=username,
            email="",
            password_hash="",  # auth-service manages passwords
            role=role,
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Auto-created local user: {username} (id={uid})")
    else:
        # Update username/role in case they changed in auth-service
        if user.username != username or user.role != role:
            user.username = username
            user.role = role
            db.commit()

    return user


# ── Dependency: require_admin ─────────────────────────────────


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency: requires admin role."""
    if getattr(current_user, "role", None) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user
