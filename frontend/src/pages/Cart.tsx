import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, Cart as CartData, deleteCartItem, formatPrice, getCart, updateCartItem } from "../api";
import { useAuth } from "../auth";
import ProductImage from "../components/ProductImage";

export default function Cart() {
  const { user, loading } = useAuth();
  const [cart, setCart] = useState<CartData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  useEffect(() => {
    if (!user) return;
    getCart().then(setCart).catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Не удалось загрузить корзину"));
  }, [user]);

  async function change(id: number, quantity?: number) {
    setBusy(id); setError(null);
    try { setCart(quantity === undefined ? await deleteCartItem(id) : await updateCartItem(id, quantity)); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Не удалось изменить корзину"); }
    finally { setBusy(null); }
  }

  if (loading) return <p className="status">Загрузка…</p>;
  if (!user) return <section className="placeholder"><h1>Корзина</h1><p>Войдите, чтобы пользоваться корзиной.</p><Link to="/login?next=/cart">Войти</Link></section>;
  if (!cart && error) return <section className="placeholder"><p className="status--error">{error}</p><button className="primary" onClick={() => { setError(null); getCart().then(setCart).catch((e) => setError(e.message)); }}>Повторить</button></section>;
  if (!cart) return <p className="status">Загружаем корзину…</p>;
  if (cart.items.length === 0) return <section className="placeholder"><h1>Корзина пуста</h1><Link to="/">Перейти в каталог</Link></section>;

  return <section className="cart">
    <h1>Корзина</h1>
    {error && <p className="status status--error" role="alert">{error}</p>}
    <ul className="cart__list">{cart.items.map((item) => <li key={item.id} className="cart__item">
      <Link to={`/products/${item.product_id}`} className="cart__image"><ProductImage name={item.name} imageKey={item.image_key} imageUrl={item.image_url} /></Link>
      <div className="cart__info">
        <Link to={`/products/${item.product_id}`} className="card__name">{item.name}</Link>
        <span className="card__meta">{item.color}, размер {item.size}</span>
        <span className="card__meta">{formatPrice(item.price)} за шт. · В наличии {item.stock}</span>
        <div className="quantity" aria-label={`Количество ${item.name}`}>
          <button type="button" disabled={busy !== null || item.quantity <= 1} onClick={() => change(item.id, item.quantity - 1)} aria-label="Уменьшить количество">−</button>
          <span>{item.quantity}</span>
          <button type="button" disabled={busy !== null || item.quantity >= Math.min(99, item.stock)} onClick={() => change(item.id, item.quantity + 1)} aria-label="Увеличить количество">+</button>
          <button type="button" className="link-button" disabled={busy !== null} onClick={() => change(item.id)}>Удалить</button>
        </div>
        {item.quantity > item.stock && <span className="status--error">В наличии только {item.stock} шт.</span>}
      </div>
      <span className="card__price">{formatPrice(item.line_total)}</span>
    </li>)}</ul>
    <div className="cart__summary"><span>Товаров: {cart.total_quantity}</span><span className="cart__total">Итого: {formatPrice(cart.total)}</span><Link to="/checkout" className="primary">Оформить заказ</Link></div>
  </section>;
}
