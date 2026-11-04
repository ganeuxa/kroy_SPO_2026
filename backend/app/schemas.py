"""Форматы ответов API (Pydantic)."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    size: str
    color: str
    sku: str
    stock: int
    in_stock: bool


class ProductListItem(BaseModel):
    id: int
    name: str
    price: Decimal
    gender: str
    category: CategoryOut
    image_key: str | None
    image_url: str | None
    in_stock: bool


class ProductList(BaseModel):
    items: list[ProductListItem]
    total: int
    limit: int
    offset: int


class ProductDetail(BaseModel):
    id: int
    name: str
    description: str | None
    price: Decimal
    gender: str
    category: CategoryOut
    image_keys: list[str]
    image_urls: list[str]
    variants: list[VariantOut]


class Filters(BaseModel):
    """Значения для выпадающих списков фильтров каталога."""

    categories: list[CategoryOut]
    sizes: list[str]
    colors: list[str]
    price_min: Decimal | None
    price_max: Decimal | None


class ErrorOut(BaseModel):
    detail: str


# --- Регистрация и вход (FR-01, FR-02) ---


class RegisterIn(BaseModel):
    email: EmailStr = Field(max_length=255)
    # bcrypt учитывает только первые 72 байта, длиннее не принимаем
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(None, pattern=r"^\+?[0-9]{10,15}$", examples=["+79001112233"])

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Имя не может быть пустым")
        return v

    @field_validator("password")
    @classmethod
    def password_bytes(cls, v: str) -> str:
        if len(v.encode()) > 72:
            raise ValueError("Пароль слишком длинный")
        return v


class LoginIn(BaseModel):

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str | None
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Корзина (FR-07) ---


class CartAddIn(BaseModel):
    variant_id: int = Field(ge=1)
    quantity: int = Field(1, ge=1, le=99)


class CartItemOut(BaseModel):
    id: int
    variant_id: int
    product_id: int
    name: str
    size: str
    color: str
    sku: str
    image_key: str | None
    image_url: str | None
    price: Decimal
    quantity: int
    stock: int
    line_total: Decimal


class CartOut(BaseModel):
    items: list[CartItemOut]
    total_quantity: int
    total: Decimal


class CartUpdateIn(BaseModel):
    quantity: int = Field(ge=1, le=99)


# --- Заказы и оплата (FR-08…FR-10) ---

PHONE_PATTERN = r"^\+?[0-9]{10,15}$"
OrderStatus = Literal["new", "paid", "shipped", "delivered", "cancelled"]
DeliveryMethod = Literal["courier", "pickup"]
CancelReason = Literal["customer", "expired", "admin", "payment_failed"]


class PickupPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str
    hours: str | None


class OrderCreateIn(BaseModel):
    delivery_method: DeliveryMethod
    delivery_address: str | None = Field(None, max_length=300)
    pickup_point_id: int | None = Field(None, ge=1)
    contact_phone: str = Field(pattern=PHONE_PATTERN, examples=["+79001112233"])
    comment: str | None = Field(None, max_length=500)

    @field_validator("delivery_address", "comment")
    @classmethod
    def strip_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip() or None

    @model_validator(mode="after")
    def check_delivery(self) -> "OrderCreateIn":
        if self.delivery_method == "courier":
            if not self.delivery_address or len(self.delivery_address) < 5:
                raise ValueError("Для доставки курьером укажите адрес (не короче 5 символов)")
            if self.pickup_point_id is not None:
                raise ValueError("Для доставки курьером пункт выдачи не указывается")
        else:
            if self.pickup_point_id is None:
                raise ValueError("Для самовывоза выберите пункт выдачи")
            if self.delivery_address is not None:
                raise ValueError("Для самовывоза адрес не указывается")
        return self


class OrderItemOut(BaseModel):
    variant_id: int
    product_id: int
    name: str
    size: str
    color: str
    sku: str
    image_url: str | None
    quantity: int
    price: Decimal
    line_total: Decimal


class StatusChangeOut(BaseModel):
    from_status: OrderStatus | None
    to_status: OrderStatus
    changed_by: Literal["customer", "admin", "system"]
    comment: str | None
    created_at: datetime


class PaymentOut(BaseModel):
    id: int
    order_id: int
    status: Literal["pending", "succeeded", "failed", "cancelled"]
    amount: Decimal
    confirmation_url: str | None
    failure_reason: str | None
    created_at: datetime
    paid_at: datetime | None


class OrderSummary(BaseModel):
    id: int
    status: OrderStatus
    total_amount: Decimal
    items_count: int
    delivery_method: DeliveryMethod
    created_at: datetime
    expires_at: datetime | None


class OrderDetail(OrderSummary):
    delivery_address: str | None
    pickup_point: PickupPointOut | None
    contact_phone: str
    comment: str | None
    cancel_reason: CancelReason | None
    items: list[OrderItemOut]
    payments: list[PaymentOut]
    history: list[StatusChangeOut]


class OrderList(BaseModel):
    items: list[OrderSummary]
    total: int
    limit: int
    offset: int


class TestProviderResultIn(BaseModel):
    result: Literal["succeeded", "failed"]
    failure_reason: str | None = Field(None, max_length=120)


# --- Админка (FR-13…FR-16) ---

Gender = Literal["men", "women", "unisex"]
SKU_PATTERN = r"^[A-Z0-9-]{3,40}$"


def _no_nulls(model: BaseModel, nullable: tuple[str, ...] = ()) -> None:
    """PATCH: передано хотя бы одно поле, и обязательные поля не стёрты через null."""
    if not model.model_fields_set:
        raise ValueError("Передайте хотя бы одно поле")
    for field in model.model_fields_set - set(nullable):
        if getattr(model, field) is None:
            raise ValueError(f"Поле {field} не может быть пустым")


class CustomerShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str | None


class AdminOrderSummary(OrderSummary):
    customer: CustomerShort


class AdminOrderOut(OrderDetail):
    customer: CustomerShort


class AdminOrderList(BaseModel):
    items: list[AdminOrderSummary]
    total: int
    limit: int
    offset: int


class OrderStatusChangeIn(BaseModel):
    status: Literal["shipped", "delivered", "cancelled"]
    comment: str | None = Field(None, max_length=300)


class AdminProductIn(BaseModel):
    category_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(None, max_length=5000)
    gender: Gender
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2, examples=["1990.00"])
    is_active: bool = True


class AdminProductPatch(BaseModel):
    category_id: int | None = Field(None, ge=1)
    name: str | None = Field(None, min_length=1, max_length=160)
    description: str | None = Field(None, max_length=5000)
    gender: Gender | None = None
    price: Decimal | None = Field(None, gt=0, max_digits=10, decimal_places=2)
    is_active: bool | None = None

    @model_validator(mode="after")
    def check_fields(self) -> "AdminProductPatch":
        _no_nulls(self, nullable=("description",))
        return self


class AdminVariantIn(BaseModel):
    size: str = Field(min_length=1, max_length=10)
    color: str = Field(min_length=1, max_length=40)
    sku: str = Field(pattern=SKU_PATTERN, examples=["TSH-P-L-BLK"])
    initial_stock: int = Field(0, ge=0, le=10000)


class AdminVariantPatch(BaseModel):
    size: str | None = Field(None, min_length=1, max_length=10)
    color: str | None = Field(None, min_length=1, max_length=40)
    sku: str | None = Field(None, pattern=SKU_PATTERN)
    is_active: bool | None = None

    @model_validator(mode="after")
    def check_fields(self) -> "AdminVariantPatch":
        _no_nulls(self)
        return self


class AdminVariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    size: str
    color: str
    sku: str
    stock: int
    is_active: bool


class ImageOut(BaseModel):
    id: int
    product_id: int
    image_url: str
    color: str | None
    sort_order: int
    content_type: str | None
    size_bytes: int | None


class ImagePatch(BaseModel):
    color: str | None = Field(None, max_length=40)
    sort_order: int | None = Field(None, ge=0, le=100)

    @model_validator(mode="after")
    def check_fields(self) -> "ImagePatch":
        _no_nulls(self, nullable=("color",))
        return self


class AdminProductOut(BaseModel):
    id: int
    category: CategoryOut
    name: str
    description: str | None
    gender: Gender
    price: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime
    variants: list[AdminVariantOut]
    images: list[ImageOut]


class AdminProductList(BaseModel):
    items: list[AdminProductOut]
    total: int
    limit: int
    offset: int


class StockAdjustmentIn(BaseModel):
    delta: int = Field(ge=-10000, le=10000, description="Положительное — приход, отрицательное — списание")
    comment: str = Field(min_length=1, max_length=300)

    @field_validator("delta")
    @classmethod
    def not_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("Изменение остатка не может быть нулевым")
        return v


class StockMovementOut(BaseModel):
    id: int
    variant_id: int
    delta: int
    reason: Literal["reserve", "release", "adjust", "initial"]
    order_id: int | None
    changed_by: CustomerShort | None
    comment: str | None
    stock_after: int | None = None
    created_at: datetime


class StockMovementList(BaseModel):
    items: list[StockMovementOut]
    total: int
    limit: int
    offset: int
