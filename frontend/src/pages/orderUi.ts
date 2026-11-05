import { OrderStatus, PaymentStatus } from "../api";
export const ORDER_STATUS: Record<OrderStatus, string> = { new: "Ожидает оплаты", paid: "Оплачен", shipped: "Передан в доставку", delivered: "Доставлен", cancelled: "Отменён" };
export const PAYMENT_STATUS: Record<PaymentStatus, string> = { pending: "Ожидает оплаты", succeeded: "Оплачен", failed: "Отклонён", cancelled: "Отменён" };
export function dateTime(value: string): string { return new Date(value).toLocaleString("ru-RU", { dateStyle: "medium", timeStyle: "short" }); }
export function errorText(error: unknown): string { return error instanceof Error ? error.message : "Не удалось выполнить действие"; }
