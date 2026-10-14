import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError

from app.config import settings
from app.routers import health, products

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("kroy")

app = FastAPI(
    title="Крой API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.include_router(health.router, prefix="/api")
app.include_router(products.router, prefix="/api")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Одна строка лога на запрос: метод, путь, код ответа, время.
    Тело запроса и заголовки не пишем, чтобы в лог не попали пароли и токены."""
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, ms)
    return response


@app.exception_handler(OperationalError)
@app.exception_handler(InterfaceError)
async def db_unavailable(request: Request, exc: Exception):
    log.error("Ошибка БД на %s %s: %s", request.method, request.url.path, exc.__class__.__name__)
    return JSONResponse(
        status_code=503,
        content={"detail": "База данных недоступна, попробуйте позже"},
    )


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    log.exception("Необработанная ошибка на %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Внутренняя ошибка сервера"})
