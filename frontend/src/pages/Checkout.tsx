import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Cart, DeliveryMethod, PickupPoint, createOrder, formatPrice, getCart, getPickupPoints } from "../api";
import { useAuth } from "../auth";
import { errorText } from "./orderUi";

export default function Checkout() {
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [cart, setCart] = useState<Cart | null>(null);
  const [points, setPoints] = useState<PickupPoint[]>([]);
  const [method, setMethod] = useState<DeliveryMethod>("pickup");
  const [pointId, setPointId] = useState("");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState(user?.phone ?? "");
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(true);
  const [cartRetry, setCartRetry] = useState(0);
  const [pointsRetry, setPointsRetry] = useState(0);
  const [pointsLoading, setPointsLoading] = useState(true);
  const [pointsError, setPointsError] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = useRef<string | null>(null);

  useEffect(() => { if (user) setPhone(user.phone ?? ""); }, [user]);

  useEffect(() => {
    if (!user) return;
    let current = true;
    setLoading(true);
    setError(null);
    getCart()
      .then((nextCart) => { if (current) setCart(nextCart); })
      .catch((e) => { if (current) setError(errorText(e)); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [user, cartRetry]);

  useEffect(() => {
    if (!user) return;
    let current = true;
    setPointsLoading(true);
    setPointsError(false);
    getPickupPoints()
      .then((nextPoints) => {
        if (!current) return;
        setPoints(nextPoints);
        setPointId((previous) => nextPoints.some((p) => String(p.id) === previous)
          ? previous
          : String(nextPoints[0]?.id ?? ""));
      })
      .catch(() => { if (current) setPointsError(true); })
      .finally(() => { if (current) setPointsLoading(false); });
    return () => { current = false; };
  }, [user, pointsRetry]);

  const hasShortage = cart?.items.some((item) => item.quantity > item.stock) ?? false;
  const pickupUnavailable = method === "pickup" && (pointsLoading || pointsError || !pointId);
  function changed() { key.current = null; setError(null); }
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (sending || hasShortage || pickupUnavailable) return;
    if (!/^\+?[0-9]{10,15}$/.test(phone.trim())) { setError("Укажите телефон в формате +79001112233"); return; }
    if (method === "pickup" && !pointId) { setError("Выберите пункт выдачи"); return; }
    if (method === "courier" && address.trim().length < 5) { setError("Укажите адрес доставки"); return; }
    key.current ??= crypto.randomUUID();
    setSending(true); setError(null);
    try {
      const order = await createOrder({ delivery_method: method, ...(method === "pickup" ? { pickup_point_id: Number(pointId) } : { delivery_address: address.trim() }), contact_phone: phone.trim(), comment: comment.trim() || undefined }, key.current);
      navigate(`/orders/${order.id}`, { replace: true });
    } catch (e) { setError(errorText(e)); }
    finally { setSending(false); }
  }
  if (authLoading) return <p className="status">Загрузка…</p>;
  if (!user) return <section className="placeholder"><h1>Оформление заказа</h1><p>Сначала войдите в аккаунт.</p><Link to="/login?next=/checkout">Войти</Link></section>;
  if (loading) return <p className="status" role="status">Загружаем корзину…</p>;
  if (!cart) return <section className="placeholder"><p className="status--error" role="alert">{error}</p><button className="primary" onClick={() => setCartRetry((n) => n + 1)}>Повторить</button></section>;
  if (cart.items.length === 0) return <section className="placeholder"><h1>Корзина пуста</h1><Link to="/">Вернуться в каталог</Link></section>;
  if (hasShortage) return <section className="placeholder"><h1>Оформление заказа</h1><p className="status--error" role="alert">Количество товаров превышает доступный остаток.</p><Link to="/cart">Исправить количество в корзине</Link></section>;
  return <section className="flow-page"><Link to="/cart" className="back">← Корзина</Link><h1>Оформление заказа</h1>
    <div className="flow-layout"><form className="flow-panel form" onSubmit={submit}>
      <fieldset><legend>Получение</legend><label><input type="radio" name="delivery" checked={method === "pickup"} onChange={() => { setMethod("pickup"); changed(); }} /> Самовывоз</label><label><input type="radio" name="delivery" checked={method === "courier"} onChange={() => { setMethod("courier"); changed(); }} /> Доставка курьером</label></fieldset>
      {method === "pickup" ? <>
        <label>Пункт выдачи
          <select value={pointId} onChange={(e) => { setPointId(e.target.value); changed(); }} disabled={pointsLoading || pointsError || !points.length} required>
            <option value="">Выберите пункт</option>
            {points.map((p) => <option key={p.id} value={p.id}>{p.name} — {p.address}{p.hours ? ` (${p.hours})` : ""}</option>)}
          </select>
        </label>
        {pointsLoading && <p role="status">Загружаем пункты выдачи…</p>}
        {pointsError && <div role="alert">
          <p className="status--error">Не удалось загрузить пункты выдачи. Можно выбрать доставку курьером.</p>
          <button type="button" onClick={() => setPointsRetry((n) => n + 1)}>Повторить загрузку</button>
        </div>}
        {!pointsLoading && !pointsError && points.length === 0 && <p className="status--error" role="status">Пунктов самовывоза пока нет. Выберите доставку курьером.</p>}
      </> : <label>Адрес доставки<input value={address} onChange={(e) => { setAddress(e.target.value); changed(); }} minLength={5} maxLength={300} required placeholder="Город, улица, дом, квартира" /></label>}
      <label>Телефон для связи<input type="tel" value={phone} onChange={(e) => { setPhone(e.target.value); changed(); }} required placeholder="+79001112233" /></label>
      <label>Комментарий к заказу<input value={comment} onChange={(e) => { setComment(e.target.value); changed(); }} maxLength={500} placeholder="Необязательно" /></label>
      {error && <p className="status--error" role="alert">{error}</p>}
      <button className="primary" disabled={sending || pickupUnavailable}>{sending ? "Создаём заказ…" : "Подтвердить заказ"}</button>
    </form><aside className="flow-panel"><h2>Ваш заказ</h2>{cart.items.map((item) => <div className="flow-row" key={item.id}><span>{item.name} × {item.quantity}</span><b>{formatPrice(item.line_total)}</b></div>)}<div className="flow-row flow-total"><span>Итого</span><b>{formatPrice(cart.total)}</b></div><p className="muted">После оформления вы сможете перейти к тестовой оплате.</p></aside></div>
  </section>;
}
