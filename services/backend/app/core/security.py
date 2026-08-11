"""
Digital Campus - Security Utilities
"""

from datetime import UTC, datetime, timedelta

from fastapi import Response
from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HttpOnly session cookie: holds the same JWT as the Bearer scheme. The
# frontend never touches it — it is sent automatically with every same-origin
# request (the Next.js proxy forwards it to the API).
AUTH_COOKIE_NAME = "dc_access_token"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
    user_id: int | None = None,
) -> str:
    to_encode = data.copy()
    if user_id is not None:
        to_encode["user_id"] = int(user_id)
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _cookie_secure() -> bool:
    return settings.APP_ENV == "production"


def set_auth_cookie(response: Response, token: str) -> None:
    """Attach the JWT as an HttpOnly, SameSite=Lax cookie."""
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )
