"""Админка: товары и варианты (FR-13, FR-14), остатки, заказы (FR-15).

Доступ проверяется один раз, зависимостью require_admin на всём роутере (FR-16, NFR-04):
без токена 401, с токеном покупателя 403. Фото товаров — в admin_images.py.
"""

import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Category, Order, Product, ProductImage, ProductVariant, StockMovement, User
from app.order_service import (
    ADMIN_TRANSITIONS,
    admin_order_out,
    admin_order_summary,
    cancel_order,
    change_status,
    customer_short,
    get_order,
    load_order,
    media_url,
)
from app.routers.products import _escape_like
from app.schemas import (
    AdminOrderList,
    AdminOrderOut,
    AdminProductIn,
    AdminProductList,
    AdminProductOut,
    AdminProductPatch,
    AdminVariantIn,
    AdminVariantOut,
    AdminVariantPatch,
    CategoryOut,
    ErrorOut,
    ImageOut,
    OrderStatus,
    OrderStatusChangeIn,
    StockAdjustmentIn,
    StockMovementList,
    StockMovementOut,
)
from app.security import require_admin

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
    responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}},
)
log = logging.getLogger("kroy.admin")


# --- Товары ---


def image_out(img: ProductImage) -> ImageOut:
    return ImageOut(
        id=img.id,
        product_id=img.product_id,
        image_url=media_url(img.storage_key),
        color=img.color,
        sort_order=img.sort_order,
        content_type=img.content_type,
        size_bytes=img.size_bytes,
    )


def product_out(p: Product) -> AdminProductOut:
    return AdminProductOut(
        id=p.id,
        category=CategoryOut.model_validate(p.category),
        name=p.name,
        description=p.description,
        gender=p.gender,
        price=p.price,
        is_active=p.is_active,
        created_at=p.created_at,
        updated_at=p.updated_at,
        variants=[AdminVariantOut.model_validate(v) for v in p.variants],
        images=[image_out(i) for i in p.images],
    )


def _load_product(db: Session, product_id: int) -> Product:
    product = db.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.variants), selectinload(Product.images))
        .execution_options(populate_existing=True)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return product


def _check_category(db: Session, category_id: int) -> None:
    if db.get(Category, category_id) is None:
        raise HTTPException(status_code=404, detail="Категория не найдена")


