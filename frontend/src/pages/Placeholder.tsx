import { Link } from "react-router-dom";

// Временная страница для маршрутов, которые появятся в следующих работах.
export default function Placeholder({ title, notFound = false }: { title: string; notFound?: boolean }) {
  return (
    <section className="placeholder">
      <h1>{title}</h1>
      <p>{notFound ? "Такой страницы нет." : "Этот раздел ещё в разработке."}</p>
      <Link to="/">Вернуться в каталог</Link>
    </section>
  );
}
