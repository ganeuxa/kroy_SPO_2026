import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// В разработке Vite проксирует /api на сервер FastAPI.
// В тестовом окружении то же самое будет делать Nginx, поэтому
// фронт всегда обращается к относительному пути /api и про адрес сервера не знает.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": process.env.VITE_PROXY_TARGET ?? "http://localhost:8000",
    },
  },
});
