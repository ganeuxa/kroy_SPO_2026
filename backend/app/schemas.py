"""Форматы ответов API (Pydantic)."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


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
    email: EmailStr
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
    price: Decimal
    quantity: int
    stock: int
    line_total: Decimal


class CartOut(BaseModel):
    items: list[CartItemOut]
    total_quantity: int
    total: Decimal
