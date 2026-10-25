# Крой — интернет-магазин одежды

Учебный проект по дисциплине «Создание программного обеспечения», РТУ МИРЭА, группа ЭФБО-07-24.

Сейчас это каркас этапа II (практическая работа №5): сервер, БД и интерфейс каталога.
Готово: просмотр каталога, фильтры, поиск, карточка товара (FR-03…FR-06),
регистрация, вход и добавление в корзину (FR-01, FR-02, FR-07).
Есть тестовое окружение: Nginx, собранный фронт, healthcheck и автоперезапуск (№7–8).

## Стек

| Слой | Технологии |
|---|---|
| Клиент | React 18, TypeScript, Vite |
| Сервер | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic |
| БД | PostgreSQL 16 |
| Окружение | Docker Compose |

## Структура

```
kroy/
├── docker-compose.yml   окружение разработки: db, backend, frontend
├── docker-compose.test.yml  тестовое окружение: db, backend, nginx со сборкой фронта
├── .env.example         шаблон переменных окружения (без настоящих паролей)
├── db/                  выполняется при первом запуске БД, по порядку:
│   ├── 01_schema.sql      таблицы, ограничения, индексы
│   ├── 02_seed.sql        тестовые данные
│   └── 03_app_role.sh     роль kroy_app с ограниченными правами
├── backend/app/
│   ├── main.py            приложение, логирование, обработка ошибок
│   ├── config.py          настройки из переменных окружения
│   ├── db.py              подключение к PostgreSQL
│   ├── models.py          модели таблиц
│   ├── schemas.py         форматы ответов API
│   ├── security.py        хэши паролей (bcrypt), JWT, текущий пользователь
│   └── routers/           health.py, products.py, auth.py, cart.py
└── frontend/
    ├── Dockerfile.prod    сборка фронта и образ Nginx для тестового окружения
    ├── nginx/             конфигурация Nginx: статика, прокси /api, заголовки
    └── src/
    ├── api.ts             все запросы к серверу
    ├── App.tsx            маршруты и общий шаблон
    ├── auth.tsx           кто вошёл: токен в localStorage, проверка через /api/auth/me
    └── pages/             Catalog, Product, Login, Register, Cart, Placeholder
```

## Запуск

Нужны Docker Desktop (или Docker Engine с плагином compose) и git.

1. Склонировать репозиторий и перейти в папку проекта.
2. Создать файл с настройками из шаблона:
   ```bash
   cp .env.example .env
   ```
   В `.env` заменить `change-me-owner` и `change-me-app` на свои пароли,
   а `change-me-jwt` на длинную случайную строку (ключ подписи токенов входа).
   Если `.env` создан до №6, добавить в него строку `JWT_SECRET=...`, иначе compose не запустится.
   Если порты 5432, 8000 или 5173 заняты другим проектом, поменять `DB_HOST_PORT`,
   `BACKEND_HOST_PORT`, `FRONTEND_HOST_PORT`.
3. Запустить:
   ```bash
   docker compose up -d --build
   ```
   Первый запуск занимает несколько минут: скачиваются образы и ставятся зависимости.
4. Открыть:
   - интерфейс: http://localhost:5173
   - документация API (Swagger): http://localhost:8000/api/docs
   - проверка состояния: http://localhost:8000/api/health

Остановить: `docker compose down`. Данные БД при этом сохраняются в томе `pgdata`.

### Пересоздать БД с нуля

Скрипты из `db/` выполняются только при первом создании тома. Чтобы применить
изменения в них или вернуть тестовые данные:

```bash
docker compose down -v
docker compose up -d
```

`-v` удаляет том с данными, всё, что было в БД, пропадёт.

### Подключиться к БД

```bash
docker compose exec db psql -U kroy_owner -d kroy
```

Или из DBeaver/pgAdmin: `localhost`, порт из `DB_HOST_PORT`, БД `kroy`.
Пользователь `kroy_app` — права как у приложения, `kroy_owner` — владелец схемы.

