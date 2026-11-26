# Итоговая проверка Крой

Приложение: коммит 599a6b8129992d89e403aac0dda75371afee886c, main от 26.11.2026.
QA-стенд kroy-varvara-nginx-qa, http://127.0.0.1:18080. Не публичный сервер.
Новые тесты: tests/unit/test_validation.py и tests/load_http.py.
Основной набор: tests/pytest; сценарий браузера: tests/ux_checkout.cjs.

Схема: schema.sql, схема сущностей: schema.md; миграции V002 и V003 приложены.
Исходные результаты приложены отдельно. Персональные .env, дампы БД и токены не включены.

Запуск:
```sh
.venv/bin/python -m pip install -r requirements-test.txt
QA_NGINX=1 .venv/bin/python -m pytest tests/pytest --run-ops -q
python3 tests/load_http.py
```
Модульные тесты и backend_regression.py выполняются внутри backend с PYTHONPATH=/app.
Playwright: QA_URL=http://127.0.0.1:18080; QA_SCREENSHOTS задаёт папку скриншотов.
Учебный QA-администратор нужен для административной ветки сценария.
Нагрузка запускается отдельно, без параллельного pytest и браузерных тестов.
Сравнение каталога до/после: tests/benchmark_catalog.py, baseline 902edb3,
новый код 599a6b8, отдельная одноразовая копия БД. Замер функции роутера
не включает HTTP/сеть и не равен HTTP-нагрузке.

Пакет содержит копии тестов. Запускать их следует из корня исходного репозитория
на указанном коммите, с настроенным изолированным QA-стендом. Для первого запуска
следуйте README репозитория; .env.qa в архив не входит.

Отзывы реальных участников ещё не получены. Для записи сеанса приложен
uat-feedback.csv; его пустые поля не являются результатами выполненных тестов.

Полный pytest: 176 passed, 0 skipped. Дополнительно: 6 модульных и
4 интеграционных теста; браузерные сценарии — успешно.

Для модульных проверок (из корня репозитория):
```sh
docker compose -f docker-compose.test.yml --env-file .env.qa -p kroy-varvara-nginx-qa exec -T backend sh -c 'cat > /tmp/test_validation.py' < tests/unit/test_validation.py
docker compose -f docker-compose.test.yml --env-file .env.qa -p kroy-varvara-nginx-qa exec -T -e PYTHONPATH=/app backend python /tmp/test_validation.py
```

Отчёт расширен до 20 страниц: 17 снимков приложения. Дополнительный браузерный прогон: ui-screenshots.txt; заказы 104/105, возврат остатка 8 → 7 → 8, pageErrors пуст. Сценарий съёмки: tests/capture_report_screenshots.cjs.
