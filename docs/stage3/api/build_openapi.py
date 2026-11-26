"""Build the checked-in OpenAPI snapshot from FastAPI plus curated Russian text.

The live FastAPI schema is authoritative for paths, parameters, responses and schemas.
stage3-paths.yaml supplies summaries/descriptions and request examples for those operations.
First refresh openapi_current.json from app.openapi() with APP_VERSION, DB_PASSWORD,
and JWT_SECRET set in the environment; then run this file from the repository root.
"""
import json
import pathlib
import yaml

here = pathlib.Path(__file__).parent
spec = json.loads((here / "openapi_current.json").read_text(encoding="utf-8"))
add = yaml.safe_load((here / "stage3-paths.yaml").read_text(encoding="utf-8"))

spec["info"] = {
    "title": "Крой API",
    "version": spec["info"]["version"],
    "description": (
        "Актуальный контракт FastAPI для учебного интернет-магазина одежды «Крой». "
        "Схема собирается из runtime API; stage3-paths.yaml добавляет русские пояснения.\n\n"
        "Общие правила: ошибки — `{\"detail\": \"...\"}`, ошибки валидации (422) — формат FastAPI; суммы — строки "
        "с двумя знаками; даты — ISO 8601 с часовым поясом; списки — `{items, total, limit, offset}`. "
        "Защищённые методы требуют `Authorization: Bearer <токен>`; методы `/api/admin/*` без токена отвечают 401, "
        "покупателю — 403 (NFR-04)."
    ),
}
spec["tags"] = [
    {"name": "service", "description": "Состояние API и сервера"},
    {"name": "catalog", "description": "Каталог, FR-03…FR-06"},
    {"name": "auth", "description": "Регистрация и вход, FR-01, FR-02"},
    {"name": "cart", "description": "Корзина, FR-07"},
    {"name": "orders", "description": "Заказы покупателя, FR-08, FR-10"},
    {"name": "payments", "description": "Оплата в тестовом режиме, FR-09, NFR-09"},
    {"name": "admin", "description": "Админка, FR-13…FR-16. Только роль admin"},
]

# Русские названия существующих методов (FastAPI по умолчанию берёт имя функции)
RU = {("/api/health", "get"): "Состояние API, БД и версия релиза",
      ("/api/products", "get"): "Каталог с фильтрами, поиском и страницами",
      ("/api/products/{product_id}", "get"): "Карточка товара с вариантами",
      ("/api/filters", "get"): "Значения для фильтров каталога",
      ("/api/auth/register", "post"): "Регистрация, сразу возвращает токен",
      ("/api/auth/login", "post"): "Вход по email и паролю",
      ("/api/auth/me", "get"): "Текущий пользователь по токену",
      ("/api/auth/logout", "post"): "Завершить все сеансы пользователя",
      ("/api/cart", "get"): "Корзина текущего пользователя",
      ("/api/cart", "post"): "Добавить вариант товара в корзину"}
for (path, method), title in RU.items():
    if path in spec["paths"] and method in spec["paths"][path]:
        spec["paths"][path][method]["summary"] = title

http_methods = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
for path, item in add["paths"].items():
    if path not in spec["paths"]:
        raise SystemExit(f"{path} is missing from runtime OpenAPI; update FastAPI first")
    for method, curated in item.items():
        if method not in http_methods:
            continue
        operation = spec["paths"][path].get(method)
        if operation is None:
            raise SystemExit(f"{method.upper()} {path} is missing from runtime OpenAPI; update FastAPI first")
        if curated.get("summary"):
            operation["summary"] = curated["summary"]
        if curated.get("description") and not operation.get("description"):
            operation["description"] = curated["description"]
        for media_type, examples in curated.get("requestExamples", {}).items():
            content = operation.get("requestBody", {}).get("content", {}).get(media_type)
            if content is None:
                raise SystemExit(f"{method.upper()} {path} no longer accepts {media_type}")
            content["examples"] = examples

out = here / "openapi.yaml"
out.write_text("# Сгенерировано build_openapi.py, правьте stage3-paths.yaml\n"
               + yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
print(out, len(spec["paths"]), "путей")
