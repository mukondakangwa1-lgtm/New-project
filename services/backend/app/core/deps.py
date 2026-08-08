"""
Digital Campus - Shared Dependencies
"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from typing import Optional

from app.core.config import settings
from app.core.database import get_db
from app.core.security import AUTH_COOKIE_NAME
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

_CSRF_HEADER = "x-requested-with"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _decode_token(token: str) -> Optional[str]:
    """Decode a JWT; returns the subject email or None."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")
        return email if email else None
    except JWTError:
        return None


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode JWT and return the current user.

    Accepts the token from the Authorization header (API clients, device
    flows) or from the HttpOnly session cookie (browser sessions). When the
    cookie is used for a state-changing request, a custom header must be
    present — the standard CSRF defense, since browsers cannot attach custom
    headers cross-origin without CORS approval (which is origin-locked).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    email = _decode_token(token) if token else None
    used_cookie = False
    if email is None:
        cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
        if cookie_token:
            email = _decode_token(cookie_token)
            used_cookie = email is not None

    if email is None:
        raise credentials_exception

    if (
        used_cookie
        and request.method not in _SAFE_METHODS
        and not request.headers.get(_CSRF_HEADER)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF guard: state-changing request requires X-Requested-With header",
        )

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require the current user to be an admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
