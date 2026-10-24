"""Пароли (bcrypt) и токены входа (JWT) для FR-01, FR-02."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User

# auto_error=False: без заголовка отвечаем своим 401 с понятным текстом, а не 403 FastAPI
bearer = HTTPBearer(auto_error=False, description="Токен из /api/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode()
    if len(raw) > 72:
        # bcrypt молча обрезает до 72 байт, и «пароль+x» совпал бы с исходным.
        # Такие пароли при регистрации не принимаются, значит и подойти не могут
        return False
    try:
        return bcrypt.checkpw(raw, password_hash.encode())
    except ValueError:
        # Хэш в БД испорчен или не bcrypt: считаем, что пароль не подошёл
        return False


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Зависимость для защищённых маршрутов: пользователь из токена Authorization: Bearer."""
    if credentials is None:
        raise _unauthorized("Требуется вход")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp"]},
        )
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Срок действия входа истёк, войдите снова")
    except (jwt.InvalidTokenError, ValueError):
        raise _unauthorized("Недействительный токен")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Пользователь не найден или заблокирован")
    return user