## Тестовое окружение (№7–8)

Отдельный compose-файл, который запускает приложение так, как оно будет работать на стенде:
фронт собран в статику и отдаётся Nginx, запросы `/api/` Nginx передаёт в FastAPI.
Окружение разработки при этом не затрагивается: другое имя проекта (`kroy-test`) и свой том БД.

```
браузер ──► :8080 Nginx ──(сеть front)──► backend:8000 ──(сеть back, internal)──► db:5432
            статика React                 FastAPI                                PostgreSQL
```

| | Разработка (`docker-compose.yml`) | Тест (`docker-compose.test.yml`) |
|---|---|---|
| Фронт | Vite dev server, горячая перезагрузка | `npm run build`, раздаёт Nginx |
| Backend | `--reload`, исходники смонтированы | код внутри образа, без `--reload` |
| Порты наружу | 5173, 8000, 5432 (на 127.0.0.1) | только 8080 (Nginx) |
| Healthcheck | только БД | БД, backend, Nginx |
| Перезапуск | `unless-stopped` у БД и backend | `unless-stopped` у всех |
| Права | | backend и Nginx не от root, ФС только для чтения, `cap_drop: ALL` |

Запуск (нужен тот же `.env`, что и для разработки):

```bash
docker compose -f docker-compose.test.yml up -d --build
docker compose -f docker-compose.test.yml ps          # все три сервиса (healthy)
```

Открыть http://localhost:8080. Swagger: http://localhost:8080/api/docs.
Порт меняется переменной `TEST_HTTP_PORT` в `.env`.

Полезные команды:

```bash
docker compose -f docker-compose.test.yml logs -f backend nginx   # логи
docker compose -f docker-compose.test.yml restart backend         # перезапуск сервиса
docker compose -f docker-compose.test.yml down                    # остановить, данные сохраняются
docker compose -f docker-compose.test.yml down -v                 # остановить и удалить БД
```

Если backend недоступен, Nginx отвечает на `/api/...` кодом 503 и JSON
`{"detail": "Сервер временно недоступен, попробуйте позже"}`, интерфейс показывает это сообщение.

## API

| Метод | Путь | Назначение | Коды |
|---|---|---|---|
| GET | `/api/health` | Сервер жив и БД доступна | 200, 503 |
| GET | `/api/products` | Каталог с фильтрами и поиском | 200, 422, 503 |
| GET | `/api/products/{id}` | Карточка товара с вариантами | 200, 404, 422, 503 |
| GET | `/api/filters` | Категории, размеры, цвета, диапазон цен для фильтров | 200, 503 |
| POST | `/api/auth/register` | Регистрация, сразу возвращает токен | 201, 409, 422 |
| POST | `/api/auth/login` | Вход по email и паролю | 200, 401, 403, 422 |
| GET | `/api/auth/me` | Текущий пользователь по токену | 200, 401 |
| GET | `/api/cart` | Корзина текущего пользователя | 200, 401 |
| POST | `/api/cart` | Добавить вариант товара в корзину | 200, 401, 404, 409, 422 |

### Вход и корзина

Регистрация и вход возвращают JWT:

```json
{"access_token": "eyJ...", "token_type": "bearer", "user": {"id": 2, "email": "anna@example.com", "full_name": "Анна Смирнова", "phone": "+79001112233", "role": "customer"}}
```

Токен передаётся в заголовке `Authorization: Bearer <токен>` и действует сутки.
В Swagger: кнопка Authorize, вставить токен. Ключ подписи берётся из `JWT_SECRET` в `.env`.

- Регистрация: `email`, `password` (8–72 символа), `full_name`, необязательный `phone`
  (`+79001112233`). Email хранится в нижнем регистре, занятый email — 409.
- Вход: неверный email и неверный пароль дают одно и то же 401 «Неверный email или пароль».
  Заблокированный пользователь — 403.
