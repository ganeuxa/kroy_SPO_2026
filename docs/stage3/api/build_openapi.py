"""Собирает docs/stage3/api/openapi.yaml: текущий API (из кода, файл openapi_current.json) + методы этапа III.
Запуск из корня репозитория:
  DB_PASSWORD=x JWT_SECRET=x python -c "import json,sys; sys.path.insert(0,'backend'); from app.main import app; json.dump(app.openapi(), open('docs/stage3/api/openapi_current.json','w'), ensure_ascii=False)"
  python docs/stage3/api/build_openapi.py
"""
import json, pathlib, yaml

here = pathlib.Path(__file__).parent
spec = json.loads((here / "openapi_current.json").read_text(encoding="utf-8"))
add = yaml.safe_load((here / "stage3-paths.yaml").read_text(encoding="utf-8"))

spec["info"] = {
    "title": "Крой API",
    "version": "0.3.0",
    "description": (
        "Интернет-магазин одежды «Крой». Версия этапа III: корзина целиком (FR-07), заказы (FR-08, FR-10), "
        "тестовая оплата (FR-09) и админка (FR-13…FR-16).\n\n"
        "Общие правила: ошибки — `{\"detail\": \"...\"}`, ошибки валидации (422) — формат FastAPI; суммы — строки "
        "с двумя знаками; даты — ISO 8601 с часовым поясом; списки — `{items, total, limit, offset}`. "
        "Защищённые методы требуют `Authorization: Bearer <токен>`; методы `/api/admin/*` без токена отвечают 401, "
        "покупателю — 403 (NFR-04)."
    ),
}
spec["tags"] = [
    {"name": "service", "description": "Состояние сервера"},
    {"name": "catalog", "description": "Каталог, FR-03…FR-06"},
    {"name": "auth", "description": "Регистрация и вход, FR-01, FR-02"},
    {"name": "cart", "description": "Корзина, FR-07"},
    {"name": "orders", "description": "Заказы покупателя, FR-08, FR-10"},
    {"name": "payments", "description": "Оплата в тестовом режиме, FR-09, NFR-09"},
    {"name": "admin", "description": "Админка, FR-13…FR-16. Только роль admin"},
]

# Изменения существующих ответов: ссылка на фото из MinIO рядом со старым ключом
sch = spec["components"]["schemas"]
sch["ProductListItem"]["properties"]["image_url"] = {"type": ["string", "null"], "example": "/media/products/1/3c9e1f0a.jpg",
    "description": "Новое в этапе III. Готовая ссылка на первое фото"}
sch["ProductDetail"]["properties"]["image_urls"] = {"type": "array", "items": {"type": "string"},
    "description": "Новое в этапе III. Ссылки на фото по порядку"}
sch["CartItemOut"]["properties"]["image_url"] = {"type": ["string", "null"], "description": "Новое в этапе III"}

# Русские названия существующих методов (FastAPI по умолчанию берёт имя функции)
RU = {("/api/health", "get"): "Сервер работает и БД доступна",
      ("/api/products", "get"): "Каталог с фильтрами, поиском и страницами",
      ("/api/products/{product_id}", "get"): "Карточка товара с вариантами",
      ("/api/filters", "get"): "Значения для фильтров каталога",
      ("/api/auth/register", "post"): "Регистрация, сразу возвращает токен",
      ("/api/auth/login", "post"): "Вход по email и паролю",
      ("/api/auth/me", "get"): "Текущий пользователь по токену",
      ("/api/cart", "get"): "Корзина текущего пользователя",
      ("/api/cart", "post"): "Добавить вариант товара в корзину"}
for (path, method), title in RU.items():
    spec["paths"][path][method]["summary"] = title

for path, item in add["paths"].items():
    if path in spec["paths"]:
        raise SystemExit(f"Путь {path} уже есть в текущем API")
    spec["paths"][path] = item
for kind, items in add["components"].items():
    target = spec["components"].setdefault(kind, {})
    for name, val in items.items():
        if name in target:
            raise SystemExit(f"Компонент {kind}/{name} уже есть")
        target[name] = val
spec["components"].setdefault("securitySchemes", {})["HTTPBearer"] = {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}

out = here / "openapi.yaml"
out.write_text("# Сгенерировано build_openapi.py, правьте stage3-paths.yaml\n"
               + yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
print(out, len(spec["paths"]), "путей")
