import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { OrderStatus, Page, OrderSummary, formatPrice, getOrders } from "../api";
import { useAuth } from "../auth";
import { dateTime, errorText, ORDER_STATUS } from "./orderUi";

export default function Orders() {
  const { user, loading: authLoading } = useAuth();
  const [params, setParams] = useSearchParams();
  const status = (params.get("status") || "") as OrderStatus | "";
  const page = Math.max(1, Number(params.get("page") || 1) || 1);
  const [data, setData] = useState<Page<OrderSummary> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!user) return;
    setLoading(true); setError(null);
    getOrders({ status: status || undefined, limit: 10, offset: (page - 1) * 10 }).then(setData).catch((e) => setError(errorText(e))).finally(() => setLoading(false));
  }, [user, status, page]);
  if (authLoading) return <p className="status">Загрузка…</p>;
  if (!user) return <section className="placeholder"><h1>Мои заказы</h1><Link to="/login?next=/account/orders">Войти</Link></section>;
  return <section className="flow-page"><h1>Мои заказы</h1><div className="toolbar"><label>Статус <select value={status} onChange={(e) => setParams(e.target.value ? { status: e.target.value } : {})}><option value="">Все заказы</option>{(Object.keys(ORDER_STATUS) as OrderStatus[]).map((s) => <option key={s} value={s}>{ORDER_STATUS[s]}</option>)}</select></label></div>
    {loading ? <p className="status">Загружаем заказы…</p> : error ? <div className="flow-panel"><p className="status--error" role="alert">{error}</p><button className="primary" onClick={() => setParams(new URLSearchParams(params))}>Повторить</button></div> : !data?.items.length ? <div className="placeholder"><h2>Заказов пока нет</h2><Link to="/">Открыть каталог</Link></div> : <><div className="flow-list">{data.items.map((order) => <Link className="flow-panel order-card" key={order.id} to={`/orders/${order.id}`}><div><b>Заказ №{order.id}</b><span className="muted">{dateTime(order.created_at)} · {order.items_count} товаров</span></div><span className={`status-pill status-pill--${order.status}`}>{ORDER_STATUS[order.status]}</span><strong>{formatPrice(order.total_amount)}</strong></Link>)}</div><div className="pager"><button disabled={page <= 1} onClick={() => setParams(status ? { status, page: String(page - 1) } : { page: String(page - 1) })}>Назад</button><span>Страница {page}</span><button disabled={page * 10 >= data.total} onClick={() => setParams(status ? { status, page: String(page + 1) } : { page: String(page + 1) })}>Далее</button></div></>}
  </section>;
}
