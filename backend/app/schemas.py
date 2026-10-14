"""Форматы ответов API (Pydantic)."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


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
