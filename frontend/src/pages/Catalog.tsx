import { FormEvent, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ApiError,
  Filters,
  GENDER_LABELS,
  ProductList,
  formatPrice,
  getFilters,
  getProducts,
} from "../api";
import ProductImage from "../components/ProductImage";

const PAGE_SIZE = 24;
const FILTER_KEYS = ["gender", "category", "size", "color", "price_min", "price_max", "q", "sort"];

export default function Catalog() {
  // Фильтры живут в адресной строке: ссылку на выдачу можно скопировать,
  // а кнопка «Назад» возвращает к прошлым фильтрам.
  const [params, setParams] = useSearchParams();
  const [filters, setFilters] = useState<Filters | null>(null);
  const [data, setData] = useState<ProductList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(params.get("q") ?? "");

  const page = Math.max(1, Number(params.get("page") ?? 1) || 1);

  useEffect(() => {
    getFilters().then(setFilters).catch(() => setFilters(null));
  }, []);

  useEffect(() => {
    setSearch(params.get("q") ?? "");
    const query: Record<string, string> = {};
    for (const key of FILTER_KEYS) {
      const value = params.get(key);
      if (value) query[key] = value;
    }
    setLoading(true);
    setError(null);
    getProducts({ ...query, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE })
      .then(setData)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Не удалось загрузить каталог"))
      .finally(() => setLoading(false));
  }, [params, page]);

  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete("page");
    setParams(next);
  }

  function onSearch(e: FormEvent) {
    e.preventDefault();
    update("q", search.trim());
  }

  function reset() {
    setSearch("");
    setParams(new URLSearchParams());
  }

  const pages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="catalog">
      <aside className="filters">
        <form onSubmit={onSearch} className="filters__search">
          <input
            type="search"
            placeholder="Поиск по названию"
            value={search}
            maxLength={100}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button type="submit">Найти</button>
        </form>

        <label>
          Для кого
          <select value={params.get("gender") ?? ""} onChange={(e) => update("gender", e.target.value)}>
            <option value="">Все</option>
            {Object.entries(GENDER_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label>
          Категория
          <select value={params.get("category") ?? ""} onChange={(e) => update("category", e.target.value)}>
            <option value="">Все</option>
            {filters?.categories.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Размер
          <select value={params.get("size") ?? ""} onChange={(e) => update("size", e.target.value)}>
            <option value="">Любой</option>
            {filters?.sizes.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>

        <label>
          Цвет
          <select value={params.get("color") ?? ""} onChange={(e) => update("color", e.target.value)}>
            <option value="">Любой</option>
            {filters?.colors.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>

        <fieldset className="filters__price">
          <legend>Цена, ₽</legend>
          <input
            type="number"
            min={0}
            placeholder={filters?.price_min ? `от ${Math.floor(Number(filters.price_min))}` : "от"}
            defaultValue={params.get("price_min") ?? ""}
            key={`min-${params.get("price_min")}`}
            onBlur={(e) => update("price_min", e.target.value)}
          />
          <input
            type="number"
            min={0}
            placeholder={filters?.price_max ? `до ${Math.ceil(Number(filters.price_max))}` : "до"}
            defaultValue={params.get("price_max") ?? ""}
            key={`max-${params.get("price_max")}`}
            onBlur={(e) => update("price_max", e.target.value)}
          />
        </fieldset>

        <button type="button" className="link-button" onClick={reset}>
          Сбросить фильтры
        </button>
      </aside>

      <section className="results">
        <div className="results__bar">
          <span>{data ? `Найдено: ${data.total}` : " "}</span>
          <select value={params.get("sort") ?? "new"} onChange={(e) => update("sort", e.target.value)}>
            <option value="new">Сначала новые</option>
            <option value="price_asc">Сначала дешевле</option>
            <option value="price_desc">Сначала дороже</option>
          </select>
        </div>

        {loading && <p className="status">Загрузка…</p>}
        {error && <p className="status status--error">{error}</p>}
        {!loading && !error && data?.items.length === 0 && (
          <p className="status">
            Ничего не найдено.{" "}
            <button type="button" className="link-button" onClick={reset}>
              Показать весь каталог
            </button>
          </p>
        )}

        {!loading && !error && data && data.items.length > 0 && (
          <ul className="grid">
            {data.items.map((p) => (
              <li key={p.id} className="card">
                <Link to={`/products/${p.id}`}>
                  <ProductImage name={p.name} imageKey={p.image_key} />
                  <div className="card__body">
                    <span className="card__name">{p.name}</span>
                    <span className="card__meta">
                      {p.category.name} · {GENDER_LABELS[p.gender]}
                    </span>
                    <span className="card__price">{formatPrice(p.price)}</span>
                    {!p.in_stock && <span className="badge">Нет в наличии</span>}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}

        {pages > 1 && (
          <nav className="pager">
            {Array.from({ length: pages }, (_, i) => i + 1).map((n) => (
              <button
                key={n}
                type="button"
                className={n === page ? "active" : ""}
                onClick={() => {
                  const next = new URLSearchParams(params);
                  next.set("page", String(n));
                  setParams(next);
                }}
              >
                {n}
              </button>
            ))}
          </nav>
        )}
      </section>
    </div>
  );
}