@router.get("/products", response_model=AdminProductList)
def admin_list_products(
    q: str | None = Query(None, min_length=1, max_length=100),
    category: str | None = Query(None, max_length=80, description="slug категории"),
    is_active: bool | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> AdminProductList:
    def filtered(stmt: Select) -> Select:
        if q:
            stmt = stmt.where(Product.name.ilike(f"%{_escape_like(q)}%", escape="\\"))
        if category:
            stmt = stmt.where(
                Product.category_id.in_(select(Category.id).where(Category.slug == category))
            )
        if is_active is not None:
            stmt = stmt.where(Product.is_active == is_active)
        return stmt

    total = db.scalar(filtered(select(func.count(Product.id)))) or 0
    products = db.scalars(
        filtered(select(Product))
        .options(selectinload(Product.variants), selectinload(Product.images))
        .order_by(Product.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return AdminProductList(
        items=[product_out(p) for p in products], total=total, limit=limit, offset=offset
    )


@router.post(
    "/products", response_model=AdminProductOut, status_code=201, responses={404: {"model": ErrorOut}}
)
def admin_create_product(
    data: AdminProductIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminProductOut:
    _check_category(db, data.category_id)
    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    log.info("Админ %s создал товар %s", admin.id, product.id)
    return product_out(_load_product(db, product.id))


@router.get("/products/{product_id}", response_model=AdminProductOut, responses={404: {"model": ErrorOut}})
def admin_get_product(product_id: int = Path(ge=1), db: Session = Depends(get_db)) -> AdminProductOut:
    return product_out(_load_product(db, product_id))


@router.patch("/products/{product_id}", response_model=AdminProductOut, responses={404: {"model": ErrorOut}})
def admin_update_product(
    data: AdminProductPatch,
    product_id: int = Path(ge=1),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminProductOut:
    """Передаются только меняемые поля. Скрыть товар — is_active false, физически он не удаляется."""
    product = _load_product(db, product_id)
    changes = data.model_dump(exclude_unset=True)
    if "category_id" in changes:
        _check_category(db, changes["category_id"])
    for field, value in changes.items():
        setattr(product, field, value)
    product.updated_at = func.now()
    db.commit()
    log.info("Админ %s изменил товар %s: %s", admin.id, product_id, ", ".join(changes))
    return product_out(_load_product(db, product_id))


# --- Варианты и остатки ---


def _variant_conflict(
    db: Session, product_id: int, size: str, color: str, sku: str, exclude_id: int | None = None
) -> str | None:
    stmt = select(ProductVariant).where(
        or_(
            ProductVariant.sku == sku,
            (ProductVariant.product_id == product_id)
            & (ProductVariant.size == size)
            & (ProductVariant.color == color),
        )
    )
    if exclude_id is not None:
        stmt = stmt.where(ProductVariant.id != exclude_id)
    other = db.scalars(stmt).first()
    if other is None:
        return None
    if other.sku == sku:
        return f"Артикул {sku} уже занят"
    return f"Вариант {size}, {color} у этого товара уже есть"


def _get_variant(db: Session, variant_id: int, lock: bool = False) -> ProductVariant:
    stmt = select(ProductVariant).where(ProductVariant.id == variant_id)
    if lock:
        stmt = stmt.with_for_update()
    variant = db.scalar(stmt)
    if variant is None:
        raise HTTPException(status_code=404, detail="Вариант не найден")
    return variant


@router.post(
    "/products/{product_id}/variants",
    response_model=AdminVariantOut,
    status_code=201,
    responses={404: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
def admin_create_variant(
    data: AdminVariantIn,
    product_id: int = Path(ge=1),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProductVariant:
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    conflict = _variant_conflict(db, product_id, data.size, data.color, data.sku)
    if conflict:
        raise HTTPException(status_code=409, detail=conflict)

    variant = ProductVariant(
        product_id=product_id, size=data.size, color=data.color, sku=data.sku, stock=data.initial_stock
    )
    db.add(variant)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Такой вариант или артикул уже есть")
    if data.initial_stock:
        # Сумма журнала по варианту всегда равна его остатку
        db.add(
            StockMovement(
                variant_id=variant.id, delta=data.initial_stock, reason="initial",
                changed_by=admin.id, comment="Начальный остаток",
            )
        )
    db.commit()
    db.refresh(variant)
    log.info("Админ %s добавил вариант %s к товару %s", admin.id, variant.id, product_id)
    return variant


@router.patch(
    "/variants/{variant_id}",
    response_model=AdminVariantOut,
    responses={404: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
def admin_update_variant(
    data: AdminVariantPatch,
    variant_id: int = Path(ge=1),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProductVariant:
    """Остаток здесь не меняется: для него есть корректировки."""
    variant = _get_variant(db, variant_id)
    changes = data.model_dump(exclude_unset=True)
    size = changes.get("size", variant.size)
    color = changes.get("color", variant.color)
    sku = changes.get("sku", variant.sku)
    conflict = _variant_conflict(db, variant.product_id, size, color, sku, exclude_id=variant.id)
    if conflict:
        raise HTTPException(status_code=409, detail=conflict)
    for field, value in changes.items():
        setattr(variant, field, value)
    variant.updated_at = func.now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Такой вариант или артикул уже есть")
    db.refresh(variant)
    log.info("Админ %s изменил вариант %s: %s", admin.id, variant_id, ", ".join(changes))
    return variant


def movement_out(m: StockMovement, stock_after: int | None = None) -> StockMovementOut:
    return StockMovementOut(
        id=m.id,
        variant_id=m.variant_id,
        delta=m.delta,
        reason=m.reason,
        order_id=m.order_id,
        changed_by=customer_short(m.author),
        comment=m.comment,
        stock_after=stock_after,
        created_at=m.created_at,
    )


@router.post(
    "/variants/{variant_id}/stock-movements",
    response_model=StockMovementOut,
    status_code=201,
    responses={404: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
def admin_adjust_stock(
    data: StockAdjustmentIn,
    variant_id: int = Path(ge=1),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StockMovementOut:
    """Остаток меняется на delta, а не устанавливается числом: правка не затрёт резерв
    покупателя, сделанный в ту же секунду (строка варианта заблокирована)."""
    variant = _get_variant(db, variant_id, lock=True)
    if variant.stock + data.delta < 0:
        raise HTTPException(
            status_code=409,
            detail=f"Нельзя списать {-data.delta} шт.: в наличии {variant.stock} шт.",
        )
    variant.stock += data.delta
    variant.updated_at = func.now()
    movement = StockMovement(
        variant_id=variant.id, delta=data.delta, reason="adjust",
        changed_by=admin.id, comment=data.comment,
    )
    db.add(movement)
    db.commit()
    db.refresh(movement)
    db.refresh(variant)
    log.info("Админ %s: остаток варианта %s %+d, стало %s", admin.id, variant.id, data.delta, variant.stock)
    return movement_out(movement, stock_after=variant.stock)


@router.get(
    "/variants/{variant_id}/stock-movements",
    response_model=StockMovementList,
    responses={404: {"model": ErrorOut}},
)
def admin_list_stock_movements(
    variant_id: int = Path(ge=1),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> StockMovementList:
    _get_variant(db, variant_id)
    cond = StockMovement.variant_id == variant_id
    total = db.scalar(select(func.count(StockMovement.id)).where(cond)) or 0
    movements = db.scalars(
        select(StockMovement)
        .where(cond)
        .options(selectinload(StockMovement.author))
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return StockMovementList(
        items=[movement_out(m) for m in movements], total=total, limit=limit, offset=offset
    )


# --- Заказы ---


@router.get("/orders", response_model=AdminOrderList)
def admin_list_orders(
    status: OrderStatus | None = None,
    user_email: str | None = Query(None, min_length=1, max_length=255, description="Часть email покупателя"),
    date_from: date | None = Query(None, examples=["2026-11-01"]),
    date_to: date | None = Query(None, examples=["2026-11-30"]),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> AdminOrderList:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from не может быть позже date_to")

    def filtered(stmt: Select) -> Select:
        stmt = stmt.join(User, User.id == Order.user_id)
        if status:
            stmt = stmt.where(Order.status == status)
        if user_email:
            stmt = stmt.where(User.email.ilike(f"%{_escape_like(user_email)}%", escape="\\"))
        # Границы — даты по времени сервера БД, date_to включительно
        if date_from:
            stmt = stmt.where(Order.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Order.created_at < date_to + timedelta(days=1))
        return stmt

    total = db.scalar(filtered(select(func.count(Order.id)))) or 0
    orders = db.scalars(
        filtered(select(Order))
        .options(selectinload(Order.items), selectinload(Order.user))
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return AdminOrderList(
        items=[admin_order_summary(o) for o in orders], total=total, limit=limit, offset=offset
    )


@router.get("/orders/{order_id}", response_model=AdminOrderOut, responses={404: {"model": ErrorOut}})
def admin_get_order(order_id: int = Path(ge=1), db: Session = Depends(get_db)) -> AdminOrderOut:
    if get_order(db, order_id) is None:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    return admin_order_out(load_order(db, order_id))


@router.post(
    "/orders/{order_id}/status",
    response_model=AdminOrderOut,
    responses={404: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
def admin_change_order_status(
    data: OrderStatusChangeIn,
    order_id: int = Path(ge=1),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminOrderOut:
    order = get_order(db, order_id, lock=True)
    if order is None:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if data.status not in ADMIN_TRANSITIONS.get(order.status, set()):
        log.warning("Админ %s: недопустимый переход заказа %s %s -> %s",
                    admin.id, order.id, order.status, data.status)
        raise HTTPException(
            status_code=409,
            detail=f"Нельзя перевести заказ из статуса {order.status} в {data.status}",
        )
    if data.status == "cancelled":
        cancel_order(db, order, "admin", changed_by=admin.id, comment=data.comment)
    else:
        change_status(db, order, data.status, changed_by=admin.id, comment=data.comment)
        log.info("Админ %s перевёл заказ %s в %s", admin.id, order.id, data.status)
    db.commit()
    return admin_order_out(load_order(db, order_id))
