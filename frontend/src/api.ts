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

async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
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
  return res.json() as Promise<T>;
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
