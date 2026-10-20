import { Link, NavLink, Route, Routes } from "react-router-dom";
import Catalog from "./pages/Catalog";
import Product from "./pages/Product";
import Placeholder from "./pages/Placeholder";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Cart from "./pages/Cart";
import { useAuth } from "./auth";

// Тема «домашняя страничка из 90-х» (в духе Geo для Bootstrap): звёздное небо, Comic Sans,
// радужный логотип, яркие объёмные кнопки, «Under construction», счётчик и веб-кольцо.
// Счётчик, веб-кольцо и «гостевая книга» — декорация, никуда не ведут.

export default function App() {
  const { user, loading, logout } = useAuth();

  return (
    <div className="page">
      <nav className="navbar">
        <Link to="/" className="navbar__brand">
          ★ Крой ★
        </Link>
        <div className="navbar__links">
          <NavLink to="/" end className="btn btn-primary">
            Главная
          </NavLink>
          <Link to="/?gender=women" className="btn btn-danger">
            Женское
          </Link>
          <Link to="/?gender=men" className="btn btn-info">
            Мужское
          </Link>
          <NavLink to="/cart" className="btn btn-warning">
            Корзина
          </NavLink>
          {user ? (
            <button type="button" className="btn btn-default" onClick={logout} title={user.email}>
              Выйти ({user.full_name})
            </button>
          ) : (
            !loading && (
              <NavLink to="/login" className="btn btn-success">
                Войти
              </NavLink>
            )
          )}
        </div>
      </nav>

      <header className="hero">
        <Link to="/" className="rainbow" aria-label="Крой, на главную">
          КРОЙ
        </Link>
        <p className="hero__lead">
          Добро пожаловать на сайт нашего магазина!!! <span className="blink">NEW!</span>
        </p>
        <div className="construction" aria-hidden="true">
          <span>🚧 Сайт в разработке 🚧</span>
        </div>
      </header>

      <div className="marquee" aria-hidden="true">
        <span>
          ☆ Новые поступления каждую неделю! ☆ Доставка по всей России!!! ☆ Зарегистрируйся и получи
          скидку! ☆ Добавь нас в Избранное! ☆
        </span>
      </div>

      <main className="window">
        <div className="window__title">
          <span>kroy.exe</span>
          <span className="window__buttons" aria-hidden="true">
            <i>_</i>
            <i>□</i>
            <i>×</i>
          </span>
        </div>
        <div className="window__body">
          <Routes>
            <Route path="/" element={<Catalog />} />
            <Route path="/products/:id" element={<Product />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/cart" element={<Cart />} />
            <Route path="*" element={<Placeholder title="Страница не найдена" notFound />} />
          </Routes>
        </div>
      </main>

      <hr className="rainbow-hr" />

      <footer className="footer">
        <div className="counter" aria-label="Счётчик посещений">
          Вы посетитель №
          {"0013666".split("").map((d, i) => (
            <b key={i}>{d}</b>
          ))}
        </div>
        <div className="webring" aria-hidden="true">
          <span>« Пред.</span>
          <span className="webring__name">Веб-кольцо модных магазинов</span>
          <span>След. »</span>
        </div>
        <div className="badges" aria-hidden="true">
          <span className="badge88 badge88--ns">Netscape Now!</span>
          <span className="badge88 badge88--ie">800×600</span>
          <span className="badge88 badge88--html">HTML 3.2</span>
        </div>
        <p>
          © 1998–2026 «Крой» · Учебный проект РТУ МИРЭА · Вебмастер: Angel20071337RUSkiller
          <br />
          Не забудьте подписать гостевую книгу!!!
        </p>
      </footer>
    </div>
  );
}
