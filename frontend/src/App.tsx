import { Link, Route, Routes } from "react-router-dom";
import Catalog from "./pages/Catalog";
import Product from "./pages/Product";
import Placeholder from "./pages/Placeholder";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Cart from "./pages/Cart";
import { useAuth } from "./auth";

export default function App() {
  const { user, loading, logout } = useAuth();

  return (
    <div className="layout">
      <header className="header">
        <div className="container header__inner">
          <Link to="/" className="logo">
            Крой
          </Link>
          <nav className="nav">
            <Link to="/?gender=women">Женское</Link>
            <Link to="/?gender=men">Мужское</Link>
          </nav>
          <div className="header__actions">
            {user ? (
              <>
                <span className="header__user" title={user.email}>
                  {user.full_name}
                </span>
                <button type="button" className="link-button" onClick={logout}>
                  Выйти
                </button>
              </>
            ) : (
              !loading && <Link to="/login">Войти</Link>
            )}
            <Link to="/cart">Корзина</Link>
          </div>
        </div>
      </header>

      <main className="container main">
        <Routes>
          <Route path="/" element={<Catalog />} />
          <Route path="/products/:id" element={<Product />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/cart" element={<Cart />} />
          <Route path="*" element={<Placeholder title="Страница не найдена" notFound />} />
        </Routes>
      </main>

      <footer className="footer">
        <div className="container">© Крой, учебный проект РТУ МИРЭА</div>
      </footer>
    </div>
  );
}
