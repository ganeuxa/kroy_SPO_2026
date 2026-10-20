import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../api";
import { useAuth } from "../auth";
import { safeNext } from "./Login";

interface Fields {
  full_name: string;
  email: string;
  phone: string;
  password: string;
  password2: string;
}

// Те же правила, что на сервере (schemas.RegisterIn), чтобы ошибку было видно сразу у поля
function validate(f: Fields): Partial<Record<keyof Fields, string>> {
  const errors: Partial<Record<keyof Fields, string>> = {};
  if (!f.full_name.trim()) errors.full_name = "Укажите имя";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email.trim())) errors.email = "Неверный email";
  if (f.phone && !/^\+?[0-9]{10,15}$/.test(f.phone)) errors.phone = "Телефон в формате +79001112233";
  if (f.password.length < 8) errors.password = "Не короче 8 символов";
  else if (new TextEncoder().encode(f.password).length > 72) errors.password = "Слишком длинный пароль";
  if (f.password2 !== f.password) errors.password2 = "Пароли не совпадают";
  return errors;
}

export default function Register() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));

  const [f, setF] = useState<Fields>({ full_name: "", email: "", phone: "", password: "", password2: "" });
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  if (user) return <Navigate to={next} replace />;

  const errors = validate(f);
  const shown = touched ? errors : {};

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    setError(null);
    if (Object.keys(errors).length) return;
    setSending(true);
    try {
      await register({
        full_name: f.full_name.trim(),
        email: f.email.trim(),
        password: f.password,
        phone: f.phone || undefined,
      });
      navigate(next, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось зарегистрироваться");
    } finally {
      setSending(false);
    }
  }

  function field(name: keyof Fields, label: string, type: string, autoComplete: string, hint?: string) {
    return (
      <label>
        {label}
        <input
          type={type}
          autoComplete={autoComplete}
          value={f[name]}
          aria-invalid={Boolean(shown[name])}
          placeholder={hint}
          onChange={(e) => setF({ ...f, [name]: e.target.value })}
        />
        {shown[name] && <span className="form__error">{shown[name]}</span>}
      </label>
    );
  }

  return (
    <section className="auth">
      <h1>Регистрация</h1>
      <form className="form" onSubmit={onSubmit} noValidate>
        {field("full_name", "Имя", "text", "name")}
        {field("email", "Email", "email", "email")}
        {field("phone", "Телефон (необязательно)", "tel", "tel", "+79001112233")}
        {field("password", "Пароль", "password", "new-password", "не короче 8 символов")}
        {field("password2", "Повторите пароль", "password", "new-password")}
        {error && <p className="status status--error" role="alert">{error}</p>}
        <button type="submit" className="primary" disabled={sending}>
          {sending ? "Создаём аккаунт…" : "Зарегистрироваться"}
        </button>
      </form>
      <p className="auth__alt">
        Уже есть аккаунт? <Link to={`/login?next=${encodeURIComponent(next)}`}>Войти</Link>
      </p>
    </section>
  );
}
