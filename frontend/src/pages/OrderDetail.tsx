import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { OrderDetail as OrderData, Payment, cancelOrder, formatPrice, getOrder, getPayment, startPayment } from "../api";
import { useAuth } from "../auth";
import { dateTime, errorText, ORDER_STATUS, PAYMENT_STATUS } from "./orderUi";

export default function OrderDetail() {
  const { id } = useParams(); const orderId = Number(id);
  const { user, loading: authLoading } = useAuth(); const navigate = useNavigate();
  const [order, setOrder] = useState<OrderData | null>(null); const [error, setError] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now()); const payKey = useRef<string | null>(null);
  async function refresh() { if (!Number.isInteger(orderId) || orderId < 1) { setError("Заказ не найден"); return; } try { setOrder(await getOrder(orderId)); setError(null); } catch (e) { setError(errorText(e)); } }
  useEffect(() => { if (user) void refresh(); }, [user, orderId]);
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  useEffect(() => { if (!order) return; const pending = order.payments.find((p) => p.status === "pending"); if (!pending) return; const timer = window.setInterval(async () => { try { const p = await getPayment(pending.id); if (p.status !== "pending") await refresh(); } catch { /* Кнопка обновления остаётся доступна */ } }, 5000); return () => clearInterval(timer); }, [order?.id, order?.payments.map((p) => `${p.id}:${p.status}`).join(",")]);
  async function pay() { if (!order) return; setBusy(true); setError(null); payKey.current ??= crypto.randomUUID(); try { const payment: Payment = await startPayment(order.id, payKey.current); if (payment.confirmation_url) navigate(`${payment.confirmation_url}?orderId=${order.id}`); else { await refresh(); setError("Ссылка на тестовую оплату недоступна"); } } catch (e) { setError(errorText(e)); } finally { setBusy(false); } }
  async function cancel() { if (!order) return; setBusy(true); setError(null); try { setOrder(await cancelOrder(order.id)); } catch (e) { setError(errorText(e)); } finally { setBusy(false); } }
  if (authLoading) return <p className="status">Загрузка…</p>;
  if (!user) return <section className="placeholder"><h1>Заказ</h1><Link to={`/login?next=/orders/${orderId}`}>Войти</Link></section>;
  if (!order) return <section className="flow-page"><Link to="/account/orders" className="back">← Мои заказы</Link>{error ? <div className="flow-panel"><p className="status--error">{error}</p><button className="primary" onClick={() => void refresh()}>Повторить</button></div> : <p className="status">Загружаем заказ…</p>}</section>;
  const seconds = order.expires_at ? Math.max(0, Math.ceil((new Date(order.expires_at).getTime() - now) / 1000)) : 0;
  const pending = order.payments.find((p) => p.status === "pending");
  return <section className="flow-page"><Link to="/account/orders" className="back">← Мои заказы</Link><div className="flow-heading"><h1>Заказ №{order.id}</h1><span className={`status-pill status-pill--${order.status}`}>{ORDER_STATUS[order.status]}</span></div>
    {error && <p className="status--error" role="alert">{error}</p>}
    <div className="flow-layout"><div className="flow-list"><div className="flow-panel"><h2>Товары</h2>{order.items.map((item) => <div className="flow-row" key={item.variant_id}><span><Link to={`/products/${item.product_id}`}>{item.name}</Link> · {item.size}, {item.color} × {item.quantity}</span><b>{formatPrice(item.line_total)}</b></div>)}<div className="flow-row flow-total"><span>Итого</span><b>{formatPrice(order.total_amount)}</b></div></div>
      <div className="flow-panel"><h2>Оплата</h2>{order.payments.length ? order.payments.map((p) => <div className="flow-row" key={p.id}><span>Платёж №{p.id} · {PAYMENT_STATUS[p.status]}{p.failure_reason && ` — ${p.failure_reason}`}</span><span>{dateTime(p.created_at)}</span></div>) : <p className="muted">Платежей пока нет</p>}
      {order.status === "new" && <><p>{seconds > 0 ? `До конца оплаты: ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}` : "Время оплаты истекло"}</p>{pending?.confirmation_url ? <Link className="primary" to={`${pending.confirmation_url}?orderId=${order.id}`}>Продолжить оплату</Link> : <button className="primary" disabled={busy || seconds <= 0} onClick={() => void pay()}>{busy ? "Подождите…" : "Оплатить тестовым платежом"}</button>}</>}
      </div></div><aside className="flow-list"><div className="flow-panel"><h2>Получение</h2><p>{order.delivery_method === "pickup" ? `Самовывоз: ${order.pickup_point?.name ?? "Пункт выдачи"}, ${order.pickup_point?.address ?? ""}` : `Курьер: ${order.delivery_address}`}</p><p>Телефон: {order.contact_phone}</p>{order.comment && <p>Комментарий: {order.comment}</p>}<p className="muted">Создан {dateTime(order.created_at)}</p>{order.status === "new" && <button className="link-button" disabled={busy} onClick={() => void cancel()}>Отменить заказ</button>}</div><div className="flow-panel"><h2>История статусов</h2>{order.history.map((h, i) => <p key={i}>{dateTime(h.created_at)} — {ORDER_STATUS[h.to_status]}{h.comment && ` · ${h.comment}`}</p>)}</div></aside></div>
  </section>;
}
