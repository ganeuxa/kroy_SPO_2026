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
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = useRef<string | null>(null);

  useEffect(() => { if (user && !phone) setPhone(user.phone ?? ""); }, [user]);
  useEffect(() => {
    if (!user) return;
    Promise.all([getCart(), getPickupPoints()]).then(([nextCart, nextPoints]) => {
      setCart(nextCart); setPoints(nextPoints); if (nextPoints[0]) setPointId(String(nextPoints[0].id));
    }).catch((e) => setError(errorText(e))).finally(() => setLoading(false));
  }, [user]);
  function changed() { key.current = null; setError(null); }
  async function submit(e: FormEvent) {
    e.preventDefault();
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
  if (loading) return <p className="status">Загружаем корзину и пункты выдачи…</p>;
  if (!cart) return <section className="placeholder"><p className="status--error">{error}</p><button className="primary" onClick={() => location.reload()}>Повторить</button></section>;
  if (cart.items.length === 0) return <section className="placeholder"><h1>Корзина пуста</h1><Link to="/">Вернуться в каталог</Link></section>;
  return <section className="flow-page"><Link to="/cart" className="back">← Корзина</Link><h1>Оформление заказа</h1>
    <div className="flow-layout"><form className="flow-panel form" onSubmit={submit}>
      <fieldset><legend>Получение</legend><label><input type="radio" name="delivery" checked={method === "pickup"} onChange={() => { setMethod("pickup"); changed(); }} /> Самовывоз</label><label><input type="radio" name="delivery" checked={method === "courier"} onChange={() => { setMethod("courier"); changed(); }} /> Доставка курьером</label></fieldset>
      {method === "pickup" ? <label>Пункт выдачи<select value={pointId} onChange={(e) => { setPointId(e.target.value); changed(); }} required><option value="">Выберите пункт</option>{points.map((p) => <option key={p.id} value={p.id}>{p.name} — {p.address}{p.hours ? ` (${p.hours})` : ""}</option>)}</select></label> : <label>Адрес доставки<input value={address} onChange={(e) => { setAddress(e.target.value); changed(); }} minLength={5} maxLength={300} required placeholder="Город, улица, дом, квартира" /></label>}
      <label>Телефон для связи<input type="tel" value={phone} onChange={(e) => { setPhone(e.target.value); changed(); }} required placeholder="+79001112233" /></label>
      <label>Комментарий к заказу<input value={comment} onChange={(e) => { setComment(e.target.value); changed(); }} maxLength={500} placeholder="Необязательно" /></label>
      {error && <p className="status--error" role="alert">{error}</p>}
      <button className="primary" disabled={sending}>{sending ? "Создаём заказ…" : "Подтвердить заказ"}</button>
    </form><aside className="flow-panel"><h2>Ваш заказ</h2>{cart.items.map((item) => <div className="flow-row" key={item.id}><span>{item.name} × {item.quantity}</span><b>{formatPrice(item.line_total)}</b></div>)}<div className="flow-row flow-total"><span>Итого</span><b>{formatPrice(cart.total)}</b></div><p className="muted">После оформления вы сможете перейти к тестовой оплате.</p></aside></div>
  </section>;
}
