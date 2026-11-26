"""Payment notification transaction. Lock order: order, then payment.

Read only identifiers before locking, never a potentially stale Payment entity.
First terminal result wins. Caller receives the persisted terminal result on repeats.
"""
import logging
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models import Order, Payment
from app.order_service import cancel_order, change_status, get_order, is_expired, payment_out
from app.schemas import PaymentOut, TestProviderResultIn

log = logging.getLogger("kroy.payments")
EXPIRED = "Срок оплаты истёк, заказ отменён"

def not_payable(order: Order) -> str | None:
    if order.status == "cancelled":
        return EXPIRED if order.cancel_reason == "expired" else "Заказ отменён"
    if order.status != "new":
        return "Заказ уже оплачен"
    return None


def process_notification(data: TestProviderResultIn, provider_payment_id: UUID, db: Session) -> PaymentOut:
    found = db.execute(
        select(Payment.id, Payment.order_id)
        .where(Payment.provider_payment_id == str(provider_payment_id))
    ).first()
    if found is None:
        raise HTTPException(status_code=404, detail="Платёж не найден")
    # Порядок блокировок как у остальных: сначала заказ, потом платёж
    order = get_order(db, found.order_id, lock=True)
    payment = db.scalar(
        select(Payment).where(Payment.id == found.id).with_for_update()
        .execution_options(populate_existing=True)
    )

    if payment.status != "pending":
        return payment_out(payment)

    if data.result == "failed":
        payment.status = "failed"
        payment.failure_reason = data.failure_reason or "Платёж отклонён"
        db.commit()
        log.info("Платёж %s отклонён, заказ %s ждёт новой попытки", payment.id, order.id)
        return payment_out(payment)

    if is_expired(order):
        cancel_order(db, order, "expired", changed_by=None, comment="Не оплачен вовремя")
        db.commit()
        raise HTTPException(status_code=409, detail=EXPIRED)
    reason = not_payable(order)
    if reason:
        payment.status = "cancelled"
        db.commit()
        raise HTTPException(status_code=409, detail=reason)

    payment.status = "succeeded"
    payment.paid_at = func.now()
    change_status(db, order, "paid", changed_by=None, comment=f"Платёж №{payment.id}")
    db.commit()
    db.refresh(payment)
    log.info("Платёж %s успешен, заказ %s оплачен", payment.id, order.id)
    return payment_out(payment)
