import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../api";
import { useAuth } from "../auth";

// Куда вернуться после входа. Только пути внутри сайта, чтобы ?next= не увёл на чужой адрес.
export function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  if (user) return <Navigate to={next} replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSending(true);
    try {
      await login(email.trim(), password);
      navigate(next, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось войти");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="auth">
      <h1>Вход</h1>
      <form className="form" onSubmit={onSubmit} noValidate>
        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label>
          Пароль
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && <p className="status status--error" role="alert">{error}</p>}
        <button type="submit" className="primary" disabled={sending || !email || !password}>
          {sending ? "Входим…" : "Войти"}
        </button>
      </form>
      <p className="auth__alt">
        Нет аккаунта? <Link to={`/register?next=${encodeURIComponent(next)}`}>Зарегистрироваться</Link>
      </p>
    </section>
  );
}
