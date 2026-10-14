import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, GENDER_LABELS, ProductDetail, formatPrice, getProduct } from "../api";
import ProductImage from "../components/ProductImage";

export default function Product() {
  const { id } = useParams();
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [color, setColor] = useState<string>("");
  const [size, setSize] = useState<string>("");

  useEffect(() => {
    const productId = Number(id);
    if (!Number.isInteger(productId) || productId < 1) {
      setError("Товар не найден");
      return;
    }
    setProduct(null);
    setError(null);
    getProduct(productId)
      .then((p) => {
        setProduct(p);
        // Сразу выбираем первый цвет, который есть в наличии
        const first = p.variants.find((v) => v.in_stock) ?? p.variants[0];
        setColor(first?.color ?? "");
        setSize("");
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Не удалось загрузить товар"));
  }, [id]);

  const colors = useMemo(
    () => [...new Set(product?.variants.map((v) => v.color) ?? [])],
    [product],
  );
  const sizes = useMemo(
    () => product?.variants.filter((v) => v.color === color) ?? [],
    [product, color],
  );
  const selected = sizes.find((v) => v.size === size);

  if (error) {
    return (
      <section className="placeholder">
        <h1>{error}</h1>
        <Link to="/">Вернуться в каталог</Link>
      </section>
    );
  }
  if (!product) return <p className="status">Загрузка…</p>;

  return (
    <article className="product">
      <Link to="/" className="back">
        ← Каталог
      </Link>
      <div className="product__layout">
        <ProductImage name={product.name} imageKey={product.image_keys[0]} />

        <div className="product__info">
          <span className="card__meta">
            {product.category.name} · {GENDER_LABELS[product.gender]}
          </span>
          <h1>{product.name}</h1>
          <p className="product__price">{formatPrice(product.price)}</p>
          {product.description && <p>{product.description}</p>}

          <div className="option">
            <span className="option__label">Цвет</span>
            <div className="chips">
              {colors.map((c) => (
                <button
                  key={c}
                  type="button"
                  className={c === color ? "chip active" : "chip"}
                  onClick={() => {
                    setColor(c);
                    setSize("");
                  }}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>

          <div className="option">
            <span className="option__label">Размер</span>
            <div className="chips">
              {sizes.map((v) => (
                <button
                  key={v.id}
                  type="button"
                  className={v.size === size ? "chip active" : "chip"}
                  disabled={!v.in_stock}
                  title={v.in_stock ? undefined : "Нет в наличии"}
                  onClick={() => setSize(v.size)}
                >
                  {v.size}
                </button>
              ))}
            </div>
          </div>

          <p className="stock">
            {selected
              ? selected.stock > 3
                ? "В наличии"
                : `Осталось ${selected.stock} шт.`
              : "Выберите размер"}
          </p>

          {/* Добавление в корзину — задача №6 (FR-07), нужен вход */}
          <button type="button" className="primary" disabled={!selected} title="Появится после входа (№6)">
            В корзину
          </button>
        </div>
      </div>
    </article>
  );
}
