# Проверки этапа II

Интеграционные pytest-тесты работают с отдельными локальными контейнерами и seed-данными проекта. Есть два режима: окружение разработки и production-сборка за Nginx. Playwright проверяет интерфейс отдельно.

## Подготовка

Нужны Python 3.10+, Git и запущенный Docker Desktop.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-test.txt
mkdir -p qa-results
```

В PowerShell: `.venv\Scripts\Activate.ps1` вместо `source`.

Если `.env.qa` ещё нет, скопировать `.env.example` в `.env.qa`, заменить три `change-me-*` на собственные случайные значения и задать:

```dotenv
DB_HOST_PORT=15432
BACKEND_HOST_PORT=18000
FRONTEND_HOST_PORT=15173
TEST_HTTP_PORT=18080
```

Не перезаписывать существующий `.env.qa`. Он исключён из Git, как и результаты и `.venv`.

## Окружение разработки

```sh
docker compose --env-file .env.qa -p kroy-varvara-qa up -d --build
python -m pytest -v
python -m pytest -v --run-ops --junitxml=qa-results/pytest-dev.xml
```

Адрес интерфейса: http://localhost:15173. API: http://localhost:18000.
Без `--run-ops` проверки остановки/перезапуска пропущены. Nginx-проверки в этом режиме также пропущены.

## Nginx: окружение №7–8

```sh
docker compose -f docker-compose.test.yml --env-file .env.qa -p kroy-varvara-nginx-qa up -d --build
QA_NGINX=1 python -m pytest -v --run-ops --junitxml=qa-results/pytest-nginx.xml
```

В PowerShell перед pytest: `$env:QA_NGINX="1"`; после проверки: `Remove-Item Env:QA_NGINX`.
Адрес: http://localhost:18080, запросы API тоже проходят через Nginx. Порты БД и backend не публикуются.
Один тест сборки пропускается: в конечном образе Nginx нет Node, production-сборка уже выполнена при сборке образа.

## Выбор тестов

```sh
python -m pytest tests/pytest/test_auth.py -v
python -m pytest tests/pytest/test_cart.py -v
python -m pytest tests/pytest/test_catalog.py -v
python -m pytest tests/pytest/test_database.py -v
python -m pytest tests/pytest/test_security.py -v
```

Регрессионный тест `test_password_suffix_after_72_utf8_bytes_is_rejected` проверяет DEF-02: пароль с изменением после 72-го байта должен отклоняться. Тест не помечен xfail.

## Изоляция и побочные эффекты

- Использовать только указанные QA-проекты. Тесты создают уникальных пользователей `qa-pytest-*`; они остаются в тестовой БД.
- Seed должен содержать исходные 8 товаров и вариант 1. Тесты корзины создают собственные аккаунты и не зависят от порядка выполнения.
- SQL-проверки откатывают транзакции и проверяют точный SQLSTATE. Проверки доступа временно меняют доступность товара/пользователя и восстанавливают её через fixture.
- `--run-ops` временно останавливает сервисы своего тестового проекта; не пользоваться этим стендом в процессе прогона.
- Запускать последовательно, без pytest-xdist: некоторые проверки изменяют общие seed-товары.
- Если health недоступен, тесты показывают ошибку подготовки, а не ложный PASS.

## UI и скриншоты

Нужны пакет Playwright и его Chromium. Пакет можно установить в отдельной папке инструментов через `npm install playwright` и `npx playwright install chromium`.

```sh
node tests/stage2_ui.cjs
# через Nginx:
QA_UI_URL=http://127.0.0.1:18080 node tests/stage2_ui.cjs
```

При отдельной установке задать `PLAYWRIGHT_MODULE` абсолютным путём к пакету. `QA_CHROMIUM` позволяет указать установленный Chromium. Скрипт создаёт `qa-results/` и сохраняет JSON и скриншоты. Chromium — единственный проверенный браузер.

## Особенность первого запуска на проверенном Mac

Скрипт `03_app_role.sh` завершался `bad interpreter: Permission denied`; роль `kroy_app` не создавалась. После перезапуска БД показывала healthy, но API возвращал 503. Это отдельный открытый дефект запуска, не скрываемый успешными функциональными тестами.

Если в журнале действительно есть эта ошибка и роль ещё отсутствует, для продолжения тестов на новом Nginx-стенде использовался обход:

```sh
docker compose -f docker-compose.test.yml --env-file .env.qa -p kroy-varvara-nginx-qa exec -T db sh /docker-entrypoint-initdb.d/03_app_role.sh
```

Для dev-стенда убрать `-f docker-compose.test.yml` и использовать `-p kroy-varvara-qa`. Не повторять при существующей роли и не удалять тома с данными.

## Границы

Набор не подменяет отсутствующие определения Q1–Q7/C1–C10. Не проверяет неготовые оформление заказа, оплату и админку; не является полным аудитом безопасности или нагрузочным тестированием.
