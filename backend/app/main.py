import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from sqlalchemy.exc import InterfaceError, OperationalError

from app.config import settings
from app.db import SessionLocal
from app.order_service import expire_orders
from app.schemas import ErrorOut
from app.routers import admin, admin_images, auth, cart, health, orders, payments, products

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("kroy")


def _expire_once() -> int:
    with SessionLocal() as db:
        return expire_orders(db)


async def _expire_orders_loop() -> None:
    """Раз в минуту отменяет неоплаченные заказы с истёкшим сроком и возвращает остаток."""
    while True:
        try:
            count = await asyncio.to_thread(_expire_once)
            if count:
                log.info("Отменено просроченных заказов: %s", count)
        except Exception:
            # БД может быть недоступна: задача не падает, а пробует снова через минуту
            log.exception("Фоновая отмена просроченных заказов не удалась")
        await asyncio.sleep(settings.expire_orders_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_expire_orders_loop())
    yield
    task.cancel()


app = FastAPI(
    title="Крой API",
    version="0.4.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
    responses={503: {"model": ErrorOut, "description": "База данных недоступна"}},
)

app.include_router(health.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(cart.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(admin_images.router, prefix="/api")


def openapi_schema():
    """Document shared auth errors and both real shapes of validation errors."""
    if app.openapi_schema is None:
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        for path, operations in schema["paths"].items():
            for operation in operations.values():
                if not isinstance(operation, dict) or "responses" not in operation:
                    continue
                responses = operation["responses"]
                if operation.get("security"):
                    responses.setdefault("401", {"description": "Требуется действующий токен",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorOut"}}}})
                if path.startswith("/api/admin/"):
                    responses.setdefault("403", {"description": "Недостаточно прав",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorOut"}}}})
                if "422" in responses:
                    responses["422"] = {"description": "Ошибка полей или бизнес-валидации",
                        "content": {"application/json": {"schema": {"anyOf": [
                            {"$ref": "#/components/schemas/HTTPValidationError"},
                            {"$ref": "#/components/schemas/ErrorOut"},
                        ]}}}}
        app.openapi_schema = schema
    return app.openapi_schema


app.openapi = openapi_schema


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