- `POST /api/cart` принимает `{"variant_id": 1, "quantity": 1}` (`quantity` от 1 до 99,
  по умолчанию 1). Если вариант уже в корзине, количество складывается. Больше остатка
  на складе положить нельзя: 409 «Недостаточно товара: в наличии N шт.». Нет варианта
  или товар скрыт — 404. В ответе вся корзина с суммой.

```bash
curl -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" \
     -d '{"email": "anna@example.com", "password": "KroyTest-2026"}'
curl http://localhost:8000/api/cart -H "Authorization: Bearer <токен>"
curl -X POST http://localhost:8000/api/cart -H "Authorization: Bearer <токен>" \
     -H "Content-Type: application/json" -d '{"variant_id": 1, "quantity": 2}'
```

Параметры `/api/products`:

| Параметр | Пример | Описание |
|---|---|---|
| `gender` | `women` | `men`, `women`, `unisex`. Унисекс попадает и в мужской, и в женский раздел |
| `category` | `jeans` | slug категории |
| `size`, `color` | `M`, `чёрный` | только товары, у которых этот вариант есть в наличии |
| `price_min`, `price_max` | `1000`, `4000` | диапазон цены, `price_min` не больше `price_max` |
| `q` | `худи` | поиск по части названия без учёта регистра |
| `sort` | `price_asc` | `new` (по умолчанию), `price_asc`, `price_desc` |
| `limit`, `offset` | `24`, `0` | страница выдачи, `limit` от 1 до 100 |

Ошибки возвращаются в виде `{"detail": "..."}`. Ошибки валидации параметров (422)
FastAPI возвращает списком в `detail`.

Примеры:

```bash
curl "http://localhost:8000/api/products?gender=women&sort=price_asc"
curl "http://localhost:8000/api/products/2"
curl "http://localhost:8000/api/products/999"          # 404 Товар не найден
curl "http://localhost:8000/api/products?gender=kids"  # 422
```

## Тестовые учётные записи

Хэши в `db/02_seed.sql` настоящие, с ними можно войти через `/api/auth/login`.
У ilya@example.com в корзине уже два товара.

| Email | Пароль | Роль |
|---|---|---|
| admin@kroy.test | KroyAdmin-2026 | admin |
| anna@example.com | KroyTest-2026 | customer |
| max@example.com | KroyTest-2026 | customer |
| ilya@example.com | KroyTest-2026 | customer |

Это учебные пароли. На стенде, доступном снаружи, их нужно сменить.

## Результат первой проверки (№5)

Проверено 14.10.2026 на Windows 11, Docker 29.4.2:

| Проверка | Ожидание | Результат |
|---|---|---|
| `docker compose up -d --build` | Три контейнера запущены, БД healthy | ✔ |
| Скрипты `db/` при первом запуске | 01, 02, 03 выполнены без ошибок | ✔ |
| `GET /api/health` | 200, `db: ok` | ✔ |
| `GET /api/products` | 8 товаров из seed | ✔ |
| Женское, размер M, чёрный (запрос Q1 из №4) | Футболка оверсайз, Худи с капюшоном | ✔ |
| Поиск «худи» | Худи с капюшоном | ✔ |
| `GET /api/products/999` | 404 «Товар не найден» | ✔ |
| `gender=kids`, `limit=1000`, `price_min > price_max` | 422 | ✔ |
| БД остановлена | `/api/health` и `/api/products` отвечают 503, сервер не падает | ✔ |
| БД снова запущена | Сервер переподключается сам, 200 | ✔ |
| От `kroy_app`: удалить заказ / удалить таблицу | permission denied / must be owner | ✔ |
| Каталог и карточка в браузере, ширина 360 px | Без горизонтальной прокрутки | ✔ |

## Правила работы

- `main` всегда рабочая, изменения только через pull request с ревью одного участника.
- Ветки: `feature/<задача>`, коммиты с префиксом `feat:`, `fix:`, `docs:`, `refactor:`.
- `.env` и пароли в репозиторий не коммитим.
- Решения записываем в `docs/decisions.md`.
