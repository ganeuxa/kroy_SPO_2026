import { Link, Route, Routes } from "react-router-dom";
import Catalog from "./pages/Catalog";
import Product from "./pages/Product";
import Placeholder from "./pages/Placeholder";

export default function App() {
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
            {/* Вход и корзина — задачи №6 */}
            <Link to="/login">Войти</Link>
            <Link to="/cart">Корзина</Link>
          </div>
        </div>
      </header>

      <main className="container main">
        <Routes>
          <Route path="/" element={<Catalog />} />
          <Route path="/products/:id" element={<Product />} />
          <Route path="/login" element={<Placeholder title="Вход" />} />
          <Route path="/register" element={<Placeholder title="Регистрация" />} />
          <Route path="/cart" element={<Placeholder title="Корзина" />} />
          <Route path="*" element={<Placeholder title="Страница не найдена" notFound />} />
        </Routes>
      </main>

      <footer className="footer">
        <div className="container">© Крой, учебный проект РТУ МИРЭА</div>
      </footer>
    </div>
  );
}
