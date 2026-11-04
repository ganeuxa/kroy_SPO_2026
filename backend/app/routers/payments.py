"""Оплата заказа (FR-09, NFR-09) через тестовый платёжный сервис.

Номер карты на наш сервер не приходит: покупатель вводит его на странице сервиса
(confirmation_url), а сервис присылает только результат. В тестовом режиме роль
уведомления играет POST /api/test-provider/payments/{provider_payment_id}.
"""

import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Order, Payment, User
from app.order_service import cancel_order, change_status, get_order, is_expired, payment_out
from app.schemas import ErrorOut, PaymentOut, TestProviderResultIn
from app.security import get_current_user

router = APIRouter(tags=["payments"])
log = logging.getLogger("kroy.payments")

EXPIRED = "Срок оплаты истёк, заказ отменён"


def _not_payable(order: Order) -> str | None:
    if order.status == "cancelled":
        return EXPIRED if order.cancel_reason == "expired" else "Заказ отменён"
    if order.status != "new":
        return "Заказ уже оплачен"
    return None


def _payment_by_key(db: Session, order_id: int, key: UUID) -> Payment | None:
    return db.scalar(
        select(Payment).where(Payment.order_id == order_id, Payment.idempotency_key == key)
    )


@router.post(
    "/orders/{order_id}/payments",
    response_model=PaymentOut,
    status_code=201,
    responses={200: {"model": PaymentOut}, 404: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
def create_payment(
    response: Response,
    order_id: int = Path(ge=1),
    idempotency_key: UUID = Header(alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentOut:
    # Блокировка заказа: фоновая отмена по сроку и второй запрос оплаты подождут
    order = get_order(db, order_id, user_id=user.id, lock=True)
    if order is None:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    repeat = _payment_by_key(db, order.id, idempotency_key)
    if repeat is not None:
        log.warning("Повтор оплаты заказа %s с тем же ключом, платёж %s", order.id, repeat.id)
        response.status_code = 200
        return payment_out(repeat)

    if is_expired(order):
        cancel_order(db, order, "expired", changed_by=None, comment="Не оплачен вовремя")
        db.commit()
        raise HTTPException(status_code=409, detail=EXPIRED)
    reason = _not_payable(order)
    if reason:
        raise HTTPException(status_code=409, detail=reason)

    payment = Payment(
        order_id=order.id,
        provider_payment_id=str(uuid4()),
        amount=order.total_amount,
        status="pending",
        idempotency_key=idempotency_key,
        provider=settings.payment_provider,
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        repeat = _payment_by_key(db, order_id, idempotency_key)
        if repeat is not None:
            response.status_code = 200
            return payment_out(repeat)
        # Частичный уникальный индекс: на заказ только один pending-платёж
        raise HTTPException(status_code=409, detail="Оплата уже начата в другой вкладке")
    db.refresh(payment)
    log.info("Платёж %s создан для заказа %s", payment.id, order.id)
    return payment_out(payment)


@router.get("/payments/{payment_id}", response_model=PaymentOut, responses={404: {"model": ErrorOut}})
def get_payment(
    payment_id: int = Path(ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentOut:
    payment = db.scalar(
        select(Payment)
        .join(Order, Order.id == Payment.order_id)
        .where(Payment.id == payment_id, Order.user_id == user.id)
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="Платёж не найден")
    return payment_out(payment)


@router.post(
    "/test-provider/payments/{provider_payment_id}",
    response_model=PaymentOut,
    responses={404: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
def test_provider_complete(
    data: TestProviderResultIn,
    provider_payment_id: UUID,
    db: Session = Depends(get_db),
) -> PaymentOut:
    """Эмулятор уведомления платёжного сервиса. Повторное уведомление ничего не меняет."""
    if settings.payment_provider != "test":
        raise HTTPException(status_code=404, detail="Не найдено")

    found = db.scalar(select(Payment).where(Payment.provider_payment_id == str(provider_payment_id)))
    if found is None:
        raise HTTPException(status_code=404, detail="Платёж не найден")
    # Порядок блокировок как у остальных: сначала заказ, потом платёж
    order = get_order(db, found.order_id, lock=True)
    payment = db.scalar(select(Payment).where(Payment.id == found.id).with_for_update())

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
    reason = _not_payable(order)
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
