"""Фото товаров в админке (FR-13). Доступ — только администратор, как у всего /api/admin."""

import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Product, ProductImage, ProductVariant, User
from app.routers.admin import image_out
from app.schemas import ErrorOut, ImageOut, ImagePatch
from app.security import require_admin
from app.storage import StorageUnavailable, put_object, remove_object

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
    responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}, 404: {"model": ErrorOut}},
)
log = logging.getLogger("kroy.admin")

MAX_SIZE = 5 * 1024 * 1024
STORAGE_DOWN = "Хранилище фото недоступно, попробуйте позже"


def _detect_type(head: bytes) -> tuple[str, str] | None:
    """Тип по сигнатуре файла, а не по расширению или заголовку от клиента."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


def _check_color(db: Session, product_id: int, color: str | None) -> None:
    if color is None:
        return
    exists = db.scalar(
        select(ProductVariant.id).where(ProductVariant.product_id == product_id, ProductVariant.color == color)
    )
    if exists is None:
        raise HTTPException(status_code=422, detail=f"У товара нет варианта цвета «{color}»")


def _get_image(db: Session, image_id: int) -> ProductImage:
    image = db.get(ProductImage, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Фото не найдено")
    return image


@router.post(
    "/products/{product_id}/images",
    response_model=ImageOut,
    status_code=201,
    responses={413: {"model": ErrorOut}, 415: {"model": ErrorOut}, 503: {"model": ErrorOut}},
)
def admin_upload_image(
    product_id: int = Path(ge=1),
    file: UploadFile = File(...),
    color: str | None = Form(None, max_length=40),
    sort_order: int = Form(0, ge=0, le=100),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ImageOut:
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    color = color.strip() if color and color.strip() else None
    _check_color(db, product_id, color)

    data = file.file.read(MAX_SIZE + 1)
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Файл больше 5 МБ")
    detected = _detect_type(data[:12]) if data else None
    if detected is None:
        raise HTTPException(status_code=415, detail="Поддерживаются только JPEG, PNG и WebP")
    content_type, ext = detected

    key = f"products/{product_id}/{uuid.uuid4().hex}.{ext}"
    try:
        put_object(key, data, content_type)
    except StorageUnavailable:
        raise HTTPException(status_code=503, detail=STORAGE_DOWN)

    image = ProductImage(
        product_id=product_id, storage_key=key, color=color, sort_order=sort_order,
        content_type=content_type, size_bytes=len(data),
    )
    db.add(image)
    try:
        db.commit()
    except Exception:
        # Строка не записалась: файл без ссылки на него не оставляем
        db.rollback()
        remove_object(key)
        raise
    db.refresh(image)
    log.info("Админ %s загрузил фото %s к товару %s (%s байт)", admin.id, image.id, product_id, len(data))
    return image_out(image)


@router.patch("/images/{image_id}", response_model=ImageOut)
def admin_update_image(
    data: ImagePatch,
    image_id: int = Path(ge=1),
    db: Session = Depends(get_db),
) -> ImageOut:
    image = _get_image(db, image_id)
    changes = data.model_dump(exclude_unset=True)
    if "color" in changes:
        _check_color(db, image.product_id, changes["color"])
    for field, value in changes.items():
        setattr(image, field, value)
    db.commit()
    db.refresh(image)
    return image_out(image)


@router.delete("/images/{image_id}", status_code=204)
def admin_delete_image(
    image_id: int = Path(ge=1),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    image = _get_image(db, image_id)
    key = image.storage_key
    db.delete(image)
    db.commit()
    remove_object(key)
    log.info("Админ %s удалил фото %s", admin.id, image_id)
    return Response(status_code=204)
