"""API Dependencies - Authentication and common utilities.

This module centralizes dependencies that can be injected into API routes,
including authentication, database sessions, and common query helpers.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

# Security scheme instance - auto_error=False allows custom error handling
_bearer = HTTPBearer(auto_error=False)


def _require_jwt_secret() -> None:
    """Ensure JWT_SECRET is properly configured."""
    if not settings.JWT_SECRET or settings.JWT_SECRET == "your-super-secret-key-change-in-production":
        raise RuntimeError("JWT_SECRET is not configured")


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    _require_jwt_secret()
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    """Get the current authenticated user from JWT Bearer token.

    This is the main authentication dependency for protected routes.

    Args:
        db: Database session
        credentials: HTTP Bearer token credentials

    Returns:
        User: The authenticated user

    Raises:
        HTTPException: 401 if authentication fails

    Note:
        If ENABLE_AUTH=false in settings, this will return the first user
        in the database for development purposes.
    """
    # Dev mode: bypass authentication
    if not settings.ENABLE_AUTH:
        user = db.query(User).order_by(User.created_at.asc()).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No users available"
            )
        return user

    # Production mode: require valid JWT
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user


def require_current_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Explicit dependency for routes that must have authentication.

    This is an alias for get_current_user that makes the intent
    more explicit in routes that always require authentication.

    Args:
        current_user: The authenticated user

    Returns:
        User: The authenticated user
    """
    return current_user
