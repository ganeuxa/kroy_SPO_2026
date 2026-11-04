"""Модели таблиц из db/01_schema.sql.

Схему создают SQL-скрипт и миграции из db/migrations, а не SQLAlchemy:
модели только описывают уже существующие таблицы. favorites и reviews
появятся на этапе IV.
"""

from datetime import datetime
from decimal import Decimal

from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(String(16), server_default=text("'customer'"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    gender: Mapped[str] = mapped_column(String(10))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    category: Mapped[Category] = relationship(lazy="joined")
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", order_by="ProductVariant.id"
    )
    images: Mapped[list["ProductImage"]] = relationship(
        order_by="ProductImage.sort_order"
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    size: Mapped[str] = mapped_column(String(10))
    color: Mapped[str] = mapped_column(String(40))
    sku: Mapped[str] = mapped_column(String(40), unique=True)
    stock: Mapped[int] = mapped_column(server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    product: Mapped[Product] = relationship(back_populates="variants")


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    storage_key: Mapped[str] = mapped_column(String(255))
    color: Mapped[str | None] = mapped_column(String(40))
    sort_order: Mapped[int] = mapped_column(server_default=text("0"))
    content_type: Mapped[str | None] = mapped_column(String(32))
    size_bytes: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"))
    quantity: Mapped[int]
    added_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    variant: Mapped[ProductVariant] = relationship(lazy="joined")


class PickupPoint(Base):
    __tablename__ = "pickup_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(300), unique=True)
    hours: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'new'"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    delivery_method: Mapped[str] = mapped_column(String(16))
    delivery_address: Mapped[str | None] = mapped_column(String(300))
    pickup_point_id: Mapped[int | None] = mapped_column(ForeignKey("pickup_points.id"))
    contact_phone: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(String(500))
    expires_at: Mapped[datetime | None]
    cancel_reason: Mapped[str | None] = mapped_column(String(16))
    checkout_key: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    user: Mapped[User] = relationship()
    pickup_point: Mapped[PickupPoint | None] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(order_by="OrderItem.id")
    payments: Mapped[list["Payment"]] = relationship(order_by="Payment.id")
    history: Mapped[list["OrderStatusHistory"]] = relationship(
        order_by="OrderStatusHistory.id"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"))
    quantity: Mapped[int]
    price_at_purchase: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    variant: Mapped[ProductVariant] = relationship()


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    provider_payment_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'pending'"))
    idempotency_key: Mapped[UUID | None]
    provider: Mapped[str] = mapped_column(String(16), server_default=text("'test'"))
    failure_reason: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    paid_at: Mapped[datetime | None]


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16))
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    author: Mapped[User | None] = relationship()


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"))
    delta: Mapped[int]
    reason: Mapped[str] = mapped_column(String(16))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    author: Mapped[User | None] = relationship()
