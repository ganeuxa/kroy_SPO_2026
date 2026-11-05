import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AdminProduct, AdminProductInput, Category, Gender, Page, createAdminProduct, formatPrice, getAdminProducts, getFilters } from "../api";
import { errorText } from "./orderUi";

const blank: AdminProductInput = { category_id: 0, name: "", description: "", gender: "unisex", price: "", is_active: true };
export default function AdminProducts() {
  const navigate = useNavigate();
  const [data, setData] = useState<Page<AdminProduct> | null>(null); const [categories, setCategories] = useState<Category[]>([]);
  const [search, setSearch] = useState(""); const [active, setActive] = useState(""); const [page, setPage] = useState(1);
  const [form, setForm] = useState<AdminProductInput>(blank); const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false); const [loading, setLoading] = useState(true);
  async function load() { setLoading(true); setError(null); try { setData(await getAdminProducts({ q: search.trim() || undefined, is_active: active || undefined, limit: 20, offset: (page - 1) * 20 })); } catch (e) { setError(errorText(e)); } finally { setLoading(false); } }
  useEffect(() => { void load(); }, [search, active, page]);
  useEffect(() => { getFilters().then((f) => setCategories(f.categories)).catch((e) => setError(errorText(e))); }, []);
  async function create(e: FormEvent) { e.preventDefault(); setBusy(true); setError(null); try { const product = await createAdminProduct(form); navigate(`/admin/products/${product.id}`); } catch (e) { setError(errorText(e)); } finally { setBusy(false); } }
  return <section className="flow-page admin-page"><div className="flow-heading"><h1>Товары</h1><Link to="/admin/orders">Заказы →</Link></div>{error && <p className="status--error" role="alert">{error}</p>}
    <div className="flow-layout"><div className="flow-list"><div className="flow-panel toolbar"><label>Поиск<input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Название товара" /></label><label>Видимость<select value={active} onChange={(e) => { setActive(e.target.value); setPage(1); }}><option value="">Все</option><option value="true">Видимые</option><option value="false">Скрытые</option></select></label></div>
      {loading ? <p className="status">Загружаем товары…</p> : !data?.items.length ? <div className="flow-panel">Товаров нет.</div> : <div className="flow-list">{data.items.map((p) => <Link key={p.id} to={`/admin/products/${p.id}`} className="flow-panel order-card"><div><b>{p.name}</b><span className="muted">#{p.id} · {p.category.name} · {p.variants.length} вариантов</span></div><span>{p.is_active ? "Виден" : "Скрыт"}</span><strong>{formatPrice(p.price)}</strong></Link>)}</div>}
      {data && <div className="pager"><button disabled={page === 1} onClick={() => setPage(page - 1)}>Назад</button><span>{page} / {Math.max(1, Math.ceil(data.total / 20))}</span><button disabled={page * 20 >= data.total} onClick={() => setPage(page + 1)}>Далее</button></div>}</div>
      <form className="flow-panel form" onSubmit={create}><h2>Новый товар</h2><label>Название<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={160} required /></label><label>Категория<select value={form.category_id || ""} onChange={(e) => setForm({ ...form, category_id: Number(e.target.value) })} required><option value="">Выберите категорию</option>{categories.map((c) => <option value={c.id} key={c.id}>{c.name}</option>)}</select></label><label>Для кого<select value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value as Gender })}><option value="unisex">Унисекс</option><option value="men">Мужское</option><option value="women">Женское</option></select></label><label>Цена, ₽<input type="number" min="0.01" step="0.01" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} required /></label><label>Описание<textarea value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} maxLength={5000} /></label><button className="primary" disabled={busy}>{busy ? "Сохраняем…" : "Создать товар"}</button></form>
    </div>
  </section>;
}
