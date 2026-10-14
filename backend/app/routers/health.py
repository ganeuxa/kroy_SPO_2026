import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter(tags=["service"])
log = logging.getLogger("kroy.health")


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """Жив ли сервер и есть ли связь с БД. Используется в healthcheck контейнера."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        log.warning("health: база данных недоступна")
        return JSONResponse(status_code=503, content={"status": "error", "db": "unavailable"})
    return {"status": "ok", "db": "ok"}
