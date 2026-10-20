import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, Cart as CartData, formatPrice, getCart } from "../api";
import { useAuth } from "../auth";
import ProductImage from "../components/ProductImage";

export default function Cart() {
  const { user, loading } = useAuth();
  const [cart, setCart] = useState<CartData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    getCart()
      .then(setCart)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Не удалось загрузить корзину"));
  }, [user]);

  if (loading) return <p className="status">Загрузка…</p>;
  if (!user) {
    return (
      <section className="placeholder">
        <h1>Корзина</h1>
        <p>Чтобы пользоваться корзиной, войдите в аккаунт.</p>
        <Link to="/login?next=/cart">Войти</Link>
      </section>
    );
  }
  if (error) return <p className="status status--error">{error}</p>;
  if (!cart) return <p className="status">Загрузка…</p>;

  if (cart.items.length === 0) {
    return (
      <section className="placeholder">
        <h1>Корзина пуста</h1>
        <Link to="/">Перейти в каталог</Link>
      </section>
    );
  }

  return (
    <section className="cart">
      <h1>Корзина</h1>
      <ul className="cart__list">
        {cart.items.map((item) => (
          <li key={item.id} className="cart__item">
            <Link to={`/products/${item.product_id}`} className="cart__image">
              <ProductImage name={item.name} imageKey={item.image_key} />
            </Link>
            <div className="cart__info">
              <Link to={`/products/${item.product_id}`} className="card__name">
                {item.name}
              </Link>
              <span className="card__meta">
                {item.color}, размер {item.size}
              </span>
              <span className="card__meta">
                {formatPrice(item.price)} × {item.quantity} шт.
              </span>
              {item.quantity > item.stock && (
                <span className="status--error">В наличии только {item.stock} шт.</span>
              )}
            </div>
            <span className="card__price">{formatPrice(item.line_total)}</span>
          </li>
        ))}
      </ul>
      <div className="cart__summary">
        <span>
          Товаров: {cart.total_quantity}
        </span>
        <span className="cart__total">Итого: {formatPrice(cart.total)}</span>
        {/* Оформление заказа (FR-08) — по плану после корзины */}
        <button type="button" className="primary" disabled title="Оформление заказа появится позже">
          Оформить заказ
        </button>
      </div>
    </section>
  );
}
