"""Регистрация (FR-01), вход (FR-02) и текущий пользователь."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import ErrorOut, LoginIn, RegisterIn, TokenOut, UserOut
from app.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("kroy.auth")

EMAIL_TAKEN = "Пользователь с таким email уже зарегистрирован"


def _find_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email.lower()))


@router.post(
    "/register",
    response_model=TokenOut,
    status_code=201,
    responses={409: {"model": ErrorOut}},
)
def register(data: RegisterIn, db: Session = Depends(get_db)) -> TokenOut:
    email = data.email.lower()
    if _find_by_email(db, email) is not None:
        raise HTTPException(status_code=409, detail=EMAIL_TAKEN)

    user = User(
        email=email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Два одновременных запроса с одним email: второй упрётся в UNIQUE
        db.rollback()
        raise HTTPException(status_code=409, detail=EMAIL_TAKEN)
    db.refresh(user)

    log.info("Зарегистрирован пользователь id=%s", user.id)
    return TokenOut(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut, responses={401: {"model": ErrorOut}})
def login(data: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = _find_by_email(db, data.email)
    # Одно сообщение для «нет такого email» и «неверный пароль»,
    # чтобы по ответу нельзя было узнать, зарегистрирован ли адрес
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Учётная запись заблокирована")
    return TokenOut(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut, responses={401: {"model": ErrorOut}})
def me(user: User = Depends(get_current_user)) -> User:
    return user
