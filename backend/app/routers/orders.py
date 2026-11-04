"""Заказы покупателя: оформление (FR-08), история (FR-10), отмена."""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db import get_db
from app.models import (
    CartItem,
    Order,
    OrderItem,
    OrderStatusHistory,
    PickupPoint,
    Product,
    ProductVariant,
    StockMovement,
    User,
)
from app.order_service import cancel_order, get_order, load_order, order_detail, order_summary
from app.schemas import ErrorOut, OrderCreateIn, OrderDetail, OrderList, OrderStatus, PickupPointOut
from app.security import get_current_user

router = APIRouter(tags=["orders"])
log = logging.getLogger("kroy.orders")

CUSTOMER_CANCEL_DENIED = {
    "paid": "Оплаченный заказ отменяет только магазин",
    "shipped": "Заказ уже передан в доставку",
    "delivered": "Заказ уже получен",
    "cancelled": "Заказ уже отменён",
}


@router.get("/pickup-points", response_model=list[PickupPointOut])
def list_pickup_points(db: Session = Depends(get_db)) -> list[PickupPoint]:
    return db.scalars(
        select(PickupPoint).where(PickupPoint.is_active).order_by(PickupPoint.name, PickupPoint.id)
    ).all()


def _existing_checkout(db: Session, user_id: int, key: UUID | None) -> Order | None:
    if key is None:
        return None
    return db.scalar(select(Order).where(Order.user_id == user_id, Order.checkout_key == key))


@router.post(
    "/orders",
    response_model=OrderDetail,
    status_code=201,
    responses={200: {"model": OrderDetail}, 401: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
def create_order(
    data: OrderCreateIn,
    response: Response,
    idempotency_key: UUID | None = Header(None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderDetail:
    """Одна транзакция: списать остатки, создать заказ со сроком оплаты, очистить корзину.
    Повтор с тем же Idempotency-Key возвращает уже созданный заказ с кодом 200."""
    existing = _existing_checkout(db, user.id, idempotency_key)
    if existing is not None:
        response.status_code = 200
        return order_detail(load_order(db, existing.id))

    if data.pickup_point_id is not None:
        point = db.get(PickupPoint, data.pickup_point_id)
        if point is None or not point.is_active:
            raise HTTPException(status_code=422, detail="Пункт выдачи не найден")

    # Блокируем корзину: параллельное добавление товара подождёт оформления
    cart = db.scalars(
        select(CartItem)
        .where(CartItem.user_id == user.id)
        .options(selectinload(CartItem.variant).selectinload(ProductVariant.product))
        .order_by(CartItem.variant_id)
        .with_for_update(of=CartItem)
    ).all()
    if not cart:
        raise HTTPException(status_code=409, detail="Корзина пуста")

    total = sum((i.variant.product.price * i.quantity for i in cart), start=0)

    # Варианты списываем по возрастанию id: одинаковый порядок у всех транзакций
    # исключает взаимную блокировку. Условие stock >= qty не даст продать последнюю штуку двоим.
    for item in cart:
        v, p = item.variant, item.variant.product
        left = db.scalar(
            update(ProductVariant)
            .where(
                ProductVariant.id == v.id,
                ProductVariant.is_active,
                ProductVariant.stock >= item.quantity,
                ProductVariant.product_id.in_(select(Product.id).where(Product.is_active)),
            )
            .values(stock=ProductVariant.stock - item.quantity, updated_at=func.now())
            .returning(ProductVariant.stock)
        )
        if left is None:
            db.rollback()
            label = f"«{p.name}» ({v.size}, {v.color})"
            current = db.get(ProductVariant, v.id, populate_existing=True)
            if not current.is_active or not current.product.is_active:
                detail = f"Товар {label} больше не продаётся, удалите его из корзины"
            else:
                detail = f"Недостаточно товара {label}: в наличии {current.stock} шт."
            log.warning("Оформление user=%s: не хватило варианта %s", user.id, v.id)
            raise HTTPException(status_code=409, detail=detail)

    order = Order(
        user_id=user.id,
        status="new",
        total_amount=total,
        delivery_method=data.delivery_method,
        delivery_address=data.delivery_address,
        pickup_point_id=data.pickup_point_id,
        contact_phone=data.contact_phone,
        comment=data.comment,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.order_payment_ttl_minutes),
        checkout_key=idempotency_key,
    )
    db.add(order)
    db.flush()
    for item in cart:
        db.add(
            OrderItem(
                order_id=order.id,
                variant_id=item.variant_id,
                quantity=item.quantity,
                price_at_purchase=item.variant.product.price,
            )
        )
        db.add(
            StockMovement(
                variant_id=item.variant_id, delta=-item.quantity, reason="reserve",
                order_id=order.id, changed_by=user.id,
            )
        )
    db.add(OrderStatusHistory(order_id=order.id, from_status=None, to_status="new", changed_by=user.id))
    db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    try:
        db.commit()
    except IntegrityError:
        # Тот же Idempotency-Key пришёл параллельно и успел первым: отдаём его заказ
        db.rollback()
        existing = _existing_checkout(db, user.id, idempotency_key)
        if existing is None:
            raise
        response.status_code = 200
        return order_detail(load_order(db, existing.id))

    log.info("Заказ %s создан user=%s, позиций %s, сумма %s", order.id, user.id, len(cart), total)
    return order_detail(load_order(db, order.id))


@router.get("/orders", response_model=OrderList)
def list_my_orders(
    status: OrderStatus | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderList:
    cond = [Order.user_id == user.id]
    if status:
        cond.append(Order.status == status)
    total = db.scalar(select(func.count(Order.id)).where(*cond)) or 0
    orders = db.scalars(
        select(Order)
        .where(*cond)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return OrderList(items=[order_summary(o) for o in orders], total=total, limit=limit, offset=offset)


@router.get("/orders/{order_id}", response_model=OrderDetail, responses={404: {"model": ErrorOut}})
def get_my_order(
    order_id: int = Path(ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderDetail:
    # Чужой заказ — 404, а не 403: по ответу нельзя узнать, какие номера существуют
    if get_order(db, order_id, user_id=user.id) is None:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    return order_detail(load_order(db, order_id))


@router.post(
    "/orders/{order_id}/cancel",
    response_model=OrderDetail,
    responses={404: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
def cancel_my_order(
    order_id: int = Path(ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderDetail:
    order = get_order(db, order_id, user_id=user.id, lock=True)
    if order is None:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if order.status != "new":
        raise HTTPException(status_code=409, detail=CUSTOMER_CANCEL_DENIED[order.status])
    cancel_order(db, order, "customer", changed_by=user.id)
    db.commit()
    return order_detail(load_order(db, order_id))
