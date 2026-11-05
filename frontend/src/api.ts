// Все запросы к серверу собраны здесь. Браузер ходит только в /api,
// напрямую к БД он не обращается.

export type Gender = "men" | "women" | "unisex";

export interface Category {
  id: number;
  name: string;
  slug: string;
}

export interface ProductListItem {
  id: number;
  name: string;
  price: string; // Decimal приходит строкой, чтобы не терять копейки
  gender: Gender;
  category: Category;
  image_key: string | null;
  image_url?: string | null;
  in_stock: boolean;
}

export interface ProductList {
  items: ProductListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface Variant {
  id: number;
  size: string;
  color: string;
  sku: string;
  stock: number;
  in_stock: boolean;
}

export interface ProductDetail {
  id: number;
  name: string;
  description: string | null;
  price: string;
  gender: Gender;
  category: Category;
  image_keys: string[];
  image_urls?: string[];
  variants: Variant[];
}

export interface Filters {
  categories: Category[];
  sizes: string[];
  colors: string[];
  price_min: string | null;
  price_max: string | null;
}

export interface ProductQuery {
  gender?: string;
  category?: string;
  size?: string;
  color?: string;
  price_min?: string;
  price_max?: string;
  q?: string;
  sort?: string;
  limit?: number;
  offset?: number;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

// Токен входа (JWT) хранится в localStorage и уходит в заголовке Authorization
const TOKEN_KEY = "kroy_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* хранилище недоступно (приватный режим) — вход проживёт до перезагрузки */
  }
}

async function request<T>(path: string, method = "GET", body?: unknown, extraHeaders: Record<string, string> = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined && !(body instanceof FormData)) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  Object.assign(headers, extraHeaders);

  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Сервер недоступен. Проверьте подключение.");
  }
  if (!res.ok) {
    let message = `Ошибка ${res.status}`;
    try {
      const data = await res.json();
      // FastAPI возвращает detail строкой либо списком ошибок валидации
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = "Проверьте правильность заполнения полей";
    } catch {
      /* тело не JSON — оставляем код ответа */
    }
    throw new ApiError(res.status, message);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export function getProducts(query: ProductQuery): Promise<ProductList> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return request<ProductList>(`/products${qs ? `?${qs}` : ""}`);
}

export function getProduct(id: number): Promise<ProductDetail> {
  return request<ProductDetail>(`/products/${id}`);
}

export function getFilters(): Promise<Filters> {
  return request<Filters>("/filters");
}

// --- Вход и регистрация (FR-01, FR-02) ---

export interface User {
  id: number;
  email: string;
  full_name: string;
  phone: string | null;
  role: "customer" | "admin";
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface RegisterData {
  email: string;
  password: string;
  full_name: string;
  phone?: string;
}

export function register(data: RegisterData): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/register", "POST", data);
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/login", "POST", { email, password });
}

export function getMe(): Promise<User> {
  return request<User>("/auth/me");
}

// --- Корзина (FR-07) ---

export interface CartItem {
  id: number;
  variant_id: number;
  product_id: number;
  name: string;
  size: string;
  color: string;
  sku: string;
  image_key: string | null;
  image_url?: string | null;
  price: string;
  quantity: number;
  stock: number;
  line_total: string;
}

export interface Cart {
  items: CartItem[];
  total_quantity: number;
  total: string;
}

export function getCart(): Promise<Cart> {
  return request<Cart>("/cart");
}

export function addToCart(variantId: number, quantity = 1): Promise<Cart> {
  return request<Cart>("/cart", "POST", { variant_id: variantId, quantity });
}

export const GENDER_LABELS: Record<Gender, string> = {
  men: "Мужское",
  women: "Женское",
  unisex: "Унисекс",
};

export function formatPrice(price: string): string {
  return `${Number(price).toLocaleString("ru-RU")} ₽`;
}

