"""Каталог: FR-03 (просмотр), FR-04 (фильтры), FR-05 (поиск), FR-06 (карточка)."""

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import Select, exists, func, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Category, Product, ProductVariant
from app.schemas import (
    CategoryOut,
    ErrorOut,
    Filters,
    ProductDetail,
    ProductList,
    ProductListItem,
    VariantOut,
)

router = APIRouter(tags=["catalog"])

Gender = Literal["men", "women", "unisex"]
Sort = Literal["new", "price_asc", "price_desc"]

# Порядок буквенных размеров; числовые (джинсы) идут после них по возрастанию.
SIZE_ORDER = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"]


def _size_key(size: str) -> tuple[int, float, str]:
    if size in SIZE_ORDER:
        return (0, SIZE_ORDER.index(size), size)
    try:
        return (1, float(size), size)
    except ValueError:
        return (2, 0, size)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _apply_filters(
    stmt: Select,
    gender: Gender | None,
    category: str | None,
    size: str | None,
    color: str | None,
    price_min: Decimal | None,
    price_max: Decimal | None,
    q: str | None,
) -> Select:
    stmt = stmt.where(Product.is_active)
    if gender == "unisex":
        stmt = stmt.where(Product.gender == "unisex")
    elif gender:
        # Унисекс показываем и в мужском, и в женском разделе (как в запросе Q1 отчёта №4)
        stmt = stmt.where(Product.gender.in_([gender, "unisex"]))
    if category:
        stmt = stmt.where(
            Product.category_id.in_(select(Category.id).where(Category.slug == category))
        )
    if size or color:
        # Нужен вариант с выбранным размером/цветом, который есть в наличии.
        cond = [ProductVariant.product_id == Product.id, ProductVariant.stock > 0]
        if size:
            cond.append(ProductVariant.size == size)
        if color:
            cond.append(ProductVariant.color == color)
        stmt = stmt.where(exists().where(*cond))
    if price_min is not None:
        stmt = stmt.where(Product.price >= price_min)
    if price_max is not None:
        stmt = stmt.where(Product.price <= price_max)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{_escape_like(q)}%", escape="\\"))
    return stmt


@router.get("/products", response_model=ProductList, responses={422: {"model": ErrorOut}})
def list_products(
    gender: Gender | None = None,
    category: str | None = Query(None, max_length=80, description="slug категории"),
    size: str | None = Query(None, max_length=10),
    color: str | None = Query(None, max_length=40),
    price_min: Decimal | None = Query(None, ge=0),
    price_max: Decimal | None = Query(None, ge=0),
    q: str | None = Query(None, min_length=1, max_length=100, description="поиск по названию"),
    sort: Sort = "new",
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> ProductList:
    if price_min is not None and price_max is not None and price_min > price_max:
        raise HTTPException(status_code=422, detail="price_min не может быть больше price_max")

    args = (gender, category, size, color, price_min, price_max, q)
    total = db.scalar(_apply_filters(select(func.count(Product.id)), *args)) or 0

    order = {
        "new": (Product.created_at.desc(), Product.id.desc()),
        "price_asc": (Product.price.asc(), Product.id.asc()),
        "price_desc": (Product.price.desc(), Product.id.desc()),
    }[sort]
    stmt = (
        _apply_filters(select(Product), *args)
        .options(selectinload(Product.variants), selectinload(Product.images))
        .order_by(*order)
        .limit(limit)
        .offset(offset)
    )
    products = db.scalars(stmt).unique().all()

    items = [
        ProductListItem(
            id=p.id,
            name=p.name,
            price=p.price,
            gender=p.gender,
            category=CategoryOut.model_validate(p.category),
            image_key=p.images[0].storage_key if p.images else None,
            in_stock=any(v.stock > 0 for v in p.variants),
        )
        for p in products
    ]
    return ProductList(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/products/{product_id}",
    response_model=ProductDetail,
    responses={404: {"model": ErrorOut}},
)
def get_product(
    product_id: int = Path(ge=1),
    db: Session = Depends(get_db),
) -> ProductDetail:
    product = db.scalar(
        select(Product)
        .where(Product.id == product_id, Product.is_active)
        .options(selectinload(Product.variants), selectinload(Product.images))
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")

    variants = sorted(product.variants, key=lambda v: (v.color, _size_key(v.size)))
    return ProductDetail(
        id=product.id,
        name=product.name,
        description=product.description,
        price=product.price,
        gender=product.gender,
        category=CategoryOut.model_validate(product.category),
        image_keys=[img.storage_key for img in product.images],
        variants=[
            VariantOut(
                id=v.id, size=v.size, color=v.color, sku=v.sku,
                stock=v.stock, in_stock=v.stock > 0,
            )
            for v in variants
        ],
    )


@router.get("/filters", response_model=Filters)
def get_filters(db: Session = Depends(get_db)) -> Filters:
    """Значения для фильтров каталога: берутся из видимых товаров."""
    categories = db.scalars(select(Category).order_by(Category.name)).all()

    active_variants = (
        select(ProductVariant)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(Product.is_active)
        .subquery()
    )
    sizes = db.scalars(select(active_variants.c.size).distinct()).all()
    colors = db.scalars(select(active_variants.c.color).distinct()).all()
    price_min, price_max = db.execute(
        select(func.min(Product.price), func.max(Product.price)).where(Product.is_active)
    ).one()

    return Filters(
        categories=[CategoryOut.model_validate(c) for c in categories],
        sizes=sorted(sizes, key=_size_key),
        colors=sorted(colors),
        price_min=price_min,
        price_max=price_max,
    )
