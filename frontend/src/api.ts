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

async function request<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { headers: { Accept: "application/json" } });
  } catch {
    throw new ApiError(0, "Сервер недоступен. Проверьте подключение.");
  }
  if (!res.ok) {
    let message = `Ошибка ${res.status}`;
    try {
      const body = await res.json();
      // FastAPI возвращает detail строкой либо списком ошибок валидации
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = "Неверные параметры запроса";
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

export const GENDER_LABELS: Record<Gender, string> = {
  men: "Мужское",
  women: "Женское",
  unisex: "Унисекс",
};

export function formatPrice(price: string): string {
  return `${Number(price).toLocaleString("ru-RU")} ₽`;
}
