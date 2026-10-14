# Образ для разработки: Vite dev server с горячей перезагрузкой.
# Для тестового окружения (№7) нужен отдельный этап сборки и Nginx.
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev"]
