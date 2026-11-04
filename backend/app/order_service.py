"""Общая логика заказов: смена статуса, отмена с возвратом остатка, сборка ответа.

Используется покупательскими методами, админкой, оплатой и фоновой отменой
просроченных заказов. Алгоритм: docs/stage3/db-design.md, разделы 2 и 3.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Order,
    OrderItem,
    OrderStatusHistory,
    Payment,
    Product,
    ProductVariant,
    StockMovement,
    User,
)
from app.schemas import (
    AdminOrderOut,
    AdminOrderSummary,
    CustomerShort,
    OrderDetail,
    OrderItemOut,
    OrderSummary,
    PaymentOut,
    PickupPointOut,
    StatusChangeOut,
)

log = logging.getLogger("kroy.orders")

# Какие переходы может сделать администратор (FR-15). В paid переводит только оплата.
ADMIN_TRANSITIONS = {
    "new": {"cancelled"},
    "paid": {"shipped", "cancelled"},
    "shipped": {"delivered"},
}


def media_url(storage_key: str | None) -> str | None:
    return f"/media/{storage_key}" if storage_key else None


def order_options():
    """Всё, что нужно для полного ответа по заказу, одним набором запросов без N+1."""
    return (
        selectinload(Order.items)
        .selectinload(OrderItem.variant)
        .selectinload(ProductVariant.product)
        .selectinload(Product.images),
        selectinload(Order.payments),
        selectinload(Order.history).selectinload(OrderStatusHistory.author),
        selectinload(Order.pickup_point),
        selectinload(Order.user),
    )


def get_order(db: Session, order_id: int, user_id: int | None = None, lock: bool = False) -> Order | None:
    """Заказ по id. С user_id — только заказ этого покупателя (чужой не найдётся)."""
    stmt = select(Order).where(Order.id == order_id)
    if user_id is not None:
        stmt = stmt.where(Order.user_id == user_id)
    if lock:
        stmt = stmt.with_for_update(of=Order)
    return db.scalar(stmt)


def load_order(db: Session, order_id: int) -> Order:
    return db.scalars(
        select(Order).where(Order.id == order_id).options(*order_options()).execution_options(
            populate_existing=True
        )
    ).one()


def change_status(
    db: Session, order: Order, to_status: str, changed_by: int | None, comment: str | None = None
) -> None:
    db.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=order.status,
            to_status=to_status,
            changed_by=changed_by,
            comment=comment,
        )
    )
    order.status = to_status
    order.updated_at = func.now()


def release_stock(db: Session, order: Order, changed_by: int | None) -> None:
    """Возвращает на склад ровно то, что было списано под заказ, по журналу.
    Повторный вызов ничего не вернёт: сумма по заказу уже будет 0."""
    reserved = db.execute(
        select(StockMovement.variant_id, func.sum(StockMovement.delta))
        .where(StockMovement.order_id == order.id)
        .group_by(StockMovement.variant_id)
        .having(func.sum(StockMovement.delta) < 0)
        .order_by(StockMovement.variant_id)
    ).all()
    for variant_id, total in reserved:
        qty = -int(total)
        db.execute(
            update(ProductVariant)
            .where(ProductVariant.id == variant_id)
            .values(stock=ProductVariant.stock + qty, updated_at=func.now())
        )
        db.add(
            StockMovement(
                variant_id=variant_id, delta=qty, reason="release",
                order_id=order.id, changed_by=changed_by,
            )
        )


def cancel_order(
    db: Session, order: Order, reason: str, changed_by: int | None, comment: str | None = None
) -> None:
    """Отмена уже заблокированного (FOR UPDATE) заказа. Коммит делает вызывающий."""
    release_stock(db, order, changed_by)
    db.execute(
        update(Payment)
        .where(Payment.order_id == order.id, Payment.status == "pending")
        .values(status="cancelled")
    )
    change_status(db, order, "cancelled", changed_by, comment)
    order.cancel_reason = reason
    log.info("Заказ %s отменён, причина %s", order.id, reason)


def is_expired(order: Order) -> bool:
    return (
        order.status == "new"
        and order.expires_at is not None
        and order.expires_at <= datetime.now(timezone.utc)
    )


def expire_orders(db: Session, batch: int = 50) -> int:
    """Отменяет неоплаченные заказы с истёкшим сроком. SKIP LOCKED: несколько копий
    backend не возьмут один заказ, а заказ, который сейчас оплачивают, пропускается."""
    orders = db.scalars(
        select(Order)
        .where(Order.status == "new", Order.expires_at < func.now())
        .order_by(Order.expires_at)
        .limit(batch)
        .with_for_update(skip_locked=True)
    ).all()
    for order in orders:
        cancel_order(db, order, "expired", changed_by=None, comment="Не оплачен вовремя")
    db.commit()
    return len(orders)


# --- Сборка ответов ---


def payment_out(p: Payment) -> PaymentOut:
    return PaymentOut(
        id=p.id,
        order_id=p.order_id,
        status=p.status,
        amount=p.amount,
        confirmation_url=f"/pay/test/{p.provider_payment_id}"
        if p.status == "pending" and p.provider_payment_id
        else None,
        failure_reason=p.failure_reason,
        created_at=p.created_at,
        paid_at=p.paid_at,
    )


def _changed_by(h: OrderStatusHistory) -> str:
    if h.author is None:
        return "system"
    return "admin" if h.author.role == "admin" else "customer"


def _summary_fields(order: Order) -> dict:
    return dict(
        id=order.id,
        status=order.status,
        total_amount=order.total_amount,
        items_count=sum(i.quantity for i in order.items),
        delivery_method=order.delivery_method,
        created_at=order.created_at,
        expires_at=order.expires_at if order.status == "new" else None,
    )


def _detail_fields(order: Order) -> dict:
    items = []
    for i in order.items:
        v = i.variant
        p = v.product
        items.append(
            OrderItemOut(
                variant_id=v.id,
                product_id=p.id,
                name=p.name,
                size=v.size,
                color=v.color,
                sku=v.sku,
                image_url=media_url(p.images[0].storage_key) if p.images else None,
                quantity=i.quantity,
                price=i.price_at_purchase,
                line_total=i.price_at_purchase * i.quantity,
            )
        )
    return dict(
        _summary_fields(order),
        delivery_address=order.delivery_address,
        pickup_point=PickupPointOut.model_validate(order.pickup_point) if order.pickup_point else None,
        contact_phone=order.contact_phone,
        comment=order.comment,
        cancel_reason=order.cancel_reason,
        items=items,
        payments=[payment_out(p) for p in order.payments],
        history=[
            StatusChangeOut(
                from_status=h.from_status,
                to_status=h.to_status,
                changed_by=_changed_by(h),
                comment=h.comment,
                created_at=h.created_at,
            )
            for h in order.history
        ],
    )


def order_summary(order: Order) -> OrderSummary:
    return OrderSummary(**_summary_fields(order))


def order_detail(order: Order) -> OrderDetail:
    return OrderDetail(**_detail_fields(order))


def admin_order_summary(order: Order) -> AdminOrderSummary:
    return AdminOrderSummary(**_summary_fields(order), customer=CustomerShort.model_validate(order.user))


def admin_order_out(order: Order) -> AdminOrderOut:
    return AdminOrderOut(**_detail_fields(order), customer=CustomerShort.model_validate(order.user))


def customer_short(user: User | None) -> CustomerShort | None:
    return CustomerShort.model_validate(user) if user else None
