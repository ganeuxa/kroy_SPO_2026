import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Payment, completeTestPayment, formatPrice } from "../api";
import { errorText, PAYMENT_STATUS } from "./orderUi";

export default function TestPayment() {
  const { providerId } = useParams(); const [params] = useSearchParams();
  const [payment, setPayment] = useState<Payment | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  async function finish(result: "succeeded" | "failed") {
    if (!providerId) return;
    setBusy(true); setError(null);
    try { setPayment(await completeTestPayment(providerId, result)); }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }
  const orderId = payment?.order_id ?? Number(params.get("orderId"));
  return <section className="flow-page payment-page"><p className="eyebrow">ТЕСТОВЫЙ ПЛАТЁЖНЫЙ СЕРВИС</p><h1>Оплата заказа</h1><div className="flow-panel">
    {payment ? <><h2>Результат: {PAYMENT_STATUS[payment.status]}</h2><p>Сумма: {formatPrice(payment.amount)}</p>{payment.failure_reason && <p className="status--error">{payment.failure_reason}</p>}{orderId > 0 && <Link className="primary" to={`/orders/${orderId}`}>Вернуться к заказу</Link>}</> : <><p>Это тестовая оплата. Деньги не списываются.</p><div className="actions"><button className="primary" disabled={busy} onClick={() => void finish("succeeded")}>Оплатить</button><button disabled={busy} onClick={() => void finish("failed")}>Отклонить платёж</button></div>{error && <p className="status--error" role="alert">{error}</p>}{orderId > 0 && <p><Link to={`/orders/${orderId}`}>Назад к заказу</Link></p>}</>}
  </div></section>;
}
