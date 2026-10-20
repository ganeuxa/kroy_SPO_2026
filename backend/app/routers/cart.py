"""Корзина (FR-07). Только для вошедших пользователей."""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.models import CartItem, Product, ProductVariant, User
from app.schemas import CartAddIn, CartItemOut, CartOut, ErrorOut
from app.security import get_current_user

router = APIRouter(prefix="/cart", tags=["cart"], responses={401: {"model": ErrorOut}})
log = logging.getLogger("kroy.cart")

# Больше этого количества одного варианта в корзину не кладём
MAX_QUANTITY = 99


def _load_cart(db: Session, user_id: int) -> CartOut:
    items = db.scalars(
        select(CartItem)
        .where(CartItem.user_id == user_id)
        .options(
            joinedload(CartItem.variant)
            .joinedload(ProductVariant.product)
            .selectinload(Product.images)
        )
        .order_by(CartItem.added_at, CartItem.id)
    ).unique().all()

    out = []
    for item in items:
        v = item.variant
        p = v.product
        out.append(
            CartItemOut(
                id=item.id,
                variant_id=v.id,
                product_id=p.id,
                name=p.name,
                size=v.size,
                color=v.color,
                sku=v.sku,
                image_key=p.images[0].storage_key if p.images else None,
                price=p.price,
                quantity=item.quantity,
                stock=v.stock,
                line_total=p.price * item.quantity,
            )
        )
    return CartOut(
        items=out,
        total_quantity=sum(i.quantity for i in out),
        total=sum((i.line_total for i in out), Decimal("0.00")),
    )


@router.get("", response_model=CartOut)
def get_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CartOut:
    return _load_cart(db, user.id)


@router.post(
    "",
    response_model=CartOut,
    responses={404: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
def add_to_cart(
    data: CartAddIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartOut:
    """Добавляет вариант товара в корзину. Если он уже там, увеличивает количество."""
    # FOR UPDATE: два одновременных добавления одного варианта не проскочат мимо проверки остатка
    variant = db.scalar(
        select(ProductVariant).where(ProductVariant.id == data.variant_id).with_for_update()
    )
    if variant is None or not variant.product.is_active:
        raise HTTPException(status_code=404, detail="Товар не найден")

    item = db.scalar(
        select(CartItem).where(CartItem.user_id == user.id, CartItem.variant_id == variant.id)
    )
    in_cart = item.quantity if item else 0
    quantity = in_cart + data.quantity

    if quantity > MAX_QUANTITY:
        raise HTTPException(
            status_code=409,
            detail=f"Не больше {MAX_QUANTITY} шт. одного товара в корзине",
        )
    if quantity > variant.stock:
        detail = f"Недостаточно товара: в наличии {variant.stock} шт."
        if in_cart:
            detail += f", в корзине уже {in_cart} шт."
        raise HTTPException(status_code=409, detail=detail)

    if item:
        item.quantity = quantity
    else:
        db.add(CartItem(user_id=user.id, variant_id=variant.id, quantity=quantity))
    db.commit()

    log.info("Корзина user=%s: вариант %s, количество %s", user.id, variant.id, quantity)
    return _load_cart(db, user.id)