// Этап III: корзина, заказы, оплата и администрирование.
export function updateCartItem(id: number, quantity: number): Promise<Cart> { return request<Cart>(`/cart/items/${id}`, "PATCH", { quantity }); }
export function deleteCartItem(id: number): Promise<Cart> { return request<Cart>(`/cart/items/${id}`, "DELETE"); }
export type OrderStatus = "new" | "paid" | "shipped" | "delivered" | "cancelled";
export type DeliveryMethod = "courier" | "pickup";
export type PaymentStatus = "pending" | "succeeded" | "failed" | "cancelled";
export interface PickupPoint { id: number; name: string; address: string; hours: string | null }
export interface OrderItem { variant_id: number; product_id: number; name: string; size: string; color: string; sku: string; image_url: string | null; quantity: number; price: string; line_total: string }
export interface Payment { id: number; order_id: number; status: PaymentStatus; amount: string; confirmation_url: string | null; failure_reason: string | null; created_at: string; paid_at: string | null }
export interface StatusChange { from_status: OrderStatus | null; to_status: OrderStatus; changed_by: "customer" | "admin" | "system"; comment: string | null; created_at: string }
export interface OrderSummary { id: number; status: OrderStatus; total_amount: string; items_count: number; delivery_method: DeliveryMethod; created_at: string; expires_at: string | null }
export interface OrderDetail extends OrderSummary { delivery_address: string | null; pickup_point: PickupPoint | null; contact_phone: string; comment: string | null; cancel_reason: string | null; items: OrderItem[]; payments: Payment[]; history: StatusChange[] }
export interface Page<T> { items: T[]; total: number; limit: number; offset: number }
export interface OrderCreate { delivery_method: DeliveryMethod; delivery_address?: string; pickup_point_id?: number; contact_phone: string; comment?: string }
function query(path: string, params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== "") search.set(key, String(value)); });
  return `${path}${search.size ? `?${search}` : ""}`;
}
export const getPickupPoints = () => request<PickupPoint[]>("/pickup-points");
export const createOrder = (data: OrderCreate, key: string) => request<OrderDetail>("/orders", "POST", data, { "Idempotency-Key": key });
export const getOrders = (params: { status?: OrderStatus; limit?: number; offset?: number } = {}) => request<Page<OrderSummary>>(query("/orders", params));
export const getOrder = (id: number) => request<OrderDetail>(`/orders/${id}`);
export const cancelOrder = (id: number) => request<OrderDetail>(`/orders/${id}/cancel`, "POST");
export const startPayment = (id: number, key: string) => request<Payment>(`/orders/${id}/payments`, "POST", undefined, { "Idempotency-Key": key });
export const getPayment = (id: number) => request<Payment>(`/payments/${id}`);
export const completeTestPayment = (providerId: string, result: "succeeded" | "failed") => request<Payment>(`/test-provider/payments/${providerId}`, "POST", { result });
export interface AdminVariant { id: number; product_id: number; size: string; color: string; sku: string; stock: number; is_active: boolean }
export interface AdminImage { id: number; product_id: number; image_url: string; color: string | null; sort_order: number; content_type: string | null; size_bytes: number | null }
export interface AdminProduct { id: number; category: Category; name: string; description: string | null; gender: Gender; price: string; is_active: boolean; created_at: string; updated_at: string; variants: AdminVariant[]; images: AdminImage[] }
export interface CustomerShort { id: number; email: string; full_name: string; phone: string | null }
export interface AdminOrderSummary extends OrderSummary { customer: CustomerShort }
export interface AdminOrder extends OrderDetail { customer: CustomerShort }
export interface StockMovement { id: number; variant_id: number; delta: number; reason: string; order_id: number | null; changed_by: CustomerShort | null; comment: string | null; stock_after: number | null; created_at: string }
export interface AdminProductInput { category_id: number; name: string; description: string | null; gender: Gender; price: string; is_active: boolean }
export interface AdminVariantInput { size: string; color: string; sku: string; initial_stock: number }
export const getAdminProducts = (params: Record<string, string | number | boolean | undefined> = {}) => request<Page<AdminProduct>>(query("/admin/products", params));
export const getAdminProduct = (id: number) => request<AdminProduct>(`/admin/products/${id}`);
export const createAdminProduct = (data: AdminProductInput) => request<AdminProduct>("/admin/products", "POST", data);
export const patchAdminProduct = (id: number, data: Partial<AdminProductInput>) => request<AdminProduct>(`/admin/products/${id}`, "PATCH", data);
export const createAdminVariant = (productId: number, data: AdminVariantInput) => request<AdminVariant>(`/admin/products/${productId}/variants`, "POST", data);
export const patchAdminVariant = (id: number, data: Partial<Omit<AdminVariant, "id" | "product_id" | "stock">>) => request<AdminVariant>(`/admin/variants/${id}`, "PATCH", data);
export const adjustStock = (id: number, delta: number, comment: string) => request<StockMovement>(`/admin/variants/${id}/stock-movements`, "POST", { delta, comment });
export const getStockMovements = (id: number) => request<Page<StockMovement>>(`/admin/variants/${id}/stock-movements`);
export const uploadAdminImage = (productId: number, file: File, color: string | null, sortOrder: number) => { const form = new FormData(); form.append("file", file); if (color) form.append("color", color); form.append("sort_order", String(sortOrder)); return request<AdminImage>(`/admin/products/${productId}/images`, "POST", form); };
export const patchAdminImage = (id: number, data: { color?: string | null; sort_order?: number }) => request<AdminImage>(`/admin/images/${id}`, "PATCH", data);
export const deleteAdminImage = (id: number) => request<void>(`/admin/images/${id}`, "DELETE");
export const getAdminOrders = (params: Record<string, string | number | undefined> = {}) => request<Page<AdminOrderSummary>>(query("/admin/orders", params));
export const getAdminOrder = (id: number) => request<AdminOrder>(`/admin/orders/${id}`);
export const changeAdminOrderStatus = (id: number, status: "shipped" | "delivered" | "cancelled", comment?: string) => request<AdminOrder>(`/admin/orders/${id}/status`, "POST", { status, comment: comment || null });
