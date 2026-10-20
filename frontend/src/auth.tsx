import { ReactNode, createContext, useContext, useEffect, useState } from "react";
import * as api from "./api";

// Кто вошёл. Токен лежит в localStorage, пользователя при загрузке страницы
// узнаём у сервера через /api/auth/me.
interface AuthState {
  user: api.User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: api.RegisterData) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<api.User | null>(null);
  const [loading, setLoading] = useState(() => api.getToken() !== null);

  useEffect(() => {
    if (!api.getToken()) return;
    api
      .getMe()
      .then(setUser)
      .catch((e: unknown) => {
        // Токен истёк или недействителен — выходим. При недоступном сервере токен не трогаем.
        if (e instanceof api.ApiError && e.status === 401) api.setToken(null);
      })
      .finally(() => setLoading(false));
  }, []);

  function accept(res: api.AuthResponse) {
    api.setToken(res.access_token);
    setUser(res.user);
  }

  const value: AuthState = {
    user,
    loading,
    login: async (email, password) => accept(await api.login(email, password)),
    register: async (data) => accept(await api.register(data)),
    logout: () => {
      api.setToken(null);
      setUser(null);
    },
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth вне AuthProvider");
  return ctx;
}
