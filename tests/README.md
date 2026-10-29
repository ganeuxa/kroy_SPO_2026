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

## Границы

Из командного отчёта покрыты выбранные тимлидом Q1, Q3, Q5, C1, C2, C3, C8, C10; остальные Q/C не входят в этот отдельный набор. Не проверяет неготовые оформление заказа, оплату и админку; не является полным аудитом безопасности или нагрузочным тестированием.

## Проверки из командного отчёта

Источник: «ОТЧЕТ СПО 1 этап команда крой», раздел 5 «Проверка типовых запросов, связей и ограничений».

```sh
QA_NGINX=1 python -m pytest tests/pytest/test_report_stage1.py -v
```

Без `QA_NGINX=1` тот же файл проверяет dev-стенд.

| ID | Проверка |
|---|---|
| Q1 | Женское/унисекс, M, чёрный, остаток > 0: две точные строки из отчёта |
| Q3 | Три варианта футболки оверсайз, размеры, цвета и остатки |
| Q5 | Итоги четырёх seed-заказов совпадают с суммами их позиций |
| C1 | Отрицательный остаток отклоняется CHECK |
| C2 | Повторный anna@example.com отклоняется UNIQUE |
| C3 | Заказ с user_id=9999 отклоняется FK |
| C8 | Роль kroy_app не может удалить заказ |
| C10 | Роль kroy_app читает 8 товаров и добавляет одну строку в favorites |

SQL-запросы Q перенесены из документа. Команды C реализуют действия его таблицы. Проверяются точные SQLSTATE и имена ограничений. Все изменения откатываются. Нужны исходные seed-данные (в том числе отсутствие пользователя 9999).
